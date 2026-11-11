"""
AbuseGuardMiddleware — application-level burst / abuse detection.

⚠️  IMPORTANT LIMITATION — PROCESS-LOCAL CACHE:
    This middleware uses Django's LocMemCache, which is **process-local**.
    In a multi-worker deployment (e.g. gunicorn with 2+ workers) each
    worker maintains an independent counter.  A client can therefore
    receive up to `ABUSE_BURST_LIMIT * N_WORKERS` requests before any
    single worker blocks them.

    This is an *application-level* control, **not** a distributed rate
    limit.  For a truly distributed limit you would need:
      • A Redis-backed cache (e.g. django-redis) shared by all workers, OR
      • Vercel Edge Middleware / a CDN-layer WAF rule applied before the
        request reaches any backend process.

    Despite this limitation, the middleware still provides meaningful
    protection against naive single-connection burst attacks targeting
    the same worker process, and adds a second layer of defence on top
    of DRF's per-view throttles.
"""

import json
import logging
import time
from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

log = logging.getLogger(__name__)

# Expensive endpoints that this guard protects.
_GUARDED_PATHS = {"/api/analyze", "/api/heatmap"}

_CACHE_PREFIX = "abuse_guard:"


def _get_client_ip(request: HttpRequest) -> str:
    """
    Return the client IP address.

    When NUM_PROXIES > 0 (default 1 in production behind a reverse proxy),
    we trust X-Forwarded-For but take the Nth-from-right address — not the
    leftmost — to avoid spoofing.  The leftmost entry in X-Forwarded-For
    is fully controlled by the client and must NEVER be trusted for
    security decisions.

    With NUM_PROXIES == 0 we fall back to REMOTE_ADDR directly.
    """
    num_proxies: int = getattr(settings, "NUM_PROXIES", 1)
    xff: str = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if num_proxies > 0 and xff:
        # XFF: "client, proxy1, proxy2, ... proxyN"
        # We want the address added by the Nth-from-right trusted proxy,
        # i.e. index -(num_proxies) from the end (0-based).
        parts = [p.strip() for p in xff.split(",")]
        idx = max(len(parts) - num_proxies, 0)
        return parts[idx]
    return request.META.get("REMOTE_ADDR", "unknown")


def _safe_ip_for_log(ip: str) -> str:
    """Return IP suitable for logging — never log full token/key fragments."""
    # Truncate to avoid accidental logging of tokens that might look like IPs.
    return ip[:45]  # IPv6 max is 39 chars; 45 gives a small safety margin


class AbuseGuardMiddleware:
    """
    Middleware that tracks per-IP request counts in LocMemCache and
    temporarily blocks an IP when it exceeds a configurable burst
    threshold within a rolling time window.

    Configuration (via Django settings / environment variables):
        ABUSE_BURST_LIMIT  — max requests per window before block (default 30)
        ABUSE_WINDOW_S     — rolling window size in seconds (default 60)
        ABUSE_BLOCK_S      — temporary block duration in seconds (default 300)

    Returns HTTP 429 with a Retry-After header and a JSON body matching
    the application's standard error envelope when a block is active.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Only guard the expensive endpoints.
        if request.path not in _GUARDED_PATHS:
            return self.get_response(request)

        burst_limit: int = getattr(settings, "ABUSE_BURST_LIMIT", 30)
        window_s: int = getattr(settings, "ABUSE_WINDOW_S", 60)
        block_s: int = getattr(settings, "ABUSE_BLOCK_S", 300)

        client_ip = _get_client_ip(request)
        safe_ip = _safe_ip_for_log(client_ip)

        block_key = f"{_CACHE_PREFIX}block:{client_ip}"
        count_key = f"{_CACHE_PREFIX}count:{client_ip}"
        window_key = f"{_CACHE_PREFIX}window_start:{client_ip}"

        # ── Check for active block ──────────────────────────────────────────
        if cache.get(block_key):
            log.warning(
                "AbuseGuard: blocked request from %s to %s",
                safe_ip,
                request.path,
            )
            return _too_many_response(block_s)

        # ── Rolling-window counter ──────────────────────────────────────────
        now = time.monotonic()
        window_start = cache.get(window_key)

        if window_start is None or (now - window_start) >= window_s:
            # Start a fresh window.
            cache.set(window_key, now, timeout=window_s + 1)
            cache.set(count_key, 1, timeout=window_s + 1)
            count = 1
        else:
            count = cache.incr(count_key) if cache.get(count_key) is not None else 1

        if count > burst_limit:
            # Activate temporary block; do NOT log any request body content.
            cache.set(block_key, 1, timeout=block_s)
            log.warning(
                "AbuseGuard: temporary %ds block activated for %s (burst=%d on %s)",
                block_s,
                safe_ip,
                count,
                request.path,
            )
            return _too_many_response(block_s)

        return self.get_response(request)


def _too_many_response(retry_after_s: int) -> HttpResponse:
    body = json.dumps({
        "error": {
            "code": "rate_limited",
            "message": "Too many requests. Please try again later.",
        }
    })
    response = HttpResponse(body, content_type="application/json", status=429)
    response["Retry-After"] = str(retry_after_s)
    return response
