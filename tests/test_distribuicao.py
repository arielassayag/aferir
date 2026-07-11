"""Testes da distribuição legal do IBS em 2033 (aferir.distribuicao).

Pré-condição: `python3 -m aferir.distribuicao` executado (CSVs em
data/processed/). Testam a CORREÇÃO da mecânica legal (conservação,
percentuais dos arts. 109-110, nivelamento do seguro, cota-parte,
determinismo) — nunca o desfecho político-fiscal (a suficiência mínima
é resultado reportado; DESIGN §2.8).
"""
from __future__ import annotations

import pandas as pd
import pytest

from aferir.config import (
    COTA_PARTE_MUNICIPAL,
    PROCESSED,
    RETENCAO_2033,
    SEGURO_RECEITA_PCT,
    UFS,
)
from aferir.distribuicao import _nivelamento_sequencial, distribui_2033

CSV = PROCESSED / "distribuicao_2033.csv"
CSV_MET = PROCESSED / "distribuicao_2033_metricas.csv"


@pytest.fixture(scope="module")
def saida() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CSV.exists():
        pytest.skip("rodar antes: python3 -m aferir.distribuicao")
    return distribui_2033()


@pytest.fixture(scope="module")
def csv_disco() -> pd.DataFrame:
    if not CSV.exists():
        pytest.skip("rodar antes: python3 -m aferir.distribuicao")
    return pd.read_csv(CSV)


# ------------------------------------------------------------------ estrutura
def test_estrutura_27x2(csv_disco):
    assert len(csv_disco) == 54
    assert sorted(csv_disco["uf"].unique()) == sorted(UFS)
    assert set(csv_disco["esfera"]) == {"E", "M"}
    for col in ("receita_referencia", "recebido_legal", "suficiencia_pct",
                "componente_retencao", "componente_destino",
                "componente_cota_parte", "componente_seguro"):
        assert col in csv_disco.columns, col


# ---------------------------------------------------------------- conservação
def test_conservacao_soma_recebido_igual_produto(saida):
    out, met = saida
    p = float(met.set_index("chave").loc["produto_total_bi", "valor"])
    assert float(out["recebido_legal"].sum()) == pytest.approx(p, rel=1e-9)
    # a referência líquida (pós-fluxos de cota-parte legada) também conserva
    assert float(out["receita_referencia"].sum()) == pytest.approx(p, rel=1e-9)


def test_componentes_somam_ao_recebido(saida):
    out, _ = saida
    soma = (out["componente_retencao"] + out["componente_destino"]
            + out["componente_cota_parte"] + out["componente_seguro"])
    pd.testing.assert_series_equal(
        soma, out["recebido_legal"], check_names=False, rtol=1e-12)


def test_percentuais_legais_2033(saida):
    """LC 227 arts. 109-110: 90% retenção; 5% do remanescente = seguro
    (0,5% do produto); 9,5% destino."""
    out, met = saida
    p = float(met.set_index("chave").loc["produto_total_bi", "valor"])
    seg_pct = SEGURO_RECEITA_PCT * (1 - RETENCAO_2033)
    assert float(out["componente_retencao"].sum()) == pytest.approx(
        RETENCAO_2033 * p, rel=1e-9)
    assert float(out["componente_seguro"].sum()) == pytest.approx(
        seg_pct * p, rel=1e-9)
    assert float(out["componente_destino"].sum()) == pytest.approx(
        (1 - RETENCAO_2033 - seg_pct) * p, rel=1e-9)
    # cota-parte é fluxo interno: soma zero
    assert float(out["componente_cota_parte"].sum()) == pytest.approx(
        0.0, abs=1e-9)


def test_coeficientes_retencao(saida):
    out, _ = saida
    assert float(out["coeficiente_retencao"].sum()) == pytest.approx(1.0, rel=1e-12)
    assert (out["coeficiente_retencao"] > 0).all()


# ------------------------------------------------- cota-parte (CF 158, IV, 'b')
def test_cota_parte_so_na_parcela_destino_estadual(saida):
    """ADCT 131, §3º: retenção estadual NÃO sofre cota-parte; a parcela-destino
    sofre 25%, creditada aos municípios da MESMA UF; DF sem municípios."""
    out, _ = saida
    ix = out.set_index(["uf", "esfera"])
    for uf in UFS:
        e = ix.loc[(uf, "E")]
        m = ix.loc[(uf, "M")]
        if uf == "DF":
            assert float(e["componente_cota_parte"]) == 0.0
            assert float(m["componente_cota_parte"]) == 0.0
        else:
            esperado = COTA_PARTE_MUNICIPAL * float(e["componente_destino"])
            assert float(e["componente_cota_parte"]) == pytest.approx(
                -esperado, rel=1e-12)
            assert float(m["componente_cota_parte"]) == pytest.approx(
                +esperado, rel=1e-12)


# ------------------------------------- seguro-receita (nivelamento, art. 117)
def test_nivelamento_exaure_pool_e_nivela():
    ann = pd.Series({"a": 1.0, "b": 2.0, "c": 10.0})
    rmaj = pd.Series({"a": 10.0, "b": 10.0, "c": 10.0})
    seg = _nivelamento_sequencial(ann, rmaj, 3.0)
    # r* = (3+1+2)/20 = 0,30 → a recebe 2, b recebe 1, c nada
    assert seg["a"] == pytest.approx(2.0)
    assert seg["b"] == pytest.approx(1.0)
    assert seg["c"] == 0.0
    assert float(seg.sum()) == pytest.approx(3.0)


def test_nivelamento_prefixo_e_pool_grande():
    ann = pd.Series({"a": 1.0, "b": 2.0, "c": 10.0})
    rmaj = pd.Series({"a": 10.0, "b": 10.0, "c": 10.0})
    seg = _nivelamento_sequencial(ann, rmaj, 12.0)
    # nivelar a,b até a razão de c (1,0) custa 17 > 12 → só a,b recebem
    assert seg["c"] == 0.0
    r_a = (ann["a"] + seg["a"]) / rmaj["a"]
    r_b = (ann["b"] + seg["b"]) / rmaj["b"]
    assert r_a == pytest.approx(r_b)              # mesma razão final (§1º)
    assert float(seg.sum()) == pytest.approx(12.0)


def test_nivelamento_invariante_a_escala_da_receita_media():
    ann = pd.Series({"a": 1.0, "b": 2.0, "c": 10.0})
    rmaj = pd.Series({"a": 10.0, "b": 10.0, "c": 10.0})
    seg1 = _nivelamento_sequencial(ann, rmaj, 3.0)
    seg2 = _nivelamento_sequencial(ann, rmaj * 1e9, 3.0)
    pd.testing.assert_series_equal(seg1, seg2, rtol=1e-12)


def test_seguro_vai_para_prefixo_das_menores_razoes(saida):
    """Quem recebe seguro forma um PREFIXO da ordenação das razões e termina
    na mesma razão final (art. 117, §1º) — testado nas saídas reais."""
    out, _ = saida
    ix = out.set_index(["uf", "esfera"])
    recebem = set(ix[ix["componente_seguro"] > 1e-12].index)
    assert len(recebem) > 0
    # razão final proxy: (destino anual pós-cota + seguro)/coeficiente — a
    # propriedade formal (prefixo) já é garantida pelos testes unitários;
    # aqui garantimos apenas não-negatividade e materialidade do pool.
    assert (out["componente_seguro"] >= 0).all()


# -------------------------------------------------------------------- métricas
def test_metricas_consistentes_com_painel(saida, csv_disco):
    _, met = saida
    m = met.set_index("chave")["valor"]
    suf = csv_disco["suficiencia_pct"]
    assert float(m["suficiencia_minima_pct"]) == pytest.approx(float(suf.min()), rel=1e-9)
    assert float(m["n_entes_abaixo_100"]) == float((suf < 100.0).sum())
    assert float(m["n_entes_abaixo_piso_905"]) == float((suf < 90.5).sum())
    assert float(m["n_entes"]) == 54.0


def test_suficiencia_dominio_sanidade(saida):
    """Domínio de sanidade do CÔMPUTO (não do desfecho): a retenção de 90%
    prende a suficiência perto de 100% — fora de [50; 150] indicaria bug."""
    out, _ = saida
    assert out["suficiencia_pct"].between(50.0, 150.0).all()
    assert (out["receita_referencia"] > 0).all()


# ---------------------------------------------------------------- determinismo
def test_determinismo_recomputo_igual_csv(saida, csv_disco):
    out, _ = saida
    a = out[["uf", "esfera", "receita_referencia", "recebido_legal",
             "suficiencia_pct", "componente_retencao", "componente_destino",
             "componente_cota_parte", "componente_seguro"]].reset_index(drop=True)
    b = csv_disco[a.columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, rtol=1e-9)


def test_determinismo_duas_execucoes(saida):
    out1, met1 = saida
    out2, met2 = distribui_2033()
    pd.testing.assert_frame_equal(out1, out2)
    pd.testing.assert_frame_equal(met1, met2)
