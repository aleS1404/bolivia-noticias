"""
main.py
=======
Orquestador principal del proyecto Bolivia Noticias.

Funciones:
  - Ejecutar el pipeline completo: scraping → indexación en ChromaDB.
  - Lanzar el dashboard web con Flask.
  - Punto de entrada para el Programador de Tareas de Windows.

Uso:
  python main.py pipeline    # Solo scraping + indexación (para automatización)
  python main.py dashboard   # Lanza el servidor web en http://localhost:5000
  python main.py todo        # Pipeline + dashboard
  python main.py             # Por defecto: todo
"""

import sys
import logging
from datetime import datetime

from flask import Flask, render_template, request, jsonify

from database import DatabaseManager
from scraper import ejecutar_scraping
from chatbot import ChatbotRAG

# ------------------------------------------------------------------
# Configuración de logging
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Instancias globales
# ------------------------------------------------------------------
db  = DatabaseManager()
app = Flask(__name__)

# El chatbot se inicializa de forma lazy (solo cuando se necesita)
_chatbot: ChatbotRAG | None = None


def obtener_chatbot() -> ChatbotRAG:
    """Inicializa el chatbot una sola vez (patrón Singleton simple)."""
    global _chatbot
    if _chatbot is None:
        _chatbot = ChatbotRAG()
        _chatbot.indexar_noticias()
    return _chatbot


# ------------------------------------------------------------------
# PIPELINE
# ------------------------------------------------------------------

def ejecutar_pipeline():
    """
    Ciclo completo:
      1. Scraping de Los Tiempos y Red Uno.
      2. Indexación de noticias nuevas en ChromaDB.
    """
    inicio = datetime.now()
    log.info("=" * 60)
    log.info(f"INICIO DE PIPELINE: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # Paso 1: Scraping
    log.info("PASO 1: Scraping de noticias...")
    resumen = ejecutar_scraping(db)
    log.info(f"Scraping completado: {resumen}")

    # Paso 2: Indexar en ChromaDB (solo si hay API key configurada)
    try:
        log.info("PASO 2: Indexando noticias en ChromaDB...")
        bot = obtener_chatbot()
        nuevas_indexadas = bot.indexar_noticias()
        log.info(f"Indexadas {nuevas_indexadas} noticias nuevas en ChromaDB.")
    except ValueError as e:
        log.warning(f"No se indexó en ChromaDB: {e}")
        log.warning("El chatbot no estará disponible hasta configurar GEMINI_API_KEY.")

    fin = datetime.now()
    duracion = (fin - inicio).seconds
    log.info(f"PIPELINE COMPLETADO en {duracion}s. {resumen}")
    return resumen


# ------------------------------------------------------------------
# RUTAS DEL DASHBOARD FLASK
# ------------------------------------------------------------------

TOPICOS = {
    "bloqueos": ["bloqueo", "bloqueos", "desbloqueo", "ruta", "carretera", "transitabilidad"],
    "politica": ["gobierno", "presidente", "ministro", "diputado", "asamblea", "elecciones"],
    "economia": ["economía", "dólar", "combustible", "ypfb", "precio", "exportación", "importación"],
    "seguridad": ["policía", "aprehendido", "delito", "atraco", "violencia", "detenido"],
    "salud": ["salud", "hospital", "paciente", "médico", "enfermedad"],
    "educacion": ["maestro", "educación", "universidad", "colegio", "estudiantes"],
    "deportes": ["fútbol", "bolívar", "oriente", "blooming", "deporte", "copa"]
}


def clasificar_topico(texto):
    texto = texto.lower()
    puntajes = {}

    for topico, palabras in TOPICOS.items():
        puntajes[topico] = sum(1 for p in palabras if p in texto)

    mejor = max(puntajes, key=puntajes.get)

    if puntajes[mejor] == 0:
        return "general"

    return mejor


@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    topico = request.args.get("topico", "").strip().lower()
    fecha = request.args.get("fecha", "").strip()

    noticias = db.obtener_recientes(limite=200)

    for n in noticias:
        contenido = f"{n['titulo']} {n['texto']}"
        n["topico"] = clasificar_topico(contenido)

    if q:
        noticias = [
            n for n in noticias
            if q in n["titulo"].lower() or q in n["texto"].lower()
        ]

    if topico:
        noticias = [n for n in noticias if n["topico"] == topico]

    if fecha:
        noticias = [
            n for n in noticias
            if (n.get("fecha_pub") or n.get("fecha_scrape") or "")[:10] == fecha
        ]

    estadisticas = db.contar_noticias()

    return render_template(
        "index.html",
        noticias=noticias,
        stats=estadisticas,
        topicos=list(TOPICOS.keys()) + ["general"],
        q=q,
        topico_actual=topico,
        fecha_actual=fecha
    )

@app.route("/chatbot")
def pagina_chatbot():
    """Página del chatbot interactivo."""
    return render_template("chatbot.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Endpoint de la API para el chatbot.
    Recibe JSON: {"pregunta": "...", "modo": "ruta|fact_checking|general"}
    Retorna JSON: {"respuesta": "..."}
    """
    datos = request.get_json()
    if not datos or "pregunta" not in datos:
        return jsonify({"error": "Falta el campo 'pregunta'"}), 400

    pregunta = datos["pregunta"].strip()
    modo     = datos.get("modo", "general")

    if not pregunta:
        return jsonify({"error": "La pregunta no puede estar vacía"}), 400

    try:
        bot       = obtener_chatbot()
        respuesta = bot.consultar(pregunta, modo=modo)
        return jsonify({"respuesta": respuesta})
    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        log.error(f"Error en /api/chat: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/api/pipeline", methods=["POST"])
def api_pipeline():
    """
    Ejecuta el pipeline de scraping manualmente desde el dashboard.
    Retorna un resumen del proceso.
    """
    try:
        resumen = ejecutar_pipeline()
        return jsonify({"ok": True, "resumen": resumen})
    except Exception as e:
        log.error(f"Error en /api/pipeline: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    """Estadísticas actualizadas para el dashboard."""
    return jsonify(db.contar_noticias())


@app.route("/historial/<path:url_noticia>")
def ver_historial(url_noticia):
    """Muestra el historial de ediciones de una noticia."""
    historial = db.obtener_historial(url_noticia)
    return render_template("historial.html", historial=historial, url=url_noticia)


# ------------------------------------------------------------------
# PUNTO DE ENTRADA
# ------------------------------------------------------------------

def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "todo"

    if modo == "pipeline":
        # Solo scraping + indexación (para el Programador de Tareas)
        ejecutar_pipeline()

    elif modo == "dashboard":
        # Solo el servidor web
        log.info("Iniciando dashboard en http://localhost:5000")
        app.run(debug=False, host="0.0.0.0", port=5000)

    elif modo in ("todo", ""):
        # Pipeline completo + dashboard
        ejecutar_pipeline()
        log.info("Iniciando dashboard en http://localhost:5000")
        app.run(debug=False, host="0.0.0.0", port=5000)

    else:
        print(f"Modo desconocido: '{modo}'")
        print("Uso: python main.py [pipeline|dashboard|todo]")
        sys.exit(1)


if __name__ == "__main__":
    main()
