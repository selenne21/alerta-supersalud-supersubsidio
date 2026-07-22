"""
Funciones para consultar la página de Información Poblacional
de la Superintendencia del Subsidio Familiar.

Criterio de selección:

1. Identificar los enlaces de Información Poblacional.
2. Extraer el periodo indicado en el nombre o en la URL.
3. Escoger el periodo más reciente.
4. Descargar el archivo.
5. Comparar la URL y el hash SHA-256 para detectar cambios.
"""

from pathlib import Path
from urllib.parse import unquote, urljoin
import hashlib
import re
import unicodedata

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


MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def normalizar_texto(texto):
    """
    Convierte el texto a minúsculas, elimina las tildes
    y reemplaza separadores por espacios.
    """

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = re.sub(
        r"[_–—/\\\-]+",
        " ",
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def extraer_periodo_poblacional(nombre, url):
    """
    Extrae el año y el mes desde el nombre o la URL.

    Reconoce, entre otros, estos formatos:

    - mayo 2026
    - 2026 mayo
    - 2026-05
    - 05-2026

    Devuelve un diccionario o None si no identifica
    un periodo válido.
    """

    texto_original = f"{nombre} {url}"
    texto_normalizado = normalizar_texto(
        texto_original
    )

    nombres_meses = "|".join(
        re.escape(mes)
        for mes in MESES
    )

    # Formato: mayo 2026
    patron_mes_anio = re.compile(
        rf"\b({nombres_meses})\b"
        rf"(?:\s+de)?\s+"
        rf"(20\d{{2}})\b"
    )

    coincidencia = patron_mes_anio.search(
        texto_normalizado
    )

    if coincidencia:
        nombre_mes = coincidencia.group(1)
        anio = int(coincidencia.group(2))
        mes = MESES[nombre_mes]

        return {
            "anio": anio,
            "mes": mes,
            "clave": (anio, mes),
            "texto": f"{nombre_mes} {anio}",
            "codigo": f"{anio}-{mes:02d}",
        }

    # Formato: 2026 mayo
    patron_anio_mes = re.compile(
        rf"\b(20\d{{2}})\b"
        rf"(?:\s+de)?\s+"
        rf"({nombres_meses})\b"
    )

    coincidencia = patron_anio_mes.search(
        texto_normalizado
    )

    if coincidencia:
        anio = int(coincidencia.group(1))
        nombre_mes = coincidencia.group(2)
        mes = MESES[nombre_mes]

        return {
            "anio": anio,
            "mes": mes,
            "clave": (anio, mes),
            "texto": f"{nombre_mes} {anio}",
            "codigo": f"{anio}-{mes:02d}",
        }

    # Formato numérico: 2026-05, 2026_05 o 2026/05
    patron_anio_mes_numerico = re.compile(
        r"\b(20\d{2})[\s_\-/]+(0?[1-9]|1[0-2])\b"
    )

    coincidencia = patron_anio_mes_numerico.search(
        texto_original
    )

    if coincidencia:
        anio = int(coincidencia.group(1))
        mes = int(coincidencia.group(2))

        return {
            "anio": anio,
            "mes": mes,
            "clave": (anio, mes),
            "texto": f"{anio}-{mes:02d}",
            "codigo": f"{anio}-{mes:02d}",
        }

    # Formato numérico: 05-2026, 05_2026 o 05/2026
    patron_mes_anio_numerico = re.compile(
        r"\b(0?[1-9]|1[0-2])[\s_\-/]+(20\d{2})\b"
    )

    coincidencia = patron_mes_anio_numerico.search(
        texto_original
    )

    if coincidencia:
        mes = int(coincidencia.group(1))
        anio = int(coincidencia.group(2))

        return {
            "anio": anio,
            "mes": mes,
            "clave": (anio, mes),
            "texto": f"{anio}-{mes:02d}",
            "codigo": f"{anio}-{mes:02d}",
        }

    return None


def buscar_archivos_poblacionales():
    """
    Consulta la página de Supersubsidio y devuelve los enlaces
    relacionados con Información Poblacional.

    Los resultados con un periodo identificable se ordenan
    desde el más reciente hasta el más antiguo.
    """

    respuesta = requests.get(
        URL_SUPERSUBSIDIO,
        timeout=TIMEOUT,
        headers=HEADERS,
    )

    respuesta.raise_for_status()

    sopa = BeautifulSoup(
        respuesta.text,
        "html.parser",
    )

    archivos = []

    for enlace in sopa.find_all(
        "a",
        href=True,
    ):
        texto = enlace.get_text(
            " ",
            strip=True,
        )

        href = enlace.get(
            "href",
            "",
        ).strip()

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

        es_icono = (
            "iconos-archivos"
            in href_minuscula
        )

        if (
            es_poblacional
            and es_documento
            and not es_icono
        ):
            nombre = (
                texto
                or href.rstrip("/").split("/")[-1]
            )

            url_archivo = urljoin(
                URL_SUPERSUBSIDIO,
                href,
            )

            periodo = extraer_periodo_poblacional(
                nombre,
                url_archivo,
            )

            archivos.append(
                {
                    "entidad": "Supersubsidio",
                    "categoria": "POBLACIONAL",
                    "nombre": nombre,
                    "url": url_archivo,
                    "periodo": periodo,
                }
            )

    archivos_unicos = []
    urls_vistas = set()

    for archivo in archivos:
        if archivo["url"] in urls_vistas:
            continue

        archivos_unicos.append(archivo)
        urls_vistas.add(archivo["url"])

    archivos_con_periodo = [
        archivo
        for archivo in archivos_unicos
        if archivo["periodo"] is not None
    ]

    archivos_sin_periodo = [
        archivo
        for archivo in archivos_unicos
        if archivo["periodo"] is None
    ]

    archivos_con_periodo.sort(
        key=lambda archivo: (
            archivo["periodo"]["clave"]
        ),
        reverse=True,
    )

    return (
        archivos_con_periodo
        + archivos_sin_periodo
    )


def calcular_hash(ruta_archivo):
    """
    Calcula la huella SHA-256 del archivo descargado.
    """

    hash_sha256 = hashlib.sha256()

    with open(
        ruta_archivo,
        "rb",
    ) as archivo:
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
    y conserva su contenido original.
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

        nombre_archivo = unquote(
            nombre_archivo
        )

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
    Garantiza que estado.json tenga las secciones necesarias.
    """

    if not isinstance(estado, dict):
        estado = {}

    if not isinstance(
        estado.get("supersubsidio"),
        dict,
    ):
        estado["supersubsidio"] = {}

    estado["supersubsidio"].setdefault(
        "url",
        "",
    )

    estado["supersubsidio"].setdefault(
        "hash",
        "",
    )

    estado["supersubsidio"].setdefault(
        "periodo",
        "",
    )

    estado["supersubsidio"].setdefault(
        "nombre",
        "",
    )

    if not isinstance(
        estado.get("supersalud"),
        dict,
    ):
        estado["supersalud"] = {}

    for categoria in (
        "EPS",
        "IPS",
        "EMP",
    ):
        if not isinstance(
            estado["supersalud"].get(
                categoria
            ),
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
    periodo_anterior,
    url_actual,
    hash_actual,
    periodo_actual,
):
    """
    Determina si existe una nueva publicación,
    una actualización o ningún cambio.
    """

    if not url_anterior:
        return "NUEVO ARCHIVO REGISTRADO"

    if (
        periodo_anterior
        and periodo_actual
        and periodo_anterior != periodo_actual
    ):
        return "NUEVA PUBLICACIÓN"

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

    periodo = archivo_mas_reciente.get(
        "periodo"
    )

    periodo_texto = (
        periodo["texto"]
        if periodo
        else "Periodo no identificado"
    )

    periodo_codigo = (
        periodo["codigo"]
        if periodo
        else ""
    )

    print(
        f"\nNombre: "
        f"{archivo_mas_reciente['nombre']}"
    )

    print(
        f"Periodo detectado: "
        f"{periodo_texto}"
    )

    print(
        f"URL: "
        f"{archivo_mas_reciente['url']}"
    )

    if periodo is None:
        print(
            "\nADVERTENCIA: no se pudo identificar "
            "el periodo del archivo seleccionado."
        )

        print(
            "Se conservó el orden original de la página "
            "para los archivos sin periodo."
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

    periodo_anterior = estado_anterior.get(
        "periodo",
        "",
    )

    url_actual = archivo_mas_reciente["url"]

    estado_cambio = determinar_estado_cambio(
        url_anterior=url_anterior,
        hash_anterior=hash_anterior,
        periodo_anterior=periodo_anterior,
        url_actual=url_actual,
        hash_actual=hash_archivo,
        periodo_actual=periodo_codigo,
    )

    print(f"\n{estado_cambio}")

    estado["supersubsidio"] = {
        "url": url_actual,
        "hash": hash_archivo,
        "periodo": periodo_codigo,
        "nombre": archivo_mas_reciente["nombre"],
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
        "periodo": periodo_texto,
        "periodo_clave": periodo_codigo,
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
    