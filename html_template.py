"""Plantilla HTML idéntica a la edición aprobada por STURAM S.A. (18/11/2026).

Incluye las hojas de estilo originales para visualización e impresión A4 vertical,
listas de bullets por noticia, tablas KPI, cuadro de prioridades gerenciales y
sección de Notas de Validación, con estilos inline de respaldo para Gmail.
"""

from html import escape
from typing import Any


def render_report_html(report: dict[str, Any], has_logo: bool = False) -> str:
    """Renderiza el informe estratégico diario con el diseño aprobado de STURAM S.A."""
    edition_date = escape(report.get("edition_date", ""))
    closing_date = escape(report.get("closing_date", ""))
    summary_items = report.get("strategic_summary", [])
    stories = report.get("stories", [])
    top_five = report.get("top_five_analysis", [])
    validation_notes = report.get("validation_notes", [])

    # Si no viene la lista plana stories pero viene regions, aplanarla respetando el orden
    if not stories and report.get("regions"):
        for reg_block in report.get("regions", []):
            reg_name = reg_block.get("region", "")
            for n in reg_block.get("news", []):
                n_copy = dict(n)
                n_copy.setdefault("region", reg_name)
                stories.append(n_copy)

    summary_html = ""
    for item in summary_items:
        topic = escape(item.get("topic", ""))
        # Permitir etiquetas seguras básicas o escapar y resaltar frases clave
        raw_text = escape(item.get("text", ""))
        raw_text = raw_text.replace(
            "CIERRE DEL DÍA HÁBIL ANTERIOR",
            "<strong>CIERRE DEL DÍA HÁBIL ANTERIOR</strong>",
        )
        summary_html += (
            f'<p class="summary-item" style="font-size:14px;line-height:1.46;margin:8px 0;padding-left:4px;">'
            f"<b>{topic}: </b>{raw_text}</p>"
        )

    stories_html = ""
    for idx, story in enumerate(stories, start=1):
        num_str = f"{idx:02d}"
        page_start_cls = " print-page-start" if (idx - 1) % 4 == 0 else ""
        region = escape(story.get("region", "GLOBAL"))
        meta_sub = escape(
            story.get("meta_subtitle")
            or f"{story.get('published_date', closing_date)} · {story.get('source_name', '')}"
        )
        title = escape(story.get("title", ""))

        bullets = story.get("bullets") or []
        if not bullets and story.get("fact_description"):
            bullets = [story["fact_description"]]
        bullets_li = "".join(
            f'<li style="margin:0 0 5px 0;">{escape(str(b))}</li>' for b in bullets
        )

        kpi_html = ""
        kpi = story.get("kpi_table")
        if isinstance(kpi, dict) and kpi.get("headers") and kpi.get("rows"):
            note = escape(kpi.get("note", ""))
            if note:
                kpi_html += f'<p class="source-note" style="font-size:12px;color:#647686;margin-top:9px;">{note}</p>'
            ths = "".join(
                f'<th style="padding:7px 9px;border:1px solid #d6e2ea;text-align:left;vertical-align:top;background:#153752;color:white;">{escape(str(h))}</th>'
                for h in kpi["headers"]
            )
            trs = ""
            for row in kpi["rows"]:
                tds = "".join(
                    f'<td style="padding:7px 9px;border:1px solid #d6e2ea;text-align:left;vertical-align:top;">{escape(str(cell))}</td>'
                    for cell in row
                )
                trs += f"<tr>{tds}</tr>"
            kpi_html += (
                f'<table class="kpi" style="width:100%;border-collapse:collapse;margin:9px 0 12px;font-size:12px;">'
                f"<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"
            )

        impact_label = escape(story.get("impact_label", "MIXTO"))
        impact_detail = escape(story.get("impact_detail", ""))

        sources = story.get("sources") or []
        if not sources and story.get("source_url"):
            sources = [
                {
                    "name": story.get("source_name", "Fuente original"),
                    "url": story.get("source_url", "#"),
                }
            ]
        source_links = " · ".join(
            f'<a href="{escape(str(s.get("url", "#")))}" rel="noopener noreferrer" target="_blank" style="color:#126192;text-decoration:underline;">{escape(str(s.get("name", "Fuente")))}</a>'
            for s in sources
            if s.get("url")
        )

        stories_html += (
            f'<section class="story{page_start_cls}" id="n{num_str}" '
            f'style="background:white;border:1px solid #dee4ec;border-radius:12px;padding:22px;margin-bottom:17px;break-inside:avoid;">'
            f'<p class="meta" style="color:#587085;font-size:13px;margin:0 0 6px 0;">'
            f'<span class="country-strong" style="color:#0648C8;font-size:26px;font-weight:800;line-height:1.25;display:inline-block;">{region}</span>'
            f" · {num_str} · {meta_sub}</p>"
            f'<h2 style="font-size:20px;color:#123a58;margin:8px 0;">{title}</h2>'
            f'<ul class="news-bullets" style="padding-left:24px;margin:10px 0 14px;line-height:1.52;">{bullets_li}</ul>'
            f"{kpi_html}"
            f'<div class="impact" style="background:#edf4f9;border-left:4px solid #297c9d;padding:12px;margin-top:12px;">'
            f"<b>IMPACTO STURAM — {impact_label}: </b>{impact_detail}</div>"
            f'<p class="source-note" style="font-size:12px;color:#647686;margin-top:9px;">Fuentes: {source_links}</p>'
            f"</section>"
        )

    top5_rows = ""
    for i, item in enumerate(top_five, start=1):
        fact = escape(item.get("fact_and_figure", ""))
        reading = escape(
            item.get("management_reading")
            or f"{item.get('mechanism', '')} ({item.get('risk_or_opportunity', '')} - {item.get('horizon', '')}). A observar: {item.get('what_to_watch', '')}"
        )
        top5_rows += (
            f"<tr>"
            f'<td style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;">{i}</td>'
            f'<td style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;">{fact}</td>'
            f'<td style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;">{reading}</td>'
            f"</tr>"
        )

    notes_html = ""
    if validation_notes:
        notes_p = "".join(
            f'<p class="source-note" style="font-size:12px;color:#647686;margin-top:9px;">{escape(str(note))}</p>'
            for note in validation_notes
        )
        notes_html = (
            f'<section class="grouped-intel" style="background:#fff;border:1px solid #d5e0ea;border-radius:12px;padding:21px;margin:20px 0;line-height:1.5;color:#203544;">'
            f'<h2 style="color:#113b5b;margin-top:0;">NOTAS DE VALIDACIÓN — FUENTES, DUPLICACIONES Y ALCANCE</h2>'
            f"{notes_p}</section>"
        )

    logo_html = (
        '<img alt="Logo original STURAM S.A." src="cid:sturam_logo" '
        'style="max-width:175px;max-height:90px;object-fit:contain;background:white;padding:10px;border-radius:8px;display:block;margin-bottom:8px;"/>'
        if has_logo
        else ""
    )

    subtitle_line = (
        f"{edition_date} · Edición de cierre {closing_date}"
        if closing_date
        else edition_date
    )

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/><meta content="width=device-width,initial-scale=1" name="viewport"/><title>STURAM S.A. | Informe Estratégico Diario | {edition_date}</title><style>
body{{font:15px Arial,sans-serif;background:#f1f4f7;color:#1a2633;margin:0}}
header{{background:#102e48;color:white;padding:25px 5%;position:relative}}
header img{{max-width:175px;max-height:90px;object-fit:contain;background:white;padding:10px;border-radius:8px}}
header h1{{font-size:64px;line-height:1.08;text-transform:uppercase;font-weight:700;margin:7px 0}}
.brand-company{{font-weight:bold;letter-spacing:.03em}}
main{{max-width:1000px;margin:auto;padding:24px 18px}}
.lead,.story{{background:white;border:1px solid #dee4ec;border-radius:12px;padding:22px;margin-bottom:17px}}.story{{break-inside:avoid}}
.meta{{color:#587085;font-size:13px}}.story .meta .country-strong{{color:#0648C8;font-size:26px;font-weight:800;line-height:1.25;display:inline-block}}
.story h2{{font-size:20px;color:#123a58;margin:8px 0}}.tag{{font-weight:700;color:#a74923}}
.f{{margin:8px 0;line-height:1.6}}.impact{{background:#edf4f9;border-left:4px solid #297c9d;padding:12px;margin-top:12px}}
.news-bullets{{padding-left:24px;margin:10px 0 14px;line-height:1.52}}.news-bullets li{{margin:0 0 5px 0}}
.strategic-summary{{background:#f4f8fc;border:1px solid #d5e1ed;border-left:5px solid #14548b;padding:18px 22px;margin:18px 0 28px}}
.strategic-summary h2{{margin-top:0;color:#124875}}.strategic-summary p{{padding-left:4px;margin:8px 0}}
.management{{background:#fff;border:1px solid #cedbe8;border-radius:12px;padding:24px;margin:25px 0}}
.management h2{{color:#113b5b}}.management h3{{color:#205277}}
.priority-table,.data-table{{border-collapse:collapse;width:100%;font-size:13px;margin:14px 0}}
.priority-table td,.priority-table th,.data-table td,.data-table th{{padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left}}
.priority-table th,.data-table th{{background:#153752;color:white}}
a{{color:#126192;text-decoration:underline}}.source-note{{font-size:12px;color:#647686;margin-top:9px}}
.grouped-intel{{background:#fff;border:1px solid #d5e0ea;border-radius:12px;padding:21px;margin:20px 0;line-height:1.5;color:#203544}}
@media(max-width:650px){{header h1{{font-size:clamp(34px,9vw,64px)}}.story .meta .country-strong{{font-size:24px}}}}
@page{{size:A4 portrait;margin:11mm 12mm}}
@media print{{html,body{{background:white!important;color:#1a2633!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}body{{font-size:9pt!important;line-height:1.18!important}}
header{{padding:12px 15px!important;break-before:auto!important}}header h1{{font-size:28pt!important;line-height:1.03!important}}header img{{max-width:112px!important;max-height:52px!important;padding:5px!important}}
main{{max-width:none!important;padding:0!important}}
main>.strategic-summary{{page-break-after:always!important;break-after:page!important;font-size:9pt!important;line-height:1.2!important;padding:8px 11px!important;margin:4px 0 0!important}}
.strategic-summary h2{{font-size:14pt!important;margin:0 0 5px!important}}.strategic-summary p{{margin:4px 0!important}}
main>.story{{font-size:8.4pt!important;line-height:1.14!important;padding:7px 9px!important;margin:0 0 6px!important;break-inside:avoid!important;page-break-inside:avoid!important}}
main>.story.print-page-start{{break-before:page!important;page-break-before:always!important}}
.story h2{{font-size:11.4pt!important;margin:3px 0 4px!important}}.story .meta .country-strong{{font-size:13pt!important}}
.story .news-bullets{{padding-left:16px!important;margin:3px 0!important;line-height:1.15!important}}.story .news-bullets li{{margin-bottom:2px!important}}
.story .impact{{padding:5px 8px!important;margin-top:4px!important;line-height:1.15!important}}
.story .source-note{{font-size:7pt!important;margin:3px 0!important}}
.management{{break-before:page!important;page-break-before:always!important;padding:12px!important;margin:0!important}}
.priority-table{{font-size:8.6pt!important}}.priority-table td,.priority-table th{{padding:6px!important}}
main > .strategic-summary:first-child {{ font-size:7.75pt !important; line-height:1.13!important; padding:6px 9px!important; margin:0!important; page-break-after:always!important; break-after:page!important; }}
main > .strategic-summary:first-child p {{ margin:3px 0!important; line-height:1.12!important; }}
main > .strategic-summary:first-child h2 {{font-size:13pt!important;margin:0 0 5px!important;}}
.grouped-intel{{page-break-before:always!important;break-before:page!important;}}
.summary-item{{font-size:8.9pt!important;line-height:1.16!important;margin:4px 0!important}} .kpi{{font-size:8pt!important}} .kpi th,.kpi td{{padding:4px 5px!important}}
}}
.summary-item{{font-size:14px;line-height:1.46;margin:8px 0;}}
.kpi{{width:100%;border-collapse:collapse;margin:9px 0 12px;font-size:12px;}}
.kpi th,.kpi td{{padding:7px 9px;border:1px solid #d6e2ea;text-align:left;vertical-align:top;}}
.kpi th{{background:#153752;color:white}}
.report-note{{color:#5b7182;font-size:12px;line-height:1.45}}
</style></head><body style="font:15px Arial,sans-serif;background:#f1f4f7;color:#1a2633;margin:0;"><header style="background:#102e48;color:white;padding:25px 5%;position:relative;">{logo_html}<p class="brand-company" style="font-weight:bold;letter-spacing:.03em;margin:6px 0;">STURAM S.A.</p><h1 style="font-size:44px;line-height:1.08;text-transform:uppercase;font-weight:700;margin:7px 0;">INFORME ESTRATÉGICO DIARIO</h1><p style="margin:6px 0;">{subtitle_line}</p></header><main style="max-width:1000px;margin:auto;padding:24px 18px;"><section class="strategic-summary" style="background:#f4f8fc;border:1px solid #d5e1ed;border-left:5px solid #14548b;padding:18px 22px;margin:18px 0 28px;"><h2 style="margin-top:0;color:#124875;">RESUMEN ESTRATÉGICO — IMPACTO STURAM</h2>{summary_html}</section>{stories_html}<section class="management" style="background:#fff;border:1px solid #cedbe8;border-radius:12px;padding:24px;margin:25px 0;"><h2 style="color:#113b5b;margin-top:0;">ANÁLISIS GERENCIAL FINAL — LAS CINCO NOTICIAS DE MAYOR IMPACTO</h2><table class="priority-table" style="border-collapse:collapse;width:100%;font-size:13px;margin:14px 0;"><thead><tr><th style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;background:#153752;color:white;">Prioridad</th><th style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;background:#153752;color:white;">Hecho y cifra contrastada</th><th style="padding:9px;border:1px solid #d8e0e8;vertical-align:top;text-align:left;background:#153752;color:white;">Lectura gerencial específica para STURAM</th></tr></thead><tbody>{top5_rows}</tbody></table></section>{notes_html}</main></body></html>"""
