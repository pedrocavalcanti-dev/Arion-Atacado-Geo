"""Whitelisted Markdown documents and a safe renderer for the internal portal."""
import html
import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.urls import reverse


DOCS_ROOT = (Path(settings.BASE_DIR).parent / "docs").resolve()
DOCUMENTS = {
    "projeto": ("Projeto", "Visão geral do Arion", "Começar", "PROJETO.md"),
    "estado-atual": ("Estado Atual", "Estado funcional do sistema", "Começar", "ESTADO-ATUAL.md"),
    "arquitetura": ("Arquitetura", "Estrutura e regras compartilhadas", "Começar", "ARQUITETURA.md"),
    "fontes-de-dados": ("Fontes de Dados", "Origem e classificação dos dados", "Começar", "FONTES-DE-DADOS.md"),
    "autenticacao": ("Autenticação e Sessão", "Login e sessão", "Funcionalidades", "funcionalidades/autenticacao.md"),
    "dashboard": ("Dashboard", "Visão executiva", "Funcionalidades", "funcionalidades/dashboard.md"),
    "cockpit": ("Cockpit", "Análise operacional", "Funcionalidades", "funcionalidades/cockpit.md"),
    "mapa": ("Mapa Operacional", "Visão geográfica", "Funcionalidades", "funcionalidades/mapa.md"),
    "ranking-provedores": ("Ranking de Provedores", "Análise por provedor", "Funcionalidades", "funcionalidades/ranking-provedores.md"),
    "base": ("Base de Links", "Espelho CMDB e importação", "Funcionalidades", "funcionalidades/base.md"),
    "ari": ("ARI", "Conversas e artifacts", "Funcionalidades", "funcionalidades/ari.md"),
    "configuracoes": ("Configurações", "Central administrativa", "Administração", "funcionalidades/configuracoes.md"),
    "integracoes": ("Integrações", "Conectores CMDB e OTRS", "Administração", "funcionalidades/integracoes.md"),
    "usuarios-grupos-escopos": ("Usuários, Grupos e Escopos", "RBAC e Data Scope", "Administração", "funcionalidades/usuarios-grupos-escopos.md"),
    "auditoria": ("Auditoria", "Rastreabilidade administrativa", "Administração", "funcionalidades/auditoria.md"),
    "tratamento-global-erros": ("Tratamento Global de Erros", "Respostas e logging", "Administração", "funcionalidades/tratamento-global-erros.md"),
    "seguranca": ("Segurança", "Controles de acesso e proteção", "Segurança e operação", "SEGURANCA.md"),
    "testes-e-qa": ("Testes e QA", "Comandos e cobertura de testes", "Segurança e operação", "TESTES-E-QA.md"),
    "implantacao-e-producao": ("Implantação e Produção", "Configuração por ambiente", "Segurança e operação", "IMPLANTACAO-E-PRODUCAO.md"),
    "diretrizes-de-interface": ("Diretrizes de Interface", "Padrões visuais e acessibilidade", "Padrões", "DIRETRIZES-DE-INTERFACE.md"),
}
CATEGORY_ORDER = ("Começar", "Funcionalidades", "Administração", "Segurança e operação", "Padrões")


def _slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def _document_url(target):
    parsed = target.split("#", 1)
    target_path = parsed[0]
    if not target_path:
        return "#" + parsed[1] if len(parsed) == 2 else None
    normalized_target = target_path.replace("\\", "/").strip("/")
    if normalized_target.casefold() == "funcionalidades":
        return reverse("configuracoes:documentation") + "#home-docs-modulos"
    document = _document_match(normalized_target)
    if document:
        slug, item = document
        url = reverse("configuracoes:documentation-page", kwargs={"slug": slug})
        return url + ("#" + _slugify(parsed[1]) if len(parsed) == 2 else "")
    return None


def _document_match(target_path):
    stem = Path(target_path.replace("\\", "/")).stem.casefold()
    for slug, item in DOCUMENTS.items():
        if Path(item[3]).stem.casefold() == stem:
            return slug, item
    return None


def _inline(text):
    """Escape source HTML first, then add only a small safe inline Markdown subset."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def replace_link(match):
        label, target = match.groups()
        if target.startswith(("https://", "http://")):
            safe_target = html.escape(target, quote=True)
            return f'<a href="{safe_target}" rel="noopener noreferrer">{label}</a>'
        internal = _document_url(target)
        if internal:
            if label.lower().endswith(".md"):
                target_path = target.split("#", 1)[0].replace("\\", "/").strip("/")
                match = _document_match(target_path)
                if match:
                    label = html.escape(match[1][0], quote=False)
            return f'<a href="{html.escape(internal, quote=True)}">{label}</a>'
        return label

    return pattern.sub(replace_link, escaped)


def render_markdown(source):
    """Render the Markdown patterns used by docs; raw HTML is always escaped."""
    lines = source.splitlines()
    output, headings, used_ids = [], [], set()
    i = 0

    def heading(level, title):
        base = _slugify(title) or "secao"
        slug, suffix = base, 2
        while slug in used_ids:
            slug, suffix = f"{base}-{suffix}", suffix + 1
        used_ids.add(slug)
        headings.append((title, slug, level))
        return f'<h{level} id="{slug}">{_inline(title)}</h{level}>'

    def is_table_separator(line):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            language = line[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            klass = f' class="language-{html.escape(language, quote=True)}"' if re.fullmatch(r"[\w+-]+", language) else ""
            block = f"<pre><code{klass}>{html.escape(chr(10).join(code))}</code></pre>"
            if language.casefold() == "mermaid":
                output.append(
                    '<section class="docs-mermaid-source" aria-label="Diagrama de fluxo">'
                    '<div><p class="docs-code-kicker">DIAGRAMA DE FLUXO</p>'
                    '<p class="docs-mermaid-note">Visualização gráfica ainda não disponível.</p></div>'
                    '<details><summary>Ver código Mermaid</summary>' + block + "</details></section>"
                )
            else:
                output.append(block)
        elif line.startswith("# ") or line.startswith("## ") or line.startswith("### "):
            level = len(line) - len(line.lstrip("#"))
            output.append(heading(level, line[level:].strip()))
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            header = [cell.strip() for cell in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")])
                i += 1
            output.append("<div class=\"doc-table-wrap\"><table><thead><tr>" + "".join(f"<th scope=\"col\">{_inline(cell)}</th>" for cell in header) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>" for row in rows) + "</tbody></table></div>")
            continue
        elif re.match(r"\s*[-*+] ", line):
            items = []
            while i < len(lines) and re.match(r"\s*[-*+] ", lines[i]):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            output.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif re.match(r"\s*\d+[.)] ", line):
            items = []
            while i < len(lines) and re.match(r"\s*\d+[.)] ", lines[i]):
                item_text = re.sub(r"^\s*\d+[.)]\s+", "", lines[i])
                items.append(f"<li>{_inline(item_text)}</li>")
                i += 1
            output.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif line.startswith("> "):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(_inline(lines[i].removeprefix("> ").removeprefix(">")))
                i += 1
            output.append("<blockquote>" + "".join(f"<p>{part}</p>" for part in quote if part) + "</blockquote>")
            continue
        elif not line.strip():
            pass
        elif re.fullmatch(r"\s*([-*_])\s*\1\s*\1[\s\1]*", line):
            output.append("<hr>")
        else:
            paragraph = [line.strip()]
            i += 1
            while i < len(lines):
                candidate = lines[i]
                starts_block = (
                    candidate.startswith(("# ", "## ", "### ", "```", "> "))
                    or candidate.lstrip().startswith("|")
                    or re.match(r"\s*[-*+] |\s*\d+[.)] ", candidate)
                    or re.fullmatch(r"\s*([-*_])\s*\1\s*\1[\s\1]*", candidate)
                )
                if not candidate.strip() or starts_block:
                    break
                paragraph.append(candidate.strip())
                i += 1
            output.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            continue
        i += 1
    return "\n".join(output), headings


class DocumentationService:
    """Render versioned Markdown files from ``docs/``, the portal's source of truth."""

    @classmethod
    def navigation(cls):
        return [
            {"slug": slug, "title": data[0], "description": data[1], "category": data[2]}
            for slug, data in DOCUMENTS.items()
        ]

    @classmethod
    def categories(cls):
        docs = cls.navigation()
        return [{"name": name, "documents": [doc for doc in docs if doc["category"] == name]} for name in CATEGORY_ORDER]

    @classmethod
    def get(cls, slug):
        data = DOCUMENTS.get(slug)
        if not data:
            return None
        path = (DOCS_ROOT / data[3]).resolve()
        if not path.is_relative_to(DOCS_ROOT) or not path.is_file():
            return None
        source = path.read_text(encoding="utf-8")
        body, headings = render_markdown(source)
        # The portal heading uses the first Markdown H1 where one is present.
        title = headings[0][0] if headings and headings[0][2] == 1 else data[0]
        if headings and headings[0][2] == 1:
            body = re.sub(r"<h1\b[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)
            headings = headings[1:]
        return {"slug": slug, "title": title, "description": data[1], "category": data[2], "body": body, "headings": headings}

    @classmethod
    def search(cls, query):
        needle = query.casefold()
        results = []
        for doc in cls.navigation():
            record = cls.get(doc["slug"])
            if record is None:
                continue
            raw = (DOCS_ROOT / DOCUMENTS[doc["slug"]][3]).read_text(encoding="utf-8")
            haystack = f"{doc['title']}\n{doc['description']}\n{raw}"
            position = haystack.casefold().find(needle)
            if position < 0:
                continue
            start, end = max(0, position - 100), min(len(haystack), position + len(query) + 140)
            excerpt = re.sub(r"\s+", " ", haystack[start:end]).strip()
            excerpt = ("…" if start else "") + excerpt + ("…" if end < len(haystack) else "")
            nearby = next((slug for title, slug, _ in record["headings"] if title.casefold() in haystack[max(0, position - 80):position + 80].casefold()), "")
            results.append({**doc, "excerpt": excerpt, "anchor": nearby})
        return results
