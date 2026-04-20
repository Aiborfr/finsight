import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

# Importa los módulos del proyecto para regenerar datos si no existen
from src.screener.screener import descargar_precios, guardar_csv, ETFS
from src.screener.metrics  import calcular_metricas, guardar_metricas
from src.sentiment.sentiment import analizar_todos, guardar_csv as guardar_sentimiento

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(page_title="FinSight", page_icon="📊", layout="wide")

# ── Rutas de datos ───────────────────────────────────────────────────────────
ROOT             = Path(__file__).parent
PRECIOS_PATH     = ROOT / "data" / "raw"       / "etf_prices.csv"
METRICAS_PATH    = ROOT / "data" / "processed" / "etf_metrics.csv"
SENTIMIENTO_PATH = ROOT / "data" / "processed" / "sentiment_scores.csv"

# ── Generación automática de datos si no existen los CSV ─────────────────────
if not PRECIOS_PATH.exists() or not METRICAS_PATH.exists():
    with st.spinner("Descargando datos historicos de precios (esto puede tardar ~30s)..."):
        precios_df = descargar_precios(ETFS)
        guardar_csv(precios_df, PRECIOS_PATH)
        metricas_df = calcular_metricas(precios_df)
        guardar_metricas(metricas_df, METRICAS_PATH)

if not SENTIMIENTO_PATH.exists():
    with st.spinner("Analizando sentimiento de noticias..."):
        sentimiento_df = analizar_todos(ETFS)
        guardar_sentimiento(sentimiento_df, SENTIMIENTO_PATH)

# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data
def cargar_precios() -> pd.DataFrame:
    return pd.read_csv(PRECIOS_PATH, index_col=0, parse_dates=True)

@st.cache_data
def cargar_metricas() -> pd.DataFrame:
    return pd.read_csv(METRICAS_PATH, index_col=0)

@st.cache_data
def cargar_sentimiento() -> pd.DataFrame:
    return pd.read_csv(SENTIMIENTO_PATH, index_col=0)

precios     = cargar_precios()
metricas    = cargar_metricas()
sentimiento = cargar_sentimiento()

# ── Helpers ──────────────────────────────────────────────────────────────────
def etiqueta_sentimiento(compound: float) -> str:
    """Convierte el score compound de VADER en una etiqueta legible con emoji."""
    if compound >= 0.05:
        return "Positivo"
    if compound <= -0.05:
        return "Negativo"
    return "Neutral"

def color_sentimiento(compound: float) -> str:
    if compound >= 0.05:
        return "normal"
    if compound <= -0.05:
        return "inverse"
    return "off"

# ── Cabecera ─────────────────────────────────────────────────────────────────
st.title("FinSight — ETF Risk Screener")
st.caption(
    f"Datos: {precios.index[0].date()} a {precios.index[-1].date()} "
    f"· {len(precios)} sesiones · {len(metricas)} ETFs"
)

st.divider()

# ── Sección 1: tabla combinada riesgo + sentimiento ───────────────────────────
st.subheader("Resumen: riesgo y sentimiento")

# Une métricas de riesgo con scores de sentimiento por ticker
combinado = metricas.join(sentimiento[["compound_medio", "n_articulos"]], how="left")
combinado["sentimiento"] = combinado["compound_medio"].fillna(0).map(etiqueta_sentimiento)

tabla = combinado.copy()
tabla["volatilidad_anual"] = tabla["volatilidad_anual"].map("{:.1%}".format)
tabla["sharpe_ratio"]      = tabla["sharpe_ratio"].map("{:.2f}".format)
tabla["max_drawdown"]      = tabla["max_drawdown"].map("{:.1%}".format)
tabla["retorno_total"]     = tabla["retorno_total"].map("{:.1%}".format)
tabla["compound_medio"]    = tabla["compound_medio"].fillna(0).map("{:.3f}".format)
tabla["n_articulos"]       = tabla["n_articulos"].fillna(0).astype(int)

tabla.columns = [
    "Volatilidad", "Sharpe", "Max Drawdown",
    "Retorno (5a)", "Compound", "Noticias", "Sentimiento",
]
tabla.index.name = "ETF"

st.dataframe(tabla, use_container_width=True, height=460)

st.divider()

# ── Sección 2: gráfico de precios normalizados ────────────────────────────────
st.subheader("Evolución de precios (base 100)")

etfs_disponibles   = precios.columns.tolist()
etfs_seleccionados = st.multiselect(
    "Selecciona ETFs",
    options=etfs_disponibles,
    default=etfs_disponibles,
)

if etfs_seleccionados:
    subset     = precios[etfs_seleccionados].copy()
    base       = subset.bfill().iloc[0]
    normalizado = (subset / base) * 100
    st.line_chart(normalizado, height=420)
else:
    st.info("Selecciona al menos un ETF para ver el gráfico.")

st.divider()

# ── Sección 3: detalle por ETF ────────────────────────────────────────────────
st.subheader("Detalle por ETF")

etf_elegido = st.selectbox("ETF", options=etfs_disponibles)

m  = metricas.loc[etf_elegido]
s  = sentimiento.loc[etf_elegido] if etf_elegido in sentimiento.index else None

# Fila 1: métricas de riesgo
col1, col2, col3, col4 = st.columns(4)
col1.metric("Volatilidad anual",  f"{m['volatilidad_anual']:.1%}")
col2.metric("Sharpe Ratio",       f"{m['sharpe_ratio']:.2f}")
col3.metric("Max Drawdown",       f"{m['max_drawdown']:.1%}")
col4.metric("Retorno total (5a)", f"{m['retorno_total']:.1%}")

# Fila 2: métricas de sentimiento
st.markdown("**Sentimiento de noticias recientes**")
col5, col6, col7, col8 = st.columns(4)

if s is not None and s["n_articulos"] > 0:
    col5.metric("Score compound",  f"{s['compound_medio']:.3f}",
                delta=etiqueta_sentimiento(s["compound_medio"]),
                delta_color=color_sentimiento(s["compound_medio"]))
    col6.metric("Noticias analizadas", int(s["n_articulos"]))
    col7.metric("Positivas",  f"{s['positivos_pct']:.0f}%")
    col8.metric("Negativas",  f"{s['negativos_pct']:.0f}%")
else:
    col5.info("Sin datos de noticias para este ETF.")

# Gráfico de drawdown histórico
serie          = precios[etf_elegido].dropna()
pico           = serie.cummax()
drawdown_serie = ((serie - pico) / pico) * 100

st.markdown("**Drawdown histórico (%)**")
st.area_chart(drawdown_serie.rename("Drawdown (%)"), height=280, color="#e63946")

st.divider()

# ── Sección 4: ranking de sentimiento ────────────────────────────────────────
st.subheader("Ranking de sentimiento")

# Filtra solo ETFs con al menos 1 artículo analizado
con_noticias = sentimiento[sentimiento["n_articulos"] > 0].copy()

if con_noticias.empty:
    st.info("No hay datos de sentimiento disponibles.")
else:
    con_noticias = con_noticias.sort_values("compound_medio", ascending=True)
    con_noticias["etiqueta"] = con_noticias["compound_medio"].map(etiqueta_sentimiento)

    st.bar_chart(
        con_noticias["compound_medio"],
        height=320,
        color="#2a9d8f",
    )

    ranking = con_noticias[["compound_medio", "n_articulos", "positivos_pct", "negativos_pct", "etiqueta"]].copy()
    ranking.columns = ["Compound", "Noticias", "Positivas %", "Negativas %", "Sentimiento"]
    ranking.index.name = "ETF"
    st.dataframe(ranking.sort_values("Compound", ascending=False), use_container_width=True)
