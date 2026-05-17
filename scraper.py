"""
scraper.py

Crawler y parser para Los Tiempos y El Deber.

Flujo:
  1. Lee la portada de cada portal y extrae links de noticias.
  2. Sigue cada link y extrae: título, URL y cuerpo limpio.
  3. Guarda en la base de datos con control de versiones.

Estrategias anti-bloqueo:
  - Rotación de User-Agents con la librería fake-useragent.
  - Delay aleatorio de 2-4 segundos entre peticiones.
  - Headers que imitan un navegador real (Accept, Accept-Language, etc.).
  - Sesión persistente de requests para reutilizar conexiones TCP.
"""

import time
import random
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
import cloudscraper
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from database import DatabaseManager

# ------------------------------------------------------------------
# Configuración de logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constantes de configuración
# ------------------------------------------------------------------
DELAY_MIN = 4.0   # segundos mínimos entre peticiones
DELAY_MAX = 8.0   # segundos máximos entre peticiones
TIMEOUT   = 15    # segundos para timeout de cada request
MAX_NOTICIAS_POR_PORTAL = 40  # límite por ejecución para no sobrecargar

PORTALES = {

    "Los Tiempos": {
        "portada": "https://www.lostiempos.com/actualidad",
        "dominio": "https://www.lostiempos.com",
        "parser": "parsear_lostiempos",
    },

    "EL DEBER": {
        "portada": "https://eldeber.com.bo/",
        "dominio": "https://eldeber.com.bo",
        "parser": "parsear_eldeber",
    },
}

# ------------------------------------------------------------------
# Helpers de HTTP
# ------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]
def _headers_aleatorios() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-BO,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.google.com/",
    }


def _pausa():
    """Espera un tiempo aleatorio entre DELAY_MIN y DELAY_MAX segundos."""
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    log.debug(f"Esperando {t:.1f}s...")
    time.sleep(t)


def _get(session: requests.Session, url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=_headers_aleatorios(), timeout=TIMEOUT)

        if resp.status_code == 403:
            log.warning(f"Posible bloqueo 403 en: {url}")
            time.sleep(300)
            return None

        if resp.status_code == 429:
            log.warning(f"Demasiadas peticiones 429 en: {url}")
            time.sleep(300)
            return None

        texto_lower = resp.text.lower()
        if "captcha" in texto_lower or "access denied" in texto_lower:
            log.warning(f"Posible CAPTCHA o bloqueo en: {url}")
            time.sleep(300)
            return None

        resp.raise_for_status()
        resp.encoding = "utf-8"
        html = resp.text

        if not html.lower().lstrip().startswith("<!doctype") and "<html" not in html.lower()[:500]:
            log.warning(f"Respuesta no parece HTML válido en: {url}")
            return None

        return BeautifulSoup(html, "html.parser")

    except requests.exceptions.Timeout:
        log.warning(f"Timeout al acceder a: {url}")
    except requests.exceptions.HTTPError as e:
        log.warning(f"Error HTTP {e.response.status_code} en: {url}")
    except requests.exceptions.RequestException as e:
        log.warning(f"Error de conexión en {url}: {e}")

    return None

# ------------------------------------------------------------------
# Parsers de portada (extracción de links)
# ------------------------------------------------------------------

def _links_lostiempos(soup: BeautifulSoup, dominio: str) -> list[str]:
    """
    Extrae links de noticias de la portada de Los Tiempos.
    Los artículos están en <a> dentro de contenedores de noticias,
    y siguen el patrón /actualidad/ o /hoy/.
    """
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Los Tiempos usa URLs relativas o absolutas con su dominio
        if href.startswith("/"):
            href = urljoin(dominio, href)
        # Filtrar solo links de noticias (excluir servicios, hemeroteca, etc.)
        partes = urlparse(href)
        segmentos = partes.path.strip("/").split("/")
        # Noticias tienen: /seccion/subseccion/fecha/slug  (≥ 3 segmentos)
        if (
            "lostiempos.com" in partes.netloc
            and len(segmentos) >= 3
            and any(s in segmentos[0] for s in ["actualidad", "hoy", "cochabamba", "pais"])
            and not any(excl in href for excl in ["#", "javascript", "mailto", "/rss", "/servicios"])
        ):
            links.add(href)
    return list(links)[:MAX_NOTICIAS_POR_PORTAL]


def _links_eldeber(soup: BeautifulSoup, dominio: str) -> list[str]:

    links = set()

    for a in soup.find_all("a", href=True):

        href = a["href"].strip()

        if href.startswith("/"):
            href = urljoin(dominio, href)

        partes = urlparse(href)

        if (
            "eldeber.com.bo" in partes.netloc
            and len(partes.path.strip("/").split("/")) >= 2
            and not any(x in href for x in ["#", "javascript", "mailto"])
        ):
            links.add(href)

    return list(links)[:MAX_NOTICIAS_POR_PORTAL]
# ------------------------------------------------------------------
# Parsers de artículo (extracción de contenido)
# ------------------------------------------------------------------

def parsear_lostiempos(soup: BeautifulSoup, url: str) -> dict | None:
    """
    Extrae título y cuerpo de una noticia de Los Tiempos.

    Estructura Drupal 7:
      - Título: <h1 class="page-header"> o <meta property="og:title">
      - Cuerpo:  <div class="field-name-body"> > <div class="field-items"> > <div class="field-item">
    """
    # Título
    titulo = None
    h1 = soup.find("h1", class_="page-header")
    if h1:
        titulo = h1.get_text(strip=True)
    else:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            titulo = og_title.get("content", "").strip()

    if not titulo:
        log.debug(f"Sin título en: {url}")
        return None

    # Cuerpo del artículo
    cuerpo_div = soup.find("div", class_="field-name-body")
    if not cuerpo_div:
        log.debug(f"Sin cuerpo (field-name-body) en: {url}")
        return None

    # Extraer solo los párrafos <p> del cuerpo (evita menús y publicidad)
    parrafos = cuerpo_div.find_all("p")
    texto = " ".join(p.get_text(" ", strip=True) for p in parrafos if p.get_text(strip=True))

    if len(texto) < 100:
        log.debug(f"Texto demasiado corto en: {url}")
        return None

    # Fecha de publicación desde meta tag
    fecha_pub = None
    meta_fecha = soup.find("meta", property="article:published_time")
    if meta_fecha:
        fecha_pub = meta_fecha.get("content", "")[:10]  # solo YYYY-MM-DD

    return {"titulo": titulo, "texto": texto, "fecha_pub": fecha_pub}


def parsear_eldeber(soup: BeautifulSoup, url: str) -> dict | None:

    titulo = None

    if soup.find("h1"):
        titulo = soup.find("h1").get_text(strip=True)

    if not titulo:
        return None

    cuerpo = []

    article = soup.find("article")

    if article:

        for p in article.find_all("p"):

            texto = p.get_text(" ", strip=True)

            if len(texto) > 40:
                cuerpo.append(texto)

    texto_final = " ".join(cuerpo).strip()

    if len(texto_final) < 200:
        return None

    return {
    "titulo": titulo,
    "texto": texto_final,
    "fecha_pub": None,
    }
# ------------------------------------------------------------------
# Función principal del scraper
# ------------------------------------------------------------------
def crear_sesion():
    session = cloudscraper.create_scraper()

    retry_strategy = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def ejecutar_scraping(db: DatabaseManager = None) -> dict:
    """
    Ejecuta el ciclo completo de scraping para todos los portales.

    Retorna un resumen con conteos por resultado para el log/dashboard.
    """
    if db is None:
        db = DatabaseManager()

    session = crear_sesion()
    resumen = {"nuevas": 0, "actualizadas": 0, "sin_cambios": 0, "errores": 0}

    for nombre_portal, config in PORTALES.items():
        log.info(f"═══ Iniciando scraping: {nombre_portal} ═══")

        # 1. Leer portada
        soup_portada = _get(session, config["portada"])
        if soup_portada is None:
            log.error(f"No se pudo acceder a la portada de {nombre_portal}")
            resumen["errores"] += 1
            continue

        _pausa()

        # 2. Extraer links de noticias
        if nombre_portal == "Los Tiempos":
            links = _links_lostiempos(soup_portada, config["dominio"])
        else:
            links = _links_eldeber(soup_portada, config["dominio"])

        log.info(f"  Encontrados {len(links)} links en {nombre_portal}")

        # 3. Procesar cada noticia
        parser_func = parsear_lostiempos if nombre_portal == "Los Tiempos" else parsear_eldeber

        for i, url in enumerate(links, 1):
            log.info(f"  [{i}/{len(links)}] Procesando: {url[:80]}...")
            soup_noticia = _get(session, url)

            if soup_noticia is None:
                resumen["errores"] += 1
                _pausa()
                continue

            datos = parser_func(soup_noticia, url)
            if datos is None:
                resumen["errores"] += 1
                _pausa()
                continue

            resultado = db.guardar_noticia(
                url=url,
                titulo=datos["titulo"],
                texto=datos["texto"],
                fuente=nombre_portal,
                fecha_pub=datos.get("fecha_pub"),
            )
            clave = {"nueva": "nuevas", "actualizada": "actualizadas",
                    "sin_cambios": "sin_cambios", "error": "errores"}.get(resultado, "errores")
            resumen[clave] += 1
            log.info(f"    → {resultado}: {datos['titulo'][:60]}")
            _pausa()

    log.info(f"Scraping completo. Resumen: {resumen}")
    return resumen


# ------------------------------------------------------------------
# Ejecución directa para pruebas
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("Iniciando scraping de prueba...")
    print("(Esto puede tardar varios minutos por los delays anti-bloqueo)\n")
    resumen = ejecutar_scraping()
    print(f"\nResumen final: {resumen}")
