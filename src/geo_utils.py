# src/geo_utils.py
import re
import unicodedata
import logging
from collections import defaultdict
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass

# Logger
logger = logging.getLogger("geo_engine")

@dataclass
class GeoResult:
    city: str
    state: str
    score: float
    confidence: str
    gap: float

    def to_dict(self):
        return {
            "city_detected": self.city,
            "state_detected": self.state,
            "geo_score": self.score,
            "geo_confidence": self.confidence,
            "geo_gap": self.gap
        }

# ============================================================
# 🗺️ DATOS MAESTROS (Simplificado para rendimiento)
# ============================================================
# Mantenemos tu estructura de datos pero optimizada para búsqueda inversa
RAW_GAZETTEER = [
    # Estados (32)
    {"city": "Aguascalientes", "state": "Aguascalientes", "aliases": ["aguascalientes","ags"]},
    {"city": "Baja California", "state": "Baja California", "aliases": ["baja california","bc"]},
    {"city": "Baja California Sur", "state": "Baja California Sur", "aliases": ["baja california sur","bcs"]},
    {"city": "Campeche", "state": "Campeche", "aliases": ["campeche"]},
    {"city": "Coahuila", "state": "Coahuila", "aliases": ["coahuila","coahuila de zaragoza","coah"]},
    {"city": "Colima", "state": "Colima", "aliases": ["colima"]},
    {"city": "Chiapas", "state": "Chiapas", "aliases": ["chiapas"]},
    {"city": "Chihuahua", "state": "Chihuahua", "aliases": ["chihuahua","chih"]},
    {"city": "Ciudad de México", "state": "Ciudad de México", "aliases": ["cdmx","ciudad de mexico","ciudad de méxico","df"]},
    {"city": "Durango", "state": "Durango", "aliases": ["durango"]},
    {"city": "Guanajuato", "state": "Guanajuato", "aliases": ["guanajuato","gto"]},
    {"city": "Guerrero", "state": "Guerrero", "aliases": ["guerrero","gro"]},
    {"city": "Hidalgo", "state": "Hidalgo", "aliases": ["hidalgo","hgo"]},
    {"city": "Jalisco", "state": "Jalisco", "aliases": ["jalisco","jal"]},
    {"city": "Estado de México", "state": "Estado de México", "aliases": ["edomex","estado de mexico","estado de méxico"]},
    {"city": "Michoacán", "state": "Michoacán", "aliases": ["michoacan","michoacán","mich"]},
    {"city": "Morelos", "state": "Morelos", "aliases": ["morelos","mor"]},
    {"city": "Nayarit", "state": "Nayarit", "aliases": ["nayarit","nay"]},
    {"city": "Nuevo León", "state": "Nuevo León", "aliases": ["nuevo leon","nuevo león","nl"]},
    {"city": "Oaxaca", "state": "Oaxaca", "aliases": ["oaxaca","oax"]},
    {"city": "Puebla", "state": "Puebla", "aliases": ["puebla","pue"]},
    {"city": "Querétaro", "state": "Querétaro", "aliases": ["queretaro","querétaro","qro"]},
    {"city": "Quintana Roo", "state": "Quintana Roo", "aliases": ["quintana roo","qroo","qr"]},
    {"city": "San Luis Potosí", "state": "San Luis Potosí", "aliases": ["san luis potosi","san luis potosí","slp"]},
    {"city": "Sinaloa", "state": "Sinaloa", "aliases": ["sinaloa","sin"]},
    {"city": "Sonora", "state": "Sonora", "aliases": ["sonora","son"]},
    {"city": "Tabasco", "state": "Tabasco", "aliases": ["tabasco","tabs"]},
    {"city": "Tamaulipas", "state": "Tamaulipas", "aliases": ["tamaulipas","tamps"]},
    {"city": "Tlaxcala", "state": "Tlaxcala", "aliases": ["tlaxcala","tlax"]},
    {"city": "Veracruz", "state": "Veracruz", "aliases": ["veracruz","ver","veracruz de ignacio de la llave"]},
    {"city": "Yucatán", "state": "Yucatán", "aliases": ["yucatan","yucatán","yuc"]},
    {"city": "Zacatecas", "state": "Zacatecas", "aliases": ["zacatecas","zac"]},

    # CDMX (16 alcaldías)
    {"city":"Álvaro Obregón","state":"Ciudad de México","aliases":["alvaro obregon","álvaro obregón","ao"], "is_borough": True},
    {"city":"Azcapotzalco","state":"Ciudad de México","aliases":["azcapotzalco","azcapo"], "is_borough": True},
    {"city":"Benito Juárez","state":"Ciudad de México","aliases":["benito juarez","benito juárez","bj"], "is_borough": True},
    {"city":"Coyoacán","state":"Ciudad de México","aliases":["coyoacan","coyoacán"], "is_borough": True},
    {"city":"Cuajimalpa de Morelos","state":"Ciudad de México","aliases":["cuajimalpa","cuajimalpa de morelos"], "is_borough": True},
    {"city":"Cuauhtémoc","state":"Ciudad de México","aliases":["cuauhtemoc","cuauhtémoc"], "is_borough": True},
    {"city":"Gustavo A. Madero","state":"Ciudad de México","aliases":["gustavo a madero","gam","gustavo a. madero"], "is_borough": True},
    {"city":"Iztacalco","state":"Ciudad de México","aliases":["iztacalco"], "is_borough": True},
    {"city":"Iztapalapa","state":"Ciudad de México","aliases":["iztapalapa"], "is_borough": True},
    {"city":"La Magdalena Contreras","state":"Ciudad de México","aliases":["magdalena contreras","la magdalena contreras","contreras"], "is_borough": True},
    {"city":"Miguel Hidalgo","state":"Ciudad de México","aliases":["miguel hidalgo","mh"], "is_borough": True},
    {"city":"Milpa Alta","state":"Ciudad de México","aliases":["milpa alta"], "is_borough": True},
    {"city":"Tláhuac","state":"Ciudad de México","aliases":["tlahuac","tláhuac"], "is_borough": True},
    {"city":"Tlalpan","state":"Ciudad de México","aliases":["tlalpan"], "is_borough": True},
    {"city":"Venustiano Carranza","state":"Ciudad de México","aliases":["venustiano carranza","vc"], "is_borough": True},
    {"city":"Xochimilco","state":"Ciudad de México","aliases":["xochimilco"], "is_borough": True},

    # Valle de México (algunas)
    {"city":"Ecatepec","state":"Estado de México","aliases":["ecatepec"]},
    {"city":"Nezahualcóyotl","state":"Estado de México","aliases":["nezahualcoyotl","nezahualcóyotl","neza","cd neza"]},
    {"city":"Naucalpan de Juárez","state":"Estado de México","aliases":["naucalpan","naucalpan de juarez","naucalpan de juárez"]},
    {"city":"Tlalnepantla de Baz","state":"Estado de México","aliases":["tlalnepantla","tlalne"]},
    {"city":"Toluca","state":"Estado de México","aliases":["toluca"]},

    # Grandes ZM y ciudades frecuentes
    {"city":"Guadalajara","state":"Jalisco","aliases":["guadalajara","gdl"]},
    {"city":"Zapopan","state":"Jalisco","aliases":["zapopan","zapop"]},
    {"city":"Monterrey","state":"Nuevo León","aliases":["monterrey","mty","nl","nuevo leon","nuevo león"]},
    {"city":"San Pedro Garza García","state":"Nuevo León","aliases":["san pedro garza garcia","san pedro garza garcía","san pedro","spgg"]},
    {"city":"Puebla","state":"Puebla","aliases":["puebla","pue"]},
    {"city":"Querétaro","state":"Querétaro","aliases":["queretaro","querétaro","qro"]},
    {"city":"León","state":"Guanajuato","aliases":["leon","león"]},
    {"city":"Tijuana","state":"Baja California","aliases":["tijuana","tij"]},
    {"city":"Mexicali","state":"Baja California","aliases":["mexicali","mxl"]},
    {"city":"Hermosillo","state":"Sonora","aliases":["hermosillo","hmo"]},
    {"city":"Ciudad Juárez","state":"Chihuahua","aliases":["ciudad juarez","ciudad juárez","juarez","juárez","cjs"]},
    {"city":"Culiacán","state":"Sinaloa","aliases":["culiacan","culiacán"]},
    {"city":"Mazatlán","state":"Sinaloa","aliases":["mazatlan","mazatlán"]},
    {"city":"Durango","state":"Durango","aliases":["durango"]},
    {"city":"Gómez Palacio","state":"Durango","aliases":["gomez palacio","gómez palacio"]},
    {"city":"Benito Juárez","state":"Quintana Roo","aliases":["benito juarez"]}, 
    {"city":"Cancún","state":"Quintana Roo","aliases":["cancun","cancún","cun"]},
    {"city":"Playa del Carmen","state":"Quintana Roo","aliases":["playa del carmen","playa","solidaridad"]},

    # Capitales y Ciudades Principales Faltantes
    {"city": "Mérida", "state": "Yucatán", "aliases": ["merida", "mid"]},
    {"city": "San Luis Potosí", "state": "San Luis Potosí", "aliases": ["slp capital", "san luis"]},
    {"city": "Saltillo", "state": "Coahuila", "aliases": ["saltillo"]},
    {"city": "Torreón", "state": "Coahuila", "aliases": ["torreon", "torreón"]},
    {"city": "Morelia", "state": "Michoacán", "aliases": ["morelia"]},
    {"city": "Aguascalientes", "state": "Aguascalientes", "aliases": ["aguascalientes capital"]},
    {"city": "Cuernavaca", "state": "Morelos", "aliases": ["cuernavaca", "cuerna"]},
    {"city": "Pachuca de Soto", "state": "Hidalgo", "aliases": ["pachuca"]},
    {"city": "Xalapa", "state": "Veracruz", "aliases": ["xalapa", "jalapa"]},
    {"city": "Tuxtla Gutiérrez", "state": "Chiapas", "aliases": ["tuxtla", "tuxtla gutierrez"]},
    {"city": "Villahermosa", "state": "Tabasco", "aliases": ["villahermosa"]},
    {"city": "Oaxaca de Juárez", "state": "Oaxaca", "aliases": ["oaxaca capital", "oaxaca de juarez"]},

    # Puertos y Turismo
    {"city": "Acapulco de Juárez", "state": "Guerrero", "aliases": ["acapulco"]},
    {"city": "Puerto Vallarta", "state": "Jalisco", "aliases": ["puerto vallarta", "vallarta", "pvr"]},
    {"city": "Veracruz", "state": "Veracruz", "aliases": ["puerto de veracruz", "veracruz puerto"]},
    {"city": "Los Cabos", "state": "Baja California Sur", "aliases": ["cabo san lucas", "san jose del cabo"]},
    {"city": "Ixtapa Zihuatanejo", "state": "Guerrero", "aliases": ["ixtapa", "zihuatanejo"]},

    # Frontera y Zona Norte
    {"city": "Reynosa", "state": "Tamaulipas", "aliases": ["reynosa"]},
    {"city": "Nuevo Laredo", "state": "Tamaulipas", "aliases": ["nuevo laredo"]},
    {"city": "Matamoros", "state": "Tamaulipas", "aliases": ["matamoros"]},
    
    # Zonas Metropolitanas (Complementos importantes)
    {"city": "San Nicolás de los Garza", "state": "Nuevo León", "aliases": ["san nicolas", "san nico"]},
    {"city": "Apodaca", "state": "Nuevo León", "aliases": ["apodaca"]},
    {"city": "Santa Catarina", "state": "Nuevo León", "aliases": ["santa catarina"]},
    {"city": "San Pedro Tlaquepaque", "state": "Jalisco", "aliases": ["tlaquepaque"]},
    {"city": "Tonalá", "state": "Jalisco", "aliases": ["tonala"]},
    {"city": "Metepec", "state": "Estado de México", "aliases": ["metepec"]},
]

# Mapa inverso: alias_normalizado -> [(city, state), ...]
ALIAS_MAP: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
ALL_ALIASES = set()

def normalize(text: str) -> str:
    """Normalización ultrarrápida usando translate."""
    if not text: return ""
    # Quitar acentos
    s = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8").lower()
    # Quitar puntuación (reemplazar por espacio para no juntar palabras)
    return re.sub(r"[^a-z0-9\s]", " ", s).strip()

# Inicialización Estática (Al importar)
def _initialize_geo_engine():
    global GEO_PATTERN, ALIAS_MAP
    
    # 1. Construir índice invertido
    # NOTA: En tu código real, añade aquí TODAS las entradas de tu GAZETTEER original
    # Incluyendo las alcaldías con flag is_borough
    
    # Simulación de carga completa (Mapea tu lista real aquí)
    # ...
    
    # Para el ejemplo, usamos RAW_GAZETTEER
    for entry in RAW_GAZETTEER:
        c, s = entry["city"], entry["state"]
        # Añadimos ciudad y estado como alias implícitos
        all_names = entry["aliases"] + [c, s]
        for name in all_names:
            norm_name = normalize(name)
            if len(norm_name) < 2: continue # Ignorar abreviaturas muy cortas peligrosas
            ALIAS_MAP[norm_name].append((c, s))
            ALL_ALIASES.add(norm_name)

    # 2. Construir Regex Unificado (Aho-Corasick style via Regex Engine)
    # Ordenamos por longitud descendente para que "baja california sur" haga match antes que "baja california"
    sorted_aliases = sorted(ALL_ALIASES, key=len, reverse=True)
    pattern_str = r'\b(?:' + '|'.join(map(re.escape, sorted_aliases)) + r')\b'
    GEO_PATTERN = re.compile(pattern_str, re.IGNORECASE)

# Ejecutar inicialización
_initialize_geo_engine()

# ============================================================
# ENGINE
# ============================================================

def enrich_location(title_raw: str, text_raw: str, url_raw: str = "") -> Dict:
    """
    Algoritmo de scoring optimizado O(1) scan.
    """
    # Normalización única
    title_norm = normalize(title_raw)
    text_norm = normalize(text_raw)
    
    # Contadores
    counts = defaultdict(lambda: {"title": 0, "text": 0, "first_pos": 999999})
    
    # 1. Scan Título
    for match in GEO_PATTERN.finditer(title_norm):
        alias = match.group() # Ya está normalizado porque el regex se hizo con normalizados
        matched_locs = ALIAS_MAP.get(alias, [])
        for loc in matched_locs:
            counts[loc]["title"] += 1
            
    # 2. Scan Texto
    for match in GEO_PATTERN.finditer(text_norm):
        alias = match.group()
        start_pos = match.start()
        matched_locs = ALIAS_MAP.get(alias, [])
        for loc in matched_locs:
            counts[loc]["text"] += 1
            if start_pos < counts[loc]["first_pos"]:
                counts[loc]["first_pos"] = start_pos

    # 3. Calcular Scores
    final_scores = []
    
    for loc, stats in counts.items():
        score = 0.0
        
        # Pesos
        if stats["title"] > 0:
            score += 3.0
            
        if stats["first_pos"] < 300: # Lead
            score += 2.0
            
        total_hits = stats["title"] + stats["text"]
        if total_hits > 1:
            score += min(3.0, float(total_hits - 1))
            
        # Bonus URL
        city_norm = normalize(loc[0])
        if city_norm in url_raw:
            score += 0.5
            
        final_scores.append((loc, score))

    # 4. Decisión
    if not final_scores:
        return GeoResult("", "", 0.0, "None", 0.0).to_dict()

    # Ordenar por Score Descendente -> Prioridad CDMX -> Alfabético
    # Prioridad CDMX hardcodeada para desempate
    def sort_key(x):
        loc, sc = x
        is_prio = 1 if loc[1] in ["Ciudad de México", "Estado de México"] else 0
        return (sc, is_prio)

    final_scores.sort(key=sort_key, reverse=True)
    
    best_loc, best_score = final_scores[0]
    gap = 0.0
    if len(final_scores) > 1:
        gap = best_score - final_scores[1][1]

    # Confianza
    bucket = "Low"
    if best_score >= 5 and gap >= 2:
        bucket = "High"
    elif best_score >= 3 and gap >= 1:
        bucket = "Medium"

    return GeoResult(
        city=best_loc[0],
        state=best_loc[1],
        score=round(best_score, 2),
        confidence=bucket,
        gap=round(gap, 2)
    ).to_dict()