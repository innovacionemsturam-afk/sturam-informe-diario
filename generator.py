"""Generador del Informe Estratégico Diario de STURAM S.A. con cobertura
multirregional garantizada (15 a 24 noticias) y diseño aprobado del 18/11/2026.
"""

import json
import os
import time
from typing import Any

from google import genai
from google.genai import errors, types

from config import MAX_NEWS_PER_EDITION, REGIONS_ORDER

# Excluir modelos lite, imagen, audio y especializados para evitar respuestas truncadas
EXCLUDED_MODEL_TAGS = (
    "lite",
    "embedding",
    "image",
    "tts",
    "audio",
    "live",
    "robotics",
    "computer-use",
    "veo",
    "imagen",
    "customtools",
    "bisect",
)

PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.8-flash",
    "gemini-2.5-pro",
    "gemini-3.8-pro",
    "gemini-3-flash-preview",
]

SYSTEM_INSTRUCTION = f"""
Actuá como el equipo profesional de inteligencia económica, financiera, industrial,
comercial y tecnológica de STURAM S.A. (fundición de aluminio HPDC/LPDC/gravedad y
mecanizado de precisión en Córdoba, Argentina).

Debés redactar el INFORME ESTRATÉGICO DIARIO replicando EXACTAMENTE el rigor, la
cobertura geográfica completa, la estructura de múltiples bullets por noticia, las
tablas KPI y las Notas de Validación de la edición modelo del 18/11/2026.

REGLAS OBLIGATORIAS DE COBERTURA Y VOLUMEN:
1. CANTIDAD MÍNIMA Y MÁXIMA:
   - Debés desarrollar ENTRE 16 Y 24 NOTICIAS (`stories`) en cada edición (nunca menos de 14,
     máximo {MAX_NEWS_PER_EDITION}).
   - Es OBLIGATORIO recorrer todas las regiones y categorías presentes en `news_candidates`:
     * ARGENTINA (mínimo 2 noticias: #01 cuadro completo de divisas BNA, mayorista, A3500 SML BCB,
       MEP, CCL, tasas oficiales del BCRA: OBLIGATORIO informar TAMAR bancos privados en % TNA y TEA,
       BADLAR bancos privados en % TNA y TEA, y tasa de adelantos en cuenta corriente en % TNA con su
       fecha exacta, IPC INDEC y riesgo país/Merval; #02+ actividad industrial, UIA, ADEFA, AFAC,
       ADIMRA, energía o política económica).
     * CÓRDOBA, ARGENTINA (1 a 2 noticias sobre UOM, SMATA, metalúrgicas o automotrices cordobesas).
     * BRASIL (3 a 4 noticias: #1 Dólar PTAX comprador/vendedor, variación % y Selic Copom;
       #2 a #4 noticias industriales de AutoData, ANFAVEA, Sindipeças, Volkswagen, Toyota,
       Stellantis, BYD, GAC o política energética/fiscal brasileña).
     * ALUMINIO (1 noticia exhaustiva con los datos oficiales de Westmetall LME: cash vendedor
       USD/t, 3 meses USD/t, variación %, diferencial cash - 3m en backwardation/contango,
       inventarios LME en toneladas + `kpi_table` obligatoria comparando las últimas 2 ruedas).
     * PETRÓLEO (1 a 2 noticias con cierres Brent y WTI, variación diaria, EIA/OilPrice, OPEP y fletes).
     * LATINOAMÉRICA (1 a 2 noticias de México / Cluster Industrial / autopartes / inversiones).
     * ESTADOS UNIDOS (1 a 2 noticias de OEMs, IA industrial, robótica, CNC o comercio exterior).
     * EUROPA (2 a 3 noticias de OEMs europeos, fundición HPDC/LPDC, EUROGUSS, Handtmann o gas TTF).
     * CHINA (1 a 2 noticias de fabricantes chinos BYD, Geely, Chery, SAIC, proveedores o aluminio).
     * INDIA / ASIA (1 a 2 noticias de India, Japón o Corea: Tata, Mahindra, Toyota, Hyundai, ACMA).
     * GLOBAL (1 a 2 noticias de logística marítima, electrificación, sostenibilidad o robótica IFR).

2. ORDEN EXACTO DE LAS REGIONES EN `stories`:
   {", ".join(REGIONS_ORDER)}.

3. PROFUNDIDAD DE CADA NOTICIA:
   - Utilizar toda la información de `snippet` y `article_excerpt` provista en el bundle.
   - `bullets`: entre 2 y 3 bullets densos y analíticos por noticia, incluyendo cifras,
     porcentajes, contexto sectorial y distinguiendo expresamente entre propuestas/anuncios
     y normas/hechos efectivamente vigentes.
   - `impact_label`: "MIXTO", "POSITIVO POTENCIAL", "NEGATIVO POTENCIAL" o "POSITIVO CONDICIONADO".
   - `impact_detail`: 2 a 3 oraciones explicando el mecanismo concreto sobre costos, primas
     físicas, aleaciones, HPDC/CNC, capital de trabajo o competitividad de STURAM, aclarando
     qué datos internos o contratos se requieren para cuantificarlo.
   - `sources`: lista con el nombre del medio + fecha y la URL real provista en el bundle.

4. ANTI-DUPLICACIÓN Y NOTAS DE VALIDACIÓN:
   - NO repetir noticias cuyos hechos específicos ya figuren en `recent_sent_titles_to_avoid`.
   - Incluir 8 bloques temáticos en `strategic_summary` (comenzando Financiación y divisas con
     "Datos correspondientes al CIERRE DEL DÍA HÁBIL ANTERIOR, <closing_date>:" e incluyendo
     obligatoriamente TAMAR, BADLAR, adelantos y Dólar Oficial A3500).
   - Incluir exactamente 5 prioridades en `top_five_analysis`.
   - Incluir 5 párrafos detallados en `validation_notes` (fecha de cierre, titulares previos
     cotejados y excluidos, relevamiento UOM/SMATA, nómina de las fuentes consultadas y
     precisión metodológica).
"""


def _discover_fallback_models(client: genai.Client, exclude: str) -> list[str]:
    """Lista modelos completos (no lite) disponibles que soporten generateContent."""
    available: set[str] = set()
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if not name or name == exclude:
                continue
            if any(tag in name.lower() for tag in EXCLUDED_MODEL_TAGS):
                continue
            if actions and "generateContent" not in actions:
                continue
            if "gemini" in name.lower():
                available.add(name)
    except Exception:
        pass

    ordered = [m for m in PREFERRED_MODELS if m in available and m != exclude]
    remaining = sorted(m for m in available if m not in ordered)
    return (ordered + remaining)[:5]


def generate_report_json(
    bundle: dict[str, Any],
    edition_date_human: str,
    closing_date_slash: str,
    recent_titles: list[str],
    is_monday: bool = False,
    is_first_monday: bool = False,
) -> dict[str, Any]:
    """Genera el diccionario completo del informe estratégico diario garantizando >=14 noticias."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")

    client = genai.Client(api_key=api_key)

    user_prompt = {
        "edition_date": edition_date_human,
        "closing_date": closing_date_slash,
        "is_monday": is_monday,
        "is_first_monday_of_month": is_first_monday,
        "minimum_required_stories": 16,
        "recent_sent_titles_to_avoid": recent_titles[-45:],
        "market_and_news_bundle": bundle,
        "required_json_schema": {
            "edition_date": "string (ej. '25 de noviembre de 2026')",
            "closing_date": "string (ej. '24/11/2026')",
            "strategic_summary": [
                {"topic": "string", "text": "string"}
            ],
            "stories": [
                {
                    "region": "ARGENTINA | CÓRDOBA, ARGENTINA | BRASIL | ALUMINIO | PETRÓLEO | LATINOAMÉRICA | ESTADOS UNIDOS | EUROPA | CHINA | RUSIA | INDIA | ASIA | GLOBAL",
                    "meta_subtitle": "string (ej. '24/11/2026 · AutoData')",
                    "title": "string",
                    "bullets": ["bullet 1 detallado", "bullet 2 detallado"],
                    "kpi_table": {
                        "note": "string opcional (obligatorio en ALUMINIO)",
                        "headers": ["Cierre", "Cash vendedor USD/t", "3 meses vendedor USD/t", "Cash − 3m"],
                        "rows": [["fecha1", "val1", "val2", "dif1"]],
                    },
                    "impact_label": "MIXTO | POSITIVO POTENCIAL | NEGATIVO POTENCIAL | POSITIVO CONDICIONADO",
                    "impact_detail": "string",
                    "sources": [{"name": "Nombre Fuente DD/MM", "url": "https://..."}],
                }
            ],
            "top_five_analysis": [
                {
                    "fact_and_figure": "string",
                    "management_reading": "string",
                }
            ],
            "validation_notes": ["párrafo 1", "párrafo 2", "párrafo 3", "párrafo 4", "párrafo 5"],
        },
    }

    models_to_try = ["gemini-2.5-flash", "gemini-3.8-flash"]
    for m in _discover_fallback_models(client, exclude=""):
        if m not in models_to_try:
            models_to_try.append(m)

    last_exc: Exception | None = None

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                print(f"Generando informe con modelo: {model_name} (intento {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=json.dumps(user_prompt, ensure_ascii=False),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        max_output_tokens=16384,
                        temperature=0.2,
                    ),
                )
                data = json.loads(response.text)
                stories_count = len(data.get("stories", []))
                print(f"Modelo {model_name} generó {stories_count} noticias.")
                if stories_count < 12:
                    last_exc = RuntimeError(
                        f"El modelo {model_name} devolvió solo {stories_count} noticias (<12)."
                    )
                    continue
                return data
            except errors.APIError as exc:
                last_exc = exc
                code = getattr(exc, "code", None)
                msg = str(exc)
                if code == 429 and "limit: 0" in msg:
                    break
                if code in (429, 500, 503):
                    time.sleep(8 * (attempt + 1))
                    continue
                if code == 404:
                    break
                raise
            except Exception as exc:
                last_exc = exc
                continue

    raise RuntimeError(f"No se pudo generar el informe completo tras reintentos: {last_exc}")
