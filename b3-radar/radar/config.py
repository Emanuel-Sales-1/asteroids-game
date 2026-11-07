"""Universo de ações, fatores macro/políticos e exposições setoriais.

As exposições são heurísticas qualitativas (de -1 a +1) que indicam como cada
setor tende a reagir quando um fator político/macro piora (+) ou melhora (-)
na ótica do mercado. Ajuste à vontade.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stock:
    ticker: str
    name: str
    sector: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    state_owned: bool = False
    # Termos ambíguos que só contam com a grafia exata (ex.: "Vale" a empresa, não "vale a pena").
    cased_aliases: tuple[str, ...] = field(default_factory=tuple)


UNIVERSE: list[Stock] = [
    Stock("PETR4", "Petrobras", "Petróleo e Gás", ("petrobras", "petr4", "petr3"), True),
    Stock("PRIO3", "PRIO", "Petróleo e Gás", ("prio", "petrorio", "prio3")),
    Stock("VALE3", "Vale", "Mineração", ("vale3", "mineradora vale", "vale s.a"), cased_aliases=("Vale",)),
    Stock("ITUB4", "Itaú Unibanco", "Bancos", ("itaú", "itau", "itub4")),
    Stock("BBDC4", "Bradesco", "Bancos", ("bradesco", "bbdc4")),
    Stock("BBAS3", "Banco do Brasil", "Bancos", ("banco do brasil", "bbas3"), True),
    Stock("B3SA3", "B3", "Serviços Financeiros", ("b3sa3", "bolsa b3")),
    Stock("WEGE3", "WEG", "Bens de Capital", ("weg", "wege3")),
    Stock("ABEV3", "Ambev", "Consumo", ("ambev", "abev3")),
    Stock("MGLU3", "Magazine Luiza", "Varejo", ("magazine luiza", "magalu", "mglu3")),
    Stock("LREN3", "Lojas Renner", "Varejo", ("renner", "lren3")),
    Stock("AXIA3", "Axia Energia (ex-Eletrobras)", "Energia Elétrica", ("axia", "axia energia", "axia3", "eletrobras", "elet3", "elet6")),
    Stock("EGIE3", "Engie Brasil", "Energia Elétrica", ("engie", "egie3")),
    Stock("SBSP3", "Sabesp", "Saneamento", ("sabesp", "sbsp3")),
    Stock("SUZB3", "Suzano", "Papel e Celulose", ("suzano", "suzb3")),
    Stock("JBSS32", "JBS (BDR)", "Proteínas", ("jbs", "jbss3", "jbss32")),
    Stock("CYRE3", "Cyrela", "Construção Civil", ("cyrela", "cyre3")),
    Stock("RENT3", "Localiza", "Locação", ("localiza", "rent3")),
    Stock("RADL3", "Raia Drogasil", "Saúde/Varejo", ("raia drogasil", "raiadrogasil", "radl3")),
    Stock("EMBJ3", "Embraer", "Aeroespacial", ("embraer", "embr3", "embj3")),
]

BENCHMARK = "^BVSP"

# Fatores do cenário político/macro. "score" positivo = piora de risco.
FACTORS: dict[str, dict] = {
    "risco_fiscal": {
        "label": "Risco fiscal",
        "keywords": ["fiscal", "arcabouço", "arcabouco", "déficit", "deficit", "gastos públicos",
                     "dívida pública", "divida publica", "meta fiscal", "orçamento", "orcamento",
                     "rombo", "contas públicas", "superávit", "superavit", "lei orçamentária"],
    },
    "juros_selic": {
        "label": "Juros/Selic em alta",
        "keywords": ["selic", "copom", "juros", "banco central", "galípolo", "galipolo",
                     "inflação", "inflacao", "ipca", "di futuro", "curva de juros"],
    },
    "cambio": {
        "label": "Dólar em alta",
        "keywords": ["dólar", "dolar", "câmbio", "cambio", "real se desvaloriza", "moeda americana"],
    },
    "intervencao_estatal": {
        "label": "Intervenção em estatais",
        "keywords": ["interferência", "interferencia", "intervenção", "intervencao", "estatal",
                     "estatais", "conselho de administração", "preço dos combustíveis",
                     "politica de preços", "política de preços", "dividendos extraordinários",
                     "indicação política"],
    },
    "governabilidade": {
        "label": "Instabilidade política",
        "keywords": ["congresso", "câmara", "camara", "senado", "eleição", "eleicao", "eleições",
                     "eleicoes", "planalto", "lula", "governo federal", "stf", "reforma",
                     "pesquisa eleitoral", "segundo turno", "ministro", "base aliada", "cpi",
                     "impeachment", "pec"],
    },
    "commodities": {
        "label": "Queda de commodities",
        "keywords": ["minério", "minerio", "petróleo", "petroleo", "brent", "commodities",
                     "china", "celulose", "soja", "boi gordo"],
    },
    "externo": {
        "label": "Aversão a risco global",
        "keywords": ["fed", "treasuries", "tarifa", "tarifas", "trump", "recessão", "recessao",
                     "wall street", "guerra", "geopolítica", "geopolitica"],
    },
}

# Fatores ambíguos só contam quando a notícia tem contexto brasileiro/estatal explícito,
# para não misturar política de outros países ou usos médicos/esportivos das palavras.
FACTOR_CONTEXT: dict[str, list[str]] = {
    "governabilidade": ["brasil", "brasileiro", "brasileira", "lula", "planalto", "congresso nacional",
                        "câmara dos deputados", "camara dos deputados", "senado federal", "stf", "tse",
                        "governo federal", "governo lula", "haddad", "alcolumbre", "hugo motta",
                        "flávio bolsonaro", "flavio bolsonaro", "bolsonaro", "tarcísio", "tarcisio",
                        "ibovespa", "b3", "pt ", "centrão", "centrao", "esplanada"],
    "intervencao_estatal": ["petrobras", "banco do brasil", "caixa econômica", "caixa economica", "bndes",
                            "correios", "estatal", "estatais", "governo federal", "governo lula", "lula",
                            "planalto", "conselho de administração", "conselho de administracao"],
}

# Sensibilidade setorial: retorno tende a cair quando o fator piora (valores negativos)
# e a subir quando melhora. Escala aproximada -1..+1.
SECTOR_EXPOSURE: dict[str, dict[str, float]] = {
    "Petróleo e Gás":       {"risco_fiscal": -0.2, "juros_selic": -0.1, "cambio": 0.4, "intervencao_estatal": -0.3, "governabilidade": -0.2, "commodities": -0.8, "externo": -0.3},
    "Mineração":            {"risco_fiscal": -0.1, "juros_selic": -0.1, "cambio": 0.5, "intervencao_estatal": -0.1, "governabilidade": -0.1, "commodities": -0.9, "externo": -0.4},
    "Bancos":               {"risco_fiscal": -0.5, "juros_selic": 0.1, "cambio": -0.2, "intervencao_estatal": -0.1, "governabilidade": -0.4, "commodities": -0.1, "externo": -0.4},
    "Serviços Financeiros": {"risco_fiscal": -0.6, "juros_selic": -0.5, "cambio": -0.3, "intervencao_estatal": 0.0, "governabilidade": -0.5, "commodities": 0.0, "externo": -0.5},
    "Bens de Capital":      {"risco_fiscal": -0.2, "juros_selic": -0.3, "cambio": 0.4, "intervencao_estatal": 0.0, "governabilidade": -0.2, "commodities": -0.1, "externo": -0.3},
    "Consumo":              {"risco_fiscal": -0.3, "juros_selic": -0.3, "cambio": -0.3, "intervencao_estatal": 0.0, "governabilidade": -0.2, "commodities": 0.1, "externo": -0.1},
    "Varejo":               {"risco_fiscal": -0.7, "juros_selic": -0.9, "cambio": -0.4, "intervencao_estatal": 0.0, "governabilidade": -0.5, "commodities": 0.0, "externo": -0.3},
    "Energia Elétrica":     {"risco_fiscal": -0.4, "juros_selic": -0.5, "cambio": -0.1, "intervencao_estatal": -0.3, "governabilidade": -0.3, "commodities": 0.0, "externo": -0.1},
    "Saneamento":           {"risco_fiscal": -0.4, "juros_selic": -0.5, "cambio": -0.1, "intervencao_estatal": -0.3, "governabilidade": -0.3, "commodities": 0.0, "externo": -0.1},
    "Papel e Celulose":     {"risco_fiscal": 0.0, "juros_selic": -0.1, "cambio": 0.7, "intervencao_estatal": 0.0, "governabilidade": 0.0, "commodities": -0.6, "externo": -0.2},
    "Proteínas":            {"risco_fiscal": 0.0, "juros_selic": -0.1, "cambio": 0.5, "intervencao_estatal": 0.0, "governabilidade": -0.1, "commodities": -0.2, "externo": -0.2},
    "Construção Civil":     {"risco_fiscal": -0.7, "juros_selic": -1.0, "cambio": -0.2, "intervencao_estatal": 0.0, "governabilidade": -0.4, "commodities": 0.0, "externo": -0.2},
    "Locação":              {"risco_fiscal": -0.5, "juros_selic": -0.8, "cambio": -0.2, "intervencao_estatal": 0.0, "governabilidade": -0.3, "commodities": 0.0, "externo": -0.2},
    "Saúde/Varejo":         {"risco_fiscal": -0.3, "juros_selic": -0.5, "cambio": -0.1, "intervencao_estatal": 0.0, "governabilidade": -0.2, "commodities": 0.0, "externo": -0.1},
    "Aeroespacial":         {"risco_fiscal": 0.0, "juros_selic": -0.1, "cambio": 0.7, "intervencao_estatal": 0.0, "governabilidade": 0.0, "commodities": 0.0, "externo": -0.5},
}

# Estatais recebem peso extra no fator de intervenção.
STATE_OWNED_EXTRA = {"intervencao_estatal": -0.5, "governabilidade": -0.2}

NEWS_QUERIES = [
    "Ibovespa hoje",
    "mercado financeiro Brasil ações",
    "Copom Selic",
    "risco fiscal arcabouço governo",
    "Congresso economia votação",
    "dólar real câmbio hoje",
    "eleições 2026 mercado",
    "Petrobras ações",
    "Vale minério ações",
    "bancos resultados trimestre",
]

DIRECT_FEEDS = [
    "https://www.infomoney.com.br/feed/",
    "https://www.moneytimes.com.br/feed/",
    "https://valor.globo.com/rss/valor/",
]
