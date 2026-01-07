# src/scraper.py
import logging
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Importamos constantes de config
from src.config import USER_AGENT, TIMEOUT_LIMIT

def setup_driver(headless=True):
    """
    Configura el driver con todas las opciones anti-detección y de rendimiento
    que tenías en tu notebook original.
    """
    options = Options()
    
    if headless:
        options.add_argument("--headless=new")
    
    # --- Argumentos ---
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")      
    options.add_argument("--incognito")               
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # --- Preferencias de Rendimiento (Bloquea imágenes/notificaciones) ---
    # Esto estaba en tu notebook y es CRÍTICO para la velocidad.
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    }
    options.add_experimental_option("prefs", prefs)
    
    # Anti-detección extra
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        # Usamos Webdriver Manager (Portable) en vez de ruta absoluta
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Script CDP (Anti-bot)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver
    except Exception as e:
        logging.critical(f"Error iniciando ChromeDriver: {e}")
        raise e

def smart_scroll(driver, max_scrolls=10, min_wait=2.5, max_wait=4.5):
    """
    Replica tu lógica de 'Scroll Infinito' del notebook de forma reutilizable.
    """
    try:
        logging.info("🔄 Iniciando Smart Scroll...")
        prev_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0
        
        while scroll_count < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(min_wait, max_wait))
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count += 1
            
            if new_height == prev_height:
                # Si la altura no cambió, llegamos al final
                break
            prev_height = new_height
            
        logging.info(f"✅ Scroll completado ({scroll_count} ciclos)")
    except Exception as e:
        logging.warning(f"⚠️ Error menor durante el scroll: {e}")

def get_page_source(driver, url, wait_for_tag="body", do_scroll=False):
    """
    Navega a la URL, espera explícitamente y opcionalmente hace scroll.
    """
    try:
        logging.info(f"Navegando a: {url}")
        driver.get(url)
        
        # Espera explícita (Robustez)
        WebDriverWait(driver, TIMEOUT_LIMIT).until(
            EC.presence_of_element_located((By.TAG_NAME, wait_for_tag))
        )
        
        # Pausa humana inicial
        time.sleep(random.uniform(2.0, 4.0)) 
        
        # Ejecutar scroll si se solicita (útil para listados infinitos)
        if do_scroll:
            smart_scroll(driver)
            
        return driver.page_source

    except TimeoutException:
        logging.warning(f"⏳ Timeout esperando a {url}")
        return None
    except WebDriverException as e:
        logging.error(f"❌ Error de Selenium en {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"⚠️ Error desconocido cargando {url}: {e}")
        return None