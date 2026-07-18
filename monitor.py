"""
Programa principal de la automatización.

Desde aquí se iniciará todo el proceso de monitoreo.
"""

from config import URL_SUPERSUBSIDIO


def main():
    print("=" * 50)
    print(" INICIANDO AUTOMATIZACIÓN")
    print("=" * 50)

    print("\nConfiguración cargada correctamente.")
    print(f"Página de Supersubsidio: {URL_SUPERSUBSIDIO}")

    print("\nProceso finalizado correctamente.")


if __name__ == "__main__":
    main()
