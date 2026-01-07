# didi-safety-intelligence-mexico
DiDi Safety Intelligence - México
Descripción
Sistema proactivo de recolección y análisis de noticias de seguridad en México. El proyecto utiliza un pipeline de datos modular para transformar señales externas (noticias) en recomendaciones accionables para el equipo de Safety Perception de DiDi.

Arquitectura
Ingesta: scraper.py (Selenium + BeautifulSoup).

NLP: nlp_models.py (Arquitectura BERT para sentimiento y severidad).

Geolocalización: geo_utils.py (Motor heurístico de pesos para resolución de ambigüedad).

Orquestación: main.py.

Requisitos
pip install -r requirements.txt
