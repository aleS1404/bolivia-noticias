"""
chatbot.py
==========
Chatbot RAG (Retrieval-Augmented Generation) para el proyecto Bolivia Noticias.

Flujo RAG:
  1. Las noticias de SQLite se convierten en vectores (embeddings) y se guardan en ChromaDB.
  2. Cuando el usuario hace una pregunta, se buscan los fragmentos más relevantes.
  3. Esos fragmentos se pasan como contexto al LLM (Gemini) junto con el prompt.
  4. Gemini responde SOLO basándose en ese contexto (no inventa información).

Dos modos de consulta:
  - "ruta"         : ¿Hay paso entre ciudad A y ciudad B? ¿Hay bloqueos?
  - "fact_checking": ¿Este texto coincide con lo reportado por los medios?
"""

import os
import logging
from pathlib import Path

import google.generativeai as genai
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from database import DatabaseManager

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------
load_dotenv()  # Carga variables desde el archivo .env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")
CHROMA_PATH      = Path(__file__).parent / "chroma_db"
COLECCION_NOMBRE = "noticias_bolivia"

# Modelo de embeddings multilingüe local (soporta español perfectamente)
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


# ------------------------------------------------------------------
# Clase principal del Chatbot RAG
# ------------------------------------------------------------------

class ChatbotRAG:
    """
    Chatbot que responde preguntas basándose EXCLUSIVAMENTE en las
    noticias almacenadas en la base de datos.
    """

    def __init__(self):
        self._validar_api_key()
        self._configurar_gemini()
        self._configurar_chromadb()
        self.db = DatabaseManager()

    def _validar_api_key(self):
        if not GEMINI_API_KEY:
            raise ValueError(
                "No se encontró GEMINI_API_KEY en el archivo .env\n"
                "Sigue la guía en el README para obtenerla."
            )

    def _configurar_gemini(self):
        """Inicializa el cliente de Gemini."""
        genai.configure(api_key=GEMINI_API_KEY)
        # gemini-1.5-flash: gratuito, rápido, 1 millón de tokens de contexto
        self.modelo = genai.GenerativeModel("gemini-2.5-flash")
        log.info("Gemini 2.5 Flash configurado correctamente.")

    def _configurar_chromadb(self):
        """
        Inicializa ChromaDB con embeddings multilingües locales.
        Los embeddings se calculan en tu máquina (sin costo, sin internet).
        """
        # Función de embeddings usando sentence-transformers
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        # Cliente persistente: guarda los vectores en disco
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.coleccion = client.get_or_create_collection(
            name=COLECCION_NOMBRE,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},  # distancia coseno para texto
        )
        log.info(f"ChromaDB listo. Colección '{COLECCION_NOMBRE}' con "
                 f"{self.coleccion.count()} documentos.")

    # ------------------------------------------------------------------
    # INDEXACIÓN: SQLite → ChromaDB
    # ------------------------------------------------------------------

    def indexar_noticias(self):
        """
        Lee todas las noticias de SQLite y las indexa en ChromaDB.
        Solo agrega noticias nuevas (verifica por ID para no duplicar).
        """
        noticias = self.db.obtener_todas()
        if not noticias:
            log.warning("No hay noticias en la base de datos. Ejecuta el scraper primero.")
            return 0

        # IDs ya indexados en ChromaDB
        ids_existentes = set(self.coleccion.get()["ids"])

        nuevas = 0
        documentos, metadatas, ids = [], [], []

        for noticia in noticias:
            doc_id = f"noticia_{noticia['id']}"
            if doc_id in ids_existentes:
                continue  # Ya indexada, saltar

            # El texto que se vectoriza combina título + cuerpo
            texto_completo = f"TÍTULO: {noticia['titulo']}\n\nCONTENIDO: {noticia['texto']}"

            documentos.append(texto_completo)
            metadatas.append({
                "url":       noticia["url"],
                "titulo":    noticia["titulo"],
                "fuente":    noticia["fuente"],
                "fecha_pub": noticia.get("fecha_pub") or "",
            })
            ids.append(doc_id)
            nuevas += 1

        if documentos:
            # ChromaDB acepta lotes de hasta 5000 documentos
            self.coleccion.add(documents=documentos, metadatas=metadatas, ids=ids)
            log.info(f"Indexadas {nuevas} noticias nuevas en ChromaDB.")
        else:
            log.info("Todas las noticias ya estaban indexadas.")

        return nuevas

    # ------------------------------------------------------------------
    # BÚSQUEDA: Recuperar contexto relevante
    # ------------------------------------------------------------------

    def _recuperar_contexto(self, consulta: str, n_resultados: int = 2) -> list[dict]:
        """
        Busca en ChromaDB los N documentos más similares a la consulta.
        Retorna lista de dicts con 'texto', 'titulo', 'fuente', 'url'.
        """
        if self.coleccion.count() == 0:
            log.warning("ChromaDB vacío. Indexando noticias primero...")
            self.indexar_noticias()

        resultados = self.coleccion.query(
            query_texts=[consulta],
            n_results=min(n_resultados, self.coleccion.count()),
        )

        contextos = []
        for i, doc in enumerate(resultados["documents"][0]):
            meta = resultados["metadatas"][0][i]
            contextos.append({
                "texto":  doc,
                "titulo": meta.get("titulo", ""),
                "fuente": meta.get("fuente", ""),
                "url":    meta.get("url", ""),
            })
        return contextos

    # ------------------------------------------------------------------
    # CONSULTA MODO 1: Ruta Segura / Bloqueos
    # ------------------------------------------------------------------

    def consultar_ruta(self, pregunta: str) -> str:
        """
        Responde si hay paso libre o bloqueos en rutas bolivianas.
        Ejemplo: "¿Hay paso en la ruta La Paz - Cochabamba?"
        """
        contextos = self._recuperar_contexto(pregunta, n_resultados=2)

        if not contextos:
            return "No hay noticias indexadas. Ejecuta el scraper y luego indexar_noticias()."

        # Construir el contexto para el prompt
        texto_contexto = "\n\n---\n\n".join(
            f"[Fuente: {c['fuente']} | {c['titulo']}]\n{c['texto'][:400]}"
            for c in contextos
        )

        prompt = f"""Eres un asistente experto en transitabilidad y bloqueos de carreteras en Bolivia.
Tu función es responder preguntas sobre el estado de las rutas y bloqueos ÚNICAMENTE basándote
en las noticias proporcionadas como contexto. NO inventes información.

Si las noticias no mencionan la ruta o ciudad consultada, di claramente:
"No encontré información específica sobre esa ruta en las noticias recientes."

CONTEXTO (noticias recientes):
{texto_contexto}

PREGUNTA DEL USUARIO:
{pregunta}

Responde de forma clara y concisa. Menciona las fuentes (nombre del medio) al final.
Si hay bloqueos, especifica dónde y desde cuándo si la información está disponible.
Responde SIEMPRE en español."""

        try:
            respuesta = self.modelo.generate_content(prompt)
            return respuesta.text
        except Exception as e:
            log.error(f"Error al consultar Gemini: {e}")
            return f"Error al procesar la consulta: {e}"

    # ------------------------------------------------------------------
    # CONSULTA MODO 2: Fact-Checking
    # ------------------------------------------------------------------

    def fact_checking(self, texto_a_verificar: str) -> str:
        """
        Evalúa si un texto ingresado coincide con lo reportado en los medios.
        Útil para verificar si una noticia compartida en redes es real o falsa.
        """
        # Buscar contexto relacionado con el texto a verificar
        contextos = self._recuperar_contexto(texto_a_verificar, n_resultados=2)

        texto_contexto = "\n\n---\n\n".join(
            f"[Fuente: {c['fuente']} | {c['titulo']}]\n{c['texto'][:400]}"
            for c in contextos
        ) if contextos else "No se encontraron noticias relacionadas en la base de datos."

        prompt = f"""Eres un verificador de hechos (fact-checker) especializado en noticias de Bolivia.
Tu tarea es analizar si el texto proporcionado por el usuario coincide, contradice o no puede
verificarse con las noticias indexadas en nuestra base de datos.

INSTRUCCIONES:
1. Compara el texto del usuario con el contexto de noticias.
2. Emite un veredicto claro: VERIFICADO / CONTRADICE LO REPORTADO / NO VERIFICABLE.
3. Explica brevemente por qué, citando las fuentes disponibles.
4. Si el contexto no es suficiente, dilo explícitamente.
5. NO asumas que algo es falso solo porque no está en las noticias.

CONTEXTO (noticias de Los Tiempos y Red Uno):
{texto_contexto}

TEXTO A VERIFICAR:
"{texto_a_verificar}"

Formato de respuesta:
🔍 VEREDICTO: [VERIFICADO / CONTRADICE LO REPORTADO / NO VERIFICABLE]
📋 ANÁLISIS: [Explicación detallada]
📰 FUENTES CONSULTADAS: [Lista de medios/titulares relevantes]

Responde SIEMPRE en español."""

        try:
            respuesta = self.modelo.generate_content(prompt)
            return respuesta.text
        except Exception as e:
            log.error(f"Error al consultar Gemini: {e}")
            return f"Error al procesar la verificación: {e}"

    # ------------------------------------------------------------------
    # CONSULTA GENERAL
    # ------------------------------------------------------------------

    def consultar(self, pregunta: str, modo: str = "general") -> str:
        """
        Punto de entrada único para el chatbot.

        Modos:
          "ruta"         → Información sobre bloqueos y transitabilidad.
          "fact_checking"→ Verificar si un texto coincide con los medios.
          "general"      → Pregunta general sobre las noticias.
        """
        if modo == "ruta":
            return self.consultar_ruta(pregunta)
        elif modo == "fact_checking":
            return self.fact_checking(pregunta)
        else:
            # Modo general: responde cualquier pregunta basada en las noticias
            contextos = self._recuperar_contexto(pregunta, n_resultados=2)
            texto_contexto = "\n\n---\n\n".join(
                f"[{c['fuente']} - {c['titulo']}]\n{c['texto'][:400]}"
                for c in contextos
            ) if contextos else "Sin noticias relacionadas."

            prompt = f"""Eres un asistente informativo sobre Bolivia. Responde la pregunta
del usuario ÚNICAMENTE basándote en las noticias del contexto. Si no tienes información
suficiente, dilo claramente. No inventes datos.

CONTEXTO:
{texto_contexto}

PREGUNTA: {pregunta}

Responde en español de forma clara y cita las fuentes."""

            try:
                return self.modelo.generate_content(prompt).text
            except Exception as e:
                return f"Error: {e}"


# ------------------------------------------------------------------
# Prueba de la consola interactiva
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("═" * 60)
    print("  Chatbot RAG - Bolivia Noticias")
    print("═" * 60)
    print("\nInicializando... (la primera vez descarga el modelo de embeddings)\n")

    try:
        bot = ChatbotRAG()
        bot.indexar_noticias()

        print("\nModos disponibles:")
        print("  1 - Consulta de rutas y bloqueos")
        print("  2 - Fact-checking")
        print("  3 - Pregunta general")
        print("  q - Salir\n")

        while True:
            modo_input = input("Modo (1/2/3/q): ").strip()
            if modo_input.lower() == "q":
                break

            modos = {"1": "ruta", "2": "fact_checking", "3": "general"}
            modo = modos.get(modo_input, "general")

            pregunta = input("Tu pregunta: ").strip()
            if not pregunta:
                continue

            print("\nProcesando...\n")
            respuesta = bot.consultar(pregunta, modo=modo)
            print("─" * 60)
            print(respuesta)
            print("─" * 60 + "\n")

    except ValueError as e:
        print(f"\n[ERROR] {e}")
    except KeyboardInterrupt:
        print("\n\nSaliendo...")
