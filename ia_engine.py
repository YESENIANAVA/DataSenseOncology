import math

def calcular_volumen_esferico(diametro):
    """Calcula el volumen de una esfera basado en su diámetro máximo."""
    radio = diametro / 2
    return (4/3) * math.pi * (radio**3)

def predecir_crecimiento_ia(diametro_inicial, dias, diametro_actual):
    """
    (Módulo Fase 1): Compara dos mediciones volumétricas para calcular la tasa de crecimiento.
    """
    vol_inicial = calcular_volumen_esferico(diametro_inicial)
    vol_actual = calcular_volumen_esferico(diametro_actual)
    
    if dias > 0 and vol_inicial > 0:
        k = math.log(vol_actual / vol_inicial) / dias
        tasa_porcentaje = k * 100
    else:
        k = 0
        tasa_porcentaje = 0

    if tasa_porcentaje > 1.5:
        tendencia = "Crecimiento Agresivo - Alerta"
    elif tasa_porcentaje > 0:
        tendencia = "Crecimiento Estable"
    elif tasa_porcentaje < 0:
        tendencia = "Remisión / Respuesta a Tratamiento"
    else:
        tendencia = "Sin cambios"

    return {
        "volumen_inicial": round(vol_inicial, 2),
        "volumen_actual": round(vol_actual, 2),
        "tasa_crecimiento": round(tasa_porcentaje, 2),
        "tendencia": tendencia
    }

def evaluar_riesgo_clinico(datos):
    """
    (Módulo Fase 2): Evalúa el perfil molecular y anatómico para calcular el riesgo de recaída,
    agresividad y emitir recomendaciones quirúrgicas y farmacológicas basadas en protocolos vigentes y la NOM-041.
    """
    # 1. Extracción de variables seguras (soporta datos opcionales)
    re = datos.get('re', 0)
    rp = datos.get('rp', 0)
    her2 = datos.get('her2', 0)
    ki67 = datos.get('ki67', 0)
    grado = datos.get('grado', 1)
    tamano_cm = datos.get('tamano', 0) / 10.0  # El NPI requiere centímetros
    ganglios_pos = datos.get('ganglios_pos', 0)
    ilv = datos.get('ilv', 0)
    margenes = datos.get('margenes', 0)
    
    # Variables extra para refinamiento clínico
    edad = datos.get('edad', 50) # Asumimos 50 si no se envía la edad
    histologia = str(datos.get('tipo_histologico', 'ductal')).lower()

    # ==========================================
    # 2. CLASIFICACIÓN DE SUBTIPO MOLECULAR
    # ==========================================
    subtipo = "Indeterminado"
    terapia_farmacologica = []

    if re == 1 or rp == 1:
        # Terapia hormonal sugerida según la edad (Premenopáusica vs Postmenopáusica)
        terapia_hormonal = "Tamoxifeno" if edad < 50 else "Inhibidores de la Aromatasa"
        
        if her2 == 1:
            subtipo = "Luminal B (HER2 Positivo)"
            terapia_farmacologica.append(f"Hormonoterapia ({terapia_hormonal}) + Terapia Dirigida (Trastuzumab)")
        else:
            if ki67 < 20 and grado <= 2:
                subtipo = "Luminal A (Bajo Riesgo)"
                terapia_farmacologica.append(f"Hormonoterapia ({terapia_hormonal}). Quimioterapia de beneficio dudoso (evaluar Oncotype DX).")
            else:
                subtipo = "Luminal B (Alto Riesgo)"
                terapia_farmacologica.append(f"Hormonoterapia ({terapia_hormonal}) + Quimioterapia adyuvante.")
    elif re == 0 and rp == 0:
        if her2 == 1:
            subtipo = "Enriquecido con HER2"
            terapia_farmacologica.append("Terapia Dirigida (Trastuzumab) + Quimioterapia.")
        else:
            subtipo = "Triple Negativo (Basal-like)"
            terapia_farmacologica.append("Quimioterapia Neoadyuvante urgente. Alto riesgo sistémico.")

    # ==========================================
    # 3. RECOMENDACIÓN QUIRÚRGICA
    # ==========================================
    cirugia = ""
    if tamano_cm > 4.0 or ganglios_pos > 0 or "inflamatorio" in histologia:
        cirugia = "Mastectomía Radical Modificada indicada (tumor >4cm o axila clínicamente positiva)."
    else:
        cirugia = "Cirugía Conservadora (Lumpectomía) + Radioterapia OBLIGATORIA."

    # Alerta especial para Carcinoma Lobulillar (Pérdida de E-Cadherina)
    alerta_lobulillar = ""
    if "lobulil" in histologia:
        alerta_lobulillar = " ALERTA: Patrón lobulillar detectado. Alto riesgo de multifocalidad y bilateralidad. Sugerencia: Resonancia Magnética."

    # ==========================================
    # 4. ÍNDICE DE PRONÓSTICO DE NOTTINGHAM (NPI)
    # ==========================================
    puntuacion_nodulo = 1
    if 1 <= ganglios_pos <= 3:
        puntuacion_nodulo = 2
    elif ganglios_pos >= 4:
        puntuacion_nodulo = 3
        
    npi = (tamano_cm * 0.2) + grado + puntuacion_nodulo
    
    # Penalizaciones anatómicas (Márgenes e Invasión)
    if ilv == 1: npi += 0.5
    if margenes == 1: npi += 1.0

# ==========================================
    # 5. CÁLCULO DE RIESGO Y REPORTE FINAL
    # ==========================================
    if npi <= 3.4 and "Luminal A" in subtipo:
        nivel_riesgo = "Bajo"
        probabilidad_recaida = round(npi * 4, 1) # Aprox 10-15%
    elif 3.4 < npi <= 5.4:
        nivel_riesgo = "Moderado"
        probabilidad_recaida = round(npi * 8, 1) # Aprox 30-45%
    else: 
        nivel_riesgo = "Alto"
        probabilidad_recaida = round(min(npi * 12, 95.0), 1) # Aprox 60-90%

    if "Triple Negativo" in subtipo:
        nivel_riesgo = "Alto"
        probabilidad_recaida = max(probabilidad_recaida, 75.0)

    # NUEVO: En lugar de un solo texto largo, creamos un diccionario (JSON) con los bloques separados
    recomendacion_final = {
        "quirurgica": cirugia,
        "farmacologica": " ".join(terapia_farmacologica),
        "nom_041": "El inicio de este plan terapéutico DEBE garantizarse en < 15 días tras el diagnóstico confirmatorio.",
        "alerta_lobulillar": alerta_lobulillar.replace(" ALERTA: ", "").strip() if alerta_lobulillar else ""
    }

    return {
        "nivel_riesgo": nivel_riesgo,
        "probabilidad_recaida": probabilidad_recaida,
        "perfil_agresividad": subtipo,
        "recomendacion_terapeutica": recomendacion_final,
        "npi_score": round(npi, 2)
    }