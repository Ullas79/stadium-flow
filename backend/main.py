"""
FastAPI backend for CrowdSync.
Handles stadium gate statuses, transport wait times, and AI Concierge chat.
"""
import asyncio
import os
import time
import random
import re
import logging
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Cache time-to-live in seconds
CACHE_TTL: int = 30
# Maximum allowed length for a chat message
MAX_MESSAGE_LENGTH: int = 500

# Configure Google Gemini
GENAI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Singleton Gemini client — initialised once at startup via lifespan.
_gemini_client: genai.Client | None = None

# Lock to serialise cache refreshes and prevent redundant Gemini instantiation
# under concurrent async requests.
_status_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise expensive resources once on startup; clean up on shutdown."""
    global _gemini_client
    
    # Automatically use Vertex AI since we're deploying to Google Cloud!
    vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT", "stadiumflow-493912")
    
    try:
        # We explicitly set vertexai=True. No API keys needed—it uses Cloud Run's native service account!
        _gemini_client = genai.Client(vertexai=True, project=vertex_project, location="us-central1")
        logger.info(f"Gemini client initialised securely via Vertex AI on {vertex_project}!")
    except Exception as e:
        logger.warning(f"Failed to initialize Vertex AI client ({e}). Checking for fallback API key...")
        if GENAI_API_KEY:
            _gemini_client = genai.Client(api_key=GENAI_API_KEY)
            logger.info("Fell back to standard Gemini client via API Key.")
        else:
            logger.warning("No authentication provided — AI Concierge will use fallback responses.")
    yield
    # Shutdown: nothing to clean up for the Gemini SDK.


app = FastAPI(
    title="CrowdSync API",
    description="Proactive stadium crowd management system",
    lifespan=lifespan,
)

# Security: Restrict CORS to known origins and explicit headers only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject basic web security headers for hardened Cloud Run deployment."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- State & Caching ---
class StadiumState:
    """Holds in-memory cached stadium data for efficient polling responses."""

    def __init__(self) -> None:
        self.cached_status: dict[str, Any] | None = None
        self.last_update_time: float = 0.0


state = StadiumState()


# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH, description="User chat message")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI Concierge reply")


class StatusResponse(BaseModel):
    data: dict[str, Any]
    cached: bool


# Valid characters accepted in a chat message.
# Allows letters, digits, spaces and common punctuation used in stadium queries.
_SAFE_MESSAGE_RE = re.compile(r"^[\w\s.,!?'\"@/:()&#\-]+$")


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to remove only genuinely dangerous content.

    Rather than silently stripping characters (which can corrupt meaningful
    queries such as "Gate B/C exit?" → "Gate BC exit"), this function:
      1. Strips surrounding whitespace.
      2. Removes HTML/XML-like tags unconditionally.
      3. Returns the cleaned string; callers reject empty results.

    Args:
        text: Raw user-supplied string.

    Returns:
        Cleaned string safe to forward to the AI model.
    """
    stripped = text.strip()
    # Remove HTML/XML tags (catches <script>, <img>, etc.)
    stripped = re.sub(r"<[^>]+>", "", stripped).strip()
    return stripped


def generate_simulated_status() -> dict[str, Any]:
    """
    Generate a fresh snapshot of stadium exit and transport conditions.

    Density values are generated first, then the status colour is *derived*
    from density so the two fields are always consistent:
        - density >= 70  → Red   (congested)
        - density >= 40  → Yellow (moderate)
        - density <  40  → Green  (clear)

    Returns:
        Dict with ``gates`` and ``transport`` lists.
    """
    def _gate(name: str) -> dict[str, Any]:
        density = random.randint(10, 100)
        if density >= 70:
            status = "Red"
        elif density >= 40:
            status = "Yellow"
        else:
            status = "Green"
        return {"id": name, "status": status, "density": density}

    gates = [_gate(f"Gate {letter}") for letter in "ABCD"]
    transport = [
        {"mode": "Metro", "wait_time": f"{random.randint(5, 30)}m"},
        {"mode": "Cabs",  "wait_time": f"{random.randint(10, 60)}m"},
        {"mode": "Bus",   "wait_time": f"{random.randint(5, 45)}m"},
    ]
    return {"gates": gates, "transport": transport}


@app.get("/health", tags=["Ops"])
async def health_check() -> dict[str, str]:
    """Liveness probe for Cloud Run and load-balancer health checks."""
    return {"status": "ok"}


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
        logger.debug("Serving cached stadium status")
        return StatusResponse(data=state.cached_status, cached=True)

    # Slow path: acquire lock, re-check, then refresh.
    async with _status_lock:
        current_time = time.time()
        if state.cached_status and (current_time - state.last_update_time < CACHE_TTL):
            # Another coroutine refreshed the cache while we were waiting.
            return StatusResponse(data=state.cached_status, cached=True)

        new_data = generate_simulated_status()
        state.cached_status = new_data
        state.last_update_time = current_time
        logger.info("Stadium status refreshed")
        return StatusResponse(data=new_data, cached=False)


@app.post("/api/chat", response_model=ChatResponse, tags=["AI"])
async def chat_concierge(request: ChatRequest) -> ChatResponse:
    """
    AI Concierge endpoint powered by the Gemini SDK.

    Sanitizes user input before forwarding it to the model. When no API key
    is present a deterministic fallback reply is returned so the frontend
    remains functional during local development without credentials.

    Args:
        request: Validated ``ChatRequest`` containing the user message.

    Returns:
        ``ChatResponse`` with the model's reply.

    Raises:
        HTTPException 400: If the sanitized message is empty.
        HTTPException 500: If the Gemini API call fails unexpectedly.
    """
    sanitized_message = sanitize_input(request.message)
    if not sanitized_message:
        raise HTTPException(status_code=400, detail="Message is empty after sanitization.")

    if _gemini_client is None:
        logger.warning("Vertex/Gemini client not initialized — returning simulated response.")
        return ChatResponse(
            reply=f"[Demo] You asked: '{sanitized_message}'. Vertex AI is not configured."
        )

    try:
        # Inject real-time stadium context directly into the prompt!
        current_status = state.cached_status or generate_simulated_status()
        
        gate_info = ", ".join([f"{g['id']}: {g['status']} (Density: {g['density']}%)" for g in current_status.get("gates", [])])
        transport_info = ", ".join([f"{t['mode']}: {t['wait_time']}" for t in current_status.get("transport", [])])
        
        prompt = (
            "You are a strictly constrained, helpful AI Concierge for Stadium Flow. "
            "Use the following real-time stadium context to answer the user's query intelligently:\n"
            f"[LIVE GATES]: {gate_info}\n"
            f"[LIVE TRANSPORT]: {transport_info}\n"
            "[STADIUM KNOWLEDGE]:\n"
            "- First Aid is located at Section 112, Section 340, and adjacent to the main concourse near Gate A.\n"
            "- For users looking to exit or find a gate, ALWAYS recommend the gates that are 'Green' (low density).\n"
            "- Mention that proceeding to a 'Green' gate grants a 10% food/beverage discount!\n"
            "If the user asks something completely unrelated to the stadium (e.g. coding, general facts), politely decline.\n\n"
            f"User query: {sanitized_message}\nConcierge:"
        )
        response = await _gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        reply_text = response.text if response.text else "I'm sorry, I couldn't process that request."
        logger.info("Gemini response generated successfully.")
        return ChatResponse(reply=reply_text)
    except HTTPException:
        raise  # Let FastAPI handle these as-is
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(status_code=500, detail=f"AI Error ({type(exc).__name__}): {str(exc)}")


# --- Serve Frontend Assets (For Docker/Cloud Run) ---
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{catchall:path}")
    async def serve_frontend(catchall: str):
        """Serve the React SPA; validates path stays within the dist directory."""
        # Resolve to an absolute path and ensure it hasn't escaped frontend_dist
        requested = os.path.realpath(os.path.join(frontend_dist, catchall))
        if not requested.startswith(os.path.realpath(frontend_dist)):
            raise HTTPException(status_code=400, detail="Invalid path.")
        if os.path.isfile(requested):
            return FileResponse(requested)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
