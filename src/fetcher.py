import requests
from typing import Optional

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

class FetchError(Exception):
    pass

def fetch_html(url: str, timeout: int = 20, headers: Optional[dict] = None) -> str:
    h = DEFAULT_HEADERS.copy()
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h, timeout=timeout)
    if resp.status_code >= 400:
        raise FetchError(f"Error HTTP {resp.status_code} al obtener {url}")
    return resp.text

__all__ = ["fetch_html", "FetchError"]
