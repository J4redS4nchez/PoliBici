# PoliBICI (Flask)

Sistema web construido con **Flask** para administrar y monitorear docks/usuarios (tipo “acceso y control”), con **panel de control**, **dashboard**, **notificaciones** y **recuperación de contraseña por correo**.

##  Funcionalidades principales

- **Inicio de sesión** para administrador (Flask-Login).
- **Panel de control** protegido por sesión.
- **Dashboard** con:
  - Conteo de docks (total, en uso, fallas) y usuarios bloqueados.
  - Listado/estado de docks vía endpoints API.
- **Administración** (blueprints separados) para:
  - Docks
  - Usuarios
  - Administrador
  - Estadísticas
  - Notificaciones 
- **Recuperación de contraseña**:
  - Envío de enlace con **token** al correo institucional.
- **Generación de PDF** para reportes/usuarios.
- **Cifrado/descifrado**

##  Tecnologías

- Python 3.x
- Flask
- Flask-Login
- Flask-SQLAlchemy
- MySQL (con PyMySQL)
- python-dotenv
- Flask-Mail 
- ReportLab (PDF)
- PyJWT (tokens)

##  Requisitos

- **Python 3.10+** 
- **MySQL** (o MariaDB) activo
- Una base de datos con las tablas que usa el sistema

##  Instalación

1) Clona el repositorio:

```bash
git clone <tu-repo>
cd PoliBICI_FLASK
