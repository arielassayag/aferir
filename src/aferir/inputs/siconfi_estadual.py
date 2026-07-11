"""Receita de referência estadual — ICMS bruto, FECP e fundos art. 350, II, 'b'.

Fontes (data/raw, sha256 no _seed_manifest.json):
  * RREO Anexo 03, período 6, coluna TOTAL (ÚLTIMOS 12 MESES) — consolidação
    Data/raw/siconfi_2024_2025/icms_uf_2024_2025.csv (endpoint SICONFI aberto).
  * DCA Anexo I-C por UF/ano — Data/raw/siconfi/dca_{UF}_{ano}.parquet.

ACHADO DE CONCEITO (medido em 2026-07-10, 54/54 UF-anos, desvio 0,0%):
a rubrica RREO 'ICMSLiquidoExcetoTransferenciasEFUNDEB' é a arrecadação BRUTA
do ICMS (líquida apenas de restituições), ANTES da cota-parte municipal e da
dedução FUNDEB, e JÁ INCLUI o adicional FECP (ADCT art. 82, §1º). Identidade
exata: RREO ≡ DCA[1.1.1.4.50.1.0 + 1.1.1.4.50.2.0, Receitas Brutas Realizadas
− Outras Deduções da Receita]. Consequências:
  (i)  icms_bruto (art. 350, II, 'a' c/ §1º) = rubrica RREO DIRETAMENTE;
  (ii) FECP NÃO deve ser SOMADO ao numerador — já está dentro; o DCA fornece a
       DECOMPOSIÇÃO (conta separável 1.1.1.4.50.2.0 em 22 UFs) — achado C3:
       dados abertos bastam para separar o FECP até o nível de UF.

FUNDOS art. 350, II, 'b' (FETHAB-MT, FUNDERSUL-MS, FUNDEINFRA-GO): a NT SERT
de 01/07/2024 (p. 4) publica apenas o TOTAL de R$ 3,5 bi; nenhuma conta DCA
registra as contribuições (verificado: inexistem contas FETHAB/FUNDERSUL/
FUNDEINFRA nas receitas dos três estados) — fronteira OD/ADM. Alocação por UF
= CONVENÇÃO declarada (proporcional ao ICMS médio 2021-2023 do DCA), corrigida
ano a ano pela variação do ICMS da UF (art. 350, §2º, II).
"""
from __future__ import annotations

import functools

import pandas as pd

from aferir.config import (
    CONTA_FECP_POS2022,
    CONTA_ICMS_ATE2021,
    CONTA_ICMS_POS2022,
    FUNDOS_ESTADUAIS,
    FUNDOS_ESTADUAIS_TOTAL_RS,
    FUNDOS_JANELA_BASE,
    JANELA_RECEITA,
    NT_SERT_JUL2024_PAGINA_FUNDOS,
    NT_SERT_JUL2024_URL,
    PROCESSED,
    RAW_DCA_ESTADUAL_DIR,
    RAW_RREO_ICMS_CSV,
    UFS,
)
from aferir.inputs.ipca_pib import deflator_para_2024
from aferir.provenance import MANIFEST, Label, Num

_FONTE_RREO = ("SICONFI RREO Anexo 03, período 6, coluna TOTAL (ÚLTIMOS 12 "
               "MESES), R$ correntes; apidatalake.tesouro.gov.br/ords/siconfi/"
               "tt/rreo; cache local data/raw/siconfi_rreo/icms_uf_2024_2025.csv")
_FONTE_DCA = ("SICONFI DCA Anexo I-C; apidatalake.tesouro.gov.br/ords/siconfi/"
              "tt/dca; cache local data/raw/siconfi_estadual/dca_{UF}_{ano}.parquet")
_TOL_TRIANGULACAO_PCT = 0.1     # invariante: RREO ≡ DCA (medido 0,0%)


@functools.lru_cache(maxsize=1)
def _rreo() -> pd.DataFrame:
    MANIFEST.registra_arquivo(RAW_RREO_ICMS_CSV)
    return pd.read_csv(RAW_RREO_ICMS_CSV)


@functools.lru_cache(maxsize=None)
def _dca(uf: str, ano: int) -> pd.DataFrame:
    path = RAW_DCA_ESTADUAL_DIR / f"dca_{uf}_{ano}.parquet"
    MANIFEST.registra_arquivo(path)
    df = pd.read_parquet(path)
    return df[df["anexo"] == "DCA-Anexo I-C"]


def _dca_valor(uf: str, ano: int, conta: str, coluna: str) -> float:
    ic = _dca(uf, ano)
    sel = ic[(ic["cod_conta"].astype(str).str.contains(conta, regex=False))
             & (ic["coluna"] == coluna)]["valor"]
    return float(sel.sum())


# --------------------------------------------------------------------------- #
# r_estadual.csv — ICMS bruto por UF/ano (numerador art. 350, II, 'a' + §1º)
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=1)
def r_estadual() -> pd.DataFrame:
    """ICMS bruto por UF e ano da janela, com triangulação RREO×DCA embutida."""
    linhas = []
    conta_icms, conta_fecp = CONTA_ICMS_POS2022, CONTA_FECP_POS2022
    for _, row in _rreo().sort_values(["uf", "ano"]).iterrows():
        uf, ano = str(row["uf"]), int(row["ano"])
        rreo_bruto = float(row["icms_liquido_ex_fundeb_cotaparte_rs"])
        dca_icms = _dca_valor(uf, ano, conta_icms, "Receitas Brutas Realizadas")
        dca_fecp = _dca_valor(uf, ano, conta_fecp, "Receitas Brutas Realizadas")
        dca_outras = (_dca_valor(uf, ano, conta_icms, "Outras Deduções da Receita")
                      + _dca_valor(uf, ano, conta_fecp, "Outras Deduções da Receita"))
        dca_comparavel = dca_icms + dca_fecp - dca_outras
        desvio_pct = (rreo_bruto - dca_comparavel) / dca_comparavel * 100.0
        if abs(desvio_pct) > _TOL_TRIANGULACAO_PCT:
            raise AssertionError(
                f"triangulação RREO×DCA {uf} {ano}: desvio {desvio_pct:.3f}% "
                f"> {_TOL_TRIANGULACAO_PCT}% — conceito quebrou")
        linhas.append({
            "uf": uf, "ano": ano,
            "icms_bruto": rreo_bruto,
            "deducao_fundeb_rreo": float(row["deducao_fundeb_total_rs"]),
            "iss_df": (float(row["iss_liquido_ex_fundeb_rs"])
                       if uf == "DF" and pd.notna(row["iss_liquido_ex_fundeb_rs"])
                       else 0.0),
            "dca_icms_bruta": dca_icms,
            "dca_fecp_bruta": dca_fecp,
            "dca_outras_deducoes": dca_outras,
            "desvio_rreo_dca_pct": desvio_pct,
            "formula": ("icms_bruto = rubrica RREO 'ICMSLiquidoExcetoTransferencias"
                        "EFUNDEB' (arrecadação bruta líquida de restituições, antes "
                        "de FUNDEB/cota-parte, INCLUI FECP); triangulação: ≡ "
                        f"DCA[{conta_icms}+{conta_fecp}, Brutas − Outras Deduções]"),
            "fonte": f"{_FONTE_RREO} | {_FONTE_DCA}",
        })
    df = pd.DataFrame(linhas)
    if sorted(df["uf"].unique()) != sorted(UFS) or len(df) != 2 * len(UFS):
        raise AssertionError("r_estadual: esperadas 27 UFs × 2 anos")
    return df


def grava_r_estadual_csv() -> pd.DataFrame:
    df = r_estadual()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "r_estadual.csv", index=False)
    return df


def paridade_v1_media_janela_Rbi() -> Num:
    """Golden de paridade com o v1: média da janela 2024-2025 (R$ bi de 2024)
    de Σ_uf [ICMS bruto (+ ISS do DF, convenção v1)], 2025 deflacionado.

    Reproduz o agregado 'R_full' do v1 (revenue_target.csv): ≈ 818,48 R$ bi.
    NÃO é o numerador do v2 (que separa o ISS-DF para a esfera municipal);
    serve como teste de que a camada de dados reproduz o v1 byte a byte.
    """
    df = r_estadual()
    d = {ano: deflator_para_2024(ano).valor for ano in JANELA_RECEITA}
    soma_por_ano = {
        ano: float(((df[df["ano"] == ano]["icms_bruto"]
                     + df[df["ano"] == ano]["iss_df"]) * d[ano]).sum()) / 1e9
        for ano in JANELA_RECEITA
    }
    media = sum(soma_por_ano.values()) / len(soma_por_ano)
    return MANIFEST.registra(
        "paridade_v1_icms_media_janela_Rbi",
        Num(media,
            "média{ano∈2024,2025} Σ_uf (icms_bruto + iss_df)·deflator_IPCA(ano→2024)",
            f"{_FONTE_RREO}; deflatores SIDRA 1737", Label.DERIVADO, "R$ bi 2024"))


# --------------------------------------------------------------------------- #
# fecp_uf.csv — decomposição do FECP (ADCT art. 82, §1º) via DCA
# --------------------------------------------------------------------------- #
def fecp_uf() -> pd.DataFrame:
    """FECP por UF/ano onde a conta é separável no DCA (22 UFs na janela).

    fecp = Receitas Brutas Realizadas − Outras Deduções da Receita (convenção
    de coluna idêntica à do ISS municipal no DESIGN §2.3; a dedução-FUNDEB é
    destinação, não redução de arrecadação). O FECP já está DENTRO da rubrica
    RREO usada em icms_bruto — este CSV decompõe, não adiciona.
    """
    linhas = []
    for uf in sorted(UFS):
        for ano in JANELA_RECEITA:
            bruta = _dca_valor(uf, ano, CONTA_FECP_POS2022,
                               "Receitas Brutas Realizadas")
            if bruta == 0.0:
                continue    # conta inexistente na UF (não separável / sem FECP)
            outras = _dca_valor(uf, ano, CONTA_FECP_POS2022,
                                "Outras Deduções da Receita")
            fundeb = _dca_valor(uf, ano, CONTA_FECP_POS2022, "Deduções - FUNDEB")
            linhas.append({
                "uf": uf, "ano": ano,
                "fecp": bruta - outras,
                "fecp_bruta": bruta,
                "deducao_fundeb": fundeb,
                "outras_deducoes": outras,
                "conta": f"{CONTA_FECP_POS2022} - Adicional ICMS - Fundo "
                         "Estadual de Combate à Pobreza (DCA Anexo I-C)",
                "formula": "fecp = Receitas Brutas Realizadas − Outras Deduções "
                           "da Receita (ADCT art. 82, §1º; já contido em "
                           "icms_bruto — decomposição, não adição)",
                "fonte": _FONTE_DCA,
            })
    df = pd.DataFrame(linhas)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "fecp_uf.csv", index=False)
    return df


# --------------------------------------------------------------------------- #
# fundos_estaduais.csv — art. 350, II, 'b' e §2º, II
# --------------------------------------------------------------------------- #
def _icms_dca_bruta(uf: str, ano: int) -> float:
    """ICMS (principal, conta consolidada) bruto no DCA, cobrindo a quebra de
    ementário 2021→2022."""
    conta = CONTA_ICMS_ATE2021 if ano <= 2021 else CONTA_ICMS_POS2022
    v = _dca_valor(uf, ano, conta, "Receitas Brutas Realizadas")
    if v <= 0:
        raise ValueError(f"ICMS DCA {uf} {ano} ausente (conta {conta})")
    return v


def fundos_estaduais() -> pd.DataFrame:
    """Fundos estaduais condicionais valorados por UF/ano da janela.

    valor(uf, ano) = TOTAL_NT × share_uf × [ICMS_uf(ano) / ICMS_uf(média 2021-23)]
      * TOTAL_NT = R$ 3,5 bi (OFICIAL — NT SERT 01/07/2024, p. 4, URL na fonte);
      * share_uf = ICMS_uf médio 2021-2023 ÷ Σ_{MT,MS,GO} (CONVENÇÃO declarada:
        a NT não publica a decomposição por fundo — fronteira OD/ADM);
      * correção pela variação do ICMS da UF = art. 350, §2º, II.
    """
    icms_medio = {
        uf: sum(_icms_dca_bruta(uf, a) for a in FUNDOS_JANELA_BASE)
        / len(FUNDOS_JANELA_BASE)
        for uf in sorted(FUNDOS_ESTADUAIS)
    }
    total_medio = sum(icms_medio.values())
    linhas = []
    for uf in sorted(FUNDOS_ESTADUAIS):
        share = icms_medio[uf] / total_medio
        for ano in JANELA_RECEITA:
            variacao = _icms_dca_bruta(uf, ano) / icms_medio[uf]
            valor = FUNDOS_ESTADUAIS_TOTAL_RS * share * variacao
            linhas.append({
                "uf": uf, "ano": ano,
                "fundo": FUNDOS_ESTADUAIS[uf],
                "fundos_rs": valor,
                "share_alocacao": share,
                "icms_medio_2021_2023": icms_medio[uf],
                "variacao_icms": variacao,
                "natureza": "OFICIAL (total) × CONVENCAO (alocação por UF) × "
                            "DERIVADO (correção §2º, II)",
                "formula": ("fundos_rs = 3,5e9 × [ICMS_uf médio 2021-2023 ÷ "
                            "Σ_{MT,MS,GO}] × [ICMS_uf(ano) ÷ ICMS_uf(média "
                            "2021-2023)]; ICMS = DCA Receitas Brutas Realizadas "
                            f"(contas {CONTA_ICMS_ATE2021}/{CONTA_ICMS_POS2022})"),
                "fonte": (f"Total: NT SERT/MF 01/07/2024, p. "
                          f"{NT_SERT_JUL2024_PAGINA_FUNDOS} ({NT_SERT_JUL2024_URL}); "
                          f"correção: LC 214/2025, art. 350, §2º, II; ICMS: "
                          f"{_FONTE_DCA}. FRONTEIRA OD/ADM: decomposição por "
                          "fundo não publicada na NT nem separável no DCA — "
                          "alocação proporcional ao ICMS é convenção declarada."),
            })
    df = pd.DataFrame(linhas)
    MANIFEST.registra(
        "fundos_estaduais_total_base_rs",
        Num(FUNDOS_ESTADUAIS_TOTAL_RS,
            "soma FETHAB-MT + FUNDERSUL-MS (base 2018) + FUNDEINFRA-GO "
            "(2023, deflacionado IPCA) — transcrição literal",
            f"NT SERT/MF 01/07/2024, p. {NT_SERT_JUL2024_PAGINA_FUNDOS} "
            f"({NT_SERT_JUL2024_URL})", Label.OFICIAL, "R$"))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "fundos_estaduais.csv", index=False)
    return df
