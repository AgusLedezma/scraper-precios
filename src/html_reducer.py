import re
from bs4 import BeautifulSoup, Comment

# Palabras clave relacionadas con precios para priorizar bloques relevantes
KEYWORDS_RE = re.compile(
    r"precio|oferta|rebaja|ahorro|descuento|price|deal|sale|promo|desde|ver precio|\bUSD\b|\bEUR\b|\bMXN\b|\bARS\b|\bCLP\b|\bCOP\b|\bBOB\b|\bPEN\b|\bBRL\b|\bUYU\b|\bGTQ\b|\bCRC\b|S/\.|Bs\.?|[$€£]",
    flags=re.IGNORECASE,
)

PRICE_RE = re.compile(
    r"""
    ([$€£]|S/\.|Bs\.?|USD\b|EUR\b|MXN\b|ARS\b|CLP\b|COP\b|BOB\b|PEN\b|BRL\b|UYU\b|GTQ\b|CRC\b)\s{0,3}
        \d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?
    |
    \d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?\s{0,3}
        (USD\b|EUR\b|MXN\b|ARS\b|CLP\b|COP\b|BOB\b|PEN\b|BRL\b|UYU\b|GTQ\b|CRC\b)
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

STRIP_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "footer",
    "header",
    "nav",
    "form",
    "input",
    "button",
    "picture",
    "source",
    "link",
    "meta",
}


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # Remove comments
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    # Remove undesired tags
    for tag in soup(STRIP_TAGS):
        tag.decompose()

    # Remove attributes that can be huge (styles, data-*, class)
    for el in soup.find_all(True):
        for attr in list(el.attrs.keys()):
            if attr.startswith("data-") or attr in {"style", "class", "onclick", "onload", "id"}:
                del el.attrs[attr]

    # Remove base64 images or long attributes
    for img in soup.find_all("img"):
        if img.has_attr("src") and ";base64," in img["src"]:
            img.decompose()

    # Collapse whitespace in text nodes
    for t in soup.find_all(string=True):
        text = re.sub(r"\s+", " ", t)
        t.replace_with(text)

    return str(soup)


def _collect_relevant_blocks(html: str, max_blocks: int = 200):
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    blocks = []

    def is_relevant(text: str) -> bool:
        if not text:
            return False
        t = text.strip()
        return bool(PRICE_RE.search(t) or KEYWORDS_RE.search(t))

    # Consider block-level tags
    candidates = body.find_all(["section", "article", "div", "ul", "ol", "li", "table", "tr", "td", "th", "p", "span", "h1", "h2", "h3", "h4"])
    for node in candidates:
        text = node.get_text(" ", strip=True)
        if is_relevant(text):
            # include limited sibling context
            parent = node.parent if node.parent else body
            wrapper = soup.new_tag("div")
            # previous siblings
            prev_count = 0
            for sib in node.previous_siblings:
                if prev_count >= 2:
                    break
                if getattr(sib, "name", None):
                    wrapper.append(sib.extract())
                    prev_count += 1
            wrapper.append(node.extract())
            # next siblings
            next_count = 0
            for sib in node.next_siblings:
                if next_count >= 2:
                    break
                if getattr(sib, "name", None):
                    wrapper.append(sib.extract())
                    next_count += 1
            blocks.append(str(wrapper))
            if len(blocks) >= max_blocks:
                break

    # Deduplicate blocks by text signature
    seen = set()
    unique_blocks = []
    for b in blocks:
        key = re.sub(r"\s+", " ", BeautifulSoup(b, "lxml").get_text(" ", strip=True))[:200]
        if key not in seen:
            seen.add(key)
            unique_blocks.append(b)

    title = (soup.title.get_text(strip=True) if soup.title else "")
    head = f"<head><meta charset='utf-8'><title>{title}</title></head>"
    body = "\n".join(unique_blocks) if unique_blocks else soup.body.get_text(" ", strip=True)
    return f"<html>{head}<body>{body}</body></html>"


def reduce_html(html: str, max_chars: int = 30000) -> str:
    """Reduce el HTML a como máximo max_chars priorizando secciones con precios.

    Estrategia:
    1) Limpieza básica del DOM, remoción de scripts/estilos/atributos enormes.
    2) Si aún excede, seleccionar bloques relevantes (precios/keywords) con poco contexto.
    3) Si aún excede, convertir a texto plano relevante (líneas con precio) y truncar.
    4) Fallback final: truncar duro a max_chars.
    """
    if not html:
        return ""

    cleaned = clean_html(html)
    if len(cleaned) <= max_chars:
        return cleaned

    relevant_html = _collect_relevant_blocks(cleaned)
    if len(relevant_html) <= max_chars:
        return relevant_html

    # Extract only relevant lines with small context
    text = BeautifulSoup(cleaned, "lxml").get_text("\n", strip=True)
    lines = [ln for ln in text.splitlines() if PRICE_RE.search(ln) or KEYWORDS_RE.search(ln)]
    # Join with separators to keep some structure
    text_only = ("\n---\n").join(lines)
    if not lines:
        return cleaned[:max_chars]
    payload = f"<html><head><meta charset='utf-8'></head><body><pre>{text_only}</pre></body></html>"
    if len(payload) <= max_chars:
        return payload

    return payload[:max_chars]


__all__ = ["reduce_html", "clean_html"]
