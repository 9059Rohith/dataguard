"""ASGI boundary: reject work before parsing and hold capacity until response completion."""

import anyio
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from dataguard.archive import is_browser_asset
from dataguard.contract_impact import IMPACT_MAX_BYTES, IMPACT_PATH
from dataguard.limits import MAX_BODY_BYTES, check_json_structure
from dataguard.policy_io import POLICY_MAX_BYTES, decode_policy_json
from dataguard.public_demo import PUBLIC_BODY_BYTES, PUBLIC_INVESTIGATE_PATH, check_origin


class RequestGuard:
    def __init__(self, app, *, state, authorize, default_csp):
        self.app = app
        self.state = state
        self.authorize = authorize
        self.default_csp = default_csp

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def protected_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Cache-Control", "no-store")
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Content-Security-Policy", self.default_csp)
            await send(message)

        async def reject(status, message, headers=None):
            await JSONResponse({"detail": message}, status_code=status, headers=headers)(
                scope, receive, protected_send
            )

        path = scope["path"].removeprefix(scope.get("root_path", ""))
        if len(scope["path"]) > 2048 or len(scope.get("query_string", b"")) > 4096:
            await reject(414, "Request target exceeds limit")
            return
        method = scope["method"]
        headers = Headers(scope=scope)
        length = headers.get("content-length")
        if length is not None:
            if not length.isascii() or not length.isdecimal() or len(length) > 12:
                await reject(400, "Invalid Content-Length")
                return
            if int(length) > MAX_BODY_BYTES:
                await reject(413, "Body exceeds 8 MB")
                return
        mutation = method in {"POST", "PUT", "PATCH", "DELETE"}
        public_investigation = method == "POST" and path == PUBLIC_INVESTIGATE_PATH
        public_impact = method == "POST" and path == IMPACT_PATH
        policy_request = path == "/policies/impact"
        if mutation:
            if not (public_investigation or public_impact):
                try:
                    self.authorize(headers.get("authorization"))
                except HTTPException as error:
                    await reject(error.status_code, error.detail, error.headers)
                    return
            else:
                try:
                    check_origin(Request(scope))
                except HTTPException as error:
                    await reject(error.status_code, error.detail, error.headers)
                    return
                public_limit = IMPACT_MAX_BYTES if public_impact else PUBLIC_BODY_BYTES
                if length is not None and int(length) > public_limit:
                    await reject(413, "Public request body exceeds limit")
                    return
            if policy_request and length is not None and int(length) > POLICY_MAX_BYTES:
                await reject(413, "Policy document exceeds 64 KiB")
                return
        elif (length is not None and int(length)) or headers.get("transfer-encoding"):
            await reject(400, "Request bodies are not supported for this method")
            return

        reserved_health = method in {"GET", "HEAD"} and path == "/health"
        limiter = (
            self.state.browser_asset_limiter
            if method in {"GET", "HEAD"} and is_browser_asset(path)
            else self.state.request_limiter
        )
        acquired = False
        try:
            if not reserved_health:
                try:
                    limiter.acquire_nowait()
                    acquired = True
                except anyio.WouldBlock:
                    await reject(503, "Request capacity is busy; retry later", {"Retry-After": "1"})
                    return
            if mutation:
                body = bytearray()
                try:
                    with anyio.fail_after(self.state.body_timeout_seconds):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                return
                            chunk = message.get("body", b"")
                            body_limit = (
                                IMPACT_MAX_BYTES
                                if public_impact
                                else PUBLIC_BODY_BYTES
                                if public_investigation or public_impact
                                else (POLICY_MAX_BYTES if policy_request else MAX_BODY_BYTES)
                            )
                            if len(chunk) > body_limit - len(body):
                                await reject(413, "Body exceeds request limit")
                                return
                            body.extend(chunk)
                            if not message.get("more_body", False):
                                break
                except TimeoutError:
                    await reject(408, "Request body deadline exceeded")
                    return
                raw = bytes(body)
                del body
                try:
                    check_json_structure(raw)
                except ValueError:
                    await reject(413, "JSON nesting or structural limit exceeded")
                    return
                if policy_request or public_impact:
                    try:
                        decode_policy_json(raw)
                    except ValueError:
                        await reject(
                            422,
                            "Invalid public contract request"
                            if public_impact
                            else "Invalid policy request",
                        )
                        return
                replayed = False

                async def bounded_receive():
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return {"type": "http.request", "body": raw, "more_body": False}
                    return await receive()

                await self.app(scope, bounded_receive, protected_send)
            else:
                await self.app(scope, receive, protected_send)
        finally:
            if acquired:
                limiter.release()
