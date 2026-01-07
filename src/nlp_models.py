# src/nlp_models.py
import logging
import re
import torch
import warnings
from typing import Tuple, Dict, Any, List

# Silenciar advertencias
warnings.filterwarnings("ignore", category=UserWarning, module='transformers')

from pysentimiento import create_analyzer
from transformers import pipeline

from src.config import (
    TOPIC_LABELS, HARD_KEYWORDS, NLP_CONFIDENCE_THRESHOLD, 
    APP_PATTERNS_DICT, IRRELEVANT_CONTEXTS, CRITICAL_OVERRIDE_KEYWORDS,
    FOCUS_WEIGHTS, SENTIMENT_NUMERIC_MAP, SOURCE_TIER_MAPPING, SEVERITY_MAPPING,
    SOURCE_NAME_MAPPING, FATALITY_KEYWORDS, EXTREME_VIOLENCE_KEYWORDS, VIOLENCIA_ARMADA_KEYWORDS
)

# SINGLETONS
_SENTIMENT_ANALYZER = None
_TOPIC_CLASSIFIER = None
_KEYWORDS_PATTERN = None

def get_device() -> int:
    if torch.cuda.is_available(): return 0
    elif torch.backends.mps.is_available(): return 0
    return -1

def compile_keywords_regex() -> re.Pattern:
    global _KEYWORDS_PATTERN
    if _KEYWORDS_PATTERN is None:
        all_kws = [kw for sublist in HARD_KEYWORDS.values() for kw in sublist]
        sorted_kws = sorted(all_kws, key=len, reverse=True)
        pattern_str = r"\b(?:" + "|".join(re.escape(k) for k in sorted_kws) + r")\b"
        _KEYWORDS_PATTERN = re.compile(pattern_str, re.IGNORECASE)
    return _KEYWORDS_PATTERN

def load_models() -> Tuple[Any, Any]:
    global _SENTIMENT_ANALYZER, _TOPIC_CLASSIFIER
    device = get_device()
    
    if _SENTIMENT_ANALYZER is None:
        logging.info("⏳ Cargando Modelo de Sentimiento...")
        _SENTIMENT_ANALYZER = create_analyzer(task="sentiment", lang="es")
    
    if _TOPIC_CLASSIFIER is None:
        logging.info("⏳ Cargando Modelo Zero-Shot...")
        _TOPIC_CLASSIFIER = pipeline(
            "zero-shot-classification",
            model="joeddav/xlm-roberta-large-xnli", 
            device=device 
        )
    return _SENTIMENT_ANALYZER, _TOPIC_CLASSIFIER

# --- LÓGICA AUXILIAR ---

def _detect_apps(text: str) -> List[str]:
    detected = []
    text_lower = text.lower()
    for app_name, pattern_str in APP_PATTERNS_DICT.items():
        if re.search(pattern_str, text_lower, re.IGNORECASE):
            detected.append(app_name)
    return list(set(detected))

def _check_irrelevance(text: str, title: str) -> bool:
    full_content = (title + " " + text).lower()
    # 1. Salvación
    for urgent in CRITICAL_OVERRIDE_KEYWORDS:
        if urgent in full_content: return False
    # 2. Descarte
    hits = 0
    found = []
    for term in IRRELEVANT_CONTEXTS:
        if term in full_content:
            hits += 1
            found.append(term)
    if hits >= 1:
        if hits == 1 and len(full_content) > 600: return False
        return True
    return False

def _generate_recommendation(topic, sentiment_label, score, text, apps):
    txt = text.lower()
    is_drv = any(w in txt for w in ["conductor", "chofer", "socio", "volante", "unidad"])
    
    if apps and sentiment_label == "Negativo":
        return f"🚨 CRÍTICO MARCA ({', '.join(apps)}): Activar crisis."

    if topic == "Accidente de tránsito o choque vial":
        return "Soporte DRV: Seguros/Guía post-siniestro." if is_drv else "Seguridad Vial: Monitoreo de zona."
    elif topic == "Delito violento, robo o asalto":
        return "Prevención Nocturna: Alerta de zona de riesgo." if is_drv else "Prevención PAX: Contactos de confianza."
    elif topic == "Acoso o agresión sexual":
        return "INTEGRIDAD / GÉNERO: Cero Tolerancia."
    elif topic == "Protestas o bloqueos viales":
        return "Operaciones: Notificar zonas a evitar (Waze/Maps)."
    elif topic == "Otros temas generales":
        return "Descartar / Baja prioridad."
    
    return "Monitoreo general."

# --- CEREBRO PRINCIPAL ---

def analyze_content(text: str, title: str):
    analyzer, classifier = load_models()
    
    # Check de irrelevancia
    if _check_irrelevance(text, title):
        return {
            "topic": "Irrelevante",
            "severity_level": 0, 
            "sentiment_label": "Neutral", 
            "sentiment_score": 0,
            "recommendation_for_comms": "N/A",
            "keywords": "N/A",
            "apps_detected": ""
        }

    detected_topic = "Otros temas generales"
    topic_score = 0.0 
    kw_found = "N/A" 

    pattern = compile_keywords_regex()
    match = pattern.search(title + " " + text)
    
    if match:
        kw_found = match.group(0).lower()
        for category, keywords in HARD_KEYWORDS.items():
            if any(kw in kw_found for kw in keywords):
                detected_topic = category
                topic_score = 1.0 # Confianza total por keyword manual
                break
    else:
        # Si no hay keyword, usamos la IA y su score
        result = classifier(text[:400], candidate_labels=TOPIC_LABELS)
        detected_topic = result['labels'][0]
        topic_score = round(result['scores'][0], 4)
    
    # 1. Obtener Severidad Base según el Tópico
    severity_level = SEVERITY_MAPPING.get(detected_topic, 1)

    # 2. Aplicar Modificadores de Riesgo (Heurísticas)
    content_lower = (title + " " + text).lower()
    
    # REGLA A: Elevación a EXTREMO (Nivel 5)
    if any(kw in content_lower for kw in EXTREME_VIOLENCE_KEYWORDS):
        severity_level = 5
    
    # REGLA B: Elevación a CRÍTICO (Nivel 4)
    elif severity_level < 4:
        if any(kw in content_lower for kw in FATALITY_KEYWORDS) or \
           any(kw in content_lower for kw in VIOLENCIA_ARMADA_KEYWORDS):
            severity_level = 4

    # REGLA C: Ajuste a MODERADO (Nivel 3)
    elif detected_topic == "Protestas o bloqueos viales":
        severity_level = 3

    sent = analyzer.predict(text[:512])
    mapping = {"POS": "Positivo", "NEU": "Neutral", "NEG": "Negativo"}
    label_final = mapping.get(sent.output, "Neutral")
    score_final = round(sent.probas.get(sent.output, 0), 4)
    peso_sentimiento = SENTIMENT_NUMERIC_MAP.get(label_final, 0.0)
    sentiment_polarity = round(peso_sentimiento * score_final, 4)

    # apps y recomendación
    apps = _detect_apps(text + " " + title)
    rec = _generate_recommendation(detected_topic, label_final, score_final, text, apps)

    return {
        "topic": detected_topic,
        "topic_confidence": topic_score,
        "severity_level": severity_level,
        "sentiment_label": label_final,
        "sentiment_score": score_final,
        "sentiment_polarity": sentiment_polarity,
        "recommendation_for_comms": rec, 
        "keywords": kw_found,           
        "apps_detected": ", ".join(apps)
    }
    
def calculate_didi_focus(title: str, body: str) -> float:
    didi_pattern = APP_PATTERNS_DICT["DiDi"]
    if re.search(didi_pattern, title, re.IGNORECASE):
        return FOCUS_WEIGHTS["TITLE_MATCH"]
    elif re.search(didi_pattern, body, re.IGNORECASE):
        return FOCUS_WEIGHTS["BODY_MATCH"]
    return FOCUS_WEIGHTS["NO_MATCH"]

def get_source_tier(source_raw: str) -> int:
    clean_name = SOURCE_NAME_MAPPING.get(source_raw, "Default")

    return SOURCE_TIER_MAPPING.get(clean_name, SOURCE_TIER_MAPPING["Default"])
