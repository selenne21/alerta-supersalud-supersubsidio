"""
Funciones para consultar y descargar los archivos financieros
publicados por la Superintendencia Nacional de Salud.

Categorías vigiladas:

1. EPS.
2. IPS privadas.
3. Entidades de Medicina Prepagada y SAP.

Criterio de selección:

1. Periodo más reciente indicado en el título.
2. Fecha de creación más reciente.
3. Fecha de modificación más reciente.
4. Comparación del hash SHA-256 para detectar cambios reales.
"""
#Vamos a usar el servicio  API REST que ya ofrece ArcGIS de Supersalud.
from datetime import datetime #Convierte las fechas que entrega ArcGIS a fechas entendibles
from pathlib import Path #Manejar la carpeta descargas y las rutas de los Excel
import hashlib #Calcula el id unico
import re #Buscar patrones dentro de los títulos
import unicodedata # Quitar tildes/normalizar texto

import requests #Comunicarnos con ArcGIS por internet

from estado import cargar_estado, guardar_estado #Aca se guarda el ultimo registro para recordar lo ultimo que visualizo

#Convierte en variables donde se busca el archivo y donde se descarga
URL_BUSCADOR = (
    "https://mapas.supersalud.gov.co/"
    "arcgisportal/sharing/rest/search"
)

URL_DESCARGA_BASE = (
    "https://mapas.supersalud.gov.co/"
    "arcgisportal/sharing/rest/content/items"
)
#Los excel que encontremos se descargaran aca
CARPETA_DESCARGAS = Path("descargas")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
}
#Aca le estamos dando la categoria de lo que debe revisar
CATEGORIAS = ("EPS", "IPS", "EMP")

#Como estas plataformas publican mucha información vamos a generarle un patron de la información que queremos traer ( riesgo que cambie sustancialmente los nombres y no se reconozcan)
# Los patrones se escriben sin tildes porque los títulos
# se normalizan antes de compararlos.
PATRONES = {
    "EPS": [
        (
            "catalogo de informacion financiera eps del regimen "
            "contributivo y subsidiado"
        ),
    ],
    "IPS": [
        (
            "catalogo de informacion financiera de las instituciones "
            "prestadoras de servicios de salud (ips) privadas"
        ),
        "catalogo de informacion financiera de las ips privadas",
        "catalogo de informacion financiera ips privadas",
    ],
    "EMP": [
        (
            "catalogo de informacion financiera de entidades de medicina "
            "prepagada (emp) y servicios de ambulancia prepagada (sap)"
        ),
        (
            "catalogo de informacion financiera de entidades de medicina "
            "prepagada (emp) y sap"
        ),
        (
            "catalogo de informacion financiera de entidades de medicina "
            "prepagada"
        ),
    ],
}

#Se hace para que el programa lea los meses y pueda comparalos
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


TRIMESTRES = {
    "primer": 3,
    "primero": 3,
    "segundo": 6,
    "tercer": 9,
    "tercero": 9,
    "cuarto": 12,
}

#Se hace lo mismo con los trimestres
SEMESTRES = {
    "primer": 6,
    "primero": 6,
    "segundo": 12,
}


def normalizar_texto(texto):
    """
    Convierte el texto a minúsculas, elimina tildes
    y reemplaza algunos separadores por espacios.
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
        r"[_–—\-]+",
        " ",
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()

#Arregla la fecha
def convertir_fecha(fecha_milisegundos):
    """
    Convierte la fecha interna de ArcGIS
    a un formato legible.
    """

    if not fecha_milisegundos:
        return "Fecha no disponible"

    fecha = datetime.fromtimestamp(
        fecha_milisegundos / 1000
    )

    return fecha.strftime("%Y-%m-%d %H:%M:%S")

#Revisa si el título que devolvió ArcGIS realmente corresponde a la categoría que estamos buscando.
def titulo_valido(categoria, titulo):
    """
    Comprueba que el título pertenezca a la serie correcta
    de EPS, IPS o EMP.
    """
#Aca va a lanzar un error si esa categoria no esta en el codigo
    if categoria not in PATRONES:
        raise ValueError(
            f"La categoría {categoria} no está configurada."
        )

    titulo_normalizado = normalizar_texto(titulo)
#Revisa si los nombres de los archivos coinciden con los patrones que le suministramos en cada categoria
    return any(
        patron in titulo_normalizado
        for patron in PATRONES[categoria]
    )


def extraer_periodo(titulo):
    """
    Extrae el periodo financiero indicado en el título.

    Reconoce:

    - Mes y año: mayo 2026.
    - Trimestre y año: primer trimestre 2026.
    - Semestre y año: segundo semestre 2025.

    Devuelve un diccionario con:

    - anio
    - mes_final
    - texto
    - clave

    La clave se utiliza para comparar periodos.
    """

    titulo_normalizado = normalizar_texto(titulo)
#Prepara los meses para buscarlos
    nombres_meses = "|".join(
        re.escape(mes)
        for mes in MESES
    )
# Eso crea una regla de búsqueda/ “mayo 2026”, “junio 2026”, “diciembre 2025”,
    patron_mes = re.compile(
        rf"\b({nombres_meses})\b"
        rf"(?:\s+de)?\s+"
        rf"(20\d{{2}})\b"
    )
# Busca todas las coincidencias de mes y año en el título
    coincidencias_mes = list(
        patron_mes.finditer(titulo_normalizado)
    )
#Toma la última coincidencia encontrada
    if coincidencias_mes:
        coincidencia = coincidencias_mes[-1]

        nombre_mes = coincidencia.group(1)
        anio = int(coincidencia.group(2))
        numero_mes = MESES[nombre_mes]

        return {
            "anio": anio,
            "mes_final": numero_mes,
            "texto": f"{nombre_mes} {anio}",
            "clave": (anio, numero_mes), #esta clave nos va a ayudar a despues ordenar y comparar fechas
            "tipo": "mes",
        }
# si no encuentra mes sigue con trimestre 
    patron_trimestre = re.compile(
        r"\b(primer|primero|segundo|tercer|tercero|cuarto)"
        r"\s+trimestre"
        r"(?:\s+de)?\s+"
        r"(20\d{2})\b"
    )

    coincidencia_trimestre = patron_trimestre.search(
        titulo_normalizado
    )

    if coincidencia_trimestre:
        nombre_trimestre = coincidencia_trimestre.group(1)
        anio = int(
            coincidencia_trimestre.group(2)
        )

        mes_final = TRIMESTRES[
            nombre_trimestre
        ]

        return {
            "anio": anio,
            "mes_final": mes_final,
            "texto": (
                f"{nombre_trimestre} trimestre "
                f"{anio}"
            ),
            "clave": (anio, mes_final),
            "tipo": "trimestre",
        }
# continua con semestre
    patron_semestre = re.compile(
        r"\b(primer|primero|segundo)"
        r"\s+semestre"
        r"(?:\s+de)?\s+"
        r"(20\d{2})\b"
    )

    coincidencia_semestre = patron_semestre.search(
        titulo_normalizado
    )

    if coincidencia_semestre:
        nombre_semestre = coincidencia_semestre.group(1)
        anio = int(
            coincidencia_semestre.group(2)
        )

        mes_final = SEMESTRES[
            nombre_semestre
        ]

        return {
            "anio": anio,
            "mes_final": mes_final,
            "texto": (
                f"{nombre_semestre} semestre "
                f"{anio}"
            ),
            "clave": (anio, mes_final),
            "tipo": "semestre",
        }
# si no encuentra por nunguna de las tres
    return None
#Aca aun no hemos decidido cual es el mas reciente solo estamos ordenando para que mas adelante podamos comparar
##################################################################################
def calcular_hash(ruta_archivo):
    """
    Calcula la huella SHA-256 del archivo descargado.
    """

    hash_sha256 = hashlib.sha256()
#Abrimos y leemos el contenido para calcular el id
    with open(ruta_archivo, "rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(8192),
            b"",
        ):
            hash_sha256.update(bloque)

    return hash_sha256.hexdigest()

###############################En este momento si vamos a consultar##########################
def consultar_resultados_arcgis(categoria):
    """
    Consulta todos los resultados disponibles en ArcGIS
    para una categoría.

    ArcGIS devuelve máximo 100 resultados por página,
    por eso la consulta utiliza paginación.
    """
#Aca vamos a poner los resultados
    resultados_totales = []
    inicio = 1
    cantidad_por_pagina = 100
#Va a consultar ArcGIS por grupos de hasta 100 resultados, empezando desde el primero, y seguiré consultando mientras haya más.
    while True:
        parametros = {
            "f": "json", #Forma de ordenar los datos
            "q": categoria, # busca entre las categorias que necesitabamos
            "sortField": "created",#Se ordenan los datos segun su fecha de creación
            "sortOrder": "desc",
            "num": cantidad_por_pagina,
            "start": inicio,
        }
#Estamos haciendo una solicitud de busqueda (Manda la solicitud al buscador de la API REST de ArcGIS de Supersalud)
        respuesta = requests.get(
            URL_BUSCADOR,
            params=parametros,
            headers=HEADERS,
            timeout=60,
        )

        respuesta.raise_for_status()
#Convertimos la respuesta segun JSON
        datos = respuesta.json()
# si no exiten resultados dame una lista vacia
        resultados_pagina = datos.get(
            "results",
            [],
        )

        resultados_totales.extend(
            resultados_pagina
        )
#Si todavia hay resultados extiende la busqueda
        siguiente_inicio = datos.get(
            "nextStart",
            -1,
        )

        if (
            siguiente_inicio in (-1, None)
            or not resultados_pagina
        ):
            break #Aca ya no sigue preguntando

        inicio = siguiente_inicio

    return resultados_totales

#Vamos a empezar a ordenarlo al mas reciente
def buscar_archivo_mas_reciente(categoria):
    """
    Busca los Excel válidos de una categoría.

    Orden de prioridad:

    1. Periodo financiero más reciente del título.
    2. Fecha de creación más reciente.
    3. Fecha de modificación más reciente.
    """

    resultados_arcgis = consultar_resultados_arcgis(
        categoria
    )

    candidatos = []

    for resultado in resultados_arcgis:
        titulo = resultado.get(
            "title",
            "",
        )

        tipo = resultado.get(
            "type",
            "",
        )

        identificador = resultado.get(
            "id",
            "",
        )

        fecha_creacion = resultado.get(
            "created",
            0,
        )

        fecha_modificacion = resultado.get(
            "modified",
            0,
        )
#Filtra por si no es un candidato ni cumple los requisitos que necesitamos le dice que continue
        if not identificador:
            continue

        if "excel" not in tipo.lower():
            continue

        if not titulo_valido(
            categoria,
            titulo,
        ):
            continue

        periodo = extraer_periodo(titulo)

        candidatos.append(
            {
                "titulo": titulo,
                "tipo": tipo,
                "id": identificador,
                "created": fecha_creacion,
                "modified": fecha_modificacion,
                "periodo": periodo,
            }
        )

    if not candidatos:
        return None

    candidatos_con_periodo = [
        candidato
        for candidato in candidatos
        if candidato["periodo"] is not None
    ]

    if candidatos_con_periodo:
        candidatos_con_periodo.sort(
            key=lambda archivo: (
                archivo["periodo"]["clave"],
                archivo["created"],
                archivo["modified"],
            ),
            reverse=True,
        )

        return candidatos_con_periodo[0]

    print(
        "\nADVERTENCIA: no se pudo identificar "
        f"el periodo en los títulos de {categoria}."
    )

    print(
        "Se utilizarán las fechas de creación "
        "y modificación como criterio alternativo."
    )

    candidatos.sort(
        key=lambda archivo: (
            archivo["created"],
            archivo["modified"],
        ),
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
            estado["supersalud"][categoria] = {}

        estado["supersalud"][categoria].setdefault(
            "id",
            "",
        )

        estado["supersalud"][categoria].setdefault(
            "hash",
            "",
        )

        estado["supersalud"][categoria].setdefault(
            "periodo",
            "",
        )

        estado["supersalud"][categoria].setdefault(
            "created",
            0,
        )

        estado["supersalud"][categoria].setdefault(
            "modified",
            0,
        )

        estado["supersalud"][categoria].setdefault(
            "titulo",
            "",
        )

    return estado


def determinar_estado_cambio(
    id_anterior,
    hash_anterior,
    periodo_anterior,
    id_actual,
    hash_actual,
    periodo_actual,
):
    """
    Compara la publicación actual con el estado anterior.
    """

    if not id_anterior:
        return "NUEVO ARCHIVO REGISTRADO"

    if (
        periodo_anterior
        and periodo_actual
        and periodo_anterior != periodo_actual
    ):
        return "NUEVA PUBLICACIÓN"

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

    fecha_creacion_legible = convertir_fecha(
        resultado["created"]
    )

    fecha_modificacion_legible = convertir_fecha(
        resultado["modified"]
    )

    periodo = resultado.get(
        "periodo"
    )

    periodo_texto = (
        periodo["texto"]
        if periodo
        else "Periodo no identificado"
    )

    periodo_clave = (
        f"{periodo['anio']}-"
        f"{periodo['mes_final']:02d}"
        if periodo
        else ""
    )

    print(f"Título: {resultado['titulo']}")
    print(f"ID: {resultado['id']}")
    print(f"Periodo detectado: {periodo_texto}")

    print(
        "Fecha de creación: "
        f"{fecha_creacion_legible}"
    )

    print(
        "Fecha de modificación: "
        f"{fecha_modificacion_legible}"
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

    periodo_anterior = estado_anterior.get(
        "periodo",
        "",
    )

    estado_cambio = determinar_estado_cambio(
        id_anterior=id_anterior,
        hash_anterior=hash_anterior,
        periodo_anterior=periodo_anterior,
        id_actual=resultado["id"],
        hash_actual=hash_archivo,
        periodo_actual=periodo_clave,
    )

    print(f"\n{estado_cambio}")

    estado["supersalud"][categoria] = {
        "id": resultado["id"],
        "hash": hash_archivo,
        "periodo": periodo_clave,
        "created": resultado["created"],
        "modified": resultado["modified"],
        "titulo": resultado["titulo"],
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
        "periodo": periodo_texto,
        "periodo_clave": periodo_clave,
        "fecha_creacion": fecha_creacion_legible,
        "fecha_actualizacion": fecha_modificacion_legible,
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