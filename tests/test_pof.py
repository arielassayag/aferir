"""Golden numbers e contratos da leitura POF 2017-2018 (aferir.inputs.pof).

Golden numbers exigidos pelo DESIGN §4:
 - aluguel estimado médio mensal por família = R$ 606,15 (IBGE SIDRA t/6970);
 - total de famílias = 69.017.704 (Σ PESO_FINAL por UC única);
 - Σ despesa por UF compatível com o derivado v1 (tolerância 0,1%), em
   comparação DIRETA: o artefato de duplicação do quadro 19 do v1 (o join
   com o Tradutor_Despesa_Geral explodia os códigos 19xxx, listados duas
   vezes no Tradutor — Habitação e Contribuições trabalhistas; a Memória de
   Cálculo IBGE aplica V8000_DEFLA UMA vez por registro) foi CORRIGIDO no
   v1 em 2026-07-10 (docs/correcao_dup_q19/RELATORIO_DECISAO.md).

Os testes leem as saídas processadas; se ausentes, constroem (lento ~4 min).
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from aferir.config import PROCESSED
from aferir.inputs.pof import CODIGO_ALUGUEL_IMPUTADO, constroi

# Paridade OPCIONAL contra o derivado v1 (fora deste repositório): ativa-se
# apontando AFERIR_V1_POF_DESPESA para o despesa_total.parquet do v1.
V1_DESPESA = Path(os.environ.get("AFERIR_V1_POF_DESPESA", "/nonexistent"))
MATRIZ_V5 = Path(__file__).resolve().parents[1] / "data" / "inputs" / "matriz_pof_ibs_v5.csv"


@pytest.fixture(scope="session")
def saidas() -> dict[str, pd.DataFrame]:
    caminhos = {
        "despesa_item_uf": PROCESSED / "pof_despesa_item_uf.parquet",
        "familias_uf": PROCESSED / "pof_familias_uf.csv",
        "decis_uf": PROCESSED / "pof_decis_uf.parquet",
    }
    if all(p.exists() for p in caminhos.values()):
        return {
            "despesa_item_uf": pd.read_parquet(caminhos["despesa_item_uf"]),
            "familias_uf": pd.read_csv(caminhos["familias_uf"]),
            "decis_uf": pd.read_parquet(caminhos["decis_uf"]),
        }
    return constroi(grava=True)


# ------------------------------------------------------------ golden numbers
def test_golden_total_familias(saidas):
    fam = saidas["familias_uf"]
    assert fam["uf"].nunique() == 27
    assert round(fam["familias"].sum()) == 69_017_704


def test_golden_aluguel_estimado_mensal(saidas):
    it = saidas["despesa_item_uf"]
    aluguel_anual = it.loc[it["codigo_pof"] == CODIGO_ALUGUEL_IMPUTADO,
                           "despesa_anual_rs"].sum()
    familias = saidas["familias_uf"]["familias"].sum()
    mensal = aluguel_anual / 12.0 / familias
    assert abs(mensal - 606.15) < 0.01, mensal  # IBGE SIDRA t/6970


# ------------------------------------------------------ compatibilidade v1
@pytest.mark.skipif(not V1_DESPESA.exists(),
                    reason="derivado v1 ausente (defina AFERIR_V1_POF_DESPESA)")
def test_despesa_uf_compativel_com_v1(saidas):
    """Σ por UF vs v1, tolerância 0,1% — comparação direta (espelho).

    O artefato de duplicação do quadro 19 (serviços domésticos; 20.554 =
    2×10.277 linhas por explosão do merge com o Tradutor) foi corrigido no
    v1 em 2026-07-10. O teste garante que os DOIS lados leem o quadro 19
    deduplicado (uma linha por registro do .txt bruto) antes de comparar.
    """
    v1 = pd.read_parquet(V1_DESPESA)
    q19 = (v1["origem"] == "despesa_coletiva") & (v1["V9001"] // 100000 == 19)
    # v1 corrigido: uma linha por registro do quadro 19 no bruto
    assert int(q19.sum()) == 10_277

    soma_v1 = v1.groupby("uf_sigla")["despesa_anual_pond"].sum()
    soma_v2 = saidas["despesa_item_uf"].groupby("uf")["despesa_anual_rs"].sum()
    cmp = pd.DataFrame({"v1": soma_v1, "v2": soma_v2})
    assert not cmp.isna().any().any()
    dif = (cmp["v2"] / cmp["v1"] - 1.0).abs()
    assert dif.max() < 1e-3, dif.sort_values().tail(3)


# ------------------------------------------------------------- matriz v5
def test_join_matriz_v5_cobre_99pct_da_despesa(saidas):
    it = saidas["despesa_item_uf"]
    matriz = pd.read_csv(MATRIZ_V5)
    codigos = set(matriz["codigo_pof"].astype("int64"))
    casada = it["codigo_pof"].isin(codigos)
    share = it.loc[casada, "despesa_anual_rs"].sum() / it["despesa_anual_rs"].sum()
    assert share >= 0.99, share  # medido: 1.0 (13.474 códigos cobrem tudo)


# ---------------------------------------------------------------- decis
def test_decis_estrutura_e_f_low(saidas):
    dec = saidas["decis_uf"]
    assert set(dec["decil_renda"]) == set(range(1, 11))
    assert dec["uf"].nunique() == 27
    assert len(dec) == 270
    assert (dec["despesa"] > 0).all()
    # f_low nacional (decis 1-3, ex-aluguel imputado): 0,0967 medido;
    # v1 (com o artefato quadro 19 no denominador) media 0,0950.
    f_low = dec.loc[dec["decil_renda"] <= 3, "despesa"].sum() / dec["despesa"].sum()
    assert 0.08 < f_low < 0.12, f_low
    # decis 1-3 gastam menos que 30% da despesa (desigualdade > uniforme)
    assert f_low < 0.30


def test_despesa_item_uf_contrato(saidas):
    it = saidas["despesa_item_uf"]
    assert list(it.columns) == ["codigo_pof", "uf", "despesa_anual_rs",
                                "formula", "fonte"]
    assert it["despesa_anual_rs"].ge(0).all()
    assert it["uf"].nunique() == 27
    # total anual ponderado (R$ de 15/01/2018): pin de regressão
    assert abs(it["despesa_anual_rs"].sum() / 3_577_442_550_121.15 - 1) < 1e-9
    # proveniência presente em todas as linhas
    assert it["formula"].notna().all() and it["fonte"].notna().all()
