# dashboard_python/estadisticas.py
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from models import db
from sqlalchemy import text

estadisticas_bp = Blueprint("estadisticas_bp", __name__)


def contar_registros(tabla: str) -> int:
    """Cuenta registros de una tabla dada. Si algo falla, regresa 0."""
    try:
        resultado = db.session.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
        return resultado.scalar() or 0
    except Exception:
        return 0


def altura_barra(valor: int) -> int:
    """
    Convierte un valor (0..∞) a una altura en % para la gráfica (escala 0–10).
    - 0   -> 0%
    - 10  -> 100%
    - >10 -> 110% (sube un poquito más que el máximo)
    """
    if valor <= 0:
        return 0
    if valor <= 10:
        return int(valor * 100 / 10)
    # Si pasa de 10, que se vea ligeramente más alta que el máximo
    return 110


def registros_por_dia_historial():
    """
    Regresa una lista con la cantidad de registros en historial por día:
    índices 0..5 => [Lun, Mar, Mié, Jue, Vie, Sáb]
    SOLO lectura, no modifica la BD.
    """
    conteos = [0, 0, 0, 0, 0, 0]

    try:
        resultado = db.session.execute(text("""
            SELECT
              DAYOFWEEK(STR_TO_DATE(fecha, '%Y-%m-%d')) AS dia,
              COUNT(*) AS total
            FROM historial
            WHERE fecha IS NOT NULL AND fecha <> ''
            GROUP BY dia
        """))

        for row in resultado:
            dia = row[0]   # 1=Dom, 2=Lun, ..., 7=Sáb
            total = row[1] or 0
            if dia is None:
                continue

            # Queremos índices 0..5 => Lun..Sáb
            indice = dia - 2  # 2->0 (Lun), 3->1 (Mar), ..., 7->5 (Sáb)
            if 0 <= indice < 6:
                conteos[indice] = total

    except Exception:
        # Si algo falla, dejamos todos en 0
        pass

    return conteos


def calcular_estadisticas():
    """
    Calcula TODOS los datos que usan las gráficas de Estadísticas.
    Se usa tanto para el HTML como para el endpoint JSON.
    """
    # --- Conteos básicos ---
    alumnos = contar_registros("alumnos")
    profesores = contar_registros("profesores")
    no_inscritos = contar_registros("no_inscritos")
    bloqueados = contar_registros("bloqueados")

    # --- Pastel: alumnos vs profesores ---
    total_ap = alumnos + profesores
    if total_ap > 0:
        porc_alumnos = round(alumnos * 100 / total_ap)
        porc_profesores = 100 - porc_alumnos  # ajustamos para que sume 100
    else:
        porc_alumnos = 0
        porc_profesores = 0

    # --- Barras: cantidad de usuarios (0–10) ---
    altura_alumnos = altura_barra(alumnos)
    altura_profesores = altura_barra(profesores)
    altura_no_inscritos = altura_barra(no_inscritos)
    altura_bloqueados = altura_barra(bloqueados)

    # --- Registros por día (historial) ---
    # índices 0..5 => Lun, Mar, Mié, Jue, Vie, Sáb
    registros_dias = registros_por_dia_historial()
    reg_lun, reg_mar, reg_mie, reg_jue, reg_vie, reg_sab = registros_dias

    altura_lun = altura_barra(reg_lun)
    altura_mar = altura_barra(reg_mar)
    altura_mie = altura_barra(reg_mie)
    altura_jue = altura_barra(reg_jue)
    altura_vie = altura_barra(reg_vie)
    altura_sab = altura_barra(reg_sab)

    return {
        # Pastel
        "alumnos": alumnos,
        "profesores": profesores,
        "total_usuarios": total_ap,
        "porc_alumnos": porc_alumnos,
        "porc_profesores": porc_profesores,
        # Cantidad de usuarios (barras)
        "no_inscritos": no_inscritos,
        "bloqueados": bloqueados,
        "altura_alumnos": altura_alumnos,
        "altura_profesores": altura_profesores,
        "altura_no_inscritos": altura_no_inscritos,
        "altura_bloqueados": altura_bloqueados,
        # Registros por día
        "reg_lun": reg_lun,
        "reg_mar": reg_mar,
        "reg_mie": reg_mie,
        "reg_jue": reg_jue,
        "reg_vie": reg_vie,
        "reg_sab": reg_sab,
        "altura_lun": altura_lun,
        "altura_mar": altura_mar,
        "altura_mie": altura_mie,
        "altura_jue": altura_jue,
        "altura_vie": altura_vie,
        "altura_sab": altura_sab,
    }


@estadisticas_bp.get("/estadisticas/fragment")
@login_required
def fragment():
    """
    Devuelve el fragmento HTML de Estadísticas.
    """
    stats = calcular_estadisticas()
    return render_template("dashboard_html/estadisticas_fragment.html", **stats)


@estadisticas_bp.get("/estadisticas/api/data")
@login_required
def api_data():
    """
    Endpoint JSON para refrescar las gráficas en “tiempo real”.
    SOLO lectura.
    """
    stats = calcular_estadisticas()
    return jsonify(stats)
