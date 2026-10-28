from pathlib import Path
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.text import get_valid_filename


ALLOWED_REPORT_EXTENSIONS = ("xls", "xlsx")
MAX_REPORT_FILE_SIZE = 25 * 1024 * 1024
report_file_extension_validator = FileExtensionValidator(ALLOWED_REPORT_EXTENSIONS)


def validate_report_file_size(uploaded_file):
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_REPORT_FILE_SIZE:
        raise ValidationError("O arquivo deve ter no máximo 25 MB.", code="max_size")


def safe_original_filename(filename):
    base_name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    safe_name = get_valid_filename(base_name)[:255]
    return safe_name or "planilha"


def report_original_upload_path(instance, filename):
    safe_name = safe_original_filename(filename)
    extension = Path(safe_name).suffix.casefold()
    if extension.lstrip(".") not in ALLOWED_REPORT_EXTENSIONS:
        raise ValidationError("Formato não permitido. Envie somente arquivos XLS ou XLSX.", code="invalid_extension")
    directory = f"relatorios/originais/{instance.competence_year:04d}-{instance.competence_month:02d}"
    return f"{directory}/{uuid.uuid4().hex}{extension}"
