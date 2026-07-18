"""
Funciones para consultar la página de Información Poblacional
de la Superintendencia del Subsidio Familiar.
"""

from pathlib import Path
from urllib.parse import unquote, urljoin
import hashlib

import requests
from bs4 import BeautifulSoup

from config import TIMEOUT, URL_SUPERSUBSIDIO
from estado import cargar_estado, guardar_estado


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}


def buscar_archivos_poblacionales():
    """
    Consulta la página de Supersubsidio y devuelve los enlaces
    relacionados con Información Poblacional.
    """

    respuesta = requests.get(
        URL_SUPERSUBSIDIO,
        timeout=TIMEOUT,
        headers=HEADERS,
    )

    respuesta.raise_for_status()

    sopa = BeautifulSoup(respuesta.text, "html.parser")
    archivos = []

    for enlace in sopa.find_all("a", href=True):
        texto = enlace.get_text(" ", strip=True)
        href = enlace.get("href", "").strip()

        texto_minuscula = texto.lower()
        href_minuscula = href.lower()

        es_poblacional = (
            "información poblacional" in texto_minuscula
            or "informacion poblacional" in texto_minuscula
            or "poblacional" in href_minuscula
        )

        es_documento = (
            "/documents/" in href_minuscula
            or ".xlsx" in href_minuscula
            or ".xls" in href_minuscula
            or ".csv" in href_minuscula
            or ".zip" in href_minuscula
        )

        es_icono = "iconos-archivos" in href_minuscula

        if es_poblacional and es_documento and not es_icono:
            nombre = texto or href.rstrip("/").split("/")[-1]

            archivos.append(
                {
                    "entidad": "Supersubsidio",
                    "categoria": "POBLACIONAL",
                    "nombre": nombre,
                    "url": urljoin(
                        URL_SUPERSUBSIDIO,
                        href,
                    ),
                }
            )

    archivos_unicos = []
    urls_vistas = set()

    for archivo in archivos:
        if archivo["url"] not in urls_vistas:
            archivos_unicos.append(archivo)
            urls_vistas.add(archivo["url"])

    return archivos_unicos


def calcular_hash(ruta_archivo):
    """
    Calcula la huella SHA-256 del archivo descargado.
    """

    hash_sha256 = hashlib.sha256()

    with open(ruta_archivo, "rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(8192),
            b"",
        ):
            hash_sha256.update(bloque)

    return hash_sha256.hexdigest()


def limpiar_nombre_archivo(nombre_archivo):
    """
    Elimina caracteres no permitidos por Windows.
    """

    caracteres_invalidos = '<>:"/\\|?*'

    for caracter in caracteres_invalidos:
        nombre_archivo = nombre_archivo.replace(
            caracter,
            "_",
        )

    return nombre_archivo.strip()


def descargar_archivo(
    archivo,
    carpeta_destino="descargas",
):
    """
    Descarga un archivo encontrado en Supersubsidio
    y conserva su contenido original sin modificarlo.
    """

    carpeta = Path(carpeta_destino)

    carpeta.mkdir(
        parents=True,
        exist_ok=True,
    )

    respuesta = requests.get(
        archivo["url"],
        timeout=TIMEOUT,
        headers=HEADERS,
    )

    respuesta.raise_for_status()

    if len(respuesta.content) < 1000:
        raise ValueError(
            "El archivo descargado de Supersubsidio "
            "es demasiado pequeño."
        )

    content_disposition = respuesta.headers.get(
        "Content-Disposition",
        "",
    )

    nombre_archivo = None

    if "filename=" in content_disposition:
        nombre_archivo = content_disposition.split(
            "filename=",
            1,
        )[1]

        nombre_archivo = (
            nombre_archivo
            .strip()
            .strip('"')
            .strip("'")
        )

        nombre_archivo = unquote(nombre_archivo)

    if not nombre_archivo:
        nombre_archivo = archivo["nombre"]

    if not Path(nombre_archivo).suffix:
        tipo_contenido = respuesta.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "spreadsheetml" in tipo_contenido:
            nombre_archivo += ".xlsx"

        elif "ms-excel" in tipo_contenido:
            nombre_archivo += ".xls"

        elif "csv" in tipo_contenido:
            nombre_archivo += ".csv"

        elif "zip" in tipo_contenido:
            nombre_archivo += ".zip"

        else:
            nombre_archivo += ".xlsx"

    nombre_archivo = limpiar_nombre_archivo(
        nombre_archivo
    )

    ruta_archivo = carpeta / nombre_archivo

    ruta_archivo.write_bytes(
        respuesta.content
    )

    return ruta_archivo


def asegurar_estructura_estado(estado):
    """
    Garantiza que estado.json tenga las secciones necesarias
    para Supersubsidio y Supersalud.
    """

    if not isinstance(estado, dict):
        estado = {}

    if not isinstance(
        estado.get("supersubsidio"),
        dict,
    ):
        estado["supersubsidio"] = {
            "url": "",
            "hash": "",
        }

    if not isinstance(
        estado.get("supersalud"),
        dict,
    ):
        estado["supersalud"] = {}

    for categoria in ("EPS", "IPS", "EMP"):
        if not isinstance(
            estado["supersalud"].get(categoria),
            dict,
        ):
            estado["supersalud"][categoria] = {
                "id": "",
                "hash": "",
            }

    return estado


def determinar_estado_cambio(
    url_anterior,
    hash_anterior,
    url_actual,
    hash_actual,
):
    """
    Determina si hay una nueva publicación,
    una actualización o ningún cambio.
    """

    if not url_anterior:
        return "NUEVO ARCHIVO REGISTRADO"

    if url_anterior != url_actual:
        return "NUEVA PUBLICACIÓN"

    if hash_anterior != hash_actual:
        return "ARCHIVO ACTUALIZADO"

    return "SIN CAMBIOS"


def procesar_supersubsidio():
    """
    Busca el archivo poblacional más reciente, lo descarga,
    calcula su hash y lo compara con estado.json.
    """

    print("\n" + "=" * 70)
    print("SUPERSUBSIDIO - INFORMACIÓN POBLACIONAL")
    print("=" * 70)

    resultados = buscar_archivos_poblacionales()

    if not resultados:
        print(
            "No se encontraron archivos de "
            "Información Poblacional."
        )

        return None

    print(
        f"Total de archivos encontrados: "
        f"{len(resultados)}"
    )

    archivo_mas_reciente = resultados[0]

    print(
        f"\nNombre: "
        f"{archivo_mas_reciente['nombre']}"
    )

    print(
        f"URL: "
        f"{archivo_mas_reciente['url']}"
    )

    ruta_archivo = descargar_archivo(
        archivo_mas_reciente
    )

    hash_archivo = calcular_hash(
        ruta_archivo
    )

    print("\nArchivo descargado correctamente:")
    print(ruta_archivo)

    print(
        f"Tamaño: "
        f"{ruta_archivo.stat().st_size:,} bytes"
    )

    print(
        f"Hash SHA-256: "
        f"{hash_archivo}"
    )

    estado = cargar_estado()

    estado = asegurar_estructura_estado(
        estado
    )

    estado_anterior = estado["supersubsidio"]

    url_anterior = estado_anterior.get(
        "url",
        "",
    )

    hash_anterior = estado_anterior.get(
        "hash",
        "",
    )

    url_actual = archivo_mas_reciente["url"]

    estado_cambio = determinar_estado_cambio(
        url_anterior=url_anterior,
        hash_anterior=hash_anterior,
        url_actual=url_actual,
        hash_actual=hash_archivo,
    )

    print(f"\n{estado_cambio}")

    estado["supersubsidio"] = {
        "url": url_actual,
        "hash": hash_archivo,
    }

    guardar_estado(estado)

    debe_alertar = estado_cambio in {
        "NUEVA PUBLICACIÓN",
        "ARCHIVO ACTUALIZADO",
    }

    return {
        "entidad": "Supersubsidio",
        "categoria": "POBLACIONAL",
        "nombre": archivo_mas_reciente["nombre"],
        "url": url_actual,
        "ruta": ruta_archivo,
        "hash": hash_archivo,
        "fecha_actualizacion": "No disponible",
        "estado_cambio": estado_cambio,
        "debe_alertar": debe_alertar,
    }


def ejecutar_supersubsidio():
    """
    Ejecuta el proceso con control de errores.
    """

    try:
        return procesar_supersubsidio()

    except requests.RequestException as error:
        print("\n" + "!" * 70)
        print("ERROR DE CONEXIÓN EN SUPERSUBSIDIO")
        print(
            f"{type(error).__name__}: "
            f"{error}"
        )
        print("!" * 70)

        return None

    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
    ) as error:
        print("\n" + "!" * 70)
        print("ERROR AL PROCESAR SUPERSUBSIDIO")
        print(
            f"{type(error).__name__}: "
            f"{error}"
        )
        print("!" * 70)

        return None


if __name__ == "__main__":
    ejecutar_supersubsidio()