"""
Funciones para consultar y descargar los archivos financieros
publicados por la Superintendencia Nacional de Salud.

Categorías vigiladas:

1. EPS.
2. IPS privadas.
3. Entidades de Medicina Prepagada y SAP.
"""

from datetime import datetime
from pathlib import Path
import hashlib

import requests

from estado import cargar_estado, guardar_estado


URL_BUSCADOR = (
    "https://mapas.supersalud.gov.co/"
    "arcgisportal/sharing/rest/search"
)

URL_DESCARGA_BASE = (
    "https://mapas.supersalud.gov.co/"
    "arcgisportal/sharing/rest/content/items"
)

CARPETA_DESCARGAS = Path("descargas")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}

CATEGORIAS = ("EPS", "IPS", "EMP")

PATRONES = {
    "EPS": [
        (
            "catálogo de información financiera eps del régimen "
            "contributivo y subsidiado"
        ),
        (
            "catalogo de informacion financiera eps del regimen "
            "contributivo y subsidiado"
        ),
    ],
    "IPS": [
        (
            "catálogo de información financiera de las instituciones "
            "prestadoras de servicios de salud (ips) privadas"
        ),
        (
            "catalogo de informacion financiera de las instituciones "
            "prestadoras de servicios de salud (ips) privadas"
        ),
    ],
    "EMP": [
        (
            "catálogo de información financiera de entidades de medicina "
            "prepagada (emp) y servicios de ambulancia prepagada (sap)"
        ),
        (
            "catalogo de informacion financiera de entidades de medicina "
            "prepagada (emp) y servicios de ambulancia prepagada (sap)"
        ),
    ],
}


def convertir_fecha(fecha_milisegundos):
    """
    Convierte la fecha interna de ArcGIS a un formato legible.
    """

    if not fecha_milisegundos:
        return "Fecha no disponible"

    fecha = datetime.fromtimestamp(fecha_milisegundos / 1000)

    return fecha.strftime("%Y-%m-%d %H:%M:%S")


def titulo_valido(categoria, titulo):
    """
    Comprueba que el título pertenezca a la serie correcta
    de EPS, IPS o EMP.
    """

    if categoria not in PATRONES:
        raise ValueError(
            f"La categoría {categoria} no está configurada."
        )

    titulo_minuscula = titulo.lower().strip()

    return any(
        patron in titulo_minuscula
        for patron in PATRONES[categoria]
    )


def calcular_hash(ruta_archivo):
    """
    Calcula la huella SHA-256 del archivo descargado.
    """

    hash_sha256 = hashlib.sha256()

    with open(ruta_archivo, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(8192), b""):
            hash_sha256.update(bloque)

    return hash_sha256.hexdigest()


def buscar_archivo_mas_reciente(categoria):
    """
    Busca en ArcGIS los Excel de la categoría indicada
    y devuelve únicamente el más reciente.
    """

    parametros = {
        "f": "json",
        "q": categoria,
        "sortField": "modified",
        "sortOrder": "desc",
        "num": 100,
    }

    respuesta = requests.get(
        URL_BUSCADOR,
        params=parametros,
        headers=HEADERS,
        timeout=60,
    )

    respuesta.raise_for_status()

    datos = respuesta.json()
    candidatos = []

    for resultado in datos.get("results", []):
        titulo = resultado.get("title", "")
        tipo = resultado.get("type", "")
        fecha = resultado.get("modified", 0)
        identificador = resultado.get("id", "")

        if not identificador:
            continue

        if "excel" not in tipo.lower():
            continue

        if not titulo_valido(categoria, titulo):
            continue

        candidatos.append(
            {
                "titulo": titulo,
                "tipo": tipo,
                "fecha": fecha,
                "id": identificador,
            }
        )

    if not candidatos:
        return None

    candidatos.sort(
        key=lambda archivo: archivo["fecha"],
        reverse=True,
    )

    return candidatos[0]


def limpiar_nombre_archivo(texto):
    """
    Elimina caracteres que Windows no permite
    en los nombres de archivo.
    """

    caracteres_invalidos = '<>:"/\\|?*'
    nombre_limpio = texto

    for caracter in caracteres_invalidos:
        nombre_limpio = nombre_limpio.replace(
            caracter,
            "",
        )

    return nombre_limpio.strip()


def descargar_archivo(categoria, resultado):
    """
    Descarga el Excel original de ArcGIS.

    Devuelve:

    - La ruta local del archivo.
    - La URL directa utilizada para descargarlo.
    """

    CARPETA_DESCARGAS.mkdir(
        parents=True,
        exist_ok=True,
    )

    nombre_base = limpiar_nombre_archivo(
        resultado["titulo"]
    )

    nombre_archivo = (
        f"{categoria}_{nombre_base}.xlsx"
    )

    ruta_salida = (
        CARPETA_DESCARGAS / nombre_archivo
    )

    url_descarga = (
        f"{URL_DESCARGA_BASE}/"
        f"{resultado['id']}/data"
    )

    respuesta = requests.get(
        url_descarga,
        headers=HEADERS,
        timeout=120,
    )

    respuesta.raise_for_status()

    tipo_contenido = respuesta.headers.get(
        "Content-Type",
        "",
    ).lower()

    if len(respuesta.content) < 1000:
        raise ValueError(
            f"El archivo recibido para {categoria} "
            "es demasiado pequeño."
        )

    tipos_permitidos = (
        "spreadsheet",
        "excel",
        "octet-stream",
        "zip",
    )

    if not any(
        tipo in tipo_contenido
        for tipo in tipos_permitidos
    ):
        raise ValueError(
            f"El servidor no devolvió un Excel para "
            f"{categoria}. Tipo recibido: "
            f"{tipo_contenido or 'desconocido'}"
        )

    ruta_salida.write_bytes(
        respuesta.content
    )

    return ruta_salida, url_descarga


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
        estado["supersubsidio"] = {
            "url": "",
            "hash": "",
        }

    if not isinstance(
        estado.get("supersalud"),
        dict,
    ):
        estado["supersalud"] = {}

    for categoria in CATEGORIAS:
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
    id_anterior,
    hash_anterior,
    id_actual,
    hash_actual,
):
    """
    Compara el archivo actual con el estado anterior.
    """

    if not id_anterior:
        return "NUEVO ARCHIVO REGISTRADO"

    if id_anterior != id_actual:
        return "NUEVA PUBLICACIÓN"

    if hash_anterior != hash_actual:
        return "ARCHIVO ACTUALIZADO"

    return "SIN CAMBIOS"


def procesar_categoria(categoria):
    """
    Busca, descarga y compara el archivo más reciente
    de una categoría de Supersalud.

    Devuelve un diccionario con la información del resultado.
    """

    print("\n" + "=" * 70)
    print(f"SUPERSALUD - {categoria}")
    print("=" * 70)

    resultado = buscar_archivo_mas_reciente(
        categoria
    )

    if resultado is None:
        print("No se encontró un archivo válido.")
        return None

    fecha_legible = convertir_fecha(
        resultado["fecha"]
    )

    print(f"Título: {resultado['titulo']}")
    print(f"ID: {resultado['id']}")
    print(
        "Fecha de actualización: "
        f"{fecha_legible}"
    )

    ruta_archivo, url_descarga = descargar_archivo(
        categoria,
        resultado,
    )

    hash_archivo = calcular_hash(
        ruta_archivo
    )

    print("\nArchivo descargado correctamente:")
    print(ruta_archivo)
    print(f"URL de descarga: {url_descarga}")
    print(f"Hash SHA-256: {hash_archivo}")

    estado = cargar_estado()
    estado = asegurar_estructura_estado(
        estado
    )

    estado_anterior = (
        estado["supersalud"][categoria]
    )

    id_anterior = estado_anterior.get(
        "id",
        "",
    )

    hash_anterior = estado_anterior.get(
        "hash",
        "",
    )

    estado_cambio = determinar_estado_cambio(
        id_anterior=id_anterior,
        hash_anterior=hash_anterior,
        id_actual=resultado["id"],
        hash_actual=hash_archivo,
    )

    print(f"\n{estado_cambio}")

    estado["supersalud"][categoria] = {
        "id": resultado["id"],
        "hash": hash_archivo,
    }

    guardar_estado(estado)

    debe_alertar = estado_cambio in {
        "NUEVA PUBLICACIÓN",
        "ARCHIVO ACTUALIZADO",
    }

    return {
        "entidad": "Supersalud",
        "categoria": categoria,
        "nombre": resultado["titulo"],
        "id": resultado["id"],
        "url": url_descarga,
        "ruta": ruta_archivo,
        "hash": hash_archivo,
        "fecha_actualizacion": fecha_legible,
        "estado_cambio": estado_cambio,
        "debe_alertar": debe_alertar,
    }


def ejecutar_supersalud():
    """
    Procesa EPS, IPS y EMP.

    Devuelve una lista con los resultados de las categorías
    procesadas correctamente.
    """

    resultados = []

    for categoria in CATEGORIAS:
        try:
            resultado = procesar_categoria(
                categoria
            )

            if resultado is not None:
                resultados.append(resultado)

        except requests.RequestException as error:
            print("\n" + "!" * 70)
            print(
                f"ERROR DE CONEXIÓN EN {categoria}"
            )
            print(
                f"{type(error).__name__}: {error}"
            )
            print("!" * 70)

        except (
            ValueError,
            KeyError,
            TypeError,
            OSError,
        ) as error:
            print("\n" + "!" * 70)
            print(
                f"ERROR AL PROCESAR {categoria}"
            )
            print(
                f"{type(error).__name__}: {error}"
            )
            print("!" * 70)

    return resultados


if __name__ == "__main__":
    ejecutar_supersalud()