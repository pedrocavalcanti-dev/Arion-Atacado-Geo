from dataclasses import dataclass
import codecs
from pathlib import PurePosixPath
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename


ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
    ".txt": {"text/plain"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
}
CANONICAL_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
NEUTRAL_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
DEFAULT_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class UploadValidationError(ValidationError):
    def __init__(self, code="ATTACHMENT_INVALID"):
        self.error_code = code
        super().__init__(code)


def max_attachment_bytes():
    return int(getattr(settings, "ARI_MAX_ATTACHMENT_BYTES", DEFAULT_MAX_ATTACHMENT_BYTES))


@dataclass(frozen=True)
class ValidatedUpload:
    upload: object
    original_name: str
    mime_type: str
    size: int


def _safe_name(name):
    basename = PurePosixPath(str(name or "").replace("\\", "/")).name
    safe = get_valid_filename(basename).strip(" .")[:255]
    if not safe or safe in {".", ".."}:
        raise ValidationError("O arquivo precisa ter um nome válido.")
    return safe


def _detect_content(upload, extension):
    upload.seek(0)
    header = upload.read(16)
    try:
        if extension == ".pdf":
            valid = header.startswith(b"%PDF-")
        elif extension in {".xlsx", ".docx"}:
            upload.seek(0)
            valid = zipfile.is_zipfile(upload)
            if valid:
                upload.seek(0)
                with zipfile.ZipFile(upload) as archive:
                    names = set(archive.namelist())
                required = {"[Content_Types].xml", "xl/workbook.xml"} if extension == ".xlsx" else {"[Content_Types].xml", "word/document.xml"}
                valid = required.issubset(names)
        elif extension == ".png":
            valid = header.startswith(b"\x89PNG\r\n\x1a\n")
        elif extension in {".jpg", ".jpeg"}:
            valid = header.startswith(b"\xff\xd8\xff")
        elif extension == ".gif":
            valid = header.startswith((b"GIF87a", b"GIF89a"))
        elif extension == ".webp":
            valid = header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        else:
            upload.seek(0)
            valid = True
            decoder = codecs.getincrementaldecoder("utf-8")()
            for chunk in upload.chunks():
                if b"\x00" in chunk:
                    valid = False
                    break
                try:
                    decoder.decode(chunk)
                except UnicodeDecodeError:
                    valid = False
                    break
            if valid:
                try:
                    decoder.decode(b"", final=True)
                except UnicodeDecodeError:
                    valid = False
    except (OSError, zipfile.BadZipFile):
        valid = False
    finally:
        upload.seek(0)
    return valid


def validate_upload(upload):
    try:
        original_name = _safe_name(getattr(upload, "name", ""))
    except ValidationError as error:
        raise UploadValidationError() from error
    extension = PurePosixPath(original_name).suffix.lower()
    if extension not in ALLOWED_MIME_TYPES:
        raise UploadValidationError()

    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0:
        raise UploadValidationError()
    maximum = max_attachment_bytes()
    if size > maximum:
        raise UploadValidationError("FILE_TOO_LARGE")

    declared_mime = (getattr(upload, "content_type", "") or "").split(";", 1)[0].strip().lower()
    expected_mimes = ALLOWED_MIME_TYPES[extension]
    if declared_mime not in NEUTRAL_MIME_TYPES and declared_mime not in expected_mimes:
        raise UploadValidationError()
    if not _detect_content(upload, extension):
        raise UploadValidationError()

    upload.name = original_name
    detected_mime = CANONICAL_MIME_TYPES[extension]
    return ValidatedUpload(upload, original_name, detected_mime, size)
