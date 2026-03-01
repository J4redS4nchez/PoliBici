# dashboard_python/notificaciones_cuadro.py
from flask import Blueprint, render_template, jsonify, current_app, request
from flask_login import login_required
from sqlalchemy import text
from datetime import datetime, date, time

from models import db

notificaciones_cuadro_bp = Blueprint("notificaciones_cuadro_bp", __name__)

# --- Helpers ---------------------------------------------------------------

def _parse_datetime(fecha_str, hora_str):
    """Convierte 'YYYY-MM-DD' y 'HH:MM' (o HH:MM:SS) en datetime. Devuelve None si falla."""
    try:
        if not fecha_str:
            return None
        f = date.fromisoformat(str(fecha_str))

        if hora_str:
            partes = str(hora_str).split(":")
            hh = int(partes[0])
            mm = int(partes[1]) if len(partes) > 1 else 0
            ss = int(partes[2]) if len(partes) > 2 else 0
            h = time(hour=hh, minute=mm, second=ss)
        else:
            h = time(0, 0)

        return datetime.combine(f, h)
    except Exception:
        return None


from datetime import datetime

def _tiempo_relativo(fecha_str, hora_str):
    """
    Devuelve un texto tipo:
      - "Hace 3 minutos"
      - "Hace 1 hr"
      - "Hace 5 hrs"
      - "Hace 1 día"
      - "Hace 3 días"
      - o "dd/mm/aaaa" si han pasado 7 días o más
    """
    dt = _parse_datetime(fecha_str, hora_str)
    if dt is None:
        return ""

    ahora = datetime.now()
    delta = ahora - dt

    # Si está en el futuro pero menos de 1 día de diferencia,
    # lo tratamos como pasado (para evitar el bug de mostrar solo la fecha)
    if delta.total_seconds() < 0 and delta.total_seconds() > -86400:
        delta = -delta
    # Si está MUY en el futuro (más de 1 día), mostramos fecha fija
    elif delta.total_seconds() <= -86400:
        return dt.strftime("%d/%m/%Y")

    dias = delta.days
    segundos = delta.seconds
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60

    # Más de 7 días → solo fecha
    if dias >= 7:
        return dt.strftime("%d/%m/%Y")

    if dias >= 2:
        return f"Hace {dias} días"
    if dias == 1:
        return "Hace 1 día"

    if horas >= 2:
        return f"Hace {horas} hrs"
    if horas == 1:
        return "Hace 1 hr"

    if minutos <= 1:
        return "Hace 1 minuto"
    return f"Hace {minutos} minutos"



def _obtener_notificaciones():
    """Lee las últimas notificaciones y agrega el campo tiempo_relativo."""
    try:
        rows = db.session.execute(text(
            """
            SELECT id, actor, notificacion, fecha, hora, motivo, riesgo, leida
            FROM notificaciones
            ORDER BY id DESC
            LIMIT 50
            """
        )).mappings().all()
    except Exception:
        current_app.logger.exception("Error consultando notificaciones")
        return []

    notifs = []
    for r in rows:
        notifs.append({
            "id": r["id"],
            "actor": r.get("actor"),
            "notificacion": r.get("notificacion"),
            "fecha": r.get("fecha"),
            "hora": r.get("hora"),
            "motivo": r.get("motivo"),
            "riesgo": r.get("riesgo"),
            "leida": int(r.get("leida") or 0),
            "tiempo_relativo": _tiempo_relativo(r.get("fecha"), r.get("hora")),
        })
    return notifs


# --- Rutas HTML ------------------------------------------------------------

@notificaciones_cuadro_bp.get("/notificaciones/cuadro")
@login_required
def cuadro():
    """Devuelve el HTML del cuadro flotante con las notificaciones actuales."""
    notifs = _obtener_notificaciones()
    return render_template(
        "dashboard_html/notificaciones_cuadro.html",
        notificaciones=notifs,
    )


# --- APIs para AJAX --------------------------------------------------------

@notificaciones_cuadro_bp.get("/notificaciones/cuadro/api/list")
@login_required
def api_list():
    """JSON con las notificaciones para refrescar el cuadro en tiempo real."""
    notifs = _obtener_notificaciones()
    return jsonify({"items": notifs})



@notificaciones_cuadro_bp.get("/notificaciones/cuadro/api/unread-count")
@login_required
def api_unread_count():
    """
    Devuelve el número de notificaciones NO leídas (leida = 0)
    para mostrarlo en la campanita.
    """
    try:
        # COUNT(*) de las que leida = 0
        result = db.session.execute(
            text("SELECT COUNT(*) AS c FROM notificaciones WHERE leida = 0")
        )
        count = result.scalar() or 0
        return jsonify({"ok": True, "count": int(count)})
    except Exception:
        current_app.logger.exception("Error contando notificaciones no leídas")
        return jsonify({"ok": False, "count": 0}), 500




@notificaciones_cuadro_bp.post("/notificaciones/cuadro/api/marcar-leida")
@login_required
def marcar_leida():
    """Marca una notificación como leída (leida = 1)."""
    data = request.get_json(silent=True) or {}
    try:
        notif_id = int(data.get("id", 0))
    except (TypeError, ValueError):
        notif_id = 0

    if not notif_id:
        return jsonify({"ok": False, "error": "missing_id"}), 400

    try:
        db.session.execute(
            text("UPDATE notificaciones SET leida = 1 WHERE id = :id"),
            {"id": notif_id},
        )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error marcando notificación como leída")
        return jsonify({"ok": False, "error": "db_error"}), 500





@notificaciones_cuadro_bp.post("/notificaciones/cuadro/api/marcar-todas")
@login_required
def marcar_todas():
    """Marca TODAS las notificaciones como leídas (leida = 1)."""
    try:
        db.session.execute(
            text("UPDATE notificaciones SET leida = 1")
        )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error marcando todas como leídas")
        return jsonify({"ok": False, "error": "db_error"}), 500




@notificaciones_cuadro_bp.post("/notificaciones/cuadro/api/eliminar-todas")
@login_required
def eliminar_todas():
    """Elimina TODAS las notificaciones y reinicia el ID."""
    try:
        db.session.execute(text("TRUNCATE TABLE notificaciones"))
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error eliminando todas las notificaciones")
        return jsonify({"ok": False, "error": "db_error"}), 500
