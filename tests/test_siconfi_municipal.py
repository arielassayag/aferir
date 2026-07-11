"""Testes da camada municipal (ISS) — golden numbers e invariantes.

Pré-condição: `python3 -m aferir.fetch.siconfi_municipal` executado (cache
completo em data/raw/siconfi_municipal/ e processados em data/processed/).
Golden numbers verificados manualmente contra a API SICONFI e o parecer
(SP capital 2024 ao centavo) e contra o inventário v1 (ISS-DF do RREO).
"""
from __future__ import annotations

import pandas as pd
import pytest

from aferir.config import (JANELA_RECEITA, PROCESSED, RAW,
                           SONDA_DF_ISS_RREO, SONDA_SP_CAPITAL_2024_ISS_BRUTA,
                           SONDA_SP_CAPITAL_COD_IBGE, UFS)

RAW_MUNICIPAL = RAW / "siconfi_municipal"

# ------------------------------------------------- golden numbers (sondas I14)
# Valores declarados em config.py (fonte única — invariante I14 do gate usa
# os mesmos): SP capital DCA I-C 2024 ao centavo; ISS-DF via RREO Anexo 03.
SP_CAPITAL_COD_IBGE = SONDA_SP_CAPITAL_COD_IBGE
SP_CAPITAL_2024_ISS_BRUTA = SONDA_SP_CAPITAL_2024_ISS_BRUTA
DF_ISS_RREO = SONDA_DF_ISS_RREO
N_MUNICIPIOS = 5_570


@pytest.fixture(scope="module")
def painel() -> dict[int, pd.DataFrame]:
    return {
        ano: pd.read_parquet(PROCESSED / f"iss_municipio_{ano}.parquet")
        for ano in JANELA_RECEITA
    }


@pytest.fixture(scope="module")
def r_uf() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "r_municipal_uf.csv")


@pytest.fixture(scope="module")
def conc() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "iss_concentracao.csv")


# ---------------------------------------------------------------- universo
def test_universo_5570(painel):
    for ano, p in painel.items():
        assert len(p) == N_MUNICIPIOS, f"{ano}: universo != 5.570"
        assert p["cod_ibge"].is_unique
        assert set(p.columns) == {
            "cod_ibge", "ente", "uf", "populacao",
            "iss_bruta", "iss_deducoes_outras", "iss_liquida",
        }


def test_sp_capital_2024_golden(painel):
    sp = painel[2024].set_index("cod_ibge").loc[SP_CAPITAL_COD_IBGE]
    assert sp["iss_bruta"] == pytest.approx(SP_CAPITAL_2024_ISS_BRUTA, abs=0.005)
    assert sp["ente"] == "São Paulo"


def test_identidade_liquida(painel):
    for ano, p in painel.items():
        d = p[p["iss_liquida"].notna()]
        erro = (d["iss_liquida"] - (d["iss_bruta"] - d["iss_deducoes_outras"])).abs()
        assert erro.max() < 1e-6, f"{ano}: iss_liquida != bruta - deducoes"


def test_fundeb_nao_incide_sobre_iss():
    """DESIGN §2.3: Deduções-FUNDEB não se aplicam ao ISS. Alguns municípios
    registram a dedução por erro contábil (universo 2024: 4 casos, ~R$ 1,5 mi
    ≈ 0,001% do ISS) — o builder as IGNORA; o invariante exige apenas
    imaterialidade (< 0,01% do ISS bruto do ano)."""
    for ano in JANELA_RECEITA:
        bruto = pd.read_parquet(RAW_MUNICIPAL / f"dca_iss_{ano}.parquet")
        fundeb = bruto[bruto["coluna"] == "Deduções - FUNDEB"]["valor"].sum()
        iss = bruto[bruto["coluna"] == "Receitas Brutas Realizadas"]["valor"].sum()
        assert fundeb <= 1e-4 * iss, (
            f"{ano}: Deducao-FUNDEB espúria = {fundeb:,.0f} (> 0,01% do ISS)"
        )


# ---------------------------------------------------------------- agregado UF
def test_df_rreo_golden(r_uf):
    for ano, esperado in DF_ISS_RREO.items():
        linha = r_uf[(r_uf["uf"] == "DF") & (r_uf["ano"] == ano)]
        assert len(linha) == 1
        assert linha["iss_liquida"].iloc[0] == pytest.approx(esperado, abs=0.005)
        assert linha["fonte"].iloc[0] == "RREO-DF"


def test_soma_nacional_2024_ordem_de_grandeza(r_uf):
    """ISS 2022 ~ R$ 107 bi (IPEA CC60); 2024 esperado em R$ 130-180 bi."""
    g = r_uf[r_uf["ano"] == 2024]
    declarado = g["iss_liquida"].sum()
    com_imputacao = declarado + g["iss_imputado"].sum()
    assert 130e9 <= declarado <= 180e9
    assert 130e9 <= com_imputacao <= 180e9


def test_cobertura(r_uf):
    for ano in JANELA_RECEITA:
        g = r_uf[r_uf["ano"] == ano]
        cobertura = 100.0 * g["n_declarantes"].sum() / g["n_universo"].sum()
        assert cobertura >= 90.0, f"{ano}: cobertura {cobertura:.2f}% < 90%"


def test_r_uf_estrutura(r_uf):
    assert sorted(r_uf["uf"].unique()) == sorted(UFS)
    assert len(r_uf) == len(UFS) * len(JANELA_RECEITA)
    assert {"formula", "fonte"} <= set(r_uf.columns)          # proveniência
    # universo ex-DF: Brasília (5300108) sai do painel DCA (ISS via RREO-DF)
    assert (r_uf["n_universo"].where(r_uf["uf"] != "DF", 0).sum()
            == (N_MUNICIPIOS - 1) * len(JANELA_RECEITA))
    assert (r_uf["iss_imputado"] >= 0).all()
    # F2: variante sem imputação = iss_liquida pura (coluna separada)
    assert (r_uf.loc[r_uf["uf"] == "DF", "iss_imputado"] == 0).all()


# ---------------------------------------------------------------- concentração
def test_concentracao_estrutura(conc):
    for ano in JANELA_RECEITA:
        tops = conc[(conc["serie"] == "share_top") & (conc["ano"] == ano)]
        s = tops.set_index("x")["y"]
        assert set(s.index) == {1.0, 10.0, 100.0}
        assert 0 < s[1.0] < s[10.0] < s[100.0] <= 1.0
        # concentração conhecida do ISS: top-100 domina o agregado nacional
        assert s[100.0] > 0.5

        lorenz = conc[(conc["serie"] == "lorenz") & (conc["ano"] == ano)]
        y = lorenz.sort_values("x")["y"].to_numpy()
        assert (pd.Series(y).diff().dropna() >= -1e-12).all()  # monotônica
        assert y[-1] == pytest.approx(1.0, abs=1e-9)

        gini = conc[(conc["serie"] == "gini") & (conc["ano"] == ano)]["y"].iloc[0]
        assert 0.7 <= gini < 1.0                               # ISS: alta desigualdade
