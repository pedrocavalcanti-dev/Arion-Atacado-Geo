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
            # The only project value currently persisted is a frozen XLSX-era value.
            project_name=None,
            project_is_official=False,
            # DesignacaoOperadora is sparse/free text and has not been confirmed as
            # the contracted macro operator, so never substitute the ISP here.
            contract_operator_name=None,
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
