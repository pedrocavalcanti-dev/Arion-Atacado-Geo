import re
import unicodedata


OPERATORS = {
    "CLARO": ("CLARO",),
    "VIVO": ("VIVO",),
    "ALGAR": ("ALGAR",),
}
PROJECTS = (
    (("BANCO DO BRASIL",), "Banco do Brasil"),
    (("CAIXA ECONOMICA", "CEF"), "Caixa Econômica"),
    (("ARCOS DOURADOS",), "Arcos Dourados"),
    (("BRADESCO",), "Bradesco"),
    (("CORREIOS",), "Correios"),
    (("SANTANDER",), "Santander"),
    (("CARREFOUR",), "Carrefour"),
    (("FUST",), "FUST"),
)


def _plain(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in value if not unicodedata.combining(char)).upper()


def _contains_phrase(text, phrase):
    phrase = _plain(phrase)
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(phrase)}(?![A-Z0-9])", text))


def _classification_text(link_data):
    return " ".join(_plain(link_data.get(field, "")) for field in ("name", "designation_arion"))


def detect_operator(link_data):
    text = _classification_text(link_data)
    matches = [name for name, aliases in OPERATORS.items() if any(_contains_phrase(text, alias) for alias in aliases)]
    return matches[0] if len(matches) == 1 else None


def detect_project(link_data):
    text = _classification_text(link_data)
    matches = [name for aliases, name in PROJECTS if any(_contains_phrase(text, alias) for alias in aliases)]
    return matches[0] if len(matches) == 1 else None
