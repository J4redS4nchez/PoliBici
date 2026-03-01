from datetime import datetime, date

from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required
from sqlalchemy import text

from app import db
from Descifrado import desencriptar
from Cifrado import encriptar

import os
import json
import shutil




administrador_bp = Blueprint("administrador_bp", __name__)


def intentar_desencriptar(valor):
    """
    Intenta descifrar 'valor' usando desencriptar().
    Si falla o es vacío/None, regresa el mismo valor (o cadena vacía).
    """
    if not valor:
        return ""
    try:
        return desencriptar(valor)
    except Exception:
        # Si ocurre cualquier problema, regresamos el valor original
        return valor


def formatear_ultimo_acceso(valor):
    """
    Recibe una cadena con formato 'YYYY-M-D,HH-MM-SS' y devuelve:
      - "Hoy a las HH:MM hrs"   si es la fecha actual
      - "Ayer a las HH:MM hrs"  si fue el día anterior
      - "dd/mm/aaaa"            en cualquier otro caso
    Si no se puede parsear, regresa el valor original.
    """
    if not valor:
        return ""

    try:
        fecha_str, hora_str = valor.split(",")
        anio, mes, dia = map(int, fecha_str.split("-"))
        fecha = date(anio, mes, dia)

        hoy = date.today()
        if fecha == hoy:
            # Hoy
            hh, mm, *_ = hora_str.split("-")
            return f"Hoy a las {hh}:{mm} hrs"
        elif (hoy - fecha).days == 1:
            # Ayer
            hh, mm, *_ = hora_str.split("-")
            return f"Ayer a las {hh}:{mm} hrs"
        else:
            # Fecha pasada
            return f"{dia:02d}/{mes:02d}/{anio}"
    except Exception:
        return valor


@administrador_bp.route("/administrador/fragment")
@login_required
def fragment():
    """
    Devuelve el fragmento HTML para la vista de Administrador.
    """
    # Obtenemos todos los administradores directamente con SQL
    query = text("""
        SELECT id,
               no_empleado,
               nombre,
               apellido,
               correo_institucional,
               telefono,
               contrasena,
               ultimo_acceso
        FROM administrador
        ORDER BY id DESC
    """)

    with db.engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    from models import Administrador  # Import local para evitar ciclos

    administradores = []
    for r in rows:
        admin = Administrador()
        admin.id = r["id"]
        admin.no_empleado = intentar_desencriptar(r["no_empleado"])
        admin.nombre = r["nombre"]
        admin.apellido = r["apellido"]
        admin.correo_institucional = r["correo_institucional"]

        # Teléfono descifrado (para mostrarlo)
        admin.telefono_plano = intentar_desencriptar(r["telefono"])

        # Contraseña descifrada (solo se usa para validaciones / peticiones específicas)
        admin.contrasena_plana = intentar_desencriptar(r["contrasena"])

        # Último acceso formateado
        admin.ultimo_acceso_formateado = formatear_ultimo_acceso(r["ultimo_acceso"])

        administradores.append(admin)

    return render_template("dashboard_html/administrador_fragment.html",
                           administradores=administradores)


@administrador_bp.route("/administrador/api/validar_contrasena", methods=["POST"])
@login_required
def api_validar_contrasena():
    """
    Valida la contraseña de un administrador.
    Ahora la contraseña se compara tal cual está guardada en la BD (sin descifrar).
    """
    if not request.is_json:
        return jsonify(ok=False, error="Solicitud inválida"), 400

    data = request.get_json(silent=True) or {}
    admin_id = data.get("admin_id")
    contrasena_ingresada = (data.get("contrasena") or "").strip()

    if not admin_id or not contrasena_ingresada:
        return jsonify(ok=False, error="Faltan datos de validación.")

    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="ID de administrador inválido.")

    # Obtenemos la contraseña tal cual desde la BD (sin desencriptar)
    query = text("SELECT contrasena FROM administrador WHERE id = :id")
    with db.engine.connect() as conn:
        row = conn.execute(query, {"id": admin_id}).mappings().first()

    if not row:
        return jsonify(ok=False, error="Administrador no encontrado.")

    contrasena_bd = (row["contrasena"] or "").strip()

    # Comparación (puedes quitar .upper() si quieres que sí distinga mayúsculas)
    if contrasena_bd.upper() != contrasena_ingresada.upper():
        return jsonify(ok=False, error="Contraseña incorrecta.")

    return jsonify(ok=True)


@administrador_bp.route("/administrador/api/detalle", methods=["POST"])
@login_required
def api_detalle():
    """
    Devuelve los datos descifrados de un administrador
    para rellenar el modal de edición.
    Se espera JSON: { "admin_id": X }
    """
    if not request.is_json:
        return jsonify(ok=False, error="Solicitud inválida"), 400

    data = request.get_json(silent=True) or {}
    admin_id = data.get("admin_id")

    if not admin_id:
        return jsonify(ok=False, error="Falta el ID del administrador.")

    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="ID de administrador inválido.")

    query = text("""
        SELECT id,
               no_empleado,
               nombre,
               apellido,
               correo_institucional,
               telefono,
               contrasena
        FROM administrador
        WHERE id = :id
    """)

    with db.engine.connect() as conn:
        row = conn.execute(query, {"id": admin_id}).mappings().first()

    if not row:
        return jsonify(ok=False, error="Administrador no encontrado.")

    admin_info = {
        "id": row["id"],
        "no_empleado": intentar_desencriptar(row["no_empleado"]),
        "nombre": row["nombre"],
        "apellido": row["apellido"],
        "correo_institucional": row["correo_institucional"],
        "telefono": intentar_desencriptar(row["telefono"]),
        "contrasena": intentar_desencriptar(row["contrasena"]),
    }

    return jsonify(ok=True, admin=admin_info)


@administrador_bp.route("/administrador/api/administrador/actualizar", methods=["POST"])
@login_required
def api_actualizar_administrador():
    """
    Actualiza los datos de un administrador.
    Espera JSON con:
      admin_id, no_empleado, correo_institucional, nombre, apellido, telefono, contrasena
    """
    if not request.is_json:
        return jsonify(ok=False, error="Solicitud inválida"), 400

    data = request.get_json(silent=True) or {}

    admin_id = data.get("admin_id")
    if not admin_id:
        return jsonify(ok=False, error="Falta el ID del administrador."), 400

    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="ID de administrador inválido."), 400

    no_empleado = (data.get("no_empleado") or "").strip()
    correo_institucional = (data.get("correo_institucional") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    apellido = (data.get("apellido") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    contrasena = (data.get("contrasena") or "").strip()

    # Seguimos cifrando no_empleado y telefono,
    # pero la contraseña se guarda tal cual (sin encriptar)
    no_empleado_cif = encriptar(no_empleado) if no_empleado else None
    telefono_cif = encriptar(telefono) if telefono else None
    contrasena_plana = contrasena  # sin cifrar

    update_q = text("""
        UPDATE administrador
        SET no_empleado = :no_empleado,
            correo_institucional = :correo_institucional,
            nombre = :nombre,
            apellido = :apellido,
            telefono = :telefono,
            contrasena = :contrasena
        WHERE id = :id
    """)

    try:
        with db.engine.begin() as conn:
            conn.execute(update_q, {
                "id": admin_id,
                "no_empleado": no_empleado_cif,
                "correo_institucional": correo_institucional,
                "nombre": nombre,
                "apellido": apellido,
                "telefono": telefono_cif,
                "contrasena": contrasena_plana
            })
        return jsonify(ok=True)
    except Exception:
        return jsonify(ok=False, error="Error al guardar los cambios del administrador."), 500



@administrador_bp.route("/administrador/api/administrador/eliminar", methods=["POST"])
@login_required
def api_eliminar_administrador():
    """
    Elimina un administrador si la contraseña ingresada coincide con la almacenada.
    Espera JSON:
      { "admin_id": X, "contrasena": "texto" }
    """
    if not request.is_json:
        return jsonify(ok=False, error="Solicitud inválida"), 400

    data = request.get_json(silent=True) or {}
    admin_id = data.get("admin_id")
    contrasena_ingresada = (data.get("contrasena") or "").strip()

    if not admin_id or not contrasena_ingresada:
        return jsonify(ok=False, error="Faltan datos para eliminar al administrador.")

    try:
        admin_id = int(admin_id)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="ID de administrador inválido.")

    # 1) Obtener contraseña cifrada
    query = text("SELECT contrasena FROM administrador WHERE id = :id")
    with db.engine.connect() as conn:
        row = conn.execute(query, {"id": admin_id}).mappings().first()

    if not row:
        return jsonify(ok=False, error="Administrador no encontrado.")

    contrasena_cifrada = row["contrasena"] or ""
    contrasena_real = intentar_desencriptar(contrasena_cifrada) or ""

    # 2) Comparar en mayúsculas (letras) y manteniendo números
    if contrasena_real.upper() != contrasena_ingresada.upper():
        return jsonify(ok=False, error="Contraseña incorrecta.")

    # 3) Eliminar registro
    delete_q = text("DELETE FROM administrador WHERE id = :id")

    try:
        with db.engine.begin() as conn:
            conn.execute(delete_q, {"id": admin_id})
        return jsonify(ok=True)
    except Exception:
        return jsonify(ok=False, error="Error al eliminar al administrador."), 500





@administrador_bp.route("/administrador/api/administrador/agregar", methods=["POST"])
@login_required
def api_agregar_administrador():
    """
    Crea un nuevo administrador en la tabla 'administrador'.
    Espera JSON con:
      no_empleado, correo_institucional, nombre, apellido, telefono, contrasena
    """
    if not request.is_json:
        return jsonify(ok=False, error="Solicitud inválida"), 400

    data = request.get_json(silent=True) or {}

    no_empleado = (data.get("no_empleado") or "").strip()
    correo_institucional = (data.get("correo_institucional") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    apellido = (data.get("apellido") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    contrasena = (data.get("contrasena") or "").strip()

    # Ciframos no_empleado y telefono, pero la contraseña se guarda tal cual
    no_empleado_cif = encriptar(no_empleado) if no_empleado else None
    telefono_cif = encriptar(telefono) if telefono else None
    contrasena_plana = contrasena  # sin cifrar

    insert_q = text("""
        INSERT INTO administrador
            (no_empleado, nombre, apellido, correo_institucional, telefono, contrasena, ultimo_acceso)
        VALUES
            (:no_empleado, :nombre, :apellido, :correo_institucional, :telefono, :contrasena, NULL)
    """)

    try:
        with db.engine.begin() as conn:
            conn.execute(insert_q, {
                "no_empleado": no_empleado_cif,
                "nombre": nombre,
                "apellido": apellido,
                "correo_institucional": correo_institucional,
                "telefono": telefono_cif,
                "contrasena": contrasena_plana
            })
        return jsonify(ok=True)
    except Exception:
        return jsonify(ok=False, error="Error al guardar el administrador."), 500




@administrador_bp.route("/api_restablecer_sistema", methods=["POST"])
def api_restablecer_sistema():
    """
    Restablece el sistema.

    - Si modo == "cero":
        * TRUNCATE de las tablas: alumnos, profesores, dock,
          bloqueados, no_inscritos, historial
        * Registra una notificación de que se restableció desde cero.

    - Si modo == "copia":
        * TRUNCATE de ALUMNOS, PROFESORES, BLOQUEADOS,
          NO_INSCRITOS, HISTORIAL (dock NO se toca)
        * Rellena cada tabla con los datos del JSON correspondiente
          en la carpeta instance (alumnos.json, etc.).
    """
    data = request.get_json(silent=True) or {}
    modo = (data.get("modo") or "").strip()

    # Tablas que se manejan en restablecimiento "desde cero" (incluye dock)
    tablas_cero = {
        "alumnos": [
            "id", "boleta", "curp", "nombre", "carrera", "escuela",
            "estado", "turno", "fecha", "url", "accion",
            "pin", "tiene_bici_guardada"
        ],
        "profesores": [
            "id", "numero_empleado", "nombre", "clave_presupuestal",
            "area_adscripcion", "estado", "fecha", "url",
            "accion", "pin", "tiene_bici_guardada"
        ],
        "dock": [
            "id", "estado", "sensor", "scanner", "status",
            "uso", "inicio_uso", "ultimo_uso", "usuario",
            "problema", "reportado", "zona", "tecnico"
        ],
        "bloqueados": [
            "id", "tipo", "identificador", "fecha",
            "motivo", "url", "nombre"
        ],
        "no_inscritos": [
            "id", "identificador", "nombre", "tipo",
            "carrera", "escuela", "estado",
            "fecha_registro", "url"
        ],
        "historial": [
            "id", "dock", "fecha", "hora_entrada",
            "hora_salida", "tiempo_total", "tipo",
            "nombre", "boleta", "accion"
        ],
    }

    # Para modo "copia", usamos las mismas tablas PERO sin dock
    tablas_copia = {
        nombre: cols
        for nombre, cols in tablas_cero.items()
        if nombre != "dock"
    }

    if modo not in ("cero", "copia"):
        return jsonify({"ok": False, "error": "Modo de restablecimiento no válido."}), 400

    try:
        if modo == "cero":
            # --- RESTABLECER DESDE CERO ---
            with db.engine.begin() as conn:
                # 1) TRUNCATE de TODAS las tablas (incluyendo dock)
                for nombre_tabla in tablas_cero.keys():
                    conn.execute(text(f"TRUNCATE TABLE {nombre_tabla}"))

                # 2) Registrar notificación
                ahora = datetime.now()
                fecha_str = ahora.strftime("%Y-%m-%d")
                hora_str = ahora.strftime("%H:%M")

                conn.execute(
                    text("""
                        INSERT INTO notificaciones (actor, notificacion, fecha, hora, motivo, leida)
                        VALUES (:actor, :notificacion, :fecha, :hora, :motivo, :leida)
                    """),
                    {
                        "actor": "sistema",
                        "notificacion": "Se restablecio el sistema desde cero",
                        "fecha": fecha_str,
                        "hora": hora_str,
                        "motivo": "Alto",
                        "leida": 1,
                    }
                )

        else:
            # --- RESTABLECER DESDE COPIA DE SEGURIDAD ---
            with db.engine.begin() as conn:
                base_path = current_app.instance_path

                # 1) TRUNCATE solo de las tablas de tablas_copia (dock no se toca)
                for nombre_tabla in tablas_copia.keys():
                    conn.execute(text(f"TRUNCATE TABLE {nombre_tabla}"))

                # 2) Restaurar desde JSON cada tabla (sin dock)
                for nombre_tabla, columnas in tablas_copia.items():
                    json_path = os.path.join(base_path, f"{nombre_tabla}.json")
                    if not os.path.exists(json_path):
                        continue  # no hay respaldo para esta tabla

                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            registros = json.load(f)
                    except Exception:
                        registros = []

                    if not isinstance(registros, list) or not registros:
                        continue

                    cols_str = ", ".join(columnas)
                    vals_str = ", ".join(f":{c}" for c in columnas)
                    insert_stmt = text(
                        f"INSERT INTO {nombre_tabla} ({cols_str}) "
                        f"VALUES ({vals_str})"
                    )

                    for fila in registros:
                        params = {c: fila.get(c) for c in columnas}
                        conn.execute(insert_stmt, params)

        return jsonify({"ok": True})
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Error al restablecer el sistema."
        }), 500




@administrador_bp.route("/administrador/api/generar_backup", methods=["POST"])
@login_required
def api_generar_backup():
    """
    Genera un respaldo en JSON de las tablas principales en la carpeta 'instance'.
    - Primero limpia la carpeta 'instance' (borra todos los archivos y carpetas dentro).
    - Luego crea un archivo JSON por cada tabla, por ejemplo:
        alumnos.json, profesores.json, administrador.json, etc.
    """
    try:
        # Definimos qué columnas de cada tabla queremos respaldar
        tablas = {
            "alumnos": [
                "id", "boleta", "curp", "nombre", "carrera", "escuela",
                "estado", "turno", "fecha", "url", "accion",
                "pin", "tiene_bici_guardada"
            ],
            "profesores": [
                "id", "numero_empleado", "nombre", "clave_presupuestal",
                "area_adscripcion", "estado", "fecha", "url",
                "accion", "pin", "tiene_bici_guardada"
            ],
            "bloqueados": [
                "id", "tipo", "identificador", "fecha",
                "motivo", "url", "nombre"
            ],
            "no_inscritos": [
                "id", "identificador", "nombre", "tipo",
                "carrera", "escuela", "estado",
                "fecha_registro", "url"
            ],
            "historial": [
                "id", "dock", "fecha", "hora_entrada",
                "hora_salida", "tiempo_total", "tipo",
                "nombre", "boleta", "accion"
            ],
        }




        # Carpeta instance de la app
        base_path = current_app.instance_path
        os.makedirs(base_path, exist_ok=True)

        # 1) Limpiar carpeta instance (borrar TODO lo que tenga dentro)
        for nombre in os.listdir(base_path):
            ruta = os.path.join(base_path, nombre)
            if os.path.isfile(ruta):
                os.remove(ruta)
            elif os.path.isdir(ruta):
                shutil.rmtree(ruta)

        # 2) Crear un JSON por cada tabla
        from sqlalchemy import text as sa_text

        with db.engine.connect() as conn:
            for nombre_tabla, columnas in tablas.items():
                query = sa_text(f"SELECT {', '.join(columnas)} FROM {nombre_tabla}")
                result = conn.execute(query).mappings()

                registros = []
                for row in result:
                    # Convertimos a diccionario simple y pasamos todo a str/None para que sea serializable
                    registro = {}
                    for col in columnas:
                        valor = row.get(col)
                        registro[col] = None if valor is None else str(valor)
                    registros.append(registro)

                # Guardar JSON: instance/alumnos.json, etc.
                json_path = os.path.join(base_path, f"{nombre_tabla}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(registros, f, ensure_ascii=False, indent=2)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Error al generar el backup: {e}"
        }), 500
