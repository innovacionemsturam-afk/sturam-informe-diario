"""Orquestador único del Informe Estratégico Diario de STURAM S.A."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

from config import EMAIL_CC, EMAIL_TO, PLAIN_TEXT_ALT, SUBJECT_PREFIX, TZ_CORDOBA
from fetch_data import collect_daily_bundle
from html_template import render_report_html
from mailer import send_html_email
from qa_check import run_qa_checks

BASE_DIR = Path(__file__).resolve().parent
HISTORY_PATH = BASE_DIR / "history.json"
OUTPUT_DIR = BASE_DIR / "output"
LOGO_PATH = BASE_DIR / "assets" / "logo_sturam.png"

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {"sent_dates": [], "recent_titles": [], "recent_urls": []}


def save_history(history: dict) -> None:
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def previous_business_day(dt: datetime) -> datetime:
    """Devuelve el día hábil anterior (viernes si hoy es lunes)."""
    if dt.weekday() == 0:
        return dt - timedelta(days=3)
    if dt.weekday() == 6:
        return dt - timedelta(days=2)
    return dt - timedelta(days=1)


def build_sample_report(edition_human: str, closing_slash: str) -> dict:
    """Genera un informe de muestra con la estructura aprobada del 18/11/2026."""
    return {
        "_is_sample": True,
        "edition_date": edition_human,
        "closing_date": closing_slash,
        "strategic_summary": [
            {
                "topic": "Financiación y divisas",
                "text": f"Datos correspondientes al CIERRE DEL DÍA HÁBIL ANTERIOR, {closing_slash}: BNA compra/venta y referencia mayorista A3500 del BCB SML; tasas TAMAR y adelantos distintas del CFT de STURAM.",
            },
            {
                "topic": "Insumos y aluminio",
                "text": "Cotización oficial LME cash y tres meses según Westmetall, diferenciando backwardation entre contratos respecto de primas físicas y aleaciones secundarias.",
            },
        ],
        "stories": [
            {
                "region": "ARGENTINA",
                "meta_subtitle": f"Cierre {closing_slash} · BCRA / BNA / BCB SML",
                "title": "Divisas, riesgo país e indicadores financieros del último cierre",
                "bullets": [
                    "Banco Nación billetes compra/venta, mayorista A3500 publicado en SML del BCB, MEP y CCL.",
                    "Tasas BCRA: TAMAR bancos privados y adelantos en cuenta corriente; IPC INDEC de referencia.",
                ],
                "impact_label": "MIXTO",
                "impact_detail": "El costo de divisas o crédito incide sobre capital de trabajo; el CFT de STURAM surge únicamente de ofertas bancarias efectivas.",
                "sources": [
                    {"name": "BCRA", "url": "https://www.bcra.gob.ar/PublicacionesEstadisticas/Principales_variables.asp"},
                    {"name": "BCB – tasa peso/dólar SML", "url": "https://www.bcb.gov.br/rex/sml/ingl/rate.asp?frame=1"},
                ],
            },
            {
                "region": "ALUMINIO",
                "meta_subtitle": f"Cotización LME oficial {closing_slash}",
                "title": "LME: evolución de contrato cash, tres meses e inventarios oficiales",
                "bullets": [
                    "Precios oficiales vendedor LME para contrato cash y tres meses, junto con stock en almacenes registrados.",
                    "El diferencial cash menos tres meses refleja tensión o contango entre contratos, no la prima física puesta en planta.",
                ],
                "kpi_table": {
                    "note": "LME oficial: precios vendedor (USD/t) y diferencial entre contratos, no primas físicas.",
                    "headers": ["Cierre", "Cash vendedor USD/t", "3 meses vendedor USD/t", "Cash − 3m"],
                    "rows": [
                        ["20/11", "3.184,50", "2.831,50", "353,00"],
                        ["23/11", "3.201,50", "2.834,00", "367,50"],
                        ["Variación diaria", "+0,53%", "+0,09%", "+14,50 USD/t"],
                    ],
                },
                "impact_label": "MIXTO",
                "impact_detail": "Contrastar fórmula de compra de aleaciones, prima física, contenido de scrap y cobertura antes de estimar impacto en costos.",
                "sources": [
                    {"name": "Westmetall histórico", "url": "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Al_cash"}
                ],
            },
        ],
        "top_five_analysis": [
            {
                "fact_and_figure": f"Indicador prioritario #{i} ({closing_slash})",
                "management_reading": "Lectura gerencial sujeta a contratos, plazos y estructura de costos internos de STURAM.",
            }
            for i in range(1, 6)
        ],
        "validation_notes": [
            f"Edición de prueba ({edition_human}) con cierre del {closing_slash}.",
            "Se cotejaron titulares previos en history.json para excluir duplicaciones.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe Estratégico Diario STURAM S.A.")
    parser.add_argument("--dry-run", action="store_true", help="Genera HTML local sin enviar correo.")
    parser.add_argument("--sample", action="store_true", help="Usa datos de muestra para probar plantilla HTML.")
    parser.add_argument("--test-to", type=str, help="Envía correo de prueba a una sola dirección.")
    parser.add_argument("--send", action="store_true", help="Envía el informe oficial a los 17 destinatarios.")
    parser.add_argument("--force", action="store_true", help="Permite reenviar la edición del día actual.")
    args = parser.parse_args()

    now = datetime.now(TZ_CORDOBA)
    prev_bday = previous_business_day(now)
    date_iso = now.strftime("%Y-%m-%d")
    date_slash = now.strftime("%d/%m/%Y")
    closing_slash = prev_bday.strftime("%d/%m/%Y")
    edition_human = f"{now.day} de {MONTHS_ES[now.month - 1]} de {now.year}"
    subject = f"{SUBJECT_PREFIX} {date_slash}"

    history = load_history()

    if args.send and not args.dry_run and not args.test_to and not args.force:
        if date_iso in set(history.get("sent_dates", [])):
            print(f"La edición {date_iso} ya fue enviada hoy. Se omite para evitar duplicados.")
            return

    if args.sample:
        report = build_sample_report(edition_human, closing_slash)
    else:
        from generator import generate_report_json

        bundle = collect_daily_bundle(
            recent_titles=history.get("recent_titles", []),
            recent_urls=history.get("recent_urls", []),
        )
        is_monday = now.weekday() == 0
        is_first_monday = is_monday and now.day <= 7
        report = generate_report_json(
            bundle=bundle,
            edition_date_human=edition_human,
            closing_date_slash=closing_slash,
            recent_titles=history.get("recent_titles", []),
            is_monday=is_monday,
            is_first_monday=is_first_monday,
        )

    has_logo = LOGO_PATH.exists()
    html_body = render_report_html(report, has_logo=has_logo)

    if args.test_to:
        to_list = [args.test_to]
        cc_list: list[str] = []
    else:
        to_list = EMAIL_TO
        cc_list = EMAIL_CC

    sent_dates = (
        set()
        if (args.dry_run or args.test_to or args.force)
        else set(history.get("sent_dates", []))
    )
    ok, errors = run_qa_checks(
        report=report,
        html_body=html_body,
        subject=subject,
        recipients_to=to_list,
        recipients_cc=cc_list,
        sent_dates=sent_dates,
        edition_date_iso=date_iso,
    )

    if not ok:
        print("BLOQUEO QA:")
        for err in errors:
            print(f" - {err}")
        raise SystemExit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"informe_{date_iso}.html"
    out_file.write_text(html_body, encoding="utf-8")
    print(f"HTML generado correctamente en: {out_file}")

    if args.dry_run:
        print("Modo --dry-run: no se envió correo.")
        return

    if args.test_to or args.send:
        msg_id = send_html_email(
            subject=subject,
            plain_text=PLAIN_TEXT_ALT,
            html_body=html_body,
            to_addrs=to_list,
            cc_addrs=cc_list,
            logo_path=LOGO_PATH if has_logo else None,
        )
        print(f"Correo enviado exitosamente. Message-ID: {msg_id}")

        if args.send:
            if date_iso not in history.setdefault("sent_dates", []):
                history["sent_dates"].append(date_iso)
            stories = report.get("stories") or [
                n for r in report.get("regions", []) for n in r.get("news", [])
            ]
            new_titles = [s.get("title", "") for s in stories if s.get("title")]
            new_urls = [
                src.get("url", "")
                for s in stories
                for src in (s.get("sources") or [])
                if src.get("url")
            ]
            history["recent_titles"] = (history.get("recent_titles", []) + new_titles)[-250:]
            history["recent_urls"] = (history.get("recent_urls", []) + new_urls)[-400:]
            save_history(history)


if __name__ == "__main__":
    main()
