"""
chatbot_local.py

Chatbot local usando TF-IDF + similitud de coseno.
No usa ninguna API externa ni internet.

Flujo:
  1. Carga noticias desde SQLite vía DatabaseManager.
  2. Vectoriza corpus (título + texto) con TfidfVectorizer.
  3. Ante una consulta, calcula similitud de coseno.
  4. Devuelve las top-k noticias más similares con su score.
"""

import logging
from typing import Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger(__name__)

# Umbral mínimo de similitud para considerar una coincidencia relevante
UMBRAL_RELEVANCIA = 0.08

# Stopwords en español (sin depender de NLTK)
STOPWORDS_ES = [
    "de","la","el","en","y","a","los","del","se","las","un","por","con","una",
    "su","para","es","al","lo","como","más","pero","sus","le","ya","o","fue",
    "este","ha","si","porque","esta","son","entre","cuando","muy","sin","sobre",
    "también","me","hasta","hay","donde","quien","desde","todo","nos","durante",
    "todos","uno","les","ni","contra","otros","ese","eso","ante","ellos","e",
    "esto","antes","algunos","qué","unos","otro","otras","otra","él","tanto",
    "esa","estos","mucho","cual","poco","ella","estar","estas","algunas","algo",
    "nosotros","mi","mis","tú","te","ti","tu","tus","que","no","ser","hacer",
    "tener","haber","poder","ir","ver","han","sido","hizo","era","eran","tiene",
    "tienen","le","les","les","nos","os","me","te","se","si","ya","aun","bien",
    "cada","cual","cuyo","desde","donde","ello","entre","esta","este","esos",
    "esas","aquí","allí","allá","ahora","luego","pues","así","ante","bajo",
    "cabe","con","contra","de","desde","en","entre","hacia","hasta","para",
    "por","según","sin","so","sobre","tras","versus","vía",
]


class ChatbotLocal:
    """
    Chatbot sin API externa. Usa TF-IDF sobre el corpus de noticias SQLite.
    """

    def __init__(self, db=None):
        from database import DatabaseManager
        self.db = db or DatabaseManager()
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._matriz = None
        self._df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Carga y vectorización
    # ------------------------------------------------------------------

    def cargar_y_vectorizar(self) -> int:
        """
        Carga todas las noticias y construye la matriz TF-IDF.
        Llama a este método antes de consultar, o cuando el corpus cambie.
        Retorna el número de documentos indexados.
        """
        noticias = self.db.obtener_todas()
        if not noticias:
            log.warning("No hay noticias en la BD para vectorizar.")
            self._df = pd.DataFrame()
            return 0

        self._df = pd.DataFrame(noticias)

        # Corpus: título + texto (da más peso al título al repetirlo)
        corpus = (
            self._df["titulo"].fillna("") + " " +
            self._df["titulo"].fillna("") + " " +   # título x2 para mayor peso
            self._df["texto"].fillna("")
        ).tolist()

        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words=STOPWORDS_ES,
            max_features=8000,
            ngram_range=(1, 2),      # unigramas y bigramas
            sublinear_tf=True,       # log(1+tf) reduce el peso de palabras muy frecuentes
            min_df=1,
            strip_accents="unicode",
        )
        self._matriz = self._vectorizer.fit_transform(corpus)
        log.info(f"Corpus vectorizado: {self._matriz.shape[0]} docs, "
                 f"{self._matriz.shape[1]} features.")
        return len(noticias)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def buscar(self, consulta: str, top_k: int = 5) -> dict:
        """
        Busca las noticias más similares a la consulta.

        Retorna:
          {
            "resultados": DataFrame con columnas extra 'similitud' y 'relevante',
            "tiene_resultados": bool,
            "mensaje": str,
            "max_similitud": float,
          }
        """
        if self._vectorizer is None or self._df is None or len(self._df) == 0:
            n = self.cargar_y_vectorizar()
            if n == 0:
                return {
                    "resultados": pd.DataFrame(),
                    "tiene_resultados": False,
                    "mensaje": "⚠️ No hay noticias en la base de datos. Ejecuta el scraping primero.",
                    "max_similitud": 0.0,
                }

        consulta = consulta.strip()
        if not consulta:
            return {
                "resultados": pd.DataFrame(),
                "tiene_resultados": False,
                "mensaje": "Escribe una pregunta o tema para buscar.",
                "max_similitud": 0.0,
            }

        try:
            consulta_vec = self._vectorizer.transform([consulta])
            similitudes  = cosine_similarity(consulta_vec, self._matriz).flatten()

            indices = similitudes.argsort()[::-1][:top_k]
            resultados = self._df.iloc[indices].copy()
            resultados["similitud"] = similitudes[indices]
            resultados["relevante"] = resultados["similitud"] >= UMBRAL_RELEVANCIA

            max_sim = float(similitudes[indices[0]]) if len(indices) else 0.0

            if max_sim < UMBRAL_RELEVANCIA:
                mensaje = (
                    "No encontré coincidencias fuertes con tu consulta, "
                    "pero estas son las noticias más cercanas en el corpus."
                )
            elif max_sim < 0.25:
                mensaje = "Encontré noticias relacionadas con tu consulta."
            else:
                mensaje = f"Encontré {int(resultados['relevante'].sum())} noticias relevantes."

            return {
                "resultados": resultados,
                "tiene_resultados": True,
                "mensaje": mensaje,
                "max_similitud": max_sim,
            }

        except Exception as e:
            log.error(f"Error en búsqueda TF-IDF: {e}")
            return {
                "resultados": pd.DataFrame(),
                "tiene_resultados": False,
                "mensaje": f"Error al procesar la consulta: {e}",
                "max_similitud": 0.0,
            }

    def invalidar_cache(self):
        """Fuerza re-vectorización en la próxima consulta."""
        self._vectorizer = None
        self._matriz = None
        self._df = None
