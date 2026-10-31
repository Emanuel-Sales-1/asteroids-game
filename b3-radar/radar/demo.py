"""Dados sintéticos para o modo demonstração (sem internet). NÃO são notícias reais."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .config import UNIVERSE
from .news import Article, tag_articles

_HEADLINES = [
    ("Copom sinaliza manutenção da Selic e mercado vê corte de juros apenas em 2027", 0.5),
    ("Dólar sobe com incerteza fiscal e aversão a risco no exterior", 0.3),
    ("Governo anuncia bloqueio de gastos para cumprir a meta fiscal", 1.0),
    ("Congresso aprova projeto de reforma em votação simbólica na Câmara", 1.5),
    ("Petrobras: analistas temem interferência na política de preços dos combustíveis", 0.8),
    ("Petróleo Brent avança com tensão geopolítica no Oriente Médio", 0.4),
    ("Vale tem lucro acima do esperado no trimestre e anuncia recompra de ações", 2.0),
    ("Minério de ferro recua na China com dados fracos da construção", 1.2),
    ("Itaú supera estimativas e lucro bate recorde no trimestre", 2.5),
    ("Bradesco mostra melhora na inadimplência, mas rentabilidade segue abaixo de pares", 2.2),
    ("Magazine Luiza tem prejuízo e ações despencam após balanço", 1.8),
    ("Varejo sofre com juros altos e consumo fraco, dizem analistas", 3.0),
    ("WEG eleva preço-alvo após crescimento forte em energia renovável", 1.1),
    ("Eletrobras aprova pagamento de dividendos extraordinários", 2.7),
    ("Sabesp avança em plano de investimentos pós-privatização", 3.5),
    ("Suzano se beneficia do dólar em alta e de alta da celulose", 0.9),
    ("Embraer recebe novas encomendas e ações renovam máxima", 1.4),
    ("Cyrela: lançamentos crescem, mas juros altos pressionam construção civil", 2.9),
    ("Pesquisa eleitoral aumenta incerteza e mercado teme polarização", 0.6),
    ("Inflação abaixo do esperado em outubro traz alívio para a curva de juros", 0.2),
    ("Banco do Brasil: indicação política no conselho preocupa investidores", 1.7),
    ("Localiza tem resultado robusto e analistas mantêm recomendação de compra", 3.2),
    ("JBS conclui listagem e ações sobem com otimismo de investidores", 4.0),
    ("Ambev recua com volumes fracos de cerveja no Brasil", 2.4),
    ("B3 tem queda no volume negociado em meio a incertezas fiscais", 1.9),
    ("Fed corta juros e apetite por risco favorece emergentes", 4.5),
    ("Renner apresenta vendas acima do esperado e margem melhor", 3.8),
    ("Raia Drogasil cresce, mas despesas pressionam margens", 2.1),
    ("PRIO dispara com aumento de produção e petróleo em alta", 0.7),
    ("Engie Brasil: aprovação de leilão de transmissão favorece elétricas", 5.0),
]


def demo_articles(now: datetime | None = None) -> list[Article]:
    now = now or datetime.now(timezone.utc)
    arts = [Article(title=t, summary="", link="", source="DEMO (fictício)", published=now - timedelta(days=d))
            for t, d in _HEADLINES]
    return tag_articles(arts)


def demo_prices(days: int = 260, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    market = rng.normal(0.0003, 0.011, days)
    cols = {}
    for i, s in enumerate(UNIVERSE):
        beta = 0.7 + 0.6 * rng.random()
        drift = rng.normal(0.0002, 0.0006)
        idio = rng.normal(drift, 0.012 + 0.01 * rng.random(), days)
        cols[s.ticker] = (10 + 40 * rng.random()) * np.exp(np.cumsum(beta * market + idio))
    cols["^BVSP"] = 125000 * np.exp(np.cumsum(market))
    return pd.DataFrame(cols, index=idx)
