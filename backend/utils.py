"""
utils.py – Reusable helpers for the CrowdSync backend.

Extracted from main.py to improve testability and separation of concerns.
Each public function has no side-effects on application state, making them
straightforward to unit-test in isolation.
"""

import asyncio
import logging
import random
import re
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "sanitize_input",
    "generate_simulated_status",
    "is_rate_limited",
    "reset_rate_limits",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum requests a single IP may make to the chat endpoint per window.
RATE_LIMIT_REQUESTS: int = 10
#: Sliding-window duration in seconds.
RATE_LIMIT_WINDOW: int = 60

# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

# Pre-compiled for performance; applied in sanitize_input.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to remove only genuinely dangerous content.

    Rather than silently stripping characters (which can corrupt meaningful
    queries such as ``"Gate B/C exit?"`` → ``"Gate BC exit"``), this function:

    1. Strips surrounding whitespace.
    2. Removes HTML/XML-like tags unconditionally (``<script>``, ``<img>``…).
    3. Returns the cleaned string; callers reject if the result is empty.

    Args:
        text: Raw user-supplied string.

    Returns:
        Cleaned string safe to forward to the AI model.
    """
    stripped = text.strip()
    stripped = _HTML_TAG_RE.sub("", stripped).strip()
    return stripped


# ---------------------------------------------------------------------------
# Simulated Stadium Data
# ---------------------------------------------------------------------------

_ANNOUNCEMENTS = [
    "",
    "",
    "",
    "Match ending in 10 minutes — Please prepare to exit.",
    "Halftime starts in 5 minutes! Grab your food fast!",
    "Rain expected in 20 mins, covered seating available at Section 300.",
]


def _gate(name: str) -> dict[str, Any]:
    """Generate a single gate snapshot with density-derived status.

    Status is *derived* from density so the two fields are always consistent:
    - density >= 70 → ``"Red"``   (congested)
    - density >= 40 → ``"Yellow"`` (moderate)
    - density <  40 → ``"Green"``  (clear)
    """
    density = random.randint(10, 100)
    if density >= 70:
        status = "Red"
    elif density >= 40:
        status = "Yellow"
    else:
        status = "Green"
    return {"id": name, "status": status, "density": density}


def generate_simulated_status() -> dict[str, Any]:
    """
    Generate a fresh snapshot of stadium exit and transport conditions.

    Returns:
        Dict with ``gates``, ``transport``, and ``announcement`` keys.
    """
    gates = [_gate(f"Gate {letter}") for letter in "ABCD"]
    transport = [
        {"mode": "Metro", "wait_time": f"{random.randint(5, 30)}m"},
        {"mode": "Cabs",  "wait_time": f"{random.randint(10, 60)}m"},
        {"mode": "Bus",   "wait_time": f"{random.randint(5, 45)}m"},
    ]
    return {
        "gates": gates,
        "transport": transport,
        "announcement": random.choice(_ANNOUNCEMENTS),
    }


# ---------------------------------------------------------------------------
# Rate Limiting (sliding-window, per-IP, async-safe)
# ---------------------------------------------------------------------------

# Maps IP → deque of request timestamps within the current window.
_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = asyncio.Lock()


async def is_rate_limited(ip: str) -> bool:
    """
    Determine whether an IP has exceeded the request rate limit.

    Uses a sliding-window algorithm: only timestamps within the last
    ``RATE_LIMIT_WINDOW`` seconds are counted.  The lock ensures correctness
    under concurrent async requests without blocking the event loop.

    Args:
        ip: The client IP address string.

    Returns:
        ``True`` if the client has exceeded their rate limit, ``False`` otherwise.
    """
    now = time.time()
    async with _rate_limit_lock:
        timestamps = _rate_limit_store[ip]
        # Evict timestamps outside the current window.
        while timestamps and timestamps[0] < now - RATE_LIMIT_WINDOW:
            timestamps.popleft()
        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            logger.warning("Rate limit exceeded for IP: %s", ip)
            return True
        timestamps.append(now)
        return False


def reset_rate_limits() -> None:
    """
    Clear all rate-limit state.

    Intended for use in tests only — never call from production code.
    """
    _rate_limit_store.clear()
