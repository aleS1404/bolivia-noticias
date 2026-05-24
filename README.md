# Bolivia Noticias — Streamlit + NLP + RAG

Sistema inteligente de monitoreo de noticias bolivianas mediante **Web Scraping**, **Procesamiento de Lenguaje Natural (NLP)**, **Recuperación Semántica (RAG)** y **Dashboards Interactivos en Streamlit**.

El proyecto permite:

- Extraer noticias automáticamente desde medios bolivianos.
- Almacenar noticias en SQLite.
- Clasificar noticias por tópicos.
- Visualizar métricas y gráficos interactivos.
- Consultar noticias mediante un chatbot con Gemini API.
- Consultar noticias mediante un chatbot local TF-IDF.
- Escuchar respuestas mediante voz IA con Edge-TTS.
- Automatizar scraping mediante Windows Task Scheduler.

---

# Tecnologías utilizadas

| Tecnología | Uso |
|---|---|
| Python | Lenguaje principal |
| Streamlit | Dashboard interactivo |
| SQLite | Base de datos local |
| ChromaDB | Base vectorial |
| Gemini API | Chatbot RAG |
| TF-IDF | Chatbot local |
| Sentence Transformers | Embeddings |
| BeautifulSoup | Parsing HTML |
| Requests | Peticiones HTTP |
| Edge-TTS | Voz IA |
| Plotly | Visualizaciones |
| Pandas | Manipulación de datos |

---

# Fuentes de noticias

- Los Tiempos
- El Deber

---

# Arquitectura del sistema

```txt
Portales Web
     │
     ▼
scraper.py
(Web Scraping)
     │
     ▼
database.py
(SQLite + historial)
     │
     ├──────────────► chatbot_local.py
     │                 (TF-IDF + similitud coseno)
     │
     ▼
chatbot.py
(RAG + ChromaDB + Gemini)
     │
     ▼
app.py
(Streamlit Dashboard)
     │
     ▼
Usuario final
```

---

# Estructura del proyecto

```txt
bolivia_noticias/
│
├── app.py                    # Dashboard principal Streamlit
├── chatbot.py                # Chatbot RAG con Gemini
├── chatbot_local.py          # Chatbot TF-IDF local
├── scraper.py                # Web scraping
├── database.py               # Gestión SQLite
├── voz_edge.py               # Voz IA con Edge-TTS
├── main.py                   # Pipeline principal
│
├── noticias.db               # Base de datos SQLite
├── chroma_db/                # Base vectorial ChromaDB
│
├── ejecutar_pipeline.bat     # Automatización Windows
├── requirements.txt          # Dependencias
├── README.md                 # Documentación
├── .gitignore
├── .env
│
├── templates/                # (legacy Flask)
├── __pycache__/
├── venv/
└── venv312/
```

---

# Características principales

## Dashboard Streamlit

Incluye:

- KPIs
- Timeline de noticias
- Noticias por tópico
- Noticias por fecha
- Filtros avanzados
- Búsqueda textual
- Visualizaciones interactivas

---

## Chatbot Gemini (RAG)

Implementa:

- Gemini API
- Recuperación semántica
- Embeddings
- Búsqueda contextual
- ChromaDB

### Flujo

```txt
Pregunta usuario
      │
      ▼
ChromaDB busca noticias relevantes
      │
      ▼
Contexto enviado a Gemini
      │
      ▼
Gemini responde usando SOLO noticias reales
```

---

## Chatbot Local (sin API)

Implementa:

- TF-IDF
- Similitud de coseno
- Recuperación local de noticias

No necesita internet ni APIs externas.

### Flujo

```txt
Noticias SQLite
      │
      ▼
TF-IDF vectoriza corpus
      │
      ▼
Consulta usuario
      │
      ▼
Similitud coseno
      │
      ▼
Top noticias relevantes
```

---

## Voz IA

Se implementó:

- Edge-TTS
- Conversión texto → voz
- Reproducción automática

---

# Instalación

## 1. Clonar repositorio

```bash
git clone https://github.com/TU-USUARIO/bolivia_noticias.git

cd bolivia_noticias
```

---

## 2. Crear entorno virtual

### Python 3.12 recomendado

```bash
py -3.12 -m venv venv312
```

### Activar entorno

```bash
venv312\Scripts\activate
```

---

## 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

# Variables de entorno

Crear archivo:

```txt
.env
```

Agregar:

```env
GEMINI_API_KEY=TU_API_KEY
```

---

# Ejecutar Streamlit

```bash
streamlit run app.py
```

Abrir:

```txt
http://localhost:8501
```

---

# Ejecutar pipeline

```bash
python main.py pipeline
```

---

# Automatización con Windows Task Scheduler

El archivo:

```txt
ejecutar_pipeline.bat
```

permite automatizar scraping cada hora.

## Configuración

### Paso 1

Editar:

```bat
SET PROYECTO=C:\Users\TU_USUARIO\bolivia_noticias
```

---

### Paso 2

Abrir:

```txt
Task Scheduler
```

o:

```txt
Win + R → taskschd.msc
```

---

### Paso 3

Crear tarea

- Create Basic Task
- Trigger → Daily
- Action → Start a Program
- Seleccionar `ejecutar_pipeline.bat`

---

### Paso 4

Configurar repetición

- Repeat task every → 1 hour
- Duration → Indefinitely

---

# Librerías principales

| Librería | Función |
|---|---|
| requests | Peticiones HTTP |
| beautifulsoup4 | Parseo HTML |
| fake-useragent | Rotación User-Agent |
| pandas | Manipulación de datos |
| plotly | Gráficos interactivos |
| streamlit | Dashboard |
| chromadb | Base vectorial |
| sentence-transformers | Embeddings |
| scikit-learn | TF-IDF + similitud |
| google-generativeai | Gemini API |
| edge-tts | Voz IA |
| python-dotenv | Variables de entorno |

---

# Scraping y anti-bloqueo

El scraper implementa:

- Rotación de User-Agents
- Delays aleatorios
- Headers HTTP realistas
- Requests persistentes
- Manejo de errores

---

# Funcionalidades NLP

## Implementadas

- Vectorización TF-IDF
- Embeddings semánticos
- Similitud coseno
- Recuperación contextual
- RAG
- Clasificación temática

---

# Tópicos automáticos

El sistema clasifica noticias automáticamente:

- Política
- Economía
- Salud
- Educación
- Deportes
- Seguridad
- Bloqueos y rutas
- General

---

# Ejemplo de ejecución

## Pipeline

```bash
python main.py pipeline
```

## Dashboard

```bash
streamlit run app.py
```

---

# Posibles mejoras futuras

- Docker
- PostgreSQL
- Redis
- Modelos LLM locales
- Speech-to-text
- Mapas interactivos
- Clasificación automática avanzada
- Deploy cloud
- Kubernetes
- Fine-tuning

---

# Autor

Proyecto académico desarrollado para la materia de:

**Minería de Datos / NLP / Inteligencia Artificial**

Universidad Mayor de San Andrés — UMSA

---

# Licencia

Uso académico y educativo.