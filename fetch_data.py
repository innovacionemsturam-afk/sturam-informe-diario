"""Recolección de indicadores oficiales (BCRA, BCB SML, Westmetall LME, Yahoo)
y noticias sectoriales (AutoData, Automotive Business, EUROGUSS, RSS), con
filtrado anti-duplicación duro en código antes de invocar al modelo.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET

from config import TZ_CORDOBA

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
SSL_CTX = ssl._create_unverified_context()

STOPWORDS = {
    "para", "como", "este", "esta", "estos", "estas", "pero", "tras", "ante",
    "sobre", "entre", "desde", "hasta", "donde", "cuando", "porque", "segun",
    "with", "from", "that", "this", "will", "after", "over", "into", "amid",
    "more", "than", "new", "nueva", "nuevo", "nuevos", "nuevas", "argentina",
    "brasil", "china", "europa", "global", "2026", "2027",
}


def _get_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _get_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-záéíóúñü0-9]{4,}", (text or "").lower())
    return {w for w in words if w not in STOPWORDS}


def is_duplicate_title(candidate_title: str, recent_titles: list[str]) -> bool:
    """Devuelve True si el titular candidato repite un hecho ya publicado."""
    cand_tokens = _tokenize(candidate_title)
    if not cand_tokens:
        return False
    for old in recent_titles:
        old_tokens = _tokenize(old)
        if not old_tokens:
            continue
        inter = cand_tokens & old_tokens
        overlap = len(inter) / min(len(cand_tokens), len(old_tokens))
        if overlap >= 0.42 or len(inter) >= 4:
            return True
    return False


def fetch_westmetall_lme() -> dict[str, Any]:
    """Obtiene LME Aluminium Cash, 3-month y Stock oficial desde Westmetall."""
    url = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Al_cash"
    out: dict[str, Any] = {"source_url": url, "sessions": []}
    try:
        html = _get_text(url)
        rows = re.findall(r"<tr[^>]*>.*?</tr>", html, re.S)
        for r in rows:
            cells = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
            ]
            if len(cells) >= 4 and re.search(r"\d{4}", cells[0]):
                try:
                    cash = float(cells[1].replace(",", ""))
                    three_m = float(cells[2].replace(",", ""))
                    stock = int(cells[3].replace(",", ""))
                    out["sessions"].append(
                        {
                            "date": cells[0],
                            "cash_usd_t": cash,
                            "three_month_usd_t": three_m,
                            "cash_minus_3m_usd_t": round(cash - three_m, 2),
                            "stock_tonnes": stock,
                        }
                    )
                except ValueError:
                    continue
            if len(out["sessions"]) >= 5:
                break
        if len(out["sessions"]) >= 2:
            latest = out["sessions"][0]
            prev = out["sessions"][1]
            out["latest"] = latest
            out["previous"] = prev
            out["cash_daily_pct"] = round(
                (latest["cash_usd_t"] - prev["cash_usd_t"]) / prev["cash_usd_t"] * 100.0, 2
            )
            out["three_month_daily_pct"] = round(
                (latest["three_month_usd_t"] - prev["three_month_usd_t"])
                / prev["three_month_usd_t"]
                * 100.0,
                2,
            )
            out["spread_change_usd_t"] = round(
                latest["cash_minus_3m_usd_t"] - prev["cash_minus_3m_usd_t"], 2
            )
    except Exception as exc:
        out["warning"] = str(exc)
    return out


def fetch_bcb_sml_rates() -> dict[str, Any]:
    """Obtiene referencia A3500 (Peso/Dólar) y PTAX (Real/Dólar) de la tabla SML del BCB."""
    url = "https://www.bcb.gov.br/rex/sml/ingl/rate.asp?frame=1"
    out: dict[str, Any] = {"source_url": url, "rows": []}
    try:
        html = _get_text(url)
        rows = re.findall(r"<tr[^>]*>.*?</tr>", html, re.S)
        for r in rows:
            cells = [
                re.sub(r"&nbsp;|\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
            ]
            if len(cells) >= 4 and re.match(r"\d{2}/\d{2}/\d{4}", cells[0]):
                out["rows"].append(
                    {
                        "date": cells[0],
                        "a3500_ars_per_usd": cells[1],
                        "sml_ars_per_brl": cells[2],
                        "ptax_brl_per_usd": cells[3],
                    }
                )
            if len(out["rows"]) >= 5:
                break
    except Exception as exc:
        out["warning"] = str(exc)
    return out


def fetch_bcra_principales_variables() -> dict[str, Any]:
    """Extrae TAMAR, Adelantos, BADLAR y Tipo de Cambio de la web oficial del BCRA."""
    url = "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp"
    out: dict[str, Any] = {"source_url": url, "variables": []}
    try:
        html = _get_text(url, timeout=12)
        rows = re.findall(r"<tr[^>]*>.*?</tr>", html, re.S)
        for r in rows:
            cells = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
            ]
            if len(cells) >= 3 and any(
                k in cells[0].lower()
                for k in ("tamar", "adelantos", "badlar", "mayorista", "minorista", "reservas", "política")
            ):
                out["variables"].append(
                    {"name": cells[0], "date": cells[1], "value": cells[2]}
                )
    except Exception as exc:
        out["warning"] = str(exc)
    return out


def fetch_argentina_indicators() -> dict[str, Any]:
    """Obtiene cotizaciones de dólar, A3500, tasas BCRA, riesgo país e inflación."""
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
        result["riesgo_pais"] = _get_json(
            "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"
        )
    except Exception as exc:
        result["warnings"].append(f"riesgo_pais: {exc}")

    try:
        inf_m = _get_json("https://api.argentinadatos.com/v1/finanzas/indices/inflacion")
        inf_ia = _get_json(
            "https://api.argentinadatos.com/v1/finanzas/indices/inflacionInteranual"
        )
        result["inflacion_mensual_ultima"] = inf_m[-1] if inf_m else None
        result["inflacion_interanual_ultima"] = inf_ia[-1] if inf_ia else None
    except Exception as exc:
        result["warnings"].append(f"inflacion: {exc}")

    result["bcb_sml_a3500_ptax"] = fetch_bcb_sml_rates()
    result["bcra_principales_variables"] = fetch_bcra_principales_variables()
    return result


def fetch_brazil_indicators() -> dict[str, Any]:
    """Obtiene PTAX USD/BRL y tasa Selic desde el Banco Central do Brasil."""
    result: dict[str, Any] = {"warnings": []}
    try:
        for name, serie in [("ptax_venta", 1), ("ptax_compra", 10813), ("selic_meta", 432)]:
            url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/3?formato=json"
            result[name] = _get_json(url)
    except Exception as exc:
        result["warnings"].append(f"bcb_brasil: {exc}")
    return result


def fetch_commodities() -> dict[str, Any]:
    """Obtiene LME oficial desde Westmetall + futuros Brent (BZ=F), WTI (CL=F) y Gas TTF (TTF=F)."""
    result: dict[str, Any] = {"warnings": [], "lme_westmetall": fetch_westmetall_lme()}
    symbols = {"aluminio_futuro": "ALI=F", "brent": "BZ=F", "wti": "CL=F", "gas_ttf_europa": "TTF=F"}
    for key, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
            data = _get_json(url)
            meta = data["chart"]["result"][0]["meta"]
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            valid_closes = [c for c in closes if c is not None]
            last_close = valid_closes[-1] if valid_closes else meta.get("regularMarketPrice")
            prev_close = (
                valid_closes[-2] if len(valid_closes) >= 2 else meta.get("chartPreviousClose")
            )
            pct = (
                ((last_close - prev_close) / prev_close * 100.0)
                if (last_close and prev_close)
                else None
            )
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


def fetch_autodata_direct(max_items: int = 8) -> list[dict[str, str]]:
    """Extrae las últimas noticias directamente de AutoData Brasil."""
    url = "https://www.autodata.com.br/"
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        html = _get_text(url, timeout=12)
        for m in re.finditer(
            r'href="(https://www\.autodata\.com\.br/noticias/\d{4}/\d{2}/\d{2}/[^"]+)"[^>]*>(.*?)</a>',
            html,
            re.S,
        ):
            link = m.group(1).strip()
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            if len(title) > 25 and link not in seen:
                seen.add(link)
                date_m = re.search(r"/noticias/(\d{4})/(\d{2})/(\d{2})/", link)
                pub_d = (
                    f"{date_m.group(3)}/{date_m.group(2)}/{date_m.group(1)}"
                    if date_m
                    else ""
                )
                items.append(
                    {"title": title, "link": link, "pubDate": pub_d, "source": "AutoData"}
                )
            if len(items) >= max_items:
                break
    except Exception:
        pass
    return items


def fetch_rss_feed(
    url: str,
    default_source: str,
    max_items: int = 5,
    max_age_hours: int = 48,
) -> list[dict[str, str]]:
    """Lee un feed RSS filtrando artículos viejos."""
    items: list[dict[str, str]] = []
    now_utc = datetime.now(TZ_CORDOBA)
    try:
        xml_text = _get_text(url)
        root = ET.fromstring(xml_text)
        for item in root.findall("./channel/item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            desc = re.sub(r"<[^>]+>", " ", item.findtext("description", "")).strip()
            desc = re.sub(r"\s+", " ", desc)[:280]
            source_el = item.find("source")
            source = (
                source_el.text.strip()
                if source_el is not None and source_el.text
                else default_source
            )
            if pub_date:
                try:
                    dt = parsedate_to_datetime(pub_date)
                    age_h = (now_utc - dt.astimezone(TZ_CORDOBA)).total_seconds() / 3600.0
                    if age_h > max_age_hours:
                        continue
                except Exception:
                    pass
            if title and link:
                items.append(
                    {
                        "title": title,
                        "snippet": desc,
                        "link": link,
                        "pubDate": pub_date,
                        "source": source,
                    }
                )
            if len(items) >= max_items:
                break
    except Exception:
        pass
    return items


def fetch_google_news_rss(
    query: str,
    hl: str = "es-419",
    gl: str = "AR",
    max_items: int = 5,
    max_age_hours: int = 48,
) -> list[dict[str, str]]:
    """Consulta titulares recientes en Google News RSS con filtro de antigüedad."""
    ceid = f"{gl}:{'es-419' if hl.startswith('es') else 'en'}"
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    return fetch_rss_feed(
        url, default_source="Google News", max_items=max_items, max_age_hours=max_age_hours
    )


def collect_daily_bundle(
    recent_titles: list[str] | None = None,
    recent_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Reúne indicadores oficiales y noticias frescas deduplicadas contra history.json."""
    now = datetime.now(TZ_CORDOBA)
    is_monday = now.weekday() == 0
    max_age_h = 80 if is_monday else 42
    when_tag = "when:3d" if is_monday else "when:2d"

    prev_titles = recent_titles or []
    prev_urls = set(recent_urls or [])

    gn_queries: dict[str, tuple[str, str, str]] = {
        "ARGENTINA_FINANZAS": (
            f'(BCRA OR "dolar oficial" OR tasas OR TAMAR OR "riesgo pais" OR Merval OR UIA) economia Argentina {when_tag}',
            "es-419",
            "AR",
        ),
        "ARGENTINA_AUTOMOTRIZ": (
            f"(ADEFA OR AFAC OR ADIMRA) produccion exportacion metalurgia automotriz Argentina {when_tag}",
            "es-419",
            "AR",
        ),
        "CORDOBA": (
            f'(Cordoba OR "Las Varillas" OR "San Francisco") (UOM OR SMATA OR metalurgica OR automotriz OR Pauny OR Iveco OR Renault OR Stellantis OR Volkswagen) {when_tag}',
            "es-419",
            "AR",
        ),
        "GREMIOS": (
            f"(UOM OR SMATA) (paritaria OR conflicto OR paro OR conciliacion OR automotriz OR metalurgica) Argentina {when_tag}",
            "es-419",
            "AR",
        ),
        "BRASIL": (
            f'(ANFAVEA OR ABIFA OR Sindipeças OR AutoData OR "Automotive Business" OR Volkswagen OR Toyota OR Stellantis OR BYD OR GAC) Brasil {when_tag}',
            "pt-BR",
            "BR",
        ),
        "MEXICO_LATAM": (
            f'("Cluster Industrial" OR "El Economista") Mexico automotriz autopartes planta {when_tag}',
            "es-419",
            "MX",
        ),
        "EEUU_AUTOMOTRIZ": (
            f'(Tesla OR "General Motors" OR Ford OR Rivian OR Stellantis) manufacturing plant supplier tariffs {when_tag}',
            "en-US",
            "US",
        ),
        "EUROPA_AUTOMOTRIZ": (
            f'("Volkswagen" OR BMW OR "Mercedes-Benz" OR Stellantis OR Renault OR Volvo OR JLR OR EUROGUSS) Europe plant production aluminum {when_tag}',
            "en-US",
            "US",
        ),
        "CHINA_AUTOMOTRIZ": (
            f'(BYD OR Geely OR Chery OR SAIC OR GAC OR Gasgoo OR Caixin) automaker supplier production export {when_tag}',
            "en-US",
            "US",
        ),
        "INDIA_ASIA_AUTOMOTRIZ": (
            f'("Tata Motors" OR Mahindra OR "Maruti Suzuki" OR "ACMA India" OR "Autocar Professional" OR Toyota OR Honda OR Hyundai) manufacturing {when_tag}',
            "en-US",
            "US",
        ),
        "ALUMINIO_LME": (
            f'(LME OR SHFE OR "London Metal Exchange") (aluminum OR aluminium) price inventory premium {when_tag}',
            "en-US",
            "US",
        ),
        "ASOCIACIONES_Y_COMPETIDORES_FUNDICION": (
            f'(Nemak OR "Bocar" OR Ahresty OR Ryobi OR "GF Casting" OR Handtmann OR "CIE Automotive" OR "Foundry-Planet" OR EUROGUSS OR NADCA OR "Buhler" OR IDRA) die casting HPDC aluminum when:4d',
            "en-US",
            "US",
        ),
        "IA_Y_ROBOTICA_INDUSTRIAL": (
            f'("ABB Robotics" OR FANUC OR KUKA OR Yaskawa OR "Universal Robots" OR Siemens OR "Rockwell Automation" OR NVIDIA OR CNC OR "predictive maintenance" OR "industrial AI") manufacturing {when_tag}',
            "en-US",
            "US",
        ),
        "ENERGIA_PETROLEO_Y_GAS": (
            f'(Brent OR WTI OR OPEC OR "TTF gas" OR "Horumuz" OR "U.S. EIA" OR IEA) oil gas industrial energy {when_tag}',
            "en-US",
            "US",
        ),
        "LOGISTICA_Y_GEOPOLITICA": (
            f'(Freightos OR "Red Sea" OR "Black Sea" OR sanctions OR tariffs OR pig iron OR steel OR aluminum) shipping trade {when_tag}',
            "en-US",
            "US",
        ),
        "SOSTENIBILIDAD_INDUSTRIAL": (
            f'("recycled aluminum" OR "low carbon aluminum" OR CBAM OR COP31 OR electrification) industrial manufacturing {when_tag}',
            "en-US",
            "US",
        ),
    }

    direct_rss: dict[str, tuple[str, str]] = {
        "OILPRICE": ("https://oilprice.com/rss/main", "OilPrice"),
        "US_EIA": ("https://www.eia.gov/rss/todayinenergy.xml", "U.S. EIA"),
    }

    news_by_topic: dict[str, list[dict[str, str]]] = {}

    with ThreadPoolExecutor(max_workers=10) as pool:
        fut_arg = pool.submit(fetch_argentina_indicators)
        fut_bra = pool.submit(fetch_brazil_indicators)
        fut_com = pool.submit(fetch_commodities)
        fut_autodata = pool.submit(fetch_autodata_direct, 8)

        rss_futures = {}
        for key, (q, hl, gl) in gn_queries.items():
            rss_futures[pool.submit(fetch_google_news_rss, q, hl, gl, 6, max_age_h)] = key
        for key, (url, src) in direct_rss.items():
            rss_futures[pool.submit(fetch_rss_feed, url, src, 5, max_age_h)] = key

        argentina_data = fut_arg.result()
        brasil_data = fut_bra.result()
        commodities_data = fut_com.result()
        autodata_items = fut_autodata.result()

        for fut in as_completed(rss_futures):
            topic = rss_futures[fut]
            raw_items = fut.result()
            filtered: list[dict[str, str]] = []
            for it in raw_items:
                if it.get("link") in prev_urls:
                    continue
                if is_duplicate_title(it.get("title", ""), prev_titles):
                    continue
                filtered.append(it)
            news_by_topic[topic] = filtered

    # Sumar AutoData directo deduplicado
    news_by_topic["BRASIL_AUTODATA_DIRECTO"] = [
        it
        for it in autodata_items
        if it.get("link") not in prev_urls
        and not is_duplicate_title(it.get("title", ""), prev_titles)
    ]

    return {
        "collected_at": now.isoformat(),
        "argentina": argentina_data,
        "brasil": brasil_data,
        "commodities": commodities_data,
        "news_candidates": news_by_topic,
    }
