"""Análise de sentimento léxica para manchetes financeiras em português."""
import re
import unicodedata

POSITIVE = {
    "alta": 1.0, "altas": 1.0, "sobe": 1.0, "sobem": 1.0, "subiu": 1.0, "dispara": 1.5, "disparam": 1.5,
    "avanca": 1.0, "avancam": 1.0, "avancou": 1.0, "valoriza": 1.0, "valorizacao": 1.0, "lucro": 1.0,
    "lucros": 1.0, "recorde": 1.2, "supera": 1.0, "superam": 1.0, "superou": 1.0, "otimismo": 1.2,
    "otimista": 1.0, "aprova": 0.8, "aprovado": 0.8, "aprovada": 0.8, "aprovacao": 0.8, "crescimento": 0.8,
    "cresce": 0.8, "crescem": 0.8, "dividendos": 0.6, "proventos": 0.6, "upgrade": 1.2, "eleva": 0.5,
    "forte": 0.6, "ganho": 0.8, "ganhos": 0.8, "melhora": 1.0, "melhor": 0.6, "acordo": 0.6, "alivio": 1.2,
    "corte": 0.4, "recompra": 1.0, "positivo": 0.8, "positiva": 0.8, "salta": 1.2, "saltam": 1.2,
    "renova": 0.5, "atrai": 0.6, "expansao": 0.6, "estabilidade": 0.6, "surpreende": 0.6, "robusto": 0.8,
    "rali": 1.2, "recupera": 0.8, "recuperam": 0.8, "favoravel": 0.8,
}
NEGATIVE = {
    "queda": -1.0, "quedas": -1.0, "cai": -1.0, "caem": -1.0, "caiu": -1.0, "recua": -1.0, "recuam": -1.0,
    "recuou": -1.0, "despenca": -1.5, "despencam": -1.5, "desaba": -1.5, "tomba": -1.3, "prejuizo": -1.2,
    "perda": -0.8, "perdas": -0.8, "rebaixa": -1.2, "rebaixamento": -1.2, "downgrade": -1.2, "crise": -1.2,
    "risco": -0.6, "riscos": -0.6, "incerteza": -0.9, "incertezas": -0.9, "investigacao": -0.9,
    "multa": -0.8, "deficit": -0.8, "rombo": -1.2, "piora": -1.0, "pior": -0.6, "tensao": -0.9,
    "fraco": -0.7, "fraca": -0.7, "abaixo": -0.5, "desvaloriza": -1.0, "interferencia": -1.2,
    "intervencao": -0.9, "denuncia": -0.9, "greve": -0.8, "calote": -1.5, "pessimismo": -1.2,
    "volatilidade": -0.4, "temor": -1.0, "temores": -1.0, "receio": -0.8, "pressiona": -0.7,
    "pressao": -0.6, "derrota": -0.9, "impasse": -0.9, "escandalo": -1.3, "corrupcao": -1.2,
    "rejeita": -0.7, "rejeitado": -0.7, "suspende": -0.6, "atraso": -0.6, "inadimplencia": -0.9,
    "desaceleracao": -0.7, "recessao": -1.2, "aversao": -1.0, "fuga": -1.0, "estresse": -1.0,
    "negativo": -0.8, "negativa": -0.8, "furo": -1.0, "estoura": -1.0,
}
PHRASES = {
    "recuperacao judicial": -1.8, "corte de juros": 1.2, "corte da selic": 1.2, "alta de juros": -1.0,
    "alta da selic": -1.0, "aumento de juros": -1.0, "acima do esperado": 0.4, "abaixo do esperado": -0.6,
    "compra recomendada": 1.0, "recomendacao de compra": 1.0, "recomendacao de venda": -1.0,
    "meta fiscal": 0.0, "nao cumpre": -1.0, "realizacao de lucros": -0.6, "preco-alvo": 0.3,
    "eleva preco-alvo": 1.0, "corta preco-alvo": -1.0, "risco fiscal": -1.0,
}
NEGATORS = {"nao", "sem", "nem", "evita", "afasta", "descarta"}
INTENSIFIERS = {"forte": 1.3, "fortemente": 1.4, "muito": 1.3, "maior": 1.2, "historica": 1.3, "historico": 1.3}

_TOKEN = re.compile(r"[a-z0-9\-]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def score_text(text: str) -> float:
    """Retorna sentimento em [-1, 1]."""
    norm = normalize(text)
    total, hits = 0.0, 0
    for phrase, w in PHRASES.items():
        if phrase in norm:
            total += w
            hits += 1
            norm = norm.replace(phrase, " ")
    tokens = _TOKEN.findall(norm)
    for i, tok in enumerate(tokens):
        w = POSITIVE.get(tok) or NEGATIVE.get(tok)
        if not w:
            continue
        window = tokens[max(0, i - 3):i]
        if any(t in NEGATORS for t in window):
            w = -0.7 * w
        if i > 0 and tokens[i - 1] in INTENSIFIERS:
            w *= INTENSIFIERS[tokens[i - 1]]
        total += w
        hits += 1
    if hits == 0:
        return 0.0
    # Suaviza e limita: mais palavras = mais convicção, com retorno decrescente.
    raw = total / (hits ** 0.5 + 1.0)
    return max(-1.0, min(1.0, raw))
