"""Deterministic, non-mutating business context parser for OTRS ticket titles."""
from dataclasses import dataclass

from .link_business_identity import BUSINESS_ID_PATTERN, BusinessIdentityRules, SEPARATOR_PATTERN, comparison_key


@dataclass(frozen=True)
class TicketBusinessIdentity:
    client_raw: str = ""
    client: str = ""
    project_raw: str = ""
    project: str = ""
    occurrence: str = ""
    service: str = ""
    business_id: str = ""
    source: str = "UNKNOWN"

    def as_dict(self):
        return {
            "client_raw": self.client_raw, "client": self.client,
            "project_raw": self.project_raw, "project": self.project,
            "occurrence": self.occurrence, "service": self.service,
            "business_id": self.business_id, "source": self.source,
        }


class TicketBusinessIdentityService:
    OCCURRENCES = {"RESTAURACAO": "Restauração", "ROMPIMENTO": "Rompimento", "INDISPONIBILIDADE": "Indisponibilidade"}
    SERVICES = {"INTERNET": "Internet", "DADOS": "Dados", "VOZ": "Voz"}

    @classmethod
    def parse(cls, title: str) -> TicketBusinessIdentity:
        value = " ".join((title or "").split())
        match = BUSINESS_ID_PATTERN.search(value)
        business_id = match.group(0).upper() if match else ""
        prefix = value[:match.start()] if match else value
        parts = [part.strip(" \t:;#") for part in SEPARATOR_PATTERN.split(prefix) if part.strip(" \t:;#")]
        raw_client = client = project_raw = project = occurrence = service = ""
        for part in parts:
            candidate = BusinessIdentityRules.client_for_token(part)
            if candidate and not raw_client:
                raw_client, client = part, candidate
            key = comparison_key(part)
            if BusinessIdentityRules.project_key(part):
                project_raw, project = part, BusinessIdentityRules.canonical_project(part)
            if key in cls.OCCURRENCES:
                occurrence = cls.OCCURRENCES[key]
            if key in cls.SERVICES:
                service = cls.SERVICES[key]
        source = "OTRS_EXPLICIT_CLIENT" if raw_client else "UNKNOWN"
        if not raw_client and project:
            client = BusinessIdentityRules.project_rule_client(project_raw)
            if client:
                source = "OTRS_PROJECT_RULE"
        return TicketBusinessIdentity(raw_client, client, project_raw, project, occurrence, service, business_id, source)
