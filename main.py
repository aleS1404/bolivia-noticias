"""
main.py
Orquestador del pipeline Bolivia Noticias.

Uso:
  python main.py pipeline
  python main.py
"""

import sys
import logging
from datetime import datetime

from database import DatabaseManager
from scraper import ejecutar_scraping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bolivia_noticias.log", encoding="utf-8"),
    ],
)

log = logging.getLogger(__name__)

def ejecutar_pipeline():
    inicio = datetime.now()

    log.info("=" * 60)
    log.info(f"INICIO DE PIPELINE: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    db = DatabaseManager()

    log.info("PASO 1: Scraping de noticias...")
    resumen = ejecutar_scraping(db)
    log.info(f"Scraping completado: {resumen}")

    log.info("PASO 2: Indexación ChromaDB opcional desde app.py/chatbot.py")
    log.info("El dashboard principal ahora se ejecuta con: streamlit run app.py")

    fin = datetime.now()
    duracion = (fin - inicio).seconds

    log.info(f"PIPELINE COMPLETADO en {duracion}s. {resumen}")

    return resumen


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "pipeline"

    if modo == "pipeline":
        ejecutar_pipeline()
    else:
        print("Modo no reconocido.")
        print("Uso correcto:")
        print("  python main.py pipeline")
        print("Dashboard:")
        print("  streamlit run app.py")


if __name__ == "__main__":
    main()