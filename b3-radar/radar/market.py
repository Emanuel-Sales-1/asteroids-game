"""Cotações (Yahoo Finance via yfinance) e indicadores técnicos."""
from __future__ import annotations

import numpy as np
import pandas as pd


def fetch_prices(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    """Preços de fechamento ajustados; colunas = tickers sem o sufixo .SA."""
    import yfinance as yf

    symbols = [t if t.startswith("^") else f"{t}.SA" for t in tickers]
    data = yf.download(symbols, period=period, interval="1d", auto_adjust=True,
                       progress=False, threads=True, group_by="column")
    if data is None or data.empty:
        return pd.DataFrame()
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]]
    if not isinstance(data.columns, pd.MultiIndex):
        close.columns = symbols[:1]
    close.columns = [c.replace(".SA", "") for c in close.columns]
    return close.dropna(how="all").ffill()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def technical_frame(close: pd.Series) -> pd.DataFrame:
    """Indicadores por data para uma série de preços."""
    df = pd.DataFrame({"close": close})
    ret = close.pct_change()
    df["ret_5d"] = close.pct_change(5)
    df["ret_20d"] = close.pct_change(20)
    df["ma20"] = close.rolling(20).mean()
    df["ma50"] = close.rolling(50).mean()
    df["rsi"] = rsi(close)
    df["vol_20d"] = ret.rolling(20).std()
    # Volatilidade robusta: desvio absoluto mediano (x1,4826), pouco afetado por um único dia extremo.
    mad = ret.rolling(20).apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True) * 1.4826
    df["vol_robust"] = mad.fillna(df["vol_20d"])
    df["max_jump_20d"] = ret.abs().rolling(20).max()
    # Score técnico: tendência + momento, com reversão em extremos de RSI.
    trend = np.tanh(((df["ma20"] / df["ma50"]) - 1) * 25)
    mom = np.tanh(df["ret_20d"] / (df["vol_robust"] * np.sqrt(20) + 1e-9) * 0.6)
    short = np.tanh(df["ret_5d"] / (df["vol_robust"] * np.sqrt(5) + 1e-9) * 0.4)
    rsi_adj = np.where(df["rsi"] > 75, -0.4, np.where(df["rsi"] < 25, 0.4, 0.0))
    df["tech_score"] = np.clip(0.4 * trend + 0.35 * mom + 0.25 * short + rsi_adj, -1, 1)
    return df


def backtest_technical(close: pd.Series, horizon: int = 5, threshold: float = 0.2) -> dict:
    """Taxa de acerto histórica do sinal técnico (sem notícias, que não têm histórico)."""
    df = technical_frame(close)
    df["fwd"] = close.shift(-horizon) / close - 1
    df = df.dropna(subset=["tech_score", "fwd"])
    sig = df[df["tech_score"].abs() >= threshold]
    if len(sig) < 10:
        return {"n": len(sig), "hit_rate": float("nan"), "avg_fwd_long": float("nan")}
    hits = (np.sign(sig["tech_score"]) == np.sign(sig["fwd"])).mean()
    longs = sig[sig["tech_score"] > 0]["fwd"]
    return {"n": int(len(sig)), "hit_rate": float(hits),
            "avg_fwd_long": float(longs.mean()) if len(longs) else float("nan")}
