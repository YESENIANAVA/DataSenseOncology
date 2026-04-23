En la carpeta de "Plantillas" se encuentra: login.html
este es el codigo de la interfaz de inicio de sesión
Permite que:
Ingrese su usuario
Ingrese su contraseña
Acceda al sistema
O recupere su acceso usando Face ID

recuperar.html
Es la pantalla de recuperación de contraseña mediante reconocimiento facial (Face ID).
Permite que el médico:
Ingrese su usuario
Active su cámara
Se tome una foto
El sistema verifica su identidad 
Si es correcto → lo manda a crear nueva contraseña

nueva_contrasena.html 
Es la pantalla para crear una nueva contraseña después de que el usuario (médico) ya fue verificado,
mediante Face ID. Es parte del módulo de recuperación de contraseña.

auth.py
Cifra contraseñas
Verifica contraseñas en el login

database.py
Controla:
Usuarios
Iniciar sesión
Bitácora
CRUD

main.py
Es el servidor principal hecho con FastAPI que:
Maneja rutas (URLs)
Conecta frontend ↔ backend
Controla usuarios, pacientes, IA y seguridad


