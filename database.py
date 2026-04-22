import sqlite3
from datetime import datetime
import auth
import re

def inicializar_db():
    """Crea la estructura completa de la base de datos."""
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # 1. Tabla de Usuarios (Médicos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT,
            especialidad TEXT,
            cedula TEXT,
            foto_ruta TEXT,
            nivel_acceso INTEGER DEFAULT 0
        )
    ''')
    
    # 2. Tabla de Bitácora
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bitacora (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            accion TEXT,
            fecha TIMESTAMP
        )
    ''')

    # 3. TABLA DE PACIENTES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            edad INTEGER,
            genero TEXT,
            direccion TEXT,
            telefono TEXT,
            estado_civil TEXT,
            religion TEXT,
            tipo_sangre TEXT,
            enfermedad_cronica TEXT,
            antecedentes_patologicos TEXT,
            antecedentes_heredofamiliares TEXT,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            medico_asignado TEXT
        )
    ''')

    # --- FASE 1: DIAGNÓSTICO INICIAL (Benigno vs Maligno) ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS diagnosticos_fase1 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_id INTEGER,
        fecha_diagnostico DATETIME DEFAULT CURRENT_TIMESTAMP,
        metodo_deteccion TEXT, -- Ej: Mastografía, Ultrasonido, Biopsia
        tamano_aparente_mm FLOAT,
        clasificacion TEXT NOT NULL, -- "Benigno" o "Maligno"
        observaciones TEXT,
        FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
    )''')

    # --- FASE 2: PATOLOGÍA AVANZADA (Solo para Malignos) ---
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS patologia_fase2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_id INTEGER UNIQUE, -- Un perfil patológico por paciente
        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
        
        -- Perfil Molecular
        re TEXT,
        rp TEXT,
        her2 TEXT,
        ki67 INTEGER,
        
        -- Morfología
        tipo_histologico TEXT,
        grado_histologico TEXT,
        tamano_tumor_mm FLOAT,
        
        -- Comportamiento Invasivo
        ilv TEXT,
        margenes TEXT,
        ganglios_analizados INTEGER,
        ganglios_positivos INTEGER,
        
        FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
    )''')

    conn.commit()
    conn.close()

# --- FUNCIONES DE APOYO ---

def generar_id_automatico(nombre):
    partes = nombre.lower().split()
    username = f"{partes[0][0]}{partes[1]}" if len(partes) >= 2 else partes[0]
    username = re.sub(r'[^a-z0-9]', '', username)
    return username


# --- GESTIÓN DE PACIENTES ---

def guardar_paciente(datos):
    """Guarda un paciente en la base de datos."""
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    query = '''
        INSERT INTO pacientes (
            nombre_completo, edad, genero, direccion, telefono, 
            estado_civil, religion, tipo_sangre, enfermedad_cronica, 
            antecedentes_patologicos, antecedentes_heredofamiliares, medico_asignado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    cursor.execute(query, (
        datos['nombre_completo'], datos['edad'], datos['genero'], datos['direccion'],
        datos['telefono'], datos['estado_civil'], datos['religion'], datos['tipo_sangre'],
        datos['enfermedad_cronica'], datos['antecedentes_patologicos'], 
        datos['antecedentes_heredofamiliares'], datos['medico_asignado']
    ))
    conn.commit()
    conn.close()

def obtener_todos_los_pacientes():
    """Retorna todos los pacientes."""
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pacientes ORDER BY id DESC")
    pacientes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return pacientes

# --- GESTIÓN DE USUARIOS Y LOGS ---

def verificar_credenciales(username, password_plano):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM usuarios WHERE username = ?", (username,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return auth.verify_password(password_plano, resultado[0])
    return False

def registrar_log(usuario, accion, detalle=""):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    mensaje = f"{accion} | {detalle}" if detalle else accion
    cursor.execute("INSERT INTO bitacora (usuario, accion, fecha) VALUES (?, ?, ?)",
                (usuario, mensaje, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def obtener_todos_los_logs():
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bitacora ORDER BY id DESC")
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return logs

def obtener_datos_doctor(username):
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
    doctor = cursor.fetchone()
    conn.close()
    return doctor

def registrar_nuevo_medico(username, password, nombre, especialidad, cedula, foto, nivel):
    hash_seguro = auth.hash_password(password)
    try:
        conn = sqlite3.connect('hospital.db')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (username, password_hash, nombre_completo, especialidad, cedula, foto_ruta, nivel_acceso) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""", 
            (username, hash_seguro, nombre, especialidad, cedula, foto, nivel))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def update_medico(uid, nombre, espec, cedula, password, nivel, foto_ruta):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    query = """UPDATE usuarios SET nombre_completo = ?, especialidad = ?, cedula = ?, nivel_acceso = ?, foto_ruta = ? WHERE id = ?"""
    cursor.execute(query, (nombre, espec, cedula, nivel, foto_ruta, uid))
    if password and password.strip():
        hash_nuevo = auth.hash_password(password)
        cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (hash_nuevo, uid))
    conn.commit()
    conn.close()

def eliminar_usuario(id_usuario, nivel_solicitante):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nivel_acceso, username FROM usuarios WHERE id = ?", (id_usuario,))
    objetivo = cursor.fetchone()
    if not objetivo or objetivo[1] == "admin":
        conn.close()
        return False
    if nivel_solicitante > objetivo[0]:
        cursor.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
        conn.commit()
        exito = True
    else:
        exito = False
    conn.close()
    return exito

# --- GESTIÓN ONCOLÓGICA (FASE 1 Y 2) ---

def guardar_diagnostico_fase1(paciente_id, metodo, tamano, clasificacion, observaciones):
    """Guarda el diagnóstico inicial (Benigno o Maligno)."""
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    query = '''
        INSERT INTO diagnosticos_fase1 (paciente_id, metodo_deteccion, tamano_aparente_mm, clasificacion, observaciones)
        VALUES (?, ?, ?, ?, ?)
    '''
    cursor.execute(query, (paciente_id, metodo, tamano, clasificacion, observaciones))
    conn.commit()
    conn.close()

def guardar_patologia_fase2(datos):
    """Guarda el perfil molecular y patológico detallado (Solo Malignos)."""
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Usamos REPLACE o INSERT OR REPLACE por si el doctor actualiza la patología
    query = '''
        INSERT OR REPLACE INTO patologia_fase2 (
            paciente_id, re, rp, her2, ki67, tipo_histologico, grado_histologico, 
            tamano_tumor_mm, ilv, margenes, ganglios_analizados, ganglios_positivos
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    valores = (
        datos['paciente_id'], datos['re'], datos['rp'], datos['her2'], datos['ki67'],
        datos['tipo_histologico'], datos['grado_histologico'], datos['tamano_tumor_mm'],
        datos['ilv'], datos['margenes'], datos['ganglios_analizados'], datos['ganglios_positivos']
    )
    cursor.execute(query, valores)
    conn.commit()
    conn.close()
    
def obtener_diagnostico_paciente(paciente_id):
    """Consulta si el paciente tiene diagnóstico y si es Benigno o Maligno."""
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM diagnosticos_fase1 WHERE paciente_id = ? ORDER BY id DESC LIMIT 1", (paciente_id,))
    diag = cursor.fetchone()
    conn.close()
    return dict(diag) if diag else None

def obtener_paciente_por_id(p_id):
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pacientes WHERE id = ?", (p_id,))
    paciente = dict(cursor.fetchone())
    conn.close()
    return paciente

def obtener_patologia_por_paciente(p_id):
    """Obtiene el perfil molecular y patológico detallado del paciente."""
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patologia_fase2 WHERE paciente_id = ?", (p_id,))
    patologia = cursor.fetchone()
    conn.close()
    return dict(patologia) if patologia else None

def obtener_datos_ia(paciente_id):
    """Une los datos del paciente con su perfil patológico para la IA."""
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = """
    SELECT p.edad, p.genero, 
           t.re, t.rp, t.her2, t.ki67, t.tamano_tumor_mm, 
           t.ganglios_positivos, t.ilv
    FROM pacientes p 
    JOIN patologia_fase2 t ON p.id = t.paciente_id 
    WHERE p.id = ?
    """
    cursor.execute(query, (paciente_id,))
    datos = cursor.fetchone()
    conn.close()
    return dict(datos) if datos else None

def inicializar_tabla_predicciones():
    """Crea la tabla de predicciones si no existe para no borrar datos anteriores"""
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predicciones_ia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            fecha_registro TEXT,
            dias_analizados INTEGER,
            tasa_crecimiento REAL,
            volumen_actual REAL,
            tendencia TEXT,
            FOREIGN KEY(paciente_id) REFERENCES pacientes(id)
        )
    ''')
    conn.commit()
    conn.close()

# Ejecutamos la creación de la tabla inmediatamente al importar database.py
inicializar_tabla_predicciones()

def guardar_prediccion_ia(paciente_id, dias, tasa, volumen, tendencia):
    from datetime import datetime
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO predicciones_ia (paciente_id, fecha_registro, dias_analizados, tasa_crecimiento, volumen_actual, tendencia)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (paciente_id, fecha_actual, dias, tasa, volumen, tendencia))
    conn.commit()
    conn.close()

def obtener_predicciones_por_paciente(paciente_id):
    conn = sqlite3.connect('hospital.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Las ordenamos de la más antigua a la más nueva
    predicciones = cursor.execute("SELECT * FROM predicciones_ia WHERE paciente_id = ? ORDER BY id ASC", (paciente_id,)).fetchall()
    conn.close()
    return [dict(p) for p in predicciones] 

def cambiar_password(username, nueva_password):
    hash_seguro = auth.hash_password(nueva_password)
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password_hash = ? WHERE username = ?", (hash_seguro, username))
    conn.commit()
    conn.close()    

def actualizar_paciente(paciente_id, datos):
    """Actualiza la información de un paciente existente en SQLite."""
    try:
        conn = sqlite3.connect('hospital.db')
        cursor = conn.cursor()
        
        sql = """
            UPDATE pacientes 
            SET nombre_completo = ?, 
                edad = ?, 
                genero = ?, 
                direccion = ?, 
                telefono = ?, 
                estado_civil = ?, 
                religion = ?, 
                tipo_sangre = ?, 
                enfermedad_cronica = ?, 
                antecedentes_patologicos = ?, 
                antecedentes_heredofamiliares = ?
            WHERE id = ?
        """
        
        valores = (
            datos["nombre_completo"], 
            datos["edad"], 
            datos["genero"], 
            datos["direccion"],
            datos["telefono"], 
            datos["estado_civil"], 
            datos["religion"], 
            datos["tipo_sangre"],
            datos["enfermedad_cronica"], 
            datos["antecedentes_patologicos"],
            datos["antecedentes_heredofamiliares"], 
            paciente_id  # El ID para el WHERE
        )
        
        cursor.execute(sql, valores)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error al actualizar paciente en SQLite: {e}")
        return False