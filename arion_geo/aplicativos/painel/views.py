import json
import csv
from datetime import datetime
from io import BytesIO, StringIO

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from aplicativos.base_links.models import CMDBImport, CMDBLink
from aplicativos.base_links.services.provider_aggregation import provider_link_queryset
from aplicativos.configuracoes.permissions import access_required
from aplicativos.configuracoes.data_scope import DataScopeService
from aplicativos.auditoria.services import AuditService
from .models import SavedAnalyticsView
from .services.analytics import AnalyticsQueryService

STATE_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}


def share(value, whole):
    return round(value / whole * 100, 1) if whole else 0


@login_required
@access_required("view_dashboard")
def index(request):
    latest_import = CMDBImport.objects.order_by("-created_at").first()
    links = DataScopeService.filter_queryset(
        request.user, CMDBLink.objects.filter(is_present_in_latest_import=True),
    )
    if latest_import is None:
        links = links.none()
    summary = links.aggregate(
        total_links=Count("id"),
        state_count=Count("uf", distinct=True, filter=~Q(uf="")),
    )
    providers = provider_link_queryset(base_queryset=links).values("provider_id").distinct().count()
    return render(request, "painel/index.html", {
        **summary,
        "provider_count": providers,
        "latest_import": latest_import,
    })


@login_required
@access_required("view_dashboard")
def dashboard(request):
    links = DataScopeService.filter_queryset(request.user, CMDBLink.objects.filter(is_present_in_latest_import=True))
    total_links = links.count()
    demo = AnalyticsQueryService().dashboard_snapshot(user=request.user)
    by_state = {row["uf"]: row["value"] for row in links.exclude(uf="").values("uf").annotate(value=Count("id")) if row["uf"] in STATE_NAMES}
    operators = []
    for row in links.values("operadora__name").annotate(value=Count("id")).order_by("operadora__name"):
        name = row["operadora__name"] or "Não classificado"
        key = name.casefold() if name.casefold() in {"algar", "claro", "vivo"} else "unclassified"
        operators.append({"name": name, "value": row["value"], "key": key, "share": share(row["value"], total_links)})
    top_states = sorted(({"code": code, "name": STATE_NAMES[code], "value": value,
                          "flag": f"imagens/bandeiras/estados/{code.lower()}.svg"}
                         for code, value in by_state.items()), key=lambda item: item["value"], reverse=True)[:5]
    return render(request, "painel/dashboard.html", {
        "data_source_mode": "cmdb", "total_links": total_links, "state_count": len(by_state),
        **demo, "repeat_share": share(demo["repeat"], demo["calls"]), "first_calls": demo["calls"] - demo["repeat"],
        "operator_count": len(operators), "operators": operators, "top_states": top_states,
        "provider_count": links.exclude(provider__isnull=True).values("provider_id").distinct().count(),
        "top_providers": list(links.exclude(provider__isnull=True).values("provider_id", "provider__name").annotate(value=Count("id")).order_by("-value", "provider__name")[:5]),
        "latest_import": CMDBImport.objects.first(),
    })


@login_required
@access_required("view_cockpit")
def cockpit(request):
    return render(request, "painel/cockpit.html", {"can_save_views": request.user.has_perm("configuracoes.save_analytics_views")})


@login_required
@access_required("view_cockpit")
@require_POST
@csrf_protect
def analytics_query(request):
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("A consulta deve ser um objeto JSON.")
        return JsonResponse(AnalyticsQueryService().query(payload, user=request.user))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error) or "Consulta inválida."}, status=400)


def _pdf_report(title, generated, filters, result):
    from html import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import (
        Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    ink = colors.HexColor("#1f3544")
    muted = colors.HexColor("#6f7f89")
    teal = colors.HexColor("#238a8c")
    orange = colors.HexColor("#d38b4d")
    line = colors.HexColor("#dce4e8")
    pale = colors.HexColor("#f2f7f8")
    white = colors.white
    width, height = A4
    content_width = width - 32 * mm
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=ink, alignment=TA_LEFT, spaceAfter=5))
    styles.add(ParagraphStyle(name="ReportMeta", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=14, textColor=muted))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=ink, spaceBefore=7, spaceAfter=7))
    styles.add(ParagraphStyle(name="CardLabel", parent=styles["Normal"], fontSize=8, leading=11, textColor=muted))
    styles.add(ParagraphStyle(name="CardValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=ink))
    styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=8, leading=11, textColor=ink))
    styles.add(ParagraphStyle(name="CellRight", parent=styles["Cell"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="SmallMeta", parent=styles["Normal"], fontSize=8, leading=12, textColor=muted))

    def safe(value):
        return escape(str(value if value is not None else ""))

    def format_number(value):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value:,}".replace(",", ".") if isinstance(value, int) else str(value).replace(".", ",")

    def short_label(value, limit=20):
        value = str(value)
        return value if len(value) <= limit else value[:limit - 1] + "…"

    class EvolutionChart(Flowable):
        def __init__(self, series):
            super().__init__()
            self.series = series
            self.width = content_width
            self.height = 172

        def draw(self):
            canvas = self.canv
            left, right, bottom, top = 40, self.width - 8, 35, self.height - 24
            values = [float(point["value"]) for point in self.series]
            maximum = max(values, default=0) or 1
            canvas.setFont("Helvetica", 7)
            for tick in range(4):
                y = bottom + (top - bottom) * tick / 3
                canvas.setStrokeColor(line)
                canvas.setLineWidth(.45)
                canvas.line(left, y, right, y)
                canvas.setFillColor(muted)
                canvas.drawRightString(left - 6, y - 2, format_number(round(maximum * tick / 3)))
            if not self.series:
                canvas.setFillColor(muted)
                canvas.drawCentredString((left + right) / 2, self.height / 2, "Sem dados para o período selecionado")
                return
            coords = []
            for index, point in enumerate(self.series):
                x = left + (right - left) * index / max(1, len(self.series) - 1)
                y = bottom + (top - bottom) * float(point["value"]) / maximum
                coords.append((x, y, point))
            path = canvas.beginPath()
            path.moveTo(coords[0][0], coords[0][1])
            for x, y, _ in coords[1:]:
                path.lineTo(x, y)
            canvas.setStrokeColor(teal)
            canvas.setLineWidth(2)
            canvas.drawPath(path)
            for x, y, point in coords:
                canvas.setFillColor(teal)
                canvas.circle(x, y, 2.8, fill=1, stroke=0)
                canvas.setFillColor(ink)
                canvas.setFont("Helvetica", 6.5)
                if len(coords) <= 12:
                    canvas.drawCentredString(x, min(top + 7, y + 7), format_number(point["value"]))
                canvas.setFillColor(muted)
                canvas.drawCentredString(x, bottom - 13, str(point.get("label") or point.get("key", "")).replace("/26", ""))

    class DistributionChart(Flowable):
        def __init__(self, breakdown, detail):
            super().__init__()
            self.rows = [{"dimension": row["key"], "value": row["value"]} for row in breakdown[:8]]
            self.shares = {row["dimension"]: row["share"] for row in detail}
            self.width = content_width
            self.height = max(54, 18 + 18 * len(self.rows))

        def draw(self):
            canvas = self.canv
            bar_left, bar_width = 120, self.width - 224
            maximum = max((float(row["value"]) for row in self.rows), default=0) or 1
            for index, row in enumerate(self.rows):
                y = self.height - 14 - index * 18
                label = short_label(row["dimension"], 21)
                canvas.setFont("Helvetica", 7.5)
                canvas.setFillColor(ink)
                canvas.drawString(0, y, label)
                canvas.setFillColor(pale)
                canvas.roundRect(bar_left, y - 2, bar_width, 7, 3, fill=1, stroke=0)
                canvas.setFillColor(orange)
                canvas.roundRect(bar_left, y - 2, max(2, bar_width * float(row["value"]) / maximum), 7, 3, fill=1, stroke=0)
                canvas.setFillColor(ink)
                canvas.drawRightString(self.width - 51, y, format_number(row["value"]))
                canvas.setFillColor(muted)
                canvas.drawRightString(self.width, y, f"{format_number(self.shares.get(row['dimension'], 0))}%")

    class NumberedCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            kwargs["pageCompression"] = 0
            super().__init__(*args, **kwargs)
            self._states = []

        def showPage(self):
            self._states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._states)
            for state in self._states:
                self.__dict__.update(state)
                self.setFont("Helvetica", 8)
                self.setFillColor(muted)
                self.drawRightString(width - 16 * mm, 11 * mm, f"Pagina {self._pageNumber} de {total}")
                super().showPage()
            super().save()

    def page_frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ink)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(doc.leftMargin, height - 13 * mm, "ARION ATACADO GEO")
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - doc.rightMargin, height - 13 * mm, "RELATÓRIO DO COCKPIT")
        canvas.setStrokeColor(line)
        canvas.setLineWidth(.6)
        canvas.line(doc.leftMargin, height - 16 * mm, width - doc.rightMargin, height - 16 * mm)
        canvas.line(doc.leftMargin, 16 * mm, width - doc.rightMargin, 16 * mm)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(doc.leftMargin, 11 * mm, f"Gerado em {generated} · Fonte conforme escopo de acesso")
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
                            topMargin=23 * mm, bottomMargin=23 * mm,
                            title=f"Arion Atacado Geo - {title}", author="Arion Atacado Geo")
    story = [
        Paragraph("ANÁLISE OPERACIONAL", styles["ReportMeta"]),
        Paragraph(safe(title), styles["ReportTitle"]),
        Paragraph(f"Período: <b>{safe(result['period_from'])} a {safe(result['period_to'])}</b>"
                  f" &nbsp;&nbsp; Comparação: <b>{safe(result['compare_to'] or 'Sem comparação')}</b>"
                  f" &nbsp;&nbsp; Agrupamento: <b>{safe(result['group_by_label'])}</b>", styles["ReportMeta"]),
        Paragraph(
            (f"Comparação: {safe(format_number(result['comparison']['value']))} · "
             f"diferença {safe(format_number(result['comparison']['difference']))} · "
             f"{safe(format_number(result['comparison']['percent']))}%"
             if result.get("comparison") and result["comparison"].get("percent") is not None
             else "Comparação sem base percentual para este recorte."
             if result.get("comparison") else ""), styles["SmallMeta"]),
        Spacer(1, 5),
        Paragraph(f"Filtros aplicados: {safe(filters)}", styles["SmallMeta"]),
        Spacer(1, 8),
        Paragraph("INDICADORES-CHAVE", styles["SectionHeading"]),
    ]
    cards = []
    for item in result["kpis"]:
        source = "DEMONSTRAÇÃO" if item.get("source") == "demo" else "CMDB REAL"
        cards.append([Paragraph(safe(item["label"]).upper(), styles["CardLabel"]),
                      Paragraph(f"{safe(format_number(item['value']))}{safe(item.get('unit', ''))}", styles["CardValue"]),
                      Paragraph(source, styles["CardLabel"])])
    card_rows = [[None, None] for _ in range(len(cards) // 2)]
    for row_index, row in enumerate(card_rows):
        first = row_index * 2
        card_width = content_width / 2 - 18
        row[:] = [Table([[value] for value in cards[first]], colWidths=[card_width]),
                  Table([[value] for value in cards[first + 1]], colWidths=[card_width])]
    if len(cards) % 2:
        lone = Table([[value] for value in cards[-1]], colWidths=[content_width / 2 - 18])
        card_rows.append([lone, ""])
    if card_rows:
        card_table = Table(card_rows, colWidths=[content_width / 2] * 2, hAlign="LEFT")
        card_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), pale), ("BOX", (0, 0), (-1, -1), .5, line),
            ("INNERGRID", (0, 0), (-1, -1), .5, white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([card_table, Paragraph("EVOLUÇÃO NO PERÍODO", styles["SectionHeading"]), EvolutionChart(result["series"])])
    if not result["kpis"]:
        story.append(Paragraph("Nenhum indicador disponível para esta consulta.", styles["SmallMeta"]))
    story.extend([Spacer(1, 3), Paragraph(f"DISTRIBUIÇÃO · {safe(result['group_by_label'])}", styles["SectionHeading"])])
    if result["breakdown"]:
        story.append(DistributionChart(result["breakdown"], result["detail"]))
    else:
        story.append(Paragraph("Nenhum resultado para a dimensão selecionada.", styles["SmallMeta"]))

    story.extend([Spacer(1, 3), Paragraph("DETALHAMENTO", styles["SectionHeading"])])
    detail_data = [[Paragraph(safe(result["group_by_label"]), styles["Cell"]),
                    Paragraph(safe(result["metric_label"]), styles["CellRight"]),
                    Paragraph("Participação", styles["CellRight"])]]
    detail_data.extend([[Paragraph(safe(row["dimension"]), styles["Cell"]),
                         Paragraph(safe(format_number(row["value"])), styles["CellRight"]),
                         Paragraph(f"{safe(format_number(row['share']))}%", styles["CellRight"])]
                        for row in result["detail"]])
    table = Table(detail_data, colWidths=[content_width - 80 * mm, 40 * mm, 40 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), pale), ("TEXTCOLOR", (0, 0), (-1, 0), ink),
        ("LINEBELOW", (0, 0), (-1, 0), .8, line), ("LINEBELOW", (0, 1), (-1, -1), .4, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def _safe_spreadsheet_text(value):
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@login_required
@access_required("view_cockpit")
@require_POST
@csrf_protect
def analytics_export(request):
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("A consulta deve ser um objeto JSON.")
        export_format = payload.pop("format", "csv")
        if export_format not in ("csv", "xlsx", "pdf"):
            raise ValueError("Formato de exportação inválido.")
        result = AnalyticsQueryService().query(payload, user=request.user)
        generated = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
        filters = ", ".join(f"{key}: {value}" for key, value in payload.get("filters", {}).items() if value not in (None, "", "all")) or "Sem filtros adicionais"
        filters = f"Metrica: {result['metric_label']}; {filters}"
        if export_format == "csv":
            buffer = StringIO(newline="")
            writer = csv.writer(buffer, delimiter=";")
            writer.writerow([result["group_by_label"], result["metric_label"], "Participação (%)"])
            writer.writerows((_safe_spreadsheet_text(row["dimension"]), row["value"], row["share"]) for row in result["detail"])
            response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
            filename = "arion-cockpit.csv"
        elif export_format == "xlsx":
            from openpyxl import Workbook
            from openpyxl.styles import Font
            workbook = Workbook()
            summary = workbook.active
            summary.title = "Resumo"
            summary.append(["ARION ATACADO GEO - Cockpit"])
            summary.append(["Gerado em", generated])
            summary.append(["Métrica", result["metric_label"]])
            summary.append(["Período", f"{result['period_from']} a {result['period_to']}"])
            summary.append(["Comparação", result["compare_to"] or "Sem comparação"])
            summary.append(["Agrupamento", result["group_by_label"]])
            summary.append(["Filtros", filters])
            summary.append([])
            summary.append(["Indicador", "Valor", "Fonte"])
            for item in result["kpis"]:
                summary.append([item["label"], item["value"], "Demo" if item["source"] == "demo" else "CMDB real"])
            summary["A1"].font = Font(bold=True, size=14)
            data = workbook.create_sheet("Dados")
            data.append([result["group_by_label"], result["metric_label"], "Participação (%)"])
            for row in result["detail"]:
                data.append([_safe_spreadsheet_text(row["dimension"]), row["value"], row["share"]])
            data.freeze_panes = "A2"
            data.auto_filter.ref = data.dimensions
            for sheet in workbook:
                for column in sheet.columns:
                    letter = column[0].column_letter
                    sheet.column_dimensions[letter].width = min(48, max(14, max(len(str(cell.value or "")) for cell in column) + 2))
            output = BytesIO()
            workbook.save(output)
            response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            filename = "arion-cockpit.xlsx"
        else:
            response = HttpResponse(_pdf_report(result["metric_label"], generated, filters, result), content_type="application/pdf")
            filename = "arion-cockpit.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        AuditService.record(request=request, category="EXPORT", action=f"EXPORT_{export_format.upper()}", module="Cockpit", description=f"Exporta??o Cockpit {export_format.upper()}", result="SUCCESS", metadata={"format": export_format, "filters": payload.get("filters", {}), "period_from": result.get("period_from"), "period_to": result.get("period_to"), "group_by": result.get("group_by_label"), "rows": len(result.get("detail", []))})
        return response
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error) or "Consulta inválida."}, status=400)


@login_required
@access_required("view_cockpit")
@require_POST
@csrf_protect
def saved_views(request):
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("A solicitação deve ser um objeto JSON.")
        action = payload.get("action", "list")
        if action in ("save", "rename", "delete") and not request.user.has_perm("configuracoes.save_analytics_views"):
            return JsonResponse({"error": "Você não tem permissão para alterar visões salvas."}, status=403)
        if action == "list":
            rows = SavedAnalyticsView.objects.filter(user=request.user)
            return JsonResponse({"views": [{"id": row.pk, "name": row.name, "configuration": row.configuration, "favorite": row.favorite} for row in rows]})
        if action == "save":
            name, config = str(payload.get("name", "")).strip(), payload.get("configuration")
            if not name or len(name) > 80 or not isinstance(config, dict):
                raise ValueError("Informe um nome e uma configuração válida.")
            allowed = {"metric", "group_by", "period", "period_from", "period_to", "compare_to", "filters"}
            if set(config) - allowed:
                raise ValueError("Configuração inválida.")
            row, created = SavedAnalyticsView.objects.update_or_create(user=request.user, name=name, defaults={"configuration": config})
            if created:
                AuditService.record(request=request, user=request.user, category="COCKPIT", action="SAVED_VIEW_CREATED", description="Visão salva criada", obj=row, metadata={"name": row.name})
            return JsonResponse({"id": row.pk, "name": row.name})
        if action == "delete":
            row = SavedAnalyticsView.objects.filter(user=request.user, pk=payload.get("id")).first()
            if row:
                AuditService.record(request=request, user=request.user, category="COCKPIT", action="SAVED_VIEW_DELETED", description="Visão salva removida", obj=row, metadata={"name": row.name})
                row.delete()
            return JsonResponse({"ok": True})
        if action == "rename":
            name = str(payload.get("name", "")).strip()
            if not name or len(name) > 80:
                raise ValueError("Informe um nome de até 80 caracteres.")
            row = SavedAnalyticsView.objects.filter(user=request.user, pk=payload.get("id")).first()
            if row is None:
                return JsonResponse({"error": "Consulta salva não encontrada."}, status=404)
            if SavedAnalyticsView.objects.filter(user=request.user, name=name).exclude(pk=row.pk).exists():
                raise ValueError("Você já tem uma consulta com esse nome.")
            old_name = row.name
            row.name = name
            row.save(update_fields=("name", "updated_at"))
            AuditService.record(request=request, user=request.user, category="COCKPIT", action="SAVED_VIEW_UPDATED", description="Consulta salva renomeada", obj=row, metadata={"old_name": old_name, "name": row.name})
            return JsonResponse({"id": row.pk, "name": row.name})
        raise ValueError("Ação inválida.")
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({"error": str(error) or "Solicitação inválida."}, status=400)
