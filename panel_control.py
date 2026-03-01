# panel_control.py
from flask import Blueprint, render_template
from flask_login import login_required

panel_control = Blueprint(
    "panel_control",        # nombre del blueprint
    __name__                # módulo actual
)

@panel_control.get("/panel")
@login_required
def mostrar_panel():
    # Renderiza templates/panel_control.html
    return render_template("panel_control.html")
