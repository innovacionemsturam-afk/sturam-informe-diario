"""Orquestador único del Informe Estratégico Diario de STURAM S.A."""

import argparse
from datetime import datetime
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
DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {"sent_dates": [], "recent_titles": []}


def save_history(history: dict) -> None:
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_sample_report(edition_human: str, date_slash: str) -> dict:
    """Genera un informe de muestra mínimo para validar el diseño HTML y QA."""
    return {
        "edition_date": edition_human,
        "strategic_summary": [
            {
                "topic": "Argentina — Financiación y divisas (CIERRE DEL DÍA HÁBIL ANTERIOR)",
                "text": f"Al cierre del {date_slash}, tipo de cambio oficial y brecha MEP/CCL estables; monitorear tasas TAMAR para capital de trabajo.",
            },
            {
                "topic": "Aluminio LME",
                "text": "Cotización LME sin variaciones superiores al 2% (se mantiene estable); primas físicas y aleaciones secundarias sin traslado inmediato.",
            },
        ],
        "regions": [
            {
                "region": "ARGENTINA",
                "news": [
                    {
                        "title": "Cuadro diario de indicadores financieros y cambiarios",
                        "published_date": date_slash,
                        "data_date": date_slash,
                        "fact_description": "Resumen de referencia de dólar oficial, mayorista, MEP, CCL, riesgo país y última inflación publicada por INDEC.",
                        "source_name": "BCRA / DolarAPI",
                        "source_url": "https://dolarapi.com/v1/dolares",
                        "impact_label": "MIXTO",
                        "impact_detail": "El costo de importación de insumos y el CFT bancario dependen de la evolución cambiaria y tasas locales; requiere validar líneas vigentes con bancos de STURAM.",
                    }
                ],
            },
            {
                "region": "ALUMINIO",
                "news": [
                    {
                        "title": "LME Aluminio se mantiene estable en la última rueda",
                        "published_date": date_slash,
                        "data_date": date_slash,
                        "fact_description": "El aluminio primario en LME registró una variación diaria inferior al 2%, por lo que se mantiene estable dentro del rango reciente.",
                        "source_name": "Mercado LME",
                        "source_url": "https://finance.yahoo.com/quote/ALI=F",
                        "impact_label": "MIXTO",
                        "impact_detail": "Estabilidad en referencia internacional, aunque el costo real de compra de STURAM depende de primas físicas, flete y aleación secundaria pactada.",
                    }
                ],
            },
        ],
        "special_bulletins": [],
        "top_five_analysis": [
            {
                "fact_and_figure": f"Referencia cambiaria y tasas locales ({date_slash})",
                "risk_or_opportunity": "Mixto",
                "mechanism": "Impacto directo en capital de trabajo e importaciones.",
                "horizon": "Corto plazo",
                "what_to_watch": "Tasas de adelantos y brecha MEP/oficial.",
            }
            for _ in range(5)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Informe Estratégico Diario STURAM S.A.")
    parser.add_argument("--dry-run", action="store_true", help="Genera HTML local sin enviar correo.")
    parser.add_argument("--sample", action="store_true", help="Usa datos de muestra para probar plantilla HTML.")
    parser.add_argument("--test-to", type=str, help="Envía correo de prueba a una sola dirección.")
    parser.add_argument("--send", action="store_true", help="Envía el informe oficial a los 17 destinatarios.")
    args = parser.parse_args()

    now = datetime.now(TZ_CORDOBA)
    date_iso = now.strftime("%Y-%m-%d")
    date_slash = now.strftime("%d/%m/%Y")
    edition_human = f"{DAYS_ES[now.weekday()]} {now.day} de {MONTHS_ES[now.month - 1]} de {now.year}"
    subject = f"{SUBJECT_PREFIX} {date_slash}"

    history = load_history()

    if args.sample:
        report = build_sample_report(edition_human, date_slash)
    else:
        from generator import generate_report_json
        bundle = collect_daily_bundle()
        is_monday = now.weekday() == 0
        is_first_monday = is_monday and now.day <= 7
        report = generate_report_json(
            bundle=bundle,
            edition_date_human=edition_human,
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

    sent_dates = set() if (args.dry_run or args.test_to) else set(history.get("sent_dates", []))
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
            history.setdefault("sent_dates", []).append(date_iso)
            new_titles = [
                n.get("title", "")
                for r in report.get("regions", [])
                for n in r.get("news", [])
                if n.get("title")
            ]
            history["recent_titles"] = (history.get("recent_titles", []) + new_titles)[-200:]
            save_history(history)


if __name__ == "__main__":
    main()
