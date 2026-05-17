# Bolivia Noticias — Proyecto de Minería de Datos

Sistema de monitoreo de noticias, bloqueos de carreteras y fact-checking para Bolivia,
construido con Python, SQLite, ChromaDB y la API de Gemini.

**Fuentes:** Los Tiempos · Red Uno  
**Materia:** Minería de Datos

---

## Estructura del proyecto

```
bolivia_noticias/
│
├── database.py              # Gestión de SQLite (noticias + historial)
├── scraper.py               # Crawler y parser de Los Tiempos y Red Uno
├── chatbot.py               # Chatbot RAG con Gemini y ChromaDB
├── main.py                  # Orquestador + dashboard Flask
│
├── templates/
│   ├── index.html           # Dashboard principal
│   ├── chatbot.html         # Interfaz del chatbot
│   └── historial.html       # Historial de ediciones
│
├── requirements.txt         # Dependencias de Python
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Archivos excluidos de Git
└── ejecutar_pipeline.bat    # Script de automatización para Windows
```

---

## Instalación paso a paso (Windows 11)

### 1. Clonar o descargar el proyecto

```bash
git clone https://github.com/tu-usuario/bolivia-noticias.git
cd bolivia-noticias
```

O simplemente descarga los archivos y colócalos en una carpeta.

### 2. Crear un entorno virtual (recomendado)

```bash
python -m venv venv
venv\Scripts\activate
```

Verás `(venv)` al inicio del prompt — eso confirma que está activo.

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

> **Nota:** La primera vez tarda varios minutos porque descarga el modelo
> de embeddings `paraphrase-multilingual-MiniLM-L12-v2` (~120 MB).

### 4. Configurar la API Key de Gemini

**Cómo obtener tu API Key gratuita:**

1. Ve a [https://aistudio.google.com/](https://aistudio.google.com/)
2. Inicia sesión con tu cuenta de Google.
3. Haz clic en **"Get API Key"** → **"Create API key in new project"**.
4. Copia la clave generada.

**Configurar el archivo `.env`:**

```bash
copy .env.example .env
```

Abre el archivo `.env` con cualquier editor de texto y reemplaza:
```
GEMINI_API_KEY="pega_tu_api_key_aqui"
```

---

## Uso

### Ejecutar el pipeline completo + dashboard

```bash
python main.py todo
```

Abre tu navegador en [http://localhost:5000](http://localhost:5000)

### Solo scraping (sin dashboard)

```bash
python main.py pipeline
```

### Solo el dashboard (con datos ya existentes)

```bash
python main.py dashboard
```

### Probar cada módulo individualmente

```bash
# Probar la base de datos
python database.py

# Probar el scraper (tarda varios minutos por los delays)
python scraper.py

# Probar el chatbot en modo consola
python chatbot.py
```

---

## Automatización con el Programador de Tareas de Windows

Para que el scraper se ejecute automáticamente cada hora:

**Paso 1:** Edita el archivo `ejecutar_pipeline.bat` y actualiza la ruta del proyecto:
```bat
SET PROYECTO=C:\Users\TuUsuario\bolivia_noticias
```

**Paso 2:** Abre el Programador de Tareas de Windows:
- Presiona `Win + R` → escribe `taskschd.msc` → Enter

**Paso 3:** Crea una nueva tarea básica:
1. Panel derecho → **"Crear tarea básica..."**
2. Nombre: `Bolivia Noticias Pipeline`
3. Desencadenador: **Diariamente** (luego se ajusta)
4. Acción: **Iniciar un programa**
5. Programa: navega hasta `ejecutar_pipeline.bat`
6. Finalizar.

**Paso 4:** Ajustar a cada hora:
1. Doble clic en la tarea creada → pestaña **"Desencadenadores"**
2. Editar el desencadenador → marcar **"Repetir cada: 1 hora"**
3. Duración: **Indefinidamente**
4. Aceptar.

---

## Cómo funciona el pipeline RAG

```
Portales web
    │
    ▼
scraper.py  ←── Extrae título + cuerpo limpio + fecha
    │
    ▼
database.py ←── Guarda en SQLite (detecta cambios, guarda historial)
    │
    ▼
chatbot.py  ←── Convierte noticias en vectores → ChromaDB
    │              Busca fragmentos relevantes → Gemini API
    ▼
Respuesta basada SOLO en noticias reales (sin alucinaciones)
```

---

## Módulos: descripción técnica

| Módulo | Función principal | Tecnologías |
|--------|------------------|-------------|
| `database.py` | Almacenamiento y versionado | SQLite + hashlib |
| `scraper.py` | Extracción de noticias | requests + BeautifulSoup + fake-useragent |
| `chatbot.py` | RAG + consultas al LLM | ChromaDB + sentence-transformers + Gemini |
| `main.py` | Orquestación + API web | Flask |

---

## Solución de problemas comunes

**Error: `ModuleNotFoundError`**
```bash
# Asegúrate de tener el entorno virtual activo
venv\Scripts\activate
pip install -r requirements.txt
```

**Error: `GEMINI_API_KEY not found`**
- Verifica que el archivo `.env` existe (no `.env.example`).
- Verifica que la clave no tiene espacios extra.

**El scraper no extrae noticias**
- Algunos días los portales cambian su estructura HTML.
- Prueba acceder manualmente a `https://www.lostiempos.com/actualidad` en el navegador.
- Revisa el archivo `bolivia_noticias.log` para ver el detalle del error.

**ChromaDB tarda mucho la primera vez**
- Normal: está descargando el modelo de embeddings (~120 MB).
- Las ejecuciones siguientes son instantáneas porque usa la caché local.
