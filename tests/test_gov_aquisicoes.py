"""Testes da camada G (compras governamentais, arts. 472-473) — dados SICONFI.

Suíte migrada para a API de perímetros da revisão A5 (g_uniao/g_estadual
antigos foram substituídos por medicoes_uniao/medicoes_estadual + grade
perímetro × natureza36 × estágio em data/processed/g_perimetros.csv).

Golden numbers VERIFICADOS em 12/07/2026 contra g_perimetros.csv gerado dos
caches hasheados (_meta.json / _seed_manifest.json):
  * União 2024, central com36, empenhadas   =  99.724.230.993,63
  * SP 2024, central com36, empenhadas      =  35.500.952.900,86
  * Municipal BR 2024, central com36, emp.  = 390.151.601.894,23
Consistência retroativa: o perímetro `min` COM natureza 36 reproduz ao
centavo o trio 3.3.90.{30,36,39} da versão pré-A5 (União 72.787.920.515,88;
SP 26.874.496.574,66). Ordem de grandeza conforme missão do módulo:
G estadual (27 UFs) na casa de R$ 150-300 bi/ano (medido 191,7/204,1 bi),
municipal similar ou maior, federal menor que o estadual.
"""
import math

import pandas as pd
import pytest

from aferir.config import JANELA_RECEITA, PROCESSED, UFS
from aferir.inputs.gov_aquisicoes import (
    CHAVES_N36,
    COLUNAS_G,
    COLUNAS_PERIMETROS,
    ESTAGIOS,
    PERIMETROS,
    constroi_g_esferas,
    estratos_v1_2023,
    medicoes_uniao,
)

BI = 1e9


@pytest.fixture(scope="module")
def artefatos() -> dict[str, pd.DataFrame]:
    if not all((PROCESSED / f).exists() for f in (
            "g_perimetros.csv", "g_esferas.csv", "sigma_compras.csv",
            "g_municipal_sensibilidade.csv")):
        constroi_g_esferas()
    return {
        "gper": pd.read_csv(PROCESSED / "g_perimetros.csv"),
        "gesf": pd.read_csv(PROCESSED / "g_esferas.csv"),
        "sigma": pd.read_csv(PROCESSED / "sigma_compras.csv"),
        "sens": pd.read_csv(PROCESSED / "g_municipal_sensibilidade.csv"),
    }


def _cel(gper: pd.DataFrame, esfera: str, uf: str, ano: int, perimetro: str,
         n36: str, estagio: str = "empenhadas") -> float:
    d = gper[(gper.esfera == esfera) & (gper.uf == uf) & (gper.ano == ano)
             & (gper.perimetro == perimetro) & (gper.natureza36 == n36)
             & (gper.estagio == estagio)]
    assert len(d) == 1, (esfera, uf, ano, perimetro, n36, estagio)
    return float(d["valor_rs"].iloc[0])


# ---------------------------------------------------------------- golden
def test_golden_uniao_2024(artefatos):
    """Era test_golden_uniao_2024 sobre g_uniao([2024]); agora a célula
    central da grade + elemento 3.3.90.30 via medicoes_uniao (mesmo golden)."""
    g = artefatos["gper"]
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "central", "com36"),
                        99_724_230_993.63, rel_tol=1e-9)
    # consistência retroativa: min com36 = trio 30+36+39 da versão pré-A5
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "min", "com36"),
                        72_787_920_515.88, rel_tol=1e-9)
    # golden por elemento preservado (DCA União Anexo I-D, empenhadas)
    u = medicoes_uniao([2024])
    emp = u[u["estagio"] == "empenhadas"].iloc[0]
    assert math.isclose(emp["g_339030"], 33_673_417_244.42, rel_tol=1e-9)


def test_golden_estadual_sp_2024(artefatos):
    g = artefatos["gper"]
    assert math.isclose(_cel(g, "estadual", "SP", 2024, "central", "com36"),
                        35_500_952_900.86, rel_tol=1e-9)
    # trio pré-A5 preservado no perímetro min com36
    assert math.isclose(_cel(g, "estadual", "SP", 2024, "min", "com36"),
                        26_874_496_574.66, rel_tol=1e-9)


def test_golden_municipal_2024(artefatos):
    g = artefatos["gper"]
    assert math.isclose(_cel(g, "municipal", "BR", 2024, "central", "com36"),
                        390_151_601_894.23, rel_tol=1e-9)


def test_golden_estratos_2023():
    """gpc por estrato re-medido no perímetro central COM natureza 36 (A5);
    o cache antigo (sem colunas de capital) é invalidado pelo módulo."""
    agg = estratos_v1_2023()
    assert set(agg["estrato"]) == {
        "ate_5k", "5k_10k", "10k_20k", "20k_50k", "50k_100k", "acima_100k",
    }
    # colunas de capital presentes (chave de invalidação do cache A5)
    assert {"gpc_g_449051", "gpc_g_449052"} <= set(agg.columns)
    ate5k = agg.set_index("estrato").loc["ate_5k"]
    assert math.isclose(float(ate5k["gpc_g_aquisicoes"]), 3315.956805,
                        rel_tol=1e-6)
    assert math.isclose(float(agg["g_aquisicoes"].sum()), 107.43e9,
                        rel_tol=1e-2)


# ---------------------------------------------------------------- estrutura
def test_esquema_e_proveniencia(artefatos):
    g_esferas = artefatos["gesf"]
    assert list(g_esferas.columns) == COLUNAS_G
    assert set(g_esferas["esfera"]) == {"uniao", "estadual", "municipal"}
    assert set(g_esferas["ano"]) == set(JANELA_RECEITA)
    # proveniência obrigatória em TODA linha agregada
    assert g_esferas["formula"].str.len().min() > 0
    assert g_esferas["fonte"].str.contains("SICONFI").all()
    # 27 UFs por ano na esfera estadual; BR nas demais
    est = g_esferas[g_esferas["esfera"] == "estadual"]
    assert est.groupby("ano")["uf"].nunique().eq(27).all()
    assert (g_esferas.loc[g_esferas["esfera"] != "estadual", "uf"] == "BR").all()
    # soma das naturezas do perímetro central fecha com o total (1e-6)
    cols_nat = ["g_339030", "g_339032", "g_339033", "g_339036", "g_339037",
                "g_339039", "g_339040"]
    soma = g_esferas[cols_nat].sum(axis=1)
    assert (abs(soma - g_esferas["g_aquisicoes"]) < 1e-6 * soma).all()


def test_grade_completa(artefatos):
    """g_perimetros.csv cobre a grade inteira: 3 perímetros × {com36, sem36}
    × 2 estágios × 2 anos × 3 esferas (27 UFs na estadual, BR nas demais)."""
    gper = artefatos["gper"]
    assert list(gper.columns) == COLUNAS_PERIMETROS
    assert set(gper["perimetro"]) == set(PERIMETROS)
    assert set(gper["natureza36"]) == set(CHAVES_N36)
    assert set(gper["estagio"]) == set(ESTAGIOS)
    assert set(gper["ano"]) == set(JANELA_RECEITA)
    chave = ["esfera", "uf", "ano", "perimetro", "natureza36", "estagio"]
    assert not gper.duplicated(chave).any()
    # cada combinação ano × perímetro × chave36 × estágio tem 29 linhas:
    # 1 União (BR) + 27 UFs + 1 municipal (BR)
    combos = gper.groupby(["ano", "perimetro", "natureza36", "estagio"]).size()
    assert len(combos) == 2 * 3 * 2 * 2
    assert combos.eq(29).all()
    assert set(gper.loc[gper["esfera"] == "estadual", "uf"]) == set(UFS)
    assert (gper.loc[gper["esfera"] != "estadual", "uf"] == "BR").all()
    # proveniência não vazia em TODA célula da grade
    assert gper["formula"].str.len().min() > 0
    assert gper["fonte"].str.len().min() > 0
    assert gper["fonte"].str.contains("SICONFI").all()


def test_monotonicidade_perimetros(artefatos):
    """G_min <= G_central <= G_max com chave 36, estágio, ano e esfera/UF
    fixos, célula a célula."""
    gper = artefatos["gper"]
    wide = gper.pivot_table(
        index=["esfera", "uf", "ano", "natureza36", "estagio"],
        columns="perimetro", values="valor_rs")
    assert wide.notna().all().all()
    assert (wide["min"] <= wide["central"] + 1e-6).all()
    assert (wide["central"] <= wide["max"] + 1e-6).all()


def test_natureza36_com36_maior_igual(artefatos):
    """com36 >= sem36 em toda célula (a natureza 3.3.90.36 é não negativa)."""
    gper = artefatos["gper"]
    wide = gper.pivot_table(
        index=["esfera", "uf", "ano", "perimetro", "estagio"],
        columns="natureza36", values="valor_rs")
    assert wide.notna().all().all()
    assert (wide["com36"] >= wide["sem36"] - 1e-6).all()


# ---------------------------------------------------------------- ordem de grandeza
def test_ordem_de_grandeza(artefatos):
    g_esferas = artefatos["gesf"]
    for ano in JANELA_RECEITA:
        d = g_esferas[g_esferas["ano"] == ano]
        g_est = d.loc[d["esfera"] == "estadual", "g_aquisicoes"].sum()
        g_uni = d.loc[d["esfera"] == "uniao", "g_aquisicoes"].sum()
        g_mun = d.loc[d["esfera"] == "municipal", "g_aquisicoes"].sum()
        # estadual na casa de R$ 150-300 bi/ano (medido 191,7/204,1 bi, A5)
        assert 150 * BI < g_est < 300 * BI
        # federal menor que estadual
        assert g_uni < g_est
        # municipal similar ou maior que o estadual
        assert g_mun > 0.8 * g_est


def test_sensibilidade_municipal_publicada(artefatos):
    """Variantes herdadas S1-S3 + corredor por perímetro (A5)."""
    s = artefatos["sens"]
    esperadas = {
        "central_pos_estratificada", "S1_escala_populacional",
        "S2_cota_inferior_amostra", "S3_liquidadas_amostra",
    } | {f"perimetro_{p}_{c}" for p in PERIMETROS for c in CHAVES_N36}
    assert set(s["variante"]) == esperadas
    for ano in JANELA_RECEITA:
        d = s[s["ano"] == ano].set_index("variante")["g_aquisicoes"]
        # cota inferior <= central; liquidadas <= empenhadas (amostra)
        assert d["S2_cota_inferior_amostra"] <= d["central_pos_estratificada"]
        assert d["S3_liquidadas_amostra"] <= d["S2_cota_inferior_amostra"] * 1.0001
        # corredor por perímetro coerente com a variante central
        assert math.isclose(d["perimetro_central_com36"],
                            d["central_pos_estratificada"], rel_tol=1e-12)
        assert d["perimetro_min_com36"] <= d["perimetro_central_com36"] \
            <= d["perimetro_max_com36"]


# ---------------------------------------------------------------- sigma (art. 370)
def test_sigma_compras_coerencia(artefatos):
    """sigma_compras.csv: pesos somam 1, recomposição exata, sigma_max <=
    sigma_central (capital tem carga embutida menor que o custeio)."""
    s = artefatos["sigma"].set_index("perimetro")
    assert set(s.index) == set(PERIMETROS)
    assert ((s["peso_custeio"] + s["peso_capital"] - 1.0).abs() < 1e-12).all()
    recomp = (s["peso_custeio"] * s["sigma_custeio"]
              + s["peso_capital"] * s["sigma_capital"])
    assert ((recomp - s["sigma"]).abs() < 1e-12).all()
    # min/central: perímetros de custeio puro (capital = 0)
    assert float(s.loc["min", "peso_capital"]) == 0.0
    assert float(s.loc["central", "peso_capital"]) == 0.0
    assert float(s.loc["max", "peso_capital"]) > 0.0
    assert float(s.loc["max", "sigma"]) <= float(s.loc["central", "sigma"])
    # sigma do max fica entre os componentes custeio/capital
    lo = float(min(s.loc["max", "sigma_custeio"], s.loc["max", "sigma_capital"]))
    hi = float(max(s.loc["max", "sigma_custeio"], s.loc["max", "sigma_capital"]))
    assert lo <= float(s.loc["max", "sigma"]) <= hi
    # proveniência
    assert s["formula"].str.len().min() > 0
    assert s["fonte"].str.len().min() > 0


# ---------------------------------------------------------------- determinismo
def test_determinismo_bytes():
    paths = [PROCESSED / "g_perimetros.csv", PROCESSED / "g_esferas.csv",
             PROCESSED / "g_municipal_sensibilidade.csv",
             PROCESSED / "sigma_compras.csv"]
    antes = {p: p.read_bytes() for p in paths}
    constroi_g_esferas()
    for p in paths:
        assert p.read_bytes() == antes[p], p.name
