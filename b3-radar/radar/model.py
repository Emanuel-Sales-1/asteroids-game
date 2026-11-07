"""Combina sinais técnicos, notícias e cenário político em previsões de curto prazo."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import UNIVERSE, Stock
from .market import backtest_technical, technical_frame
from .news import Article
from .politics import FactorReading, political_impact


@dataclass
class Weights:
    technical: float = 0.40
    news: float = 0.35
    political: float = 0.25

    def normalized(self) -> "Weights":
        s = self.technical + self.news + self.political or 1.0
        return Weights(self.technical / s, self.news / s, self.political / s)


@dataclass
class Forecast:
    ticker: str
    name: str
    sector: str
    price: float
    tech_score: float
    news_score: float
    political_score: float
    llm_adjust: float
    composite: float
    expected_return: float     # retorno esperado no horizonte
    range_low: float
    range_high: float
    prob_up: float
    confidence: str
    recommendation: str
    stop: float
    target: float
    n_news: int
    rsi: float
    vol_daily: float
    backtest: dict
    max_jump_20d: float = 0.0
    factor_contrib: dict[str, float] = field(default_factory=dict)
    headlines: list[Article] = field(default_factory=list)
    rationale: str = ""


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def news_score_for(stock: Stock, articles: list[Article], half_life: float) -> tuple[float, list[Article]]:
    direct = [a for a in articles if stock.ticker in a.tickers]
    sector_kw = stock.sector.lower().split("/")[0].split(" ")[0]
    sector = [a for a in articles if stock.ticker not in a.tickers and sector_kw in a.text.lower()]
    num = den = 0.0
    for a in direct:
        w = a.weight(half_life)
        num += w * a.sentiment
        den += w
    for a in sector:
        w = 0.3 * a.weight(half_life)
        num += w * a.sentiment
        den += w
    # Prior neutro com peso 2: poucas notícias -> score próximo de zero.
    score = num / (den + 2.0)
    return float(np.clip(score * 2.0, -1, 1)), sorted(direct, key=lambda a: a.published, reverse=True)


def classify(composite: float) -> str:
    if composite >= 0.35:
        return "Compra forte"
    if composite >= 0.15:
        return "Compra"
    if composite <= -0.35:
        return "Evitar / Venda"
    if composite <= -0.15:
        return "Cautela"
    return "Neutro"


def confidence_label(parts: list[float], n_news: int) -> str:
    signs = [np.sign(p) for p in parts if abs(p) > 0.05]
    agree = abs(sum(signs)) / len(signs) if signs else 0
    pts = agree * 2 + min(n_news, 10) / 10
    return "Alta" if pts >= 2.2 else "Média" if pts >= 1.3 else "Baixa"


def build_forecasts(prices: pd.DataFrame, articles: list[Article], scenario: dict[str, FactorReading],
                    weights: Weights, horizon: int = 5, half_life: float = 2.0,
                    llm: dict | None = None, universe: list[Stock] | None = None) -> list[Forecast]:
    w = weights.normalized()
    llm = llm or {}
    out = []
    for stock in universe or UNIVERSE:
        if stock.ticker not in prices.columns:
            continue
        close = prices[stock.ticker].dropna()
        if len(close) < 60:
            continue
        tf = technical_frame(close).iloc[-1]
        tech = float(tf["tech_score"])
        news, heads = news_score_for(stock, articles, half_life)
        pol, contrib = political_impact(stock, scenario)
        adj_info = llm.get(stock.ticker, {})
        adj = float(adj_info.get("ajuste", 0.0))
        composite = w.technical * tech + w.news * news + w.political * pol
        if adj_info:
            composite = 0.7 * composite + 0.3 * adj
        composite = float(np.clip(composite, -1, 1))

        vol = float(tf["vol_robust"]) if not math.isnan(tf["vol_robust"]) else 0.02
        sigma_h = vol * math.sqrt(horizon)
        # Sinais de curto prazo têm poder preditivo modesto: limitamos a ~0,35σ.
        exp_ret = composite * 0.35 * sigma_h
        price = float(close.iloc[-1])
        rec = classify(composite)
        out.append(Forecast(
            ticker=stock.ticker, name=stock.name, sector=stock.sector, price=price,
            tech_score=tech, news_score=news, political_score=pol, llm_adjust=adj, composite=composite,
            expected_return=exp_ret, range_low=exp_ret - sigma_h, range_high=exp_ret + sigma_h,
            prob_up=_norm_cdf(exp_ret / sigma_h) if sigma_h else 0.5,
            confidence=confidence_label([tech, news, pol], len(heads)), recommendation=rec,
            stop=price * (1 - 1.5 * sigma_h), target=price * (1 + max(exp_ret, 0) + sigma_h),
            n_news=len(heads), rsi=float(tf["rsi"]), vol_daily=vol,
            backtest=backtest_technical(close, horizon), max_jump_20d=float(tf["max_jump_20d"]),
            factor_contrib=contrib, headlines=heads[:8],
            rationale=adj_info.get("justificativa", ""),
        ))
    return sorted(out, key=lambda f: f.composite, reverse=True)


def forecasts_to_frame(forecasts: list[Forecast]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Ticker": f.ticker, "Empresa": f.name, "Setor": f.sector, "Preço (R$)": f.price,
        "Recomendação": f.recommendation, "Score": f.composite, "Ret. esperado": f.expected_return,
        "Faixa baixa": f.range_low, "Faixa alta": f.range_high, "Prob. alta": f.prob_up,
        "Confiança": f.confidence, "Técnico": f.tech_score, "Notícias": f.news_score,
        "Político": f.political_score, "IA": f.llm_adjust, "Nº notícias": f.n_news,
        "Stop (R$)": f.stop, "Alvo (R$)": f.target,
    } for f in forecasts])
