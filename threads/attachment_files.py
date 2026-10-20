import mimetypes
import os
import warnings

from PIL import Image

from common.types import AdminFieldValidationProblem

KIND_IMAGE = "IMAGE"
KIND_DOCUMENT = "DOCUMENT"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS

IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
DOCUMENT_CONTENT_TYPES = {"application/pdf"}
ALLOWED_CONTENT_TYPES = IMAGE_CONTENT_TYPES | DOCUMENT_CONTENT_TYPES

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

_IMAGE_FORMAT_METADATA = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "GIF": (".gif", "image/gif"),
    "WEBP": (".webp", "image/webp"),
}


def attachment_filename(file_field):
    name = getattr(file_field, "name", "") or ""
    return os.path.basename(name)


def attachment_extension(name):
    return os.path.splitext(name or "")[1].lower()


def attachment_kind(name, content_type=None):
    ext = attachment_extension(name)
    if ext in IMAGE_EXTENSIONS:
        return KIND_IMAGE
    if ext in DOCUMENT_EXTENSIONS:
        return KIND_DOCUMENT
    ctype = (content_type or "").lower()
    if ctype in IMAGE_CONTENT_TYPES:
        return KIND_IMAGE
    return KIND_DOCUMENT


def is_image_attachment(name, content_type=None):
    return attachment_kind(name, content_type) == KIND_IMAGE


def inferred_content_type(name, uploaded_content_type=None):
    if uploaded_content_type:
        return uploaded_content_type
    guessed, _encoding = mimetypes.guess_type(name or "")
    return guessed or ""


def validate_comment_upload(upload):
    if upload is None:
        return AdminFieldValidationProblem(
            name="files", message="attachment file is missing"
        )
    name = getattr(upload, "name", "") or ""
    content_type = (getattr(upload, "content_type", None) or "").lower()
    size = getattr(upload, "size", 0) or 0
    ext = attachment_extension(name)

    if size > MAX_ATTACHMENT_BYTES:
        return AdminFieldValidationProblem(
            name="files",
            message="attachment must be 10 MB or smaller",
        )

    if ext:
        if ext not in ALLOWED_EXTENSIONS:
            return AdminFieldValidationProblem(
                name="files",
                message="attachment must be an image (jpeg, png, gif, webp) or a PDF",
            )
    elif content_type not in ALLOWED_CONTENT_TYPES:
        return AdminFieldValidationProblem(
            name="files",
            message="attachment must be an image (jpeg, png, gif, webp) or a PDF",
        )
    return None


def prepare_comment_upload(upload):
    """Accept older mobile image uploads after inspecting their actual contents."""
    problem = validate_comment_upload(upload)
    if problem is None or upload is None:
        return problem
    if (
        upload.size > MAX_ATTACHMENT_BYTES
        or attachment_extension(upload.name)
        or (upload.content_type or "").lower() not in ("", "application/octet-stream")
    ):
        return problem

    position = upload.tell()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as image:
                metadata = _IMAGE_FORMAT_METADATA.get(image.format)
                if metadata is None:
                    return problem
                image.verify()
            # Verification checks the container; loading also detects truncated pixels.
            upload.seek(0)
            with Image.open(upload) as image:
                image.load()
    except (
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return problem
    finally:
        upload.seek(position)

    extension, content_type = metadata
    upload.name = f"{upload.name}{extension}"
    upload.content_type = content_type
    return None
