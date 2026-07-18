"""
Módulo encargado de enviar correos electrónicos
cuando se detectan archivos nuevos o actualizados.

Los archivos pequeños se adjuntan.
Los archivos demasiado grandes se notifican mediante
su enlace directo de descarga.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


# Se utiliza un límite menor al de Gmail porque los adjuntos
# aumentan de tamaño durante la codificación del correo.
LIMITE_ADJUNTO_BYTES = 17 * 1024 * 1024


def obtener_configuracion_correo():
    """
    Lee la configuración del correo desde variables de entorno.
    """

    configuracion = {
        "servidor": os.getenv("SMTP_SERVIDOR", ""),
        "puerto": os.getenv("SMTP_PUERTO", ""),
        "usuario": os.getenv("CORREO_USUARIO", ""),
        "contrasena": os.getenv("CORREO_CONTRASENA", ""),
        "destinatario": os.getenv("CORREO_DESTINATARIO", ""),
    }

    faltantes = [
        nombre
        for nombre, valor in configuracion.items()
        if not valor
    ]

    if faltantes:
        raise ValueError(
            "Faltan variables de entorno para el correo: "
            + ", ".join(faltantes)
        )

    try:
        configuracion["puerto"] = int(
            configuracion["puerto"]
        )
    except ValueError as error:
        raise ValueError(
            "SMTP_PUERTO debe ser un número entero."
        ) from error

    return configuracion


def obtener_destinatarios(destinatario):
    """
    Convierte una cadena de uno o varios correos
    separados por comas en una lista.
    """

    destinatarios = [
        correo.strip()
        for correo in destinatario.split(",")
        if correo.strip()
    ]

    if not destinatarios:
        raise ValueError(
            "No se encontró ningún correo destinatario válido."
        )

    return destinatarios


def crear_mensaje(resultado, configuracion):
    """
    Crea un correo para una sola alerta.

    Adjunta el archivo cuando cumple el límite de tamaño.
    Cuando no puede adjuntarse, incluye el enlace de descarga.
    """

    mensaje = EmailMessage()

    entidad = resultado.get(
        "entidad",
        "Entidad no disponible",
    )

    categoria = resultado.get(
        "categoria",
        "",
    )

    nombre = resultado.get(
        "nombre",
        "Nombre no disponible",
    )

    estado_cambio = resultado.get(
        "estado_cambio",
        "Cambio detectado",
    )

    fecha = resultado.get(
        "fecha_actualizacion",
        "Fecha no disponible",
    )

    url = resultado.get(
        "url",
        "URL no disponible",
    )

    encabezado = entidad

    if categoria:
        encabezado += f" - {categoria}"

    destinatarios = obtener_destinatarios(
        configuracion["destinatario"]
    )

    mensaje["From"] = configuracion["usuario"]
    mensaje["To"] = ", ".join(destinatarios)
    mensaje["Subject"] = (
        f"Alerta de nueva información: {encabezado}"
    )

    ruta = None
    archivo_adjuntado = False
    motivo_sin_adjunto = ""

    ruta_resultado = resultado.get("ruta")

    if ruta_resultado:
        ruta = Path(ruta_resultado)

        if not ruta.exists():
            motivo_sin_adjunto = (
                "El archivo no se encontró en la carpeta local."
            )

        elif ruta.stat().st_size > LIMITE_ADJUNTO_BYTES:
            tamano_mb = ruta.stat().st_size / (1024 * 1024)

            motivo_sin_adjunto = (
                f"El archivo pesa aproximadamente "
                f"{tamano_mb:.2f} MB y supera el límite "
                f"seguro para adjuntos."
            )

        else:
            archivo_adjuntado = True

    else:
        motivo_sin_adjunto = (
            "El monitor no proporcionó una ruta local."
        )

    lineas = [
        "Hola,",
        "",
        "El monitor detectó información nueva o actualizada.",
        "",
        f"Entidad: {encabezado}",
        f"Estado: {estado_cambio}",
        f"Archivo: {nombre}",
        f"Fecha de actualización: {fecha}",
        f"Enlace de descarga: {url}",
        "",
        "-" * 60,
        "",
    ]

    if archivo_adjuntado:
        lineas.extend(
            [
                "El archivo se encuentra adjunto a este correo.",
                "",
            ]
        )
    else:
        lineas.extend(
            [
                "El archivo no se adjuntó.",
                f"Motivo: {motivo_sin_adjunto}",
                "",
                "Puede descargarlo desde este enlace:",
                url,
                "",
            ]
        )

    lineas.append(
        "Mensaje generado automáticamente."
    )

    mensaje.set_content("\n".join(lineas))

    if archivo_adjuntado and ruta is not None:
        contenido = ruta.read_bytes()

        mensaje.add_attachment(
            contenido,
            maintype="application",
            subtype=(
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            filename=ruta.name,
        )

    return mensaje, archivo_adjuntado


def enviar_mensaje(mensaje, configuracion):
    """
    Envía un mensaje mediante el servidor SMTP.
    """

    with smtplib.SMTP(
        configuracion["servidor"],
        configuracion["puerto"],
        timeout=60,
    ) as servidor:
        servidor.ehlo()
        servidor.starttls()
        servidor.ehlo()

        servidor.login(
            configuracion["usuario"],
            configuracion["contrasena"],
        )

        servidor.send_message(mensaje)


def enviar_correo(resultados):
    """
    Envía un correo independiente por cada alerta.

    Así se evita que varios archivos adjuntos juntos
    superen el límite de tamaño de Gmail.
    """

    if not resultados:
        print(
            "\nNo hay archivos nuevos o actualizados. "
            "No se enviará correo."
        )
        return False

    configuracion = obtener_configuracion_correo()

    correos_enviados = 0
    errores = []

    for resultado in resultados:
        entidad = resultado.get(
            "entidad",
            "Entidad no disponible",
        )

        categoria = resultado.get(
            "categoria",
            "",
        )

        identificador = entidad

        if categoria:
            identificador += f" - {categoria}"

        try:
            mensaje, archivo_adjuntado = crear_mensaje(
                resultado,
                configuracion,
            )

            print(
                f"\nConectando con el servidor de correo "
                f"para {identificador}..."
            )

            enviar_mensaje(
                mensaje,
                configuracion,
            )

            if archivo_adjuntado:
                print(
                    f"Correo enviado correctamente con adjunto: "
                    f"{identificador}"
                )
            else:
                print(
                    f"Correo enviado correctamente con enlace: "
                    f"{identificador}"
                )

            correos_enviados += 1

        except Exception as error:
            errores.append(
                {
                    "identificador": identificador,
                    "tipo": type(error).__name__,
                    "mensaje": str(error),
                }
            )

            print(
                f"No se pudo enviar el correo de "
                f"{identificador}."
            )
            print(
                f"{type(error).__name__}: {error}"
            )

    print("\n" + "-" * 70)
    print("RESUMEN DEL ENVÍO DE CORREOS")
    print("-" * 70)
    print(f"Correos enviados: {correos_enviados}")
    print(f"Errores: {len(errores)}")

    if errores:
        for error in errores:
            print(
                f"- {error['identificador']}: "
                f"{error['tipo']} - {error['mensaje']}"
            )

    return correos_enviados > 0