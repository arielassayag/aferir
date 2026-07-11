"""Base potencial de destino B^ord por UF — SEM compras governamentais.

B^ord_uf = C_uf (consumo das famílias em campo, ex-combustíveis monofásicos)
         + ISFLSF_uf (por população)
         + FBCF_NC_uf (não-corporativa, m=1,00 — convenção legal art. 200 §4º)

Compras governamentais saíram da base ordinária: são o módulo do art. 473
(govpurchases.py), tributadas à alíquota combinada pós-redutor e destinadas
ao ente comprador.

Âncoras nacionais: TRU 2021 nível 68 (última detalhada — NÃO migrar p/ 2023),
escaladas ao biênio 2024-2025 pela variação NOMINAL da série própria de cada
âncora na SIDRA 1846: consumo das famílias (c93404) para C_fam e — proxy
declarado, ISFLSF não separável no SCN trimestral — para ISFLSF; FBCF
(c93406) para a FBCF. Distribuição por UF: shares da POF 2017-18 (em campo).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config
from .gaps import carrega_matriz
from .provenance import MANIFEST, Label, Num


@dataclass(frozen=True)
class AncorasNacionais:
    """Agregados TRU 2021 (R$ bi correntes de 2021) e escalas p/ o biênio."""

    c_familias_tru: float          # consumo das famílias, TRU 2021
    c_isflsf_tru: float            # consumo das ISFLSF, TRU 2021
    fbcf_tru: float                # FBCF total, TRU 2021
    share_fbcf_nc: float           # fração não-corporativa da FBCF (v1: VTI/PIA)
    escala_biênio: float           # C_fam nominal (média 2024-25) / C_fam 2021
    escala_biênio_fbcf: float      # FBCF nominal (média 2024-25) / FBCF 2021


def _shares_uf(despesa_item_uf: pd.DataFrame, itens_excluidos: set[str]) -> pd.Series:
    """Share de cada UF na despesa POF em campo (ex-itens excluídos)."""
    df = despesa_item_uf[~despesa_item_uf["codigo_pof"].isin(itens_excluidos)]
    por_uf = df.groupby("uf")["despesa_anual_rs"].sum()
    return por_uf / por_uf.sum()


def itens_fora_do_campo() -> set[str]:
    m = carrega_matriz()
    return set(m.loc[m["flag"] == "F", "codigo_pof"])


def itens_combustiveis(despesa_item_uf: pd.DataFrame) -> set[str]:
    """Códigos POF de combustíveis monofásicos (gasolina, etanol, diesel, GLP,
    gás veicular) — identificados pela descrição na matriz vendorada."""
    m = pd.read_csv(config.V2_ROOT / "data" / "inputs" / "matriz_pof_ibs_v5.csv",
                    dtype={"codigo_pof": str})
    desc = m["descricao_pof"].fillna("").str.upper()
    padrao = r"GASOLINA|ETANOL|ALCOOL PARA VEIC|OLEO DIESEL|GAS DE BOTIJAO|GLP|GAS VEICULAR|QUEROSENE"
    return set(m.loc[desc.str.contains(padrao, regex=True), "codigo_pof"])


# Produtos TRU 2021 removidos da âncora de consumo (remoção NO LADO TRU —
# a POF entra só na distribuição por UF e no π; remover shares POF da âncora
# TRU dupla-removeria impostos/contribuições que a TRU já não contém):
#   68002 Aluguel imputado           — fora do campo (art. 4º, convenção v5-22)
#   97001 Serviços domésticos        — fora do campo (art. 4º; família F da matriz)
#   19912 Gasoálcool, 19921 Etanol,
#   19916 Outros refino (GLP)        — monofásicos (art. 172; tratados à parte)
TRU_PRODUTOS_REMOVIDOS = ("68002", "97001", "19912", "19921", "19916")


def base_ordinaria_uf(
    despesa_item_uf: pd.DataFrame,
    populacao_uf: pd.Series,
    fbcf_nc_share_uf: pd.Series,
    ancoras: AncorasNacionais,
    tru_usos: pd.DataFrame,
    sifim: str = "incluido",
    fbcf_imob: str = "padrao",
    matriz: pd.DataFrame | None = None,
    sufixo_chave: str = "",
) -> pd.DataFrame:
    """B^ord por UF em R$ bi do biênio (preços 2024).

    Retorna [uf, B_C, B_ISFLSF, B_FBCF_NC, B_ord] com proveniência registrada.
    Consumo fora-do-campo residual (jogos, cerimônias etc. sem produto TRU
    próprio) permanece na âncora — vies declarado PARA BAIXO na alíquota.

    Alavancas ADITIVAS do E7 (defaults = comportamento vigente bit a bit;
    o flip do central é decisão do orquestrador):
      sifim='excluido'      — subtrai da âncora de consumo (nível TRU-2021,
        antes da escala) o SIFIM imputado às famílias estimado em
        data/processed/ajuste_sifim.csv (serviço imputado sem operação
        onerosa — fora do campo, LC 214, art. 4º); tarifas/juros/prêmios
        EXPLÍCITOS permanecem. Distribuição por UF inalterada (shares POF) —
        mesma convenção das remoções TRU_PRODUTOS_REMOVIDOS.
      fbcf_imob='redutores' — subtrai da âncora de FBCF não-corporativa
        (nível TRU-2021) o delta do art. 261 da LC 214 (alíquota reduzida em
        50% na parcela residencial nova) estimado em
        data/processed/ajuste_fbcf_imobiliaria.csv.
    """
    if sifim not in ("incluido", "excluido"):
        raise ValueError(f"sifim inválido: {sifim!r}")
    if fbcf_imob not in ("padrao", "redutores"):
        raise ValueError(f"fbcf_imob inválido: {fbcf_imob!r}")
    # matriz alternativa (E2, envelopes de classificação): a fronteira F
    # usada na distribuição por UF acompanha a matriz do cenário.
    if matriz is None:
        fora = itens_fora_do_campo()
    else:
        fora = set(matriz.loc[matriz["flag"] == "F", "codigo_pof"].astype(str))
    comb = itens_combustiveis(despesa_item_uf)

    t = tru_usos.assign(cod=tru_usos["produto_cod"].astype(str))
    removidos = t[t["cod"].isin(TRU_PRODUTOS_REMOVIDOS)]["consumo_familias"].sum()
    c_tru_liq = (ancoras.c_familias_tru - float(removidos) / 1e3)
    formula_bc = "[C_fam_TRU2021 − (68002 + 97001 + 19912 + 19921 + 19916)] × escala"
    chave_bc = "B_C_nacional" + sufixo_chave
    if sifim == "excluido":
        from .sifim_fbcf import carrega_ajuste_sifim
        sifim_bi = carrega_ajuste_sifim()
        c_fin = float(t.loc[t["cod"] == "64801", "consumo_familias"].sum()) / 1e3
        if not 0.0 <= sifim_bi <= c_fin:
            raise ValueError(f"SIFIM imputado ({sifim_bi:.1f} R$ bi) fora de "
                             f"[0; consumo 64801 = {c_fin:.1f}]")
        c_tru_liq -= sifim_bi
        formula_bc += " − SIFIM_imputado (ajuste_sifim.csv, nível 2021)"
        chave_bc = "B_C_nacional[sifim=excluido]" + sufixo_chave
    c_nacional = c_tru_liq * ancoras.escala_biênio
    MANIFEST.registra(
        chave_bc,
        Num(c_nacional,
            formula_bc,
            "TRU 2021 tab2 (remoções no lado TRU); escala SIDRA 1846",
            Label.DERIVADO, "R$ bi biênio"),
    )

    shares = _shares_uf(despesa_item_uf, fora | comb)
    pop = populacao_uf / populacao_uf.sum()
    # ISFLSF: proxy C_fam declarado (não separável no SCN trimestral);
    # FBCF: escala pela série PRÓPRIA (SIDRA 1846 c93406) — a escala C_fam
    # sobreestimava B_FBCF_NC (achado da banca; viés ↓ nas τ corrigido).
    isflsf_nacional = ancoras.c_isflsf_tru * ancoras.escala_biênio
    fbcf_nc_2021 = ancoras.fbcf_tru * ancoras.share_fbcf_nc
    if fbcf_imob == "redutores":
        from .sifim_fbcf import carrega_ajuste_fbcf
        delta_fbcf = carrega_ajuste_fbcf()
        if not 0.0 <= delta_fbcf < fbcf_nc_2021:
            raise ValueError(f"delta FBCF imobiliária ({delta_fbcf:.1f} R$ bi)"
                             f" fora de [0; FBCF_NC = {fbcf_nc_2021:.1f})")
        fbcf_nc_2021 -= delta_fbcf
        MANIFEST.registra(
            "B_FBCF_NC_nacional[fbcf_imob=redutores]" + sufixo_chave,
            Num(fbcf_nc_2021 * ancoras.escala_biênio_fbcf,
                "(FBCF_TRU × share_NC − delta_art261) × escala_fbcf",
                "ajuste_fbcf_imobiliaria.csv (LC 214, art. 261)",
                Label.DERIVADO, "R$ bi biênio"),
        )
    fbcf_nc_nacional = fbcf_nc_2021 * ancoras.escala_biênio_fbcf

    out = pd.DataFrame({
        "uf": sorted(config.UFS),
        "B_C": [c_nacional * shares.get(u, 0.0) for u in sorted(config.UFS)],
        "B_ISFLSF": [isflsf_nacional * pop.get(u, 0.0) for u in sorted(config.UFS)],
        "B_FBCF_NC": [fbcf_nc_nacional * fbcf_nc_share_uf.get(u, 0.0)
                      for u in sorted(config.UFS)],
    })
    out["B_ord"] = out[["B_C", "B_ISFLSF", "B_FBCF_NC"]].sum(axis=1)
    return out
