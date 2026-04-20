import pandas as pd
import numpy as np
from pathlib import Path

# Tasa libre de riesgo anual aproximada (Euribor ~3.5% en 2024)
TASA_LIBRE_RIESGO = 0.035

# Rutas de entrada y salida
PRECIOS_PATH = Path(__file__).parents[2] / "data" / "raw" / "etf_prices.csv"
METRICAS_PATH = Path(__file__).parents[2] / "data" / "processed" / "etf_metrics.csv"


def calcular_retornos(precios: pd.DataFrame) -> pd.DataFrame:
    """Calcula los retornos diarios porcentuales a partir de los precios de cierre."""

    # pct_change() calcula la variación porcentual entre días consecutivos
    retornos = precios.pct_change()

    # Elimina la primera fila que siempre es NaN tras pct_change
    return retornos.dropna(how="all")


def calcular_volatilidad(retornos: pd.DataFrame) -> pd.Series:
    """Volatilidad anualizada: desviación estándar diaria * sqrt(252 días hábiles)."""

    # std() calcula la desviación estándar de los retornos diarios
    vol_diaria = retornos.std()

    # Anualiza multiplicando por la raíz cuadrada de los días hábiles del año
    return (vol_diaria * np.sqrt(252)).rename("volatilidad_anual")


def calcular_sharpe(retornos: pd.DataFrame, tasa_rf: float = TASA_LIBRE_RIESGO) -> pd.Series:
    """Sharpe Ratio anualizado: (retorno medio anual - tasa libre de riesgo) / volatilidad anual."""

    # Retorno medio diario de cada ETF
    retorno_medio_diario = retornos.mean()

    # Convierte el retorno diario medio a escala anual
    retorno_anual = retorno_medio_diario * 252

    # Volatilidad anualizada reutilizando la función anterior
    volatilidad = calcular_volatilidad(retornos)

    # Fórmula estándar del Sharpe Ratio
    sharpe = (retorno_anual - tasa_rf) / volatilidad

    return sharpe.rename("sharpe_ratio")


def calcular_max_drawdown(precios: pd.DataFrame) -> pd.Series:
    """Maximum Drawdown: caída máxima desde un pico histórico hasta el valle siguiente."""

    resultados = {}

    for ticker in precios.columns:
        # Serie de precios del ETF sin NaN
        serie = precios[ticker].dropna()

        # Máximo acumulado hasta cada fecha (pico histórico en cada punto)
        pico_acumulado = serie.cummax()

        # Drawdown en cada día: cuánto ha caído respecto al pico anterior
        drawdown = (serie - pico_acumulado) / pico_acumulado

        # El maximum drawdown es el valor más negativo de toda la serie
        resultados[ticker] = drawdown.min()

    return pd.Series(resultados, name="max_drawdown")


def calcular_retorno_total(precios: pd.DataFrame) -> pd.Series:
    """Retorno total del periodo: variación porcentual entre el primer y el último precio."""

    # Primer precio válido de cada ETF
    primer_precio = precios.bfill().iloc[0]

    # Último precio válido de cada ETF
    ultimo_precio = precios.ffill().iloc[-1]

    # Variación porcentual total acumulada
    retorno = (ultimo_precio - primer_precio) / primer_precio

    return retorno.rename("retorno_total")


def calcular_metricas(precios: pd.DataFrame) -> pd.DataFrame:
    """Combina todas las métricas en un único DataFrame por ETF."""

    retornos = calcular_retornos(precios)

    # Construye el DataFrame uniendo cada métrica como columna
    metricas = pd.concat([
        calcular_volatilidad(retornos),
        calcular_sharpe(retornos),
        calcular_max_drawdown(precios),
        calcular_retorno_total(precios),
    ], axis=1)

    # Ordena por Sharpe Ratio descendente (mejor primero)
    return metricas.sort_values("sharpe_ratio", ascending=False)


def guardar_metricas(df: pd.DataFrame, ruta: Path) -> None:
    """Guarda el DataFrame de métricas en data/processed/."""

    # Crea el directorio si no existe
    ruta.parent.mkdir(parents=True, exist_ok=True)

    # Redondea a 4 decimales para legibilidad
    df.round(4).to_csv(ruta)

    print(f"Metricas guardadas en: {ruta}")
    print(df.round(4).to_string())


if __name__ == "__main__":
    # Carga los precios descargados previamente por screener.py
    precios = pd.read_csv(PRECIOS_PATH, index_col=0, parse_dates=True)

    print("Calculando metricas de riesgo...\n")
    metricas = calcular_metricas(precios)
    guardar_metricas(metricas, METRICAS_PATH)
