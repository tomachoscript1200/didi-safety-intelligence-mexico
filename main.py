# main.py
import logging
import pandas as pd
import os
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup

# Importamos Selenium y herramientas de espera (Necesarias para TV Azteca)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- IMPORTACIONES MODULARES ---
from src.config import (
    URL_EL_UNIVERSAL, URL_MILENIO_FMT, URL_DIARIO_PORTAL_FMT, 
    URL_JORNADA_FMT, URL_TVAZTECA,
    PAGES_TO_SCRAPE, PAGE_WAIT_RANGE, SOURCE_NAME_MAPPING
)
from src.scraper import setup_driver, get_page_source, smart_scroll
from src.parsers import (
    extract_data_el_universal,
    extract_data_milenio,
    extract_data_diario_portal,
    extract_data_jornada,
    extract_data_tvazteca
)
from src.nlp_models import (
    analyze_content, 
    calculate_didi_focus, 
    get_source_tier, 
)
from src.geo_utils import enrich_location

# Configuración de Logs
if not os.path.exists('logs'): os.makedirs('logs')
if not os.path.exists('data/processed'): os.makedirs('data/processed')

logging.basicConfig(
    filename='logs/scraper.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# ============================================================
# CRAWLERS
# ============================================================

def get_links_el_universal(driver, pages):
    links = []
    print(f"🔎 [El Universal] Aplicando ruteo por directorio (/page/)")
    
    # URL base de la sección específica
    base_url = "https://www.eluniversal.com.mx/minuto-x-minuto/estados/"
    
    for page in range(1, pages + 1):
        # CAMBIO DEFINITIVO: El Universal usa /estados/2/, /estados/3/, etc.
        # Conservamos el slash final para evitar redirecciones del servidor.
        url = f"{base_url}{page}/" if page > 1 else base_url
        
        driver.get(url)
        
        try:
            # 1. Simulación de scroll para activar la hidratación de datos
            for scroll in [800, 1800, 2800]:
                driver.execute_script(f"window.scrollTo(0, {scroll});")
                time.sleep(1.5)
            
            # 2. Verificación de Integridad de la URL
            # Si el sitio nos redirige y elimina 'minuto-x-minuto', la página no tendrá los datos nuevos.
            if "minuto-x-minuto" not in driver.current_url:
                print(f"   ⚠️ Redirección detectada en Pág {page}. El servidor no permite el acceso directo.")
                continue

            # 3. Espera explícita a que los artículos estén presentes en el DOM
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/estados/')]"))
            )
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            found_on_page = 0
            
            # 4. Extracción de enlaces con filtro de longitud para evitar ruido
            for a in soup.find_all("a", href=True):
                href = a['href']
                full_url = href if href.startswith("http") else "https://www.eluniversal.com.mx" + href
                
                # Filtro: debe ser nota de estados y tener longitud de slug real (evita menús)
                if "/estados/" in full_url and len(full_url) > 65:
                    if full_url not in [l['url'] for l in links]:
                        links.append({"url": full_url, "source": "eluniversal"})
                        found_on_page += 1
            
            print(f"   ↳ Pág {page}: {found_on_page} noticias recolectadas.")
            
        except Exception as e:
            print(f"   ⚠️ Error de carga en El Universal Pág {page}. Es posible que la página no exista.")
            
    return links

def get_links_milenio(driver, pages):
    links = []
    print(f"🔎 [Milenio] Escaneando {pages} páginas (incluyendo Video-Notas)...")
    
    for page in range(1, pages + 1):
        url = URL_MILENIO_FMT.format(page)
        # Forzamos scroll para que el DOM se hidrate completamente
        html = get_page_source(driver, url, wait_for_tag="body", do_scroll=True)
        if not html: continue
        
        soup = BeautifulSoup(html, "html.parser")
        found = 0
        
        # Buscamos en los contenedores de noticias típicos de Milenio
        for a in soup.find_all("a", href=True):
            href = a['href']
            
            # FILTRO PERMISIVO: Captura estados, policía y videos
            valid_patterns = ["/policia/", "/estados/", "/videos/", "/ciudad/"]
            if any(p in href for p in valid_patterns):
                # Evitar links de secciones raíz o paginación interna
                if href.endswith(tuple(valid_patterns)) or "page=" in href:
                    continue
                
                # Reconstrucción de URL absoluta
                full_url = href if href.startswith("http") else "https://www.milenio.com" + href
                
                if full_url not in [l['url'] for l in links]:
                    links.append({"url": full_url, "source": "milenio"})
                    found += 1
                    
        print(f"   ↳ Pág {page}: {found} links detectados.")
    return links

def get_links_portal(driver, pages):
    links = []
    print(f"🔎 [Diario Portal] Escaneando {pages} páginas...")
    # Lista negra para evitar links que no son noticias
    DENY = ["/tag/", "/author/", "/edicion-impresa", "/feed", "page="]
    
    for page in range(1, pages + 1):
        # Usamos el formato de URL que definiste en config.py
        url = URL_DIARIO_PORTAL_FMT.format(page)
        html = get_page_source(driver, url, wait_for_tag="body")
        if not html: continue
        
        soup = BeautifulSoup(html, "html.parser")
        found = 0
        
        # Buscamos todos los enlaces y filtramos los que pertenecen a noticias
        for a in soup.find_all("a", href=True):
            l = a["href"]
            
            # Normalización de URL
            if not l.startswith("http"): l = "https://diarioportal.com" + l
            
            # Filtros de calidad: debe ser del sitio, tener longitud de noticia y ser de seguridad
            if "diarioportal.com" in l and len(l) > 50:
                if "/seguridad-y-justicia/" in l and not any(bad in l for bad in DENY):
                    if l not in links:
                        links.append({"url": l, "source": "diarioportal"})
                        found += 1
                        
        print(f"   ↳ Pág {page}: {found} links nuevos detectados.")
    return links

def get_links_jornada(driver, pages):
    links = []
    print(f"🔎 [La Jornada] Escaneando sección Capital...")
    url = "https://www.jornada.com.mx/categoria/capital"
    
    # Navegamos a la sección
    driver.get(url)
    
    # Aplicamos scroll para cargar noticias dinámicas
    driver.execute_script("window.scrollTo(0, 1000);")
    time.sleep(4)
    driver.execute_script("window.scrollTo(0, 2000);")
    time.sleep(2)
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Buscamos el patrón /noticia/ y /capital/ que detectamos en el test exitoso
    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/capital/" in href and "/noticia/" in href:
            # Reconstrucción de URL relativa
            full_url = href if href.startswith("http") else "https://www.jornada.com.mx" + href
            if full_url not in links:
                links.append({"url": full_url, "source": "jornada"})
                
    print(f"   ✅ Se detectaron {len(links)} noticias potenciales en La Jornada.")
    return links

def get_links_tvazteca(driver, clicks_target=5):
    links = []
    # 1. LISTA NEGRA REFINADA: Eliminamos rutas de secciones y video.
    # No usamos espacios ni tildes, solo los slugs que aparecen en la URL.
    blacklist = ["/videos/", "/envivo/", "/programas/", "/radio/", "/noticieros/", "/VIDEOS/", "/Política/", "/Finanzas/", "/Salud y Educación/", "/Seguridad/", "/Estados/", "/Mundo/", "/Opinión/", "/Tendencias/", "/Videos/"]
    
    print(f"🔎 [TV Azteca] Iniciando recolección selectiva (Solo Notas de Texto)...")
    url = "https://www.tvazteca.com/aztecanoticias/accidentes-en-mexico-noticias"
    
    try:
        driver.get(url)
        time.sleep(5) # Espera crítica para que React cargue el contenido dinámico
        
        # EXPANSIÓN: Clic en "Ver más" para cargar notas históricas
        for i in range(clicks_target):
            try:
                btn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Ver más')]"))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)
                print(f"   🖱️ Click {i+1} de expansión.")
                time.sleep(3) # Tiempo para que el DOM se actualice tras la carga
            except:
                break

        # --- FASE DE FILTRADO TÉCNICO ---
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 2. AISLAMIENTO: Buscamos únicamente dentro de la lista de noticias.
        # Esto ignora automáticamente los menús de 'Política', 'Finanzas', etc.
        content_area = soup.select_one(".Topic-news-list") or soup.find("main")
        
        if not content_area:
            print("   ⚠️ No se encontró el contenedor principal, usando búsqueda general.")
            content_area = soup

        potential_links = content_area.find_all("a", href=True)

        for a in potential_links:
            href = a['href'].lower() # Trabajamos en minúsculas para mayor seguridad
            
            # Reconstrucción de URL absoluta
            full_url = href if href.startswith("http") else "https://www.tvazteca.com" + href
            
            # 3. CRITERIOS DE CALIDAD:
            # - Debe pertenecer a aztecanoticias.
            # - No debe contener palabras de la lista negra.
            # - Debe tener un slug largo (evita links a categorías como /seguridad).
            is_valid_path = "/aztecanoticias/" in full_url
            is_not_blacklisted = not any(word in full_url for word in blacklist)
            
            # Un slug de noticia real suele tener más de 40 caracteres tras el último '/'
            slug = full_url.rstrip("/").split("/")[-1]
            is_real_news = len(slug) > 25 
            
            if is_valid_path and is_not_blacklisted and is_real_news:
                if full_url not in [l['url'] for l in links]:
                    links.append({"url": full_url, "source": "tvazteca"})
                    
    except Exception as e:
        print(f"   ❌ Error en recolección TV Azteca: {e}")
    
    print(f"   ✅ Se obtuvieron {len(links)} noticias únicas filtradas.")
    return links

# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================

def main():
    # --- CRONÓMETRO INICIO ---
    start_time = time.time()
    start_str = datetime.now().strftime('%H:%M:%S')
    
    print(f"⏱️ INICIO DE EJECUCIÓN: {start_str}")
    print("Iniciando Scraper de Seguridad (Modular v3.0 - Excel + Timer)...")
    
    driver = setup_driver(headless=True) # True para producción
    all_data = []
    
    try:
        # --- FASE 1: Recolección de URLs ---
        # Usamos PAGES_TO_SCRAPE desde config.py para escalabilidad
        print(f"\n--- FASE 1: Recolección de URLs ({PAGES_TO_SCRAPE} páginas por fuente) ---")
        
        # Eliminamos el [:3] que limitaba los resultados
        links_univ = get_links_el_universal(driver, PAGES_TO_SCRAPE) 
        links_mile = get_links_milenio(driver, PAGES_TO_SCRAPE)
        links_port = get_links_portal(driver, PAGES_TO_SCRAPE)
        links_jorn = get_links_jornada(driver, PAGES_TO_SCRAPE)
        
        # Para TV Azteca, clicks_target suele ser mayor para obtener más noticias
        links_azteca = get_links_tvazteca(driver, clicks_target=PAGES_TO_SCRAPE)
        
        master_list = links_univ + links_mile + links_port + links_jorn + links_azteca
        
        unique_links = []
        seen_urls = set()
        for item in master_list:
            if item['url'] not in seen_urls:
                unique_links.append(item)
                seen_urls.add(item['url'])
        
        print(f"\n🔗 Total de noticias únicas a procesar: {len(unique_links)}")

        # --- FASE 2: Procesamiento ---
        print("\n--- FASE 2: Procesamiento Inteligente ---")
        
        for i, item in enumerate(unique_links):
            url = item['url']
            source = item['source']
            
            print(f"({i+1}/{len(unique_links)}) [{source}] Procesando...")
            
            # Descarga
            html = get_page_source(driver, url, wait_for_tag="body")
            if not html: continue
            
            # Parsers
            data = {}
            if source == "eluniversal":
                data = extract_data_el_universal(html, url)
            elif source == "milenio":
                data = extract_data_milenio(html, url)
            elif source == "diarioportal":
                data = extract_data_diario_portal(html, url)
            elif source == "jornada":
                data = extract_data_jornada(html, url)
            elif source == "tvazteca":
                data = extract_data_tvazteca(html, url)
            
            if not data.get("text"):
                logging.warning(f"Texto nulo en {url}")
                continue
                
            # Definimos umbrales: Milenio es muy breve (10 chars), otros son más largos
            min_char_threshold = 10 if source == "milenio" else 150 

            if len(data["text"]) < min_char_threshold:
                logging.warning(f"⚠️ Salteado por contenido insuficiente ({len(data['text'])} chars): {url}")
                continue

            # NLP + Geo
            nlp_result = analyze_content(data["text"], data["title"])
            if nlp_result["topic"] == "Irrelevante":
                print(f"   🗑️ Ignorando noticia irrelevante: {data['title'][:40]}...")
                continue 

            geo_result = enrich_location(data["title"], data["text"], url)
            
            # --- FASE 2.2: CAPA ESTRATÉGICA (Foco + OKR) ---
            foco = calculate_didi_focus(data["title"], data["text"])
            tier = get_source_tier(source)

            # Obtenemos el nombre "bonito" del noticiero
            pretty_source = SOURCE_NAME_MAPPING.get(source, source.capitalize())

            strategy_data = {
                "source": pretty_source,
                "didi_focus_score": foco,
                "media_tier": tier
            }
            
            # Unir todos los diccionarios en la fila final para el Excel
            row = {**data, **nlp_result, **geo_result, **strategy_data}
            all_data.append(row)
            
            # Backup parcial en CSV por seguridad (sobreescribe)
            if len(all_data) % 10 == 0:
                pd.DataFrame(all_data).to_csv("data/processed/backup_parcial.csv", index=False)

    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO EN MAIN: {e}")
        logging.critical("Fallo total", exc_info=True)
        
    finally:
        print("\n🛑 Cerrando navegador...")
        driver.quit()
        
        # --- EXPORTACIÓN A EXCEL (.xlsx) ---
        if all_data:
            df = pd.DataFrame(all_data)
            
            cols_order = [
                "source", "title", "date", 
                "severity_level",
                "sentiment_polarity",
                "sentiment_label", 
                "sentiment_score",           
                "topic", 
                "keywords",                 
                "recommendation_for_comms",
                "city_detected", "state_detected", "url"
            ]
            
            final_cols = [c for c in cols_order if c in df.columns] + [c for c in df.columns if c not in cols_order]
            df = df[final_cols]
            
            # Nombre de archivo con fecha
            filename = f"data/processed/Noticias_Seguridad_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            # Guardar en Excel (requiere openpyxl)
            try:
                df.to_excel(filename, index=False, engine='openpyxl')
                print(f"\n✅ ¡ÉXITO! Reporte Excel generado: {filename}")
                print(f"📊 Noticias procesadas: {len(df)}")
            except Exception as e:
                print(f"\n❌ Error guardando Excel (¿instalaste openpyxl?): {e}")
                # Fallback a CSV si falla el Excel
                csv_name = filename.replace(".xlsx", ".csv")
                df.to_csv(csv_name, index=False, encoding="utf-8-sig")
                print(f"   ⚠️ Se guardó como CSV de respaldo: {csv_name}")

        else:
            print("\n⚠️ No se generaron datos.")

        # --- CRONÓMETRO FINAL ---
        end_time = time.time()
        end_str = datetime.now().strftime('%H:%M:%S')
        total_seconds = int(end_time - start_time)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        print("\n" + "="*40)
        print("⏱️  RESUMEN DE TIEMPO")
        print(f"   ▶ Inicio:   {start_str}")
        print(f"   ⏹ Término:  {end_str}")
        print(f"   ⏳ Duración: {minutes} min {seconds} seg")
        print("="*40)

if __name__ == "__main__":
    main()