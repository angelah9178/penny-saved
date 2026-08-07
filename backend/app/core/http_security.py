"""Public HTTP trust-boundary middleware."""

from __future__ import annotations

from collections.abc import Iterable
from ipaddress import ip_address, ip_network

from app.core.config import AppEnvironment
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _safe_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


class RequestBodyTooLargeError(Exception):
    """Raised internally when a streamed request crosses the configured limit."""


class RequestBodyLimitMiddleware:
    """Reject declared and streamed request bodies above one bounded size."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_length = Headers(scope=scope).get("content-length")
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                await _safe_error(400, "invalid_content_length", "Content-Length is invalid.")(
                    scope, receive, send
                )
                return
            if content_length < 0:
                await _safe_error(400, "invalid_content_length", "Content-Length is invalid.")(
                    scope, receive, send
                )
                return
            if content_length > self.max_bytes:
                await _safe_error(413, "payload_too_large", "The request body is too large.")(
                    scope, receive, send
                )
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLargeError:
            await _safe_error(413, "payload_too_large", "The request body is too large.")(
                scope, receive, send
            )


class TrustedProxyMiddleware:
    """Honor forwarding metadata only when the socket peer is explicitly trusted."""

    def __init__(self, app: ASGIApp, trusted_networks: Iterable[str]) -> None:
        self.app = app
        self.trusted_networks = tuple(ip_network(value) for value in trusted_networks)

    def _is_trusted(self, value: str) -> bool:
        try:
            address = ip_address(value)
        except ValueError:
            return False
        return any(address in network for network in self.trusted_networks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.trusted_networks:
            await self.app(scope, receive, send)
            return

        direct_client = scope.get("client")
        if direct_client is None or not self._is_trusted(direct_client[0]):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        forwarded_for = headers.get("x-forwarded-for")
        forwarded_proto = headers.get("x-forwarded-proto")
        if forwarded_for:
            chain = [item.strip() for item in forwarded_for.split(",")]
            try:
                addresses = [str(ip_address(item)) for item in chain]
            except ValueError:
                await _safe_error(
                    400, "invalid_forwarded_headers", "Forwarding metadata is invalid."
                )(scope, receive, send)
                return
            resolved = addresses[0]
            for candidate in reversed(addresses):
                if not self._is_trusted(candidate):
                    resolved = candidate
                    break
            scope["client"] = (resolved, direct_client[1])

        if forwarded_proto:
            normalized_proto = forwarded_proto.strip().lower()
            if "," in normalized_proto or normalized_proto not in {"http", "https"}:
                await _safe_error(
                    400, "invalid_forwarded_headers", "Forwarding metadata is invalid."
                )(scope, receive, send)
                return
            scope["scheme"] = normalized_proto

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Apply conservative response headers, including HSTS only for production HTTPS."""

    def __init__(self, app: ASGIApp, environment: AppEnvironment) -> None:
        self.app = app
        self.production = environment is AppEnvironment.PRODUCTION

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
                if scope.get("path", "").startswith("/api"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'; "
                        "base-uri 'none'; form-action 'none'"
                    )
                if self.production and scope.get("scheme") == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)
