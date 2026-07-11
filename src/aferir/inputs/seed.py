"""Seed da camada de dados: constrói os insumos processados a partir dos raws
v1 (fontes abertas) e grava o manifesto de proveniência.

Execução:  PYTHONPATH=src python3 -m aferir.inputs.seed

Produtos (data/processed/):
  tru_2021_usos.parquet, tru_gov_carga.csv, r_estadual.csv, fecp_uf.csv,
  fundos_estaduais.csv, combustiveis_uf.csv, _seed_manifest.json.

Determinístico: mesmos seeds ⇒ mesmos bytes; nenhum datetime no cálculo
(o _seed_manifest.json registra sha256 dos arquivos lidos e a proveniência
dos números, sem timestamps).
"""
from __future__ import annotations

from aferir.config import JANELA_RECEITA, PROCESSED
from aferir.inputs.combustiveis import combustiveis_uf
from aferir.inputs.ipca_pib import deflator_para_2024
from aferir.inputs.siconfi_estadual import (
    fecp_uf,
    fundos_estaduais,
    grava_r_estadual_csv,
    paridade_v1_media_janela_Rbi,
)
from aferir.inputs.tru import grava_gov_carga_csv, grava_usos_parquet
from aferir.provenance import MANIFEST


def main() -> dict:
    """Roda todos os leitores e devolve os agregados-chave (para inspeção)."""
    for ano in JANELA_RECEITA:
        deflator_para_2024(ano)
    usos = grava_usos_parquet()
    carga = grava_gov_carga_csv()
    r_est = grava_r_estadual_csv()
    fecp = fecp_uf()
    fundos = fundos_estaduais()
    comb = combustiveis_uf()
    paridade = paridade_v1_media_janela_Rbi()

    PROCESSED.mkdir(parents=True, exist_ok=True)
    MANIFEST.grava(PROCESSED / "_seed_manifest.json")

    return {
        "deflator_2025_para_2024": deflator_para_2024(2025).valor,
        "paridade_v1_icms_media_janela_Rbi": paridade.valor,
        "carga_embutida_gov_central_pct": float(
            carga.loc[carga["cenario"] == "carga_embutida_gov_central_pct",
                      "carga_embutida_estimada_pct"].iloc[0]),
        "n_produtos_tru": len(usos),
        "n_linhas_r_estadual": len(r_est),
        "n_linhas_fecp": len(fecp),
        "fecp_total_2024_Rbi": float(
            fecp[fecp["ano"] == 2024]["fecp"].sum()) / 1e9,
        "fundos_total_2024_Rbi": float(
            fundos[fundos["ano"] == 2024]["fundos_rs"].sum()) / 1e9,
        "combustiveis_adrem_2024_Rbi": float(
            comb[comb["ano"] == 2024]["receita_adrem_estimada"].sum()) / 1e9,
        "n_arquivos_manifest": len(MANIFEST.arquivos),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(main(), ensure_ascii=False, indent=1))
