# dashboard_python/docks.py
from flask import Blueprint, render_template, jsonify, current_app, request
from flask_login import login_required
from sqlalchemy import text
from models import db

docks_bp = Blueprint("docks_bp", __name__)


@docks_bp.get("/docks/fragment")
@login_required
def fragment():
    # Devuelve un fragmento (sin <html> completo)
    return render_template("dashboard_html/docks_fragment.html")


@docks_bp.get("/docks/api/list")
@login_required
def api_docks_list():
    """
    Devuelve la lista de docks con todos los campos necesarios
    para el fragmento de Docks.
    """
    try:
        rows = db.session.execute(text("""
            SELECT
              id,
              estado,
              sensor,
              scanner,
              status,
              uso,
              inicio_uso,
              ultimo_uso,
              usuario,
              problema,
              reportado,
              zona,
              tecnico
            FROM dock
            ORDER BY id
        """)).mappings().all()

        docks = [dict(row) for row in rows]
        return jsonify({"docks": docks})
    except Exception:
        current_app.logger.exception("Error consultando docks")
        return jsonify({"error": "db_error"}), 500


@docks_bp.post("/docks/api/delete")
@login_required
def api_dock_delete():
    """
    Elimina un dock por id. Se usa al presionar la 'X' en la tarjeta
    de Disponible o Con falla.
    """
    data = request.get_json(silent=True) or {}
    dock_id = data.get("id")

    if not dock_id:
        return jsonify({"ok": False, "error": "missing_id"}), 400

    try:
        # Aseguramos que sea int
        dock_id = int(dock_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    try:
        db.session.execute(text("DELETE FROM dock WHERE id = :id"), {"id": dock_id})
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("Error eliminando dock")
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error"}), 500






# --- Reiniciar dock ---
@docks_bp.post("/docks/api/reiniciar")
@login_required
def api_dock_reiniciar():
    """
    Reinicia un dock usando los valores base del JSON en /reinicio_dock.
    Respeta 'uso' y 'ultimo_uso'.
    """
    import json
    import os
    from flask import current_app

    data = request.get_json(silent=True) or {}
    dock_id = data.get("id")

    if not dock_id:
        return jsonify({"ok": False, "error": "missing_id"}), 400

    try:
        dock_id = int(dock_id)
    except:
        return jsonify({"ok": False, "error": "invalid_id"}), 400

    # Ruta del JSON
    json_path = os.path.join(current_app.root_path, "reinicio_dock", "reinicio_default_dock.json")

    if not os.path.isfile(json_path):
        return jsonify({"ok": False, "error": "json_not_found"}), 500

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            defaults = json.load(f)
    except Exception as e:
        current_app.logger.exception("Error leyendo JSON de reinicio")
        return jsonify({"ok": False, "error": "json_read_error"}), 500

    # Leer uso y ultimo_uso actuales
    row = db.session.execute(
        text("SELECT uso, ultimo_uso FROM dock WHERE id = :id"),
        {"id": dock_id}
    ).mappings().first()

    if not row:
        return jsonify({"ok": False, "error": "dock_not_found"}), 404

    uso_actual = row["uso"]
    ultimo_actual = row["ultimo_uso"]

    # Aplicar valores del JSON, excepto uso y ultimo_uso
    try:
        db.session.execute(text("""
            UPDATE dock
            SET estado      = :estado,
                sensor      = :sensor,
                scanner     = :scanner,
                status      = :status,
                zona        = :zona,
                tecnico     = :tecnico,
                inicio_uso  = :inicio_uso,
                usuario     = :usuario,
                problema    = :problema,
                reportado   = :reportado,
                uso         = :uso_actual,
                ultimo_uso  = :ultimo_actual
            WHERE id = :id
        """), {
            "id": dock_id,
            "estado": defaults["estado"],
            "sensor": defaults["sensor"],
            "scanner": defaults["scanner"],
            "status": defaults["status"],
            "zona": defaults["zona"],
            "tecnico": defaults["tecnico"],
            "inicio_uso": defaults["inicio_uso"],
            "usuario": defaults["usuario"],
            "problema": defaults["problema"],
            "reportado": defaults["reportado"],
            "uso_actual": uso_actual,
            "ultimo_actual": ultimo_actual
        })

        db.session.commit()
        return jsonify({"ok": True})

    except Exception:
        current_app.logger.exception("Error reiniciando dock")
        db.session.rollback()
        return jsonify({"ok": False, "error": "db_error"}), 500
