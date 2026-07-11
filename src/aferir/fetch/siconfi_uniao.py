"""Fetcher SICONFI — DCA da UNIÃO (id_ente=1), Anexo I-D (despesa por natureza).

Insumo do módulo de compras governamentais (LC 214, arts. 472-473): naturezas
de AQUISIÇÃO 3.3.90.30 (material de consumo), 3.3.90.36 (serviços PF) e
3.3.90.39 (serviços PJ) — folha fora do campo (art. 4º).

Operação:
  * paginação ORDS OBRIGATÓRIA: o Anexo I-D da União tem >5.000 linhas
    (limite por página); percorre offset até hasMore=False;
  * idempotente: data/raw/siconfi_uniao/dca_uniao_{ano}_ID.parquet; _meta.json
    com url, sha256, collected_at (datetime SÓ aqui);
  * anos: JANELA_RECEITA (2024-2025; 2025 verificado disponível em 10/07/2026).

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_uniao
"""
from __future__ import annotations

import pandas as pd

from aferir.config import (
    COD_IBGE_UNIAO,
    DCA_ANEXO_DESPESA,
    JANELA_RECEITA,
    RAW,
    SICONFI_API,
)
from aferir.fetch.siconfi_comum import (
    atualiza_meta,
    get_items_paginado,
    grava_parquet_atomico,
)

RAW_DIR = RAW / "siconfi_uniao"


def caminho_dca_uniao(ano: int):
    return RAW_DIR / f"dca_uniao_{ano}_ID.parquet"


def fetch_dca_uniao(ano: int) -> pd.DataFrame:
    """DCA Anexo I-D da União no exercício `ano` (todas as colunas/estágios)."""
    path = caminho_dca_uniao(ano)
    if path.exists():
        return pd.read_parquet(path)
    params = {
        "an_exercicio": ano,
        "no_anexo": DCA_ANEXO_DESPESA,
        "id_ente": COD_IBGE_UNIAO,
    }
    items, paginas = get_items_paginado("dca", params)
    if not items:
        raise ValueError(f"DCA União {ano} ({DCA_ANEXO_DESPESA}): API vazia")
    df = (
        pd.DataFrame(items)
        .sort_values(["cod_conta", "coluna"])
        .reset_index(drop=True)
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    grava_parquet_atomico(df, path)
    atualiza_meta(
        RAW_DIR,
        endpoint_dca=(
            f"{SICONFI_API}/dca?an_exercicio={{ano}}"
            f"&no_anexo={DCA_ANEXO_DESPESA}&id_ente={COD_IBGE_UNIAO}"
        ),
        **{f"n_itens_{ano}": len(df), f"n_paginas_{ano}": paginas},
    )
    return df


def main() -> None:
    for ano in JANELA_RECEITA:
        df = fetch_dca_uniao(ano)
        print(f"[uniao {ano}] {len(df)} linhas (Anexo I-D)", flush=True)


if __name__ == "__main__":
    main()
