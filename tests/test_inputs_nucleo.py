"""Golden tests dos insumos do núcleo: TRU 2021, SICONFI estadual, IPCA, ANP.

Goldens EXTERNOS (transcritos de fonte oficial ou paridade v1 auditada):
  * deflator 2025→2024 = 0,952229023823 (v1 MANIFEST.toml, SIDRA 1737);
  * Σ ICMS janela (média 2024-2025, R$ 2024, convenção v1 c/ ISS-DF) ≈ 818,48;
  * totais TRU 2021 (linha Total das planilhas IBGE, R$ mi correntes);
  * FECP-RJ 2024 (DCA 1.1.1.4.50.2.0): R$ 6,662 bi brutos;
  * fundos estaduais: total-base R$ 3,5 bi (NT SERT 01/07/2024, p. 4).
"""
from __future__ import annotations

import math

import pytest

from aferir.inputs import combustiveis, ipca_pib, siconfi_estadual, tru

# ------------------------------------------------------------------ deflator
DEFLATOR_2025_GOLDEN = 0.952229023823          # v1 MANIFEST.toml (SIDRA 1737)


def test_deflator_2025_para_2024_golden():
    d = ipca_pib.deflator_para_2024(2025).valor
    assert math.isclose(d, DEFLATOR_2025_GOLDEN, abs_tol=1e-9)


def test_deflator_2024_e_identidade():
    assert ipca_pib.deflator_para_2024(2024).valor == 1.0


# ------------------------------------------------------------------ TRU 2021
# Linha "Total" das planilhas IBGE (tab1/oferta e tab2/demanda), R$ mi de 2021.
TRU_TOTAIS_GOLDEN = {
    "consumo_familias": 5_415_523,
    "consumo_governo": 1_671_535,
    "fbcf": 1_614_782,
    "exportacoes": 1_722_169,
    "impostos_liquidos_produtos": 1_298_143,
    "oferta_preco_consumidor": 19_551_489,
}


def test_tru_usos_totais_golden():
    df = tru.usos_2021()
    assert len(df) == 128                      # nível 68 = 128 produtos
    for col, total in TRU_TOTAIS_GOLDEN.items():
        assert math.isclose(df[col].sum(), total, abs_tol=0.5), col


def test_tru_carga_embutida_gov_sanity():
    nums = tru.carga_embutida_gov()
    central = nums["carga_embutida_gov_central_pct"].valor
    # sanity de ordem de grandeza do redutor iso-carga (FORK F8)
    assert 5.0 <= central <= 20.0
    # diagnóstico do consumo final total tem de ser MUITO menor (produção
    # própria não-mercantil quase sem impostos sobre produtos)
    assert nums["carga_embutida_gov_consumo_total_pct"].valor < 1.0


def test_tru_parquet_tem_proveniencia(tmp_path):
    df = tru.grava_usos_parquet()
    assert {"formula", "fonte"} <= set(df.columns)


# ------------------------------------------------------- SICONFI estadual
PARIDADE_V1_GOLDEN_RBI = 818.48                # v1 revenue_target.csv (R_full)


def test_paridade_v1_icms_janela():
    v = siconfi_estadual.paridade_v1_media_janela_Rbi().valor
    assert math.isclose(v, PARIDADE_V1_GOLDEN_RBI, abs_tol=0.01)


def test_r_estadual_estrutura_e_triangulacao():
    df = siconfi_estadual.r_estadual()
    assert len(df) == 54                       # 27 UFs × 2 anos
    # identidade RREO ≡ DCA(ICMS+FECP, brutas − outras deduções): medida 0,0%
    assert df["desvio_rreo_dca_pct"].abs().max() < 0.05
    # FECP embutido na rubrica RREO (achado de conceito): RJ tem o maior
    rj24 = df[(df.uf == "RJ") & (df.ano == 2024)].iloc[0]
    assert rj24["dca_fecp_bruta"] > 6e9
    assert {"formula", "fonte"} <= set(df.columns)


def test_fecp_uf_separavel():
    df = siconfi_estadual.fecp_uf()
    # 22 UFs com conta separável na janela (44 linhas medidas em 2026-07-10)
    assert len(df) == 44
    assert set(df.columns) >= {"uf", "ano", "fecp", "conta", "formula", "fonte"}
    rj24 = df[(df.uf == "RJ") & (df.ano == 2024)].iloc[0]
    assert math.isclose(rj24["fecp_bruta"], 6.662e9, rel_tol=0.01)
    # UFs sem conta separável (fronteira documentada): 5 = 27 − 22
    assert len(set("AC AP PA RR SC".split()) & set(df["uf"].unique())) == 0


def test_fundos_estaduais():
    df = siconfi_estadual.fundos_estaduais()
    assert sorted(df["uf"].unique()) == ["GO", "MS", "MT"]
    # a alocação-base soma exatamente os R$ 3,5 bi da NT (antes da correção)
    base = (df.drop_duplicates("uf")["share_alocacao"]).sum()
    assert math.isclose(base, 1.0, abs_tol=1e-12)
    # correção §2º, II > 1 (ICMS nominal cresce ante a média 2021-2023)
    assert (df["variacao_icms"] > 1.0).all()
    assert (df["fundos_rs"] > 0).all()
    total_2024 = df[df.ano == 2024]["fundos_rs"].sum()
    assert 3.5e9 < total_2024 < 6e9            # 3,5 bi corrigidos p/ 2024


# ------------------------------------------------------------ combustíveis
def test_combustiveis_uf():
    df = combustiveis.combustiveis_uf()
    assert len(df) == 54
    assert ((df["share_do_icms"] > 0) & (df["share_do_icms"] < 0.6)).all()
    # ordem de grandeza nacional: gasolina ~45 bi L + diesel ~65 bi L + GLP
    # ~7,5 mi t × ad rem 2024 ⇒ dezenas de R$ bi (regressão de camada de dados)
    nac24 = df[df.ano == 2024]["receita_adrem_estimada"].sum() / 1e9
    assert 80.0 < nac24 < 200.0
    assert {"formula", "fonte"} <= set(df.columns)
