import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ensure src is on path to import project modules
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()
load_dotenv(dotenv_path=BASE_DIR / ".env")

from fetcher import fetch_html
from html_reducer import reduce_html, clean_html
from price_extractor import extract_prices_from_html
from llm_price_extractor import LLMExtractor
from emailer import send_email_smtp

app = FastAPI(title="Scraper de Precios")

static_dir = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": None,
            "defaults": {
                "url": "https://monaco-srl.com/categoria-producto/sillas-secretariales/",
                "use_llm": True,
                "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "max_chars": 30000,
                "email_to": os.getenv("DEFAULT_TO", "agustin.ledezma@ucb.edu.bo"),
            },
        },
    )


@app.post("/extract", response_class=HTMLResponse)
def extract_view(
    request: Request,
    url: str = Form(...),
    use_llm: Optional[bool] = Form(False),
    model: str = Form("gpt-4.1-mini"),
    max_chars: int = Form(30000),
    api_key: Optional[str] = Form(None),
):
    error = None
    try:
        html = fetch_html(url)
        heuristic = extract_prices_from_html(html)
        llm_result = None
        reduced_len = None
        original_len = len(html)

        if use_llm:
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY no definido (o no enviado en el formulario)")
            html_llm = reduce_html(html, max_chars=max_chars)
            reduced_len = len(html_llm)
            extractor = LLMExtractor(api_key=key, model=model)
            llm_result = extractor.extract(html_llm)

        merged = {"prices": []}
        seen = set()
        for p in heuristic:
            k = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
            if k not in seen:
                seen.add(k)
                merged["prices"].append(p)
        if llm_result:
            for p in llm_result.get("prices", []):
                k = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
                if k not in seen:
                    seen.add(k)
                    merged["prices"].append(p)

        payload = {
            "url": url,
            "use_llm": bool(use_llm),
            "model": model,
            "max_chars": max_chars,
            "original_len": original_len,
            "reduced_len": reduced_len,
            "result": merged,
        }
    except Exception as ex:
        error = str(ex)
        payload = {
            "url": url,
            "use_llm": bool(use_llm),
            "model": model,
            "max_chars": max_chars,
            "original_len": None,
            "reduced_len": None,
            "result": {"prices": []},
        }

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": payload,
            "error": error,
            "defaults": {
                "url": url,
                "use_llm": bool(use_llm),
                "model": model,
                "max_chars": max_chars,
                "email_to": os.getenv("DEFAULT_TO", "agustin.ledezma@ucb.edu.bo"),
            },
        },
    )


@app.post("/api/extract", response_class=JSONResponse)
def extract_api(
    url: str = Form(...),
    use_llm: Optional[bool] = Form(False),
    model: str = Form("gpt-4.1-mini"),
    max_chars: int = Form(30000),
    api_key: Optional[str] = Form(None),
):
    html = fetch_html(url)
    heuristic = extract_prices_from_html(html)
    llm_result = None
    if use_llm:
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return JSONResponse({"error": "OPENAI_API_KEY faltante"}, status_code=400)
        html_llm = reduce_html(html, max_chars=max_chars)
        extractor = LLMExtractor(api_key=key, model=model)
        llm_result = extractor.extract(html_llm)

    merged = {"prices": []}
    seen = set()
    for p in heuristic:
        k = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
        if k not in seen:
            seen.add(k)
            merged["prices"].append(p)
    if llm_result:
        for p in llm_result.get("prices", []):
            k = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
            if k not in seen:
                seen.add(k)
                merged["prices"].append(p)

    return {"prices": merged["prices"]}


@app.post("/email")
async def email_report(request: Request):
    data = await request.json()
    to = data.get("to") or os.getenv("DEFAULT_TO", "agustin.ledezma@ucb.edu.bo")
    meta = data.get("meta") or {}
    result = data.get("result") or {}
    prices = (result.get("prices") if isinstance(result, dict) else None) or []

    # Render HTML email via template
    from fastapi.templating import Jinja2Templates
    tpls = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    # Use the internal env to render to string
    template = tpls.env.get_template("email.html")
    html_body = template.render(
        url=meta.get("url"),
        original_len=meta.get("original_len"),
        reduced_len=meta.get("reduced_len"),
        model=meta.get("model"),
        prices=prices,
    )
    subject = data.get("subject") or "Reporte de precios"
    try:
        send_email_smtp(to=to, subject=subject, html_body=html_body)
    except Exception as ex:
        return JSONResponse({"ok": False, "error": str(ex)}, status_code=500)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port)
