# cifrado.py
# Encriptador alfa-numérico (solo MAYÚSCULAS y dígitos) por coordenadas + sustitución

# --- Configuración (compartida) ---
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 26 + 10 = 36 = 6x6
FILAS, COLUMNAS = 6, 6
SUBSTITUCION = {  # dígito -> símbolo/letra
    "0": "$", "1": "#", "2": "%", "3": "A", "4": "B",
    "5": "C", "6": "D", "7": "E", "8": "F", "9": "G"
}

# Construcción de tabla carácter -> (fila, columna)
_pos = {}
for idx, ch in enumerate(CHARSET):
    f, c = divmod(idx, COLUMNAS)
    _pos[ch] = (f, c)

def encriptar(texto: str) -> str:
    """
    Convierte cada carácter (MAYÚSCULA o dígito) a coordenadas encriptadas.
    Ignora todo lo que no esté en CHARSET.
    """
    salida = []
    for ch in texto.upper():  # fuerza mayúsculas
        if ch in _pos:
            f, c = _pos[ch]
            salida.append(SUBSTITUCION[str(f)])
            salida.append(SUBSTITUCION[str(c)])
    return "".join(salida)
