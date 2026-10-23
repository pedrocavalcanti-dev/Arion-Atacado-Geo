"""Portable, database-side search for the current CMDB link mirror."""
import unicodedata

from django.db.models import F, Q, Value
from django.db.models.functions import Lower, Replace


TEXT_SEARCH_FIELDS = (
    "name", "designation", "address", "city", "state", "legacy_project",
    "operator__name", "contract_number", "customer_id", "identification",
    "circuit", "isp_raw",
)
IDENTIFIER_FIELDS = ("source_config_item_id", "source_number")

# Applying Replace in SQL keeps accent-insensitive matching portable across the
# SQLite development database and MariaDB production database. Tokens are matched
# independently, so repeated whitespace in source values does not need rewriting.
_ACCENTS = (
    ("áàâãä", "a"), ("éèêë", "e"), ("íìîï", "i"),
    ("óòôõö", "o"), ("úùûü", "u"), ("ç", "c"), ("ñ", "n"),
)


def normalize_search_text(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.split())


def _normalized_expression(field):
    expression = F(field)
    # SQLite's lower() is ASCII-only, so replace uppercase Portuguese accents too.
    for accented, plain in _ACCENTS:
        for char in accented + accented.upper():
            expression = Replace(expression, Value(char), Value(plain))
    return Lower(expression)


def matching_link_queryset(queryset, query):
    """Filter a scoped queryset in SQL; never materialize all mirror rows in Python."""
    tokens = normalize_search_text(query).split()
    if not tokens:
        return queryset
    aliases = {field: f"_base_search_{index}" for index, field in enumerate(TEXT_SEARCH_FIELDS)}
    queryset = queryset.annotate(**{
        alias: _normalized_expression(field)
        for field, alias in aliases.items()
    })
    for token in tokens:
        # Text is matched after accent/case normalization. Identifier comparisons
        # stay literal so punctuation and the original identifier characters remain.
        expression_matches = Q()
        for alias in aliases.values():
            expression_matches |= Q(**{f"{alias}__contains": token})
        identifier_matches = Q()
        for field in IDENTIFIER_FIELDS + ("circuit", "operator_designation"):
            identifier_matches |= Q(**{f"{field}__icontains": token})
        queryset = queryset.filter(expression_matches | identifier_matches)
    return queryset

