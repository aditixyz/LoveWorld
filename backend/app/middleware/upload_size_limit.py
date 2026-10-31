from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse

from app.core.config import get_settings

_UPLOAD_PATH = "/photos/upload"
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


class _RequestBodyTooLarge(Exception):
    pass


class UploadRequestSizeLimitMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != _UPLOAD_PATH
        ):
            await self.app(scope, receive, send)
            return

        max_body_bytes = (
            get_settings().photo_max_upload_bytes + _MULTIPART_OVERHEAD_BYTES
        )
        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if content_lengths:
            if len(content_lengths) != 1 or not content_lengths[0].isdigit():
                await JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )(scope, receive, send)
                return
            if int(content_lengths[0]) > max_body_bytes:
                await self._too_large(scope, receive, send)
                return

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._too_large(scope, receive, send)

    @staticmethod
    async def _too_large(
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[dict[str, Any]]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        await JSONResponse(
            status_code=413,
            content={"detail": "Photo upload request exceeds the size limit"},
        )(scope, receive, send)
