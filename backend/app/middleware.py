"""Bound request bodies before multipart parsing/spooling."""

from fastapi.responses import JSONResponse


class UploadTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app, limit=55 * 1024**2):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ["POST", "PATCH", "PUT"]:
            return await self.app(scope, receive, send)
        raw = dict(scope.get("headers", [])).get(b"content-length")
        try:
            length = int(raw) if raw else 0
        except ValueError:
            return await JSONResponse({"detail": "잘못된 요청 크기입니다."}, status_code=400)(
                scope, receive, send
            )
        if length > self.limit:
            return await JSONResponse(
                {"detail": "요청 크기 제한(55MB)을 초과했습니다."}, status_code=413
            )(scope, receive, send)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.limit:
                    raise UploadTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except UploadTooLarge:
            await JSONResponse({"detail": "요청 크기 제한(55MB)을 초과했습니다."}, status_code=413)(
                scope, receive, send
            )
