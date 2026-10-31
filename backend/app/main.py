from fastapi import FastAPI

from app.middleware.upload_size_limit import UploadRequestSizeLimitMiddleware
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.love_notes import router as love_notes_router
from app.routers.memories import router as memories_router
from app.routers.photos import router as photos_router
from app.routers.surprises import router as surprises_router
from app.routers.timeline import router as timeline_router

app = FastAPI(
    title="LoveWorld Backend API",
    description="Private backend API for LoveWorld.",
)
app.add_middleware(UploadRequestSizeLimitMiddleware)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(love_notes_router)
app.include_router(memories_router)
app.include_router(photos_router)
app.include_router(surprises_router)
app.include_router(timeline_router)
