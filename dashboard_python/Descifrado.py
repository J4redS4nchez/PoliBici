# descifrado.py
# Desencriptador alfa-numérico (solo MAYÚSCULAS y dígitos)

# --- Configuración (idéntica a la de cifrado.py) ---
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
FILAS, COLUMNAS = 6, 6
SUBSTITUCION = {
    "0": "$", "1": "#", "2": "%", "3": "A", "4": "B",
    "5": "C", "6": "D", "7": "E", "8": "F", "9": "G"
}
INV_SUB = {v: k for k, v in SUBSTITUCION.items()}

# Construcción de tabla (fila, col) -> carácter
_rev = {}
for idx, ch in enumerate(CHARSET):
    f, c = divmod(idx, COLUMNAS)
    _rev[(f, c)] = ch

def desencriptar(cadena: str) -> str:
    """
    Revierte la sustitución y reconstruye el texto en MAYÚSCULAS y números.
    """
    digitos = []
    for ch in cadena:
        if ch not in INV_SUB:
            raise ValueError(f"Carácter inválido en cadena cifrada: {ch!r}")
        digitos.append(INV_SUB[ch])
    digitos = "".join(digitos)

    if len(digitos) % 2 != 0:
        raise ValueError("Longitud inválida: deben ser pares de coordenadas.")

    salida = []
    for i in range(0, len(digitos), 2):
        f = int(digitos[i])
        c = int(digitos[i+1])
        letra = _rev.get((f, c))
        if letra is None:
            raise ValueError(f"Coordenadas fuera de rango: ({f},{c})")
        salida.append(letra)
    return "".join(salida)
