import os
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Carga las variables de entorno desde el archivo .env en la raíz del proyecto
load_dotenv(Path(__file__).parents[2] / ".env")

# Lee la clave de NewsAPI desde el entorno
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# URL base de la API de NewsAPI
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Lista de ETFs sobre los que buscar noticias
ETFS = [
    "IWDA.AS", "VUSA.AS", "CSPX.AS", "EUNA.AS",
    "IEMG",    "QQQ",     "VWCE.DE", "SPPW.DE",
    "IUSN.DE", "ZPRV.DE", "AGGH.MI", "IQQH.DE",
]

# Ruta de salida del CSV con los scores de sentimiento
OUTPUT_PATH = Path(__file__).parents[2] / "data" / "processed" / "sentiment_scores.csv"

# Número máximo de artículos a descargar por ETF
MAX_ARTICULOS = 20


def buscar_noticias(ticker: str, api_key: str, max_resultados: int = MAX_ARTICULOS) -> list[dict]:
    """Consulta NewsAPI y devuelve una lista de artículos para el ticker dado."""

    # Elimina el sufijo de bolsa (.AS, .DE, etc.) para mejorar los resultados de búsqueda
    termino = ticker.split(".")[0]

    # Parámetros de la petición HTTP
    params = {
        "q":        termino,
        "language": "en",
        "sortBy":   "publishedAt",
        "pageSize": max_resultados,
        "apiKey":   api_key,
    }

    # Realiza la petición GET a la API
    respuesta = requests.get(NEWSAPI_URL, params=params, timeout=10)

    # Lanza excepción si la respuesta no es 200 OK
    respuesta.raise_for_status()

    # Extrae la lista de artículos del JSON devuelto
    return respuesta.json().get("articles", [])


def analizar_sentimiento(texto: str, analizador: SentimentIntensityAnalyzer) -> dict:
    """Aplica VADER al texto y devuelve los cuatro scores (neg, neu, pos, compound)."""

    # polarity_scores devuelve un dict con neg, neu, pos y compound
    return analizador.polarity_scores(texto)


def procesar_etf(ticker: str, analizador: SentimentIntensityAnalyzer) -> dict:
    """Descarga noticias de un ETF, calcula el sentimiento medio y devuelve un resumen."""

    articulos = buscar_noticias(ticker, NEWSAPI_KEY)

    if not articulos:
        # Si no hay noticias, devuelve ceros para no romper el DataFrame
        return {
            "ticker":          ticker,
            "n_articulos":     0,
            "compound_medio":  0.0,
            "positivos_pct":   0.0,
            "negativos_pct":   0.0,
            "neutrales_pct":   0.0,
        }

    scores = []
    for articulo in articulos:
        # Combina título y descripción para un análisis más completo
        titulo      = articulo.get("title")       or ""
        descripcion = articulo.get("description") or ""
        texto       = f"{titulo}. {descripcion}".strip()

        if texto and texto != ".":
            scores.append(analizar_sentimiento(texto, analizador))

    if not scores:
        return {"ticker": ticker, "n_articulos": 0, "compound_medio": 0.0,
                "positivos_pct": 0.0, "negativos_pct": 0.0, "neutrales_pct": 0.0}

    # Convierte la lista de dicts a DataFrame para calcular medias fácilmente
    df_scores = pd.DataFrame(scores)

    # Clasifica cada artículo según el compound: >0.05 positivo, <-0.05 negativo
    n = len(df_scores)
    positivos = (df_scores["compound"] >  0.05).sum()
    negativos = (df_scores["compound"] < -0.05).sum()
    neutrales = n - positivos - negativos

    return {
        "ticker":         ticker,
        "n_articulos":    n,
        "compound_medio": round(df_scores["compound"].mean(), 4),
        "positivos_pct":  round(positivos / n * 100, 1),
        "negativos_pct":  round(negativos / n * 100, 1),
        "neutrales_pct":  round(neutrales / n * 100, 1),
    }


def analizar_todos(tickers: list[str]) -> pd.DataFrame:
    """Itera sobre todos los ETFs, analiza el sentimiento y devuelve un DataFrame."""

    # Instancia el analizador VADER una sola vez (es costoso crearlo repetidamente)
    analizador = SentimentIntensityAnalyzer()

    resultados = []
    for ticker in tickers:
        print(f"  Procesando {ticker}...")
        fila = procesar_etf(ticker, analizador)
        resultados.append(fila)

    # Construye el DataFrame y lo ordena por compound_medio descendente
    df = pd.DataFrame(resultados).set_index("ticker")
    return df.sort_values("compound_medio", ascending=False)


def guardar_csv(df: pd.DataFrame, ruta: Path) -> None:
    """Guarda los scores de sentimiento en data/processed/."""

    # Crea el directorio si no existe
    ruta.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(ruta)
    print(f"\nResultados guardados en: {ruta}")
    print(df.to_string())


if __name__ == "__main__":
    if not NEWSAPI_KEY:
        raise EnvironmentError("No se encontró NEWSAPI_KEY en el archivo .env")

    print("Analizando sentimiento de noticias para 12 ETFs...\n")
    df_sentimiento = analizar_todos(ETFS)
    guardar_csv(df_sentimiento, OUTPUT_PATH)
