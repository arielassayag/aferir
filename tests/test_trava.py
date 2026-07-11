"""Trava do art. 475, §§10-11: Σ(λ*)=26,5 ± 1e-4; λ* monotônico em γ;
determinismo; identidades estruturais (π^p linear em λ; custo iso-receita)."""
import math

import pandas as pd
import pytest

from aferir import config, pipeline, trava
from aferir.base import itens_combustiveis
from aferir.gaps import policy_gap_por_uf


@pytest.fixture(scope="module")
def grade():
    """λ* para γ ∈ {10; 12,5; 15}% (bisseção completa — reusada nos testes)."""
    return trava.resolve_grade()


def test_soma_no_gatilho(grade):
    for rotulo, res in grade.items():
        soma_pp = res["r_star"]["sol"].soma * 100
        assert abs(soma_pp - 26.5) <= 1e-4, f"{rotulo}: Σ={soma_pp:.6f}"


def test_lambda_em_dominio_aberto(grade):
    # a trava VINCULA (λ*>0: Σ(0)>26,5) mas não exaure os favorecimentos (λ*<1)
    for rotulo, res in grade.items():
        assert 0.0 < res["lam"] < 1.0, rotulo


def test_lambda_monotonico_em_gamma(grade):
    lams = [grade[r]["lam"] for r in ("factivel", "central", "conservador")]
    assert lams[0] < lams[1] < lams[2], lams


def test_determinismo(grade):
    res2 = trava.resolve_lambda(config.GAP_CONFORMIDADE["central"])
    res1 = grade["central"]
    assert res2["lam"] == res1["lam"]                      # bit a bit
    s1, s2 = res1["r_star"]["sol"], res2["r_star"]["sol"]
    assert (s1.tau_U, s1.tau_E, s1.tau_M) == (s2.tau_U, s2.tau_E, s2.tau_M)
    assert trava.custo_beneficios_bi(res2) == trava.custo_beneficios_bi(res1)


def test_custo_identidade_iso_receita(grade):
    # τ_s(λ*)·[D_s(λ*)−D_s(0)] == [τ_s(0)−τ_s(λ*)]·D_s(0), esfera a esfera
    res = grade["central"]
    s_star, s_0 = res["r_star"]["sol"], res["r_0"]["sol"]
    taus_star = {"uniao": s_star.tau_U, "estadual": s_star.tau_E,
                 "municipal": s_star.tau_M}
    taus_0 = {"uniao": s_0.tau_U, "estadual": s_0.tau_E,
              "municipal": s_0.tau_M}
    for e in taus_star:
        d_star = float(res["r_star"]["d"][e].sum())
        d_0 = float(res["r_0"]["d"][e].sum())
        lhs = taus_star[e] * (d_star - d_0)
        rhs = (taus_0[e] - taus_star[e]) * d_0
        assert math.isclose(lhs, rhs, rel_tol=1e-9), e
    assert trava.custo_beneficios_bi(res) > 0.0


def test_pi_p_linear_em_lambda():
    # encolhimento uniforme ⇒ π^p(λ) = (1−λ)·π^p(0), UF a UF (identidade exata)
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    em_campo = despesa[~despesa["codigo_pof"].isin(itens_combustiveis(despesa))]
    lam = 0.37
    pi0 = policy_gap_por_uf(em_campo).set_index("uf")["pi_p"]
    pil = policy_gap_por_uf(em_campo, lam=lam).set_index("uf")["pi_p"]
    assert float((pil - (1 - lam) * pi0).abs().max()) < 1e-12


def test_lambda_zero_reproduz_central(grade):
    # λ=0 é o próprio cenário central da construção B (nenhum efeito colateral)
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")].iloc[0]
    s0 = grade["central"]["r_0"]["sol"]
    assert math.isclose(s0.soma * 100, float(c.soma_pp), rel_tol=1e-12)


def test_csv_trava_conforme_consistente():
    # saída gravada (make trava) consistente com o contrato de colunas
    path = config.PROCESSED / "trava_conforme.csv"
    if not path.exists():
        pytest.skip("trava_conforme.csv ainda não gerado (rodar aferir.trava)")
    t = pd.read_csv(path)
    assert list(t["cenario_gamma"]) == ["factivel", "central", "conservador"]
    assert (t["soma_pp"] - 26.5).abs().max() <= 1e-4
    assert t["lambda"].is_monotonic_increasing
    assert (t["custo_beneficios_rs_bi"] > 0).all()
    for col in ("lambda", "tau_CBS_pp", "tau_E_pp", "tau_M_pp", "soma_pp",
                "pi_p_pos_lambda", "custo_beneficios_rs_bi", "formula",
                "fonte"):
        assert col in t.columns, col
