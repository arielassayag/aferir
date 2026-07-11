"""Compras governamentais (LC 214, arts. 472-473) — leitura e convenções.

Perímetros de G (revisão A5; elementos da Portaria Interm. STN/SOF 163/2001):
  * min     = 3.3.90.{30,39};
  * central = 3.3.90.{30,32,33,37,39,40} — CENTRAL do artigo, COM a natureza
    36 (chave `natureza36`: serviços de PF podem estar fora do campo IBS/CBS);
  * max     = central + 4.4.90.{51,52} (obras e equipamentos).
Grade completa em `g_perimetros.csv` (União: DCA id_ente=1; Estados: DCA das
27 UFs; Municípios: amostra capitais+top-200 com extrapolação
pós-estratificada — estágio 'liquidadas' municipal = amostra sem
extrapolação, cota inferior declarada). `g_esferas.csv` espelha o central.

Redutor do art. 370 (⚑ F8): modo iso-carga usa σ̂ por perímetro
(`sigma_compras.csv`): custeio = carga embutida no mix do CI das atividades
de governo (TRU 2021) = 8,234%; capital (só no perímetro max) = t_embutida
dos produtos de FBCF (construção p/ 51, máquinas p/ 52) ponderada pela
composição de G.
"""
from __future__ import annotations

import pandas as pd

from . import config


def deflaciona_media_janela(df: pd.DataFrame, col: str, deflator_2025: float,
                            por: list[str],
                            janela: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Média da janela em R$ de 2024. Default (janela=None) = 2024-2025:
    (v2024 + v2025·δ)/2. janela=(2024,) = sensibilidade A6 (peça DCA
    ratificada de 2024 apenas; 2025 sai do alvo)."""
    anos = list(janela) if janela is not None else list(config.JANELA_RECEITA)
    wide = df.pivot_table(index=por, columns="ano", values=col, aggfunc="sum")
    faltantes = [a for a in anos if a not in wide.columns]
    if faltantes:
        raise ValueError(f"janela incompleta em {col}: faltam {faltantes}")
    acum = wide[2024].copy() if 2024 in anos else 0.0 * wide[anos[0]]
    if 2025 in anos:
        acum = acum + wide[2025] * deflator_2025
    out = (acum / len(anos)).rename(col)
    return out.reset_index()


def media_janela_serie(por_ano: "pd.Series", deflator_2025: float,
                       janela: tuple[int, ...] | None = None) -> float:
    """Média deflacionada de uma série indexada por ano (mesma convenção de
    deflaciona_media_janela, para séries já agregadas)."""
    anos = list(janela) if janela is not None else list(config.JANELA_RECEITA)
    total = 0.0
    for ano in anos:
        total += float(por_ano[ano]) * (deflator_2025 if ano == 2025 else 1.0)
    return total / len(anos)


def g_por_esfera_uf(deflator_2025: float, perimetro: str = "central",
                    natureza36: bool = True, estagio: str = "empenhadas",
                    janela: tuple[int, ...] | None = None,
                    ) -> dict[str, pd.Series | float]:
    """G_s na janela (R$ BILHÕES de 2024): União escalar; estadual/municipal por UF.

    Default (perimetro='central', natureza36=True, estagio='empenhadas') =
    NOVO central do artigo (revisão A5). Chamadas antigas sem argumento
    continuam válidas e passam a refletir o perímetro ampliado.

    Municípios: o total BR é distribuído por UF pela POPULAÇÃO municipal
    (convenção declarada — a extrapolação da amostra é per-capita por estrato;
    sensibilidade pela receita entra no corredor S1/S2). No estágio
    'liquidadas' o total municipal é a amostra sem extrapolação (cota
    inferior declarada em g_perimetros.csv).
    """
    g = pd.read_csv(config.PROCESSED / "g_perimetros.csv")
    chave36 = "com36" if natureza36 else "sem36"
    anos = list(janela) if janela is not None else list(config.JANELA_RECEITA)
    g = g[(g["ano"].isin(anos))
          & (g["perimetro"] == perimetro)
          & (g["natureza36"] == chave36)
          & (g["estagio"] == estagio)]
    if g.empty:
        raise ValueError(
            f"g_perimetros.csv sem células para perimetro={perimetro!r}, "
            f"natureza36={chave36!r}, estagio={estagio!r}")

    BI = 1e9
    uniao = deflaciona_media_janela(g[g.esfera == "uniao"], "valor_rs",
                                    deflator_2025, ["esfera"], janela)
    g_u = float(uniao["valor_rs"].iloc[0]) / BI

    est = deflaciona_media_janela(g[g.esfera == "estadual"], "valor_rs",
                                  deflator_2025, ["uf"], janela)
    g_e = est.set_index("uf")["valor_rs"] / BI

    mun_total = deflaciona_media_janela(g[g.esfera == "municipal"],
                                        "valor_rs", deflator_2025,
                                        ["esfera"], janela)
    # DF fora da distribuição: o G de Brasília está no DCA único do GDF
    # (esfera estadual; art. 349, II, 'c') e o total municipal medido o exclui.
    pop = populacao_municipal_uf().drop("DF", errors="ignore")
    g_m = (pop / pop.sum()) * float(mun_total["valor_rs"].iloc[0]) / BI
    g_m["DF"] = 0.0
    return {"uniao": g_u, "estadual": g_e, "municipal": g_m.sort_index()}


def populacao_municipal_uf() -> pd.Series:
    entes = pd.read_parquet(config.RAW / "siconfi_municipal" / "entes.parquet")
    mun = entes[entes["esfera"] == "M"]
    return mun.groupby("uf")["populacao"].sum().astype(float)


def sigma_iso_carga(perimetro: str = "central") -> float:
    """σ̂ do redutor iso-carga (art. 370) coerente com o perímetro de G.

    min/central: σ_custeio (TRU 2021, mix CI do governo geral — valor
    idêntico ao σ̂ histórico de 8,234%); max: mistura custeio × capital
    (sigma_compras.csv, revisão A5)."""
    t = pd.read_csv(config.PROCESSED / "sigma_compras.csv")
    linha = t[t["perimetro"] == perimetro]
    if linha.empty:
        raise ValueError(f"sigma_compras.csv sem linha para {perimetro!r}")
    return float(linha["sigma"].iloc[0])
