import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()


class Config:
    # Clave secreta y sesión
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Base de datos
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "mysql+pymysql://root:hola@127.0.0.1/sistemaAcceso?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Config SMTP propia (la que ya tenías)
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    MAIL_SENDER = os.getenv("MAIL_SENDER", os.getenv("SMTP_USER", ""))

    # URL base de la app (para enlaces en correos)
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")

    # 🔥 Adaptación para Flask-Mail (lo que Flask-Mail sí usa)
    MAIL_SERVER = SMTP_SERVER
    MAIL_PORT = SMTP_PORT
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = SMTP_USER
    MAIL_PASSWORD = SMTP_PASS
    MAIL_DEFAULT_SENDER = MAIL_SENDER
