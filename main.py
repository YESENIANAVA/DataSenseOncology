import os
import shutil
import uvicorn
import sqlite3
import ia_engine
import face_recognition
import io
from typing import Optional
from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from pydantic import BaseModel
from fastapi import Query

import auth
import database

# Creamos moldes estrictos para recibir el JSON
class Medicion(BaseModel):
    fecha: str
    volumen: float
    tratamiento: bool

# --- MODELOS DE DATOS (Para recibir JSON desde la web) ---
class DatosPrediccionClinica(BaseModel):
    paciente_id: int
    medico: str
    re: float
    rp: float
    her2: float
    ki67: float
    grado: int
    tamano: float
    ilv: int
    margenes: int
    ganglios_pos: int
    ganglios_tot: int

class ConsultaPaciente(BaseModel):
    paciente_id: int

class DatosGuardarPrediccion(BaseModel):
    paciente_id: int
    dias_analizados: int
    tasa_crecimiento: float
    volumen_actual: float
    tendencia: str
    medico_operando: Optional[str] = None

app = FastAPI()

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")
templates_path = os.path.join(BASE_DIR, "templates")

if not os.path.exists(static_path):
    os.makedirs(static_path)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

@app.post("/verificar_biometria")
async def verificar_biometria(username: str = Form(...), foto_capturada: UploadFile = File(...)):
    # 1. Buscamos al doctor en la base de datos para saber cómo se llama su foto de perfil
    doctor = database.obtener_datos_doctor(username)
    if not doctor:
        return {"status": "error", "mensaje": "Usuario no encontrado en el sistema."}
    
    # 2. Armamos la ruta de su foto de perfil guardada en /static
    nombre_foto_db = doctor['foto_ruta']
    ruta_foto_db = os.path.join(static_path, nombre_foto_db)
    
    if not os.path.exists(ruta_foto_db) or nombre_foto_db == "default_doc.png":
        return {"status": "error", "mensaje": "El usuario no tiene una foto biométrica registrada."}

    try:
        # 3. Leemos la foto de la base de datos y le extraemos los "puntos faciales"
        imagen_db = face_recognition.load_image_file(ruta_foto_db)
        encodings_db = face_recognition.face_encodings(imagen_db)
        if not encodings_db:
            return {"status": "error", "mensaje": "No se detectó un rostro claro en la foto de perfil."}
        rostro_oficial = encodings_db[0] # Guardamos el mapa 3D del rostro

        # 4. Leemos la foto que acaba de tomar la cámara web
        contenido_webcam = await foto_capturada.read()
        imagen_webcam = face_recognition.load_image_file(io.BytesIO(contenido_webcam))
        encodings_webcam = face_recognition.face_encodings(imagen_webcam)
        
        if not encodings_webcam:
            return {"status": "error", "mensaje": "No se detectó ningún rostro en la cámara. Acércate más."}
        rostro_camara = encodings_webcam[0]

        # 5. EL MOMENTO DE LA VERDAD: Comparamos los rostros (Tolerancia 0.6 es el estándar de seguridad)
        coincide = face_recognition.compare_faces([rostro_oficial], rostro_camara, tolerance=0.6)

        if coincide[0]:
            database.registrar_log(username, "FACE ID EXITOSO", "Validación biométrica correcta para recuperación de contraseña.")
            return {"status": "success", "mensaje": "¡Identidad confirmada!"}
        else:
            database.registrar_log(username, "ALERTA DE SEGURIDAD", "Intento de recuperación fallido. El rostro no coincide.")
            return {"status": "error", "mensaje": "Acceso Denegado: El rostro no coincide con el expediente."}

    except Exception as e:
        return {"status": "error", "mensaje": f"Error del servidor biométrico: {str(e)}"}
    
    
# --- INICIALIZACIÓN ---
database.inicializar_db()


# --- ACCESO Y LOGIN ---

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/recuperar", response_class=HTMLResponse)
async def recuperar_page(request: Request):
    return templates.TemplateResponse("recuperar.html", {"request": request})

@app.post("/login")
async def handle_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if database.verificar_credenciales(username, password):
        database.registrar_log(username, "ACCESO EXITOSO", "Inicio de sesión validado correctamente en el sistema.")
        return RedirectResponse(url=f"/dashboard?user={username}", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas"})

@app.get("/logout")
async def cerrar_sesion(user: str):
    # Registramos la salida antes de enviarlo a la pantalla de login
    if user:
        database.registrar_log(user, "CIERRE DE SESIÓN", "El usuario cerró su sesión y salió del sistema de forma segura.")
    return RedirectResponse(url="/", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: str):
    doctor = database.obtener_datos_doctor(user)
    if not doctor: return RedirectResponse(url="/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "doctor": doctor})


# --- GESTIÓN DE PACIENTES (Tu nueva sección) ---

@app.get("/gestion_pacientes", response_class=HTMLResponse)
async def gestion_pacientes_page(request: Request, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion: 
        return RedirectResponse(url="/")
    
    # Obtenemos la lista de pacientes registrados
    lista_pacientes = database.obtener_todos_los_pacientes()
    
    # Apuntamos exactamente a tu archivo pacientes.html
    return templates.TemplateResponse("pacientes.html", {
        "request": request, 
        "doctor": doctor_sesion,
        "pacientes": lista_pacientes
    })

@app.post("/guardar_paciente")
async def handle_guardar_paciente(
    nombre_completo: str = Form(...), 
    edad: str = Form(...), # Lo cambiamos a str para que acepte el envío del form y luego lo validamos
    genero: str = Form(...), 
    tipo_sangre: str = Form(...),
    medico_asignado: str = Form(...),
    direccion: Optional[str] = Form(""),
    telefono: Optional[str] = Form(""), 
    estado_civil: Optional[str] = Form(""),
    religion: Optional[str] = Form(""), 
    enfermedad_cronica: Optional[str] = Form(""), 
    antecedentes_patologicos: Optional[str] = Form(""),
    antecedentes_heredofamiliares: Optional[str] = Form(""), 
    paciente_id: Optional[str] = Form(None) 
):
    # Convertimos edad a entero de forma segura
    try:
        edad_int = int(edad)
    except:
        edad_int = 0

    datos = {
        "nombre_completo": nombre_completo, "edad": edad_int, "genero": genero,
        "direccion": direccion, "telefono": telefono, "estado_civil": estado_civil,
        "religion": religion, "tipo_sangre": tipo_sangre, "enfermedad_cronica": enfermedad_cronica,
        "antecedentes_patologicos": antecedentes_patologicos,
        "antecedentes_heredofamiliares": antecedentes_heredofamiliares,
        "medico_asignado": medico_asignado
    }
    
    if paciente_id and paciente_id.strip() and paciente_id != "None":
        database.actualizar_paciente(paciente_id, datos)
        database.registrar_log(medico_asignado, "ACTUALIZACIÓN", f"Datos modificados para {nombre_completo} (ID: {paciente_id}).")
    else:
        database.guardar_paciente(datos)
        database.registrar_log(medico_asignado, "NUEVO PACIENTE", f"Expediente creado para {nombre_completo}.")
    
    return RedirectResponse(url=f"/gestion_pacientes?user={medico_asignado}", status_code=303)

# --- HISTORIAL MÉDICO Y PERFIL ---

@app.get("/historial_medico", response_class=HTMLResponse)
async def historial_medico_page(
    request: Request, 
    user: str, 
    paciente_id: int = Query(None)
):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion:
        return RedirectResponse(url="/")

    todos_los_pacientes = database.obtener_todos_los_pacientes()
    
    datos_paciente = None
    diagnostico = None
    patologia = None
    predicciones_guardadas = []

    if paciente_id:
        datos_paciente = database.obtener_paciente_por_id(paciente_id) 
        # AHORA LEEMOS LA FASE 1 Y LA FASE 2
        diagnostico = database.obtener_diagnostico_paciente(paciente_id)
        patologia = database.obtener_patologia_por_paciente(paciente_id)
        
        predicciones_guardadas = database.obtener_predicciones_por_paciente(paciente_id)

    return templates.TemplateResponse("historial.html", {
        "request": request,
        "doctor": doctor_sesion,
        "pacientes": todos_los_pacientes,
        "paciente_seleccionado": datos_paciente,
        "diagnostico": diagnostico,  # Enviamos Fase 1 al HTML
        "patologia": patologia,      # Enviamos Fase 2 al HTML
        "predicciones": predicciones_guardadas
    })


@app.get("/historial/{paciente_id}", response_class=HTMLResponse)
async def perfil_paciente_page(request: Request, paciente_id: int, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion: return RedirectResponse(url="/")
    
    # Buscamos los datos específicos con el nuevo formato
    paciente = database.obtener_paciente_por_id(paciente_id)
    diagnostico = database.obtener_diagnostico_paciente(paciente_id)
    patologia = database.obtener_patologia_por_paciente(paciente_id)
    
    return templates.TemplateResponse("perfil_paciente.html", {
        "request": request,
        "doctor": doctor_sesion,
        "paciente": paciente,
        "diagnostico": diagnostico,
        "patologia": patologia
    })

# --- GESTIÓN DE USUARIOS (MÉDICOS) ---

@app.get("/gestion_usuarios", response_class=HTMLResponse)
async def gestion_usuarios_page(request: Request, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    
    # CANDADO: Si no hay sesión o el nivel es 0 (Médico), lo regresamos al Dashboard
    if not doctor_sesion or doctor_sesion['nivel_acceso'] < 1:
        return RedirectResponse(url=f"/dashboard?user={user}", status_code=303)

    # Si pasa el candado, cargamos la lista de usuarios
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    usuarios = [dict(row) for row in conn.execute("SELECT * FROM usuarios").fetchall()]
    conn.close()

    return templates.TemplateResponse("usuarios.html", {"request": request, "doctor": doctor_sesion, "usuarios": usuarios})

# --- OTROS PROCESOS ---

@app.post("/crear_usuario")
async def crear_usuario(
    nombre: str = Form(...),
    especialidad: str = Form(...),
    cedula: str = Form(...),
    password: str = Form(...),
    nivel_acceso: int = Form(...),
    admin_operando: str = Form(...),
    foto: UploadFile = File(None)
):
    # 1. Consultamos el rango real de quien está creando al usuario
    datos_operando = database.obtener_datos_doctor(admin_operando)
    rango_operador = datos_operando['nivel_acceso'] if datos_operando else 0

    # CANDADO DE SEGURIDAD 1: Si un doctor nivel 0 hackea el formulario para llegar aquí, lo expulsamos.
    if rango_operador < 1:
        database.registrar_log(admin_operando, "INTRUSIÓN BLOQUEADA", "Un usuario sin permisos intentó crear un nuevo médico.")
        return RedirectResponse(url=f"/dashboard?user={admin_operando}", status_code=303)

    # 2. Lógica de Poder Blindada:
    if rango_operador == 2:
        # El SuperAdmin es el rey, asigna el nivel que se haya elegido en el formulario
        nivel_final = nivel_acceso 
    else:
        # Un Admin (Nivel 1) JAMÁS podrá crear a alguien de su mismo nivel o superior. 
        # Lo forzamos incondicionalmente a Nivel 0 (Doctor) sin importar qué mande el formulario HTML.
        nivel_final = 0
    
    username_generado = database.generar_id_automatico(nombre)
    nombre_foto = "default_doc.png"
    
    if foto and foto.filename:
        extension = os.path.splitext(foto.filename)[1]
        nombre_foto = f"perfil_{username_generado}{extension}"
        with open(os.path.join(static_path, nombre_foto), "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

    database.registrar_nuevo_medico(username_generado, password, nombre, especialidad, cedula, nombre_foto, nivel_final)
    
    database.registrar_log(admin_operando, "NUEVO MÉDICO", f"Se dio de alta al Dr(a). {nombre} ({username_generado}) con Nivel de Acceso {nivel_final}.")
    return RedirectResponse(url=f"/gestion_usuarios?user={admin_operando}", status_code=303)



@app.get("/bitacora", response_class=HTMLResponse)
async def bitacora_page(request: Request, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    
    # CANDADO: Exactamente el mismo bloqueo
    if not doctor_sesion or doctor_sesion['nivel_acceso'] < 1:
        return RedirectResponse(url=f"/dashboard?user={user}", status_code=303)

    registros = database.obtener_todos_los_logs()
    return templates.TemplateResponse("bitacora.html", {"request": request, "doctor": doctor_sesion, "logs": registros})

@app.post("/actualizar_usuario")
async def actualizar_usuario(
    usuario_id: int = Form(...),
    nombre: str = Form(...),
    especialidad: str = Form(...),
    cedula: str = Form(...),
    password: str = Form(None),
    nivel_acceso: int = Form(...),
    admin_operando: str = Form(...),
    foto: UploadFile = File(None)
):
    # 1. Recuperamos los datos actuales para respaldo
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    user_actual = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    conn.close()
    
    if not user_actual:
        return RedirectResponse(url=f"/gestion_usuarios?user={admin_operando}", status_code=303)

    # Verificamos quién edita
    datos_operando = database.obtener_datos_doctor(admin_operando)
    rango_operador = datos_operando['nivel_acceso'] if datos_operando else 0

    # CANDADO DE SEGURIDAD 2 (Jerarquía Absoluta): 
    # Menor O IGUAL (<=). Un admin no puede editar a otro admin, solo a sí mismo.
    if rango_operador <= user_actual['nivel_acceso'] and datos_operando['username'] != user_actual['username']:
        database.registrar_log(admin_operando, "HACKEO EVITADO", f"Intentó modificar el perfil de un igual o superior: {user_actual['username']}.")
        return RedirectResponse(url=f"/gestion_usuarios?user={admin_operando}", status_code=303)
    
    # CANDADO DE SEGURIDAD 3 (El que faltaba - Evita auto-ascensos):
    if rango_operador == 2:
        nivel_final = nivel_acceso
    else:
        nivel_final = user_actual['nivel_acceso']
    
    # 3. Mantenemos la foto actual si no se sube una nueva
    nombre_foto = user_actual['foto_ruta']
    if foto and foto.filename:
        extension = os.path.splitext(foto.filename)[1]
        nombre_foto = f"perfil_{user_actual['username']}{extension}"
        with open(os.path.join(static_path, nombre_foto), "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
    
    database.update_medico(usuario_id, nombre, especialidad, cedula, password, nivel_final, nombre_foto)
    database.registrar_log(admin_operando, "EDICIÓN DE PERFIL", f"Se actualizaron los datos, permisos o contraseña del usuario: {user_actual['username']}.")
    return RedirectResponse(url=f"/gestion_usuarios?user={admin_operando}", status_code=303)

@app.post("/eliminar_usuario/{id_objetivo}")
async def borrar_medico(id_objetivo: int, admin_operando: str = Form(...)):
    # 1. Obtenemos el nivel real del que dio el clic
    datos_operando = database.obtener_datos_doctor(admin_operando)
    nivel_operador = datos_operando['nivel_acceso'] if datos_operando else 0

    # 2. Mandamos su nivel real a la base de datos (quitamos el 2 hardcodeado)
    exito = database.eliminar_usuario(id_objetivo, nivel_operador)
    
    if exito:
        database.registrar_log(admin_operando, "BAJA DE USUARIO", f"Se eliminó al médico con ID: {id_objetivo}.")
    else:
        database.registrar_log(admin_operando, "BLOQUEO DE BORRADO", f"Intento sin permisos para borrar ID: {id_objetivo}.")
        
    # 3. Lo regresamos a SU propia sesión, no a la del SuperAdmin
    return RedirectResponse(url=f"/gestion_usuarios?user={admin_operando}", status_code=303)

# --- RUTA PARA MOSTRAR EL FORMULARIO ONCOLÓGICO ---
@app.get("/informacion_oncologica", response_class=HTMLResponse)
async def informacion_oncologica_page(request: Request, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion: 
        return RedirectResponse(url="/")
    
    # Necesitamos la lista de pacientes para el menú desplegable (Select)
    lista_pacientes = database.obtener_todos_los_pacientes()
    
    return templates.TemplateResponse("tumores.html", {
        "request": request, 
        "doctor": doctor_sesion,
        "pacientes": lista_pacientes
    })

# --- RUTA PARA GUARDAR LOS DATOS DEL TUMOR ---
@app.post("/guardar_tumor")
async def handle_guardar_tumor(
    # --- FASE 1: OBLIGATORIOS ---
    paciente_id: int = Form(...),
    metodo_deteccion: str = Form(...),
    tamano_aparente_mm: float = Form(...),
    clasificacion: str = Form(...),
    medico: str = Form(...),
    observaciones: Optional[str] = Form(""),
    
    # --- FASE 2: OPCIONALES (Vienen vacíos si es Benigno) ---
    re: Optional[str] = Form(""),
    rp: Optional[str] = Form(""),
    her2: Optional[str] = Form(""),
    ki67: Optional[str] = Form(""),
    tipo_histologico: Optional[str] = Form(""),
    grado_histologico: Optional[str] = Form(""),
    tamano_tumor_mm: Optional[str] = Form(""),
    ilv: Optional[str] = Form(""),
    margenes: Optional[str] = Form(""),
    ganglios_analizados: Optional[str] = Form(""),
    ganglios_positivos: Optional[str] = Form("")
):
    # 1. Siempre guardamos la Fase 1 (Diagnóstico Inicial)
    database.guardar_diagnostico_fase1(
        paciente_id, metodo_deteccion, tamano_aparente_mm, clasificacion, observaciones
    )
    
    # 2. Evaluamos la lógica: ¿Es Maligno?
    if clasificacion == "Maligno":
        # Convertimos los textos a números de forma segura para no romper SQLite
        ki67_val = int(ki67) if ki67 and ki67.strip() else 0
        tamano_patologia_val = float(tamano_tumor_mm) if tamano_tumor_mm and tamano_tumor_mm.strip() else 0.0
        g_analizados_val = int(ganglios_analizados) if ganglios_analizados and ganglios_analizados.strip() else 0
        g_positivos_val = int(ganglios_positivos) if ganglios_positivos and ganglios_positivos.strip() else 0
        
        datos_fase2 = {
            'paciente_id': paciente_id,
            're': re,
            'rp': rp,
            'her2': her2,
            'ki67': ki67_val,
            'tipo_histologico': tipo_histologico,
            'grado_histologico': grado_histologico,
            'tamano_tumor_mm': tamano_patologia_val,
            'ilv': ilv,
            'margenes': margenes,
            'ganglios_analizados': g_analizados_val,
            'ganglios_positivos': g_positivos_val
        }
        
        # Guardamos el perfil avanzado
        database.guardar_patologia_fase2(datos_fase2)
        
        # Log detallado de caso de cáncer
        database.registrar_log(medico, "PATOLOGÍA MALIGNA", f"Expediente oncológico completo (Fase 1 y 2) guardado para paciente #{paciente_id}.")
    else:
        # Log simple de tumor benigno
        database.registrar_log(medico, "DIAGNÓSTICO BENIGNO", f"Evaluación por {metodo_deteccion} registrada como Benigna para paciente #{paciente_id}.")
        
    # 3. Redirigimos de vuelta a la pantalla de tumores
    return RedirectResponse(url=f"/informacion_oncologica?user={medico}", status_code=303)

@app.get("/prediccion_crecimiento", response_class=HTMLResponse)
async def prediccion_crecimiento_page(request: Request, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion: 
        return RedirectResponse(url="/")
    
    # Obtenemos los pacientes para alimentar el buscador interactivo
    lista_pacientes = database.obtener_todos_los_pacientes()
    
    return templates.TemplateResponse("prediccion.html", {
        "request": request, 
        "doctor": doctor_sesion,
        "pacientes": lista_pacientes
    })

@app.post("/calcular_prediccion_clinica")
async def calcular_prediccion_clinica(consulta: ConsultaPaciente):
    # 1. Traer los datos directamente de la base de datos
    patologia = database.obtener_patologia_por_paciente(consulta.paciente_id)
    
    if not patologia:
        return {"error": "El paciente seleccionado no tiene un perfil patológico (Fase 2) registrado. Vaya a 'Info Onc' para registrarlo primero."}

    # 2. Función traductora (Convierte "Positivo"/"Presente" a 1, y lo demás a 0)
    def a_binario(texto, clave_positiva):
        if not texto: return 0
        return 1 if clave_positiva.lower() in str(texto).lower() else 0

    # 3. Empaquetar y traducir los datos para el motor IA
    datos_ia = {
        're': a_binario(patologia['re'], 'positivo'),
        'rp': a_binario(patologia['rp'], 'positivo'),
        'her2': 1 if patologia['her2'] and 'positivo' in str(patologia['her2']).lower() else (0.5 if patologia['her2'] and 'equivoco' in str(patologia['her2']).lower() else 0),
        'ki67': float(patologia['ki67'] or 0),
        'grado': int(patologia['grado_histologico']) if patologia['grado_histologico'] and str(patologia['grado_histologico']).isdigit() else 1,
        'tamano': float(patologia['tamano_tumor_mm'] or 0),
        'ilv': a_binario(patologia['ilv'], 'presente'),
        'margenes': a_binario(patologia['margenes'], 'comprometidos'),
        'ganglios_pos': int(patologia['ganglios_positivos'] or 0),
        'ganglios_tot': int(patologia['ganglios_analizados'] or 0)
    }

    # 4. Ejecutar el modelo
    try:
        resultado_ia = ia_engine.evaluar_riesgo_clinico(datos_ia)
        return resultado_ia
    except Exception as e:
        print(f"Error en IA: {e}")
        return {"error": "Hubo un fallo matemático al procesar la IA."}

@app.post("/guardar_prediccion_historial")
async def guardar_prediccion_endpoint(datos: DatosGuardarPrediccion):
    try:
        # Guardamos en la base de datos
        database.guardar_prediccion_ia(
            datos.paciente_id,
            datos.dias_analizados,
            datos.tasa_crecimiento,
            datos.volumen_actual,
            datos.tendencia
        )
        
        # Registramos quién hizo el cálculo en la bitácora
        if datos.medico_operando:
            database.registrar_log(datos.medico_operando, "SEGUIMIENTO NUMÉRICO (IA)", f"Cálculo guardado. Tasa: {datos.tasa_crecimiento}%, Volumen: {datos.volumen_actual} mm³ (Paciente #{datos.paciente_id}).")
        
        return {"status": "success", "mensaje": "Guardado exitoso"}
    except Exception as e:
        print(f"Error en servidor al guardar: {e}") # Esto se verá en tu terminal negra
        return {"status": "error", "mensaje": str(e)}

@app.get("/historial/{paciente_id}", response_class=HTMLResponse)
async def historial_page(request: Request, paciente_id: int, user: str):
    doctor_sesion = database.obtener_datos_doctor(user)
    if not doctor_sesion: return RedirectResponse(url="/")
    
    # Buscamos los datos específicos
    paciente = database.obtener_paciente_por_id(paciente_id)
    tumores = database.obtener_tumores_por_paciente(paciente_id)
    
    return templates.TemplateResponse("perfil_paciente.html", {
        "request": request,
        "doctor": doctor_sesion,
        "paciente": paciente,
        "tumores": tumores
    })

@app.get("/ejecutar_ia/{paciente_id}")
async def ejecutar_ia(paciente_id: int):
    # 1. Buscamos el diagnóstico y la patología con el nuevo sistema
    diagnostico = database.obtener_diagnostico_paciente(paciente_id)
    patologia = database.obtener_patologia_por_paciente(paciente_id)
    
    if not diagnostico:
        return {"error": "No hay diagnóstico registrado para este paciente."}
    
    # 2. Lógica inteligente para obtener el diámetro (Prioridad: Patología > Imagen)
    diametro = 0.0
    if patologia and patologia['tamano_tumor_mm']:
        diametro = patologia['tamano_tumor_mm']
    elif diagnostico and diagnostico['tamano_aparente_mm']:
        diametro = diagnostico['tamano_aparente_mm']
        
    if diametro <= 0:
        return {"error": "El tamaño del tumor no es válido para ejecutar la predicción."}

    # 3. El truco de la Esfera Perfecta para no romper tu ia_engine actual
    # Como tu ia_engine.py todavía pide (largo, ancho, profundidad), 
    # le mandamos el mismo diámetro 3 veces para que matemáticamente lo trate como una esfera perfecta.
    resultado = ia_engine.predecir_crecimiento_ia(
        diametro,  # Simula el largo
        diametro,  # Simula el ancho
        diametro   # Simula la profundidad
    )
    
    # 4. Ajuste por si el tumor es Benigno
    if diagnostico['clasificacion'] == "Benigno":
        # Sobreescribimos el resultado del IA Engine porque los benignos no tienen crecimiento agresivo
        resultado['tasa_crecimiento'] = 0.0
        resultado['tendencia'] = "Estable (Benigno) - Riesgo Bajo"
        # Mantenemos el volumen inicial pero sin crecimiento proyectado
    
    return resultado

@app.get("/nueva_contrasena", response_class=HTMLResponse)
async def nueva_contrasena_page(request: Request, user: str):
    # Mostramos la pantalla para escribir la contraseña
    return templates.TemplateResponse("nueva_contrasena.html", {"request": request, "user": user})

@app.post("/guardar_nueva_contrasena")
async def guardar_nueva_contrasena(request: Request, user: str = Form(...), password: str = Form(...), confirm_password: str = Form(...)):
    # 1. Verificamos que no se haya equivocado al teclear
    if password != confirm_password:
        return templates.TemplateResponse("nueva_contrasena.html", {"request": request, "user": user, "error": "Las contraseñas no coinciden. Intenta de nuevo."})
    
    # 2. Guardamos la nueva contraseña en la base de datos
    database.cambiar_password(user, password)
    
    # 3. Registramos el movimiento en la bitácora de seguridad
    database.registrar_log(user, "CONTRASEÑA RESTABLECIDA", "El usuario cambió su contraseña exitosamente tras validación por Face ID.")
    
    # 4. Lo mandamos directo a su Dashboard, ¡ya con la sesión iniciada!
    return RedirectResponse(url=f"/dashboard?user={user}", status_code=303)

# (Rutas de crear/actualizar usuario se mantienen igual...)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)