"""
FastAPI backend for CrowdSync.
Handles stadium gate statuses, transport wait times, and AI Concierge chat.
"""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel, Field

from utils import (
    generate_simulated_status,
    is_rate_limited,
    sanitize_input,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Structured JSON logging (compatible with Cloud Logging)
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for Cloud Logging ingestion."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Cache time-to-live in seconds
CACHE_TTL: int = 30
#: Maximum allowed length for a chat message
MAX_MESSAGE_LENGTH: int = 500

# ---------------------------------------------------------------------------
# Application-level metrics counters
# ---------------------------------------------------------------------------

_metrics: dict[str, int] = {
    "request_count": 0,
    "ai_call_count": 0,
    "cache_hit_count": 0,
    "cache_miss_count": 0,
}

# Singleton Gemini client — initialised once at startup via lifespan.
_gemini_client: genai.Client | None = None

# Lock to serialise cache refreshes and prevent redundant Gemini instantiation
# under concurrent async requests.
_status_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Background cache warmer
# ---------------------------------------------------------------------------

async def _cache_warmer() -> None:
    """Proactively refresh the stadium status cache 5 s before TTL expiry."""
    while True:
        try:
            remaining = CACHE_TTL - (time.time() - state.last_update_time)
            sleep_for = max(remaining - 5, 1)
            await asyncio.sleep(sleep_for)
            async with _status_lock:
                state.cached_status = generate_simulated_status()
                state.last_update_time = time.time()
                logger.info({"event": "cache_warmed_proactively"})
        except asyncio.CancelledError:
            break
        except Exception as exc:  # pragma: no cover
            logger.error({"event": "cache_warmer_error", "error": str(exc)})
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise expensive resources once on startup; clean up on shutdown."""
    global _gemini_client

    vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT")

    try:
        kwargs: dict[str, Any] = {"vertexai": True, "location": "us-central1"}
        if vertex_project:
            kwargs["project"] = vertex_project

        _gemini_client = genai.Client(**kwargs)
        logger.info({"event": "gemini_client_initialised", "mode": "vertex_ai"})
    except Exception as e:
        logger.error({"event": "gemini_client_init_failed", "error": str(e)})
        logger.warning({"event": "ai_concierge_fallback_mode"})

    warmer_task = asyncio.create_task(_cache_warmer())
    yield
    warmer_task.cancel()
    await asyncio.gather(warmer_task, return_exceptions=True)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CrowdSync API",
    description="Proactive stadium crowd management system",
    lifespan=lifespan,
)

# Security: CORS origins configurable via env var.
# Set ALLOWED_ORIGINS=* to allow all origins (public Cloud Run deployment).
# Set to a comma-separated list of URLs to restrict to specific origins.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins.strip() == "*":
    _cors_origins = ["*"]
    _cors_credentials = False          # credentials cannot be used with allow_origins=["*"]
else:
    _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)



@app.middleware("http")
async def add_security_and_metrics_headers(request: Request, call_next):
    """Inject security headers and track per-request latency."""
    start = time.perf_counter()
    _metrics["request_count"] += 1
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "frame-src https://www.google.com;"
    )
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    logger.info(
        {"event": "request", "method": request.method,
         "path": request.url.path, "status": response.status_code,
         "latency_ms": elapsed_ms}
    )
    return response


# ---------------------------------------------------------------------------
# State & Caching
# ---------------------------------------------------------------------------

class StadiumState:
    """Holds in-memory cached stadium data for efficient polling responses."""

    def __init__(self) -> None:
        self.cached_status: dict[str, Any] | None = None
        self.last_update_time: float = 0.0


state = StadiumState()


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH, description="User chat message")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI Concierge reply")


class StatusResponse(BaseModel):
    data: dict[str, Any]
    cached: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Ops"])
async def health_check() -> dict[str, str]:
    """Liveness probe for Cloud Run and load-balancer health checks."""
    return {"status": "ok"}


@app.get("/metrics", tags=["Ops"])
async def get_metrics() -> dict[str, Any]:
    """
    Expose runtime operational metrics for monitoring dashboards.

    Returns:
        JSON object with request counts, AI call counts, cache hit/miss
        ratios, and the age of the current status cache.
    """
    cache_age_s = round(time.time() - state.last_update_time, 1) if state.last_update_time else None
    return {
        **_metrics,
        "cache_age_seconds": cache_age_s,
        "cache_ttl_seconds": CACHE_TTL,
    }


@app.get("/api/stadium/status", response_model=StatusResponse, tags=["Stadium"])
async def get_stadium_status() -> StatusResponse:
    """
    Return real-time status of stadium gates and transportation.

    Efficiency: responses are served from a local in-memory cache for
    ``CACHE_TTL`` seconds (currently 30 s) to avoid generating new random
    data on every poll request.

    Concurrency: an ``asyncio.Lock`` is used to serialise cache refreshes,
    preventing multiple concurrent requests from all triggering a refresh
    simultaneously (double-checked locking pattern).
    """
    current_time = time.time()
    # Fast path: serve from cache without acquiring the lock.
    if state.cached_status and (current_time - state.last_update_time < CACHE_TTL):
        logger.debug({"event": "cache_hit"})
        _metrics["cache_hit_count"] += 1
        return StatusResponse(data=state.cached_status, cached=True)

    # Slow path: acquire lock, re-check, then refresh.
    async with _status_lock:
        current_time = time.time()
        if state.cached_status and (current_time - state.last_update_time < CACHE_TTL):
            _metrics["cache_hit_count"] += 1
            return StatusResponse(data=state.cached_status, cached=True)

        new_data = generate_simulated_status()
        state.cached_status = new_data
        state.last_update_time = current_time
        _metrics["cache_miss_count"] += 1
        logger.info({"event": "stadium_status_refreshed"})
        return StatusResponse(data=new_data, cached=False)


@app.post("/api/chat", response_model=ChatResponse, tags=["AI"])
async def chat_concierge(request: ChatRequest, http_request: Request) -> ChatResponse:
    """
    AI Concierge endpoint powered by the Gemini SDK.

    Sanitizes user input before forwarding it to the model. Enforces a
    per-IP sliding-window rate limit (10 req / 60 s). When no Vertex AI
    client is configured, a deterministic fallback reply is returned so the
    frontend remains functional during local development without credentials.

    Args:
        request: Validated ``ChatRequest`` containing the user message.
        http_request: The raw FastAPI ``Request`` used for IP extraction.

    Returns:
        ``ChatResponse`` with the model's reply.

    Raises:
        HTTPException 400: If the sanitized message is empty.
        HTTPException 429: If the client IP has exceeded the rate limit.
        HTTPException 500: If the Gemini API call fails unexpectedly.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    if await is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending another message.")

    sanitized_message = sanitize_input(request.message)
    if not sanitized_message:
        raise HTTPException(status_code=400, detail="Message is empty after sanitization.")

    if _gemini_client is None:
        logger.warning({"event": "gemini_fallback", "reason": "client_not_initialized"})
        return ChatResponse(
            reply=f"[Demo] You asked: '{sanitized_message}'. Vertex AI is not configured."
        )

    try:
        # Inject real-time stadium context directly into the prompt.
        current_status = state.cached_status or generate_simulated_status()

        gate_info = ", ".join(
            [f"{g['id']}: {g['status']} (Density: {g['density']}%)" for g in current_status.get("gates", [])]
        )
        transport_info = ", ".join(
            [f"{t['mode']}: {t['wait_time']}" for t in current_status.get("transport", [])]
        )

        prompt = (
            "You are a strictly constrained, helpful AI Concierge for Stadium Flow. "
            "Use the following real-time stadium context to answer the user's query intelligently:\n"
            f"[LIVE GATES]: {gate_info}\n"
            f"[LIVE TRANSPORT]: {transport_info}\n"
            "[STADIUM KNOWLEDGE]:\n"
            "- Food Counters: Burger Stand (Sec 101, Gate A), Vegan Delights (Sec 205, Gate B), Pizza Hub (Sec 310, Gate C), Drinks/Beer (Near Gate D).\n"
            "- First Aid is located at Section 112, Section 340, and adjacent to the main concourse near Gate A.\n"
            "- Restrooms: Located near all gates, and Sections 105, 210, 315.\n"
            "- Parking: North Lot (Gates A/B), East Lot (Gate C), South VIP (Gate D).\n"
            "- Merchandise: Main store at Gate B, kiosks at Gates A and C.\n"
            "- For users looking to exit or find a gate, ALWAYS recommend gates that are 'Green' (low density).\n"
            "- Mention that proceeding to a 'Green' gate grants a 10% food/beverage discount!\n"
            "If the user asks something completely unrelated to the stadium (e.g. coding, general facts), politely decline.\n\n"
            f"User query: {sanitized_message}\nConcierge:"
        )
        _metrics["ai_call_count"] += 1
        response = await _gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        reply_text = response.text if response.text else "I'm sorry, I couldn't process that request."
        logger.info({"event": "gemini_response_generated"})
        return ChatResponse(reply=reply_text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error({"event": "gemini_api_error", "error_type": type(exc).__name__, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"AI Error ({type(exc).__name__}): {str(exc)}")


# ---------------------------------------------------------------------------
# Serve Frontend Assets (For Docker/Cloud Run)
# ---------------------------------------------------------------------------

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{catchall:path}")
    async def serve_frontend(catchall: str):
        """Serve the React SPA; validates path stays within the dist directory."""
        requested = os.path.realpath(os.path.join(frontend_dist, catchall))
        if not requested.startswith(os.path.realpath(frontend_dist)):
            raise HTTPException(status_code=400, detail="Invalid path.")
        if os.path.isfile(requested):
            return FileResponse(requested)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
