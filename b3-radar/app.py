"""B3 Radar — painel Streamlit de recomendações de curto prazo para ações brasileiras.

Execute com:  streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from radar import config, demo, llm, market, news, politics
from radar.model import Weights, build_forecasts, forecasts_to_frame

st.set_page_config(page_title="B3 Radar", page_icon="📈", layout="wide")

REC_COLORS = {"Compra forte": "#1a7f37", "Compra": "#4caf50", "Neutro": "#8a8f98",
              "Cautela": "#e3a008", "Evitar / Venda": "#d1242f"}


# ---------------------------------------------------------------- dados
@st.cache_data(ttl=900, show_spinner=False)
def load_live(period: str):
    tickers = [s.ticker for s in config.UNIVERSE] + [config.BENCHMARK]
    prices = market.fetch_prices(tickers, period)
    articles = news.fetch_all()
    return prices, articles, datetime.now()


def load_data(mode: str):
    if mode == "Demonstração (offline)":
        return demo.demo_prices(), demo.demo_articles(), datetime.now()
    return load_live("1y")


@st.cache_data(ttl=1800, show_spinner=False)
def run_llm(_articles, _scenario, tech: dict, web_search: bool, cache_key: str):
    return llm.analyze(_articles, _scenario, tech, web_search=web_search)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("📈 B3 Radar")
    mode = st.radio("Fonte de dados", ["Ao vivo (internet)", "Demonstração (offline)"])
    horizon = st.select_slider("Horizonte da previsão (pregões)", options=[3, 5, 10, 15], value=5)
    half_life = st.slider("Meia-vida das notícias (dias)", 0.5, 5.0, 2.0, 0.5,
                          help="Notícias mais antigas perdem peso exponencialmente.")
    st.subheader("Pesos dos sinais")
    w_tech = st.slider("Técnico (preço/momento)", 0.0, 1.0, 0.40, 0.05)
    w_news = st.slider("Notícias da empresa/setor", 0.0, 1.0, 0.35, 0.05)
    w_pol = st.slider("Cenário político/macro", 0.0, 1.0, 0.25, 0.05)
    st.subheader("Análise com IA (Claude)")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    use_llm = st.checkbox("Refinar com Claude", value=False, disabled=not has_key,
                          help="Requer ANTHROPIC_API_KEY. Claude lê as manchetes e ajusta o cenário e as ações.")
    use_web = st.checkbox("Permitir que a IA pesquise na web", value=True, disabled=not use_llm)
    if not has_key:
        st.caption("Defina `ANTHROPIC_API_KEY` para habilitar a análise com IA.")
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()

st.title("B3 Radar — previsões de curto prazo")
st.warning(
    "**Aviso:** ferramenta educacional e experimental. As previsões são estimativas estatísticas "
    "com alta incerteza e **não constituem recomendação de investimento** (Resolução CVM 20/2021). "
    "Faça sua própria análise e, se necessário, consulte um profissional certificado.", icon="⚠️")

with st.spinner("Coletando cotações e notícias…"):
    try:
        prices, articles, loaded_at = load_data(mode)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao carregar dados: {exc}")
        st.stop()

if prices.empty:
    st.error("Não foi possível obter cotações. Verifique a conexão ou use o modo demonstração.")
    st.stop()
if not articles:
    st.info("Nenhuma notícia foi coletada — o modelo usará apenas sinais técnicos.")

scenario = politics.read_scenario(articles, half_life)
ia_result = None
llm_adj: dict = {}
if use_llm:
    tech_snapshot = {}
    for s in config.UNIVERSE:
        if s.ticker in prices.columns and prices[s.ticker].dropna().size >= 60:
            tf = market.technical_frame(prices[s.ticker].dropna()).iloc[-1]
            tech_snapshot[s.ticker] = {"preco": round(float(tf["close"]), 2), "ret_5d": round(float(tf["ret_5d"]), 4),
                                       "ret_20d": round(float(tf["ret_20d"]), 4), "rsi": round(float(tf["rsi"]), 1),
                                       "score_tecnico": round(float(tf["tech_score"]), 3)}
    with st.spinner("Claude está analisando o cenário político e as notícias…"):
        try:
            ia_result = run_llm(articles, scenario, tech_snapshot, use_web,
                                f"{loaded_at:%Y%m%d%H}{len(articles)}{mode}")
            scenario = llm.merge_scenario(scenario, ia_result)
            llm_adj = llm.to_adjustments(ia_result)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Análise com IA indisponível: {exc}")

forecasts = build_forecasts(prices, articles, scenario, Weights(w_tech, w_news, w_pol),
                            horizon=horizon, half_life=half_life, llm=llm_adj)
df = forecasts_to_frame(forecasts)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Ações analisadas", len(forecasts))
c2.metric("Notícias (7 dias)", len(articles))
if config.BENCHMARK in prices.columns:
    ibov = prices[config.BENCHMARK].dropna()
    c3.metric("Ibovespa", f"{ibov.iloc[-1]:,.0f}".replace(",", "."), f"{ibov.pct_change(5).iloc[-1]:+.2%} (5d)")
risk = sum(r.score for r in scenario.values()) / len(scenario)
c4.metric("Termômetro de risco", f"{risk:+.2f}", "piorando" if risk > 0.05 else "melhorando" if risk < -0.05 else "estável",
          delta_color="inverse" if abs(risk) > 0.05 else "off")
st.caption(f"Dados carregados em {loaded_at:%d/%m/%Y %H:%M} · fonte: {mode}")

tab_rec, tab_pol, tab_stock, tab_news, tab_method = st.tabs(
    ["🏆 Recomendações", "🏛️ Cenário político", "🔍 Ação detalhada", "📰 Notícias", "📐 Metodologia"])

# ---------------------------------------------------------------- recomendações
with tab_rec:
    buys = [f for f in forecasts if f.recommendation.startswith("Compra")][:3]
    st.subheader("Destaques de compra")
    if not buys:
        st.info("Nenhuma ação atingiu o limiar de compra no cenário atual.")
    cols = st.columns(max(1, len(buys)))
    for col, f in zip(cols, buys):
        with col.container(border=True):
            st.markdown(f"### {f.ticker}  \n{f.name} · {f.sector}")
            st.markdown(f"**{f.recommendation}** · confiança {f.confidence}")
            st.metric("Retorno esperado", f"{f.expected_return:+.2%}", f"{horizon} pregões", delta_color="off")
            st.caption(f"Faixa provável: {f.range_low:+.1%} a {f.range_high:+.1%} · P(alta) {f.prob_up:.0%}")
            st.caption(f"Preço R\\$ {f.price:.2f} · stop R\\$ {f.stop:.2f} · alvo R\\$ {f.target:.2f}")
            if f.rationale:
                st.caption(f"🤖 {f.rationale}")

    st.subheader("Ranking completo")
    styled = df.style.format({
        "Preço (R$)": "{:.2f}", "Score": "{:+.2f}", "Ret. esperado": "{:+.2%}", "Faixa baixa": "{:+.1%}",
        "Faixa alta": "{:+.1%}", "Prob. alta": "{:.0%}", "Técnico": "{:+.2f}", "Notícias": "{:+.2f}",
        "Político": "{:+.2f}", "IA": "{:+.2f}", "Stop (R$)": "{:.2f}", "Alvo (R$)": "{:.2f}",
    }).map(lambda v: f"color: {REC_COLORS.get(v, 'inherit')}; font-weight: 600", subset=["Recomendação"]) \
      .background_gradient(cmap="RdYlGn", vmin=-0.6, vmax=0.6, subset=["Score"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8"), "b3_radar.csv", "text/csv")

    st.subheader("Decomposição do score")
    wn = Weights(w_tech, w_news, w_pol).normalized()
    fig = go.Figure()
    for label, attr, wt, color in [("Técnico", "tech_score", wn.technical, "#4e79a7"),
                                   ("Notícias", "news_score", wn.news, "#f28e2b"),
                                   ("Político", "political_score", wn.political, "#b07aa1")]:
        fig.add_bar(name=label, x=[f.ticker for f in forecasts], y=[getattr(f, attr) * wt for f in forecasts],
                    marker_color=color)
    fig.add_scatter(name="Score final", x=[f.ticker for f in forecasts], y=[f.composite for f in forecasts],
                    mode="markers", marker=dict(color="black", size=9, symbol="diamond"))
    fig.update_layout(barmode="relative", height=420, margin=dict(t=20, b=20), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- cenário político
with tab_pol:
    if ia_result:
        st.subheader("🤖 Leitura do cenário (Claude)")
        st.write(ia_result.resumo_cenario)
        if ia_result.eventos_proximos:
            st.markdown("**Próximos eventos no radar:**\n" + "\n".join(f"- {e}" for e in ia_result.eventos_proximos))
        with st.expander("Comentários por fator"):
            for f in ia_result.fatores:
                st.markdown(f"- **{config.FACTORS.get(f.fator, {}).get('label', f.fator)}** ({f.score:+.2f}): {f.comentario}")

    st.subheader("Fatores de risco (positivo = piorando)")
    readings = list(scenario.values())
    fig = go.Figure(go.Bar(
        x=[r.score for r in readings], y=[r.label for r in readings], orientation="h",
        marker_color=["#d1242f" if r.score > 0 else "#1a7f37" for r in readings],
        text=[f"{r.score:+.2f} · {r.n_articles} notícias" for r in readings], textposition="outside"))
    fig.update_layout(xaxis=dict(range=[-1, 1], zeroline=True), height=380, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Sensibilidade setorial ao cenário atual")
    rows = []
    for s in config.UNIVERSE:
        impact, contrib = politics.political_impact(s, scenario)
        rows.append({"Ticker": s.ticker, "Setor": s.sector, "Estatal": "sim" if s.state_owned else "",
                     "Impacto": impact, **{config.FACTORS[k]["label"]: v for k, v in contrib.items()}})
    imp = pd.DataFrame(rows).sort_values("Impacto", ascending=False)
    num_cols = [c for c in imp.columns if c not in ("Ticker", "Setor", "Estatal")]
    st.dataframe(imp.style.format({c: "{:+.2f}" for c in num_cols})
                 .background_gradient(cmap="RdYlGn", vmin=-0.5, vmax=0.5, subset=num_cols),
                 use_container_width=True, hide_index=True)

    st.subheader("Manchetes que movem cada fator")
    for r in readings:
        with st.expander(f"{r.label} ({r.score:+.2f})"):
            st.markdown("\n".join(f"- {h}" for h in r.top_headlines) or "_Sem notícias recentes._")

# ---------------------------------------------------------------- ação detalhada
with tab_stock:
    if forecasts:
        choice = st.selectbox("Ação", [f"{f.ticker} — {f.name}" for f in forecasts])
        f = next(x for x in forecasts if choice.startswith(x.ticker))
        a, b, c, d = st.columns(4)
        a.metric("Recomendação", f.recommendation)
        b.metric("Retorno esperado", f"{f.expected_return:+.2%}", f"{horizon} pregões", delta_color="off")
        c.metric("Probabilidade de alta", f"{f.prob_up:.0%}")
        d.metric("RSI (14)", f"{f.rsi:.0f}")

        close = prices[f.ticker].dropna().iloc[-120:]
        tf = market.technical_frame(prices[f.ticker].dropna()).iloc[-120:]
        future = pd.bdate_range(close.index[-1], periods=horizon + 1)
        fig = go.Figure()
        fig.add_scatter(x=close.index, y=close, name="Preço", line=dict(color="#222"))
        fig.add_scatter(x=tf.index, y=tf["ma20"], name="MM20", line=dict(color="#4e79a7", dash="dot"))
        fig.add_scatter(x=tf.index, y=tf["ma50"], name="MM50", line=dict(color="#f28e2b", dash="dot"))
        steps = [i / horizon for i in range(horizon + 1)]
        mid = [f.price * (1 + f.expected_return * s) for s in steps]
        hi = [f.price * (1 + f.expected_return * s + (f.range_high - f.expected_return) * s ** 0.5) for s in steps]
        lo = [f.price * (1 + f.expected_return * s + (f.range_low - f.expected_return) * s ** 0.5) for s in steps]
        fig.add_scatter(x=list(future) + list(future[::-1]), y=hi + lo[::-1], fill="toself", name="Faixa ±1σ", mode="lines",
                        fillcolor="rgba(76,175,80,0.18)", line=dict(width=0))
        fig.add_scatter(x=future, y=mid, name="Previsão", mode="lines", line=dict(color="#1a7f37", width=3))
        fig.update_layout(height=430, margin=dict(t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.markdown("**Componentes do score**")
            st.dataframe(pd.DataFrame({"Sinal": ["Técnico", "Notícias", "Político", "Ajuste IA", "Final"],
                                       "Valor": [f.tech_score, f.news_score, f.political_score, f.llm_adjust, f.composite]})
                         .style.format({"Valor": "{:+.2f}"}), hide_index=True, use_container_width=True)
            bt = f.backtest
            if bt.get("n", 0) >= 10:
                st.caption(f"Backtest do sinal técnico (1 ano, {horizon} pregões): acerto de direção "
                           f"{bt['hit_rate']:.0%} em {bt['n']} sinais. Notícias não entram no backtest "
                           "por falta de histórico.")
            st.caption(f"Volatilidade diária: {f.vol_daily:.2%} · stop sugerido R\\$ {f.stop:.2f} · alvo R\\$ {f.target:.2f}")
        with right:
            st.markdown("**Contribuição de cada fator político/macro**")
            contrib = pd.Series({config.FACTORS[k]["label"]: v for k, v in f.factor_contrib.items()}).sort_values()
            st.plotly_chart(go.Figure(go.Bar(x=contrib.values, y=contrib.index, orientation="h",
                                             marker_color=["#d1242f" if v < 0 else "#1a7f37" for v in contrib.values]))
                            .update_layout(height=280, margin=dict(t=5, b=5)), use_container_width=True)
        if f.rationale:
            st.info(f"🤖 **Claude:** {f.rationale}  \n**Riscos:** {llm_adj.get(f.ticker, {}).get('riscos', '')}")
        st.markdown("**Notícias recentes sobre a empresa**")
        for art in f.headlines:
            emoji = "🟢" if art.sentiment > 0.1 else "🔴" if art.sentiment < -0.1 else "⚪"
            link = f"[{art.title}]({art.link})" if art.link else art.title
            st.markdown(f"{emoji} {link} — _{art.source}, {art.published:%d/%m %H:%M}_")
        if not f.headlines:
            st.caption("Sem notícias específicas nos últimos dias.")

# ---------------------------------------------------------------- notícias
with tab_news:
    if articles:
        nd = pd.DataFrame([{"Data": a.published.strftime("%d/%m %H:%M"), "Fonte": a.source, "Manchete": a.title,
                            "Sentimento": a.sentiment, "Ações": ", ".join(a.tickers),
                            "Fatores": ", ".join(config.FACTORS[x]["label"] for x in a.factors), "Link": a.link}
                           for a in articles])
        q = st.text_input("Filtrar manchetes", "")
        if q:
            nd = nd[nd["Manchete"].str.contains(q, case=False, na=False)]
        st.dataframe(nd, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir"),
                                    "Sentimento": st.column_config.ProgressColumn("Sentimento", min_value=-1, max_value=1, format="%.2f")})

# ---------------------------------------------------------------- metodologia
with tab_method:
    st.markdown(f"""
### Como o score é calculado
1. **Técnico** — tendência (MM20 vs MM50), momento de 20 e 5 dias normalizado pela volatilidade
   e reversão em extremos do RSI(14). Escala −1 a +1.
2. **Notícias** — manchetes dos últimos 7 dias (Google Notícias + feeds de InfoMoney, Money Times,
   Valor e Investing). Cada manchete recebe um sentimento léxico em português; menções diretas à
   empresa pesam 1, notícias do setor pesam 0,3, com decaimento exponencial (meia-vida configurável)
   e encolhimento para zero quando há poucas notícias.
3. **Cenário político/macro** — sete fatores (risco fiscal, Selic, câmbio, intervenção em estatais,
   governabilidade/eleições, commodities e cenário externo) são lidos a partir das manchetes com
   regras direcionais (ex.: "dólar sobe" = câmbio piorando). O impacto em cada ação é a soma
   *exposição setorial × score do fator*; estatais têm sensibilidade extra a interferência política.
4. **IA (opcional)** — Claude lê as manchetes (e pode pesquisar na web), revisa os fatores e propõe um
   ajuste por ação com justificativa. A leitura da IA entra com 50% no cenário e 30% no score final.

**Score final** = média ponderada dos sinais (pesos na barra lateral).
**Retorno esperado** = score × 0,35 × σ(horizonte), onde σ é a volatilidade de 20 dias. O fator 0,35
é deliberadamente conservador: sinais de curto prazo explicam pouco da variação dos preços.
A **faixa provável** é ±1σ e a **probabilidade de alta** assume distribuição normal.

| Score | Classificação |
|---|---|
| ≥ 0,35 | Compra forte |
| 0,15 a 0,35 | Compra |
| −0,15 a 0,15 | Neutro |
| −0,35 a −0,15 | Cautela |
| ≤ −0,35 | Evitar / Venda |

### Limitações
- Sentimento léxico erra ironia, contexto e manchetes ambíguas; a IA reduz, mas não elimina, esse erro.
- As exposições setoriais são heurísticas (edite `radar/config.py`).
- Não há backtest do componente de notícias. Rentabilidade passada não garante resultados futuros.
- Cotações do Yahoo Finance podem ter atraso de ~15 minutos.
""")
