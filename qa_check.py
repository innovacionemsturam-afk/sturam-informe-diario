"""Control de calidad automático antes del envío (Sección 14)."""

from typing import Any
from config import EMAIL_TO, EMAIL_CC, MAX_NEWS_PER_EDITION, SUBJECT_PREFIX


def run_qa_checks(
    report: dict[str, Any],
    html_body: str,
    subject: str,
    recipients_to: list[str],
    recipients_cc: list[str],
    sent_dates: set[str],
    edition_date_iso: str,
) -> tuple[bool, list[str]]:
    """Ejecuta validaciones bloqueantes. Devuelve (ok, lista_de_errores)."""
    errors: list[str] = []

    if edition_date_iso in sent_dates:
        errors.append(f"La edición {edition_date_iso} ya figura como enviada.")

    if not subject.startswith(SUBJECT_PREFIX):
        errors.append(f"Asunto inválido: {subject}")

    total_recipients = len(recipients_to) + len(recipients_cc)
    if recipients_to != EMAIL_TO or recipients_cc != EMAIL_CC:
        # Solo permitir desvío si es una prueba explícita (--test-to)
        if total_recipients != 1:
            errors.append(
                f"Destinatarios no coinciden con los 17 autorizados (hay {total_recipients})."
            )

    if not report.get("strategic_summary"):
        errors.append("Falta el RESUMEN ESTRATÉGICO inicial.")

    regions = report.get("regions", [])
    total_news = sum(len(r.get("news", [])) for r in regions)
    if total_news == 0:
        errors.append("El informe no contiene noticias desarrolladas.")
    if total_news > MAX_NEWS_PER_EDITION:
        errors.append(
            f"Excede el máximo de {MAX_NEWS_PER_EDITION} noticias ({total_news})."
        )

    for r in regions:
        for n in r.get("news", []):
            if not n.get("title") or not n.get("fact_description") or not n.get("impact_detail"):
                errors.append(f"Noticia incompleta en {r.get('region')}: {n.get('title')}")
            if not n.get("source_url"):
                errors.append(f"Noticia sin URL de fuente: {n.get('title')}")

    top5 = report.get("top_five_analysis", [])
    if len(top5) != 5:
        errors.append(f"El análisis gerencial final debe tener 5 puntos (tiene {len(top5)}).")

    if not html_body or "<html" not in html_body or "</html>" not in html_body:
        errors.append("El cuerpo HTML está incompleto o mal formado.")

    return (len(errors) == 0, errors)
