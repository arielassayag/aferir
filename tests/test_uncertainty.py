"""Contratos da banda de incerteza amostral POF (aferir.uncertainty).

Exigências (DESIGN §2.7 + missão onda 3):
 - determinismo: mesma seed ⇒ mesmos percentis (byte-idênticos);
 - réplica de pesos unitários reproduz o cenário central EXATAMENTE
   (o bootstrap perturba, não redefine, o pipeline);
 - p50 da soma ≈ central (±0,1 p.p.);
 - largura amostral < largura do corredor γ (esperado; a falha seria um
   ACHADO a reportar, não um bug — por isso a mensagem do assert o diz).

Os testes leem banda_incerteza.csv se existir (B=500 do main); na ausência,
rodam B=200 declarado. O cache UPA×estrato é construído uma vez (~4 min).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aferir import config
from aferir.pipeline import monta_insumos
from aferir.uncertainty import (
    BANDA_CSV,
    carrega_cache,
    estatisticas_replicas,
    pesos_rao_wu,
    propaga_taus,
    roda_bootstrap,
)

COMPONENTES = ["pi_p_nacional", "f_low_nacional", "tau_CBS_pp", "tau_E_pp",
               "tau_M_pp", "soma_pp"]


@pytest.fixture(scope="session")
def cache():
    return carrega_cache()


@pytest.fixture(scope="session")
def ins():
    return monta_insumos()


@pytest.fixture(scope="session")
def central() -> pd.Series:
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")]
    assert len(c) == 1
    return c.iloc[0]


@pytest.fixture(scope="session")
def banda(cache, ins) -> pd.DataFrame:
    if BANDA_CSV.exists():
        return pd.read_csv(BANDA_CSV)
    b, _ = roda_bootstrap(B=200, seed=config.SEED, ins=ins, cache=cache)
    return b


# ------------------------------------------------------ pesos: Rao-Wu
def test_pesos_rao_wu_estrutura(cache):
    W = pesos_rao_wu(cache["upa"], B=25, seed=config.SEED)
    assert W.shape == (25, len(cache["upa"]))
    assert (W >= 0).all()
    # dentro de cada estrato com n_h>=2, Σ pesos = n_h (reescalonamento
    # n_h/(n_h-1) × (n_h-1) sorteios); com n_h=1, peso fixo = 1
    upa = cache["upa"]
    soma_estrato = pd.DataFrame(W.T, index=upa["estrato_pof"]) \
        .groupby(level=0).sum()
    n_h = upa.groupby("estrato_pof").size()
    esperado = np.tile(n_h.to_numpy()[:, None], (1, 25))
    assert np.allclose(soma_estrato.to_numpy(), esperado, atol=1e-9)


# ------------------------------------- réplica unitária reproduz o central
def test_w1_reproduz_central(cache, ins, central):
    W1 = np.ones((1, len(cache["upa"])))
    est = estatisticas_replicas(cache, W1)
    b = ins["b"]
    assert np.allclose(est["pi_uf"][0], b["pi_p"].to_numpy(), rtol=1e-9)
    assert np.allclose(est["f_low_uf"][0], b["f_low"].to_numpy(), rtol=1e-9)
    taus = propaga_taus(ins, est["pi_uf"], est["f_low_uf"])
    assert abs(taus["tau_CBS_pp"].iloc[0] - central["tau_CBS_pp"]) < 1e-6
    assert abs(taus["tau_E_pp"].iloc[0] - central["tau_E_pp"]) < 1e-6
    assert abs(taus["tau_M_pp"].iloc[0] - central["tau_M_pp"]) < 1e-6
    assert abs(taus["soma_pp"].iloc[0] - central["soma_pp"]) < 1e-6


# ------------------------------------------------------------ determinismo
def test_determinismo_mesma_seed(cache, ins):
    b1, r1 = roda_bootstrap(B=40, seed=config.SEED, ins=ins, cache=cache)
    b2, r2 = roda_bootstrap(B=40, seed=config.SEED, ins=ins, cache=cache)
    pd.testing.assert_frame_equal(b1, b2, check_exact=True)
    pd.testing.assert_frame_equal(r1, r2, check_exact=True)


def test_seed_diferente_perturba(cache, ins):
    b1, _ = roda_bootstrap(B=40, seed=config.SEED, ins=ins, cache=cache)
    b2, _ = roda_bootstrap(B=40, seed=config.SEED + 1, ins=ins, cache=cache)
    assert not np.allclose(
        b1.set_index("componente")["p50"].to_numpy(),
        b2.set_index("componente")["p50"].to_numpy())


# ------------------------------------------------------------ contrato CSV
def test_contrato_banda(banda):
    assert list(banda.columns) == ["componente", "p5", "p50", "p95",
                                   "largura", "formula", "fonte"]
    assert list(banda["componente"]) == COMPONENTES
    assert (banda["p5"] <= banda["p50"]).all()
    assert (banda["p50"] <= banda["p95"]).all()
    assert np.allclose(banda["largura"], banda["p95"] - banda["p5"])
    assert (banda["largura"] > 0).all()
    assert banda["formula"].notna().all() and banda["fonte"].notna().all()
    # toda banda declara o que propaga (correção E2 do v1)
    assert banda.loc[banda.componente == "soma_pp", "fonte"] \
        .str.contains("PROPAGA").all()


# --------------------------------------------------- p50 ≈ central (0,1 pp)
def test_p50_proximo_do_central(banda, central):
    s = banda.set_index("componente")
    assert abs(s.at["soma_pp", "p50"] - central["soma_pp"]) < 0.1
    assert abs(s.at["tau_CBS_pp", "p50"] - central["tau_CBS_pp"]) < 0.1
    assert abs(s.at["tau_E_pp", "p50"] - central["tau_E_pp"]) < 0.1
    assert abs(s.at["tau_M_pp", "p50"] - central["tau_M_pp"]) < 0.1


# ------------------------------------------- amostral < corredor γ (achado)
def test_largura_amostral_menor_que_corredor_gamma(banda):
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    cor = nac[(nac.psi == 0.0) & (nac.modo_redutor == "iso_carga")] \
        .set_index("cenario_gamma")["soma_pp"]
    largura_gamma = float(cor["conservador"] - cor["factivel"])
    largura_amostral = float(
        banda.set_index("componente").at["soma_pp", "largura"])
    assert largura_amostral < largura_gamma, (
        f"ACHADO (não bug): banda amostral POF ({largura_amostral:.2f} p.p.) "
        f">= corredor γ ({largura_gamma:.2f} p.p.) — reportar no artigo")
