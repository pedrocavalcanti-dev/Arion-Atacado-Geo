import json
import re
import secrets
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from aplicativos.configuracoes.data_scope import DataScopeService
from aplicativos.configuracoes.permissions import access_required
from aplicativos.auditoria.services import AuditService

from .data_source import get_data_source_mode
from .models import CMDBImport, CMDBLink, Operadora, Projeto, Provider
from .services.provider_aggregation import get_provider_aggregates
from .services.cmdb.excel_provider import ExcelCMDBProvider
from .services.cmdb.sync import inspect_items, sync_items


MAX_UPLOAD_BYTES = 15 * 1024 * 1024
STAGING_DIR = Path(tempfile.gettempdir()) / "arion-geo-cmdb-previews"
FIELD_LABELS = {
    "version": "Versão", "source_class": "Classe", "incident_state": "Estado de incidente",
    "deployment_state": "Estado de implantação", "name": "Nome", "designation_arion": "Designação ARION",
    "cnpj_arion": "CNPJ ARION", "address": "Endereço", "city": "Cidade", "uf": "UF",
    "uf_raw": "Estado original", "client_raw": "Cliente", "circuit": "Circuito", "isp_raw": "ISP",
    "speed_raw": "Velocidade", "range_ip": "Range IP", "link_type": "Tipo",
    "contract_number": "Número de contrato", "operator_designation": "Designação da operadora",
    "client_identification": "Identificação", "business_hours": "Horário de funcionamento",
    "notes": "Observação", "source_created_at": "Hora de criação", "provider": "Provedor",
    "operadora": "Operadora", "projeto": "Projeto",
}


def _preview_path(token):
    if not re.fullmatch(r"[a-f0-9]{48}", token or ""):
        return None
    return STAGING_DIR / f"{token}.json"


def _serialize_preview_item(item):
    return {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in item.items()}


def _deserialize_preview_item(item):
    value = dict(item)
    raw = value.get("source_created_at")
    if raw:
        from datetime import datetime
        value["source_created_at"] = datetime.fromisoformat(raw)
    return value


def _status_summary(items):
    summary = {"operational": 0, "canceled": 0, "maintenance": 0, "incident": 0}
    for item in items:
        deployment = str(item.get("deployment_state", "")).casefold()
        incident = str(item.get("incident_state", "")).casefold()
        if "cancel" in deployment:
            summary["canceled"] += 1
        elif "manuten" in deployment or "maintenance" in deployment:
            summary["maintenance"] += 1
        elif "operacional" in deployment or "operational" in deployment:
            summary["operational"] += 1
        if "incident" in incident and "operational" not in incident:
            summary["incident"] += 1
    return summary


@login_required
@access_required("view_base")
def index(request):
    scoped_links = DataScopeService.filter_queryset(request.user, CMDBLink.objects.all())
    view = request.GET.get("view", "links")
    if view == "providers":
        provider_filters = {
            "q": request.GET.get("q", "").strip(), "operadora": request.GET.get("operadora", ""),
            "projeto": request.GET.get("projeto", ""), "uf": request.GET.get("uf", "").upper(),
        }
        providers, total_links = get_provider_aggregates(
            operator_id=provider_filters["operadora"], project_id=provider_filters["projeto"],
            uf=provider_filters["uf"], query=provider_filters["q"], base_queryset=scoped_links,
        )
        return render(request, "base_links/providers.html", {
            "view": view, "provider_filters": provider_filters, "providers": providers,
            "total_links": total_links, "provider_count": len(providers),
            "latest_import": CMDBImport.objects.first(),
            "operators": Operadora.objects.filter(links__in=scoped_links, links__is_present_in_latest_import=True).distinct(),
            "projects": Projeto.objects.filter(links__in=scoped_links, links__is_present_in_latest_import=True).distinct(),
            "ufs": scoped_links.filter(is_present_in_latest_import=True).exclude(uf="").values_list("uf", flat=True).distinct().order_by("uf"),
        })
    queryset = scoped_links.select_related("provider", "operadora", "projeto")
    filters = {
        "q": request.GET.get("q", "").strip(),
        "operadora": request.GET.get("operadora", ""),
        "projeto": request.GET.get("projeto", ""),
        "uf": request.GET.get("uf", "").upper(),
        "provedor": request.GET.get("provedor", ""),
        "deployment_state": request.GET.get("deployment_state", ""),
        "incident_state": request.GET.get("incident_state", ""),
        "link_type": request.GET.get("link_type", ""),
        "classification_status": request.GET.get("classification_status", ""),
        "presence": request.GET.get("presence", ""),
    }
    if filters["q"]:
        query = Q()
        for field in ("config_item_id", "designation_arion", "name", "address", "city", "uf", "provider__name", "isp_raw", "circuit", "contract_number", "operator_designation", "client_identification"):
            query |= Q(**{f"{field}__icontains": filters["q"]})
        queryset = queryset.filter(query)
    if filters["operadora"]:
        queryset = queryset.filter(operadora_id=filters["operadora"])
    if filters["projeto"]:
        queryset = queryset.filter(projeto_id=filters["projeto"])
    if filters["uf"]:
        queryset = queryset.filter(uf=filters["uf"])
    if filters["provedor"]:
        queryset = queryset.filter(provider_id=filters["provedor"])
    for field in ("deployment_state", "incident_state", "link_type", "classification_status"):
        if filters[field]:
            queryset = queryset.filter(**{field: filters[field]})
    if filters["presence"] in ("present", "absent"):
        queryset = queryset.filter(is_present_in_latest_import=(filters["presence"] == "present"))

    sort_options = {"designation": "designation_arion", "uf": "uf", "provider": "provider__name", "deployment": "deployment_state"}
    sort = request.GET.get("sort", "designation")
    queryset = queryset.order_by(sort_options.get(sort, sort_options["designation"]), "config_item_id")
    try:
        page_size = int(request.GET.get("page_size", "50"))
    except ValueError:
        page_size = 50
    if page_size not in (25, 50, 100, 200, 500):
        page_size = 50
    page_obj = Paginator(queryset, page_size).get_page(request.GET.get("page"))
    total = scoped_links.count()
    valid_providers, _ = get_provider_aggregates(base_queryset=scoped_links)
    state_counts = dict(scoped_links.values_list("deployment_state").annotate(count=Count("id")))
    incident_count = scoped_links.filter(incident_state__icontains="incident").exclude(incident_state__icontains="operational").count()
    context = {
        "view": "links",
        "data_source_mode": get_data_source_mode(), "page_obj": page_obj, "links": page_obj.object_list,
        "filters": filters, "sort": sort, "page_size": page_size, "total_links": total,
        "operational_count": sum(count for state, count in state_counts.items() if "operacional" in state.casefold() or "operational" in state.casefold()),
        "canceled_count": sum(count for state, count in state_counts.items() if "cancel" in state.casefold()),
        "incident_count": incident_count,
        "provider_count": len(valid_providers),
        "operators": Operadora.objects.filter(links__in=scoped_links).distinct(),
        "projects": Projeto.objects.filter(links__in=scoped_links).distinct(),
        "providers": Provider.objects.filter(links__in=scoped_links).distinct(),
        "ufs": scoped_links.exclude(uf="").values_list("uf", flat=True).distinct().order_by("uf"),
        "deployment_states": scoped_links.exclude(deployment_state="").values_list("deployment_state", flat=True).distinct().order_by("deployment_state"),
        "incident_states": scoped_links.exclude(incident_state="").values_list("incident_state", flat=True).distinct().order_by("incident_state"),
        "link_types": scoped_links.exclude(link_type="").values_list("link_type", flat=True).distinct().order_by("link_type"),
        "classification_options": CMDBLink.ClassificationStatus.choices,
        "latest_import": CMDBImport.objects.first(),
    }
    return render(request, "base_links/index.html", context)


@login_required
@access_required("view_base")
@require_GET
def provider_detail(request, pk):
    scoped = DataScopeService.filter_queryset(request.user, CMDBLink.objects.all())
    providers, total_links = get_provider_aggregates(provider_id=pk, base_queryset=scoped)
    if not providers:
        return JsonResponse({"error": "Provedor sem links presentes na base atual."}, status=404)
    provider = providers[0]
    provider["total_links"] = total_links
    return JsonResponse(provider)


@login_required
@access_required("view_base")
@require_GET
def detail(request, pk):
    scoped = DataScopeService.filter_queryset(request.user, CMDBLink.objects.all())
    link = get_object_or_404(scoped.select_related("provider", "operadora", "projeto").prefetch_related("changes__import_batch"), pk=pk)
    data = {
        "id": link.pk, "config_item_id": link.config_item_id, "version": link.version,
        "designation_arion": link.designation_arion, "name": link.name,
        "operadora": link.operadora.name if link.operadora else "", "projeto": link.projeto.name if link.projeto else "",
        "classification_status": link.get_classification_status_display(),
        "deployment_state": link.deployment_state, "incident_state": link.incident_state,
        "provider": link.provider.name if link.provider else "", "provider_cmdb_config_item_id": link.provider.cmdb_config_item_id if link.provider else "",
        "isp_raw": link.isp_raw, "speed_raw": link.speed_raw, "link_type": link.link_type,
        "range_ip": link.range_ip, "circuit": link.circuit, "operator_designation": link.operator_designation,
        "address": link.address, "city": link.city, "uf": link.uf or link.uf_raw,
        "client_raw": link.client_raw, "contract_number": link.contract_number,
        "client_identification": link.client_identification, "cnpj_arion": link.cnpj_arion,
        "business_hours": link.business_hours, "notes": link.notes,
        "changes": [{"field": FIELD_LABELS.get(change.field_name, change.field_name),
                     "old": change.old_value, "new": change.new_value,
                     "created_at": timezone.localtime(change.created_at).strftime("%d/%m/%Y %H:%M")}
                    for change in link.changes.all()[:30]],
    }
    return JsonResponse(data)


@login_required
@access_required("view_map")
@require_GET
def map_aggregates(request):
    full_queryset = DataScopeService.filter_queryset(request.user, CMDBLink.objects.filter(is_present_in_latest_import=True))
    source_total = full_queryset.count()
    records = full_queryset.select_related("operadora", "projeto")
    operator_id = request.GET.get("operator", "")
    project_id = request.GET.get("project", "")
    if operator_id:
        records = records.filter(operadora_id=operator_id)
    if project_id:
        records = records.filter(projeto_id=project_id)
    filtered_source_total = records.count()
    valid_ufs = "AC AL AP AM BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR SC SE SP TO".split()
    invalid_uf_count = records.filter(Q(uf="") | ~Q(uf__in=valid_ufs)).count()
    result = {}
    for row in records.iterator():
        uf = row.uf
        if not uf:
            continue
        item = result.setdefault(uf, {"claro": 0, "vivo": 0, "algar": 0, "total_links": 0, "chamados": 0, "reincidentes": 0, "motivos": {}, "operator_counts": {}, "project_counts": {}})
        if row.operadora:
            key = row.operadora.name.casefold()
            item["operator_counts"][row.operadora.name] = item["operator_counts"].get(row.operadora.name, 0) + 1
            if key in ("claro", "vivo", "algar"):
                item[key] += 1
        if row.projeto:
            item["project_counts"][row.projeto.name] = item["project_counts"].get(row.projeto.name, 0) + 1
        item["total_links"] += 1
    # Compact, real CMDB facets let the map filter operator + project together
    # without per-state database queries.
    combinations = []
    for row in records.values(
        "uf", "operadora__name", "projeto_id", "projeto__name", "provider__name",
    ).annotate(links=Count("id")).order_by("uf", "operadora__name", "projeto__name"):
        combinations.append({
            "uf": row["uf"], "operator": row["operadora__name"] or "",
            "project_id": row["projeto_id"], "project": row["projeto__name"] or "",
            "provider": row["provider__name"] or "", "links": row["links"],
        })
    return JsonResponse({
        "mode": "cmdb", "states": result,
        "total_links": sum(item["total_links"] for item in result.values()),
        "source_total": source_total, "filtered_source_total": filtered_source_total, "invalid_uf_count": invalid_uf_count,
        "ticket_data_available": False,
        "operators": list(Operadora.objects.filter(links__in=full_queryset, links__is_present_in_latest_import=True).distinct().values("id", "name")),
        "projects": list(Projeto.objects.filter(links__in=full_queryset, links__is_present_in_latest_import=True).distinct().values("id", "name")),
        "combinations": combinations,
    })


@login_required
@access_required("import_cmdb")
def import_cmdb(request):
    if request.method == "GET":
        return render(request, "base_links/import.html", {"data_source_mode": get_data_source_mode()})
    if request.method != "POST":
        return redirect("base_links:import")
    uploaded = request.FILES.get("file")
    if uploaded is None:
        messages.error(request, "Selecione o arquivo XLSX do CMDB.")
        return redirect("base_links:import")
    if uploaded.size > MAX_UPLOAD_BYTES:
        messages.error(request, "O arquivo excede o limite de 15 MB.")
        return redirect("base_links:import")
    if Path(uploaded.name).suffix.casefold() != ".xlsx":
        messages.error(request, "Envie um arquivo com extensão .xlsx.")
        return redirect("base_links:import")

    provider = ExcelCMDBProvider(uploaded.read(), uploaded.name)
    try:
        provider.load_items()
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("base_links:import")
    valid_headers = provider.validate()
    items = provider.normalize() if valid_headers else []
    if not valid_headers:
        preview_result = {"new": [], "updated": [], "unchanged": [], "changes": [], "unclassified": 0}
        preview_result["errors"] = provider.errors
    else:
        preview_result = inspect_items(items)
        preview_result["errors"] = provider.errors
    for item in preview_result["updated"]:
        for change in item.get("changes", []):
            change["label"] = FIELD_LABELS.get(change["field"], change["field"].replace("_", " ").title())
    summary = _status_summary(items)
    token = secrets.token_hex(24)
    STAGING_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    for old_file in STAGING_DIR.glob("*.json"):
        try:
            if timezone.now().timestamp() - old_file.stat().st_mtime > 3600:
                old_file.unlink()
        except OSError:
            pass
    stage = {
        "filename": uploaded.name, "sha256": provider.sha256,
        "items": [_serialize_preview_item(item) for item in items], "errors": provider.errors,
    }
    _preview_path(token).write_text(json.dumps(stage, ensure_ascii=False), encoding="utf-8")
    request.session["cmdb_import_preview_token"] = token
    request.session["cmdb_import_preview_at"] = timezone.now().timestamp()
    duplicate = CMDBImport.objects.filter(file_sha256=provider.sha256).first()
    context = {
        "data_source_mode": get_data_source_mode(), "filename": uploaded.name,
        "headers": provider.headers, "total_rows": len(provider.raw_items), "valid_count": len(items), "can_confirm": valid_headers and bool(items),
        "column_count": len(provider.headers), "new_count": len(preview_result["new"]),
        "updated_count": len(preview_result["updated"]), "unchanged_count": len(preview_result["unchanged"]),
        "error_count": len(provider.errors), "unclassified_count": preview_result["unclassified"],
        **summary, "new_examples": preview_result["new"][:10], "updated_examples": preview_result["updated"][:10],
        "unchanged_examples": preview_result["unchanged"][:10], "error_examples": provider.errors[:10],
        "duplicate_import": duplicate,
    }
    return render(request, "base_links/import.html", context)


@login_required
@access_required("import_cmdb")
@require_POST
def confirm_import(request):
    token = request.session.get("cmdb_import_preview_token")
    path = _preview_path(token)
    timestamp = request.session.get("cmdb_import_preview_at", 0)
    if not path or timezone.now().timestamp() - timestamp > 3600 or not path.is_file():
        messages.error(request, "A prévia expirou. Envie o arquivo novamente.")
        return redirect("base_links:import")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = [_deserialize_preview_item(item) for item in payload["items"]]
        if not items:
            raise ValueError("O arquivo não contém registros válidos para importar.")
        batch = sync_items(items=items, filename=payload["filename"], sha256=payload["sha256"], imported_by=request.user, errors=payload.get("errors", []))
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        messages.error(request, f"Não foi possível concluir a importação: {error}")
        return redirect("base_links:import")
    finally:
        request.session.pop("cmdb_import_preview_token", None)
        request.session.pop("cmdb_import_preview_at", None)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    AuditService.record(request=request, user=request.user, category="INTEGRATION", action="CMDB_IMPORT", description="Importação CMDB concluída", obj=batch, metadata={
        "import_id": batch.pk, "filename": Path(batch.filename).name[:120], "total_rows": batch.total_rows,
        "new_count": batch.new_count, "updated_count": batch.updated_count, "unchanged_count": batch.unchanged_count,
        "error_count": batch.error_count, "result": batch.get_status_display(), "timestamp": batch.created_at.isoformat(),
    })
    return render(request, "base_links/result.html", {"batch": batch})
