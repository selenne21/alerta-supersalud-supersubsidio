"""
Monitor principal de publicaciones.

Ejecuta en un solo proceso:

1. Supersubsidio - Información Poblacional.
2. Supersalud - EPS.
3. Supersalud - IPS.
4. Supersalud - EMP.
5. Envía correo solo si detecta cambios.
"""

from correo import enviar_correo
from supersalud import ejecutar_supersalud
from supersubsidio import ejecutar_supersubsidio


def ejecutar_monitor():
    """
    Ejecuta todos los monitores del proyecto,
    reúne los resultados y envía correo
    cuando hay archivos nuevos o actualizados.
    """

    print("\n" + "#" * 70)
    print("INICIO DEL MONITOR")
    print("#" * 70)

    resultados = []

    print("\nRevisando Supersubsidio...")

    try:
        resultado_supersubsidio = ejecutar_supersubsidio()

        if resultado_supersubsidio is not None:
            resultados.append(resultado_supersubsidio)

    except Exception as error:
        print("\n" + "!" * 70)
        print("ERROR GENERAL EN SUPERSUBSIDIO")
        print(f"{type(error).__name__}: {error}")
        print("!" * 70)

    print("\nRevisando Supersalud...")

    try:
        resultados_supersalud = ejecutar_supersalud()

        if resultados_supersalud:
            resultados.extend(resultados_supersalud)

    except Exception as error:
        print("\n" + "!" * 70)
        print("ERROR GENERAL EN SUPERSALUD")
        print(f"{type(error).__name__}: {error}")
        print("!" * 70)

    resultados_para_alerta = [
        resultado
        for resultado in resultados
        if resultado.get("debe_alertar", False)
    ]

    print("\n" + "-" * 70)
    print("RESUMEN DE ALERTAS")
    print("-" * 70)

    if resultados_para_alerta:
        print(
            f"Se detectaron "
            f"{len(resultados_para_alerta)} "
            f"archivo(s) nuevo(s) o actualizado(s)."
        )

        for resultado in resultados_para_alerta:
            print(
                f"- {resultado['entidad']} "
                f"{resultado.get('categoria', '')}: "
                f"{resultado['estado_cambio']}"
            )

        try:
            enviar_correo(resultados_para_alerta)

        except Exception as error:
            print("\n" + "!" * 70)
            print("ERROR AL ENVIAR EL CORREO")
            print(f"{type(error).__name__}: {error}")
            print("!" * 70)

    else:
        print(
            "No se detectaron archivos nuevos o actualizados."
        )
        print("No se enviará correo.")

    print("\n" + "#" * 70)
    print("FIN DEL MONITOR")
    print("#" * 70)


if __name__ == "__main__":
    ejecutar_monitor()