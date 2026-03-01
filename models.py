from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Administrador(UserMixin, db.Model):
    __tablename__ = "administrador"  # coincide con tu tabla

    id = db.Column(db.Integer, primary_key=True)
    no_empleado = db.Column(db.Text)
    nombre = db.Column(db.Text)
    apellido = db.Column(db.Text)
    correo_institucional = db.Column(db.Text, unique=True)
    telefono = db.Column(db.Text)
    contrasena = db.Column(db.Text)  # puede venir en claro o hasheada (ver métodos)

    def get_id(self):
        return str(self.id)

    def set_password(self, password: str):
        self.contrasena = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Soporta dos casos:
        - Hasheado con werkzeug (prefijo 'pbkdf2:')
        - Texto plano (mientras migras)
        """
        if self.contrasena and self.contrasena.startswith("pbkdf2:"):
            return check_password_hash(self.contrasena, password)
        return self.contrasena == password
