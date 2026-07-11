"""Item A1.2 — QA do confronto CONFAZ × RREO (aferir.qa_confaz).

Estrutural: 27 UFs × 2 anos; contagem de meses declarada (inclusive
pendências da vintage de 23/06/2026); desvios finitos; linhas de resumo
(mediana e máximo por ano) presentes; determinismo byte a byte; goldens
medidos; avaliação A2.5 sem artefato (decisão documentada no módulo).
"""
import math

import pandas as pd
import pytest

from aferir import config, qa_confaz

ANOS = sorted(config.JANELA_RECEITA)          # [2024, 2025]
PONTES = {"sem_ajuste", "confaz+DAIC", "rreo-FECP", "confaz+DAIC e rreo-FECP"}


@pytest.fixture(scope="module")
def qa() -> pd.DataFrame:
    return qa_confaz.qa_confaz_vs_rreo()


@pytest.fixture(scope="module")
def ufano(qa) -> pd.DataFrame:
    return qa[qa["estatistica"] == "uf_ano"]


# ------------------------------------------------------------- estrutura
def test_27_ufs_x_2_anos(ufano):
    assert len(ufano) == 27 * 2
    assert sorted(ufano["uf"].unique()) == config.UFS
    assert sorted(ufano["ano"].unique()) == ANOS
    assert not ufano.duplicated(subset=["uf", "ano"]).any()


def test_meses_de_2026_fora_da_janela(qa):
    assert set(qa["ano"]) == set(ANOS)


def test_contagem_de_meses_declarada(ufano):
    assert (ufano["meses_confaz"] == 12).all()
    assert (ufano["meses_pendentes"] >= 0).all()
    # pendências conhecidas da vintage 23/06/2026 (cabeçalho 'com pendencias')
    sc25 = ufano[(ufano["uf"] == "SC") & (ufano["ano"] == 2025)].iloc[0]
    assert sc25["meses_pendentes"] == 3
    assert sc25["meses_pendentes_lista"] == "1+7+10"
    sc24 = ufano[(ufano["uf"] == "SC") & (ufano["ano"] == 2024)].iloc[0]
    assert sc24["meses_pendentes"] == 1


def test_desvios_finitos_e_pontes_rotuladas(ufano):
    cols = ["desvio_pct", "desvio_mais_daic_pct", "desvio_ex_fecp_pct",
            "desvio_mais_daic_ex_fecp_pct", "desvio_pos_ponte_pct"]
    for c in cols:
        assert ufano[c].notna().all() and ufano[c].apply(math.isfinite).all()
    assert set(ufano["ponte_melhor"]) <= PONTES
    # a melhor ponte nunca piora o desvio sem ajuste
    assert (ufano["desvio_pos_ponte_pct"].abs()
            <= ufano["desvio_pct"].abs() + 1e-12).all()


def test_proveniencia_formula_e_fonte(qa):
    assert {"formula", "fonte"} <= set(qa.columns)
    assert qa["formula"].str.len().gt(0).all()
    assert qa["fonte"].str.contains("CONFAZ").all()
    assert qa["fonte"].str.contains("RREO").all()


def test_investigacao_para_desvios_acima_de_1pct(ufano):
    acima = ufano[ufano["desvio_pct"].abs() > qa_confaz.LIMIAR_INVESTIGA_PCT]
    assert acima["investigacao"].str.len().gt(0).all()
    dentro = ufano[ufano["desvio_pct"].abs() <= qa_confaz.LIMIAR_INVESTIGA_PCT]
    assert dentro["investigacao"].fillna("").str.len().eq(0).all()


# ------------------------------------------------------------- resumo
def test_resumo_mediana_e_maximo_por_ano(qa):
    resumo = qa[qa["estatistica"] != "uf_ano"]
    assert len(resumo) == 2 * len(ANOS)
    for ano in ANOS:
        sel = resumo[resumo["ano"] == ano]
        assert set(sel["estatistica"]) == {"mediana_ano", "maximo_ano"}
        assert (sel["uf"] == "BR").all()
        assert sel["desvio_pct"].apply(math.isfinite).all()


def test_goldens_medidos(qa, ufano):
    """Goldens da vintage 23/06/2026 × RREO (regressão; rel 1e-6)."""
    resumo = qa[qa["estatistica"] != "uf_ano"].set_index(["ano", "estatistica"])
    esperado = {
        (2024, "mediana_ano"): 0.4642284,
        (2024, "maximo_ano"): 14.3569315,   # BA 2024 (subdeclaração no boletim)
        (2025, "mediana_ano"): 0.3585849,
        (2025, "maximo_ano"): 24.4764592,   # SC 2025 (3 meses pendentes)
    }
    for chave, valor in esperado.items():
        assert math.isclose(resumo.loc[chave, "desvio_pct"], valor,
                            rel_tol=1e-6)
    # pontes conceituais medidas: RJ fecha por FECP; AC 2024 fecha por DAIC
    rj24 = ufano[(ufano["uf"] == "RJ") & (ufano["ano"] == 2024)].iloc[0]
    assert abs(rj24["desvio_pct"]) > 10
    assert abs(rj24["desvio_ex_fecp_pct"]) < 0.1
    ac24 = ufano[(ufano["uf"] == "AC") & (ufano["ano"] == 2024)].iloc[0]
    assert abs(ac24["desvio_mais_daic_pct"]) < 1e-6


# ------------------------------------------------------------- determinismo
def test_determinismo_byte_identico(qa):
    antes = qa_confaz.QA_CSV.read_bytes()
    qa_confaz.qa_confaz_vs_rreo()
    assert qa_confaz.QA_CSV.read_bytes() == antes


# ------------------------------------------------------------- A2.5
def test_a25_sem_artefato_de_reconciliacao():
    """Decisão documentada: a ponte ad rem × CNAE 19 é indefensável por UF
    (CNAE do recolhedor ≠ ICMS do produto) — o CSV NÃO deve existir."""
    assert not (config.PROCESSED / "qa_adrem_vs_confaz.csv").exists()


def test_a25_diagnostico_mede_a_indefensabilidade():
    a25 = qa_confaz.avaliacao_adrem_cnae()
    assert len(a25) == 27 * 2 + 2                 # UF-anos + agregados BR
    assert a25["razao_adrem_div19"].apply(math.isfinite).all()
    br = a25[a25["uf"] == "BR"].set_index("ano")["razao_adrem_div19"]
    for ano in ANOS:                              # nacional: mesma ordem de
        assert 1.0 < br.loc[ano] < 2.0            # grandeza (≈1,6×), mas...
    por_uf = a25[a25["uf"] != "BR"]["razao_adrem_div19"]
    assert por_uf.max() / por_uf.min() > 20       # ...dispersão 0,8×-58× por UF
