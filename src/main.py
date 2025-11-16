import os
import json
import argparse
from pathlib import Path
from fetcher import fetch_html
from price_extractor import extract_prices_from_html
from llm_price_extractor import LLMExtractor
from html_reducer import reduce_html, clean_html
try:
    from dotenv import load_dotenv
    load_dotenv()  # Carga variables desde .env si existe
    # También intenta cargar .env junto a este archivo
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except Exception:
    pass

"""Pipeline principal:
1. Descarga HTML.
2. Extrae precios heurísticos rápidos.
3. (Opcional) Usa LLM para mayor precisión/contexto.
4. Fusiona y deduplica.
"""

def merge_results(heuristic: list, llm: dict | None) -> dict:
    merged = {"prices": []}
    seen = set()
    for p in heuristic:
        key = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
        if key not in seen:
            seen.add(key)
            merged["prices"].append(p)
    if llm:
        for p in llm.get("prices", []):
            key = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
            if key not in seen:
                seen.add(key)
                merged["prices"].append(p)
    return merged

def main():
    parser = argparse.ArgumentParser(description="Extracción de precios desde una página web usando heurística y LLM.")
    parser.add_argument("url", help="URL a procesar")
    parser.add_argument("--llm", action="store_true", help="Activar extracción con LLM además de heurística")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Modelo OpenAI a usar si se activa --llm")
    parser.add_argument("--max-chars", type=int, default=30000, help="Tamaño máximo del HTML para el LLM")
    parser.add_argument("--output", default="resultados_precios.json", help="Archivo de salida JSON")
    parser.add_argument("--dump-reduced", default=None, help="Ruta para guardar el HTML reducido enviado al LLM")
    parser.add_argument("--dump-cleaned", default=None, help="Ruta para guardar el HTML limpio (sin reducción)")
    args = parser.parse_args()

    print(f"Descargando HTML de {args.url}...")
    html = fetch_html(args.url)

    print("Extrayendo precios (heurística)...")
    heuristic = extract_prices_from_html(html)
    llm_result = None

    if args.llm:
        print("Ejecutando extracción con LLM...")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("ERROR: Definir variable de entorno OPENAI_API_KEY")
        # Reducir HTML antes de enviar al LLM
        original_len = len(html)
        if args.dump_cleaned:
            cleaned = clean_html(html)
            with open(args.dump_cleaned, "w", encoding="utf-8") as f:
                f.write(cleaned)
        html_llm = reduce_html(html, max_chars=args.max_chars)
        reduced_len = len(html_llm)
        print(f"HTML para LLM: {reduced_len} chars (original {original_len})")
        if args.dump_reduced:
            with open(args.dump_reduced, "w", encoding="utf-8") as f:
                f.write(html_llm)
        extractor = LLMExtractor(api_key=api_key, model=args.model)
        llm_result = extractor.extract(html_llm)

    merged = merge_results(heuristic, llm_result)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Precios encontrados: {len(merged['prices'])}")
    print(f"Guardado en {args.output}")
    print(json.dumps(merged, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
