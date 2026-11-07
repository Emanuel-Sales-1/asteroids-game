from datetime import datetime, timezone

from radar import config, demo, politics
from radar.model import Weights, build_forecasts, classify
from radar.news import Article, tag_articles
from radar.sentiment import score_text


def art(title, days=0):
    return Article(title=title, summary="", link="", source="t", published=datetime.now(timezone.utc))


def test_sentiment_polarity():
    assert score_text("Vale tem lucro recorde e ações disparam") > 0.3
    assert score_text("Magazine Luiza tem prejuízo e ações despencam") < -0.3
    assert score_text("Empresa divulga calendário de eventos") == 0


def test_negation_flips():
    assert score_text("Governo descarta interferência na Petrobras") > score_text("Governo prevê interferência na Petrobras")


def test_ticker_and_factor_tagging():
    [a] = tag_articles([art("Petrobras sobe com alta do petróleo; Copom mantém Selic")])
    assert "PETR4" in a.tickers
    assert {"juros_selic", "commodities"} <= set(a.factors)
    assert tag_articles([art("Vale anuncia recompra")])[0].tickers == ["VALE3"]
    assert "VALE3" not in tag_articles([art("Vale a pena investir em renda fixa?")])[0].tickers
    assert "VALE3" not in tag_articles([art("o que vale mais: CDB ou LCI")])[0].tickers


def test_directional_factor():
    arts = tag_articles([art("Dólar dispara com incerteza fiscal"), art("Dólar sobe e fecha em alta"),
                         art("Copom sinaliza alta da Selic"), art("Juros sobem com inflação acima do esperado")])
    sc = politics.read_scenario(arts)
    assert sc["cambio"].score > 0
    assert sc["juros_selic"].score > 0


def test_rate_hike_hurts_retail_more_than_exporters():
    sc = politics.read_scenario(tag_articles([art("Copom eleva juros"), art("Alta da Selic surpreende"),
                                              art("Juros sobem de novo"), art("Aumento de juros pressiona")]))
    by = {s.ticker: s for s in config.UNIVERSE}
    retail, _ = politics.political_impact(by["MGLU3"], sc)
    exporter, _ = politics.political_impact(by["SUZB3"], sc)
    assert retail < exporter


def test_end_to_end_demo():
    fc = build_forecasts(demo.demo_prices(), demo.demo_articles(),
                         politics.read_scenario(demo.demo_articles()), Weights())
    assert len(fc) == len(config.UNIVERSE)
    assert all(-1 <= f.composite <= 1 and f.range_low < f.expected_return < f.range_high for f in fc)
    assert fc == sorted(fc, key=lambda f: f.composite, reverse=True)


def test_classify():
    assert classify(0.5) == "Compra forte" and classify(0) == "Neutro" and classify(-0.5) == "Evitar / Venda"


def test_foreign_politics_not_counted_as_brazilian_governability():
    [us] = tag_articles([art("Vance culpa guerra no Irã por derrota republicana e busca espaço para 2028")])
    [br] = tag_articles([art("Governo Lula sofre derrota no Congresso em votação de MP")])
    assert "governabilidade" not in us.factors
    assert "governabilidade" in br.factors
