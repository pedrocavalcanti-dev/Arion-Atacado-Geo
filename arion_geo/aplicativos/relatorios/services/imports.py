"""Transactional persistence for immutable Claro Multas source imports."""

from django.db import transaction
from django.utils import timezone

from aplicativos.relatorios.models import PenaltyCompetence, PenaltySourceRow, PenaltyTreatmentRow
from .calculations import source_total_claro

from .workbooks import WorkbookImportError, iter_import_rows


BATCH_SIZE = 500


class ImportAlreadyCompleted(Exception):
    pass


def _flush_source_batch(competence, batch):
    if not batch:
        return 0
    row_numbers = [row.source_row_number for row in batch]
    PenaltySourceRow.objects.bulk_create(batch, batch_size=BATCH_SIZE)
    persisted_rows = PenaltySourceRow.objects.filter(
        competence=competence,
        source_row_number__in=row_numbers,
    ).only("id", "source_row_number", "canonical_data")
    treatments = [
        PenaltyTreatmentRow(source_row=row, source_values=row.canonical_data, arion_values={},
                            total_claro=source_total_claro(row.canonical_data))
        for row in persisted_rows
    ]
    PenaltyTreatmentRow.objects.bulk_create(treatments, batch_size=BATCH_SIZE)
    return len(batch)


@transaction.atomic
def confirm_competence_import(*, competence_id, data, extension, sheet_name, header_row, mapping, physical_row_count, user):
    competence = PenaltyCompetence.objects.select_for_update().get(pk=competence_id)
    if competence.imported_at or competence.source_rows.exists():
        raise ImportAlreadyCompleted
    if not competence.original_file or not competence.original_file_sha256:
        raise WorkbookImportError("O arquivo original desta competência não está disponível para importação.")

    batch = []
    imported_count = 0
    with iter_import_rows(
        data,
        extension,
        sheet_name=sheet_name,
        header_row=header_row,
        mapping=mapping,
    ) as (headers, source_rows):
        for row in source_rows:
            batch.append(PenaltySourceRow(
                competence=competence,
                source_row_number=row["source_row_number"],
                source_data=row["source_data"],
                canonical_data=row["canonical_data"],
                row_hash=row["row_hash"],
            ))
            if len(batch) >= BATCH_SIZE:
                imported_count += _flush_source_batch(competence, batch)
                batch = []
    imported_count += _flush_source_batch(competence, batch)
    if imported_count == 0:
        raise WorkbookImportError("Não há registros com REC válida para importar abaixo do cabeçalho selecionado.")
    competence.original_sheet_name = sheet_name
    competence.header_row = int(header_row)
    competence.source_headers = headers
    competence.column_mapping = {str(index): field for index, field in mapping.items()}
    competence.source_total_rows = max(0, int(physical_row_count or 0))
    competence.imported_row_count = imported_count
    competence.imported_at = timezone.now()
    competence.import_error = ""
    competence.status = PenaltyCompetence.Status.IN_TREATMENT
    competence.updated_by = user
    competence.save(update_fields=(
        "original_sheet_name", "header_row", "source_headers", "column_mapping",
        "source_total_rows", "imported_row_count", "imported_at", "import_error",
        "status", "updated_by", "updated_at",
    ))

    return {
        "source_total_rows": competence.source_total_rows,
        "imported_rows": imported_count,
        "sheet_name": sheet_name,
        "header_row": int(header_row),
    }
