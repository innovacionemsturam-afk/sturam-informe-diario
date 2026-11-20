"""Configuración central del Informe Estratégico Diario de STURAM S.A."""

from datetime import timezone, timedelta

TZ_CORDOBA = timezone(timedelta(hours=-3), name="America/Argentina/Cordoba")

# Colores y diseño corporativo (Sección 11)
COLOR_PRIMARY_DARK = "#102e48"
COLOR_REGION_BLUE = "#0648c8"
FONT_FAMILY = "Arial, Helvetica, sans-serif"

# Destinatarios obligatorios (Sección 13: exactamente 17 direcciones)
EMAIL_TO = ["anasturam@gmail.com"]
EMAIL_CC = [
    "cesar.ortega@emsturam.com.ar",
    "cristian.perelli@emsturam.com.ar",
    "ezequiel.fabro@emsturam.com.ar",
    "michelle.quijada@emsturam.com.ar",
    "silvana.caceres@emsturam.com.ar",
    "julio.beltran@emsturam.com.ar",
    "hernan.rp@emsturam.com.ar",
    "g.sturam@emsturam.com.ar",
    "maximiliano.ledesma@emsturam.com.ar",
    "rodolfo.salas@emsturam.com.ar",
    "trinidad.cardozo@emsturam.com.ar",
    "gonzalo.herrera@emsturam.com.ar",
    "dante.bustos@emsturam.com.ar",
    "dario.leguizamon@emsturam.com.ar",
    "cristian.bono@emsturam.com.ar",
    "luisasturam@gmail.com",
]

SUBJECT_PREFIX = "STURAM S.A. | Informe estratégico diario |"

PLAIN_TEXT_ALT = (
    "Buen dia, envio Informe estrategico diario de STURAM SA para su "
    "informacion y analisis. slds y que tenga un excelente dia."
)

# Orden exacto de secciones (Sección 4.C)
REGIONS_ORDER = [
    "ARGENTINA",
    "CÓRDOBA, ARGENTINA",
    "BRASIL",
    "ALUMINIO",
    "PETRÓLEO",
    "LATINOAMÉRICA",
    "ESTADOS UNIDOS",
    "EUROPA",
    "CHINA",
    "RUSIA",
    "INDIA",
    "ASIA",
    "GLOBAL",
]

MAX_NEWS_PER_EDITION = 30

# Clientes actuales y potenciales a monitorear (Sección 8)
CLIENTS_WATCHLIST = [
    "Volkswagen",
    "Stellantis",
    "Mercedes-Benz",
    "Daimler Truck",
    "IVECO",
    "Toyota",
    "Volvo",
    "ZF",
    "Renault",
    "General Motors",
    "Ford",
    "Tesla",
    "BYD",
]

# Competidores de fundición HPDC/LPDC/Gravedad (Fundal excluida por regla)
COMPETITORS_WATCHLIST = [
    "Nemak",
    "Bocar Group",
    "CIE Automotive",
    "Ahresty",
    "Dynacast",
    "Aludyne",
    "Handtmann",
    "Ryobi",
    "Gibbs",
    "GF Casting Solutions",
]

# Tecnología de fundición, Robótica e Industria 4.0
FOUNDRY_TECH_WATCHLIST = [
    "Bühler Group",
    "LK Machinery",
    "IDRA Group",
    "Italpresse Gauss",
    "YIZUMI",
]

ROBOTICS_AND_I40_WATCHLIST = [
    "ABB Robotics",
    "FANUC",
    "KUKA",
    "Yaskawa",
    "Universal Robots",
    "Siemens",
    "Rockwell Automation",
    "Schneider Electric",
    "NVIDIA",
]
