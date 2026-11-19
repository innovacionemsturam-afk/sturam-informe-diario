"""Generador del informe usando Google Gemini (SDK google-genai) con JSON estructurado."""

import json
import os
from typing import Any

from google import genai
from google.genai import types

from config import REGIONS_ORDER, MAX_NEWS_PER_EDITION

SYSTEM_INSTRUCTION = f"""
Actuá como un equipo profesional de inteligencia económica, financiera, industrial,
comercial y tecnológica especializado en la industria automotriz, la fundición de
aluminio (HPDC/LPDC/gravedad) y el mecanizado de precisión, elaborando el
INFORME ESTRATÉGICO DIARIO DE STURAM S.A. (empresa industrial de Córdoba, Argentina).

REGLAS INQUEBRANTABLES:
1. NO INVENTAR cifras, fechas, fuentes ni noticias. Usar EXCLUSIVAMENTE los datos y
   titulares provistos en el bundle de entrada (o marcar explícitamente cuando un dato
   corresponda al CIERRE DEL DÍA HÁBIL ANTERIOR).
2. NO DUPLICAR noticias ya presentes en recent_titles.
3. Máximo {MAX_NEWS_PER_EDITION} noticias en total. Calidad y profundidad sobre cantidad.
4. Orden exacto de regiones (omitir las que no tengan novedades):
   {", ".join(REGIONS_ORDER)}.
5. Regla LME Aluminio: si la variación diaria es menor al 2%, indicar "se mantiene estable"
   sin inventar explicaciones. Diferenciar aluminio primario LME de aleaciones secundarias
   y primas físicas.
6. Distinguir tasas de mercado del CFT aplicable a STURAM, y precios internacionales de
   petróleo/gas de las tarifas efectivamente pagadas por STURAM.
7. Excluir a Fundal de la lista de competidores.
8. En cada noticia:
   - fact_description: hasta 4 líneas con cifras concretas, causas y fuente.
   - impact_label: POSITIVO, NEGATIVO o MIXTO.
   - impact_detail: 2 a 3 líneas identificando qué costo/ingreso/margen/riesgo se ve
     afectado, el mecanismo productivo o económico, y qué dato interno falta para cuantificarlo.
9. Cerrar con exactamente 5 elementos en top_five_analysis ordenados por materialidad.
"""


def generate_report_json(
    bundle: dict[str, Any],
    edition_date_human: str,
    recent_titles: list[str],
    is_monday: bool = False,
    is_first_monday: bool = False,
) -> dict[str, Any]:
    """Llama a Gemini y devuelve el diccionario estructurado del informe."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")

    client = genai.Client(api_key=api_key)

    user_prompt = {
        "edition_date": edition_date_human,
        "is_monday": is_monday,
        "is_first_monday_of_month": is_first_monday,
        "recent_sent_titles_to_avoid": recent_titles[-60:],
        "market_and_news_bundle": bundle,
        "required_json_schema": {
            "edition_date": "string (fecha completa en español)",
            "strategic_summary": [
                {"topic": "string", "text": "Hecho -> causa -> impacto STURAM (incluir 'CIERRE DEL DÍA HÁBIL ANTERIOR' en financiación y divisas)"}
            ],
            "regions": [
                {
                    "region": "una de las regiones exactas de REGIONS_ORDER",
                    "news": [
                        {
                            "title": "string",
                            "published_date": "DD/MM/YYYY",
                            "data_date": "DD/MM/YYYY",
                            "fact_description": "string",
                            "source_name": "string",
                            "source_url": "string (URL real del bundle)",
                            "impact_label": "POSITIVO | NEGATIVO | MIXTO",
                            "impact_detail": "string",
                        }
                    ],
                }
            ],
            "special_bulletins": [
                {"title": "string", "body": "string (solo si is_monday o is_first_monday_of_month es true, sino [])"}
            ],
            "top_five_analysis": [
                {
                    "fact_and_figure": "string",
                    "risk_or_opportunity": "Riesgo | Oportunidad | Mixto",
                    "mechanism": "string",
                    "horizon": "Corto plazo | Mediano plazo | Largo plazo",
                    "what_to_watch": "string",
                }
            ],
        },
    }

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=json.dumps(user_prompt, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    return json.loads(response.text)
