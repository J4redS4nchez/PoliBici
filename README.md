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

##  Imagenes

- Dock
![1](https://github.com/user-attachments/assets/9d4803b7-281b-43b3-a0b5-815be919d7eb)

- Interfaz del dock
![2](https://github.com/user-attachments/assets/e7ff8d38-0f22-41c7-b4f6-1d0128b137b2)

- Dashboard
![3](https://github.com/user-attachments/assets/cf0ef092-eb86-40ca-a8a0-d605a7d0cfe4)

- Docks
![4](https://github.com/user-attachments/assets/dfa5f541-1641-4822-a97c-6b398551a97d)

- Configuración
![5](https://github.com/user-attachments/assets/c2458a90-8d7a-4f39-b0ec-efc0f42d7c38)

- Notificaciones
![6](https://github.com/user-attachments/assets/629d3217-fdd3-47b2-ac68-4b5091442153)
