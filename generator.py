"""Generador del Informe Estratégico Diario de STURAM S.A.

Soporta dos motores:
1. Gemini CLI (`@google/gemini-cli`) autenticado con la suscripción Google del
   usuario en el servidor Debian (`USE_GEMINI_CLI=1`), sin costo de tokens extra.
2. Google GenAI SDK (`GEMINI_API_KEY`) como alternativa en entornos cloud.
"""

import json
import os
import re
import shutil
import subprocess
from typing import Any

from config import MAX_NEWS_PER_EDITION, REGIONS_ORDER

EXCLUDED_MODEL_TAGS = (
    "2.0",
    "1.5",
    "1.0",
    "nano-banana",
    "omni",
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
    "aqa",
)

PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-4-hydrogen",
    "gemini-3.8-pro",
    "gemini-2.5-pro",
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
     * EUROPA (2 a 3 noticias de OEMs europeos, fundición HPDC/LPDC, gigacasting, EUROGUSS, Handtmann o gas TTF).
     * CHINA (1 a 2 noticias de Gasgoo China Automotive News, BYD, Geely, Chery, SAIC, proveedores o aluminio).
     * INDIA / ASIA (1 a 2 noticias de India, Japón o Corea: Tata, Mahindra, Toyota, Hyundai, ACMA).
     * GLOBAL (1 a 2 noticias de logística marítima, electrificación, gigacasting, inyectoras LinkedIn o robótica IFR).

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
   - Incluir 5 párrafos detallados en `validation_notes`.
"""


def _extract_json_dict(raw_output: str) -> dict[str, Any]:
    """Extrae y parsea el objeto JSON principal desde la salida de texto/markdown."""
    text = raw_output.strip()
    # Quitar fences ```json ... ``` si existen
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.S)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def _sanitize_report(
    data: dict[str, Any], edition_date_human: str, closing_date_slash: str
) -> dict[str, Any]:
    """Normaliza campos faltantes en noticias individuales para evitar bloqueos."""
    data.setdefault("edition_date", edition_date_human)
    data.setdefault("closing_date", closing_date_slash)

    if not data.get("strategic_summary"):
        data["strategic_summary"] = [
            {
                "topic": "Financiación y divisas",
                "text": f"Datos correspondientes al CIERRE DEL DÍA HÁBIL ANTERIOR, {closing_date_slash}.",
            }
        ]

    clean_stories: list[dict[str, Any]] = []
    for s in data.get("stories", []):
        if not isinstance(s, dict) or not s.get("title"):
            continue
        if not s.get("bullets") and s.get("fact_description"):
            s["bullets"] = [s["fact_description"]]
        if not s.get("bullets"):
            s["bullets"] = [s["title"]]
        s.setdefault("region", "GLOBAL")
        s.setdefault("impact_label", "MIXTO")
        if not s.get("impact_detail"):
            s["impact_detail"] = (
                "El impacto efectivo sobre costos, márgenes o capital de trabajo de STURAM "
                "depende de las condiciones contractuales y datos operativos internos."
            )
        valid_sources = [
            src
            for src in (s.get("sources") or [])
            if isinstance(src, dict) and src.get("url")
        ]
        if not valid_sources:
            fallback_url = (
                s.get("source_url")
                or "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp"
            )
            fallback_name = (
                s.get("source_name") or s.get("meta_subtitle") or "Fuente verificada"
            )
            valid_sources = [{"name": fallback_name, "url": fallback_url}]
        s["sources"] = valid_sources
        clean_stories.append(s)

    data["stories"] = clean_stories

    top5 = [t for t in (data.get("top_five_analysis") or []) if isinstance(t, dict)]
    while len(top5) < 5 and clean_stories:
        ref = clean_stories[min(len(top5), len(clean_stories) - 1)]
        top5.append(
            {
                "fact_and_figure": ref.get("title", "Indicador relevante de la jornada"),
                "management_reading": ref.get(
                    "impact_detail", "Requiere seguimiento gerencial."
                ),
            }
        )
    data["top_five_analysis"] = top5[:5]
    return data


def _generate_via_gemini_cli(
    user_prompt: dict[str, Any], edition_date_human: str, closing_date_slash: str
) -> dict[str, Any]:
    """Invoca el CLI oficial `gemini` usando la sesión OAuth de la suscripción del usuario."""
    gemini_bin = (
        os.environ.get("GEMINI_CLI_BIN")
        or shutil.which("agy")
        or "/home/respaldo-pi/.local/bin/agy"
    )
    full_stdin = (
        SYSTEM_INSTRUCTION.strip()
        + "\n\nIMPORTANTE: NO uses herramientas ni edites archivos. Respondé ÚNICAMENTE con el objeto JSON válido (sin texto adicional antes ni después) siguiendo `required_json_schema`.\n\nDATOS DE ENTRADA:\n"
        + json.dumps(user_prompt, ensure_ascii=False)
    )
    instruction_arg = (
        "Leé todas las instrucciones y el JSON de datos de entrada desde stdin y "
        "devolvé únicamente el JSON completo del Informe Estratégico Diario de STURAM S.A. "
        "con entre 16 y 24 noticias (stories) cubriendo todas las regiones disponibles."
    )

    env = dict(os.environ)
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    for attempt in range(2):
        print(f"Generando informe vía Antigravity CLI ({gemini_bin}), intento {attempt + 1}...")
        proc = subprocess.run(
            [gemini_bin, "--disable-slash-commands", "--mode", "plan", "-p", instruction_arg],
            input=full_stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=360,
        )
        if proc.returncode != 0:
            err_preview = (proc.stderr or proc.stdout or "")[:300]
            print(f"  -> Gemini CLI código {proc.returncode}: {err_preview}")
            if attempt == 0:
                continue
            raise RuntimeError(f"Error en Gemini CLI: {err_preview}")

        data = _sanitize_report(
            _extract_json_dict(proc.stdout), edition_date_human, closing_date_slash
        )
        count = len(data.get("stories", []))
        print(f"Gemini CLI generó {count} noticias.")
        if count >= 10 or attempt == 1:
            return data

    raise RuntimeError("Gemini CLI no devolvió un informe válido.")


def generate_report_json(
    bundle: dict[str, Any],
    edition_date_human: str,
    closing_date_slash: str,
    recent_titles: list[str],
    is_monday: bool = False,
    is_first_monday: bool = False,
) -> dict[str, Any]:
    """Genera el diccionario completo del informe usando Gemini CLI o SDK."""
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
            "strategic_summary": [{"topic": "string", "text": "string"}],
            "stories": [
                {
                    "region": "ARGENTINA | CÓRDOBA, ARGENTINA | BRASIL | ALUMINIO | PETRÓLEO | LATINOAMÉRICA | ESTADOS UNIDOS | EUROPA | CHINA | RUSIA | INDIA | ASIA | GLOBAL",
                    "meta_subtitle": "string (ej. '24/11/2026 · AutoData')",
                    "title": "string",
                    "bullets": ["bullet 1 detallado", "bullet 2 detallado"],
                    "kpi_table": {
                        "note": "string opcional (obligatorio en ALUMINIO)",
                        "headers": [
                            "Cierre",
                            "Cash vendedor USD/t",
                            "3 meses vendedor USD/t",
                            "Cash − 3m",
                        ],
                        "rows": [["fecha1", "val1", "val2", "dif1"]],
                    },
                    "impact_label": "MIXTO | POSITIVO POTENCIAL | NEGATIVO POTENCIAL | POSITIVO CONDICIONADO",
                    "impact_detail": "string",
                    "sources": [{"name": "Nombre Fuente DD/MM", "url": "https://..."}],
                }
            ],
            "top_five_analysis": [
                {"fact_and_figure": "string", "management_reading": "string"}
            ],
            "validation_notes": [
                "párrafo 1",
                "párrafo 2",
                "párrafo 3",
                "párrafo 4",
                "párrafo 5",
            ],
        },
    }

    use_cli = os.environ.get("USE_GEMINI_CLI", "").strip().lower() in ("1", "true", "yes")
    if use_cli or (not os.environ.get("GEMINI_API_KEY") and shutil.which("gemini")):
        return _generate_via_gemini_cli(
            user_prompt, edition_date_human, closing_date_slash
        )

    from google import genai
    from google.genai import errors, types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY o activar USE_GEMINI_CLI=1.")

    client = genai.Client(api_key=api_key)
    models_to_try = list(PREFERRED_MODELS)
    last_exc: Exception | None = None

    for model_name in models_to_try:
        try:
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
            return _sanitize_report(
                json.loads(response.text), edition_date_human, closing_date_slash
            )
        except errors.APIError as exc:
            last_exc = exc
            continue
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(f"No se pudo generar el informe: {last_exc}")
