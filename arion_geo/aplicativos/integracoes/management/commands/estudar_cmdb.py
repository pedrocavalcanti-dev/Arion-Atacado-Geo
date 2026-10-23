from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from aplicativos.base_links.models import CMDBLink
from aplicativos.integracoes.models import Integration
from aplicativos.integracoes.services.errors import IntegrationError
from aplicativos.integracoes.views import _cmdb_client


BASE_FIELDS = (
    "config_item_id", "name", "designation_arion", "operator_designation", "circuit",
    "isp_raw", "city", "uf_raw", "link_type", "speed_raw", "range_ip",
    "deployment_state", "incident_state",
)


class Command(BaseCommand):
    help = "Executa inventário e comparação somente leitura do CMDB ServiceUp."

    def handle(self, *args, **options):
        try:
            integration = Integration.objects.get(key=Integration.Key.CMDB)
            client = _cmdb_client(integration)
        except Integration.DoesNotExist as exc:
            raise CommandError("CMDB não possui configuração existente na Central de Integrações.") from exc
        except IntegrationError as exc:
            raise CommandError(f"Não foi possível preparar o cliente CMDB ({type(exc).__name__}).") from None
        except Exception as exc:
            raise CommandError(f"Não foi possível preparar o cliente CMDB ({type(exc).__name__}).") from None

        queryset = CMDBLink.objects.filter(is_present_in_latest_import=True)
        base_count_before = queryset.count()
        base_rows = list(queryset.values(*BASE_FIELDS).iterator(chunk_size=1000))
        self.stdout.write(f"[CMDB] Base para comparação: {base_count_before} links.")

        from aplicativos.integracoes.services.cmdb_study import CMDBStudyService

        study = CMDBStudyService(client, progress=self.stdout.write)
        try:
            result = study.run(base_rows)
        except Exception as exc:
            raise CommandError(f"Estudo CMDB interrompido ({type(exc).__name__}); nenhuma alteração local foi confirmada.") from None

        base_count_after = queryset.count()
        result["base_count_before"] = base_count_before
        result["base_count_after"] = base_count_after
        result["base_unchanged"] = base_count_before == base_count_after
        result["report"] = CMDBStudyService.render_report(result)
        result["report"] += f"\n\nVerificação local: Base antes={base_count_before}; depois={base_count_after}; quantidade inalterada={'sim' if result['base_unchanged'] else 'não'}.\n"
        fields_markdown = self._render_fields(result)

        protected_values = [client.password, integration.secret_ciphertext, integration.username]
        for value in protected_values:
            if value and (value in result["report"] or value in fields_markdown):
                raise CommandError("O relatório contém uma credencial configurada; gravação cancelada.")

        output_dir = Path("docs") / "estudos"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "CMDB-ESTUDO-REAL.md"
        report_path.write_text(result["report"], encoding="utf-8")
        fields_path = output_dir / "CMDB-CAMPOS.md"
        fields_path.write_text(fields_markdown, encoding="utf-8")

        links, operators = result["links"], result["operators"]
        relation = result["relation"]["counts"]
        self.stdout.write(self.style.SUCCESS(
            f"Estudo {'completo' if result['complete'] else 'parcial'}: "
            f"Links {links['fetch']['processed']}/{links['ids_found']}; "
            f"Operadoras {operators['fetch']['processed']}/{operators['ids_found']}; "
            f"ISP com valor {relation.get('with_isp', 0)}, resolvidos "
            f"{sum(value for key, value in relation.items() if key in ('ConfigItemID', 'Number', 'Name') or key.startswith('CIXMLData.'))}, "
            f"Base inalterada={'sim' if result['base_unchanged'] else 'não'}."
        ))
        self.stdout.write(f"Relatório: {report_path.as_posix()}")
        self.stdout.write(f"Inventário agregado: {fields_path.as_posix()}")

    @staticmethod
    def _render_fields(result):
        lines = [
            "# Inventário agregado de campos CMDB", "",
            "Somente presença, preenchimento, tipo e sensibilidade. Sem valores de ConfigItem.", "",
        ]
        for title, key in (("Links de internet", "links"), ("Operadoras", "operators")):
            lines.extend((f"## {title}", "", "| Campo | Presença | Preenchido | Vazio | Tipo | Sensibilidade |", "|---|---:|---:|---:|---|---|"))
            for name, metric in sorted(result[key]["fields"].items(), key=lambda row: row[0].casefold()):
                protected = "PROTEGIDO — NÃO PERSISTIR" if metric["sensitive"] else "Público"
                lines.append(f"| {name} | {metric['exists']} | {metric['filled']} | {metric['empty']} | {', '.join(metric['types']) or '—'} | {protected} |")
            lines.append("")
        return "\n".join(lines)
