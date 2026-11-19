"""Generador de plantilla HTML corporativa para STURAM S.A.

Compatible con clientes de correo (Gmail Web, Outlook, móvil) usando tablas
y estilos inline, y optimizada para impresión en formato A4 vertical.
Colores: #102e48 (encabezado oscuro), #0648c8 (títulos regionales).
Tipografía: Arial.
"""

from html import escape
from typing import Any


def _badge_color(impact_type: str) -> tuple[str, str]:
    """Devuelve (background, text_color) según tipo de impacto."""
    upper = (impact_type or "").upper()
    if "POSITIVO" in upper:
        return ("#e6f4ea", "#137333")
    if "NEGATIVO" in upper:
        return ("#fce8e6", "#c5221f")
    return ("#fef7e0", "#b06000")


def render_report_html(report: dict[str, Any], has_logo: bool = False) -> str:
    """Renderiza el informe completo en HTML listo para el cuerpo de Gmail."""
    edition_date = escape(report.get("edition_date", ""))
    summary_bullets = report.get("strategic_summary", [])
    regions = report.get("regions", [])
    special_bulletins = report.get("special_bulletins", [])
    top_five = report.get("top_five_analysis", [])

    summary_html = ""
    for item in summary_bullets:
        topic = escape(item.get("topic", ""))
        text = escape(item.get("text", ""))
        summary_html += f"""
        <tr>
          <td style="padding:4px 0 6px 0;font-family:Arial,Helvetica,sans-serif;font-size:12.5px;line-height:1.45;color:#1f2937;vertical-align:top;">
            <span style="color:#0648c8;font-weight:bold;">&#9632; {topic}:</span> {text}
          </td>
        </tr>"""

    regions_html = ""
    for region_block in regions:
        region_name = escape(region_block.get("region", ""))
        news_list = region_block.get("news", [])
        if not news_list:
            continue

        news_cards = ""
        for idx, n in enumerate(news_list):
            title = escape(n.get("title", ""))
            pub_date = escape(n.get("published_date", ""))
            data_date = escape(n.get("data_date", ""))
            fact = escape(n.get("fact_description", ""))
            source_name = escape(n.get("source_name", "Fuente original"))
            source_url = escape(n.get("source_url", "#"))
            impact_label = escape(n.get("impact_label", "MIXTO"))
            impact_text = escape(n.get("impact_detail", ""))
            bg_col, txt_col = _badge_color(impact_label)

            border_top = "1px solid #e5e7eb" if idx > 0 else "none"
            news_cards += f"""
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:{border_top};padding-top:10px;margin-top:8px;page-break-inside:avoid;">
              <tr>
                <td style="font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;color:#0648c8;letter-spacing:0.4px;text-transform:uppercase;">
                  {region_name}
                </td>
              </tr>
              <tr>
                <td style="padding:3px 0 4px 0;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:#102e48;line-height:1.3;">
                  {title}
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 6px 0;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#6b7280;">
                  Publicación: {pub_date} &nbsp;|&nbsp; Datos: {data_date}
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 6px 0;font-family:Arial,Helvetica,sans-serif;font-size:12.5px;color:#111827;line-height:1.45;">
                  <strong style="color:#102e48;">DESCRIPCIÓN DEL HECHO:</strong> {fact}
                  &nbsp;<a href="{source_url}" style="color:#0648c8;text-decoration:underline;font-size:11.5px;">[{source_name}]</a>
                </td>
              </tr>
              <tr>
                <td style="padding:6px 10px;background-color:#f8fafc;border-left:3px solid #102e48;font-family:Arial,Helvetica,sans-serif;font-size:12.5px;color:#1f2937;line-height:1.45;">
                  <span style="display:inline-block;padding:1px 6px;border-radius:3px;background-color:{bg_col};color:{txt_col};font-weight:bold;font-size:11px;margin-right:4px;">
                    IMPACTO STURAM — {impact_label}
                  </span>
                  {impact_text}
                </td>
              </tr>
            </table>"""

        regions_html += f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:18px;">
          <tr>
            <td style="padding:6px 0 4px 0;border-bottom:2px solid #0648c8;font-family:Arial,Helvetica,sans-serif;font-size:16px;font-weight:bold;color:#0648c8;text-transform:uppercase;">
              {region_name}
            </td>
          </tr>
          <tr>
            <td>{news_cards}</td>
          </tr>
        </table>"""

    bulletins_html = ""
    if special_bulletins:
        items_html = ""
        for b in special_bulletins:
            b_title = escape(b.get("title", ""))
            b_body = escape(b.get("body", ""))
            items_html += f"""
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-family:Arial,Helvetica,sans-serif;font-size:12.5px;color:#1f2937;line-height:1.45;">
                <strong style="color:#102e48;">{b_title}</strong><br/>
                {b_body}
              </td>
            </tr>"""
        bulletins_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;page-break-inside:avoid;">
          <tr>
            <td style="padding:6px 0 4px 0;border-bottom:2px solid #102e48;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;color:#102e48;text-transform:uppercase;">
              BOLETINES ESPECIALES
            </td>
          </tr>
          {items_html}
        </table>"""

    top5_html = ""
    for i, item in enumerate(top_five, start=1):
        fact = escape(item.get("fact_and_figure", ""))
        kind = escape(item.get("risk_or_opportunity", ""))
        mech = escape(item.get("mechanism", ""))
        horizon = escape(item.get("horizon", ""))
        watch = escape(item.get("what_to_watch", ""))
        top5_html += f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid #e5e7eb;font-family:Arial,Helvetica,sans-serif;font-size:12.5px;line-height:1.45;color:#1f2937;">
            <strong style="color:#102e48;">{i}. {fact}</strong>
            <span style="color:#0648c8;font-weight:bold;">[{kind}]</span><br/>
            <strong>Mecanismo:</strong> {mech}<br/>
            <strong>Horizonte:</strong> {horizon} &nbsp;|&nbsp; <strong>A observar:</strong> {watch}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>INFORME ESTRATÉGICO DIARIO — STURAM S.A.</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 12mm;
    }}
    @media print {{
      body {{ margin: 0; background: #ffffff; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f3f4f6;padding:12px 0;">
    <tr>
      <td align="center">
        <!-- Contenedor principal ancho A4 (~740px) -->
        <table width="740" cellpadding="0" cellspacing="0" border="0" style="width:740px;max-width:100%;background-color:#ffffff;border:1px solid #d1d5db;">
          <!-- A. ENCABEZADO -->
          <tr>
            <td style="background-color:#102e48;padding:20px 24px;color:#ffffff;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:21px;font-weight:bold;letter-spacing:0.6px;text-transform:uppercase;margin:0;">
                      INFORME ESTRATÉGICO DIARIO
                    </div>
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;color:#cbd5e1;margin-top:4px;">
                      STURAM S.A.
                    </div>
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:12.5px;color:#e2e8f0;margin-top:6px;">
                      {edition_date}
                    </div>
                  </td>
                  {'''<td align="right" style="vertical-align:middle;width:150px;">
                    <img src="cid:sturam_logo" alt="STURAM S.A." style="max-height:54px;max-width:140px;display:block;border:0;" />
                  </td>''' if has_logo else ""}
                </tr>
              </table>
            </td>
          </tr>

          <!-- Cuerpo -->
          <tr>
            <td style="padding:18px 24px 24px 24px;">
              <!-- B. RESUMEN ESTRATÉGICO -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;border:1px solid #cbd5e1;border-top:4px solid #102e48;padding:12px 14px;page-break-after:auto;">
                <tr>
                  <td style="padding-bottom:8px;font-family:Arial,Helvetica,sans-serif;font-size:14.5px;font-weight:bold;color:#102e48;text-transform:uppercase;">
                    RESUMEN ESTRATÉGICO — IMPACTO STURAM
                  </td>
                </tr>
                {summary_html}
              </table>

              <!-- C. NOTICIAS DESARROLLADAS -->
              {regions_html}

              <!-- D. BOLETINES ESPECIALES -->
              {bulletins_html}

              <!-- E. ANÁLISIS GERENCIAL FINAL -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:22px;border:1px solid #102e48;page-break-inside:avoid;">
                <tr>
                  <td style="background-color:#102e48;padding:8px 12px;font-family:Arial,Helvetica,sans-serif;font-size:13.5px;font-weight:bold;color:#ffffff;text-transform:uppercase;">
                    ANÁLISIS GERENCIAL FINAL — LAS CINCO NOTICIAS DE MAYOR IMPACTO
                  </td>
                </tr>
                {top5_html}
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
