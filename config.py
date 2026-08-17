"""Configuración general de la automatización."""#guarda información para que las otras areas lo utilicen
# Página oficial de Supersubsidio
URL_SUPERSUBSIDIO = "https://www.ssf.gov.co/poblacional"

# Búsquedas oficiales de Supersalud
URLS_SUPERSALUD = {
    "EPS": "https://mapas.supersalud.gov.co/arcgisportal/apps/sites/#/datos-abiertos/search?q=eps&sort=-modified",
    "IPS": "https://mapas.supersalud.gov.co/arcgisportal/apps/sites/#/datos-abiertos/search?q=ips&sort=-modified",
    "EMP": "https://mapas.supersalud.gov.co/arcgisportal/apps/sites/#/datos-abiertos/search?q=emp&sort=-modified",
}

# Archivo donde guardaremos el historial
ARCHIVO_ESTADO = "estado.json"

# Tiempo máximo de espera
TIMEOUT = 60

# Asuntos de los correos
ASUNTOS = {
    "POBLACIONAL": "Nueva publicación - Supersubsidio - Información poblacional",
    "EPS": "Nueva publicación - Supersalud - EPS",
    "IPS": "Nueva publicación - Supersalud - IPS",
    "EMP": "Nueva publicación - Supersalud - EMP",
}
