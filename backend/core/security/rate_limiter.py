"""
In-memory rate limiter — sliding-window algorithm using collections.deque.

Usage:
    limiter = RateLimiter()
    allowed = limiter.check("192.168.1.1", limit=60, window=60)
    if not allowed:
        raise HTTPException(429, "Rate limit exceeded")

Thread-safety: deque operations are GIL-protected in CPython; sufficient for
single-process FastAPI/uvicorn. For multi-worker deployments use Redis instead.
"""
from __future__ import annotations

import time
import threading
from collections import deque, defaultdict
from typing import Dict


class RateLimiter:
    """
    Sliding-window in-memory rate limiter.

    Args:
        default_limit:  Maximum requests per window (default 60).
        default_window: Window size in seconds (default 60).
    """

    def __init__(self, default_limit: int = 60, default_window: int = 60, limit: int = None, window: int = None):
        self.default_limit = limit if limit is not None else default_limit
        self.default_window = window if window is not None else default_window
        # key → deque of timestamps (float)
        self._windows: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int = None, window: int = None) -> bool:
        """
        Return True if the request is within the rate limit, False otherwise.

        Args:
            key:    Unique identifier for the rate-limited entity (e.g. IP address).
            limit:  Max requests allowed in the window (overrides instance default).
            window: Window duration in seconds (overrides instance default).
        """
        limit = limit if limit is not None else self.default_limit
        window = window if window is not None else self.default_window
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            dq = self._windows[key]
            # Evict expired timestamps
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) >= limit:
                return False   # Rate limit exceeded

            dq.append(now)
            return True

    def reset(self, key: str) -> None:
        """Clear the window for a specific key (e.g. after a successful auth)."""
        with self._lock:
            self._windows.pop(key, None)

    def status(self, key: str, limit: int = None, window: int = None) -> dict:
        """
        Return rate limit status for a key without consuming a slot.
        """
        limit = limit if limit is not None else self.default_limit
        window = window if window is not None else self.default_window
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            dq = self._windows.get(key, deque())
            count = sum(1 for ts in dq if ts >= cutoff)
            remaining = max(0, limit - count)
            return {
                "key": key,
                "limit": limit,
                "window": window,
                "used": count,
                "remaining": remaining,
                "allowed": count < limit,
            }


# Module-level singleton — import and use directly
rate_limiter = RateLimiter(default_limit=60, default_window=60)
