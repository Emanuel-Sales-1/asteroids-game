# B3 Radar 📈

Painel em Streamlit que gera **previsões de curto prazo (3 a 15 pregões)** para ações da B3,
combinando três sinais:

1. **Técnico**: tendência (MM20 × MM50), momento de 5 e 20 dias e RSI.
2. **Notícias**: manchetes dos últimos 7 dias (Google Notícias + InfoMoney, Money Times e Valor)
   com análise de sentimento em português, marcadas por empresa e setor.
3. **Cenário político/macro**: sete fatores lidos das manchetes (risco fiscal, Selic, câmbio,
   intervenção em estatais, governabilidade/eleições, commodities, cenário externo), aplicados a
   uma matriz de exposição setorial. As estatais (PETR4, BBAS3) têm sensibilidade extra a interferência.

Opcionalmente, **Claude** (API da Anthropic) lê as manchetes, pode pesquisar na web, revisa o
cenário e sugere um ajuste justificado para cada ação.

> ⚠️ Ferramenta educacional. As previsões têm alta incerteza e **não são recomendação de investimento**.

## Como rodar

```bash
cd b3-radar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Abra http://localhost:8501. Escolha **Ao vivo** (precisa de internet) ou **Demonstração**
(dados fictícios e offline).

### Análise com IA (opcional)

```bash
export ANTHROPIC_API_KEY="sua-chave"     # Windows PowerShell: $env:ANTHROPIC_API_KEY="sua-chave"
streamlit run app.py
```

Marque **Refinar com Claude** na barra lateral. O app usa o modelo `claude-opus-5-5` com saída
estruturada e fallback automático no servidor. Cada análise custa algumas dezenas de centavos de
dólar, mais se a busca na web estiver ligada. O resultado fica em cache por 30 minutos.

## O que a tela mostra

| Aba | Conteúdo |
|---|---|
| Recomendações | Destaques de compra, ranking com retorno esperado, faixa ±1σ, probabilidade de alta, stop e alvo; decomposição do score |
| Cenário político | Termômetro de cada fator, resumo da IA, sensibilidade setorial e as manchetes que movem cada fator |
| Ação detalhada | Gráfico com médias e cone de previsão, componentes do score, backtest do sinal técnico, notícias da empresa |
| Notícias | Todas as manchetes com sentimento, ações e fatores identificados |
| Metodologia | Fórmulas e limitações |

## Personalizar

- `radar/config.py`: lista de ações, palavras-chave dos fatores e matriz de exposição setorial.
- `radar/sentiment.py`: léxico de sentimento.
- Os pesos dos sinais, o horizonte e a meia-vida das notícias são ajustados na barra lateral.

## Testes

```bash
pytest -q
```

## Estrutura

```
app.py             interface Streamlit
radar/config.py    universo, fatores e exposições
radar/news.py      coleta RSS, deduplicação e marcação
radar/sentiment.py sentimento léxico PT-BR
radar/politics.py  leitura do cenário e impacto por ação
radar/market.py    cotações (yfinance), indicadores e backtest
radar/model.py     combinação dos sinais e previsão
radar/llm.py       análise opcional com Claude
radar/demo.py      dados fictícios para o modo offline
```
