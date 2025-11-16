import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Iterable

PRICE_PATTERN = re.compile(r"""
    (?:(?P<currency_symbol>[$€£]|S/\.|Bs\.?|USD\b|EUR\b|MXN\b|ARS\b|CLP\b|COP\b|BOB\b|PEN\b|BRL\b|UYU\b|GTQ\b|CRC\b))\s{0,3}
    (?P<amount>\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?|\d+(?:[\.,]\d{2}))
    |(?P<amount_alt>\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?)\s{0,3}(?P<currency_trailing>USD\b|EUR\b|MXN\b|ARS\b|CLP\b|COP\b|BOB\b|PEN\b|BRL\b|UYU\b|GTQ\b|CRC\b)
""", re.VERBOSE)

CURRENCY_NORMALIZATION = {
    '$': 'USD', 'USD': 'USD', 'EUR': 'EUR', '€': 'EUR', '£': 'GBP', 'S/.': 'PEN', 'PEN': 'PEN',
    'MXN': 'MXN', 'ARS': 'ARS', 'CLP': 'CLP', 'COP': 'COP', 'Bs.': 'BOB', 'Bs': 'BOB', 'BOB': 'BOB',
    'BRL': 'BRL', 'UYU': 'UYU', 'GTQ': 'GTQ', 'CRC': 'CRC'
}

@dataclass
class PriceCandidate:
    raw: str
    value: float
    currency: Optional[str]
    context: str

    def to_dict(self) -> Dict:
        return asdict(self)

def _normalize_amount(text: str) -> Optional[float]:
    # Replace thousand separators and unify decimal
    if text.count(',') > 0 and text.count('.') > 0:
        # Heuristic: assume last occurrence is decimal if pattern like 1.234,56 or 1,234.56
        if text[-3] in {',', '.'}:
            if ',' in text[-3:]:  # decimal comma
                cleaned = text.replace('.', '').replace(',', '.')
            else:
                cleaned = text.replace(',', '')
        else:
            cleaned = text.replace(',', '').replace('.', '.')
    else:
        # Single type of separator
        if text.count(',') > 0 and text.count('.') == 0:
            # Treat comma as decimal if appears in last 3 chars
            if ',' in text[-3:]:
                cleaned = text.replace(',', '.')
            else:
                cleaned = text.replace(',', '')
        else:
            cleaned = text.replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def extract_price_candidates(text: str, context_window: int = 60) -> List[PriceCandidate]:
    candidates: List[PriceCandidate] = []
    for match in PRICE_PATTERN.finditer(text):
        currency_symbol = match.group('currency_symbol') or match.group('currency_trailing')
        amount = match.group('amount') or match.group('amount_alt')
        if not amount:
            continue
        value = _normalize_amount(amount)
        if value is None:
            continue
        currency = CURRENCY_NORMALIZATION.get(currency_symbol) if currency_symbol else None
        start, end = match.span()
        left = max(0, start - context_window)
        right = min(len(text), end + context_window)
        context = re.sub(r"\s+", " ", text[left:right]).strip()
        candidates.append(PriceCandidate(raw=match.group(0), value=value, currency=currency, context=context))
    return candidates

def deduplicate_prices(candidates: Iterable[PriceCandidate]) -> List[PriceCandidate]:
    seen = {}
    result = []
    for c in candidates:
        key = (round(c.value, 2), c.currency)
        if key not in seen:
            seen[key] = c
            result.append(c)
    return result

def extract_prices_from_html(html: str) -> List[Dict]:
    # Quick removal of script/style to reduce noise
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    # Remove tags, keep text
    text = re.sub(r"<[^>]+>", " ", cleaned)
    text = re.sub(r"\s+", " ", text)
    candidates = extract_price_candidates(text)
    candidates = deduplicate_prices(candidates)
    return [c.to_dict() for c in candidates]

__all__ = ["extract_prices_from_html", "extract_price_candidates", "PriceCandidate"]
