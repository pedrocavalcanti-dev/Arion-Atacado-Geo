"""Explicit project aliases used only for analytical grouping and filters."""
import re
import unicodedata


PROJECT_ALIASES = {
    "BDN": "BRADESCO",
    "BDN BRADESCO": "BRADESCO",
    "BRADESCO": "BRADESCO",
    "BB": "BANCO DO BRASIL",
    "PROJETO BB": "BANCO DO BRASIL",
    "BANCO DO BRASIL": "BANCO DO BRASIL",
    "BOTICARIO": "O BOTICÁRIO",
    "O BOTICÁRIO": "O BOTICÁRIO",
}


def project_comparison_key(value):
    folded = unicodedata.normalize("NFKD", str(value or ""))
    folded = "".join(char for char in folded if not unicodedata.combining(char)).upper()
    folded = re.sub(r"[-_\u2010-\u2015]+", " ", folded)
    return " ".join(folded.split())


def canonical_project_name(value):
    """Return a canonical display/filter name without changing the source value."""
    raw = " ".join(str(value or "").split())
    return PROJECT_ALIASES.get(project_comparison_key(raw), raw)


def project_alias_groups(raw_names):
    """Group a small distinct project catalog and retain its source spellings."""
    grouped = {}
    for raw in raw_names:
        if not str(raw or "").strip():
            continue
        grouped.setdefault(canonical_project_name(raw), set()).add(raw)
    return {
        canonical: tuple(sorted(values, key=lambda value: (value.casefold(), value)))
        for canonical, values in grouped.items()
    }
