# dashboard_python/usuarios.py
from flask import Blueprint, render_template, jsonify, current_app, request
from flask_login import login_required
from sqlalchemy import text
from datetime import datetime
from models import db
from Descifrado import desencriptar
from Cifrado import encriptar
import unicodedata



from flask import send_file  # además de Blueprint, render_template, etc.
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

import os
from flask import current_app



SIGLAS_ESCUELAS = {
    "ESCOM":  "Escuela Superior de Cómputo",
    "ESFM":   "Escuela Superior de Física y Matemáticas",
    "ESIME":  "Escuela Superior de Ingeniería Mecánica y Eléctrica",
    "ESIQIE": "Escuela Superior de Ingeniería Química e Industrias Extractivas",
    "ESIT":   "Escuela Superior de Ingeniería Textil",
    "ESIA":   "Escuela Superior de Ingeniería y Arquitectura",
    "ESCA":   "Escuela Superior de Comercio y Administración",
    "ESE":    "Escuela Superior de Economía",
    "ENCB":   "Escuela Nacional de Ciencias Biológicas",
    "ENMH":   "Escuela Nacional de Medicina y Homeopatía",
    "ESM":    "Escuela Superior de Medicina",
    "EST":    "Escuela Superior de Turismo",
    "UPIBI":  "Unidad Profesional Interdisciplinaria de Biotecnología",
    "UPIITA": "Unidad Profesional Interdisciplinaria de Ingeniería en Tecnologías Avanzadas",
    "UPIICSA":"Unidad Profesional Interdisciplinaria de Ingeniería y Ciencias Sociales y Administrativas",
}



usuarios_bp = Blueprint("usuarios_bp", __name__)



def normalizar_mayus_sin_acentos(texto: str) -> str:
    """
    Convierte el texto a MAYÚSCULAS y elimina acentos/diéresis.
    Si viene None, regresa cadena vacía.
    """
    if not texto:
        return ""
    # Quitar espacios y pasar a mayúsculas
    texto = texto.strip().upper()
    # Normalizar y eliminar marcas de acento
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

# ========= FRAGMENTO HTML =========

@usuarios_bp.get("/usuarios/fragment")
@login_required
def fragment():
    # Devuelve un fragmento (sin <html> completo)
    return render_template("dashboard_html/usuarios_fragment.html")


# ========= KPIs DE USUARIOS =========

@usuarios_bp.get("/usuarios/api/kpis")
@login_required
def api_kpis_usuarios():
    """
    KPIs de la sección Usuarios:
      - total_alumnos           (todos los alumnos)
      - total_profesores        (todos los profesores)
      - total_registrados       (alumnos + profesores NO bloqueados)
      - total_noinscritos       (no_inscritos NO bloqueados)
      - total_bloqueados        (tabla bloqueados)
    """
    try:
        # Totales brutos de alumnos y profesores (para los dos primeros KPIs)
        row_alumnos = db.session.execute(
            text("SELECT COUNT(*) AS total_alumnos FROM alumnos")
        ).mappings().first()

        row_profes = db.session.execute(
            text("SELECT COUNT(*) AS total_profesores FROM profesores")
        ).mappings().first()

        # Registrados = alumnos/profesores cuya URL NO está en bloqueados
        row_reg_alum = db.session.execute(
            text("""
                SELECT COUNT(*) AS registrados_alumnos
                FROM alumnos
                WHERE url IS NULL
                   OR url NOT IN (SELECT url FROM bloqueados)
            """)
        ).mappings().first()

        row_reg_prof = db.session.execute(
            text("""
                SELECT COUNT(*) AS registrados_profesores
                FROM profesores
                WHERE url IS NULL
                   OR url NOT IN (SELECT url FROM bloqueados)
            """)
        ).mappings().first()

        # No inscritos visibles = no_inscritos cuya URL NO está en bloqueados
        row_noins_visibles = db.session.execute(
            text("""
                SELECT COUNT(*) AS total_noinscritos_visibles
                FROM no_inscritos
                WHERE url IS NULL
                   OR url NOT IN (SELECT url FROM bloqueados)
            """)
        ).mappings().first()

        # Bloqueados (tal cual la tabla bloqueados)
        row_bloq = db.session.execute(
            text("SELECT COUNT(*) AS total_bloqueados FROM bloqueados")
        ).mappings().first()

        total_alumnos          = (row_alumnos or {}).get("total_alumnos", 0)
        total_profesores       = (row_profes or {}).get("total_profesores", 0)
        registrados_alumnos    = (row_reg_alum or {}).get("registrados_alumnos", 0)
        registrados_profesores = (row_reg_prof or {}).get("registrados_profesores", 0)
        total_noinscritos      = (row_noins_visibles or {}).get("total_noinscritos_visibles", 0)
        total_bloqueados       = (row_bloq or {}).get("total_bloqueados", 0)

        # Registrados reales: solo los que no están bloqueados
        total_registrados = (registrados_alumnos or 0) + (registrados_profesores or 0)

        return jsonify({
            "total_alumnos": int(total_alumnos or 0),
            "total_profesores": int(total_profesores or 0),
            "total_registrados": int(total_registrados or 0),
            "total_noinscritos": int(total_noinscritos or 0),
            "total_bloqueados": int(total_bloqueados or 0),
        })
    except Exception:
        current_app.logger.exception("Error consultando KPIs de usuarios")
        return jsonify({"error": "db_error"}), 500


# ========= LISTA DE USUARIOS (TABLA) =========

@usuarios_bp.get("/usuarios/api/lista")
@login_required
def api_lista_usuarios():
    """
    Devuelve la lista de usuarios para la tabla.
    Incluye:
      - Alumnos (tabla alumnos)
      - Profesores (tabla profesores)
      - No inscritos (tabla no_inscritos)
      Además:
      - Si la URL de un alumno / profesor / no inscrito está en 'bloqueados',
        se marca su estado como 'Bloqueado'.
      - Si el nombre del alumno/profesor aparece en la tabla dock.usuario,
        se marca 'ocupando_dock' para ocultar los botones de acción.
    """
    try:
        items = []

        # ---- URLs de usuarios bloqueados ----
        filas_bloq = db.session.execute(
            text("SELECT url FROM bloqueados")
        ).mappings().all()
        urls_bloqueados = {f["url"] for f in filas_bloq if f.get("url")}

        # ---- NOMBRES QUE ESTÁN OCUPANDO ALGÚN DOCK ----
        filas_dock = db.session.execute(
            text("""
                SELECT usuario
                FROM dock
                WHERE usuario IS NOT NULL
                  AND TRIM(usuario) <> ''
            """)
        ).mappings().all()
        nombres_en_dock = {
            (f["usuario"] or "").strip().lower()
            for f in filas_dock
            if f.get("usuario")
        }

        # ---- ALUMNOS ----
        filas_alumnos = db.session.execute(
            text("""
                SELECT id, nombre, boleta, fecha, url
                FROM alumnos
                ORDER BY id
            """)
        ).mappings().all()

        for f in filas_alumnos:
            boleta_cifrada = f["boleta"]
            try:
                credencial = desencriptar(boleta_cifrada) if boleta_cifrada else None
            except Exception:
                credencial = boleta_cifrada

            url = f.get("url")
            estado = "Bloqueado" if url and url in urls_bloqueados else "Registrado"

            nombre = f["nombre"] or ""
            nombre_norm = nombre.strip().lower()
            ocupando = nombre_norm in nombres_en_dock

            items.append({
                "id": f["id"],
                "nombre": nombre,
                "tipo": "Alumno",
                "credencial": credencial,
                "estado": estado,
                "fecha": f["fecha"],
                "url": url,
                "origen": "alumnos",
                "ocupando_dock": ocupando,
            })

        # ---- PROFESORES ----
        filas_profes = db.session.execute(
            text("""
                SELECT id, nombre, numero_empleado, fecha, url
                FROM profesores
                ORDER BY id
            """)
        ).mappings().all()

        for f in filas_profes:
            emp_cifrado = f["numero_empleado"]
            try:
                credencial = desencriptar(emp_cifrado) if emp_cifrado else None
            except Exception:
                credencial = emp_cifrado

            url = f.get("url")
            estado = "Bloqueado" if url and url in urls_bloqueados else "Registrado"

            nombre = f["nombre"] or ""
            nombre_norm = nombre.strip().lower()
            ocupando = nombre_norm in nombres_en_dock

            items.append({
                "id": f["id"],
                "nombre": nombre,
                "tipo": "Profesor",
                "credencial": credencial,
                "estado": estado,
                "fecha": f["fecha"],
                "url": url,
                "origen": "profesores",
                "ocupando_dock": ocupando,
            })

        # ---- NO INSCRITOS ----
        filas_noins = db.session.execute(
            text("""
                SELECT id, nombre, tipo, identificador, fecha_registro, url
                FROM no_inscritos
                ORDER BY id
            """)
        ).mappings().all()

        for f in filas_noins:
            identificador_cifrado = f["identificador"]
            try:
                credencial = desencriptar(identificador_cifrado) if identificador_cifrado else None
            except Exception:
                credencial = identificador_cifrado

            url = f.get("url")

            # Decidir si es Alumno o Profesor según el campo 'tipo' de no_inscritos
            tipo_raw = (f.get("tipo") or "").strip().lower()
            if tipo_raw == "profesor":
                tipo_visual = "Profesor"
            else:
                # cualquier otro valor (alumno, vacío, null) lo tratamos como Alumno
                tipo_visual = "Alumno"

            estado = "Bloqueado" if url and url in urls_bloqueados else "No inscrito"

            items.append({
                "id": f["id"],
                "nombre": f["nombre"],
                "tipo": tipo_visual,      # Alumno o Profesor según BD
                "credencial": credencial,
                "estado": estado,
                "fecha": f["fecha_registro"],
                "url": url,
                "origen": "no_inscritos",
                "ocupando_dock": False,   # no manejan docks
            })

        return jsonify({"items": items})
    except Exception:
        current_app.logger.exception("Error consultando lista de usuarios")
        return jsonify({"error": "db_error"}), 500


def construir_titulo_lista(filtro_tipo: str, filtro_estado: str) -> str:
    """
    Construye el texto "Lista de X" según el filtro de tipo y estado.
    filtro_tipo: 'todos' | 'alumno' | 'profesor'
    filtro_estado: 'todos' | 'registrado' | 'no inscrito' | 'bloqueado'
    """
    ft = (filtro_tipo or "todos").lower()
    fe = (filtro_estado or "todos").lower()

    if ft == "alumno":
        base = "Lista de Alumnos"
    elif ft == "profesor":
        base = "Lista de Profesores"
    else:
        base = "Lista de Usuarios"

    if fe != "todos":
        if fe == "registrado":
            sufijo = " Registrados"
        elif fe == "no inscrito":
            sufijo = " No inscritos"
        elif fe == "bloqueado":
            sufijo = " Bloqueados"
        else:
            sufijo = ""
        base += sufijo

    return base


#GENERAR PDF

def generar_pdf_lista_usuarios(items, titulo: str) -> BytesIO:
    """
    Genera un PDF en memoria con el encabezado IPN/ESCOM, el título recibido
    y una tabla con los usuarios.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ===== Encabezado centrado =====
    y = height - 60  # un poco más abajo del borde superior

    texto1 = "INSTITUTO POLITÉCNICO NACIONAL"
    texto2 = "ESCUELA SUPERIOR DE CÓMPUTO"

    # Línea 1: IPN (Times New Roman, negritas, tamaño 14)
    c.setFont("Times-Bold", 14)  # Times-Bold = Times New Roman en negritas
    t1_w = c.stringWidth(texto1, "Times-Bold", 14)
    c.drawString((width - t1_w) / 2, y, texto1)

    # Línea 2: ESCOM (puede quedarse en 12 normal)
    y -= 18
    c.setFont("Times-Roman", 12)
    t2_w = c.stringWidth(texto2, "Times-Roman", 12)
    c.drawString((width - t2_w) / 2, y, texto2)

    # Espacio en blanco
    y -= 28

    # Título ("Lista de Usuarios...", etc.)
    c.setFont("Times-Bold", 13)
    title_w = c.stringWidth(titulo, "Times-Bold", 13)
    c.drawString((width - title_w) / 2, y, titulo)

    y -= 30
    # ===== Fin encabezado centrado =====

    # Encabezados de la tabla
    headers = ["ID", "Nombre", "Tipo", "Credencial", "Estado", "Último Acceso"]
    col_x = [72, 110, 260, 340, 430, 500]  # posiciones aproximadas

    c.setFont("Times-Bold", 10)
    for x, htext in zip(col_x, headers):
        c.drawString(x, y, htext)

    y -= 14
    c.setFont("Times-Roman", 9)

    # Filas
    max_rows_per_page = 40
    row_count = 0
    for idx, u in enumerate(items, start=1):
        if row_count >= max_rows_per_page:
            c.showPage()
            width, height = letter
            y = height - 72
            c.setFont("Times-Roman", 9)
            row_count = 0

        id_txt   = str(idx).zfill(3)
        nombre   = (u.get("nombre") or "")[:40]
        tipo     = (u.get("tipo") or "")[:15]
        cred     = (u.get("credencial") or "")[:20]
        estado   = (u.get("estado") or "")[:15]
        fecha    = str(u.get("fecha") or "")[:20]

        valores = [id_txt, nombre, tipo, cred, estado, fecha]
        for x, val in zip(col_x, valores):
            c.drawString(x, y, val)

        y -= 12
        row_count += 1

    c.save()
    buffer.seek(0)
    return buffer




#descargar PDF

@usuarios_bp.get("/usuarios/descargar")
@login_required
def descargar_usuarios_pdf():
    # 1) Leer filtros que mande el frontend
    filtro_tipo   = (request.args.get("tipo") or "todos").lower()
    filtro_estado = (request.args.get("estado") or "todos").lower()
    texto_busqueda = (request.args.get("q") or "").strip().lower()

    # 2) Reusar la lógica de api_lista_usuarios para obtener los items
    resp = api_lista_usuarios()
    data = resp.get_json(silent=True) or {}
    items = data.get("items", [])

    # 3) Aplicar filtros igual que en tu JS
    filtrados = []
    for idx, u in enumerate(items, start=1):
        tipo   = (u.get("tipo") or "").lower()       # "alumno" / "profesor"
        estado = (u.get("estado") or "").lower()     # "registrado", "no inscrito", "bloqueado"
        nombre = (u.get("nombre") or "")
        cred   = (u.get("credencial") or "")
        fecha  = str(u.get("fecha") or "")

        # Filtro tipo
        if filtro_tipo == "alumno" and tipo != "alumno":
            continue
        if filtro_tipo == "profesor" and tipo != "profesor":
            continue

        # Filtro estado
        if filtro_estado == "registrado" and estado != "registrado":
            continue
        if filtro_estado == "no inscrito" and estado != "no inscrito":
            continue
        if filtro_estado == "bloqueado" and estado != "bloqueado":
            continue

        # Filtro buscador (opcional)
        if texto_busqueda:
            q = texto_busqueda
            id_txt = str(idx).zfill(3)
            texto_completo = " ".join([
                id_txt,
                nombre,
                cred,
                tipo,
                estado,
                fecha,
            ]).lower()
            if q not in texto_completo:
                continue

        filtrados.append(u)

    # 4) Construir título según filtros
    titulo = construir_titulo_lista(filtro_tipo, filtro_estado)

    # 5) Generar PDF y devolverlo
    pdf_buffer = generar_pdf_lista_usuarios(filtrados, titulo)
    filename = titulo.replace(" ", "_") + ".pdf"

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )



# ========= BLOQUEAR USUARIO =========

@usuarios_bp.post("/usuarios/api/bloquear")
@login_required
def api_bloquear_usuario():
    """
    Inserta (o actualiza) un registro en la tabla 'bloqueados' para la URL dada.
    Campos:
      - tipo: "Alumno" / "Profesor" (desde el frontend)
      - credencial: boleta o número de empleado
      - url: url única del usuario
    """
    try:
        data = request.get_json(silent=True) or {}
        tipo_front = (data.get("tipo") or "").strip()
        credencial = (data.get("credencial") or "").strip()
        url = (data.get("url") or "").strip()

        if not tipo_front or not credencial or not url:
            return jsonify({"ok": False, "error": "missing_fields"}), 400

        # Normalizar tipo para la BD
        tipo_db = "alumno" if tipo_front.lower().startswith("alum") else "profesor"

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        motivo = "Se presiono el boton bloquear"

        db.session.execute(
            text("""
                INSERT INTO bloqueados (tipo, identificador, fecha, motivo, url)
                VALUES (:tipo, :identificador, :fecha, :motivo, :url)
                ON DUPLICATE KEY UPDATE
                    tipo = VALUES(tipo),
                    identificador = VALUES(identificador),
                    fecha = VALUES(fecha),
                    motivo = VALUES(motivo)
            """),
            {
                "tipo": tipo_db,
                "identificador": credencial,
                "fecha": fecha_hoy,
                "motivo": motivo,
                "url": url,
            },
        )

        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("Error al bloquear usuario")
        db.session.rollback()
        return jsonify({"ok": False, "error": "server_error"}), 500



# ========= DESBLOQUEAR USUARIO =========

@usuarios_bp.post("/usuarios/api/desbloquear")
@login_required
def api_desbloquear_usuario():
    """
    Elimina el registro de 'bloqueados' asociado a la URL dada.
    """
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()

        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400

        db.session.execute(
            text("DELETE FROM bloqueados WHERE url = :url"),
            {"url": url},
        )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("Error al desbloquear usuario")
        db.session.rollback()
        return jsonify({"ok": False, "error": "server_error"}), 500


# ========= DETALLE ALUMNO (PARA EDITAR) =========

@usuarios_bp.post("/usuarios/api/detalle_alumno")
@login_required
def api_detalle_alumno():
    """Devuelve los datos de un alumno para precargar el modal de edición."""
    try:
        data = request.get_json(silent=True) or {}
        origen = (data.get("origen") or "").strip()
        id_raw = data.get("id")

        # Solo permitimos alumnos registrados en la tabla 'alumnos'
        if origen != "alumnos":
            return jsonify({"ok": False, "error": "invalid_origin"}), 400

        try:
            alumno_id = int(id_raw)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_id"}), 400

        fila = db.session.execute(
            text("""
                SELECT id, boleta, curp, nombre, carrera,
                       escuela, turno, url, pin
                FROM alumnos
                WHERE id = :id
            """),
            {"id": alumno_id}
        ).mappings().first()

        if not fila:
            return jsonify({"ok": False, "error": "not_found"}), 404

        def intentar_desencriptar(valor):
            if not valor:
                return ""
            try:
                return desencriptar(valor)
            except Exception:
                # Si falla el descifrado, regresamos el valor tal cual
                return valor

        # Boleta, CURP y PIN en claro (si estaban cifrados)
        boleta_plana = intentar_desencriptar(fila["boleta"])
        curp_plana   = intentar_desencriptar(fila["curp"])
        pin_plano    = intentar_desencriptar(fila["pin"])

        escuela_bd = fila["escuela"] or ""
        escuela_sigla = ""

        if escuela_bd:
            # Buscar la sigla a partir del nombre completo almacenado
            for sigla, nombre in SIGLAS_ESCUELAS.items():
                if nombre == escuela_bd:
                    escuela_sigla = sigla
                    break
            # Si no se encontró, asumimos que ya está guardada como sigla
            if not escuela_sigla:
                escuela_sigla = escuela_bd

        data_out = {
            "id": fila["id"],
            "boleta": boleta_plana or "",
            "curp": curp_plana or "",
            "nombre": fila["nombre"] or "",
            "carrera": fila["carrera"] or "",
            "escuela_sigla": escuela_sigla,
            "turno": fila["turno"] or "",
            "pin": pin_plano or "",
            "url": fila["url"] or "",
        }

        return jsonify({"ok": True, "data": data_out})
    except Exception:
        current_app.logger.exception("Error obteniendo detalle de alumno")
        return jsonify({"ok": False, "error": "server_error"}), 500



@usuarios_bp.post("/usuarios/api/detalle_profesor")
@login_required
def api_detalle_profesor():
    """
    Regresa el detalle de un profesor para el modal de edición,
    DESCIFRANDO numero_empleado, clave_presupuestal y pin.
    """
    try:
        data_in = request.get_json(silent=True) or {}
        profesor_id = data_in.get("id")
        origen      = data_in.get("origen")

        # Solo aceptamos si viene de la tabla profesores
        if not profesor_id or origen != "profesores":
            return jsonify({"ok": False, "error": "bad_request"}), 400

        fila = db.session.execute(
            text("""
                SELECT
                    id,
                    numero_empleado,
                    nombre,
                    clave_presupuestal,
                    area_adscripcion,
                    url,
                    pin
                FROM profesores
                WHERE id = :id
            """),
            {"id": profesor_id}
        ).mappings().first()

        if not fila:
            return jsonify({"ok": False, "error": "not_found"}), 404

        def intentar_desencriptar(valor):
            if not valor:
                return ""
            try:
                return desencriptar(valor)
            except Exception:
                # Si algo falla, regresamos el valor tal cual
                return valor

        num_empleado_plano = intentar_desencriptar(fila["numero_empleado"])
        clave_plana        = intentar_desencriptar(fila["clave_presupuestal"])
        pin_plano          = intentar_desencriptar(fila["pin"])

        data_out = {
            "id": fila["id"],
            "numero_empleado": num_empleado_plano or "",
            "nombre": fila["nombre"] or "",
            "clave_presupuestal": clave_plana or "",
            "area_adscripcion": fila["area_adscripcion"] or "",
            "url": fila["url"] or "",
            "pin": pin_plano or "",
        }

        return jsonify({"ok": True, "data": data_out})
    except Exception:
        current_app.logger.exception("Error obteniendo detalle de profesor")
        return jsonify({"ok": False, "error": "server_error"}), 500



# ========= ACTUALIZAR ALUMNO (EDITAR) =========

@usuarios_bp.post("/usuarios/api/actualizar_alumno")
@login_required
def api_actualizar_alumno():
    """
    Actualiza SOLO el PIN de un alumno existente en la tabla 'alumnos'.
    Ya no permite editar boleta, CURP, nombre, carrera, escuela, turno ni URL.
    """
    try:
        data = request.get_json(silent=True) or {}

        id_raw = data.get("id")
        try:
            alumno_id = int(id_raw)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_id"}), 400

        pin = (data.get("pin") or "").strip()
        if not pin:
            return jsonify({"ok": False, "error": "missing_pin"}), 400

        # Cifrar solo el PIN
        try:
            pin_cifrado = encriptar(pin)
        except Exception:
            current_app.logger.exception("Error cifrando PIN (update)")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Actualizar SOLO el PIN en la tabla alumnos
        sql = text("""
            UPDATE alumnos
               SET pin = :pin
             WHERE id = :id
        """)

        try:
            db.session.execute(sql, {
                "pin": pin_cifrado,
                "id":  alumno_id,
            })
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Error actualizando PIN de alumno")
            return jsonify({"ok": False, "error": "server_error"}), 500

        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("Error procesando actualización de alumno")
        return jsonify({"ok": False, "error": "server_error"}), 500




# ========= BORRAR USUARIO =========

@usuarios_bp.post("/usuarios/api/borrar")
@login_required
def api_borrar_usuario():
    """
    Borra el registro del usuario en su tabla de origen:
      - origen = 'alumnos'      -> tabla alumnos
      - origen = 'profesores'   -> tabla profesores
      - origen = 'no_inscritos' -> tabla no_inscritos
    Se borra por id.
    Además, si se recibe una URL, también elimina cualquier
    registro asociado en la tabla 'bloqueados'.
    """
    try:
        data = request.get_json(silent=True) or {}
        origen = (data.get("origen") or "").strip()
        id_raw = data.get("id")
        url = (data.get("url") or "").strip()   # 👈 NUEVO

        if not origen or id_raw is None:
            return jsonify({"ok": False, "error": "missing_fields"}), 400

        try:
            user_id = int(id_raw)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_id"}), 400

        if origen == "alumnos":
            tabla = "alumnos"
        elif origen == "profesores":
            tabla = "profesores"
        elif origen == "no_inscritos":
            tabla = "no_inscritos"
        else:
            return jsonify({"ok": False, "error": "invalid_origin"}), 400

        # Borrar de la tabla de origen
        db.session.execute(
            text(f"DELETE FROM {tabla} WHERE id = :id"),
            {"id": user_id},
        )

        # Si viene URL, borrar también de bloqueados
        if url:
            db.session.execute(
                text("DELETE FROM bloqueados WHERE url = :url"),
                {"url": url},
            )

        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.exception("Error al borrar usuario")
        db.session.rollback()
        return jsonify({"ok": False, "error": "server_error"}), 500



# ========= NUEVO ALUMNO =========

@usuarios_bp.post("/usuarios/api/nuevo_alumno")
@login_required
def api_nuevo_alumno():
    """
    Inserta un nuevo alumno en la tabla 'alumnos'.
    - Cifra CURP y PIN con Cifrado.encriptar
    - Convierte la sigla de la escuela a su nombre completo
    """
    from flask import request  # import local para no mover tus imports de arriba

    try:
        data = request.get_json(silent=True) or {}

        boleta = normalizar_mayus_sin_acentos(data.get("boleta") or "")
        curp = normalizar_mayus_sin_acentos(data.get("curp") or "")
        nombre = normalizar_mayus_sin_acentos(data.get("nombre") or "")
        carrera = normalizar_mayus_sin_acentos(data.get("carrera") or "")
        escuela_sigla = (data.get("escuela_sigla") or "").strip()  # sin cambio
        estado = (data.get("estado") or "").strip()  # sin cambio
        turno = normalizar_mayus_sin_acentos(data.get("turno") or "")
        url = (data.get("url") or "").strip()  # sin cambio
        pin = (data.get("pin") or "").strip()  # sin cambio

        # Validar campos vacíos
        if not all([boleta, curp, nombre, carrera,
                    escuela_sigla, estado, turno, url, pin]):
            return jsonify({"ok": False, "error": "missing_fields"}), 400

        # Validar escuela
        escuela = SIGLAS_ESCUELAS.get(escuela_sigla.upper())
        if not escuela:
            return jsonify({"ok": False, "error": "invalid_escuela"}), 400

        # Cifrar BOLETA
        try:
            boleta_cifrada = encriptar(boleta)
        except Exception:
            current_app.logger.exception("Error cifrando BOLETA")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Cifrar CURP
        try:
            curp_cifrada = encriptar(curp)
        except Exception:
            current_app.logger.exception("Error cifrando CURP")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500
        #cifrar pin
        try:
            pin_cifrado = encriptar(pin)
        except Exception:
            current_app.logger.exception("Error cifrando PIN")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Fecha y hora actual en formato "YYYY-MM-DD,HH-MM-SS"
        fecha_hoy = datetime.now().strftime("%Y-%m-%d,%H-%M-%S")

        # Insertar en la tabla alumnos
        sql = text("""
            INSERT INTO alumnos
                (boleta, curp, nombre, carrera, escuela,
                 estado, turno, fecha, url, pin)
            VALUES
                (:boleta, :curp, :nombre, :carrera, :escuela,
                 :estado, :turno, :fecha, :url, :pin)
        """)

        db.session.execute(sql, {
            "boleta": boleta_cifrada,
            "curp": curp_cifrada,
            "nombre": nombre,
            "carrera": carrera,
            "escuela": escuela,
            "estado": estado,
            "turno": turno,
            "fecha": fecha_hoy,
            "url": url,
            "pin": pin_cifrado,
        })
        db.session.commit()

        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.exception("Error agregando nuevo alumno")
        db.session.rollback()

        # Si quieres detectar URL duplicada
        msg = str(e).lower()
        if "duplicate" in msg and "url" in msg:
            return jsonify({"ok": False, "error": "duplicate_url"}), 400

        return jsonify({"ok": False, "error": "server_error"}), 500


# ========= NUEVO PROFESOR =========

@usuarios_bp.post("/usuarios/api/nuevo_profesor")
@login_required
def api_nuevo_profesor():
    """
    Inserta un nuevo profesor en la tabla 'profesores'.

    Campos esperados en el JSON:
      - numero_empleado   (se cifra)
      - nombre            (texto plano)
      - clave_presupuestal (se cifra)
      - area_adscripcion  (texto plano)
      - estado            (por ahora siempre "Registrado")
      - url               (texto plano, UNIQUE)
      - pin               (se cifra)
    """
    try:
        data = request.get_json(silent=True) or {}

        numero_empleado = (data.get("numero_empleado") or "").strip()  # sin cambio
        nombre = normalizar_mayus_sin_acentos(data.get("nombre") or "")
        clave_presupuestal = (data.get("clave_presupuestal") or "").strip()  # sin cambio
        area_adscripcion = normalizar_mayus_sin_acentos(data.get("area_adscripcion") or "")
        estado = (data.get("estado") or "").strip()  # sin cambio
        url = (data.get("url") or "").strip()  # sin cambio
        pin = (data.get("pin") or "").strip()  # sin cambio

        # Validar campos vacíos
        if (not numero_empleado or not nombre or not clave_presupuestal or
            not area_adscripcion or not estado or not url or not pin):
            return jsonify({"ok": False, "error": "missing_fields"}), 400

        # Cifrar número de empleado
        try:
            numero_empleado_cifrado = encriptar(numero_empleado)
        except Exception:
            current_app.logger.exception("Error cifrando NUMERO_EMPLEADO")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Cifrar clave presupuestal
        try:
            clave_cifrada = encriptar(clave_presupuestal)
        except Exception:
            current_app.logger.exception("Error cifrando CLAVE_PRESUPUESTAL")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Cifrar PIN
        try:
            pin_cifrado = encriptar(pin)
        except Exception:
            current_app.logger.exception("Error cifrando PIN (profesor)")
            return jsonify({"ok": False, "error": "encrypt_error"}), 500

        # Fecha y hora actual en formato "YYYY-MM-DD,HH-MM-SS"
        fecha_hoy = datetime.now().strftime("%Y-%m-%d,%H-%M-%S")

        # Insertar en la tabla profesores
        sql = text("""
            INSERT INTO profesores
                (numero_empleado, nombre, clave_presupuestal,
                 area_adscripcion, estado, fecha, url, pin)
            VALUES
                (:numero_empleado, :nombre, :clave_presupuestal,
                 :area_adscripcion, :estado, :fecha, :url, :pin)
        """)

        db.session.execute(sql, {
            "numero_empleado": numero_empleado_cifrado,
            "nombre": nombre,
            "clave_presupuestal": clave_cifrada,
            "area_adscripcion": area_adscripcion,
            "estado": estado,
            "fecha": fecha_hoy,
            "url": url,
            "pin": pin_cifrado,
        })
        db.session.commit()

        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.exception("Error agregando nuevo profesor")
        db.session.rollback()

        # Detectar URL duplicada
        msg = str(e).lower()
        if "duplicate" in msg and "url" in msg:
            return jsonify({"ok": False, "error": "duplicate_url"}), 400

        return jsonify({"ok": False, "error": "server_error"}), 500



@usuarios_bp.post("/api/actualizar_profesor")
def api_actualizar_profesor():
    """
    Actualiza SOLO el PIN de un profesor en la tabla `profesores`.
    Ya no permite editar número de empleado, nombre, clave, área ni URL.
    """
    data = request.get_json(silent=True) or {}

    profesor_id = (data.get("id") or "").strip()
    pin         = (data.get("pin") or "").strip()

    if not profesor_id:
        return jsonify(ok=False, error="missing_id"), 400
    if not pin:
        return jsonify(ok=False, error="missing_pin"), 400

    # Cifrar solo el PIN
    try:
        pin_cif = encriptar(pin)
    except Exception:
        current_app.logger.exception("Error cifrando PIN del profesor (update)")
        return jsonify(ok=False, error="encrypt_error"), 500

    # Actualizar SOLO el PIN en BD
    try:
        sql_upd = text("""
            UPDATE profesores
               SET pin = :pin
             WHERE id = :id
        """)
        db.session.execute(sql_upd, {
            "pin": pin_cif,
            "id":  profesor_id,
        })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al actualizar PIN de profesor")
        return jsonify(ok=False, error="db_error"), 500

    return jsonify(ok=True)
