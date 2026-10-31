import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_DIMENSION = 8000
MAX_IMAGE_PIXELS = 40_000_000
THUMBNAIL_SIZE = (512, 512)

_FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


class InvalidPhotoImage(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedPhotoImage:
    original: bytes
    extension: str
    thumbnail: bytes


def validate_and_make_thumbnail(data: bytes) -> ValidatedPhotoImage:
    if not data:
        raise InvalidPhotoImage("Image upload must not be empty.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                extension = _FORMAT_EXTENSIONS.get(image.format or "")
                if extension is None or getattr(image, "is_animated", False):
                    raise InvalidPhotoImage("Unsupported image format.")
                width, height = image.size
                if (
                    width < 1
                    or height < 1
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise InvalidPhotoImage("Image dimensions exceed the limit.")
                if getattr(image, "n_frames", 1) != 1:
                    raise InvalidPhotoImage("Animated images are not supported.")
                image.verify()

            with Image.open(BytesIO(data)) as image:
                image.load()
                oriented = ImageOps.exif_transpose(image)
                has_alpha = "A" in oriented.getbands() or "transparency" in (
                    oriented.info
                )
                clean_image = oriented.convert("RGBA" if has_alpha else "RGB")
                original_output = BytesIO()
                save_options: dict[str, int | bool | bytes] = {}
                if extension == "jpg":
                    save_options["quality"] = 95
                    save_options["optimize"] = True
                elif extension == "webp":
                    save_options["quality"] = 95
                    save_options["method"] = 6
                else:
                    save_options["optimize"] = True
                clean_image.save(
                    original_output,
                    format=image.format,
                    exif=b"",
                    **save_options,
                )
                clean_image.thumbnail(
                    THUMBNAIL_SIZE,
                    Image.Resampling.LANCZOS,
                )
                thumbnail_output = BytesIO()
                clean_image.save(
                    thumbnail_output,
                    format="WEBP",
                    quality=82,
                    method=6,
                    exif=b"",
                )
    except InvalidPhotoImage:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        raise InvalidPhotoImage("The uploaded file is not a valid supported image.") from None

    return ValidatedPhotoImage(
        original=original_output.getvalue(),
        extension=extension,
        thumbnail=thumbnail_output.getvalue(),
    )
