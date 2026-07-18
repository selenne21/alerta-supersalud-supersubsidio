"""
Funciones para consultar la página de Información Poblacional
de la Superintendencia del Subsidio Familiar.
"""

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import TIMEOUT, URL_SUPERSUBSIDIO


def buscar_archivos_poblacionales():
    """
    Consulta la página de Supersubsidio y devuelve los enlaces
    relacionados con Información Poblacional.
    """

    respuesta = requests.get(
        URL_SUPERSUBSIDIO,
        timeout=TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        },
    )

    respuesta.raise_for_status()

    sopa = BeautifulSoup(respuesta.text, "html.parser")
    archivos = []

    for enlace in sopa.find_all("a", href=True):
        texto = enlace.get_text(" ", strip=True)
        href = enlace["href"]

        texto_minuscula = texto.lower()
        href_minuscula = href.lower()

        es_poblacional = "poblacional" in texto_minuscula
        es_archivo = any(
            extension in href_minuscula
            for extension in (".xlsx", ".xls", ".csv", ".zip")
        )

        if es_poblacional and es_archivo:
            archivos.append(
                {
                    "entidad": "Supersubsidio",
                    "categoria": "POBLACIONAL",
                    "nombre": texto or href.split("/")[-1],
                    "url": urljoin(URL_SUPERSUBSIDIO, href),
                }
            )

    return archivos


if __name__ == "__main__":
    resultados = buscar_archivos_poblacionales()

    print("=" * 60)
    print("ARCHIVOS ENCONTRADOS EN SUPERSUBSIDIO")
    print("=" * 60)

    if not resultados:
        print("No se encontraron archivos de Información Poblacional.")
    else:
        for numero, archivo in enumerate(resultados, start=1):
            print(f"\nArchivo {numero}")
            print(f"Nombre: {archivo['nombre']}")
            print(f"Enlace: {archivo['url']}")

        print(f"\nTotal encontrado: {len(resultados)}")
