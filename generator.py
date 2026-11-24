"""Generador del Informe Estratégico Diario de STURAM S.A. con el formato,
profundidad y rigor metodológico de la edición aprobada del 18/11/2026.
"""

import json
import os
import time
from typing import Any

from google import genai
from google.genai import errors, types

from config import MAX_NEWS_PER_EDITION, REGIONS_ORDER

EXCLUDED_MODEL_TAGS = (
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
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.8-pro",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
]

SYSTEM_INSTRUCTION = f"""
Actuá como el equipo profesional de inteligencia económica, financiera, industrial,
comercial y tecnológica de STURAM S.A. (fundición de aluminio HPDC/LPDC/gravedad y
mecanizado de precisión en Córdoba, Argentina).

Debés redactar el INFORME ESTRATÉGICO DIARIO replicando EXACTAMENTE el rigor, la
estructura de múltiples bullets por noticia, las tablas KPI y las Notas de Validación
de la edición modelo del 18/11/2026:

1. PRINCIPIO FUNDAMENTAL:
   - NO INVENTAR datos ni atribuir contratos, tasas (CFT), ahorros o volúmenes a STURAM
     sin datos internos.
   - NO REPETIR ninguna noticia o hecho de ediciones anteriores listados en
     `recent_sent_titles_to_avoid` (salvo la actualización diaria obligatoria de
     cotizaciones financieras, PTAX, LME y petróleo con los valores de la nueva rueda).
   - Distinguir siempre en el texto entre anuncios/propuestas y normas/desembolsos vigentes.

2. RESUMEN ESTRATÉGICO (strategic_summary):
   - Incluir entre 6 y 8 bloques temáticos densos:
     * "Financiación y divisas": comenzar expresamente con "Datos correspondientes al
       CIERRE DEL DÍA HÁBIL ANTERIOR, <fecha>:" seguido de BNA compra/venta, mayorista
       de referencia A3500 exacto (de bcb_sml_a3500_ptax), MEP, CCL, referencia TAMAR y
       adelantos del BCRA (aclarando que difieren del CFT de STURAM) y riesgo país.
     * "Insumos y aluminio": LME cash vendedor y 3 meses de lme_westmetall con variación %,
       backwardation/contango e inventarios en toneladas, diferenciando de primas físicas
       y aleaciones secundarias.
     * "Córdoba, Arg." (si hay novedad verificada).
     * "Producción y clientes"
     * "Competencia y nuevas plantas" (excluyendo siempre a Fundal)
     * "IA industrial y robótica"
     * "Energía y sostenibilidad"
     * "Comercio, abastecimiento y logística"

3. NOTICIAS DESARROLLADAS (stories — entre 15 y 22 noticias nuevas, máx {MAX_NEWS_PER_EDITION}):
   - Ordenar estrictamente según la secuencia de regiones:
     {", ".join(REGIONS_ORDER)} (omitiendo regiones sin novedades verificadas).
   - Noticia 01 (ARGENTINA): "Divisas, riesgo país e indicadores financieros del último cierre"
     con 3 a 4 bullets detallando BNA, mayorista, A3500 SML BCB (con 4 decimales), MEP, CCL,
     tasas BCRA (TAMAR y adelantos con su fecha exacta), IPC INDEC de referencia y Riesgo País/Merval.
   - Primera noticia de BRASIL: Dólar PTAX (comprador/vendedor y variación % frente a la
     rueda previa) y tasa Selic Copom, seguido de las noticias industriales de Brasil
     (AutoData, Automotive Business, ANFAVEA, Sindipeças, terminales).
   - Noticia de ALUMINIO: 3 bullets analizando el cierre oficial LME de Westmetall
     (cash USD/t, 3 meses USD/t, diferencial cash - 3m, stock en toneladas y variación %)
     E INCLUIR OBLIGATORIAMENTE `kpi_table` con:
       headers: ["Cierre", "Cash vendedor USD/t", "3 meses vendedor USD/t", "Cash − 3m"]
       rows: [fila rueda previa, fila última rueda, fila "Variación diaria" con % y USD/t].
   - Para CADA noticia:
     * `bullets`: lista de 2 a 4 bullets completos y analíticos (con cifras, porcentajes,
       contexto industrial y aclaración de vigencia real).
     * `impact_label`: "MIXTO", "POSITIVO POTENCIAL", "NEGATIVO POTENCIAL" o "POSITIVO CONDICIONADO".
     * `impact_detail`: 2 a 3 oraciones precisas sobre el mecanismo económico/productivo
       para STURAM (HPDC, CNC, aleaciones, capital de trabajo, fletes) y qué condiciones
       contractuales o datos internos se requieren para cuantificarlo.
     * `sources`: lista de objetos {{"name": "Nombre Fuente DD/MM", "url": "https://..."}}
       usando las URLs reales del bundle.

4. ANÁLISIS GERENCIAL FINAL (top_five_analysis):
   - Exactamente 5 filas ordenadas por materialidad (1 a 5), con `fact_and_figure` y
     `management_reading` (lectura gerencial específica para STURAM).

5. NOTAS DE VALIDACIÓN (validation_notes):
   - Lista de 5 párrafos explicando:
     1) Fecha de la edición y fecha de cierre de las cotizaciones.
     2) Constancia expresa de qué titulares de la edición previa (`recent_sent_titles_to_avoid`)
        fueron cotejados y excluidos para evitar duplicaciones.
     3) Estado del relevamiento diario de UOM y SMATA.
     4) Nómina de fuentes oficiales y sectoriales consultadas en la corrida.
     5) Nota de precisión metodológica (diferenciación entre anuncios y ejecución efectiva).
"""


def _discover_fallback_models(client: genai.Client, exclude: str) -> list[str]:
    """Lista modelos de texto disponibles en la cuenta que soporten generateContent."""
    available: set[str] = set()
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if not name or name == exclude:
                continue
            if any(tag in name for tag in EXCLUDED_MODEL_TAGS):
                continue
            if actions and "generateContent" not in actions:
                continue
            if "gemini" in name:
                available.add(name)
    except Exception:
        pass

    ordered = [m for m in PREFERRED_MODELS if m in available and m != exclude]
    remaining = sorted(m for m in available if m not in ordered)
    return (ordered + remaining)[:6]


def generate_report_json(
    bundle: dict[str, Any],
    edition_date_human: str,
    closing_date_slash: str,
    recent_titles: list[str],
    is_monday: bool = False,
    is_first_monday: bool = False,
) -> dict[str, Any]:
    """Genera el diccionario completo del informe estratégico diario."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")

    client = genai.Client(api_key=api_key)

    user_prompt = {
        "edition_date": edition_date_human,
        "closing_date": closing_date_slash,
        "is_monday": is_monday,
        "is_first_monday_of_month": is_first_monday,
        "recent_sent_titles_to_avoid": recent_titles[-50:],
        "market_and_news_bundle": bundle,
        "required_json_schema": {
            "edition_date": "string (ej. '24 de noviembre de 2026')",
            "closing_date": "string (ej. '23/11/2026')",
            "strategic_summary": [
                {"topic": "string", "text": "string"}
            ],
            "stories": [
                {
                    "region": "ARGENTINA | CÓRDOBA, ARGENTINA | BRASIL | ALUMINIO | PETRÓLEO | LATINOAMÉRICA | ESTADOS UNIDOS | EUROPA | CHINA | RUSIA | INDIA | ASIA | GLOBAL",
                    "meta_subtitle": "string (ej. 'Cierre 23/11/2026 · AutoData')",
                    "title": "string",
                    "bullets": ["bullet 1 con datos y contexto", "bullet 2 con cifras y alcance"],
                    "kpi_table": {
                        "note": "string opcional",
                        "headers": ["col1", "col2", "col3", "col4"],
                        "rows": [["val1", "val2", "val3", "val4"]],
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

    models_to_try = ["gemini-3.8-flash"]
    models_to_try.extend(_discover_fallback_models(client, exclude="gemini-3.8-flash"))
    last_exc: Exception | None = None

    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=json.dumps(user_prompt, ensure_ascii=False),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        temperature=0.15,
                    ),
                )
                return json.loads(response.text)
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

    raise RuntimeError(f"No se pudo generar el informe tras reintentos: {last_exc}")
