import logging
import re
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)
_STORAGE_KEY_PATTERN = re.compile(r"[0-9a-f]{32}(?:\.(?:jpg|png|webp))?\Z")
_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class PhotoStorageError(Exception):
    pass


class PhotoStorage(Protocol):
    def store(self, storage_key: str, original: bytes, thumbnail: bytes) -> None: ...

    def read_original(self, storage_key: str) -> tuple[bytes, str] | None: ...

    def read_thumbnail(self, storage_key: str) -> bytes | None: ...

    def delete(self, storage_key: str) -> None: ...


class LocalPhotoStorage:
    def __init__(self, storage_dir: Path) -> None:
        if storage_dir.is_absolute():
            self._root = storage_dir.resolve()
        else:
            backend_root = Path(__file__).resolve().parents[2]
            self._root = (backend_root / storage_dir).resolve()

    @staticmethod
    def _validate_key(storage_key: str) -> None:
        if _STORAGE_KEY_PATTERN.fullmatch(storage_key) is None:
            raise PhotoStorageError("Invalid photo storage identifier")

    def _paths(self, storage_key: str) -> tuple[Path, Path]:
        self._validate_key(storage_key)
        original_path = self._root / storage_key
        thumbnail_path = self._root / f"{Path(storage_key).stem}.thumb.webp"
        if original_path.is_symlink() or thumbnail_path.is_symlink():
            raise PhotoStorageError("Photo storage item is unavailable")
        return original_path, thumbnail_path

    def _ensure_root(self) -> None:
        try:
            self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError:
            raise PhotoStorageError("Photo storage is unavailable") from None

    def store(self, storage_key: str, original: bytes, thumbnail: bytes) -> None:
        original_path, thumbnail_path = self._paths(storage_key)
        self._ensure_root()
        written: list[Path] = []
        for path, content in (
            (original_path, original),
            (thumbnail_path, thumbnail),
        ):
            try:
                with path.open("xb") as output:
                    written.append(path)
                    output.write(content)
            except OSError:
                for created_path in reversed(written):
                    try:
                        created_path.unlink(missing_ok=True)
                    except OSError:
                        logger.error(
                            "Photo storage cleanup failed after a write error"
                        )
                raise PhotoStorageError("Photo storage is unavailable") from None

    def read_original(self, storage_key: str) -> tuple[bytes, str] | None:
        original_path, _ = self._paths(storage_key)
        media_type = _MEDIA_TYPES.get(original_path.suffix.lower())
        if media_type is None:
            return None
        try:
            return original_path.read_bytes(), media_type
        except FileNotFoundError:
            return None
        except OSError:
            raise PhotoStorageError("Photo storage is unavailable") from None

    def read_thumbnail(self, storage_key: str) -> bytes | None:
        _, thumbnail_path = self._paths(storage_key)
        try:
            return thumbnail_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            raise PhotoStorageError("Photo storage is unavailable") from None

    def delete(self, storage_key: str) -> None:
        original_path, thumbnail_path = self._paths(storage_key)
        failed = False
        for path in (original_path, thumbnail_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                failed = True
        if failed:
            raise PhotoStorageError("Photo storage cleanup failed")
