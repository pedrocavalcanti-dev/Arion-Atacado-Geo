"""Business labels for CMDB link attributes; unresolved concepts stay explicit."""
from dataclasses import dataclass


UNCLASSIFIED = "Não classificado"


@dataclass(frozen=True)
class LinkSemantics:
    project_name: str | None
    project_is_official: bool
    contract_operator_name: str | None
    provider_name: str
    provider_config_item_id: str
    isp_raw: str

    @classmethod
    def from_link(cls, link):
        provider = getattr(link, "operator", None)
        return cls(
            project_name=(link.business_project.strip() or None),
            project_is_official=bool(link.business_project and link.business_identity_confidence in {"HIGH", "MEDIUM"}),
            contract_operator_name=(link.contracting_client.strip() or None),
            provider_name=(provider.name.strip() if provider and provider.name.strip() else UNCLASSIFIED),
            provider_config_item_id=(provider.source_config_item_id if provider else ((link.isp_raw or "").strip() if str(link.isp_raw or "").strip().isdigit() else "")),
            isp_raw=(link.isp_raw or "").strip(),
        )


def provider_label(link):
    """Return a human provider name, never a bare ConfigItemID."""
    return LinkSemantics.from_link(link).provider_name


def provider_filter_queryset(queryset, value):
    """Filter by the mirror entity identifier; never treat isp_raw as a label."""
    if not value:
        return queryset
    if value == UNCLASSIFIED:
        return queryset.filter(operator__isnull=True)
    return queryset.filter(operator__source_config_item_id=value)
