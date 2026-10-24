from django.core.management.base import BaseCommand, CommandError

from aplicativos.integracoes.models import CMDBLinkMirror
from aplicativos.integracoes.services.link_business_identity import LinkBusinessIdentityService


class Command(BaseCommand):
    help = "Classifica as dimensoes de negocio presentes em nomes CMDB espelhados."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persiste o resultado idempotente no mirror local.")
        parser.add_argument("--all", action="store_true", help="Inclui links ausentes da origem no mirror.")

    def handle(self, *args, **options):
        if not options["apply"]:
            self.stdout.write("Modo de simulacao: use --apply para persistir a classificacao.")
        queryset = CMDBLinkMirror.objects.all() if options["all"] else CMDBLinkMirror.objects.filter(is_present_in_source=True)
        fields = (
            "contracting_client_raw", "contracting_client", "business_project", "business_account",
            "business_id", "business_identity_confidence", "business_identity_source",
        )
        batch = []
        counts = {field: 0 for field in fields}
        predicted = {"client": 0, "project": 0, "account": 0}
        confidence = {}
        updated = 0
        for link in queryset.only("pk", "name", *fields).iterator(chunk_size=500):
            result = LinkBusinessIdentityService.parse(link.name).as_dict()
            predicted["client"] += bool(result["contracting_client"])
            predicted["project"] += bool(result["business_project"])
            predicted["account"] += bool(result["business_account"])
            level = result["business_identity_confidence"]
            confidence[level] = confidence.get(level, 0) + 1
            changed = False
            for field in fields:
                value = result[field]
                if getattr(link, field) != value:
                    setattr(link, field, value)
                    counts[field] += 1
                    changed = True
            if changed:
                updated += 1
                batch.append(link)
            if len(batch) >= 500 and options["apply"]:
                CMDBLinkMirror.objects.bulk_update(batch, fields, batch_size=500)
                batch.clear()
        if batch and options["apply"]:
            CMDBLinkMirror.objects.bulk_update(batch, fields, batch_size=500)

        summary = {
            "total": queryset.count(),
            "changed": updated,
            **predicted,
            "confidence": confidence,
            "identified": {key: value for key, value in counts.items() if value},
        }
        self.stdout.write(self.style.SUCCESS(f"Identidade CMDB: {summary}"))
