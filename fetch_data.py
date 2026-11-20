"""Recolección de indicadores económicos y noticias vía APIs públicas y RSS.

Cada fuente es tolerante a fallos y se ejecuta en paralelo: si una fuente
secundaria no responde o tiene paywall, se omite sin bloquear el informe.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET
import urllib.request
import json

from config import TZ_CORDOBA

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SturamIntelBot/1.0)"}


def _get_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_argentina_indicators() -> dict[str, Any]:
    """Obtiene cotizaciones de dólar, riesgo país e inflación de APIs públicas."""
    result: dict[str, Any] = {"warnings": []}

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

    try:
        rp = _get_json("https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo")
        result["riesgo_pais"] = rp
    except Exception as exc:
        result["warnings"].append(f"riesgo_pais: {exc}")

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


def fetch_rss_feed(url: str, default_source: str, max_items: int = 5) -> list[dict[str, str]]:
    """Lee cualquier feed RSS público estándar sin bloquear si falla."""
    items: list[dict[str, str]] = []
    try:
        xml_text = _get_text(url)
        root = ET.fromstring(xml_text)
        for item in root.findall("./channel/item")[:max_items]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else default_source
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


def fetch_google_news_rss(
    query: str, hl: str = "es-419", gl: str = "AR", max_items: int = 5
) -> list[dict[str, str]]:
    """Consulta titulares recientes en Google News RSS."""
    ceid = f"{gl}:{'es-419' if hl.startswith('es') else 'en'}"
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    return fetch_rss_feed(url, default_source="Google News", max_items=max_items)


def collect_daily_bundle() -> dict[str, Any]:
    """Reúne todos los datos de mercado y noticias en paralelo."""
    now = datetime.now(TZ_CORDOBA)

    # Consultas Google News RSS (español + inglés para fuentes globales abiertas)
    gn_queries: dict[str, tuple[str, str, str]] = {
        "ARGENTINA_FINANZAS": ("(BCRA OR \"dolar oficial\" OR tasas OR TAMAR OR \"El Cronista\" OR \"Ambito\" OR Infobae OR \"La Nacion\") economia Argentina when:2d", "es-419", "AR"),
        "ARGENTINA_AUTOMOTRIZ": ("(ADEFA OR AFAC OR ADIMRA) produccion exportacion metalurgia automotriz Argentina when:5d", "es-419", "AR"),
        "CORDOBA": ("Cordoba industria automotriz metalurgica energia UOM SMATA when:3d", "es-419", "AR"),
        "GREMIOS": ("UOM OR SMATA paritarias suspensiones automotriz Argentina when:3d", "es-419", "AR"),
        "BRASIL": ("(ANFAVEA OR ABIFA OR AutoData OR \"Automotive Business\" OR \"Valor Economico\") Brasil automotiva economia when:3d", "es-419", "AR"),
        "MEXICO_LATAM": ("(\"Cluster Industrial\" OR \"El Economista\") Mexico automotriz Nissan BMW Stellantis GM Ford Tesla when:4d", "es-419", "MX"),
        "EEUU_AUTOMOTRIZ": ("(Tesla OR \"General Motors\" OR Ford OR Rivian OR Lucid) EV production plant supplier when:3d", "en-US", "US"),
        "EUROPA_AUTOMOTRIZ": ("(\"Volkswagen Group\" OR BMW OR \"Mercedes-Benz\" OR Stellantis OR Renault OR Volvo OR JLR) Europe plant production when:3d", "en-US", "US"),
        "CHINA_AUTOMOTRIZ": ("(BYD OR Geely OR Chery OR SAIC OR XPeng OR NIO OR \"Li Auto\" OR Gasgoo OR \"Caixin\") EV casting China when:4d", "en-US", "US"),
        "INDIA_ASIA_AUTOMOTRIZ": ("(\"Tata Motors\" OR Mahindra OR \"Maruti Suzuki\" OR \"Autocar Professional\" OR \"Economic Times\" OR \"Nikkei Asia\") auto manufacturing when:4d", "en-US", "US"),
        "JAPON_COREA_AUTOMOTRIZ": ("(Toyota OR Honda OR Nissan OR Hyundai OR Kia OR Mazda OR Subaru) production supply chain when:4d", "en-US", "US"),
        "ALUMINIO_LME": ("LME aluminum price OR \"London Metal Exchange\" aluminium supply demand when:3d", "en-US", "US"),
        "ASOCIACIONES_FUNDICION": ("(\"American Foundry Society\" OR \"Modern Casting\" OR NADCA OR \"Die Casting Engineer\" OR \"Foundry-Planet\" OR \"Global Casting Magazine\" OR \"China Foundry Association\") when:7d", "en-US", "US"),
        "COMPETIDORES_FUNDICION": ("Nemak OR \"Bocar Group\" OR Ahresty OR Ryobi OR \"GF Casting Solutions\" OR Handtmann OR \"CIE Automotive\" when:7d", "en-US", "US"),
        "TECNOLOGIA_FUNDICION": ("\"Buhler Group\" OR \"LK Machinery\" OR \"IDRA Group\" OR \"Italpresse Gauss\" OR YIZUMI die casting when:7d", "en-US", "US"),
        "ROBOTICA_IND40": ("\"ABB Robotics\" OR FANUC OR KUKA OR Yaskawa OR \"Universal Robots\" OR IFR robotics manufacturing when:5d", "en-US", "US"),
        "INDUSTRIA_40": ("Siemens OR \"Rockwell Automation\" OR \"Schneider Electric\" OR NVIDIA industrial AI factory automation when:4d", "en-US", "US"),
        "ENERGIA_IEA": ("\"International Energy Agency\" OR \"U.S. EIA\" oil gas energy market when:4d", "en-US", "US"),
        "FLETES_FREIGHTOS": ("Freightos ocean freight container shipping rates Red Sea when:5d", "en-US", "US"),
        "GEOPOLITICA_CRISIS": ("site:crisisgroup.org OR site:defensenews.com OR site:reuters.com/world sanctions war supply chain when:3d", "en-US", "US"),
        "SOSTENIBILIDAD": ("recycled aluminum low carbon automotive supply chain ESG when:5d", "en-US", "US"),
    }

    # Feeds RSS oficiales directos (gratuitos, sin paywall)
    direct_rss: dict[str, tuple[str, str]] = {
        "BBC_WORLD": ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
        "AL_JAZEERA": ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera"),
        "OILPRICE": ("https://oilprice.com/rss/main", "OilPrice"),
        "US_EIA": ("https://www.eia.gov/rss/todayinenergy.xml", "U.S. EIA"),
    }

    news_by_topic: dict[str, list[dict[str, str]]] = {}
    argentina_data: dict[str, Any] = {}
    brasil_data: dict[str, Any] = {}
    commodities_data: dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        fut_arg = pool.submit(fetch_argentina_indicators)
        fut_bra = pool.submit(fetch_brazil_indicators)
        fut_com = pool.submit(fetch_commodities)

        rss_futures = {}
        for key, (q, hl, gl) in gn_queries.items():
            rss_futures[pool.submit(fetch_google_news_rss, q, hl, gl, 4)] = key
        for key, (url, src) in direct_rss.items():
            rss_futures[pool.submit(fetch_rss_feed, url, src, 4)] = key

        argentina_data = fut_arg.result()
        brasil_data = fut_bra.result()
        commodities_data = fut_com.result()

        for fut in as_completed(rss_futures):
            topic = rss_futures[fut]
            news_by_topic[topic] = fut.result()

    return {
        "collected_at": now.isoformat(),
        "argentina": argentina_data,
        "brasil": brasil_data,
        "commodities": commodities_data,
        "news_candidates": news_by_topic,
    }
