import re
import json
import logging
import pandas as pd
from bs4 import BeautifulSoup

# ============================================================
# 🛠️ UTILIDAD MAESTRA DE ESTANDARIZACIÓN
# ============================================================

def clean_date(raw_value):
    """
    Convierte cualquier formato de fecha de las fuentes a YYYY-MM-DD HH:MM:SS
    """
    if not raw_value or pd.isna(raw_value):
        return None
        
    s = str(raw_value).strip()
    
    # 1. Quitar palabras basura comunes
    s = re.sub(r'Publicado|🕑|\||actualizada|de\s+', ' ', s, flags=re.IGNORECASE).strip()

    # 2. Diccionario de meses en español
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", 
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08", 
        "septiembre": "09", "setiembre": "09", "octubre": "10", 
        "noviembre": "11", "diciembre": "12",
        "ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06",
        "jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12"
    }

    s_lower = s.lower()
    for nombre, num in meses.items():
        if nombre in s_lower:
            s = re.sub(rf'\b{nombre}\b', num, s, flags=re.IGNORECASE)

    try:
        s = re.sub(r'\s+', ' ', s)
        # Intentamos primero detectar si es ISO (YYYY-MM-DD) que es lo más común en tus fuentes
        if re.match(r'\d{4}-\d{2}-\d{2}', s):
            dt = pd.to_datetime(s, errors='coerce')
        else:
            # Si no parece ISO, usamos dayfirst para formatos latinos (DD/MM/YYYY)
            dt = pd.to_datetime(s, errors='coerce', dayfirst=True)
            
        if not pd.isna(dt):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        pass

    return s 

# ============================================================
# PARSER: EL UNIVERSAL
# ============================================================

def _get_date_el_universal(soup):
    # 1) Meta tag (Lo más fiable)
    meta = soup.find("meta", {"property": "article:published_time"})
    if meta and meta.get("content"):
        return meta["content"]
    
    # 2) <time datetime="...">
    t = soup.find("time")
    if t and t.has_attr("datetime"):
        return t.get("datetime")
        
    return None

def extract_data_el_universal(html, url):
    soup = BeautifulSoup(html, "html.parser")
    data = {"title": "Sin Título", "text": "", "date": "Sin Fecha", "url": url}
    
    # 1. Título
    title_tag = soup.find("h1")
    if title_tag:
        data["title"] = title_tag.get_text(strip=True)

    # 2. Texto con Limpieza
    paragraphs = soup.select('p.cl-at-p') or soup.find_all('p')
    clean_blocks = []
    for p in paragraphs:
        txt = p.get_text(strip=True)
        if len(txt) > 45 and not txt.lower().startswith("lee también"):
            clean_blocks.append(txt)
    data["text"] = " ".join(clean_blocks)

    # 3. FECHA (Búsqueda Multicapa para El Universal 2025)
    # A. Intentar con la etiqueta <time> (muy común en sus nuevas notas)
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        data["date"] = time_tag.get("datetime").split("T")[0]
    
    # B. Intentar con Meta Tags si falló la anterior
    if data["date"] == "Sin Fecha":
        meta_date = soup.select_one('meta[property="article:published_time"]') or \
                    soup.select_one('meta[name="published_at"]')
        if meta_date:
            data["date"] = meta_date.get("content", "").split("T")[0]

    # C. Búsqueda profunda en JSON-LD (Para notas con estructura compleja)
    if data["date"] == "Sin Fecha":
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                js = json.loads(s.string)
                # El Universal anida esto a veces en una lista
                items = js if isinstance(js, list) else [js]
                for item in items:
                    val = item.get("datePublished") or item.get("dateCreated")
                    if val:
                        data["date"] = str(val).split("T")[0]
                        break
                if data["date"] != "Sin Fecha": break
            except: continue
            
    return data

# ============================================================
# PARSER: MILENIO
# ============================================================

def _get_date_milenio(soup):
    # 1. JSON-LD
    for sc in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            jsdata = json.loads(sc.string or "")
            if isinstance(jsdata, list): jsdata = jsdata[0]
            if isinstance(jsdata, dict) and jsdata.get("datePublished"):
                return jsdata["datePublished"]
        except: pass
    
    # 2. Time tag
    t = soup.find("time")
    if t and t.has_attr("datetime"):
        return t["datetime"]
    
    return None

def extract_data_milenio(html, url):
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. TÍTULO
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Sin título"
        
        # 2. FECHA (Usa tu función auxiliar _get_date_milenio que ya tienes)
        date_raw = _get_date_milenio(soup)

        # 3. TEXTO (Actualizado para Milenio 2025)
        # Buscamos en el contenedor principal de la nota
        body = soup.select_one(".article-body-container") or soup.find("article")
        text = ""
        
        if body:
            # Eliminamos firmas, publicidad y etiquetas de video
            for extra in body(["script", "style", "figure", "aside", ".nd-related-news"]):
                extra.decompose()
                
            ps = body.find_all("p")
            # Filtramos párrafos basura
            text_blocks = []
            for p in ps:
                t = p.get_text(strip=True)
                if len(t) > 20 and "Suscríbete" not in t and "Lee también" not in t:
                    text_blocks.append(t)
            text = " ".join(text_blocks)
        
        return {
            "source": "milenio",
            "url": url,
            "title": title,
            "date": clean_date(date_raw),
            "text": text
        }
    except Exception as e:
        return {"source": "milenio", "url": url, "title": "Error", "date": None, "text": ""}
    
# ============================================================
# PARSER: DIARIO PORTAL
# ============================================================

def extract_data_diario_portal(html, url):
    soup = BeautifulSoup(html, "html.parser")
    data = {"source": "diarioportal", "title": "Sin Título", "text": "", "date": "Sin Fecha", "url": url}
    
    # 1. TÍTULO Y TEXTO (Se mantiene igual)
    title_tag = soup.find("h1", class_="entry-title") or soup.find("h1")
    if title_tag: data["title"] = title_tag.get_text(strip=True)
    
    content_area = soup.find("div", class_="td-post-content") or soup.find("article")
    if content_area:
        text_blocks = [p.get_text(strip=True) for p in content_area.find_all("p") if len(p.get_text(strip=True)) > 40]
        data["text"] = " ".join(text_blocks)

    # 2. FECHA: Lógica de cascada infalible
    def is_invalid(d):
        return d is None or d == "Sin Fecha"

    # A. Meta Tags
    meta = soup.select_one('meta[property="article:published_time"]') or soup.select_one('meta[name="publish_date"]')
    if meta and meta.get("content"):
        data["date"] = clean_date(meta["content"])

    # B. JSON-LD Graph
    if is_invalid(data["date"]):
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                js = json.loads(s.string)
                items = js.get("@graph", []) if isinstance(js, dict) and "@graph" in js else [js]
                for item in items:
                    val = item.get("datePublished") or item.get("dateModified")
                    if val:
                        data["date"] = clean_date(val)
                        break
                if not is_invalid(data["date"]): break
            except: continue

    # C. URL Fallback (Regex) - Si nada funcionó, el link tiene la fecha
    if is_invalid(data["date"]):
        match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if match:
            data["date"] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return data
    
# ============================================================
# PARSER: LA JORNADA
# ============================================================

def extract_data_jornada(html, url):
    soup = BeautifulSoup(html, "html.parser")
    data = {"title": "Sin Título", "text": "", "date": "Sin Fecha", "url": url}
    
    # 1. TÍTULO (Prioridad en Metadatos para evitar el header de fecha)
    # El tag meta og:title es el más fiable en La Jornada 2025
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title:
        # Limpiamos el nombre del medio si viene incluido
        data["title"] = og_title.get("content", "").replace(" - La Jornada", "")
    
    # Respaldo: Si no hay meta tag, buscamos h1 pero descartamos si es fecha
    if not data["title"] or data["title"] == "Sin Título" or "de 202" in data["title"].lower():
        all_h1s = soup.find_all("h1")
        for h1 in all_h1s:
            t = h1.get_text(strip=True)
            # Una noticia real suele ser larga y no contiene el formato de fecha del header
            if len(t) > 15 and "de 202" not in t.lower():
                data["title"] = t
                break

    # 2. TEXTO (Se mantiene tu lógica que ya funciona)
    content_area = (
        soup.find("div", id="article-text") or 
        soup.find("div", class_="nota-contenido") or
        soup.find("article")
    )
    if content_area:
        paragraphs = content_area.find_all("p")
        text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40]
        data["text"] = " ".join(text_blocks)

    # 3. FECHA (Mantenemos tu lógica de URL que ya validaste)
    match_url = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if match_url:
        data["date"] = f"{match_url.group(1)}-{match_url.group(2)}-{match_url.group(3)}"
    
    if data["date"] == "Sin Fecha":
        json_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_scripts:
            try:
                js = json.loads(script.string)
                if isinstance(js, list): js = js[0]
                f_date = js.get("datePublished") or js.get("uploadDate")
                if f_date:
                    data["date"] = str(f_date).split("T")[0]
                    break
            except: continue

    return data

# ============================================================
# PARSER: TV AZTECA NOTICIAS
# ============================================================

def extract_data_tvazteca(html, url):
    try:
        soup = BeautifulSoup(html, "html.parser")
        data = {"source": "tvazteca", "url": url, "title": "Sin título", "date": None, "text": ""}
        
        # 1. TÍTULO: Evitamos los menús buscando específicamente el título de la nota
        # Intentamos primero con metadatos de OpenGraph (son los más limpios)
        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and meta_title.get("content"):
            title_raw = meta_title["content"].split(" - ")[0].split(" | ")[0]
            data["title"] = title_raw.strip()
        else:
            # Respaldo: H1 dentro del área de artículo únicamente
            article_h1 = soup.select_one('article h1') or soup.select_one('.Article-title')
            if article_h1:
                data["title"] = article_h1.get_text(strip=True)

        # 2. FECHA: Prioridad absoluta a metadatos técnicos para evitar fechas de "hoy"
        meta_date = soup.select_one('meta[property="article:published_time"]') or \
                    soup.select_one('meta[name="published_at"]')
        
        if meta_date and meta_date.get("content"):
            data["date"] = clean_date(meta_date["content"])
        
        # 3. TEXTO: Solo extraemos de los contenedores de contenido real
        # Esto evita que tome el texto de AMLO o menús laterales
        content_container = soup.select_one(".Article-body") or \
                           soup.select_one(".RichText") or \
                           soup.select_one("article")
        
        if content_container:
            # Limpieza de basura dentro del texto
            for trash in content_container(["script", "style", "aside", "nav", "header", "footer"]):
                trash.decompose()
            
            ps = content_container.find_all("p")
            text_blocks = []
            for p in ps:
                txt = p.get_text(strip=True)
                # Filtro de calidad: más de 40 caracteres y que no sea ruido de navegación
                if len(txt) > 40 and not txt.startswith(("Descarga la app", "Léase también", "Video:", "Foto:")):
                    text_blocks.append(txt)
            
            data["text"] = " ".join(text_blocks)
        
        return data

    except Exception as e:
        logging.error(f"Error parseando TV Azteca ({url}): {e}")
        return {"source": "tvazteca", "url": url, "title": "Error", "date": None, "text": ""}