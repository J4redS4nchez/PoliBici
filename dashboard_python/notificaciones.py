# dashboard_python/notificaciones.py
from flask import Blueprint, render_template
from flask_login import login_required

notificaciones_bp = Blueprint("notificaciones_bp", __name__)

@notificaciones_bp.get("/notificaciones/fragment")
@login_required
def fragment():
    return render_template("dashboard_html/notificaciones_fragment.html")
