from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for
from config import Config
from models import Administrador, db
from mailer import send_mail_smtp
from token_reset import generar_token_reset

import jwt
import hashlib

olvido = Blueprint("olvido", __name__)

# ===============================
# MOSTRAR FORMULARIO DE RECUPERACIÓN
# ===============================
@olvido.get("/olvidar")
def mostrar_formulario():
    return render_template("olvidaste_contrasena.html")


# ===============================
# ENVIAR ENLACE DE RECUPERACIÓN (TOKEN)
# ===============================
@olvido.post("/olvidar")
def enviar_link_reset():
    correo = (request.form.get("correo") or "").strip().lower()

    if not correo:
        flash("Ingresa un correo.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    usuario = Administrador.query.filter(
        Administrador.correo_institucional == correo
    ).first()

    if not usuario:
        # Puedes hacer el mensaje más genérico si quieres no revelar si existe o no
        flash("No existe un usuario con ese correo.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    # Generar token con firma basada en contraseña actual
    token = generar_token_reset(
        usuario.correo_institucional,
        usuario.contrasena,
        current_app.config["SECRET_KEY"]
    )

    enlace = url_for("olvido.vista_reset", token=token, _external=True)

    # Construcción del correo
    html = f"""
        <p>Hola <b>{usuario.nombre}</b>,</p>
        <p>Haz clic en el siguiente enlace para restablecer tu contraseña:</p>
        <p><a href="{enlace}">{enlace}</a></p>
        <p>Este enlace es de un solo uso y expira en 15 minutos.</p>
    """

    texto_simple = f"""
Hola {usuario.nombre},

Restablece tu contraseña usando este enlace:

{enlace}

Este enlace dejará de funcionar cuando cambies tu contraseña o pasen 15 minutos.
    """

    try:
        send_mail_smtp(
            server=Config.SMTP_SERVER,
            port=Config.SMTP_PORT,
            user=Config.SMTP_USER,
            password=Config.SMTP_PASS,
            sender=Config.MAIL_SENDER,
            to=correo,
            subject="Restablecer contraseña - PoliBICI",
            html=html,
            text=texto_simple
        )
        flash("Si el correo existe, se envió un enlace para restablecer tu contraseña.", "ok")
    except Exception as e:
        flash(f"Error enviando correo: {e}", "error")

    return redirect(url_for("olvido.mostrar_formulario"))


# ===============================
# MOSTRAR FORMULARIO DE NUEVA CONTRASEÑA (GET)
# ===============================
@olvido.get("/olvidar/reset")
def vista_reset():
    token = request.args.get("token")

    if not token:
        flash("Enlace inválido.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    try:
        data = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
        correo = data["correo"]
        firma_token = data["firma"]
    except jwt.ExpiredSignatureError:
        flash("El enlace para restablecer ya expiró.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))
    except Exception:
        flash("Enlace inválido.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    usuario = Administrador.query.filter(
        Administrador.correo_institucional == correo
    ).first()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    # Firma actual basada en contraseña actual
    firma_actual = hashlib.sha256(usuario.contrasena.encode()).hexdigest()

    # Si las firmas no coinciden → token ya usado o contraseña ya cambió
    if firma_token != firma_actual:
        flash("Este enlace ya fue usado o ya no es válido.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    return render_template("reset_password.html", token=token)


# ===============================
# PROCESAR CAMBIO DE CONTRASEÑA (POST)
# ===============================
@olvido.post("/olvidar/reset")
def reset_password():
    token = request.form.get("token")
    nueva = request.form.get("password")

    if not nueva:
        flash("Ingresa una contraseña válida.", "error")
        return redirect(request.url)

    try:
        data = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
        correo = data["correo"]
        firma_token = data["firma"]
    except Exception:
        flash("Enlace inválido o expirado.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    usuario = Administrador.query.filter(
        Administrador.correo_institucional == correo
    ).first()

    if not usuario:
        flash("Usuario no encontrado.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    firma_actual = hashlib.sha256(usuario.contrasena.encode()).hexdigest()

    if firma_token != firma_actual:
        flash("Este enlace ya fue usado anteriormente.", "error")
        return redirect(url_for("olvido.mostrar_formulario"))

    # Guardar la nueva contraseña (hasheada)
    if hasattr(usuario, "set_password"):
        usuario.set_password(nueva)
    else:
        usuario.contrasena = nueva

    db.session.commit()

    flash("Tu contraseña fue actualizada exitosamente.", "ok")
    return redirect(url_for("login"))
