# vigilante.py
#
# Script independiente que revisa cada 10 segundos las tablas:
#   - alumnos
#   - profesores
#   - bloqueados
#   - no_inscritos
#
# y por cada registro nuevo inserta una fila en la tabla `notificaciones`
# con los textos:
#   "[nombre] se ha registrado correctamente"
#   "[nombre] fue bloqueado del sistema"
#   "[nombre] no se pudo registrar al sistema"
#
# Además vigila la tabla dock:
#   - cuando un dock pasa a status "inactivo" genera una notificación
#     con mensaje dependiendo del campo "problema".
#
# Requisitos:
#   pip install pymysql python-dotenv

import os
import time
from urllib.parse import urlparse
import pymysql
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

# --- CONFIGURACIÓN BD --------------------------------------------------------


def _parse_db_url():
    """
    Obtiene los datos de conexión desde:
    - SQLALCHEMY_DATABASE_URI (si existe)
    - o DATABASE_URL
    - o un valor por defecto

    Formato esperado: mysql+pymysql://user:pass@host/dbname?charset=utf8mb4
    """
    url = (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or "mysql+pymysql://root:hola@127.0.0.1/sistemaAcceso?charset=utf8mb4"
    )

    parsed = urlparse(url)

    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "database": (parsed.path or "/sistemaAcceso").lstrip("/"),
    }


DB_CONFIG = _parse_db_url()


def obtener_conexion():
    """
    Crea una conexión nueva a MySQL usando pymysql.
    """
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


# --- TABLAS A VIGILAR --------------------------------------------------------

MONITORED_TABLES = ("alumnos", "profesores", "bloqueados", "no_inscritos")


def asegurar_tabla_monitor(cur):
    """
    Crea la tabla monitor_notificaciones si no existe
    y se asegura de que haya una fila por cada tabla monitoreada.
    """
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_notificaciones (
          id INT PRIMARY KEY AUTO_INCREMENT,
          nombre_tabla VARCHAR(50) NOT NULL UNIQUE,
          ultimo_id_revisado INT NOT NULL DEFAULT 0
        )
        """
    )

    for nombre in MONITORED_TABLES:
        # INSERT IGNORE evita error si ya existe
        cur.execute(
            """
            INSERT IGNORE INTO monitor_notificaciones (nombre_tabla, ultimo_id_revisado)
            VALUES (%s, 0)
            """,
            (nombre,),
        )


def obtener_ultimo_id_revisado(cur, nombre_tabla):
    """
    Devuelve el ultimo_id_revisado para una tabla.
    Si no existe el registro, lo crea en 0.
    """
    cur.execute(
        "SELECT ultimo_id_revisado FROM monitor_notificaciones WHERE nombre_tabla = %s",
        (nombre_tabla,),
    )
    fila = cur.fetchone()

    if fila is None:
        cur.execute(
            "INSERT INTO monitor_notificaciones (nombre_tabla, ultimo_id_revisado) VALUES (%s, 0)",
            (nombre_tabla,),
        )
        return 0

    return fila["ultimo_id_revisado"]


def actualizar_ultimo_id_revisado(cur, nombre_tabla, nuevo_ultimo_id):
    """
    Actualiza el ultimo_id_revisado de una tabla.
    """
    cur.execute(
        """
        UPDATE monitor_notificaciones
        SET ultimo_id_revisado = %s
        WHERE nombre_tabla = %s
        """,
        (nuevo_ultimo_id, nombre_tabla),
    )


# --- INSERCIÓN DE NOTIFICACIONES --------------------------------------------


def insertar_notificacion(cur, texto, riesgo="Bajo", actor="sistema"):
    """
    Inserta una notificación en la tabla `notificaciones`.

    Campos usados:
      - actor        : 'sistema' por defecto, o el que se pase (por ej. 'dock')
      - notificacion : texto corto
      - motivo       : mismo texto (por ahora)
      - fecha        : CURDATE()
      - hora         : HH:MM
      - riesgo       : 'Bajo' / 'Medio' / 'Alto'
      - leida        : 0 (no leída)
    """
    sql = """
        INSERT INTO notificaciones (actor, notificacion, fecha, hora, motivo, riesgo, leida)
        VALUES (%s, %s, CURDATE(), DATE_FORMAT(NOW(), '%%H:%%i'), %s, %s, 0)
    """
    cur.execute(sql, (actor, texto, texto, riesgo))


# --- PROCESADORES POR TABLA --------------------------------------------------


def procesar_alumnos_nuevos(cur):
    nombre_tabla = "alumnos"
    ultimo_id = obtener_ultimo_id_revisado(cur, nombre_tabla)

    cur.execute(
        "SELECT id, nombre FROM alumnos WHERE id > %s ORDER BY id ASC",
        (ultimo_id,),
    )
    filas = cur.fetchall()
    if not filas:
        return

    max_id = ultimo_id

    for fila in filas:
        alumno_id = fila["id"]
        nombre = fila.get("nombre") or "Alumno sin nombre"

        texto = f"{nombre} se ha registrado correctamente"
        insertar_notificacion(cur, texto, riesgo="Bajo")

        if alumno_id > max_id:
            max_id = alumno_id

    actualizar_ultimo_id_revisado(cur, nombre_tabla, max_id)
    print(f"[vigilante] Nuevos alumnos procesados hasta id {max_id}")


def procesar_profesores_nuevos(cur):
    nombre_tabla = "profesores"
    ultimo_id = obtener_ultimo_id_revisado(cur, nombre_tabla)

    cur.execute(
        "SELECT id, nombre FROM profesores WHERE id > %s ORDER BY id ASC",
        (ultimo_id,),
    )
    filas = cur.fetchall()
    if not filas:
        return

    max_id = ultimo_id

    for fila in filas:
        profesor_id = fila["id"]
        nombre = fila.get("nombre") or "Profesor sin nombre"

        texto = f"{nombre} se ha registrado correctamente"
        insertar_notificacion(cur, texto, riesgo="Bajo")

        if profesor_id > max_id:
            max_id = profesor_id

    actualizar_ultimo_id_revisado(cur, nombre_tabla, max_id)
    print(f"[vigilante] Nuevos profesores procesados hasta id {max_id}")


def procesar_bloqueados_nuevos(cur):
    nombre_tabla = "bloqueados"
    ultimo_id = obtener_ultimo_id_revisado(cur, nombre_tabla)

    # Solo necesitamos id y url para buscar el nombre real
    cur.execute(
        "SELECT id, url FROM bloqueados WHERE id > %s ORDER BY id ASC",
        (ultimo_id,),
    )
    filas = cur.fetchall()
    if not filas:
        return

    max_id = ultimo_id

    for fila in filas:
        bloqueado_id = fila["id"]
        url = fila.get("url")

        nombre = None

        if url:
            # 1) Intentar buscar en alumnos por url
            cur.execute(
                "SELECT nombre FROM alumnos WHERE url = %s LIMIT 1",
                (url,),
            )
            res = cur.fetchone()
            if res and res.get("nombre"):
                nombre = res["nombre"]

            # 2) Si no está en alumnos, probar en profesores
            if not nombre:
                cur.execute(
                    "SELECT nombre FROM profesores WHERE url = %s LIMIT 1",
                    (url,),
                )
                res = cur.fetchone()
                if res and res.get("nombre"):
                    nombre = res["nombre"]

            # 3) Si tampoco, probar en no_inscritos
            if not nombre:
                cur.execute(
                    "SELECT nombre FROM no_inscritos WHERE url = %s LIMIT 1",
                    (url,),
                )
                res = cur.fetchone()
                if res and res.get("nombre"):
                    nombre = res["nombre"]

        if not nombre:
            nombre = "Usuario"

        texto = f"{nombre} fue bloqueado del sistema"
        insertar_notificacion(cur, texto, riesgo="Medio")

        if bloqueado_id > max_id:
            max_id = bloqueado_id

    actualizar_ultimo_id_revisado(cur, nombre_tabla, max_id)
    print(f"[vigilante] Nuevos bloqueados procesados hasta id {max_id}")


def procesar_no_inscritos_nuevos(cur):
    nombre_tabla = "no_inscritos"
    ultimo_id = obtener_ultimo_id_revisado(cur, nombre_tabla)

    cur.execute(
        "SELECT id, nombre FROM no_inscritos WHERE id > %s ORDER BY id ASC",
        (ultimo_id,),
    )
    filas = cur.fetchall()
    if not filas:
        return

    max_id = ultimo_id

    for fila in filas:
        no_inscrito_id = fila["id"]
        nombre = fila.get("nombre") or "Usuario"

        texto = f"{nombre} no se pudo registrar al sistema"
        insertar_notificacion(cur, texto, riesgo="Bajo")

        if no_inscrito_id > max_id:
            max_id = no_inscrito_id

    actualizar_ultimo_id_revisado(cur, nombre_tabla, max_id)
    print(f"[vigilante] Nuevos no_inscritos procesados hasta id {max_id}")


# --- TEXTO PERSONALIZADO PARA DOCKS ------------------------------------------


def construir_texto_dock(dock_id, problema):
    """
    Construye el texto de la notificación para un dock,
    según el contenido del campo 'problema'.
    """
    problema = (problema or "").strip()

    if problema.lower() == "atasco detectado durante cierre":
        return f"El dock {dock_id} presento atasco durante el cierre"
    elif problema.lower() == "atasco detectado durante apertura":
        return f"El dock {dock_id} sufrió atasco durante la apertura"
    else:
        # Comportamiento predeterminado:
        # si hay texto en problema, lo usamos tal cual,
        # si no, usamos el mensaje genérico.
        if problema:
            return problema
        return f"El dock {dock_id} se encuentra inactivo."


# --- VIGILANCIA DE DOCKS -----------------------------------------------------


def procesar_docks_inactivos(cur):
    """
    Vigila la tabla dock.
    Si un dock tiene status 'inactivo', generamos una notificación
    la primera vez que lo vemos en ese estado, y cada vez que cambie
    de otro estado a 'inactivo'.

    - actor  : 'dock'
    - riesgo : 'Alto'
    - notificacion/motivo : texto construido a partir de 'problema'.
    """
    # Tabla auxiliar para recordar el último status de cada dock
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_dock_status (
          dock_id INT PRIMARY KEY,
          ultimo_status TEXT
        )
        """
    )

    # Leemos todos los docks
    cur.execute("SELECT id, status, problema FROM dock")
    docks = cur.fetchall()
    if not docks:
        print("[vigilante] No hay docks en la tabla dock.")
        return

    for d in docks:
        dock_id = d["id"]
        # Normalizamos status por si trae mayúsculas o espacios
        status = (d.get("status") or "").strip().lower()
        problema = (d.get("problema") or "").strip()

        # Leer último status guardado
        cur.execute(
            "SELECT ultimo_status FROM monitor_dock_status WHERE dock_id = %s",
            (dock_id,),
        )
        row = cur.fetchone()

        if row is None:
            # Primera vez que vemos este dock: lo registramos
            cur.execute(
                "INSERT INTO monitor_dock_status (dock_id, ultimo_status) VALUES (%s, %s)",
                (dock_id, status),
            )

            # Si YA está inactivo en este momento, mandamos 1 notificación
            if status == "inactivo":
                texto = construir_texto_dock(dock_id, problema)
                print(f"[vigilante] (dock {dock_id}) status inicial INACTIVO → notifico: {texto}")
                insertar_notificacion(
                    cur,
                    texto=texto,
                    riesgo="Alto",
                    actor="dock",
                )
            else:
                print(f"[vigilante] (dock {dock_id}) status inicial '{status}', solo lo registro.")
            continue

        ultimo_status = (row.get("ultimo_status") or "").strip().lower()

        # Caso importante:
        # Si antes NO estaba inactivo y ahora SÍ → notificación
        if status == "inactivo" and ultimo_status != "inactivo":
            texto = construir_texto_dock(dock_id, problema)
            print(f"[vigilante] (dock {dock_id}) CAMBIO a INACTIVO → notifico: {texto}")
            insertar_notificacion(
                cur,
                texto=texto,
                riesgo="Alto",
                actor="dock",
            )

        # Actualizar si cambió el status
        if status != ultimo_status:
            cur.execute(
                "UPDATE monitor_dock_status SET ultimo_status = %s WHERE dock_id = %s",
                (status, dock_id),
            )

    print("[vigilante] Revisado estado de docks (status inactivo).")


# --- CICLO PRINCIPAL ---------------------------------------------------------

INTERVALO_SEGUNDOS = 5


def ciclo_vigilante():
    print(
        f"[vigilante] Iniciando vigilante de notificaciones. "
        f"Intervalo: {INTERVALO_SEGUNDOS} segundos"
    )
    print(
        f"[vigilante] BD: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
        f"{DB_CONFIG['database']}"
    )

    while True:
        try:
            conn = obtener_conexion()
            cur = conn.cursor()

            # Asegurarnos de que la tabla de monitor exista
            asegurar_tabla_monitor(cur)

            # Procesar cada tabla
            procesar_alumnos_nuevos(cur)
            procesar_profesores_nuevos(cur)
            procesar_bloqueados_nuevos(cur)
            procesar_no_inscritos_nuevos(cur)
            procesar_docks_inactivos(cur)

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            # En producción podrías loguear esto en archivo
            print(f"[vigilante] Error en el ciclo: {e}")

        # Esperar antes de la siguiente revisión
        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == "__main__":
    ciclo_vigilante()
