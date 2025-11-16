import os
import math
from typing import List, Dict
from openai import OpenAI
from dataclasses import dataclass
import re

SYSTEM_PROMPT = """Eres un asistente experto en extracción de precios desde HTML plano. Devuelves SOLO JSON válido.
Extrae todos los precios, incluso aquellos en listas, tablas o texto corrido. 
Normaliza:
- currency: ISO 4217 si es posible
- value: número decimal
Incluye contexto breve (max 120 chars) que ayude a identificar el producto o condición.
Formato de salida:
{
  "prices": [
    {"raw": "$199", "value": 199.0, "currency": "USD", "context": "Título/fragmento"}
  ]
}
Si no hay precios devuelve {"prices": []}.
No añadas comentarios ni texto fuera del JSON."""

@dataclass
class LLMPrice:
    raw: str
    value: float
    currency: str
    context: str

PRICE_VALUE_FIX = re.compile(r'"value"\s*:\s*"(\d+(?:\.\d+)?)"')

class LLMExtractor:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4.1-mini"):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no definido.")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _chunk(self, text: str, max_chars: int = 12000) -> List[str]:
        text = re.sub(r"\s+", " ", text)
        if len(text) <= max_chars:
            return [text]
        parts = []
        chunk_count = math.ceil(len(text) / max_chars)
        for i in range(chunk_count):
            parts.append(text[i*max_chars:(i+1)*max_chars])
        return parts

    def _build_user_prompt(self, chunk: str) -> str:
        return f"HTML PLANO:\n{chunk}\n\nTarea: Extrae precios en JSON como se indicó."

    def extract(self, html_text: str) -> Dict:
        chunks = self._chunk(html_text)
        merged: Dict[str, List[Dict]] = {"prices": []}
        for idx, chunk in enumerate(chunks):
            prompt = self._build_user_prompt(chunk)
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            content = response.choices[0].message.content.strip()
            # Fix possible value quoted as string
            content = PRICE_VALUE_FIX.sub(r'"value": \1', content)
            # Ensure starts with '{'
            if not content.startswith('{'):
                first_brace = content.find('{')
                if first_brace != -1:
                    content = content[first_brace:]
            # Try parse
            import json
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                data = {"prices": []}
            for p in data.get("prices", []):
                # basic normalization
                if isinstance(p.get("value"), str):
                    try:
                        p["value"] = float(p["value"].replace(',', '.'))
                    except ValueError:
                        continue
                merged["prices"].append(p)
        # Deduplicate by (value,currency,raw)
        seen = set()
        dedup = []
        for p in merged["prices"]:
            key = (round(p.get("value", 0), 4), p.get("currency"), p.get("raw"))
            if key not in seen:
                seen.add(key)
                dedup.append(p)
        merged["prices"] = dedup
        return merged

__all__ = ["LLMExtractor"]
