import yfinance as yf
import pandas as pd
from pathlib import Path

# Lista de ETFs a analizar
ETFS = [
    "IWDA.AS", "VUSA.AS", "CSPX.AS", "EUNA.AS",
    "IEMG",    "QQQ",     "VWCE.DE", "SPPW.DE",
    "IUSN.DE", "ZPRV.DE", "AGGH.MI", "IQQH.DE",
]

# Ruta de salida relativa a la raíz del proyecto
OUTPUT_PATH = Path(__file__).parents[2] / "data" / "raw" / "etf_prices.csv"


def descargar_precios(tickers: list[str], periodo: str = "5y") -> pd.DataFrame:
    """Descarga el precio de cierre ajustado de cada ETF y devuelve un DataFrame."""

    # Descarga todos los tickers en una sola llamada para mayor eficiencia
    raw = yf.download(tickers, period=periodo, auto_adjust=True, progress=False)

    # Extrae solo la columna 'Close' (precio de cierre ajustado)
    precios = raw["Close"]

    # Elimina filas donde todos los valores son NaN (días sin cotización)
    precios = precios.dropna(how="all")

    return precios


def guardar_csv(df: pd.DataFrame, ruta: Path) -> None:
    """Guarda el DataFrame en disco como CSV."""

    # Crea el directorio de destino si no existe
    ruta.parent.mkdir(parents=True, exist_ok=True)

    # Escribe el CSV con el índice (fecha) incluido
    df.to_csv(ruta)

    print(f"Datos guardados en: {ruta}")
    print(f"Rango de fechas: {df.index[0].date()} a {df.index[-1].date()}")
    print(f"ETFs descargados: {list(df.columns)}")
    print(f"Total de filas: {len(df)}")


if __name__ == "__main__":
    print("Descargando datos históricos (5 años)...")
    precios = descargar_precios(ETFS)
    guardar_csv(precios, OUTPUT_PATH)
