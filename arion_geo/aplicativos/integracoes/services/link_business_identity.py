"""Central rules for business identity parsed from CMDB and OTRS titles."""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass


SOURCE = "CMDB_NAME_ORIGINAL"
BUSINESS_ID_PATTERN = re.compile(r"\b(?:BD|BL)[A-Z0-9]*\d[A-Z0-9]*\b", re.IGNORECASE)
SEPARATOR_PATTERN = re.compile(r"\s*[-\u2013\u2014]\s*")


def comparison_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    return " ".join("".join(ch for ch in folded if not unicodedata.combining(ch)).upper().split())


class BusinessIdentityRules:
    """Single source for client precedence, project identity and display labels."""

    CLIENTS = {
        "CLARO": "Claro", "TELMEX": "Claro", "VIVO": "Vivo", "TELEFONICA": "Vivo",
        "TELEFONICA BRASIL": "Vivo", "TELEFONICA BRASIL S A": "Vivo",
        "ALGAR": "Algar",
    }
    PROJECT_ALIASES = {
        "CORREIOS": "Correios", "BANCO DO BRASIL": "Banco do Brasil",
        "CAIXA ECONOMICA": "Caixa Econômica Federal",
        "CAIXA ECONOMICA FEDERAL": "Caixa Econômica Federal", "CEF": "Caixa Econômica Federal",
        "CARREFOUR": "Carrefour", "PROJETO CARREFOUR": "Carrefour", "BRAD": "Bradesco", "BRADESCO": "Bradesco",
        "FUST": "Fust", "L2L": "L2L", "ARCOS DOURADOS": "Arcos Dourados",
        "MC DONALDS": "Arcos Dourados", "MCDONALDS": "Arcos Dourados",
        "MCDONALD S": "Arcos Dourados", "MCDONALD'S": "Arcos Dourados", "ESCOLAS CONECTADAS": "Escolas Conectadas",
        "DIVERSOS": "Diversos", "PROJETO DIVERSOS": "Diversos", "PROJETOS DIVERSOS": "Diversos",
    }
    PROJECT_CLIENT = {
        "CORREIOS": "Claro", "BANCO DO BRASIL": "Claro", "CAIXA ECONOMICA": "Claro",
        "CAIXA ECONOMICA FEDERAL": "Claro", "CEF": "Claro", "CARREFOUR": "Claro", "PROJETO CARREFOUR": "Claro",
        "FUST": "Vivo", "L2L": "Vivo", "ARCOS DOURADOS": "Vivo",
        "MC DONALDS": "Vivo", "MCDONALDS": "Vivo", "MCDONALD S": "Vivo", "MCDONALD'S": "Vivo",
        "ESCOLAS CONECTADAS": "Algar",
    }
    SHARED_PROJECTS = {"BRAD", "BRADESCO", "DIVERSOS", "PROJETO DIVERSOS", "PROJETOS DIVERSOS"}

    @classmethod
    def client_for_token(cls, token: str) -> str:
        key = comparison_key(token)
        if key in cls.CLIENTS:
            return cls.CLIENTS[key]
        # OTRS commonly spells the legal name with punctuation.
        if key.startswith("TELEFONICA BRASIL S A") or key.startswith("TELEFONICA BRASIL"):
            return "Vivo"
        if key.startswith("CLARO "):
            return "Claro"
        if key.startswith("ALGAR "):
            return "Algar"
        return ""

    @classmethod
    def canonical_project(cls, raw: str) -> str:
        key = comparison_key(raw)
        return cls.PROJECT_ALIASES.get(key, raw.strip())

    @classmethod
    def project_rule_client(cls, raw: str) -> str:
        return cls.PROJECT_CLIENT.get(comparison_key(raw), "")

    @classmethod
    def project_key(cls, raw: str) -> str:
        key = comparison_key(raw)
        return key if key in cls.PROJECT_ALIASES else ""


def _configured_aliases(aliases=None):
    if aliases is not None:
        return aliases
    try:
        value = json.loads(os.environ.get("ARION_LINK_CLIENT_ALIASES", "{}"))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class LinkBusinessIdentity:
    contracting_client_raw: str = ""
    contracting_client: str = ""
    business_project: str = ""
    business_account: str = ""
    business_id: str = ""
    confidence: str = "UNCLASSIFIED"
    source: str = "UNKNOWN"

    def as_dict(self):
        return {
            "contracting_client_raw": self.contracting_client_raw,
            "contracting_client": self.contracting_client,
            "business_project": self.business_project,
            "business_account": self.business_account,
            "business_id": self.business_id,
            "business_identity_confidence": self.confidence,
            "business_identity_source": self.source,
        }


class LinkBusinessIdentityService:
    """Parse structured CMDB name segments, retaining the untouched source in name."""

    @classmethod
    def parse(cls, name: str, *, aliases=None) -> LinkBusinessIdentity:
        original = " ".join((name or "").split())
        if not original:
            return LinkBusinessIdentity()
        match = BUSINESS_ID_PATTERN.search(original)
        business_id = match.group(0).upper() if match else ""
        prefix = original[:match.start()] if match else original
        parts = [part.strip() for part in SEPARATOR_PATTERN.split(prefix) if part.strip()]
        if not parts:
            return LinkBusinessIdentity(business_id=business_id)

        raw_client = ""
        client = ""
        client_index = -1
        for index, part in enumerate(parts):
            candidate = BusinessIdentityRules.client_for_token(part)
            if candidate:
                raw_client, client, client_index = part, candidate, index
                break
        aliases_by_key = {
            comparison_key(raw): str(canonical).strip()
            for raw, canonical in _configured_aliases(aliases).items()
            if isinstance(raw, str) and isinstance(canonical, str) and canonical.strip()
        }
        if raw_client and comparison_key(raw_client) in aliases_by_key:
            client = aliases_by_key[comparison_key(raw_client)]
        client_tokens = {comparison_key(part) for part in parts}
        if client == "Claro" and {"CLARO", "TELMEX"}.issubset(client_tokens):
            raw_client = "CLARO / TELMEX"

        project_index = -1
        project_raw = ""
        project = ""
        for index, part in enumerate(parts):
            if BusinessIdentityRules.project_key(part):
                project_index, project_raw = index, part
                # Prefer the segment nearest the Business ID when projects repeat.
        if project_index >= 0:
            project = BusinessIdentityRules.canonical_project(project_raw)
        elif raw_client:
            # Only use the legacy adjacent-token fallback for a real commercial
            # segment. Regional Claro circuit prefixes are technical context.
            candidate_index = client_index + 1
            candidate = parts[candidate_index] if candidate_index < len(parts) else ""
            is_regional_claro = bool(re.match(r"^CLARO\.(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)(?:\.|$)", comparison_key(candidate)))
            if candidate and not is_regional_claro and comparison_key(candidate) != "TELMEX":
                project_index = candidate_index
                project_raw = candidate
                project = BusinessIdentityRules.canonical_project(project_raw)
        else:
            project = ""

        source = "CMDB_EXPLICIT_CLIENT" if raw_client else "UNKNOWN"
        if not client and project:
            inferred = BusinessIdentityRules.project_rule_client(project_raw)
            if inferred:
                client = inferred
                source = "CMDB_PROJECT_RULE"
        account = ""
        if raw_client and project_index >= 0:
            context_indices = {
                index for index, part in enumerate(parts)
                if client == "Claro" and comparison_key(part) == "TELMEX"
            }
            remaining = [part for index, part in enumerate(parts)
                         if index not in ({client_index, project_index} | context_indices)]
            if len(remaining) == 1:
                account = remaining[0]
        confidence = "HIGH" if client and project and business_id else "MEDIUM" if client or project or business_id else "LOW"
        if source == "UNKNOWN":
            confidence = "LOW"
        return LinkBusinessIdentity(raw_client, client, project, account, business_id, confidence, source)


def classify_link_name(name: str, *, aliases=None) -> dict:
    return LinkBusinessIdentityService.parse(name, aliases=aliases).as_dict()
