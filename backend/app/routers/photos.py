import logging
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.authorization import (
    assign_resource_owner,
    require_resource_access,
    require_resource_owner,
)
from app.auth.dependencies import get_current_user
from app.core.config import Settings, get_settings
from app.db.errors import log_database_error
from app.db.models import Photo, User
from app.db.session import get_db
from app.schemas.photo import (
    PhotoCreate,
    PhotoPage,
    PhotoResponse,
    PhotoUpdate,
    PhotoVisibility,
)
from app.services.photo_images import InvalidPhotoImage, validate_and_make_thumbnail
from app.services.photo_storage import (
    LocalPhotoStorage,
    PhotoStorage,
    PhotoStorageError,
)

router = APIRouter(prefix="/photos", tags=["photos"])
logger = logging.getLogger(__name__)
DatabaseSession = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(get_current_user)]
PhotoSettings = Annotated[Settings, Depends(get_settings)]

_UPLOAD_CHUNK_SIZE = 64 * 1024


def get_photo_storage(settings: PhotoSettings) -> PhotoStorage:
    return LocalPhotoStorage(settings.photo_storage_dir)


PhotoStorageDependency = Annotated[PhotoStorage, Depends(get_photo_storage)]


def _database_unavailable(
    db: Session,
    operation: str,
    error: SQLAlchemyError,
) -> HTTPException:
    log_database_error(logger, operation, error)
    try:
        db.rollback()
    except SQLAlchemyError as rollback_error:
        log_database_error(logger, f"{operation}.rollback", rollback_error)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database operation unavailable",
    )


def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Photo storage unavailable",
    )


def _safe_display_filename(filename: str | None) -> str:
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A valid original filename is required",
        )
    display_name = filename.strip()
    if (
        not display_name
        or display_name in {".", ".."}
        or "/" in display_name
        or "\\" in display_name
        or len(display_name) > 255
        or any(
            ord(character) < 32 or ord(character) == 127
            for character in display_name
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A valid original filename is required",
        )
    return display_name


async def _read_limited_upload(upload: UploadFile, max_bytes: int) -> bytes:
    contents = bytearray()
    while True:
        chunk = await upload.read(min(_UPLOAD_CHUNK_SIZE, max_bytes + 1 - len(contents)))
        if not chunk:
            break
        contents.extend(chunk)
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Photo upload exceeds the size limit",
            )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Image upload must not be empty",
        )
    return bytes(contents)


def _image_response(content: bytes, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/upload",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    file: Annotated[UploadFile, File()],
    request: Request,
    db: DatabaseSession,
    user: AuthenticatedUser,
    storage: PhotoStorageDependency,
    settings: PhotoSettings,
    caption: Annotated[str | None, Form(max_length=5000)] = None,
    visibility: Annotated[PhotoVisibility, Form()] = "private",
) -> PhotoResponse:
    form = await request.form()
    allowed_fields = {"file", "caption", "visibility"}
    if (
        set(form.keys()) - allowed_fields
        or len(form.getlist("file")) != 1
        or len(form.getlist("caption")) > 1
        or len(form.getlist("visibility")) > 1
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unexpected or duplicate photo upload fields",
        )

    filename = _safe_display_filename(file.filename)
    try:
        validated_metadata = PhotoCreate(
            original_filename=filename,
            caption=caption,
            visibility=visibility,
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid photo metadata",
        ) from None

    try:
        contents = await _read_limited_upload(file, settings.photo_max_upload_bytes)
    finally:
        await file.close()

    try:
        image = validate_and_make_thumbnail(contents)
    except InvalidPhotoImage as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None

    storage_key = f"{uuid4().hex}.{image.extension}"
    try:
        storage.store(storage_key, image.original, image.thumbnail)
    except PhotoStorageError:
        logger.error("Photo upload could not be stored")
        try:
            storage.delete(storage_key)
        except PhotoStorageError:
            logger.error("Photo files could not be cleaned up after a storage error")
        raise _storage_unavailable() from None

    photo = assign_resource_owner(
        Photo(
            **validated_metadata.model_dump(),
            storage_key=storage_key,
        ),
        user,
    )
    try:
        db.add(photo)
        db.flush()
        db.refresh(photo)
        db.commit()
    except SQLAlchemyError as error:
        database_error = _database_unavailable(db, "photo.upload", error)
        try:
            storage.delete(storage_key)
        except PhotoStorageError:
            logger.error("Photo files could not be cleaned up after a database error")
        raise database_error from None
    return PhotoResponse.model_validate(photo)


@router.post(
    "",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_photo(
    photo_data: PhotoCreate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> PhotoResponse:
    photo = assign_resource_owner(
        Photo(
            **photo_data.model_dump(),
            storage_key=uuid4().hex,
        ),
        user,
    )
    try:
        db.add(photo)
        db.commit()
        db.refresh(photo)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.create", error) from None
    return PhotoResponse.model_validate(photo)


@router.get("", response_model=PhotoPage)
def list_photos(
    db: DatabaseSession,
    user: AuthenticatedUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PhotoPage:
    access_filter = or_(
        Photo.uploaded_by == user.id,
        Photo.visibility == "shared",
    )
    try:
        total = db.scalar(
            select(func.count()).select_from(Photo).where(access_filter)
        )
        photos = db.scalars(
            select(Photo)
            .where(access_filter)
            .order_by(Photo.created_at.desc(), Photo.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.list", error) from None
    return PhotoPage(
        items=[PhotoResponse.model_validate(photo) for photo in photos],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{photo_id}", response_model=PhotoResponse)
def get_photo(
    photo_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> PhotoResponse:
    try:
        photo = require_resource_access(db.get(Photo, photo_id), user)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.read", error) from None
    return PhotoResponse.model_validate(photo)


@router.get("/{photo_id}/image")
def get_photo_image(
    photo_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
    storage: PhotoStorageDependency,
) -> Response:
    try:
        photo = require_resource_access(db.get(Photo, photo_id), user)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.image_read", error) from None
    try:
        stored_image = storage.read_original(photo.storage_key)
    except PhotoStorageError:
        logger.error("Photo image could not be read from private storage")
        raise _storage_unavailable() from None
    if stored_image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    content, media_type = stored_image
    return _image_response(content, media_type)


@router.get("/{photo_id}/thumbnail")
def get_photo_thumbnail(
    photo_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
    storage: PhotoStorageDependency,
) -> Response:
    try:
        photo = require_resource_access(db.get(Photo, photo_id), user)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.thumbnail_read", error) from None
    try:
        thumbnail = storage.read_thumbnail(photo.storage_key)
    except PhotoStorageError:
        logger.error("Photo thumbnail could not be read from private storage")
        raise _storage_unavailable() from None
    if thumbnail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    return _image_response(thumbnail, "image/webp")


@router.patch("/{photo_id}", response_model=PhotoResponse)
def update_photo(
    photo_id: int,
    photo_data: PhotoUpdate,
    db: DatabaseSession,
    user: AuthenticatedUser,
) -> PhotoResponse:
    try:
        photo = require_resource_owner(db.get(Photo, photo_id), user)
        for field, value in photo_data.model_dump(exclude_unset=True).items():
            setattr(photo, field, value)
        db.commit()
        db.refresh(photo)
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.update", error) from None
    return PhotoResponse.model_validate(photo)


@router.delete(
    "/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_photo(
    photo_id: int,
    db: DatabaseSession,
    user: AuthenticatedUser,
    storage: PhotoStorageDependency,
) -> Response:
    try:
        photo = require_resource_owner(db.get(Photo, photo_id), user)
        storage_key = photo.storage_key
        db.delete(photo)
        db.commit()
    except SQLAlchemyError as error:
        raise _database_unavailable(db, "photo.delete", error) from None
    try:
        storage.delete(storage_key)
    except PhotoStorageError:
        logger.error("Photo metadata was deleted but file cleanup was incomplete")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo deletion completed with incomplete file cleanup",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
