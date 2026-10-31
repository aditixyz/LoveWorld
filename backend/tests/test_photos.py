import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
import struct
import tempfile
from typing import Any
from uuid import uuid4
import zlib

import jwt
import pytest
from httpx import ASGITransport, AsyncClient, Response
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.db.base import Base
from app.db.models import Photo, User
from app.db.session import get_db
from app.main import app
from app.routers.photos import get_photo_storage
from app.services.photo_storage import LocalPhotoStorage

TEST_SECRET = "photo-api-test-secret-with-enough-entropy"


@pytest.fixture
def photo_context() -> Iterator[tuple[Session, User, User, Settings]]:
    temp_storage = tempfile.TemporaryDirectory()
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    owner = User(
        account_slot=1,
        username="photo-owner",
        password_hash=hash_password("owner-password-for-tests"),
        display_name="Photo Owner",
    )
    other_user = User(
        account_slot=2,
        username="photo-reader",
        password_hash=hash_password("reader-password-for-tests"),
        display_name="Photo Reader",
    )
    db.add_all([owner, other_user])
    db.commit()
    db.refresh(owner)
    db.refresh(other_user)
    settings = Settings(
        _env_file=None,
        app_environment="test",
        jwt_secret=TEST_SECRET,
        photo_storage_dir=Path(temp_storage.name),
    )

    def override_db() -> Iterator[Session]:
        yield db

    from app.core.config import get_settings

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_photo_storage] = lambda: LocalPhotoStorage(
        settings.photo_storage_dir
    )
    yield db, owner, other_user, settings
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
    temp_storage.cleanup()


def _request(
    method: str,
    path: str,
    token: str | None = None,
    **kwargs: Any,
) -> Response:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    async def send() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(send())


def _token(user: User, settings: Settings) -> str:
    return create_access_token(user.id, settings)


def _create_photo(
    db: Session,
    owner: User,
    filename: str,
    visibility: str = "private",
    caption: str | None = None,
) -> Photo:
    photo = Photo(
        original_filename=filename,
        storage_key=uuid4().hex,
        caption=caption,
        visibility=visibility,
        uploaded_by=owner.id,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def _image_bytes(
    image_format: str = "JPEG",
    size: tuple[int, int] = (32, 24),
) -> bytes:
    image = Image.new("RGB", size, (120, 80, 200))
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _png_dimensions_header(width: int, height: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(name + data)
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IEND", b"")
    )


def _upload(
    token: str,
    image: bytes,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
    **data: str,
) -> Response:
    return _request(
        "POST",
        "/photos/upload",
        token=token,
        files={"file": (filename, image, content_type)},
        data=data,
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/photos"),
        ("GET", "/photos"),
        ("GET", "/photos/1"),
        ("PATCH", "/photos/1"),
        ("DELETE", "/photos/1"),
        ("GET", "/photos/1/image"),
        ("GET", "/photos/1/thumbnail"),
    ],
)
def test_photo_routes_require_authentication(
    photo_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, *_ = photo_context

    response = _request(
        method,
        path,
        json={"original_filename": "unauthenticated.jpg"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


@pytest.mark.parametrize("token_kind", ["malformed", "expired"])
def test_photo_routes_reject_invalid_or_expired_tokens(
    photo_context: tuple[Session, User, User, Settings],
    token_kind: str,
) -> None:
    _, owner, _, settings = photo_context
    if token_kind == "malformed":
        token = "not-a-valid-token"
    else:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(owner.id),
                "iat": now - timedelta(minutes=2),
                "exp": now - timedelta(minutes=1),
                "jti": "expired-photo-token",
            },
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    response = _request("GET", "/photos", token=token)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/photos"),
        ("GET", "/photos"),
        ("GET", "/photos/1"),
        ("PATCH", "/photos/1"),
        ("DELETE", "/photos/1"),
        ("GET", "/photos/1/image"),
        ("GET", "/photos/1/thumbnail"),
    ],
)
def test_photo_routes_reject_inactive_users(
    photo_context: tuple[Session, User, User, Settings],
    method: str,
    path: str,
) -> None:
    db, owner, _, settings = photo_context
    owner.is_active = False
    db.commit()

    response = _request(
        method,
        path,
        token=_token(owner, settings),
        json={"original_filename": "inactive.jpg"},
    )

    assert response.status_code == 401
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


def test_create_assigns_owner_defaults_private_and_hides_storage_key(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context

    response = _request(
        "POST",
        "/photos",
        token=_token(owner, settings),
        json={
            "original_filename": "  our-day.jpg  ",
            "caption": "  A favorite moment  ",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["original_filename"] == "our-day.jpg"
    assert result["caption"] == "A favorite moment"
    assert result["uploaded_by"] == owner.id
    assert result["visibility"] == "private"
    assert "storage_key" not in result
    stored = db.scalar(select(Photo))
    assert stored is not None
    assert stored.uploaded_by == owner.id
    assert stored.storage_key
    assert db.scalar(select(func.count()).select_from(Photo)) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"original_filename": ""},
        {"original_filename": "   "},
        {"original_filename": "x" * 256},
        {"original_filename": "valid.jpg", "caption": "   "},
        {"original_filename": "valid.jpg", "caption": "x" * 5001},
        {"original_filename": "valid.jpg", "visibility": "public"},
        {"original_filename": "valid.jpg", "created_by": 2},
        {"original_filename": "valid.jpg", "owner_id": 2},
        {"original_filename": "valid.jpg", "uploaded_by": 2},
        {"original_filename": "valid.jpg", "storage_key": "client/path"},
    ],
)
def test_create_rejects_invalid_or_unexpected_fields(
    photo_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    db, owner, _, settings = photo_context

    response = _request(
        "POST",
        "/photos",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


def test_owner_can_read_private_photo_and_other_user_cannot(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    photo = _create_photo(db, owner, "private.jpg")

    owner_response = _request(
        "GET",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
    )
    other_response = _request(
        "GET",
        f"/photos/{photo.id}",
        token=_token(other_user, settings),
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["id"] == photo.id
    assert "storage_key" not in owner_response.json()
    assert other_response.status_code == 404
    assert other_response.json() == {"detail": "Resource not found"}


def test_other_user_can_read_shared_photo_but_cannot_update_or_delete(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    photo = _create_photo(db, owner, "shared.jpg", visibility="shared")
    other_token = _token(other_user, settings)

    read_response = _request(
        "GET",
        f"/photos/{photo.id}",
        token=other_token,
    )
    patch_response = _request(
        "PATCH",
        f"/photos/{photo.id}",
        token=other_token,
        json={"caption": "Hijacked"},
    )
    delete_response = _request(
        "DELETE",
        f"/photos/{photo.id}",
        token=other_token,
    )

    assert read_response.status_code == 200
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert db.scalar(select(Photo.caption).where(Photo.id == photo.id)) is None


def test_list_returns_owner_and_shared_only_with_accurate_pagination(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    _create_photo(db, owner, "owner-one.jpg")
    _create_photo(db, owner, "owner-two.jpg")
    _create_photo(db, other_user, "shared.jpg", visibility="shared")
    _create_photo(db, other_user, "private-other.jpg")
    token = _token(owner, settings)

    first_page = _request("GET", "/photos?limit=2&offset=0", token=token)
    second_page = _request("GET", "/photos?limit=2&offset=2", token=token)
    all_photos = _request("GET", "/photos?limit=10", token=token)

    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["limit"] == 2
    assert first_page.json()["offset"] == 0
    assert len(first_page.json()["items"]) == 2
    assert len(second_page.json()["items"]) == 1
    ids = [
        item["id"]
        for page in (first_page, second_page)
        for item in page.json()["items"]
    ]
    assert ids == sorted(ids, reverse=True)
    assert {item["original_filename"] for item in all_photos.json()["items"]} == {
        "owner-one.jpg",
        "owner-two.jpg",
        "shared.jpg",
    }


def test_list_validates_pagination_bounds(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = photo_context
    token = _token(owner, settings)

    assert _request("GET", "/photos?limit=0", token=token).status_code == 422
    assert _request("GET", "/photos?limit=101", token=token).status_code == 422
    assert _request("GET", "/photos?offset=-1", token=token).status_code == 422


def test_missing_and_inaccessible_photo_ids_use_same_generic_response(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    photo = _create_photo(db, owner, "private.jpg")
    other_token = _token(other_user, settings)

    inaccessible = _request(
        "GET",
        f"/photos/{photo.id}",
        token=other_token,
    )
    missing = _request("GET", "/photos/999999", token=other_token)

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json() == {
        "detail": "Resource not found"
    }


def test_owner_can_update_metadata_and_clear_caption(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    photo = _create_photo(db, owner, "before.jpg", caption="Old caption")

    update_response = _request(
        "PATCH",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
        json={
            "original_filename": "after.jpg",
            "caption": "New caption",
            "visibility": "shared",
        },
    )
    clear_response = _request(
        "PATCH",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
        json={"caption": None},
    )

    assert update_response.status_code == 200
    assert update_response.json()["original_filename"] == "after.jpg"
    assert update_response.json()["caption"] == "New caption"
    assert update_response.json()["visibility"] == "shared"
    assert clear_response.status_code == 200
    assert clear_response.json()["caption"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"original_filename": ""},
        {"original_filename": "   "},
        {"original_filename": None},
        {"original_filename": "x" * 256},
        {"caption": "   "},
        {"caption": "x" * 5001},
        {"visibility": None},
        {"visibility": "public"},
        {"uploaded_by": 999},
        {"created_by": 999},
        {"owner_id": 999},
        {"storage_key": "client/path"},
    ],
)
def test_patch_rejects_empty_invalid_or_spoofed_fields(
    photo_context: tuple[Session, User, User, Settings],
    payload: dict[str, object],
) -> None:
    db, owner, _, settings = photo_context
    photo = _create_photo(db, owner, "original.jpg", caption="Original")

    response = _request(
        "PATCH",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
        json=payload,
    )

    assert response.status_code == 422
    assert db.scalar(
        select(Photo.original_filename).where(Photo.id == photo.id)
    ) == "original.jpg"
    assert db.scalar(select(Photo.caption).where(Photo.id == photo.id)) == "Original"
    assert db.scalar(select(Photo.uploaded_by).where(Photo.id == photo.id)) == owner.id


def test_owner_can_delete_photo(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    photo = _create_photo(db, owner, "to-delete.jpg")

    response = _request(
        "DELETE",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
    )

    assert response.status_code == 204
    assert response.content == b""
    assert db.get(Photo, photo.id) is None


@pytest.mark.parametrize("operation", ["create", "update"])
def test_database_write_failures_are_generic_and_rolled_back(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db, owner, _, settings = photo_context
    photo = _create_photo(db, owner, "original.jpg") if operation == "update" else None

    def fail_commit() -> None:
        raise OperationalError(
            "INSERT INTO photos",
            {},
            Exception("private database password and SQL details"),
        )

    monkeypatch.setattr(db, "commit", fail_commit)
    if operation == "create":
        response = _request(
            "POST",
            "/photos",
            token=_token(owner, settings),
            json={"original_filename": "failed.jpg"},
        )
    else:
        assert photo is not None
        response = _request(
            "PATCH",
            f"/photos/{photo.id}",
            token=_token(owner, settings),
            json={"original_filename": "failed-update.jpg"},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Database operation unavailable"}
    assert "password" not in response.text.lower()
    assert "INSERT" not in response.text
    assert "OperationalError" in caplog.text
    assert "photo." in caplog.text
    assert "private database password and SQL details" not in caplog.text
    assert "INSERT INTO photos" not in caplog.text
    if operation == "create":
        assert db.scalar(select(func.count()).select_from(Photo)) == 0
    else:
        assert photo is not None
        assert db.scalar(
            select(Photo.original_filename).where(Photo.id == photo.id)
        ) == "original.jpg"


@pytest.mark.parametrize(
    ("image_format", "filename", "content_type", "extension"),
    [
        ("JPEG", "photo.jpg", "image/jpeg", ".jpg"),
        ("PNG", "photo.png", "image/png", ".png"),
        ("WEBP", "photo.webp", "image/webp", ".webp"),
    ],
)
def test_upload_stores_supported_image_and_private_thumbnail(
    photo_context: tuple[Session, User, User, Settings],
    image_format: str,
    filename: str,
    content_type: str,
    extension: str,
) -> None:
    db, owner, _, settings = photo_context

    response = _upload(
        _token(owner, settings),
        _image_bytes(image_format),
        filename=filename,
        content_type=content_type,
    )

    assert response.status_code == 201
    result = response.json()
    assert result["original_filename"] == filename
    assert result["visibility"] == "private"
    assert result["uploaded_by"] == owner.id
    assert "storage_key" not in result
    photo = db.get(Photo, result["id"])
    assert photo is not None
    storage_root = settings.photo_storage_dir
    original_path = storage_root / photo.storage_key
    thumbnail_path = storage_root / f"{Path(photo.storage_key).stem}.thumb.webp"
    assert original_path.is_file()
    assert original_path.suffix == extension
    assert thumbnail_path.is_file()
    with Image.open(original_path) as stored_original:
        assert stored_original.format == image_format
    with Image.open(thumbnail_path) as stored_thumbnail:
        assert stored_thumbnail.format == "WEBP"
        assert stored_thumbnail.size == (32, 24)


def test_upload_normalizes_orientation_and_strips_exif_metadata(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    image = Image.new("RGB", (16, 32), (120, 80, 200))
    exif = Image.Exif()
    exif[274] = 6
    image_output = BytesIO()
    image.save(image_output, format="JPEG", exif=exif)

    response = _upload(_token(owner, settings), image_output.getvalue())

    assert response.status_code == 201
    photo = db.get(Photo, response.json()["id"])
    assert photo is not None
    with Image.open(settings.photo_storage_dir / photo.storage_key) as stored:
        assert stored.size == (32, 16)
        assert not stored.getexif()


def test_upload_supports_shared_visibility_and_derives_owner(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context

    response = _upload(
        _token(owner, settings),
        _image_bytes(),
        visibility="shared",
        caption="Shared photo",
    )

    assert response.status_code == 201
    photo = db.get(Photo, response.json()["id"])
    assert photo is not None
    assert photo.uploaded_by == owner.id
    assert photo.visibility == "shared"
    assert other_user.id != photo.uploaded_by


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("../unsafe.jpg", "image/jpeg"),
        ("unsafe\\photo.jpg", "image/jpeg"),
        ("x" * 256, "image/jpeg"),
    ],
)
def test_upload_rejects_unsafe_filename_and_unaccepted_metadata(
    photo_context: tuple[Session, User, User, Settings],
    filename: str,
    content_type: str,
) -> None:
    _, owner, _, settings = photo_context

    response = _upload(
        _token(owner, settings),
        _image_bytes(),
        filename=filename,
        content_type=content_type,
    )

    assert response.status_code == 422


def test_upload_rejects_invalid_image_inputs(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = photo_context
    valid_jpeg = _image_bytes()
    truncated_jpeg = valid_jpeg[:-20]

    for data in (b"", b"not an image", truncated_jpeg):
        response = _upload(_token(owner, settings), data)
        assert response.status_code == 422

    svg_response = _upload(
        _token(owner, settings),
        b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        filename="photo.svg",
        content_type="image/svg+xml",
    )
    assert svg_response.status_code == 422

    gif_response = _upload(
        _token(owner, settings),
        _image_bytes("GIF"),
        filename="animation.gif",
        content_type="image/gif",
    )
    assert gif_response.status_code == 422


def test_upload_uses_actual_image_format_not_client_mime_or_extension(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context

    response = _upload(
        _token(owner, settings),
        _image_bytes("PNG"),
        filename="misleading.jpg",
        content_type="text/plain",
    )

    assert response.status_code == 201
    photo = db.get(Photo, response.json()["id"])
    assert photo is not None
    assert photo.original_filename == "misleading.jpg"
    assert photo.storage_key.endswith(".png")

    image_response = _request(
        "GET",
        f"/photos/{photo.id}/image",
        token=_token(owner, settings),
    )
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"


def test_upload_rejects_oversized_and_excessive_dimension_images(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, _, settings = photo_context
    settings.photo_max_upload_bytes = 100

    oversized = _upload(_token(owner, settings), _image_bytes())
    assert oversized.status_code == 413

    settings.photo_max_upload_bytes = 10 * 1024 * 1024
    too_wide = _image_bytes(size=(8001, 1))
    dimensions = _upload(_token(owner, settings), too_wide)
    assert dimensions.status_code == 422

    too_many_pixels = _upload(
        _token(owner, settings),
        _png_dimensions_header(7000, 6000),
        filename="large.png",
        content_type="image/png",
    )
    assert too_many_pixels.status_code == 422


def test_upload_accepts_image_at_configured_size_limit_with_multipart_overhead(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    image = _image_bytes()
    settings.photo_max_upload_bytes = len(image)

    response = _upload(_token(owner, settings), image)

    assert response.status_code == 201
    assert db.scalar(select(func.count()).select_from(Photo)) == 1


def test_upload_request_body_limit_rejects_before_multipart_parsing(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = photo_context
    settings.photo_max_upload_bytes = 128
    from app.middleware import upload_size_limit

    monkeypatch.setattr(upload_size_limit, "get_settings", lambda: settings)
    boundary = "test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + b"x" * (128 + 64 * 1024 + 1)

    response = _request(
        "POST",
        "/photos/upload",
        token=_token(owner, settings),
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Photo upload request exceeds the size limit"
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


def test_upload_request_body_limit_counts_streamed_body_without_content_length(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, settings = photo_context
    settings.photo_max_upload_bytes = 1
    from app.middleware import upload_size_limit

    monkeypatch.setattr(upload_size_limit, "get_settings", lambda: settings)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/photos/upload",
        "headers": [],
    }
    messages = [
        {
            "type": "http.request",
            "body": b"x" * (1 + 64 * 1024 + 1),
            "more_body": False,
        }
    ]
    responses: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return messages.pop(0)

    async def send(message: dict[str, object]) -> None:
        responses.append(message)

    async def consume_body(scope, receive, send) -> None:
        while (await receive())["type"] == "http.request":
            continue

    middleware = upload_size_limit.UploadRequestSizeLimitMiddleware(consume_body)
    asyncio.run(middleware(scope, receive, send))

    response_start = next(
        message for message in responses if message["type"] == "http.response.start"
    )
    assert response_start["status"] == 413


def test_upload_rejects_client_attempts_to_set_owner_or_storage_key(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    _, owner, other_user, settings = photo_context
    token = _token(owner, settings)
    image = _image_bytes()

    owner_spoof = _request(
        "POST",
        "/photos/upload",
        token=token,
        files={"file": ("photo.jpg", image, "image/jpeg")},
        data={"uploaded_by": str(other_user.id)},
    )
    key_spoof = _request(
        "POST",
        "/photos/upload",
        token=token,
        files={"file": ("photo.jpg", image, "image/jpeg")},
        data={"storage_key": "client/path"},
    )
    assert owner_spoof.status_code == 422
    assert key_spoof.status_code == 422


def test_upload_database_failure_cleans_both_files_and_metadata(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = photo_context

    def fail_commit() -> None:
        raise OperationalError(
            "INSERT INTO photos",
            {},
            Exception("private database password and SQL details"),
        )

    monkeypatch.setattr(db, "commit", fail_commit)
    response = _upload(_token(owner, settings), _image_bytes())

    assert response.status_code == 503
    assert response.json() == {"detail": "Database operation unavailable"}
    assert "password" not in response.text.lower()
    assert "INSERT" not in response.text
    assert db.scalar(select(func.count()).select_from(Photo)) == 0
    assert list(settings.photo_storage_dir.iterdir()) == []


def test_upload_storage_failure_does_not_create_metadata(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = photo_context

    def fail_store(self, storage_key: str, original: bytes, thumbnail: bytes) -> None:
        raise PhotoStorageError("private storage path")

    from app.services.photo_storage import PhotoStorageError

    monkeypatch.setattr(LocalPhotoStorage, "store", fail_store)
    response = _upload(_token(owner, settings), _image_bytes())

    assert response.status_code == 503
    assert response.json() == {"detail": "Photo storage unavailable"}
    assert "path" not in response.text
    assert db.scalar(select(func.count()).select_from(Photo)) == 0


def test_owner_can_retrieve_private_image_and_thumbnail(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    upload_response = _upload(_token(owner, settings), _image_bytes())
    photo = db.get(Photo, upload_response.json()["id"])
    assert photo is not None

    original = _request(
        "GET",
        f"/photos/{photo.id}/image",
        token=_token(owner, settings),
    )
    thumbnail = _request(
        "GET",
        f"/photos/{photo.id}/thumbnail",
        token=_token(owner, settings),
    )

    assert original.status_code == thumbnail.status_code == 200
    assert original.headers["content-type"] == "image/jpeg"
    assert thumbnail.headers["content-type"] == "image/webp"
    assert original.headers["cache-control"] == "private, no-store"
    assert original.headers["x-content-type-options"] == "nosniff"
    assert original.content
    assert thumbnail.content


@pytest.mark.parametrize("endpoint", ["image", "thumbnail"])
def test_private_image_delivery_rejects_other_user_and_hides_missing_id(
    photo_context: tuple[Session, User, User, Settings],
    endpoint: str,
) -> None:
    db, owner, other_user, settings = photo_context
    upload_response = _upload(_token(owner, settings), _image_bytes())
    photo = db.get(Photo, upload_response.json()["id"])
    assert photo is not None
    other_token = _token(other_user, settings)

    inaccessible = _request(
        "GET",
        f"/photos/{photo.id}/{endpoint}",
        token=other_token,
    )
    missing = _request("GET", f"/photos/999999/{endpoint}", token=other_token)

    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json() == {
        "detail": "Resource not found"
    }


def test_other_user_can_retrieve_shared_image_and_thumbnail(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    upload_response = _upload(
        _token(owner, settings),
        _image_bytes("PNG"),
        filename="shared.png",
        content_type="image/png",
        visibility="shared",
    )
    photo = db.get(Photo, upload_response.json()["id"])
    assert photo is not None
    token = _token(other_user, settings)

    original = _request("GET", f"/photos/{photo.id}/image", token=token)
    thumbnail = _request("GET", f"/photos/{photo.id}/thumbnail", token=token)

    assert original.status_code == thumbnail.status_code == 200
    assert original.headers["content-type"] == "image/png"
    assert thumbnail.headers["content-type"] == "image/webp"


def test_delete_removes_photo_metadata_original_and_thumbnail(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    upload_response = _upload(_token(owner, settings), _image_bytes())
    photo_id = upload_response.json()["id"]
    photo = db.get(Photo, photo_id)
    assert photo is not None
    original_path = settings.photo_storage_dir / photo.storage_key
    thumbnail_path = (
        settings.photo_storage_dir / f"{Path(photo.storage_key).stem}.thumb.webp"
    )
    assert original_path.exists()
    assert thumbnail_path.exists()

    response = _request(
        "DELETE",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
    )

    assert response.status_code == 204
    assert db.get(Photo, photo_id) is None
    assert not original_path.exists()
    assert not thumbnail_path.exists()


def test_non_owner_cannot_delete_photo_files(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, other_user, settings = photo_context
    upload_response = _upload(_token(owner, settings), _image_bytes())
    photo = db.get(Photo, upload_response.json()["id"])
    assert photo is not None
    original_path = settings.photo_storage_dir / photo.storage_key

    response = _request(
        "DELETE",
        f"/photos/{photo.id}",
        token=_token(other_user, settings),
    )

    assert response.status_code == 404
    assert db.get(Photo, photo.id) is not None
    assert original_path.exists()


def test_delete_missing_storage_file_still_removes_metadata_safely(
    photo_context: tuple[Session, User, User, Settings],
) -> None:
    db, owner, _, settings = photo_context
    photo = _create_photo(db, owner, "missing-file.jpg")

    response = _request(
        "DELETE",
        f"/photos/{photo.id}",
        token=_token(owner, settings),
    )

    assert response.status_code == 204
    assert db.get(Photo, photo.id) is None


def test_delete_storage_failure_returns_incomplete_cleanup_error(
    photo_context: tuple[Session, User, User, Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, _, settings = photo_context
    upload_response = _upload(_token(owner, settings), _image_bytes())
    photo_id = upload_response.json()["id"]

    def fail_delete(self, storage_key: str) -> None:
        raise PhotoStorageError("private storage path")

    from app.services.photo_storage import PhotoStorageError

    monkeypatch.setattr(LocalPhotoStorage, "delete", fail_delete)
    response = _request(
        "DELETE",
        f"/photos/{photo_id}",
        token=_token(owner, settings),
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Photo deletion completed with incomplete file cleanup"
    }
    assert db.get(Photo, photo_id) is None


def test_storage_rejects_path_traversal_keys(tmp_path: Path) -> None:
    from app.services.photo_storage import PhotoStorageError

    storage = LocalPhotoStorage(tmp_path)

    with pytest.raises(PhotoStorageError):
        storage.read_original("../../outside.jpg")
    with pytest.raises(PhotoStorageError):
        storage.delete("../outside")
