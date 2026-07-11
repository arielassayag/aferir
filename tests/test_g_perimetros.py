"""Testes da revisão A5 — perímetros de G (arts. 472-473) e σ recalibrado.

Golden numbers medidos em 12/07/2026 sobre os caches hasheados (_meta.json /
_seed_manifest.json). Consistência retroativa verificada: o perímetro
`min` COM natureza 36 reproduz AO CENTAVO o trio 3.3.90.30/36/39 da versão
anterior (g_uniao 2024 = 72.787.920.515,88; SP 2024 = 26.874.496.574,66;
municipal 2024 = 353.410.979.234,56).
"""
import math

import pandas as pd
import pytest

from aferir.config import JANELA_RECEITA, PROCESSED
from aferir.govpurchases import g_por_esfera_uf, sigma_iso_carga
from aferir.inputs.gov_aquisicoes import (
    CHAVES_N36,
    COLUNAS_G,
    COLUNAS_PERIMETROS,
    PERIMETROS,
    constroi_g_esferas,
    naturezas_de,
)
from aferir.inputs.ipca_pib import deflator_para_2024

BI = 1e9


@pytest.fixture(scope="module")
def artefatos() -> dict[str, pd.DataFrame]:
    if not (PROCESSED / "g_perimetros.csv").exists() \
            or not (PROCESSED / "sigma_compras.csv").exists():
        constroi_g_esferas()
    return {
        "gper": pd.read_csv(PROCESSED / "g_perimetros.csv"),
        "gesf": pd.read_csv(PROCESSED / "g_esferas.csv"),
        "sigma": pd.read_csv(PROCESSED / "sigma_compras.csv"),
        "sens": pd.read_csv(PROCESSED / "g_municipal_sensibilidade.csv"),
    }


def _cel(gper, esfera, uf, ano, perimetro, n36, estagio="empenhadas") -> float:
    d = gper[(gper.esfera == esfera) & (gper.uf == uf) & (gper.ano == ano)
             & (gper.perimetro == perimetro) & (gper.natureza36 == n36)
             & (gper.estagio == estagio)]
    assert len(d) == 1, (esfera, uf, ano, perimetro, n36, estagio)
    return float(d["valor_rs"].iloc[0])


# ---------------------------------------------------------------- perímetros
def test_definicao_perimetros():
    assert naturezas_de("min", False) == ("3.3.90.30", "3.3.90.39")
    assert "3.3.90.36" in naturezas_de("min", True)
    assert set(naturezas_de("central", False)) == {
        "3.3.90.30", "3.3.90.32", "3.3.90.33", "3.3.90.37", "3.3.90.39",
        "3.3.90.40",
    }
    assert set(naturezas_de("max", True)) - set(naturezas_de("central", True)) \
        == {"4.4.90.51", "4.4.90.52"}
    # 4.4.90.40 (TIC-PJ capital) NÃO entra em nenhum perímetro (A5, item 2)
    assert all("4.4.90.40" not in naturezas_de(p, True) for p in PERIMETROS)


# ---------------------------------------------------------------- goldens
def test_golden_uniao_2024(artefatos):
    g = artefatos["gper"]
    # min com36 = trio antigo 3.3.90.30/36/39 (consistência retroativa)
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "min", "com36"),
                        72_787_920_515.88, rel_tol=1e-9)
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "central", "com36"),
                        99_724_230_993.63, rel_tol=1e-9)
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "max", "com36"),
                        121_665_914_159.21, rel_tol=1e-9)
    assert math.isclose(_cel(g, "uniao", "BR", 2024, "central", "sem36"),
                        97_017_282_868.42, rel_tol=1e-9)


def test_golden_estadual_sp_2024(artefatos):
    g = artefatos["gper"]
    assert math.isclose(_cel(g, "estadual", "SP", 2024, "min", "com36"),
                        26_874_496_574.66, rel_tol=1e-9)
    assert math.isclose(_cel(g, "estadual", "SP", 2024, "central", "com36"),
                        35_500_952_900.86, rel_tol=1e-9)
    assert math.isclose(_cel(g, "estadual", "SP", 2024, "max", "com36"),
                        45_720_874_839.57, rel_tol=1e-9)


def test_golden_municipal_2024(artefatos):
    g = artefatos["gper"]
    assert math.isclose(_cel(g, "municipal", "BR", 2024, "min", "com36"),
                        353_410_979_234.56, rel_tol=1e-9)
    assert math.isclose(_cel(g, "municipal", "BR", 2024, "central", "com36"),
                        390_151_601_894.23, rel_tol=1e-9)
    assert math.isclose(_cel(g, "municipal", "BR", 2024, "max", "com36"),
                        512_571_220_050.65, rel_tol=1e-9)


def test_golden_janela_deflacionada():
    """G médio da janela (R$ bi de 2024) via API — o que o motor consome."""
    defl = deflator_para_2024(2025).valor
    g = g_por_esfera_uf(defl)                      # default = central com36
    assert math.isclose(g["uniao"], 102.549606368, rel_tol=1e-9)
    assert math.isclose(float(g["estadual"].sum()), 193.061397438, rel_tol=1e-9)
    assert math.isclose(float(g["municipal"].sum()), 385.058248340, rel_tol=1e-9)
    gmax = g_por_esfera_uf(defl, perimetro="max")
    assert math.isclose(gmax["uniao"], 125.842608817, rel_tol=1e-9)
    assert math.isclose(float(gmax["municipal"].sum()), 488.563935174,
                        rel_tol=1e-9)


# ---------------------------------------------------------------- monotonia
def test_monotonia_perimetros(artefatos):
    """G_min <= G_central <= G_max com a chave 36 fixa, célula a célula."""
    g = artefatos["gper"]
    wide = g.pivot_table(index=["esfera", "uf", "ano", "natureza36", "estagio"],
                         columns="perimetro", values="valor_rs")
    assert (wide["min"] <= wide["central"] + 1e-6).all()
    assert (wide["central"] <= wide["max"] + 1e-6).all()


def test_chave_natureza36_reduz(artefatos):
    """sem36 < com36 em toda célula (a natureza 36 é positiva nas 3 esferas)."""
    g = artefatos["gper"]
    wide = g.pivot_table(index=["esfera", "uf", "ano", "perimetro", "estagio"],
                         columns="natureza36", values="valor_rs")
    assert (wide["sem36"] < wide["com36"]).all()


def test_liquidadas_menor_que_empenhadas_uniao_estados(artefatos):
    g = artefatos["gper"]
    d = g[g.esfera.isin(["uniao", "estadual"])]
    wide = d.pivot_table(index=["esfera", "uf", "ano", "perimetro", "natureza36"],
                         columns="estagio", values="valor_rs")
    assert (wide["liquidadas"] <= wide["empenhadas"] * 1.0001).all()


# ---------------------------------------------------------------- sigma
def test_sigma_coerente_por_perimetro(artefatos):
    s = artefatos["sigma"].set_index("perimetro")
    assert set(s.index) == set(PERIMETROS)
    # custeio: valor histórico do redutor F8 (TRU 2021, mix CI do governo)
    assert math.isclose(float(s.loc["central", "sigma"]),
                        0.0823385030098401, rel_tol=1e-12)
    assert math.isclose(float(s.loc["min", "sigma"]),
                        float(s.loc["central", "sigma"]), rel_tol=1e-12)
    # capital dentro da faixa plausível [2; 25]%
    assert (s["sigma_capital"].between(0.02, 0.25)).all()
    # max = média ponderada exata dos componentes; pesos somam 1
    for p in PERIMETROS:
        r = s.loc[p]
        assert math.isclose(r["peso_custeio"] + r["peso_capital"], 1.0,
                            rel_tol=1e-12)
        assert math.isclose(
            r["sigma"],
            r["peso_custeio"] * r["sigma_custeio"]
            + r["peso_capital"] * r["sigma_capital"], rel_tol=1e-12)
    assert float(s.loc["max", "peso_capital"]) > 0.1
    lo = min(s.loc["max", "sigma_custeio"], s.loc["max", "sigma_capital"])
    hi = max(s.loc["max", "sigma_custeio"], s.loc["max", "sigma_capital"])
    assert lo <= float(s.loc["max", "sigma"]) <= hi
    # golden medido 12/07/2026
    assert math.isclose(float(s.loc["max", "sigma"]), 0.076755381930,
                        rel_tol=1e-9)


def test_sigma_api_retrocompativel():
    assert math.isclose(sigma_iso_carga(), 0.0823385030098401, rel_tol=1e-12)
    assert sigma_iso_carga("max") < sigma_iso_carga("central")
    with pytest.raises(ValueError):
        sigma_iso_carga("inexistente")


def test_tru_gov_carga_compatibilidade():
    """As linhas/colunas antigas de tru_gov_carga.csv não podem sumir (o
    manuscrito lê carga_embutida_gov_central_pct)."""
    t = pd.read_csv(PROCESSED / "tru_gov_carga.csv")
    assert list(t.columns) == ["cenario", "papel", "carga_embutida_estimada_pct",
                               "formula", "fonte"]
    assert {"carga_embutida_gov_central_pct",
            "carga_embutida_gov_consumo_total_pct",
            "carga_embutida_gov_consumo_ex_producao_propria_pct",
            "carga_embutida_fbcf_construcao_pct",
            "carga_embutida_fbcf_maquinas_pct"} <= set(t["cenario"])
    c = t.set_index("cenario")["carga_embutida_estimada_pct"]
    assert math.isclose(float(c["carga_embutida_gov_central_pct"]),
                        8.23385030098401, rel_tol=1e-9)


# ---------------------------------------------------------------- esquema
def test_esquema_e_proveniencia(artefatos):
    gper, gesf = artefatos["gper"], artefatos["gesf"]
    assert list(gper.columns) == COLUNAS_PERIMETROS
    assert set(gper["perimetro"]) == set(PERIMETROS)
    assert set(gper["natureza36"]) == set(CHAVES_N36)
    assert set(gper["estagio"]) == {"empenhadas", "liquidadas"}
    assert set(gper["ano"]) == set(JANELA_RECEITA)
    assert gper["formula"].str.len().min() > 0
    assert gper["fonte"].str.contains("SICONFI").all()
    # adaptação declarada: DCA consolidada, sem abertura institucional
    assert gper["fonte"].str.contains("CONSOLIDADA").all()
    est = gper[gper["esfera"] == "estadual"]
    assert est.groupby(["ano", "perimetro", "natureza36", "estagio"])["uf"] \
        .nunique().eq(27).all()

    # g_esferas espelha o perímetro central COM 36 (empenhadas)
    assert list(gesf.columns) == COLUNAS_G
    cols_nat = ["g_339030", "g_339032", "g_339033", "g_339036", "g_339037",
                "g_339039", "g_339040"]
    soma = gesf[cols_nat].sum(axis=1)
    assert (abs(soma - gesf["g_aquisicoes"]) < 1e-6 * soma).all()
    for _, r in gesf.iterrows():
        assert math.isclose(
            r["g_aquisicoes"],
            _cel(gper, r["esfera"], r["uf"], r["ano"], "central", "com36"),
            rel_tol=1e-9)


def test_sensibilidade_municipal_variantes(artefatos):
    s = artefatos["sens"]
    esperadas = {"central_pos_estratificada", "S1_escala_populacional",
                 "S2_cota_inferior_amostra", "S3_liquidadas_amostra"} | {
        f"perimetro_{p}_{c}" for p in PERIMETROS for c in CHAVES_N36}
    assert set(s["variante"]) == esperadas
    for ano in JANELA_RECEITA:
        d = s[s["ano"] == ano].set_index("variante")["g_aquisicoes"]
        assert d["S2_cota_inferior_amostra"] <= d["central_pos_estratificada"]
        assert d["S3_liquidadas_amostra"] <= d["S2_cota_inferior_amostra"] * 1.0001
        # a variante de perímetro central com36 é o próprio central
        assert math.isclose(d["perimetro_central_com36"],
                            d["central_pos_estratificada"], rel_tol=1e-12)
        assert d["perimetro_min_com36"] <= d["perimetro_central_com36"] \
            <= d["perimetro_max_com36"]


# ---------------------------------------------------------------- API motor
def test_api_g_por_esfera_uf_estrutura():
    defl = deflator_para_2024(2025).valor
    g = g_por_esfera_uf(defl)
    assert isinstance(g["uniao"], float)
    assert len(g["estadual"]) == 27
    assert len(g["municipal"]) == 27
    assert g["municipal"]["DF"] == 0.0     # G do DF na esfera estadual
    # perímetro maior => G maior, esfera a esfera
    gmax = g_por_esfera_uf(defl, perimetro="max")
    assert gmax["uniao"] > g["uniao"]
    assert (gmax["estadual"] >= g["estadual"]).all()
    with pytest.raises(ValueError):
        g_por_esfera_uf(defl, perimetro="inexistente")


# ---------------------------------------------------------------- determinismo
def test_determinismo_bytes():
    paths = [PROCESSED / "g_perimetros.csv", PROCESSED / "sigma_compras.csv",
             PROCESSED / "g_esferas.csv",
             PROCESSED / "g_municipal_sensibilidade.csv"]
    antes = {p: p.read_bytes() for p in paths}
    constroi_g_esferas()
    for p in paths:
        assert p.read_bytes() == antes[p], p.name
