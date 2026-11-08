from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException


class PayloadTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Request exceeds the upload limit.")


class BodyLimitMiddleware:
    """Bound received bytes even when no Content-Length is sent."""
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        total = 0
        started = False
        limit = min(self.limit, 128 * 1024) if "/signals" in scope.get("path", "") else self.limit

        async def bounded_receive():
            nonlocal total
            event = await receive()
            if event["type"] == "http.request":
                total += len(event.get("body", b""))
                if total > limit:
                    raise PayloadTooLarge()
            return event

        async def tracked_send(event):
            nonlocal started
            if event["type"] == "http.response.start":
                started = True
            await send(event)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except PayloadTooLarge:
            if not started:
                await JSONResponse({"detail": "Request exceeds the upload limit."}, status_code=413)(scope, receive, send)
