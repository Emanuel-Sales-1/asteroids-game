"""Análise opcional com Claude: lê as manchetes e o cenário e devolve ajustes estruturados.

Requer a variável de ambiente ANTHROPIC_API_KEY (ou `ant auth login`).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel

from .config import FACTORS, UNIVERSE
from .news import Article
from .politics import FactorReading

MODEL = "claude-opus-5-5"

SYSTEM = """Você é um analista sênior de renda variável brasileira (B3), especializado em
macroeconomia e risco político. Recebe manchetes recentes, a leitura automática de fatores
de cenário e indicadores técnicos das ações. Sua tarefa é produzir uma leitura de CURTO PRAZO
(próximos 5 a 10 pregões).

Regras:
- Baseie-se nas manchetes fornecidas (e em buscas na web, se a ferramenta estiver disponível).
  Não invente fatos, números ou declarações; se a evidência for fraca, use ajustes próximos de zero.
- Scores de fator vão de -1 a 1: positivo = o risco está PIORANDO para o mercado brasileiro.
- Ajustes por ação vão de -1 (muito negativo) a 1 (muito positivo) para os próximos dias,
  considerando notícias específicas, exposição setorial ao cenário político/macro e catalisadores
  (balanços, Copom, votações no Congresso, eleições, dividendos).
- Seja calibrado: a maioria dos ajustes deve ficar entre -0,4 e 0,4.
- Escreva em português do Brasil, de forma objetiva."""


class FatorIA(BaseModel):
    fator: str
    score: float
    comentario: str


class AcaoIA(BaseModel):
    ticker: str
    ajuste: float
    justificativa: str
    riscos: str


class AnaliseIA(BaseModel):
    resumo_cenario: str
    eventos_proximos: list[str]
    fatores: list[FatorIA]
    acoes: list[AcaoIA]


def _build_prompt(articles: list[Article], scenario: dict[str, FactorReading], tech: dict[str, dict]) -> str:
    heads = sorted(articles, key=lambda a: a.published, reverse=True)[:120]
    lines = [f"- [{a.published:%d/%m %H:%M}] ({a.source}) {a.title}" for a in heads]
    fat = {f: {"rotulo": r.label, "score_automatico": r.score, "n_noticias": r.n_articles}
           for f, r in scenario.items()}
    acoes = [{"ticker": s.ticker, "empresa": s.name, "setor": s.sector, "estatal": s.state_owned,
              **tech.get(s.ticker, {})} for s in UNIVERSE if s.ticker in tech]
    return (
        f"Data de referência: {datetime.now(timezone.utc):%Y-%m-%d}.\n\n"
        f"## Manchetes recentes ({len(lines)})\n" + "\n".join(lines) +
        "\n\n## Leitura automática dos fatores (chaves válidas para 'fator')\n" +
        json.dumps(fat, ensure_ascii=False, indent=1) +
        "\n\n## Ações e indicadores técnicos\n" + json.dumps(acoes, ensure_ascii=False, indent=1) +
        "\n\nDevolva: resumo do cenário político/econômico; próximos eventos relevantes; um score "
        f"para cada fator ({', '.join(FACTORS)}); e um ajuste com justificativa e riscos para cada ação listada."
    )


def analyze(articles: list[Article], scenario: dict[str, FactorReading], tech: dict[str, dict],
            web_search: bool = False, effort: str = "high") -> AnaliseIA:
    import anthropic

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _build_prompt(articles, scenario, tech)}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5,
              "user_location": {"type": "approximate", "country": "BR"}}] if web_search else []
    kwargs = {"tools": tools} if tools else {}

    for _ in range(4):  # continua se a busca na web pausar o turno
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=messages,
            output_config={"effort": effort},
            output_format=AnaliseIA,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **kwargs,
        )
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason == "refusal":
            raise RuntimeError("O modelo recusou a solicitação.")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Resposta truncada (max_tokens).")
        if response.parsed_output is None:
            raise RuntimeError("Resposta sem saída estruturada.")
        return response.parsed_output
    raise RuntimeError("A análise não terminou após várias pausas.")


def to_adjustments(result: AnaliseIA) -> dict[str, dict]:
    clip = lambda x: max(-1.0, min(1.0, float(x)))
    return {a.ticker.upper().strip(): {"ajuste": clip(a.ajuste), "justificativa": a.justificativa,
                                       "riscos": a.riscos} for a in result.acoes}


def merge_scenario(scenario: dict[str, FactorReading], result: AnaliseIA, weight: float = 0.5) -> dict[str, FactorReading]:
    """Média ponderada entre a leitura automática e a da IA."""
    ia = {f.fator: max(-1.0, min(1.0, f.score)) for f in result.fatores}
    merged = {}
    for key, r in scenario.items():
        score = (1 - weight) * r.score + weight * ia[key] if key in ia else r.score
        merged[key] = FactorReading(r.factor, r.label, round(score, 3), r.n_articles, r.top_headlines)
    return merged
