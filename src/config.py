# src/config.py

# ============================================================
# CONFIGURACIÓN GENERAL Y DEL NAVEGADOR
# ============================================================
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT_LIMIT = 20
PAGE_WAIT_RANGE = (2.0, 4.0)
PAGES_TO_SCRAPE = 6 # Ajusta según necesidad

# ============================================================
# URLs OBJETIVO
# ============================================================
URL_EL_UNIVERSAL = "https://www.eluniversal.com.mx/minuto-x-minuto/estados/"
URL_MILENIO_FMT = "https://www.milenio.com/temas/policia?page={}"
URL_DIARIO_PORTAL_FMT = "https://diarioportal.com/categoria/seguridad-y-justicia?page={}"
URL_JORNADA_FMT = "https://www.jornada.com.mx/categoria/capital"
URL_TVAZTECA = "https://www.tvazteca.com/aztecanoticias/accidentes-en-mexico-noticias"

SOURCE_NAME_MAPPING = {
    "eluniversal": "El Universal",
    "milenio": "Milenio",
    "tvazteca": "TV Azteca",
    "jornada": "La Jornada",
    "diarioportal": "Diario Portal"
}

# ============================================================
# [MEJORA 1] TÓPICOS REFINADOS + CATEGORÍA DE CONTROL
# ============================================================
TOPIC_LABELS = [
    "Accidente de tránsito o choque vial",
    "Delito violento, robo o asalto",
    "Acoso o agresión sexual",
    "Operativo policial o detención",
    "Protestas o bloqueos viales",
    "Noticia corporativa o regulación de transporte",
    "Otros temas generales" # <--- LA PAPELERA MÁGICA (Sube el accuracy de los demás)
]

# ============================================================
# [MEJORA 2] DICCIONARIO DE KEYWORDS PARA OVERRIDE (JERARQUÍA MÁXIMA)
# ============================================================
# Si aparece una de estas, ignoramos a la IA y asignamos el tema directo.
HARD_KEYWORDS = {
    "Accidente de tránsito o choque vial": [
        "choque", "volcadura", "carambola", "atropellado", "atropellamiento", 
        "impacto vehicular", "siniestro vial", "colisión vehicular", "embistió"
    ],
    "Delito violento, robo o asalto": [
        "balacera", "ejecutado", "comando armado", "sicarios", "asesinado", 
        "homicidio", "asalto a mano armada", "robo con violencia", "fallecido por disparo"
    ],
    "Protestas o bloqueos viales": [
        "bloqueo", "manifestación", "cierre vial", "tomaron la avenida", 
        "marcha de transportistas", "marcha de protesta", "vialidad cerrada"
    ],
    "Acoso o agresión sexual": [
        "abuso sexual", "violación", "acoso", "feminicidio", "tocamientos indebidos"
    ]
}

# Lista general para regex (compatibilidad anterior)
KEYWORDS = [w for sublist in HARD_KEYWORDS.values() for w in sublist]

# ============================================================
# FILTROS DE MARCA (REGEX)
# ============================================================
APP_PATTERNS_DICT = {
    "Uber": r"\buber(?:y|i)?\b",
    "DiDi": r"\bdi+di+(?:y)?\b",
    "Cabify": r"\bcabify\b",
    "InDrive": r"\bindrive(?:r)?\b",
    "Beat": r"\bbeat\b",
    "Rappi": r"\brappi\b"
}

# ============================================================
# FILTROS DE IRRELEVANCIA (Contexto Negativo)
# ============================================================
IRRELEVANT_CONTEXTS = [
    "perro", "gato", "mascota", "adopción", "refugio animal", "veterinaria", "zoológico",
    "museo", "exposición artística", "obra de teatro", "concierto", "festival de cine",
    "gastronomía", "chef", "turismo", "horóscopo", "farándula", "espectáculos",
    "entrega de cobijas", "jornada de salud", "poda de árboles", "bacheo"
]

CRITICAL_OVERRIDE_KEYWORDS = [
    "muerto", "fallecido", "homicidio", "asesinado", "balazos", "arma de fuego",
    "choque", "volcadura", "atropellado", "bloqueo", "manifestación", 
    "asalto", "robo", "secuestro", "comando armado"
]

# Agregar esto a src/config.py

# ============================================================
# CONFIGURACIÓN DE OKR (PPT 2025)
# ============================================================

# Mapeo de Tiers de medios según impacto [cite: 303-305, 405-407]
SOURCE_TIER_MAPPING = {
    "El Universal": 3,
    "Milenio": 3,
    "TV Azteca": 3,
    "La Jornada": 3,
    "Diario Portal": 2,
    "Default": 1
}

# Pesos para el cálculo de Focus [cite: 301, 403, 459]
FOCUS_WEIGHTS = {
    "TITLE_MATCH": 1.0,
    "BODY_MATCH": 0.5,
    "NO_MATCH": 0.0
}

# Mapeo numérico de sentimiento [cite: 300, 402, 457]
SENTIMENT_NUMERIC_MAP = {
    "Positivo": 1.0,
    "Neutral": 0.0,
    "Negativo": -1.0
}

# ============================================================
# ESCALA DE SEVERIDAD REFINADA (1 a 5)
# ============================================================
FATALITY_KEYWORDS = [
    "muerto", "fallecido", "occiso", "cadáver", "pierde la vida", 
    "mortal", "cuerpo sin vida", "fallece", "homicidio"
]

EXTREME_VIOLENCE_KEYWORDS = [
    "feminicidio", "secuestro", "ejecutado", "asesinado", 
    "violación", "abuso sexual", "levantón", "tortura", "desmembrado"
]

VIOLENCIA_ARMADA_KEYWORDS = [
    "disparos", "balacera", "arma de fuego", "armados", 
    "encapuchados", "comando", "r15", "ak47", "pistola"
]

# --- ESCALA 1-5 REFINADA ---
SEVERITY_MAPPING = {
    "Acoso o agresión sexual": 5,
    "Delito violento, robo o asalto": 4, 
    "Operativo policial o detención": 2, 
    "Accidente de tránsito o choque vial": 2,
    "Protestas o bloqueos viales": 3,
    "Noticias de comunidad o locales": 1,
    "Otros temas generales": 1,
    "Irrelevante": 0
}

# Umbral de confianza (Lo bajamos un poco porque ahora tenemos Hard Keywords)
NLP_CONFIDENCE_THRESHOLD = 0.40