"""IPCA (SIDRA 1737) — deflatores da janela legal para R$ de 2024.

Leitor fino sobre data/raw/sidra/ipca_1737.parquet (número-índice
mensal, base dez/1993=100). Deflator(ano→2024) = média anual do índice em 2024
÷ média anual do índice no ano. Golden number (paridade v1, MANIFEST.toml):
deflator 2025→2024 = 0,952229023823.

Determinístico: nenhum datetime, nenhum acesso à rede.
"""
from __future__ import annotations

import functools

import pandas as pd

from aferir.config import ANO_PRECOS, RAW_IPCA_1737
from aferir.provenance import MANIFEST, Label, Num

_FONTE = ("IBGE SIDRA tabela 1737 (IPCA número-índice, base dez/1993=100), "
          "https://sidra.ibge.gov.br/tabela/1737; cache local "
          "data/raw/sidra/ipca_1737.parquet")


@functools.lru_cache(maxsize=1)
def _indices() -> pd.DataFrame:
    """Índice IPCA mensal → DataFrame[ano, indice]; registra o arquivo lido."""
    MANIFEST.registra_arquivo(RAW_IPCA_1737)
    df = pd.read_parquet(RAW_IPCA_1737)
    out = pd.DataFrame({
        # D3N = "janeiro 2013", "fevereiro 2013", ... — o ano é o 2º token
        "ano": df["D3N"].astype(str).str.split().str[1].astype(int),
        "indice": pd.to_numeric(df["V"], errors="coerce"),
    }).dropna()
    return out


def ipca_indice_medio(ano: int) -> Num:
    """Média anual do número-índice IPCA (12 meses exigidos)."""
    m = _indices()[lambda d: d["ano"] == ano]["indice"]
    if len(m) != 12:
        raise ValueError(f"IPCA {ano}: esperados 12 meses, obtidos {len(m)}")
    return MANIFEST.registra(
        f"ipca_indice_medio_{ano}",
        Num(float(m.mean()), f"média dos 12 números-índice mensais de {ano}",
            _FONTE, Label.DADO, "índice (dez/1993=100)"))


def deflator_para_2024(ano: int) -> Num:
    """Deflator multiplicativo que converte R$ correntes de `ano` em R$ de 2024."""
    base = ipca_indice_medio(ANO_PRECOS).valor
    ref = ipca_indice_medio(ano).valor
    return MANIFEST.registra(
        f"deflator_ipca_{ano}_para_{ANO_PRECOS}",
        Num(base / ref,
            f"IPCA_médio({ANO_PRECOS}) / IPCA_médio({ano})",
            _FONTE, Label.DERIVADO, f"R$ {ANO_PRECOS} por R$ {ano}"))
