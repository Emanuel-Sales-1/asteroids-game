"""Leitura do cenário político/macro a partir das notícias.

Cada fator recebe um score em [-1, 1]: positivo = o risco está piorando
(ex.: juros subindo, dólar subindo, ruído fiscal), negativo = melhorando.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .config import FACTORS, SECTOR_EXPOSURE, STATE_OWNED_EXTRA, Stock
from .news import Article
from .sentiment import normalize

# Pistas direcionais: (regex, direção). +1 = fator piora, -1 = fator melhora.
DIRECTIONAL: dict[str, list[tuple[str, int]]] = {
    "juros_selic": [
        (r"(alta|aumento|elev\w+|sobe|subir|subida|aperto)\s+(d[aoe]s?\s+)?(selic|juros|taxa)", 1),
        (r"(selic|juros)\s+(sobe|sobem|em alta|maior|dispara)", 1),
        (r"inflacao\s+(acima|sobe|acelera|dispara|surpreende)", 1),
        (r"(corte|queda|reduc\w+|reduz|cortar|afrouxamento)\s+(d[aoe]s?\s+)?(selic|juros|taxa)", -1),
        (r"(selic|juros)\s+(cai|caem|recua|recuam|em queda|menor)", -1),
        (r"inflacao\s+(abaixo|desacelera|cai|recua|perde forca)", -1),
        (r"manutencao\s+da\s+selic", 0),
    ],
    "cambio": [
        (r"dolar\s+(sobe|dispara|avanca|salta|fecha em alta|renova maxima|em alta|bate)", 1),
        (r"real\s+(se desvaloriza|perde|cai)", 1),
        (r"dolar\s+(cai|recua|despenca|fecha em queda|em queda|perde)", -1),
        (r"real\s+(se valoriza|ganha|sobe)", -1),
    ],
    "risco_fiscal": [
        (r"(rombo|deficit|estouro|furo|gastos?\s+acima|descumpr\w+|mudanca\s+da\s+meta|piora\s+fiscal|pacote\s+de\s+gastos)", 1),
        (r"(superavit|corte\s+de\s+gastos|ajuste\s+fiscal|cumpr\w+\s+(a\s+)?meta|meta\s+cumprida|contingenciamento|bloqueio\s+de\s+gastos)", -1),
    ],
    "intervencao_estatal": [
        (r"(interferencia|intervencao|ingerencia|troca\s+(no|do)\s+comando|indicacao\s+politica|congela\w*\s+preco)", 1),
        (r"(governanca|independencia|sem\s+interferencia|privatiza\w+)", -1),
    ],
    "governabilidade": [
        (r"(derrota|impasse|crise|tensao|cpi|denuncia|escandalo|rejeita|obstrucao|polariza\w+)", 1),
        (r"(aprova\w*|acordo|alianca|consenso|vitoria\s+do\s+governo|sancion\w+)", -1),
    ],
    "commodities": [
        (r"(petroleo|brent|minerio|commodities|celulose)\s+(cai|caem|recua|recuam|despenca|em queda|tomba)", 1),
        (r"(petroleo|brent|minerio|commodities|celulose)\s+(sobe|sobem|avanca|avancam|dispara|em alta|salta)", -1),
        (r"china\s+(desacelera|fraca|crise)", 1),
        (r"china\s+(estimulo|estimulos|cresce|acelera)", -1),
    ],
    "externo": [
        (r"(aversao\s+a\s+risco|tarifa\w*|guerra|tensao\s+geopolitica|recessao|treasuries\s+sobem|fed\s+(sobe|eleva|mantem))", 1),
        (r"(fed\s+(corta|reduz)|apetite\s+(por|a)\s+risco|alivio\s+global|tregua|wall\s+street\s+(sobe|renova))", -1),
    ],
}
_COMPILED = {f: [(re.compile(rx), d) for rx, d in rules] for f, rules in DIRECTIONAL.items()}


@dataclass
class FactorReading:
    factor: str
    label: str
    score: float      # -1..1, positivo = piora
    n_articles: int
    top_headlines: list[str]


def _direction(article: Article, factor: str) -> float:
    norm = normalize(article.text)
    votes = [d for rx, d in _COMPILED.get(factor, []) if rx.search(norm)]
    if votes:
        return max(-1.0, min(1.0, sum(votes) / len(votes)))
    # Sem pista explícita: notícia negativa sobre o tema = piora do fator.
    return -article.sentiment


def read_scenario(articles: list[Article], half_life_days: float = 2.0) -> dict[str, FactorReading]:
    readings = {}
    for f, cfg in FACTORS.items():
        related = [a for a in articles if f in a.factors]
        num = den = 0.0
        for a in related:
            w = a.weight(half_life_days)
            num += w * _direction(a, f)
            den += w
        # Encolhe para zero quando há poucas notícias (prior neutro com peso 3).
        score = num / (den + 3.0) if related else 0.0
        top = sorted(related, key=lambda a: a.weight(half_life_days) * (abs(_direction(a, f)) + 0.1), reverse=True)
        readings[f] = FactorReading(f, cfg["label"], round(max(-1, min(1, score * 1.5)), 3), len(related),
                                    [a.title for a in top[:5]])
    return readings


def exposure_for(stock: Stock) -> dict[str, float]:
    exp = dict(SECTOR_EXPOSURE.get(stock.sector, {}))
    if stock.state_owned:
        for f, extra in STATE_OWNED_EXTRA.items():
            exp[f] = exp.get(f, 0.0) + extra
    return exp


def political_impact(stock: Stock, scenario: dict[str, FactorReading]) -> tuple[float, dict[str, float]]:
    """Impacto esperado do cenário na ação, em [-1, 1], e contribuição por fator."""
    exp = exposure_for(stock)
    contrib = {f: exp.get(f, 0.0) * r.score for f, r in scenario.items()}
    total = sum(contrib.values())
    return math.tanh(total * 1.5), contrib
