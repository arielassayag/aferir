"""Contratos do erro de classificação POF×LC 214 (E2 — aferir.classificacao
e o sorteio conjunto de aferir.uncertainty).

Exigências: artefatos vendorados byte-idênticos (sha256 pinados — amostra
estratificada do v1 e amostra dirigida pelo peso R6); contagens de
divergência goldens (fixadas por amostra × matriz v5); κ reproduz o v1 na
amostra original e é pinado por amostra; cobertura da amostra combinada
≥ 50% da despesa da base de π^p; ordenação π^p_env_min ≤ central ≤
π^p_env_max (UF a UF e BR); determinismo do sorteio de classificação;
assinatura antiga de policy_gap_por_uf intacta.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from aferir import config
from aferir.base import itens_combustiveis
from aferir.classificacao import (DUPLA_CSV, DUPLA_DIRIGIDA_CSV, NIVEIS_M,
                                  carrega_amostras, carrega_dupla_codificacao,
                                  carrega_dupla_codificacao_dirigida,
                                  divergencias, envelope_pi, kappas,
                                  matriz_envelope, pi_p_central_nacional,
                                  tabela_divergencias)
from aferir.gaps import carrega_matriz, policy_gap_por_uf
from aferir.uncertainty import (pi_replicas_com_classificacao,
                                sorteio_classificacao)

SHA256_DUPLA = "031042197145fea1bf5c563c3415b12041945399e20fd494e251de299896860a"
SHA256_DIRIGIDA = ("71fcf4b7fec68e094e899e04a2e1d8ac"
                   "63deb8fe646f8113aa597ecc05c59bbc")


@pytest.fixture(scope="module")
def despesa() -> pd.DataFrame:
    d = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    d["codigo_pof"] = d["codigo_pof"].astype(str)
    return d


@pytest.fixture(scope="module")
def em_campo(despesa) -> pd.DataFrame:
    return despesa[~despesa["codigo_pof"].isin(itens_combustiveis(despesa))]


# ------------------------------------------------------------ artefato
def test_sha256_artefato_vendorado():
    h = hashlib.sha256(DUPLA_CSV.read_bytes()).hexdigest()
    assert h == SHA256_DUPLA, "dupla codificação difere do artefato v1"


def test_sha256_artefato_dirigido():
    h = hashlib.sha256(DUPLA_DIRIGIDA_CSV.read_bytes()).hexdigest()
    assert h == SHA256_DIRIGIDA, "amostra dirigida difere do artefato R6"


def test_amostra_bem_formada():
    a = carrega_dupla_codificacao()
    assert len(a) == 470
    assert a["avaliador"].eq("LLM_cego_2026_07").all()
    assert set(a["m_avaliador2"]) <= {0.0, 0.30, 0.40, 0.60, 0.70, 1.0}


def test_amostra_dirigida_bem_formada():
    d = carrega_dupla_codificacao_dirigida()
    assert len(d) == 46
    assert d["avaliador"].eq("LLM_cego_2026_07").all()
    assert d["metodo"].eq("dirigida_peso_top50").all()
    assert d["data"].eq("2026-07-13").all()
    assert set(d["m_avaliador2"]) <= set(NIVEIS_M)
    assert d.loc[d["flag_avaliador2"].eq("F"), "m_avaliador2"].eq(1.0).all()
    # itens da base de π^p por construção: em campo na matriz central
    m = carrega_matriz().set_index("codigo_pof")
    assert m.loc[d["codigo_pof"], "flag"].ne("F").all()
    assert m.loc[d["codigo_pof"], "m_i"].notna().all()


def test_amostras_combinadas_dedup_original_prevalece():
    o = carrega_amostras("original")
    d = carrega_amostras("dirigida")
    c = carrega_amostras("combinada")
    assert len(c) == 516 == len(o) + len(d)          # zero interseção
    assert not c["codigo_pof"].duplicated().any()
    assert set(o["codigo_pof"]).isdisjoint(set(d["codigo_pof"]))
    assert c["amostra"].value_counts().to_dict() == {
        "original": 470, "dirigida_peso_top50": 46}
    assert list(c["codigo_pof"]) == sorted(c["codigo_pof"])


def test_selecao_dirigida_top50_deterministica(despesa):
    """A amostra dirigida = itens da base de π^p ordenados por despesa
    nacional decrescente (desempate codigo_pof) até 50% do denominador,
    MENOS os já presentes na amostra original."""
    d_nac = despesa.groupby("codigo_pof")["despesa_anual_rs"].sum()
    m = carrega_matriz()
    comb = itens_combustiveis(despesa)
    cod_base = (set(m.loc[m["flag"].ne("F") & m["m_i"].notna(),
                          "codigo_pof"]) - comb)
    base = (d_nac[d_nac.index.isin(cod_base)].reset_index()
            .sort_values(["despesa_anual_rs", "codigo_pof"],
                         ascending=[False, True]).reset_index(drop=True))
    acum = base["despesa_anual_rs"].cumsum() / base["despesa_anual_rs"].sum()
    top = set(base.loc[:(acum >= 0.5).idxmax(), "codigo_pof"])
    esperados = top - set(carrega_dupla_codificacao()["codigo_pof"])
    assert set(carrega_dupla_codificacao_dirigida()["codigo_pof"]) == esperados


# --------------------------------------------------------- divergências
def test_contagens_divergencia_goldens():
    div = divergencias()                              # combinada (default)
    tipos = div["tipo_divergencia"].value_counts().to_dict()
    assert len(div) == 118
    assert tipos.get("m_diverge", 0) == 109
    assert tipos.get("campo_diverge", 0) == 9
    assert tipos.get("ambos", 0) == 0
    assert not div["codigo_pof"].duplicated().any()
    por_amostra = div["amostra"].value_counts().to_dict()
    assert por_amostra == {"original": 110, "dirigida_peso_top50": 8}

    o = divergencias("original")                      # goldens v1 intactos
    t_o = o["tipo_divergencia"].value_counts().to_dict()
    assert len(o) == 110 and t_o.get("m_diverge", 0) == 107
    d = divergencias("dirigida")
    t_d = d["tipo_divergencia"].value_counts().to_dict()
    assert len(d) == 8
    assert t_d.get("m_diverge", 0) == 2
    assert t_d.get("campo_diverge", 0) == 6


# ------------------------------------------------------------------ kappa
def test_kappas_reproduzem_v1_e_goldens_r6():
    o = kappas("original")                 # reproduz byte a byte o v1 (13b)
    assert o["n"] == 470 and o["n_em_campo_ambos"] == 448
    assert o["kappa_m_raw_ex_F"] == pytest.approx(0.637137, abs=1e-6)
    assert o["kappa_m_linear_ex_F"] == pytest.approx(0.670573, abs=1e-6)
    assert o["kappa_F_binario"] == pytest.approx(0.923494, abs=1e-6)

    d = kappas("dirigida")
    assert d["n"] == 46 and d["n_em_campo_ambos"] == 40
    assert d["kappa_m_raw_ex_F"] == pytest.approx(0.903846, abs=1e-6)
    # κ_F degenerado por construção (matriz central sem F na base de π^p):
    assert d["kappa_F_binario"] == 0.0

    c = kappas("combinada")
    assert c["n"] == 516 and c["n_em_campo_ambos"] == 488
    assert c["kappa_m_raw_ex_F"] == pytest.approx(0.658118, abs=1e-6)
    assert c["kappa_m_linear_ex_F"] == pytest.approx(0.687912, abs=1e-6)


# -------------------------------------------------------------- cobertura
def test_cobertura_combinada_da_base_pi(despesa):
    _, ag = tabela_divergencias(despesa)
    assert ag["n_amostra"] == 516
    assert ag["cobertura_amostra_base_pi"] >= 0.5          # exigência R6
    assert ag["cobertura_amostra_base_pi"] == pytest.approx(0.5322, abs=5e-4)
    assert ag["cobertura_amostra_base_pi_original"] == pytest.approx(
        0.1082, abs=5e-4)                                  # era a cota 10,8%
    assert ag["kappas"]["combinada"]["kappa_m_raw_ex_F"] == pytest.approx(
        0.658118, abs=1e-6)


def test_envelope_altera_so_divergentes(em_campo):
    pi_ref = pi_p_central_nacional(em_campo)
    central = carrega_matriz().set_index("codigo_pof")
    alt = matriz_envelope("pi_alto", pi_ref).set_index("codigo_pof")
    fora = central.index.difference(divergencias()["codigo_pof"])
    pd.testing.assert_frame_equal(central.loc[fora], alt.loc[fora])


# ------------------------------------------------------------ envelopes
def test_ordenacao_envelopes(em_campo):
    env = envelope_pi(em_campo)
    assert set(env["uf"]) == set(config.UFS) | {"BR"}
    assert (env["pi_p_envelope_aliquotas_min"]
            <= env["pi_p_central"] + 1e-12).all()
    assert (env["pi_p_central"]
            <= env["pi_p_envelope_aliquotas_max"] + 1e-12).all()
    br = env.set_index("uf").loc["BR"]
    # envelopes movem π^p (não degeneram) mas dentro de ordem de grandeza sã
    # (limite superior alargado após a amostra dirigida R6: os itens pesados
    # de aquisição de imóveis divergem F×não-F e movem o envelope máximo)
    assert 0.0 < br["delta_aliquotas_max_pp"] < 3.0
    assert -2.0 < br["delta_aliquotas_min_pp"] < 0.0


# ------------------------------------------------- sorteio determinístico
def test_sorteio_deterministico():
    itens = sorted(divergencias()["codigo_pof"])
    z1 = sorteio_classificacao(itens, 40, config.SEED)
    z2 = sorteio_classificacao(itens, 40, config.SEED)
    assert np.array_equal(z1, z2)
    assert z1.shape == (40, len(itens))
    assert set(np.unique(z1)) <= {0.0, 1.0}
    z3 = sorteio_classificacao(itens, 40, config.SEED + 1)
    assert not np.array_equal(z1, z3)


def _cache_sintetico():
    upa = pd.DataFrame({
        "estrato_pof": [1, 1, 2, 2],
        "cod_upa": ["u1", "u2", "u3", "u4"],
        "uf": ["AC", "AC", "SP", "SP"],
        "num_pi": [10.0, 20.0, 30.0, 40.0],
        "den_pi": [100.0, 100.0, 100.0, 100.0],
    })
    deltas = pd.DataFrame({
        "cod_upa": ["u1", "u3"],
        "codigo_pof": ["900101", "900101"],
        "d_num": [5.0, -5.0],
        "d_den": [0.0, 0.0],
    })
    return {"upa": upa}, deltas


@pytest.mark.filterwarnings("ignore:invalid value encountered in divide")
def test_pi_replicas_deterministicas_e_z0_reproduz_base():
    # cache sintético cobre só AC/SP — as demais UFs dividem 0/0 (NaN esperado)
    cache, deltas = _cache_sintetico()
    itens = ["900101"]
    B = 8
    W = np.ones((B, 4))
    Z = sorteio_classificacao(itens, B, config.SEED)
    r1 = pi_replicas_com_classificacao(cache, W, deltas, Z, itens)
    r2 = pi_replicas_com_classificacao(cache, W, deltas, Z, itens)
    assert np.array_equal(r1["pi_nac"], r2["pi_nac"])          # mesma seed
    assert np.array_equal(r1["pi_uf"], r2["pi_uf"], equal_nan=True)

    z0 = pi_replicas_com_classificacao(cache, W, deltas,
                                       np.zeros((B, 1)), itens)
    assert np.allclose(z0["pi_nac"], 100.0 / 400.0)            # base central
    z1 = pi_replicas_com_classificacao(cache, W, deltas,
                                       np.ones((B, 1)), itens)
    assert np.allclose(z1["pi_nac"], 100.0 / 400.0)            # Δnum soma 0
    pos = sorted(config.UFS).index("AC")
    assert np.allclose(z1["pi_uf"][:, pos], (30.0 + 5.0) / 200.0)


# ----------------------------------------------------- regressão gaps.py
def test_policy_gap_assinatura_antiga_intacta(em_campo):
    from aferir.provenance import MANIFEST

    pequena = em_campo[em_campo["uf"].isin(["AC", "SE"])]
    # a subamostra registraria pi_p_nacional divergente do registro do teste
    # de envelopes (mesmo processo) — limpa a chave antes (só neste teste)
    MANIFEST.nums.pop("pi_p_nacional", None)
    antiga = policy_gap_por_uf(pequena)
    MANIFEST.nums.pop("pi_p_nacional", None)
    explicita = policy_gap_por_uf(pequena, matriz=carrega_matriz())
    pd.testing.assert_frame_equal(antiga, explicita)
    com_lam = policy_gap_por_uf(pequena, 0.5)                  # posicional
    assert np.allclose(com_lam["pi_p"], 0.5 * antiga["pi_p"])  # identidade λ
