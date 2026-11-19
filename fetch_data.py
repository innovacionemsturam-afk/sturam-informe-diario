"""Recolección de indicadores económicos y noticias vía APIs públicas y RSS.

Cada fuente es tolerante a fallos: si una fuente secundaria no responde,
se registra la advertencia sin bloquear el resto del informe (Sección 2 y 14).
"""

from datetime import datetime
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET
import urllib.request
import json

from config import TZ_CORDOBA

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SturamIntelBot/1.0)"}


def _get_json(url: str, timeout: int = 12) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_text(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_argentina_indicators() -> dict[str, Any]:
    """Obtiene cotizaciones de dólar, riesgo país e inflación de APIs públicas."""
    result: dict[str, Any] = {"warnings": []}

    # Dólares: oficial, mayorista, MEP, CCL
    try:
        dolares = _get_json("https://dolarapi.com/v1/dolares")
        result["dolares"] = [
            {
                "casa": d.get("casa"),
                "nombre": d.get("nombre"),
                "compra": d.get("compra"),
                "venta": d.get("venta"),
                "fechaActualizacion": d.get("fechaActualizacion"),
            }
            for d in dolares
            if d.get("casa") in {"oficial", "mayorista", "bolsa", "contadoconliqui"}
        ]
    except Exception as exc:
        result["warnings"].append(f"dolarapi: {exc}")

    # Riesgo país
    try:
        rp = _get_json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo")
        result["riesgo_pais"] = rp
    except Exception as exc:
        result["warnings"].append(f"riesgo_pais: {exc}")

    # Inflación mensual e interanual
    try:
        inf_m = _get_json("https://api.argentinadatos.com/v1/finanzas/indices/inflacion")
        inf_ia = _get_json("https://api.argentinadatos.com/v1/finanzas/indices/inflacionInteranual")
        result["inflacion_mensual_ultima"] = inf_m[-1] if inf_m else None
        result["inflacion_interanual_ultima"] = inf_ia[-1] if inf_ia else None
    except Exception as exc:
        result["warnings"].append(f"inflacion: {exc}")

    return result


def fetch_brazil_indicators() -> dict[str, Any]:
    """Obtiene PTAX USD/BRL y tasa Selic desde el Banco Central do Brasil."""
    result: dict[str, Any] = {"warnings": []}
    try:
        # Serie 1: PTAX venta, Serie 10813: PTAX compra, Serie 432: Meta Selic
        for name, serie in [("ptax_venta", 1), ("ptax_compra", 10813), ("selic_meta", 432)]:
            url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/2?formato=json"
            result[name] = _get_json(url)
    except Exception as exc:
        result["warnings"].append(f"bcb_brasil: {exc}")
    return result


def fetch_commodities() -> dict[str, Any]:
    """Obtiene último cierre y variación de Aluminio (ALI=F), Brent (BZ=F) y WTI (CL=F)."""
    result: dict[str, Any] = {"warnings": []}
    symbols = {"aluminio_futuro": "ALI=F", "brent": "BZ=F", "wti": "CL=F"}
    for key, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
            data = _get_json(url)
            meta = data["chart"]["result"][0]["meta"]
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            valid_closes = [c for c in closes if c is not None]
            last_close = valid_closes[-1] if valid_closes else meta.get("regularMarketPrice")
            prev_close = valid_closes[-2] if len(valid_closes) >= 2 else meta.get("chartPreviousClose")
            pct = ((last_close - prev_close) / prev_close * 100.0) if (last_close and prev_close) else None
            result[key] = {
                "symbol": sym,
                "last_close": round(last_close, 2) if last_close else None,
                "prev_close": round(prev_close, 2) if prev_close else None,
                "daily_pct": round(pct, 2) if pct is not None else None,
                "currency": meta.get("currency"),
            }
        except Exception as exc:
            result["warnings"].append(f"{key}: {exc}")
    return result


def fetch_google_news_rss(query: str, hl: str = "es-419", gl: str = "AR", max_items: int = 5) -> list[dict[str, str]]:
    """Consulta titulares recientes en Google News RSS."""
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={gl}:es-419"
    items: list[dict[str, str]] = []
    try:
        xml_text = _get_text(url)
        root = ET.fromstring(xml_text)
        for item in root.findall("./channel/item")[:max_items]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
            if title and link:
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "pubDate": pub_date,
                        "source": source,
                    }
                )
    except Exception:
        pass
    return items


def collect_daily_bundle() -> dict[str, Any]:
    """Reúne todos los datos de mercado y noticias para pasarle al generador."""
    now = datetime.now(TZ_CORDOBA)
    queries = {
        "ARGENTINA_FINANZAS": "BCRA economia dolar inflacion industria Argentina when:2d",
        "CORDOBA": "Cordoba industria automotriz metalurgica energia UOM SMATA when:3d",
        "GREMIOS": "UOM OR SMATA paritarias suspensiones automotriz Argentina when:3d",
        "BRASIL": "ANFAVEA OR industria automotiva Brasil economia Selic when:2d",
        "ALUMINIO": "LME aluminum price OR aluminium smelting supply demand when:3d",
        "PETROLEO": "Brent WTI oil price OPEC energy gas when:2d",
        "AUTOMOTRICES": "Stellantis OR Volkswagen OR IVECO OR Toyota OR Mercedes Benz produccion planta inversion when:3d",
        "COMPETIDORES_FUNDICION": "Nemak OR CIE Automotive OR Handtmann OR Ryobi OR die casting HPDC aluminum when:7d",
        "IA_ROBOTICA": "industrial AI robotics CNC die casting predictive maintenance manufacturing when:3d",
        "SOSTENIBILIDAD": "recycled aluminum low carbon automotive supply chain ESG when:5d",
    }

    news_by_topic = {k: fetch_google_news_rss(q, max_items=5) for k, q in queries.items()}

    return {
        "collected_at": now.isoformat(),
        "argentina": fetch_argentina_indicators(),
        "brasil": fetch_brazil_indicators(),
        "commodities": fetch_commodities(),
        "news_candidates": news_by_topic,
    }
