"""Distribuição LEGAL do produto do IBS em 2033 — quem recebe o quê.

Responde, no sentido juridicamente correto, à pergunta "todos os entes
respeitam o piso de 90,5%?": em 2033 a receita de cada ente NÃO é
τ_s·D_uf (esse é o contrafactual de plena destinação, pós-2077, dos
vetores indicativos), e sim o resultado da cadeia de distribuição da
transição federativa. Cadeia legal implementada (texto literal em
References/legal/ do v1):

  1. RETENÇÃO (ADCT art. 131, §1º, II; LC 227 art. 109, II): 90% do
     produto de cada ente apurado às alíquotas de referência, ANTES da
     cota-parte do art. 158, IV, 'b', é retido e distribuído a TODOS os
     entes (pool único E+DF+M) proporcionalmente à receita média de
     referência (LC 227 art. 114, §1º).
  2. RECEITA MÉDIA (LC 227 art. 115): valores anuais 2019-2026,
     corrigidos até 2026 pela variação nominal da arrecadação nacional
     ICMS+ISS (§2º). Componentes: Estados = ICMS após o art. 158, IV,
     'a' (75%) + fundos estaduais (art. 115, I, 'b'; §3º); DF = ICMS +
     ISS (inciso II); Municípios = ISS + cota-parte recebida (25% do
     ICMS; inciso III). §1º inclui Simples, adicional FECP (ADCT 82) e
     multas/dívida ativa. Pela ADCT 82, §1º (destinação integral ao
     fundo), o adicional FECP entra a 100% no estado e FORA da base da
     cota-parte — convenção declarada.
  3. SEGURO-RECEITA (ADCT art. 132; LC 227 arts. 110 e 117): 5% do
     produto APÓS a retenção (⇒ 0,5% do produto em 2033) distribuído
     sequencial e sucessivamente aos entes com as MENORES razões entre
     (i) produto às alíquotas de referência pós-art. 158, IV, 'b' e
     (ii) receita média ajustada (≤ 3× a média per capita da esfera,
     §§3º-6º), nivelando as razões por baixo (water-filling exato do
     §1º do art. 117).
  4. DESTINO: o restante (9,5% do produto em 2033) segue o regime de
     destino (ADCT 131, §4º) — proxy declarado: shares da base de
     destino B^ord (base_uf.csv).
  5. COTA-PARTE MUNICIPAL DO IBS (CF 158, IV, 'b'; LC 227/2026, art. 128):
     25% da parcela-destino dos estados vai aos municípios da própria
     UF. NÃO incide sobre a parcela retida dos estados (ADCT 131, §3º)
     nem sobre o seguro (que nivela razões já pós-cota — convenção
     declarada). Critérios do art. 128 (80% população, 10% educação,
     5% ambiental, 5% igualitário) só redistribuem DENTRO da UF —
     inertes no nível UF deste exercício (declarado).

Convenções adicionais declaradas (todas com direção/materialidade):
  * Produto distribuído = receita de referência CHEIA da esfera na
    janela 2024-25 deflacionada (E: ICMS bruto + fundos; M: ISS com
    DF): às alíquotas de referência a reposição nacional é exata por
    construção; o bloco monofásico de combustíveis é reposto pelo ad
    rem simétrico e viaja DENTRO do produto (as receitas médias legais
    usam o ICMS cheio — simetria mantida).
  * Nível UF: municípios agregados por UF (POF/base param na UF); o
    cap de 3× per capita do seguro é aplicado ao agregado — no nível
    municipal individual seria mais apertado (fronteira declarada).
  * Janela disponível 2019-2025 (lei: 2019-2026; 2026 inexistente em
    jul/2026). Correção do art. 115, §2º, II feita até 2025.
  * ISS municipal 2019-2023: subamostra aleatória v1 (2.844 entes)
    expandida por razão UF a UF ancorada no universo 2024 (estimador
    de razão); 8 UFs sem amostra (AL/CE/GO/MS/MT/PE/RN/SE) retropolam
    pelo índice nacional do ISS estimado (declarado no CSV, coluna
    `iss_mun_origem`). O componente ISS é minoritário na receita média
    municipal (a cota-parte, medida no lado estadual completo, domina).
  * População: universo municipal SICONFI (/entes), vintage única —
    proxy da média 2019-2026 do art. 117, §§3º-4º (a lei manda usar as
    estimativas mais recentes do IBGE; §7º).

Executar: PYTHONPATH=src python3 -m aferir.distribuicao
Saídas em data/processed/: distribuicao_2033.csv (27 UF × esfera E/M),
distribuicao_2033_metricas.csv, distribuicao_rm_historica.csv.
Determinístico: nenhuma fonte de aleatoriedade; reexecução byte-idêntica.
"""
from __future__ import annotations

import functools
import glob

import pandas as pd

from . import config, revenue
from .govpurchases import deflaciona_media_janela, populacao_municipal_uf
from .inputs.siconfi_estadual import _dca_valor
from .provenance import MANIFEST, Label, Num

BI = 1e9

_FONTE_LEGAL = ("EC 132/2023, ADCT arts. 131-132; LC 227/2026, arts. 104-117; "
                "CF art. 158, IV; LC 227/2026, art. 128")
_FONTE_DCA_UF = ("SICONFI DCA Anexo I-C estadual (data/raw/siconfi_estadual/"
                 "dca_{UF}_{ano}.parquet; apidatalake.tesouro.gov.br)")
_FONTE_DCA_MUN = ("SICONFI DCA Anexo I-C municipal (subamostra fixada dca_mun_*, "
                  "2.844 entes, 2019-2023; universo 2024-2025 em "
                  "data/raw/siconfi_municipal/)")

# esfera municipal: conta ISS por geração do ementário (quebra 2021→2022)
_CONTA_ISS = {True: config.CONTA_ISS_ATE2021, False: config.CONTA_ISS_POS2022}
_CONTA_ICMS = {True: config.CONTA_ICMS_ATE2021, False: config.CONTA_ICMS_POS2022}
_CONTA_FECP = {True: config.CONTA_FECP_ATE2021, False: config.CONTA_FECP_POS2022}

# UFs sem NENHUM ente na subamostra municipal v1 2018-2023 (fato do cache,
# medido em 2026-07-10) — ISS 2019-2023 retropolado pelo índice nacional.
UFS_SEM_AMOSTRA_MUN = ("AL", "CE", "GO", "MS", "MT", "PE", "RN", "SE")


# --------------------------------------------------------------------------- #
# 1. Histórico de arrecadação 2019-2025 (insumo da receita média, art. 115)
# --------------------------------------------------------------------------- #
def _liquida(uf: str, ano: int, conta: str) -> float:
    """Receitas Brutas Realizadas − Outras Deduções (convenção do DESIGN §2.3)."""
    return (_dca_valor(uf, ano, conta, "Receitas Brutas Realizadas")
            - _dca_valor(uf, ano, conta, "Outras Deduções da Receita"))


@functools.lru_cache(maxsize=1)
def _iss_amostra_por_uf() -> pd.DataFrame:
    """ISS líquido da subamostra municipal v1 por UF×ano (2019-2023) e o
    conjunto de entes presentes, para o estimador de razão ancorado em 2024."""
    linhas = []
    for ano in [a for a in config.JANELA_RECEITA_MEDIA if a <= 2023]:
        conta = _CONTA_ISS[ano <= 2021]
        for path in sorted(glob.glob(
                str(config.RAW_DCA_MUN_DIR / f"dca_mun_*_{ano}.parquet"))):
            d = pd.read_parquet(
                path, columns=["uf", "cod_ibge", "cod_conta", "coluna", "valor"])
            sub = d[d["cod_conta"].astype(str).str.contains(conta, regex=False)]
            if not len(sub):
                continue
            br = sub[sub["coluna"] == "Receitas Brutas Realizadas"]["valor"].sum()
            od = sub[sub["coluna"] == "Outras Deduções da Receita"]["valor"].sum()
            linhas.append({"ano": ano, "uf": str(d["uf"].iloc[0]),
                           "cod_ibge": int(d["cod_ibge"].iloc[0]),
                           "iss_liquida": float(br - od)})
    return pd.DataFrame(linhas)


@functools.lru_cache(maxsize=1)
def _painel_2024_ex_df() -> pd.DataFrame:
    p = pd.read_parquet(config.PROCESSED / "iss_municipio_2024.parquet")
    return p[p["uf"] != "DF"]


def _iss_municipal_historico() -> pd.DataFrame:
    """ISS municipal por UF×ano (ex-DF), 2019-2025.

    2024-2025: universo completo (r_municipal_uf.csv, declarantes — central).
    2019-2023: estimador de razão — Σ_amostra(uf, ano) × [ISS_universo(uf, 2024)
    ÷ ISS_2024 dos MESMOS entes da amostra] — corrige a subcobertura da
    subamostra (ex.: SP capital fora dela). 8 UFs sem amostra retropolam por
    ISS(uf, 2024) × índice nacional do ISS estimado (Σ 18 UFs amostradas).
    """
    rm = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    rm = rm[rm["uf"] != "DF"]
    univ = {int(a): g.set_index("uf")["iss_liquida"]
            for a, g in rm.groupby("ano")}
    p24 = _painel_2024_ex_df()
    amostra = _iss_amostra_por_uf()

    linhas = []
    for ano in config.JANELA_RECEITA_MEDIA:
        if ano in univ:                                   # 2024-2025: universo
            for uf, v in univ[ano].items():
                linhas.append({"ano": ano, "uf": uf, "iss_mun": float(v),
                               "iss_mun_origem": "universo_dca"})
            continue
        am = amostra[amostra["ano"] == ano]
        est = {}
        for uf, g in am.groupby("uf"):
            base24 = p24[p24["cod_ibge"].isin(set(g["cod_ibge"]))]["iss_liquida"].sum()
            if base24 <= 0:
                continue
            razao = float(univ[2024][uf]) / float(base24)
            est[uf] = float(g["iss_liquida"].sum()) * razao
        idx_nacional = (sum(est.values())
                        / float(univ[2024].reindex(sorted(est)).sum()))
        for uf in sorted(univ[2024].index):
            if uf in est:
                linhas.append({"ano": ano, "uf": uf, "iss_mun": est[uf],
                               "iss_mun_origem": "amostra_razao_2024"})
            else:
                linhas.append({"ano": ano, "uf": uf,
                               "iss_mun": float(univ[2024][uf]) * idx_nacional,
                               "iss_mun_origem": "retropolado_indice_nacional"})
    df = pd.DataFrame(linhas)
    faltam = {(a, u) for a in config.JANELA_RECEITA_MEDIA
              for u in config.UFS if u != "DF"} \
        - set(zip(df["ano"], df["uf"]))
    if faltam:
        raise AssertionError(f"ISS municipal histórico incompleto: {faltam}")
    return df


@functools.lru_cache(maxsize=1)
def historico_receitas() -> pd.DataFrame:
    """ICMS (principal, líquido), FECP e ISS por UF×ano, 2019-2025, correntes.

    ICMS/FECP: DCA estadual (contas por geração do ementário); ISS: DCA
    municipal (ver _iss_municipal_historico) e, no DF, a conta ISS da DCA
    única do GDF (art. 349, II, 'c').
    """
    iss_mun = _iss_municipal_historico().set_index(["uf", "ano"])
    linhas = []
    for uf in sorted(config.UFS):
        for ano in config.JANELA_RECEITA_MEDIA:
            antigo = ano <= 2021
            icms = _liquida(uf, ano, _CONTA_ICMS[antigo])
            fecp = _liquida(uf, ano, _CONTA_FECP[antigo])
            if icms <= 0:
                raise ValueError(f"ICMS DCA ausente: {uf} {ano}")
            if uf == "DF":
                iss, origem = _liquida(uf, ano, _CONTA_ISS[antigo]), "dca_gdf"
            else:
                r = iss_mun.loc[(uf, ano)]
                iss, origem = float(r["iss_mun"]), str(r["iss_mun_origem"])
            linhas.append({"uf": uf, "ano": ano, "icms_liq": icms,
                           "fecp_liq": fecp, "iss_mun": iss,
                           "iss_mun_origem": origem})
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------- #
# 2. Receita média de referência (art. 115) e coeficientes (art. 114, §1º)
# --------------------------------------------------------------------------- #
def receita_media() -> pd.DataFrame:
    """Receita média de referência por UF×esfera (unidades: R$ corrigidos a
    2025 pelo art. 115, §2º, II — os coeficientes e o seguro são invariantes
    a escala, então a unidade não propaga).

    E (ex-DF) = média_ano f_ano·(0,75·ICMS + FECP) + fundos art. 115, I, 'b'
    DF-E      = média_ano f_ano·(ICMS + FECP)         [sem cota-parte]
    M (ex-DF) = média_ano f_ano·(ISS + 0,25·ICMS)
    DF-M      = média_ano f_ano·ISS_DF
    (ADCT 82, §1º: adicional FECP 100% no estado, fora da base da cota-parte.)
    """
    h = historico_receitas()
    total_ano = h.groupby("ano").apply(
        lambda g: (g["icms_liq"] + g["fecp_liq"] + g["iss_mun"]).sum(),
        include_groups=False)
    ultimo = max(config.JANELA_RECEITA_MEDIA)
    fator = (total_ano[ultimo] / total_ano).rename("fator_correcao")
    h = h.merge(fator, left_on="ano", right_index=True)

    cota = config.COTA_PARTE_MUNICIPAL
    fundos = pd.read_csv(config.PROCESSED / "fundos_estaduais.csv")
    share_fundos = fundos.drop_duplicates("uf").set_index("uf")["share_alocacao"]
    # art. 115, §3º: média 2021-2023 (= total OFICIAL da NT × share declarado),
    # corrigida de 2023 ao último ano disponível pelo fator nacional (§3º, II, 'b', 2).
    fundos_rm = (config.FUNDOS_ESTADUAIS_TOTAL_RS * share_fundos
                 * float(fator[2023]))

    linhas = []
    for uf, g in h.groupby("uf"):
        f = g["fator_correcao"]
        if uf == "DF":
            rm_e = float((f * (g["icms_liq"] + g["fecp_liq"])).mean())
            rm_m = float((f * g["iss_mun"]).mean())
        else:
            rm_e = (float((f * ((1 - cota) * g["icms_liq"] + g["fecp_liq"])).mean())
                    + float(fundos_rm.get(uf, 0.0)))
            rm_m = float((f * (g["iss_mun"] + cota * g["icms_liq"])).mean())
        linhas.append({"uf": uf, "esfera": "E", "rm": rm_e})
        linhas.append({"uf": uf, "esfera": "M", "rm": rm_m})
    df = pd.DataFrame(linhas)
    if (df["rm"] <= 0).any():
        raise ValueError("receita média não positiva")
    df["coeficiente_retencao"] = df["rm"] / df["rm"].sum()
    return df.sort_values(["esfera", "uf"]).reset_index(drop=True)


def grava_rm_historica() -> pd.DataFrame:
    h = historico_receitas().copy()
    h["formula"] = ("icms_liq/fecp_liq = DCA[conta por geração do ementário, "
                    "Brutas − Outras Deduções]; iss_mun: universo 2024-25, "
                    "estimador de razão 2019-23 (origem na coluna)")
    h["fonte"] = f"{_FONTE_DCA_UF} | {_FONTE_DCA_MUN} | LC 227 art. 115"
    h.to_csv(config.PROCESSED / "distribuicao_rm_historica.csv", index=False)
    return h


# --------------------------------------------------------------------------- #
# 3. Produto 2033 e receitas de referência por ente (janela 2024-25, R$ bi 2024)
# --------------------------------------------------------------------------- #
def produto_e_referencia(defl: float) -> pd.DataFrame:
    """Produto do IBS 2033 (= referência CHEIA reposta às alíquotas de
    referência) e a referência LÍQUIDA de cada ente (pós-fluxos de cota-parte
    do sistema legado), por UF×esfera. Σ referência ≡ Σ produto (conservação).
    """
    alvo_e = revenue.alvo_estadual_uf(defl)          # icms_bruto/fundos R$ bi
    alvo_m = revenue.alvo_municipal_uf(defl)         # ISS R$ bi (inclui DF)
    re_ = pd.read_csv(config.PROCESSED / "r_estadual.csv")
    fecp = deflaciona_media_janela(re_, "dca_fecp_bruta", defl, ["uf"]) \
        .set_index("uf")["dca_fecp_bruta"] / BI

    cota = config.COTA_PARTE_MUNICIPAL
    linhas = []
    for uf in sorted(config.UFS):
        icms = float(alvo_e.loc[uf, "icms_bruto"])
        fnd = float(alvo_e.loc[uf, "fundos"])
        iss = float(alvo_m[uf])
        base_cota = 0.0 if uf == "DF" else icms - float(fecp[uf])  # ADCT 82 §1º
        linhas.append({"uf": uf, "esfera": "E",
                       "produto_uf": icms + fnd,
                       "receita_referencia": icms + fnd - cota * base_cota})
        linhas.append({"uf": uf, "esfera": "M",
                       "produto_uf": iss,
                       "receita_referencia": iss + cota * base_cota})
    df = pd.DataFrame(linhas)
    if abs(df["produto_uf"].sum() - df["receita_referencia"].sum()) > 1e-9:
        raise AssertionError("Σ referência ≠ Σ produto (cota-parte não conserva)")
    return df


# --------------------------------------------------------------------------- #
# 4. Seguro-receita (ADCT 132, §1º; LC 227 art. 117) — nivelamento exato
# --------------------------------------------------------------------------- #
def _nivelamento_sequencial(ann: pd.Series, rmaj: pd.Series,
                            pool: float) -> pd.Series:
    """Distribui `pool` aos entes com as menores razões ann/rmaj de modo que,
    ao final, todos os contemplados fiquem na MESMA razão (water-filling —
    transcrição do §1º do art. 117 da LC 227). Determinístico; Σ = pool."""
    if pool <= 0:
        return pd.Series(0.0, index=ann.index)
    ratio = (ann / rmaj).sort_values(kind="mergesort")
    idx = list(ratio.index)
    cum_rm = cum_ann = 0.0
    k_final = len(idx)
    for k, i in enumerate(idx):
        cum_rm += float(rmaj[i])
        cum_ann += float(ann[i])
        if k + 1 < len(idx):
            custo = float(ratio.iloc[k + 1]) * cum_rm - cum_ann
            if custo >= pool:
                k_final = k + 1
                break
    contemplaveis = idx[:k_final]
    r_star = ((pool + sum(float(ann[i]) for i in contemplaveis))
              / sum(float(rmaj[i]) for i in contemplaveis))
    seg = pd.Series(0.0, index=ann.index)
    for i in contemplaveis:
        seg[i] = r_star * float(rmaj[i]) - float(ann[i])
    if (seg < -1e-9).any() or abs(float(seg.sum()) - pool) > 1e-9 * max(pool, 1):
        raise AssertionError("nivelamento do seguro-receita não conserva o pool")
    return seg


# --------------------------------------------------------------------------- #
# 5. Distribuição 2033
# --------------------------------------------------------------------------- #
def distribui_2033() -> tuple[pd.DataFrame, pd.DataFrame]:
    defl = revenue.deflator_2025()
    pr = produto_e_referencia(defl).set_index(["uf", "esfera"])
    rm = receita_media().set_index(["uf", "esfera"])
    base = pd.read_csv(config.PROCESSED / "base_uf.csv").set_index("uf")
    s_dest = base["B_ord"] / base["B_ord"].sum()
    pop = populacao_municipal_uf()                  # universo SICONFI, inclui DF

    P_E = float(pr.xs("E", level="esfera")["produto_uf"].sum())
    P_M = float(pr.xs("M", level="esfera")["produto_uf"].sum())
    P = P_E + P_M
    ret_pct = config.RETENCAO_2033
    seg_pct = config.SEGURO_RECEITA_PCT * (1 - ret_pct)      # 0,5% de P em 2033
    dest_pct = 1 - ret_pct - seg_pct                          # 9,5% de P
    pool_seguro = seg_pct * P
    cota = config.COTA_PARTE_MUNICIPAL

    # ---- 1) retenção (art. 114, §1º: pool único, coeficientes de receita média)
    retencao = ret_pct * P * rm["coeficiente_retencao"]

    # ---- 2) destino (parcela própria de cada ente, pré-cota-parte)
    dest = pd.Series({(uf, esf): dest_pct * (P_E if esf == "E" else P_M)
                      * float(s_dest[uf])
                      for uf, esf in pr.index}, name="componente_destino")

    # ---- 3) cota-parte municipal do IBS: só sobre a parcela-destino dos
    #         estados (ADCT 131, §3º exclui a retenção; seguro pós-cota)
    cota_flux = pd.Series(0.0, index=pr.index)
    for uf in config.UFS:
        if uf == "DF":
            continue                                # DF sem municípios (CF 32)
        v = cota * float(dest[(uf, "E")])
        cota_flux[(uf, "E")] = -v
        cota_flux[(uf, "M")] = +v

    # ---- 4) seguro-receita: razões do art. 117 (produto anual às alíquotas
    #         de referência pós-158, IV, 'b' ÷ receita média ajustada); DF é
    #         UM ente (ICMS+ISS, §§5º-6º)
    ann, rmaj = {}, {}
    pop_total = float(pop.sum())
    percap_e = float(rm.xs("E", level="esfera")["rm"].sum()) / pop_total
    percap_m = float(rm.xs("M", level="esfera")["rm"].sum()) / pop_total
    k = config.SEGURO_CAP_PER_CAPITA
    for uf in config.UFS:
        p_uf = float(pop[uf])
        if uf == "DF":
            ann[uf] = (P_E + P_M) * float(s_dest[uf])
            rmaj[uf] = min(float(rm.loc[(uf, "E"), "rm"] + rm.loc[(uf, "M"), "rm"]),
                           k * (percap_e + percap_m) * p_uf)          # §6º
        else:
            ann[f"{uf}_E"] = (1 - cota) * P_E * float(s_dest[uf])
            ann[f"{uf}_M"] = (P_M + cota * P_E) * float(s_dest[uf])
            rmaj[f"{uf}_E"] = min(float(rm.loc[(uf, "E"), "rm"]),
                                  k * percap_e * p_uf)                # §3º
            rmaj[f"{uf}_M"] = min(float(rm.loc[(uf, "M"), "rm"]),
                                  k * percap_m * p_uf)                # §4º
    seg_ente = _nivelamento_sequencial(pd.Series(ann), pd.Series(rmaj),
                                       pool_seguro)
    seguro = pd.Series(0.0, index=pr.index)
    for uf in config.UFS:
        if uf == "DF":       # split E/M do ente único DF: pro rata do produto
            seguro[(uf, "E")] = float(seg_ente[uf]) * P_E / (P_E + P_M)
            seguro[(uf, "M")] = float(seg_ente[uf]) * P_M / (P_E + P_M)
        else:
            seguro[(uf, "E")] = float(seg_ente[f"{uf}_E"])
            seguro[(uf, "M")] = float(seg_ente[f"{uf}_M"])

    # ---- consolidação
    out = pr.copy()
    out["componente_retencao"] = retencao
    out["componente_destino"] = dest
    out["componente_cota_parte"] = cota_flux
    out["componente_seguro"] = seguro
    out["recebido_legal"] = (out["componente_retencao"] + out["componente_destino"]
                             + out["componente_cota_parte"]
                             + out["componente_seguro"])
    out["suficiencia_pct"] = 100 * out["recebido_legal"] / out["receita_referencia"]
    out["coeficiente_retencao"] = rm["coeficiente_retencao"]

    if abs(float(out["recebido_legal"].sum()) - P) > 1e-6 * P:
        raise AssertionError("conservação violada: Σ recebido ≠ Σ produto")

    piso = 90.5                                     # art. 371 + Anexo XVI LC 214
    suf = out["suficiencia_pct"]
    met = pd.DataFrame([
        ("produto_total_bi", P, "Σ produto IBS 2033 (E: ICMS bruto + fundos; "
         "M: ISS com DF), janela 2024-25 deflacionada", _FONTE_LEGAL),
        ("produto_estadual_bi", P_E, "Σ esfera E", "r_estadual.csv + fundos"),
        ("produto_municipal_bi", P_M, "Σ esfera M", "r_municipal_uf.csv"),
        ("pool_seguro_bi", pool_seguro,
         "5% × (1 − 90%) × produto (LC 227, arts. 109-110)", _FONTE_LEGAL),
        ("suficiencia_minima_pct", float(suf.min()),
         f"mín recebido/referência (ente: {suf.idxmin()[0]}-{suf.idxmin()[1]})",
         "distribuicao_2033.csv"),
        ("suficiencia_maxima_pct", float(suf.max()),
         f"máx (ente: {suf.idxmax()[0]}-{suf.idxmax()[1]})",
         "distribuicao_2033.csv"),
        ("suficiencia_mediana_pct", float(suf.median()), "mediana 54 entes",
         "distribuicao_2033.csv"),
        ("n_entes_abaixo_100", float((suf < 100.0).sum()),
         "nº de UF×esfera com suficiência < 100%", "distribuicao_2033.csv"),
        ("n_entes_abaixo_piso_905", float((suf < piso).sum()),
         "nº de UF×esfera abaixo do piso de 90,5% (art. 371 + Anexo XVI)",
         "distribuicao_2033.csv"),
        ("n_entes", float(len(out)), "27 UFs × 2 esferas", "—"),
    ], columns=["chave", "valor", "formula", "fonte"])

    MANIFEST.registra("distribuicao_2033_suficiencia_minima", Num(
        float(suf.min()), "mín_ente[recebido_legal ÷ receita_referencia]",
        _FONTE_LEGAL, Label.DERIVADO, "%"))
    MANIFEST.registra("distribuicao_2033_produto_total", Num(
        P, "Σ referência cheia E+M, janela 2024-25 deflacionada",
        _FONTE_LEGAL, Label.DERIVADO, "R$ bi 2024"))

    out = out.reset_index()
    out["formula"] = ("recebido = 90%·P·coef_rm (arts. 109/114-115) + 9,5%·P_s·"
                      "share_destino (ADCT 131, §4º; proxy B_ord) ± cota-parte "
                      "25% da parcela-destino estadual (CF 158, IV, 'b'; ADCT "
                      "131, §3º) + seguro (arts. 110/117, nivelamento)")
    out["fonte"] = (f"{_FONTE_LEGAL}; numerários: r_estadual.csv, "
                    "r_municipal_uf.csv, fundos_estaduais.csv, base_uf.csv, "
                    "distribuicao_rm_historica.csv")
    return out, met


def main() -> None:
    grava_rm_historica()
    out, met = distribui_2033()
    out.to_csv(config.PROCESSED / "distribuicao_2033.csv", index=False)
    met.to_csv(config.PROCESSED / "distribuicao_2033_metricas.csv", index=False)
    pd.set_option("display.width", 160)
    print(out[["uf", "esfera", "receita_referencia", "recebido_legal",
               "suficiencia_pct", "componente_retencao", "componente_destino",
               "componente_cota_parte", "componente_seguro"]]
          .round(3).to_string(index=False))
    print()
    print(met[["chave", "valor"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
