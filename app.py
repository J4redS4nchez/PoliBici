import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from config import Config
from models import db, Administrador

# Blueprints
from olvidaste_contrasena import olvido
from panel_control import panel_control
from dashboard_python.dashboard import dashboard_bp
from dashboard_python.docks import docks_bp
from dashboard_python.usuarios import usuarios_bp
from dashboard_python.administrador import administrador_bp
from dashboard_python.estadisticas import estadisticas_bp
from dashboard_python.notificaciones import notificaciones_bp
from dashboard_python.notificaciones_cuadro import notificaciones_cuadro_bp



# ACEVEDO
# Flask-Mail (solo para pruebas /test-email)
from flask_mail import Mail, Message


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    # Extensiones
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Administrador, int(user_id))

    # Flask-Mail: inicialización y acceso global como app.mail
    mail = Mail(app)
    app.mail = mail

    # ---------- Rutas ----------
    @app.get("/")
    def root():
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            correo = (request.form.get("correo") or "").strip().lower()
            password = request.form.get("contrasena") or ""

            if not correo or not password:
                flash("Completa correo y contraseña.", "error")
                return redirect(url_for("login"))

            try:
                u = Administrador.query.filter(
                    Administrador.correo_institucional == correo
                ).first()
            except Exception as e:
                app.logger.exception("Error consultando la BD")
                flash(f"Error de base de datos: {e.__class__.__name__}", "error")
                return redirect(url_for("login"))

            # Compatibilidad: si existe u.check_password úsala; si no, compara texto plano
            valido = False
            if u:
                if hasattr(u, "check_password") and callable(u.check_password):
                    try:
                        valido = u.check_password(password)
                    except Exception:
                        valido = False
                else:
                    valido = (u.contrasena == password)

            if u and valido:
                try:
                    login_user(u)
                except Exception as e:
                    app.logger.exception("Error iniciando sesión")
                    flash(f"Error de sesión: {e}", "error")
                    return redirect(url_for("login"))

                flash(f"Bienvenido, {u.nombre or 'Administrador'}", "ok")
                # Redirige al blueprint panel_control
                return redirect(url_for("panel_control.mostrar_panel"))

            flash("Credenciales inválidas.", "error")
            return redirect(url_for("login"))

        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Sesión cerrada.", "ok")
        return redirect(url_for("login"))

    # Ruta de prueba para verificar Flask-Mail / SMTP
    @app.get("/test-email")
    def test_email():
        try:
            msg = Message(
                subject="Prueba PoliBICI - SMTP funcionando",
                recipients=[Config.MAIL_USERNAME],
            )
            msg.body = (
                "Este es un correo de prueba enviado desde tu servidor PoliBICI "
                "usando Flask-Mail."
            )

            app.mail.send(msg)

            return f"Correo enviado correctamente a {Config.MAIL_USERNAME}"

        except Exception as e:
            return f"Error enviando correo: {e}"

    # ---------- Blueprints ----------
    app.register_blueprint(olvido)          # /olvidaste-contrasena
    app.register_blueprint(panel_control)   # /panel
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(docks_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(administrador_bp)
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(notificaciones_bp)
    app.register_blueprint(notificaciones_cuadro_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
