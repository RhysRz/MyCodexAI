"""Small, explicit HTTP hardening controls for the browser-facing application."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.settings import settings


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests before FastAPI parses form or JSON bodies."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    return JSONResponse({"detail": "Request body is too large"}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        return await call_next(request)


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """Require same-origin unsafe browser requests in production.

    The UI is intentionally same-origin and has no cross-origin API clients. Requiring
    Origin is a strong CSRF boundary alongside the Strict, HttpOnly session cookie.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if (
            not settings.is_production
            or request.method not in UNSAFE_METHODS
            or not request.url.path.startswith("/api/")
        ):
            return await call_next(request)

        origin = request.headers.get("origin", "").rstrip("/")
        expected_origin = settings.public_origin.rstrip("/")
        if not origin or origin != expected_origin:
            return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative headers compatible with the bundled same-origin UI."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("Content-Security-Policy", (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'"
        ))
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        # Voice chat and push-to-talk commands are browser features.  Keep them
        # limited to this same-origin application while all unrelated hardware
        # capabilities remain disabled.
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=(), payment=(), usb=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.url.path in {"/", "/remote"} or request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store, max-age=0")
            headers.setdefault("Pragma", "no-cache")
        if settings.force_https:
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.hsts_max_age_seconds}; includeSubDomains",
            )
        return response
