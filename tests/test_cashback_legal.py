"""E6 — critério legal do cashback (LC 214, arts. 112-118) e take-up.

Contratos testados:
 1. limiar e unidades: ½ × SM de 15/01/2018 (Decreto nº 9.255/2017) sobre
    renda MENSAL per capita, corte inclusivo ("de até meio salário mínimo");
 2. golden: f_low_legal nacional medido nos microdados (2026-07-12);
 3. coerência: f_low_legal nacional ∈ (0,05; 0,25);
 4. take_up=1,0 reproduz o comportamento atual bit a bit;
 5. take_up=0,8 escala a dedução linearmente.

Os testes leem os artefatos processados (pof_elegiveis_legal_uf.csv,
cashback_elegibilidade.csv, qa_cashback_custo.csv); os geradores lentos
(microdados ~4 min) rodam via `python3 -m aferir.inputs.pof legal` e
`python3 -m aferir.cashback`.
"""
from __future__ import annotations

import pandas as pd
import pytest

from aferir.cashback import BaseElegivel, base_elegivel, cb_base
from aferir.config import PROCESSED
from aferir.inputs.pof import (
    LIMIAR_LEGAL_RPC,
    SALARIO_MINIMO_2018,
    classifica_elegivel_legal,
)

F_LOW_LEGAL_NACIONAL_GOLDEN = 0.051224   # medido 2026-07-12 (microdados POF)


@pytest.fixture(scope="session")
def legal_uf() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "pof_elegiveis_legal_uf.csv")


@pytest.fixture(scope="session")
def comparacao() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "cashback_elegibilidade.csv")


@pytest.fixture(scope="session")
def qa_custo() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "qa_cashback_custo.csv").set_index("variante")


# ------------------------------------------------------- limiar e unidades
def test_limiar_meio_salario_minimo():
    assert SALARIO_MINIMO_2018 == 954.00          # Decreto nº 9.255/2017
    assert LIMIAR_LEGAL_RPC == 477.00             # ½ SM, R$/mês per capita


def test_classificacao_rpc_mensal_corte_inclusivo():
    uc = pd.DataFrame({
        "renda_total": [954.00, 954.02, 4770.0, 477.0],   # R$/mês da UC
        "n_pessoas": [2, 2, 10, 0],                       # 0 → clip(1)
        "peso_final": [1.0, 1.0, 1.0, 1.0],
    })
    d = classifica_elegivel_legal(uc)
    assert d["rpc"].tolist() == [477.00, 477.01, 477.00, 477.00]
    # "de até meio salário mínimo" (art. 113): corte INCLUSIVO em 477,00
    assert d["elegivel_legal"].tolist() == [True, False, True, True]
    assert d["pop_w"].tolist() == [2.0, 2.0, 10.0, 0.0]


# ------------------------------------------------------------------ golden
def test_golden_f_low_legal_nacional(comparacao):
    br = comparacao.set_index("uf").loc["BR"]
    assert br["f_low_legal"] == pytest.approx(F_LOW_LEGAL_NACIONAL_GOLDEN,
                                              abs=5e-6)


def test_coerencia_f_low_legal(legal_uf, comparacao):
    br = comparacao.set_index("uf").loc["BR"]
    assert 0.05 < br["f_low_legal"] < 0.25
    assert legal_uf["uf"].nunique() == 27
    assert legal_uf["f_low_legal"].between(0.0, 1.0).all()
    # famílias elegíveis são maiores que a média ⇒ share de pessoas > famílias
    assert br["share_pessoas_elegiveis"] > br["share_familias_elegiveis"]


def test_f_low_decis3_espelha_pipeline(comparacao):
    """f_low_decis3 da comparação = f_low do pipeline (base_uf.csv), UF a UF."""
    base = pd.read_csv(PROCESSED / "base_uf.csv").set_index("uf")["f_low"]
    comp = comparacao[comparacao["uf"] != "BR"].set_index("uf")["f_low_decis3"]
    for uf in base.index:
        assert comp[uf] == pytest.approx(base[uf], rel=1e-9), uf


def test_delta_e_sinal(comparacao):
    c = comparacao.set_index("uf")
    assert (c["delta_f_low"] - (c["f_low_legal"] - c["f_low_decis3"])) \
        .abs().max() < 1e-12
    # achado E6: na POF (RENDA_TOTAL, conceito amplo) o critério legal é MAIS
    # restrito que decis 1-3 em TODAS as UFs ⇒ menor devolução
    assert (c["delta_f_low"] < 0).all()


# ------------------------------------------------------------------ take-up
_ELEGIVEL = base_elegivel(100.0, 0.10, 0.09)


@pytest.mark.parametrize("esfera", ["uniao", "estadual", "municipal"])
def test_take_up_1_reproduz_bit_a_bit(esfera):
    assert cb_base(esfera, _ELEGIVEL) == cb_base(esfera, _ELEGIVEL,
                                                 take_up=1.0)


@pytest.mark.parametrize("esfera", ["uniao", "estadual", "municipal"])
def test_take_up_08_escala_linear(esfera):
    assert cb_base(esfera, _ELEGIVEL, take_up=0.8) == \
        pytest.approx(0.8 * cb_base(esfera, _ELEGIVEL), rel=1e-15)


def test_take_up_dominio():
    with pytest.raises(ValueError):
        cb_base("uniao", _ELEGIVEL, take_up=1.2)
    with pytest.raises(ValueError):
        cb_base("uniao", _ELEGIVEL, take_up=-0.1)
    assert cb_base("uniao", BaseElegivel(0.0, 0.0), take_up=0.5) == 0.0


# ------------------------------------------------------------------ QA custo
def test_qa_custo_variantes(qa_custo):
    d3 = qa_custo.loc["decis3_takeup_100"]
    l100 = qa_custo.loc["legal_takeup_100"]
    l80 = qa_custo.loc["legal_takeup_80"]
    # legal < decis-3 (f_low_legal < f_low em todas as UFs)
    assert l100["cb_total_bi"] < d3["cb_total_bi"]
    # take-up 80% = 0,8 × take-up 100% (linearidade da dedução e do custo)
    assert l80["cb_total_bi"] == pytest.approx(0.8 * l100["cb_total_bi"],
                                               rel=1e-12)
    assert l80["custo_rs_bi"] == pytest.approx(0.8 * l100["custo_rs_bi"],
                                               rel=1e-12)
    # confronto oficial: custo implícito NT SERT = (0,39+0,04)% × B*
    anc = pd.read_csv(PROCESSED / "aferir_ancoras.csv")
    b_star = float(anc["B_star_bi"].iloc[0])
    oficial = qa_custo.loc["oficial_nt_sert_implicito", "custo_rs_bi"]
    assert oficial == pytest.approx(0.0043 * b_star, rel=1e-12)
    # desvio da variante legal >20% — investigação registrada (conceito de
    # renda POF ≠ renda declarada CadÚnico; ver cashback.py e relatório E6)
    assert abs(l100["desvio_pct_vs_oficial"]) > 20.0
    assert abs(d3["desvio_pct_vs_oficial"]) < 20.0
