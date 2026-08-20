import mimetypes
import os

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
