import json
from pathlib import Path

ARCHIVO_ESTADO = Path("estado.json")
# Este archivo permite leer el estado anterior
# y guardar el nuevo estado en estado.json.
def cargar_estado():
    """
    Lee estado.json.
    Si no existe, crea una estructura vacía.
    """

    if not ARCHIVO_ESTADO.exists():
        return {
            "supersubsidio": {
                "url": "",
                "hash": ""
            },
            "supersalud": {
                "EPS": {
                    "id": "",
                    "hash": ""
                },
                "IPS": {
                    "id": "",
                    "hash": ""
                },
                "EMP": {
                    "id": "",
                    "hash": ""
                }
            }
        }

    with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_estado(estado):
    """
    Guarda el estado actualizado.
    """

    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as archivo:
        json.dump(
            estado,
            archivo,
            indent=4,
            ensure_ascii=False
        )