"""
app.py

Aplicación principal Bolivia Noticias — Streamlit.

Pestañas:
  1. Dashboard   — métricas, gráficos, timeline
  2. Noticias    — tarjetas filtradas por fuente / tópico / fecha / texto
  3. Chatbot Gemini — RAG con Gemini (chatbot.py)
  4. Chatbot Local  — TF-IDF sin API (chatbot_local.py)
  5. Historial   — versiones anteriores de noticias

Ejecutar:
  streamlit run app.py
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, date, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Añadir el directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

from database import DatabaseManager

# ─────────────────────────────────────────────────────────
# Configuración de página — DEBE ir primero
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bolivia Noticias",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# CSS personalizado
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

  /* Variables */
  :root {
    --azul:    #1a3fbf;
    --verde:   #065f46;
    --rojo:    #b91c1c;
    --gris:    #f5f500;
    --muted:   #6b7280;
    --borde:   #e5e5e0;
    --card:    #ffffff;
  }

  /* Ocultar elementos de Streamlit */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

  /* Tipografía */
  h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.02em !important; }

  /* Header principal */
  .site-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 0 18px 0; border-bottom: 2px solid var(--borde); margin-bottom: 24px;
  }
  .site-brand {
    font-family: 'Syne', sans-serif; font-size: 1.6rem; font-weight: 800;
    color: #0f0f0e; letter-spacing: -0.03em; line-height: 1;
  }
  .site-brand span { color: #dc2626; }
  .site-sub { font-size: 0.8rem; color: var(--muted); margin-top: 3px; }

  /* KPIs */
  .kpi-wrap {
    background: #0f0f0e; border-radius: 12px; padding: 18px 20px;
    border-left: 4px solid;
  }
  .kpi-val {
    font-family: 'Syne', sans-serif; font-size: 2.1rem; font-weight: 800;
    color: #f1f5f9; letter-spacing: -0.04em; line-height: 1;
  }
  .kpi-lbl {
    font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;
    letter-spacing: 0.06em; margin-top: 4px;
  }

  /* Tarjeta noticia */
  .noticia-card {
    background: var(--card); border: 1px solid var(--borde); border-radius: 12px;
    padding: 16px 18px; margin-bottom: 12px;
    border-left: 4px solid var(--azul);
    transition: box-shadow 0.15s;
  }
  .noticia-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.07); }
  .noticia-titulo {
    font-family: 'Syne', sans-serif; font-size: 0.97rem; font-weight: 700;
    color: #0f0f0e; margin-bottom: 5px; letter-spacing: -0.01em;
  }
  .noticia-meta { font-size: 0.76rem; color: var(--muted); margin-bottom: 6px; }
  .noticia-extracto { font-size: 0.84rem; color: #374151; line-height: 1.55; }
  .badge {
    display: inline-block; padding: 2px 9px; border-radius: 99px;
    font-size: 0.7rem; font-weight: 600; margin-right: 4px;
  }
  .badge-lt   { background: #dbeafe; color: #1e40af; }
  .badge-deber{ background: #fef3c7; color: #92400e; }
  .badge-gral { background: #f3f4f6; color: #374151; }

  /* Tarjeta resultado chatbot */
  .resultado-card {
    background: var(--card); border: 1px solid var(--borde); border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px;
  }
  .sim-bar-bg { background: #f3f4f6; border-radius: 3px; height: 5px; margin: 6px 0 4px; }
  .sim-bar    { height: 5px; border-radius: 3px; background: var(--azul); }

  /* Chat bubbles */
  .burbuja-usuario {
    background: var(--azul); color: white; border-radius: 12px 12px 4px 12px;
    padding: 10px 14px; margin: 6px 0; font-size: 0.9rem; max-width: 80%;
    margin-left: auto; display: block; width: fit-content;
  }
  .burbuja-bot {
    background: var(--card); border: 1px solid var(--borde);
    border-radius: 12px 12px 12px 4px; padding: 10px 14px;
    margin: 6px 0; font-size: 0.9rem; max-width: 80%; white-space: pre-wrap;
  }

  /* Sección header */
  .sec-hdr {
    font-family: 'Syne', sans-serif; font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.09em; color: var(--muted);
    border-bottom: 1px solid var(--borde); padding-bottom: 6px; margin-bottom: 14px;
  }

  /* Sidebar */
  [data-testid="stSidebar"] { background: #0f0f0e !important; }
  [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  [data-testid="stSidebar"] .stSelectbox > div > div { background: #1e293b !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# Tópicos
# ─────────────────────────────────────────────────────────
TOPICOS = {
    "🚧 Bloqueos y rutas": [
        "bloqueo","bloqueos","desbloqueo","ruta","carretera","transitabilidad",
        "sindicato","marcha","protesta","corte","paro","cierre vía",
    ],
    "🏛️ Política": [
        "gobierno","presidente","ministro","diputado","asamblea","elecciones",
        "parlamento","senado","decreto","ley","partido","candidato","arce","morales",
    ],
    "💰 Economía": [
        "economía","dólar","combustible","ypfb","precio","exportación","importación",
        "gestora","banco","deuda","inflación","presupuesto","empresa","inversión",
    ],
    "⚖️ Seguridad": [
        "policía","aprehendido","detenido","delito","atraco","violencia",
        "crimen","narcotráfico","droga","homicidio","fiscal","tribunal",
    ],
    "🏥 Salud": [
        "salud","hospital","paciente","médico","enfermedad","vacuna",
        "epidemia","dengue","tratamiento","sanitario",
    ],
    "📚 Educación": [
        "educación","maestro","universidad","colegio","estudiantes",
        "clases","bachiller","magisterio","huelga docente",
    ],
    "⚽ Deportes": [
        "fútbol","bolívar","oriente","blooming","deporte","copa",
        "liga","gol","torneo","selección","atleta",
    ],
}
COLORES_TOPICOS = {
    "🚧 Bloqueos y rutas": "#dc2626",
    "🏛️ Política":         "#1a3fbf",
    "💰 Economía":         "#d97706",
    "⚖️ Seguridad":        "#7c3aed",
    "🏥 Salud":            "#059669",
    "📚 Educación":        "#0891b2",
    "⚽ Deportes":         "#16a34a",
    "📰 General":          "#6b7280",
}
COLORES_FUENTE = {
    "Los Tiempos": "#1a3fbf",
    "EL DEBER":    "#d97706",
}

def asignar_topico(titulo: str, texto: str) -> str:
    contenido = (titulo + " " + texto).lower()
    for topico, palabras in TOPICOS.items():
        if any(p in contenido for p in palabras):
            return topico
    return "📰 General"

def badge_fuente(fuente: str) -> str:
    cls = "badge-lt" if "Tiempos" in fuente else "badge-deber"
    return f'<span class="badge {cls}">{fuente}</span>'

def badge_topico(topico: str) -> str:
    color = COLORES_TOPICOS.get(topico, "#6b7280")
    return f'<span class="badge" style="background:{color}22;color:{color}">{topico}</span>'

# ─────────────────────────────────────────────────────────
# Carga de datos con caché
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cargar_noticias() -> pd.DataFrame:
    db = DatabaseManager()
    noticias = db.obtener_todas()
    if not noticias:
        return pd.DataFrame()
    df = pd.DataFrame(noticias)
    df["fecha_final"] = pd.to_datetime(
        df["fecha_pub"].fillna(df["fecha_scrape"]), errors="coerce"
    )
    df["fecha_str"] = df["fecha_final"].dt.strftime("%Y-%m-%d").fillna("Sin fecha")
    df["topico"]    = df.apply(lambda r: asignar_topico(
        r.get("titulo",""), r.get("texto","")), axis=1)
    df["titulo"]    = df["titulo"].fillna("Sin título")
    df["texto"]     = df["texto"].fillna("")
    df["fuente"]    = df["fuente"].fillna("Desconocido")
    df["url"]       = df["url"].fillna("#")
    return df.sort_values("fecha_final", ascending=False, na_position="last")

@st.cache_data(ttl=300, show_spinner=False)
def cargar_historial_urls() -> list:
    db = DatabaseManager()
    try:
        noticias = db.obtener_todas()
        return [n["url"] for n in noticias if n.get("url")]
    except Exception:
        return []

# ─────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────
st.markdown("""
<div class="site-header">
  <div>
    <div class="site-brand">📡 Bolivia<span>Noticias</span></div>
    <div class="site-sub">Monitor de medios bolivianos · Los Tiempos &amp; El Deber</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# Sidebar — filtros globales
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Filtros")

    df_all = cargar_noticias()

    fuentes_disp = ["Todas"] + sorted(df_all["fuente"].unique().tolist()) if not df_all.empty else ["Todas"]
    sel_fuente = st.selectbox("📰 Fuente", fuentes_disp)

    topicos_disp = ["Todos"] + sorted(df_all["topico"].unique().tolist()) if not df_all.empty else ["Todos"]
    sel_topico = st.selectbox("🏷️ Tópico", topicos_disp)

    if not df_all.empty and df_all["fecha_final"].notna().any():
        f_min = df_all["fecha_final"].min().date()
        f_max = df_all["fecha_final"].max().date()
        fecha_inicio_default = max(f_min, f_max - timedelta(days=7))

        rango_fechas = st.date_input(
            "📅 Rango de fechas",
            value=(fecha_inicio_default, f_max),
            min_value=f_min,
            max_value=f_max,
        )
    else:
        rango_fechas = None

    busqueda = st.text_input("🔍 Buscar texto", placeholder="Bloqueos, economía...")

    max_noticias = st.slider("Máx. noticias a mostrar", 10, 200, 50, step=10)

    st.markdown("---")
    if st.button("▶ Ejecutar scraping ahora", use_container_width=True):
        with st.spinner("Scrapeando noticias… (puede tardar varios minutos)"):
            try:
                from scraper import ejecutar_scraping
                db = DatabaseManager()
                resumen = ejecutar_scraping(db)
                st.success(
                    f"✅ {resumen.get('nuevas',0)} nuevas · "
                    f"{resumen.get('actualizadas',0)} actualizadas · "
                    f"{resumen.get('errores',0)} errores"
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("### Sobre el proyecto")
    st.markdown("""
    - 🗞️ **Los Tiempos** · **El Deber**
    - 🔄 Scraping automático cada hora
    - 🤖 Chatbot Gemini RAG
    - 🧠 Chatbot local TF-IDF
    - 📦 SQLite + ChromaDB
    """)

# ─────────────────────────────────────────────────────────
# Aplicar filtros
# ─────────────────────────────────────────────────────────
def filtrar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if sel_fuente != "Todas":
        out = out[out["fuente"] == sel_fuente]
    if sel_topico != "Todos":
        out = out[out["topico"] == sel_topico]
    if rango_fechas and len(rango_fechas) == 2:
        f0 = pd.Timestamp(rango_fechas[0])
        f1 = pd.Timestamp(rango_fechas[1]) + pd.Timedelta(days=1)
        out = out[(out["fecha_final"] >= f0) | out["fecha_final"].isna()]
        out = out[(out["fecha_final"] <= f1) | out["fecha_final"].isna()]
    if busqueda.strip():
        q = busqueda.strip().lower()
        mask = (
            out["titulo"].str.lower().str.contains(q, na=False) |
            out["texto"].str.lower().str.contains(q, na=False)
        )
        out = out[mask]
    return out.head(max_noticias)

df_filtrado = filtrar(df_all)

# ─────────────────────────────────────────────────────────
# PESTAÑAS
# ─────────────────────────────────────────────────────────
tab_dash, tab_noticias, tab_gemini, tab_local, tab_historial = st.tabs([
    "📊 Dashboard",
    "📰 Noticias",
    "🤖 Chatbot Gemini",
    "🧠 Chatbot Local",
    "📋 Historial",
])

# ══════════════════════════════════════════════════════════
# TAB 1: DASHBOARD
# ══════════════════════════════════════════════════════════
with tab_dash:

    # KPIs
    if df_all.empty:
        st.warning("No hay noticias en la base de datos. Ejecuta el scraping desde la barra lateral.")
    else:
        ultima_fecha = df_all["fecha_final"].max()
        ultima_str   = ultima_fecha.strftime("%d/%m/%Y %H:%M") if pd.notna(ultima_fecha) else "N/D"

        k1, k2, k3, k4, k5 = st.columns(5)
        kpis = [
            (len(df_all),                                "Noticias totales",    "#1a3fbf"),
            (len(df_filtrado),                           "Con filtros activos", "#059669"),
            (df_all["fuente"].nunique(),                 "Fuentes activas",     "#d97706"),
            (df_all["topico"].nunique(),                 "Tópicos detectados",  "#7c3aed"),
            (ultima_str,                                 "Última actualización","#0f0f0e"),
        ]
        for col, (val, lbl, color) in zip([k1,k2,k3,k4,k5], kpis):
            with col:
                st.markdown(f"""
                <div class="kpi-wrap" style="border-left-color:{color}">
                  <div class="kpi-val">{val}</div>
                  <div class="kpi-lbl">{lbl}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Gráficos fila 1 ──
        gc1, gc2 = st.columns(2)

        with gc1:
            st.markdown('<div class="sec-hdr">Noticias por fuente</div>', unsafe_allow_html=True)
            cnt_fuente = df_all["fuente"].value_counts().reset_index()
            cnt_fuente.columns = ["Fuente", "Total"]
            fig_fuente = px.bar(
                cnt_fuente, x="Total", y="Fuente", orientation="h",
                color="Fuente",
                color_discrete_map=COLORES_FUENTE,
                text="Total",
            )
            fig_fuente.update_layout(
                showlegend=False, plot_bgcolor="white",
                paper_bgcolor="white", height=220,
                margin=dict(t=0, b=0, l=0, r=10),
                yaxis_title="", xaxis_title="",
                font=dict(family="DM Sans, sans-serif", size=12),
            )
            fig_fuente.update_traces(textposition="outside")
            st.plotly_chart(fig_fuente, use_container_width=True)

        with gc2:
            st.markdown('<div class="sec-hdr">Noticias por tópico</div>', unsafe_allow_html=True)
            cnt_topico = df_all["topico"].value_counts().reset_index()
            cnt_topico.columns = ["Tópico", "Total"]
            fig_topico = px.bar(
                cnt_topico, x="Total", y="Tópico", orientation="h",
                color="Tópico",
                color_discrete_map=COLORES_TOPICOS,
                text="Total",
            )
            fig_topico.update_layout(
                showlegend=False, plot_bgcolor="white",
                paper_bgcolor="white", height=340,
                margin=dict(t=0, b=0, l=0, r=10),
                yaxis_title="", xaxis_title="",
                font=dict(family="DM Sans, sans-serif", size=11),
            )
            fig_topico.update_traces(textposition="outside")
            st.plotly_chart(fig_topico, use_container_width=True)

        # ── Timeline ──
        st.markdown('<div class="sec-hdr">Noticias por fecha</div>', unsafe_allow_html=True)
        df_tiempo = (
            df_all[df_all["fecha_final"].notna()]
            .groupby([df_all["fecha_final"].dt.date, "fuente"])
            .size()
            .reset_index(name="Total")
        )
        df_tiempo.columns = ["Fecha", "Fuente", "Total"]

        if not df_tiempo.empty:
            fig_time = px.area(
                df_tiempo, x="Fecha", y="Total", color="Fuente",
                color_discrete_map=COLORES_FUENTE,
                line_shape="spline",
            )
            fig_time.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                height=260, margin=dict(t=10, b=0, l=0, r=0),
                legend=dict(orientation="h", y=-0.2),
                xaxis_title="", yaxis_title="Noticias/día",
                font=dict(family="DM Sans, sans-serif", size=11),
            )
            fig_time.update_traces(fill="tozeroy", opacity=0.7)
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.info("Sin datos de fecha para el timeline.")

        # ── Donut tópicos ──
        st.markdown('<div class="sec-hdr">Distribución de tópicos</div>', unsafe_allow_html=True)
        fig_donut = px.pie(
            cnt_topico, values="Total", names="Tópico",
            color="Tópico", color_discrete_map=COLORES_TOPICOS,
            hole=0.45,
        )
        fig_donut.update_layout(
            height=300, margin=dict(t=0, b=0, l=0, r=0),
            legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
            font=dict(family="DM Sans, sans-serif"),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

# ══════════════════════════════════════════════════════════
# TAB 2: NOTICIAS
# ══════════════════════════════════════════════════════════
with tab_noticias:
    st.markdown(
        f'<div class="sec-hdr">{len(df_filtrado)} noticias · '
        f'{"todos los filtros" if sel_fuente=="Todas" and sel_topico=="Todos" else "filtros aplicados"}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if df_filtrado.empty:
        st.info("No hay noticias con los filtros seleccionados.")
    else:
        # Agrupar por fecha
        fechas_unicas = df_filtrado["fecha_str"].unique()
        for fecha in fechas_unicas:
            grupo = df_filtrado[df_filtrado["fecha_str"] == fecha]
            st.markdown(
                f"<div style='font-family:Syne,sans-serif;font-size:0.78rem;"
                f"font-weight:700;text-transform:uppercase;letter-spacing:.08em;"
                f"color:#6b7280;border-bottom:1px solid #e5e5e0;padding-bottom:5px;"
                f"margin:16px 0 10px;'>{fecha} · {len(grupo)} noticias</div>",
                unsafe_allow_html=True,
            )
            for _, n in grupo.iterrows():
                color_borde = COLORES_FUENTE.get(n["fuente"], "#6b7280")
                extracto = n["texto"][:220] + "…" if len(n["texto"]) > 220 else n["texto"]
                with st.container():
                    st.markdown(f"""
                    <div class="noticia-card" style="border-left-color:{color_borde}">
                      <div class="noticia-titulo">{n['titulo']}</div>
                      <div class="noticia-meta">
                        {badge_fuente(n['fuente'])}
                        {badge_topico(n['topico'])}
                        &nbsp;{n['fecha_str']}
                      </div>
                      <div class="noticia-extracto">{extracto}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    col_link, col_exp = st.columns([1, 5])
                    with col_link:
                        st.link_button("Leer →", n["url"])
                    with col_exp:
                        with st.expander("Ver texto completo"):
                            st.write(n["texto"])

# ══════════════════════════════════════════════════════════
# TAB 3: CHATBOT GEMINI
# ══════════════════════════════════════════════════════════
with tab_gemini:
    st.markdown('<div class="sec-hdr">Chatbot Gemini — RAG con noticias indexadas</div>',
                unsafe_allow_html=True)

    # Intentar cargar Gemini
    gemini_ok = False
    bot_gemini = None
    try:
        from chatbot import ChatbotRAG
        bot_gemini = ChatbotRAG()
        gemini_ok  = True
    except ValueError as e:
        st.warning(f"⚠️ {e}")
    except Exception as e:
        err_str = str(e).lower()
        if "429" in err_str or "quota" in err_str or "resource" in err_str:
            st.error(
                "🚫 **Cuota de Gemini agotada temporalmente.**\n\n"
                "Intenta más tarde o usa el **Chatbot Local** (pestaña 🧠)."
            )
        else:
            st.warning(f"⚠️ No se pudo inicializar Gemini: {e}")

    if gemini_ok and bot_gemini:
        # Indexar si es necesario
        with st.spinner("Indexando noticias en ChromaDB…"):
            try:
                n_idx = bot_gemini.indexar_noticias()
                if n_idx > 0:
                    st.success(f"✅ {n_idx} noticias nuevas indexadas.")
            except Exception as e:
                st.warning(f"Error al indexar: {e}")

        modo = st.radio(
            "Modo de consulta",
            ["📰 General", "🗺️ Ruta y bloqueos", "🔍 Fact-checking"],
            horizontal=True,
        )
        modos_map = {
            "📰 General":           "general",
            "🗺️ Ruta y bloqueos":   "ruta",
            "🔍 Fact-checking":     "fact_checking",
        }
        descripciones = {
            "📰 General":         "Haz cualquier pregunta sobre las noticias recientes de Bolivia.",
            "🗺️ Ruta y bloqueos": "Pregunta si hay paso libre o bloqueos entre ciudades.",
            "🔍 Fact-checking":   "Pega un texto y verificaré si coincide con lo reportado.",
        }
        st.caption(descripciones[modo])

        # Historial de chat en session_state
        if "historial_gemini" not in st.session_state:
            st.session_state.historial_gemini = []

        # Mostrar historial
        for msg in st.session_state.historial_gemini:
            if msg["rol"] == "usuario":
                st.markdown(
                    f'<div class="burbuja-usuario">{msg["texto"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="burbuja-bot">{msg["texto"]}</div>',
                    unsafe_allow_html=True,
                )

                if msg.get("audio"):
                    import base64

                    audio_base64 = base64.b64encode(msg["audio"]).decode()

                    audio_html = f"""
                    <audio autoplay controls>
                        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                    </audio>
                    """

                    st.markdown(audio_html, unsafe_allow_html=True)

                if msg.get("audio_error"):
                    st.warning(msg["audio_error"])

        # Input
        with st.form("form_gemini", clear_on_submit=True):
            pregunta_g = st.text_area(
                "Tu pregunta", height=80,
                placeholder="¿Hay bloqueos en la ruta La Paz–Cochabamba?",
                label_visibility="collapsed",
            )
            enviado_g = st.form_submit_button("Enviar →", use_container_width=True)

        if enviado_g and pregunta_g.strip():

            # Guardar mensaje usuario
            st.session_state.historial_gemini.append(
                {"rol": "usuario", "texto": pregunta_g}
            )
            st.session_state.pop("audio_gemini", None)
            st.session_state.pop("audio_gemini_error", None)

            respuesta = ""

            # =========================
            # CONSULTAR GEMINI
            # =========================
            with st.spinner("Consultando Gemini…"):

                try:
                    respuesta = bot_gemini.consultar(
                        pregunta_g.strip(),
                        modo=modos_map[modo]
                    )

                except Exception as e:

                    err = str(e).lower()

                    if "429" in err or "quota" in err:
                        respuesta = (
                            "🚫 La cuota de Gemini se agotó temporalmente.\n\n"
                            "Prueba el Chatbot Local (🧠) que no usa API."
                        )

                    else:
                        respuesta = f"Error: {e}"

            # =========================
            # GUARDAR RESPUESTA
            # =========================
            audio_bytes = None
            audio_error = None

            try:
                from voz_edge import texto_a_voz_edge
                audio_bytes = texto_a_voz_edge(respuesta)
            except Exception as e:
                audio_error = "⚠️ No se pudo generar audio con Edge-TTS."
                print("Error Edge-TTS:", e)

            st.session_state.historial_gemini.append(
                {
                    "rol": "bot",
                    "texto": respuesta,
                    "audio": audio_bytes,
                    "audio_error": audio_error,
                }
            )

            # =========================
            # GENERAR AUDIO
            # =========================
            if "audio_gemini" in st.session_state:
                st.audio(
                    st.session_state.audio_gemini,
                    format="audio/mp3"
                )

            if "audio_gemini_error" in st.session_state:
                st.warning(
                    st.session_state.audio_gemini_error
                )

            st.rerun()

        # =========================
        # AUDIO EDGE-TTS
        # =========================

        if "audio_gemini" in st.session_state:

            st.audio(
                st.session_state.audio_gemini,
                format="audio/mp3"
            )

        if "audio_gemini_error" in st.session_state:

            st.warning(
                st.session_state.audio_gemini_error
            )
        if st.button("🗑 Limpiar conversación", key="limpiar_gemini"):
            st.session_state.historial_gemini = []
            st.rerun()

# ══════════════════════════════════════════════════════════
# TAB 4: CHATBOT LOCAL TF-IDF
# ══════════════════════════════════════════════════════════
with tab_local:
    st.markdown('<div class="sec-hdr">Chatbot Local — TF-IDF sin API externa</div>',
                unsafe_allow_html=True)
    st.caption(
        "Busca noticias similares a tu consulta usando TF-IDF y similitud de coseno. "
        "No inventa información — devuelve noticias reales de la base de datos."
    )

    # Inicializar chatbot local en session_state para no re-vectorizar en cada interacción
    if "bot_local" not in st.session_state:
        from chatbot_local import ChatbotLocal
        bot_local = ChatbotLocal()
        with st.spinner("Vectorizando corpus con TF-IDF…"):
            n_docs = bot_local.cargar_y_vectorizar()
        st.session_state.bot_local   = bot_local
        st.session_state.n_docs_tfidf = n_docs

    bot_local = st.session_state.bot_local

    col_conf1, col_conf2 = st.columns([2, 1])
    with col_conf1:
        st.info(
            f"📦 Corpus: **{st.session_state.n_docs_tfidf}** documentos vectorizados. "
            "Los resultados se basan exclusivamente en las noticias de la BD."
        )
    with col_conf2:
        if st.button("🔄 Re-vectorizar corpus", help="Actualiza el índice con noticias nuevas"):
            with st.spinner("Re-vectorizando…"):
                bot_local.invalidar_cache()
                n = bot_local.cargar_y_vectorizar()
                st.session_state.n_docs_tfidf = n
            st.success(f"✅ {n} documentos indexados.")

    top_k = st.slider("Noticias a devolver", 3, 10, 5)

    # Input
    with st.form("form_local", clear_on_submit=True):
        consulta_l = st.text_input(
            "Consulta",
            placeholder="¿Qué está pasando con los bloqueos? ¿Dólar en Bolivia?",
            label_visibility="collapsed",
        )
        enviado_l = st.form_submit_button("Buscar →", use_container_width=True)

    if enviado_l and consulta_l.strip():
        with st.spinner("Buscando noticias similares…"):
            resultado = bot_local.buscar(consulta_l.strip(), top_k=top_k)

        st.markdown(f"**{resultado['mensaje']}**")
        st.markdown(
            f"Similitud máxima: `{resultado['max_similitud']:.3f}` "
            f"({'alta' if resultado['max_similitud'] > 0.25 else 'media' if resultado['max_similitud'] > 0.08 else 'baja'})"
        )
        st.markdown("---")

        if resultado["tiene_resultados"] and not resultado["resultados"].empty:
            for _, row in resultado["resultados"].iterrows():
                sim = float(row["similitud"])
                sim_pct = min(int(sim * 400), 100)
                relevante = row.get("relevante", False)
                color_sim = "#059669" if sim > 0.25 else "#d97706" if sim > 0.08 else "#6b7280"
                extracto  = row.get("texto","")[:200] + "…"
                fecha_r   = str(row.get("fecha_pub", row.get("fecha_scrape", "")))[:10]
                fuente_r  = row.get("fuente","")
                topico_r  = asignar_topico(row.get("titulo",""), row.get("texto",""))

                st.markdown(f"""
                <div class="resultado-card">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
                    <div style="font-family:'Syne',sans-serif;font-size:.93rem;font-weight:700;
                                color:#0f0f0e;flex:1">{row.get('titulo','')}</div>
                    <span style="font-size:.75rem;font-weight:600;color:{color_sim};
                                 white-space:nowrap">sim: {sim:.3f}</span>
                  </div>
                  <div class="sim-bar-bg">
                    <div class="sim-bar" style="width:{sim_pct}%;background:{color_sim}"></div>
                  </div>
                  <div style="font-size:.75rem;color:#6b7280;margin-bottom:6px">
                    {badge_fuente(fuente_r)} {badge_topico(topico_r)} &nbsp; {fecha_r}
                  </div>
                  <div style="font-size:.83rem;color:#374151;line-height:1.5">{extracto}</div>
                </div>
                """, unsafe_allow_html=True)

                col_a, col_b = st.columns([1, 8])
                with col_a:
                    st.link_button("Leer →", row.get("url","#"))

# ══════════════════════════════════════════════════════════
# TAB 5: HISTORIAL
# ══════════════════════════════════════════════════════════
with tab_historial:
    st.markdown('<div class="sec-hdr">Historial de ediciones de noticias</div>',
                unsafe_allow_html=True)

    if df_all.empty:
        st.info("No hay noticias en la base de datos.")
    else:
        # Selector de noticia
        opciones = df_all[["titulo","url"]].drop_duplicates("url")
        titulos  = opciones["titulo"].tolist()
        sel_titulo = st.selectbox("Selecciona una noticia", titulos)
        sel_url = opciones[opciones["titulo"] == sel_titulo]["url"].values[0]

        st.markdown(
            f"<div style='font-size:.8rem;color:#6b7280;word-break:break-all;"
            f"margin-bottom:12px'>{sel_url}</div>",
            unsafe_allow_html=True,
        )

        # Cargar historial desde DB
        try:
            db = DatabaseManager()
            hist = db.obtener_historial(sel_url)
        except AttributeError:
            # Si obtener_historial no existe, usar una consulta directa
            try:
                import sqlite3
                conn = sqlite3.connect("noticias.db")
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT * FROM historial_noticias WHERE url=? ORDER BY fecha_cambio DESC",
                    (sel_url,)
                )
                hist = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception as e:
                hist = []
                st.warning(f"No se pudo cargar historial: {e}")

        if not hist:
            st.info("Esta noticia no tiene ediciones registradas.")
        else:
            st.success(f"📋 {len(hist)} versión(es) anterior(es) encontrada(s).")
            for version in hist:
                with st.expander(
                    f"📝 Guardado: {str(version.get('fecha_cambio',''))[:19]}",
                    expanded=False,
                ):
                    if version.get("titulo"):
                        st.markdown(f"**Título:** {version['titulo']}")
                    if version.get("texto_anterior"):
                        st.text_area(
                            "Texto anterior",
                            value=version["texto_anterior"],
                            height=150,
                            disabled=True,
                            key=f"hist_{version.get('id', hash(str(version)))}",
                        )
