# dashboard_python/dashboard.py
from flask import Blueprint, render_template
from flask_login import login_required

from flask import jsonify, current_app
from sqlalchemy import text
from models import db

from Descifrado import desencriptar



dashboard_bp = Blueprint("dashboard_bp", __name__)

@dashboard_bp.get("/dashboard/fragment")
@login_required
def fragment():
    # Devuelve un FRAGMENTO (sin <html> completo)
    return render_template("dashboard_html/dashboard_fragment.html")


@dashboard_bp.get("/dashboard/api/docks/count")
def api_docks_count():
    try:
        row = db.session.execute(text("""
            SELECT
              COUNT(*) AS total,
              -- Docks en uso: solo los que NO están inactivos y su estado es 'ocupado'
              SUM(
                CASE 
                  WHEN status = 'inactivo' THEN 0
                  WHEN estado = 'ocupado' THEN 1
                  ELSE 0
                END
              ) AS en_uso,
              -- Docks con fallas: status = 'inactivo'
              SUM(CASE WHEN status = 'inactivo' THEN 1 ELSE 0 END) AS fallas,
              -- Usuarios bloqueados
              (SELECT COUNT(*) FROM bloqueados) AS bloqueados
            FROM dock
        """)).first()

        total       = int(row.total or 0)
        en_uso      = int(row.en_uso or 0)
        fallas      = int(row.fallas or 0)
        bloqueados  = int(row.bloqueados or 0)

        return jsonify({
            "total":      total,
            "en_uso":     en_uso,
            "fallas":     fallas,
            "bloqueados": bloqueados
        })
    except Exception as e:
        current_app.logger.exception("Error consultando COUNT(*) FROM dock/bloqueados")
        return jsonify({"error": "db_error"}), 500



#Para la lista de estados del dock
@dashboard_bp.get("/dashboard/api/docks/list")
def api_docks_list():
    try:
        rows = db.session.execute(text("""
            SELECT id, estado, sensor, scanner, status
            FROM dock
            ORDER BY id
        """)).mappings().all()

        # Convertimos cada fila a dict normal para jsonify
        docks = [dict(row) for row in rows]
        return jsonify({"docks": docks})
    except Exception as e:
        current_app.logger.exception("Error consultando lista de docks")
        return jsonify({"error": "db_error"}), 500


#endpoints historial
@dashboard_bp.get("/dashboard/api/historial/list")
def api_historial_list():
    try:
        # 1) ====== MAPA ALUMNOS: boleta_plana -> nombre ======
        alumnos_rows = db.session.execute(text("""
            SELECT boleta, nombre
            FROM alumnos
        """)).mappings().all()

        mapa_alumnos = {}
        for r in alumnos_rows:
            boleta_cifrada = r.get("boleta") or ""
            try:
                boleta_plana = desencriptar(boleta_cifrada)
                if boleta_plana:
                    mapa_alumnos[boleta_plana] = r.get("nombre") or ""
            except Exception:
                # Si algo viene mal cifrado, lo ignoramos
                continue

        # 2) ====== MAPA PROFESORES: numero_empleado_plano -> nombre ======
        profesores_rows = db.session.execute(text("""
            SELECT numero_empleado, nombre
            FROM profesores
        """)).mappings().all()

        mapa_profesores = {}
        for r in profesores_rows:
            num_emp_cifrado = r.get("numero_empleado") or ""
            try:
                num_emp_plano = desencriptar(num_emp_cifrado)
                if num_emp_plano:
                    mapa_profesores[num_emp_plano] = r.get("nombre") or ""
            except Exception:
                continue

        # 3) ====== LEEMOS HISTORIAL ======
        rows = db.session.execute(text("""
            SELECT
              id,
              dock,
              fecha,
              hora_entrada,
              hora_salida,
              tiempo_total,
              tipo,
              nombre,
              boleta,
              accion
            FROM historial
            ORDER BY id DESC
            LIMIT 100
        """)).mappings().all()

        items = []
        for row in rows:
            d = dict(row)
            tipo_lower = (d.get("tipo") or "").lower()

            # --- Alumno: usar nombre desde tabla alumnos según boleta ---
            if tipo_lower == "alumno":
                boleta_hist = d.get("boleta") or ""
                nombre_alumno = mapa_alumnos.get(boleta_hist)
                if nombre_alumno:
                    d["nombre"] = nombre_alumno

            # --- Profesor: usar nombre desde tabla profesores según numero_empleado ---
            elif tipo_lower == "profesor":
                # En historial.boleta también se guarda el número de empleado en texto plano
                num_emp_hist = d.get("boleta") or ""
                nombre_prof = mapa_profesores.get(num_emp_hist)
                if nombre_prof:
                    d["nombre"] = nombre_prof

            items.append(d)

        return jsonify({"items": items})
    except Exception as e:
        current_app.logger.exception("Error consultando historial")
        return jsonify({"error": "db_error"}), 500
