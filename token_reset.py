import jwt
import datetime
import hashlib

def generar_token_reset(correo, password_actual, secret_key):
    firma = hashlib.sha256(password_actual.encode()).hexdigest()

    payload = {
        "correo": correo,
        "firma": firma,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
    }

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token.decode() if isinstance(token, bytes) else token
