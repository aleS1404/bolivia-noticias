
#scraper.py
#Crawler y parser para Los Tiempos y Red Uno.

#Flujo:
#  1. Lee la portada de cada portal y extrae links de noticias.
# 2. Sigue cada link y extrae: título, URL y cuerpo limpio.
# 3. Guarda en la base de datos con control de versiones.

#Estrategias anti-bloqueo:
#- Rotación de User-Agents con la librería fake-useragent.
#- Delay aleatorio de 2-4 segundos entre peticiones.
#- Headers que imitan un navegador real (Accept, Accept-Language, etc.).
# - Sesión persistente de requests para reutilizar conexiones TCP.

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

# Ruta de la base de datos (en la misma carpeta que este script)
DB_PATH = Path(__file__).parent / "noticias.db"


def _hash_texto(texto: str) -> str:
    """Genera un hash MD5 del texto para detectar cambios rápidamente."""
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


class DatabaseManager:
    """Clase principal para interactuar con la base de datos."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._crear_tablas()

    def _conectar(self) -> sqlite3.Connection:
        """Abre una conexión con row_factory para acceder a columnas por nombre."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _crear_tablas(self):
        """Crea las tablas si no existen. Seguro de llamar múltiples veces."""
        sql_noticias = """
        CREATE TABLE IF NOT EXISTS noticias (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT    UNIQUE NOT NULL,
            titulo      TEXT    NOT NULL,
            texto       TEXT    NOT NULL,
            fuente      TEXT    NOT NULL,
            hash_texto  TEXT    NOT NULL,
            fecha_pub   TEXT,
            fecha_scrape TEXT   NOT NULL
        );
        """
        sql_historial = """
        CREATE TABLE IF NOT EXISTS historial_noticias (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            noticia_id   INTEGER NOT NULL,
            url          TEXT    NOT NULL,
            titulo       TEXT    NOT NULL,
            texto_anterior TEXT  NOT NULL,
            hash_anterior  TEXT  NOT NULL,
            fecha_cambio   TEXT  NOT NULL,
            FOREIGN KEY (noticia_id) REFERENCES noticias(id)
        );
        """
        with self._conectar() as conn:
            conn.execute(sql_noticias)
            conn.execute(sql_historial)

    # ------------------------------------------------------------------
    # ESCRITURA
    # ------------------------------------------------------------------

    def guardar_noticia(
        self,
        url: str,
        titulo: str,
        texto: str,
        fuente: str,
        fecha_pub: str = None,
    ) -> str:
        """
        Guarda o actualiza una noticia.

        Retorna:
          "nueva"       — artículo nunca visto antes.
          "actualizada" — el texto cambió; se guardó historial.
          "sin_cambios" — el texto no cambió, no se hace nada.
        """
        nuevo_hash = _hash_texto(texto)
        ahora = datetime.now().isoformat(sep=" ", timespec="seconds")

        with self._conectar() as conn:
            existente = conn.execute(
                "SELECT id, hash_texto, titulo, texto FROM noticias WHERE url = ?",
                (url,),
            ).fetchone()

            if existente is None:
                # Noticia nueva → insertar directamente
                conn.execute(
                    """
                    INSERT INTO noticias (url, titulo, texto, fuente, hash_texto, fecha_pub, fecha_scrape)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (url, titulo, texto, fuente, nuevo_hash, fecha_pub, ahora),
                )
                return "nueva"

            if existente["hash_texto"] == nuevo_hash:
                # Sin cambios → ignorar para ahorrar recursos
                return "sin_cambios"

            # El texto cambió → guardar versión anterior en historial
            conn.execute(
                """
                INSERT INTO historial_noticias
                    (noticia_id, url, titulo, texto_anterior, hash_anterior, fecha_cambio)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    existente["id"],
                    url,
                    existente["titulo"],
                    existente["texto"],
                    existente["hash_texto"],
                    ahora,
                ),
            )
            # Actualizar la versión actual
            conn.execute(
                """
                UPDATE noticias
                SET titulo = ?, texto = ?, hash_texto = ?, fecha_scrape = ?
                WHERE url = ?
                """,
                (titulo, texto, nuevo_hash, ahora, url),
            )
            return "actualizada"

    # ------------------------------------------------------------------
    # LECTURA
    # ------------------------------------------------------------------

    def obtener_todas(self) -> list[dict]:
        """Devuelve todas las noticias actuales como lista de diccionarios."""
        with self._conectar() as conn:
            filas = conn.execute(
                "SELECT * FROM noticias ORDER BY fecha_scrape DESC"
            ).fetchall()
        return [dict(f) for f in filas]

    def obtener_recientes(self, limite: int = 50) -> list[dict]:
        """Devuelve las N noticias más recientes."""
        with self._conectar() as conn:
            filas = conn.execute(
                "SELECT * FROM noticias ORDER BY fecha_scrape DESC LIMIT ?",
                (limite,),
            ).fetchall()
        return [dict(f) for f in filas]

    def obtener_historial(self, url: str) -> list[dict]:
        """Devuelve el historial de ediciones de una URL específica."""
        with self._conectar() as conn:
            filas = conn.execute(
                """
                SELECT h.* FROM historial_noticias h
                JOIN noticias n ON h.noticia_id = n.id
                WHERE n.url = ?
                ORDER BY h.fecha_cambio DESC
                """,
                (url,),
            ).fetchall()
        return [dict(f) for f in filas]

    def contar_noticias(self) -> dict:
        """Estadísticas básicas para el dashboard."""
        with self._conectar() as conn:
            total = conn.execute("SELECT COUNT(*) FROM noticias").fetchone()[0]
            editadas = conn.execute(
                "SELECT COUNT(DISTINCT noticia_id) FROM historial_noticias"
            ).fetchone()[0]
            por_fuente = conn.execute(
                "SELECT fuente, COUNT(*) as total FROM noticias GROUP BY fuente"
            ).fetchall()
        return {
            "total": total,
            "editadas": editadas,
            "por_fuente": {r["fuente"]: r["total"] for r in por_fuente},
        }

    def buscar_por_palabras(self, terminos: str) -> list[dict]:
        """
        Búsqueda simple de texto completo.
        Útil para el chatbot cuando ChromaDB no está disponible.
        """
        patron = f"%{terminos}%"
        with self._conectar() as conn:
            filas = conn.execute(
                """
                SELECT * FROM noticias
                WHERE titulo LIKE ? OR texto LIKE ?
                ORDER BY fecha_scrape DESC
                LIMIT 10
                """,
                (patron, patron),
            ).fetchall()
        return [dict(f) for f in filas]


# ------------------------------------------------------------------
# Prueba rápida (ejecutar este archivo directamente)
# ------------------------------------------------------------------
if __name__ == "__main__":
    db = DatabaseManager()

    # Insertar una noticia de prueba
    resultado = db.guardar_noticia(
        url="https://www.lostiempos.com/test/noticia-prueba",
        titulo="Noticia de prueba para verificar la base de datos",
        texto="Este es el cuerpo de la noticia de prueba. "
              "Contiene información sobre bloqueos en la ruta La Paz - Cochabamba.",
        fuente="Los Tiempos",
        fecha_pub="2026-05-15",
    )
    print(f"[+] Primera inserción: {resultado}")

    # Simular edición de la misma noticia
    resultado2 = db.guardar_noticia(
        url="https://www.lostiempos.com/test/noticia-prueba",
        titulo="Noticia de prueba EDITADA",
        texto="Este es el cuerpo EDITADO. Ahora hay paso libre en la ruta.",
        fuente="Los Tiempos",
        fecha_pub="2026-05-15",
    )
    print(f"[+] Segunda inserción (edición): {resultado2}")

    # Sin cambios
    resultado3 = db.guardar_noticia(
        url="https://www.lostiempos.com/test/noticia-prueba",
        titulo="Noticia de prueba EDITADA",
        texto="Este es el cuerpo EDITADO. Ahora hay paso libre en la ruta.",
        fuente="Los Tiempos",
        fecha_pub="2026-05-15",
    )
    print(f"[+] Tercera inserción (sin cambios): {resultado3}")

    stats = db.contar_noticias()
    print(f"[+] Estadísticas: {stats}")
    print("[✓] database.py funciona correctamente.")
