"""Etanol hidratado combustível (EHC) — dedução AD VALOREM mensal do ICMS.

Achado da auditoria adversarial (2026-07): o EHC é MONOFÁSICO na LC 214
(art. 172, VI — "etanol hidratado combustível (EHC)"), e a base o trata
assim (produto TRU 19921 removido da âncora; itens POF de etanol fora das
shares — `base.py::TRU_PRODUTOS_REMOVIDOS` e `itens_combustiveis`). MAS o
EHC está FORA dos convênios ad rem da LC 192/2022 (Conv. ICMS 199/2022 e
15/2023 cobrem gasolina+EAC, diesel+B100 e GLP/GLGN) e por isso recolhe
HOJE ICMS ad valorem — receita que permanecia dentro do Alvo_E (icms_bruto
do RREO) SEM dedução simétrica, sobreestimando a alíquota de reposição.

Dedução espelhada no desenho ad rem (medição direta, sem multiplicadores):
    deducao(uf, ano, mes) = volume_ANP(uf, ano, mes, ETANOL HIDRATADO) [L]
                            × preço_médio_revenda_ANP-SLP(uf, ano, mes) [R$/l]
                            × carga_advalorem_vigente(uf, mes)
com a carga ad valorem lida da TABELA CURADA de vigências
data/inputs/icms_etanol_hidratado_vigencias.csv (uma linha por UF × período
de vigência, ATO NORMATIVO citado linha a linha: alíquota específica de
EHC, base reduzida — expressa como carga EFETIVA sobre o preço final — ou
alíquota modal da UF quando não há tratamento próprio).

Convenções DECLARADAS:
  * base de cálculo ≈ preço final ao consumidor: o ICMS do EHC é retido por
    substituição tributária sobre o PMPF (preço médio ponderado a consumidor
    final, ATO COTEPE/PMPF); a rotina usa o preço médio de REVENDA da
    ANP-SLP (mensal, por UF) como proxy ABERTO e mensal do PMPF;
  * a coluna `aliquota` da tabela curada é a carga ad valorem EFETIVA sobre
    esse preço (alíquota nominal × % de base reduzida, quando houver), de
    modo que deducao_rs = volume × preço × aliquota é exata por construção;
  * MESES PARTIDOS: quando a troca de carga não ocorre no dia 1º (casos na
    janela: MA em 19/02/2024 e 23/02/2025; RN em 20/03/2025), a carga do mês
    é a média das vigências PONDERADA PELOS DIAS de cada trecho (os volumes
    ANP são mensais — rateio por dias é a convenção declarada; nos demais
    meses×UF a vigência é única e a carga mensal é exata);
  * fundos estaduais de combustível embutidos na sistemática de cada UF
    seguem o tratamento declarado na coluna `nota` da tabela curada.

Fontes (data/raw + data/inputs):
  * ANP, Vendas de derivados (m³, mensal, por UF) — mesmo CSV do módulo
    ad rem (data/raw/anp/vendas-combustiveis-m3-1990-2025.csv);
  * ANP-SLP, Série Histórica do Levantamento de Preços, Mensal — Estados
    (R$/l, preço médio de revenda), data/raw/anp_precos/ (fetch.anp_precos);
  * atos estaduais transcritos em data/inputs/icms_etanol_hidratado_
    vigencias.csv (RICMS/decretos/leis, um por linha, com URL).

Saídas (data/processed/):
  * deducao_icms_etanol_uf_mes.csv — grão uf × ano × mês (auditável);
  * deducao_icms_etanol_uf.csv    — agregado uf × ano no ESQUEMA espelhado
    de combustiveis_uf.csv [uf, ano, receita_etanol_estimada, share_do_icms,
    vol_etanol_hidratado_m3, formula, fonte].
Integração ao alvo estadual: `revenue.alvo_estadual_uf` (módulo do
orquestrador — NÃO editado daqui) passa a subtrair também
`receita_etanol_estimada`; ver nota de integração no relatório da revisão.
"""
from __future__ import annotations

import functools

import pandas as pd

from aferir.config import (
    ETANOL_PRODUTO_ANP,
    ETANOL_VIGENCIAS_CSV,
    JANELA_RECEITA,
    PROCESSED,
    RAW_ANP_PRECOS_XLSX,
    UFS,
)
from aferir.inputs.combustiveis import _norm, _UF_NOME2SIGLA, volumes_anp_mensais
from aferir.inputs.siconfi_estadual import r_estadual
from aferir.provenance import MANIFEST, Label, Num

_FONTE_ANP_VENDAS = (
    "ANP, Vendas de derivados de petróleo e biocombustíveis por UF (m³, "
    "mensal), https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "vendas-de-derivados-de-petroleo-e-biocombustiveis; cache local "
    "data/raw/anp/vendas-combustiveis-m3-1990-2025.csv")
_FONTE_ANP_PRECOS = (
    "ANP-SLP, Série Histórica do Levantamento de Preços — Mensal — Estados "
    "(preço médio de revenda, R$/l), https://www.gov.br/anp/pt-br/assuntos/"
    "precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-"
    "combustiveis/serie-historica-do-levantamento-de-precos; cache local "
    "data/raw/anp_precos/mensal-estados-desde-jan2013.xlsx")
_FONTE_VIGENCIAS = (
    "Carga ad valorem do ICMS sobre o EHC por UF (alíquota específica, base "
    "reduzida ou modal — ato normativo citado linha a linha): tabela de "
    "vigências data/inputs/icms_etanol_hidratado_vigencias.csv")

# Sanidade da carga ad valorem: nenhum estado tributa EHC acima de 30% nem a
# zero na janela (menor efetiva observada: MT 8,5% = 17% × base 50%).
_ALIQ_MIN, _ALIQ_MAX = 0.05, 0.30
# Sanidade do preço de revenda do EHC na janela (R$/l correntes 2024-2025).
_PRECO_MIN, _PRECO_MAX = 2.0, 8.0


@functools.lru_cache(maxsize=1)
def vigencias_etanol() -> pd.DataFrame:
    """Tabela curada validada: por UF, TODOS os dias da janela cobertos por
    exatamente 1 vigência (sem lacuna e sem sobreposição); linhas de nota
    (aliquota vazia) descartadas; ato citado linha a linha."""
    MANIFEST.registra_arquivo(ETANOL_VIGENCIAS_CSV)
    df = pd.read_csv(ETANOL_VIGENCIAS_CSV)
    df = df.dropna(subset=["aliquota"]).copy()
    df["aliquota"] = df["aliquota"].astype(float)
    df["vigencia_inicio"] = pd.to_datetime(df["vigencia_inicio"])
    df["vigencia_fim"] = pd.to_datetime(df["vigencia_fim"])
    faltam = set(UFS) - set(df["uf"])
    if faltam:
        raise ValueError(f"vigências de EHC ausentes para {sorted(faltam)}")
    if not df["ato"].astype(str).str.strip().all():
        raise ValueError("linha de vigência de EHC sem ato citado")
    fora = df[(df["aliquota"] <= _ALIQ_MIN) | (df["aliquota"] >= _ALIQ_MAX)]
    if not fora.empty:
        raise ValueError(
            f"carga ad valorem de EHC fora do plausível ({_ALIQ_MIN}; "
            f"{_ALIQ_MAX}): {fora['uf'].tolist()}")
    ini_j = pd.Timestamp(min(JANELA_RECEITA), 1, 1)
    fim_j = pd.Timestamp(max(JANELA_RECEITA), 12, 31)
    for uf in UFS:
        sel = df[df["uf"] == uf].sort_values("vigencia_inicio")
        if sel["vigencia_inicio"].iloc[0] > ini_j:
            raise ValueError(f"EHC {uf}: início da janela descoberto")
        if sel["vigencia_fim"].iloc[-1] < fim_j:
            raise ValueError(f"EHC {uf}: fim da janela descoberto")
        fins = sel["vigencia_fim"].iloc[:-1].reset_index(drop=True)
        inis = sel["vigencia_inicio"].iloc[1:].reset_index(drop=True)
        if len(fins) and not (inis == fins + pd.Timedelta(days=1)).all():
            raise ValueError(f"EHC {uf}: lacuna ou sobreposição entre "
                             "vigências (exigido encadeamento dia a dia)")
    return df


def aliquota_vigente_etanol(uf: str, ano: int, mes: int) -> dict:
    """Carga ad valorem do mês (uf) — EXATA quando a vigência é única; nos
    meses PARTIDOS (troca fora do dia 1º: MA 19/02/2024 e 23/02/2025, RN
    20/03/2025), média ponderada pelos DIAS de cada vigência no mês
    (convenção declarada no cabeçalho do módulo).

    Retorna dict com aliquota (efetiva do mês), ato, fonte_url, nota e
    n_trechos (1 = mês inteiro sob uma única vigência).
    """
    vig = vigencias_etanol()
    ini = pd.Timestamp(ano, mes, 1)
    fim = ini + pd.offsets.MonthEnd(0)
    sel = vig[(vig["uf"] == uf) & (vig["vigencia_inicio"] <= fim)
              & (vig["vigencia_fim"] >= ini)].sort_values("vigencia_inicio")
    if len(sel) == 0:
        raise ValueError(f"EHC {uf} {ano}-{mes:02d}: sem vigência")
    dias_mes = (fim - ini).days + 1
    peso, acum = 0, 0.0
    for _, r in sel.iterrows():
        dias = ((min(r["vigencia_fim"], fim)
                 - max(r["vigencia_inicio"], ini)).days + 1)
        acum += float(r["aliquota"]) * dias
        peso += dias
    if peso != dias_mes:
        raise ValueError(f"EHC {uf} {ano}-{mes:02d}: cobertura de dias "
                         f"{peso}/{dias_mes}")
    return {
        "aliquota": acum / dias_mes,
        "ato": " || ".join(sel["ato"].astype(str)),
        "fonte_url": " || ".join(sel["fonte_url"].astype(str)),
        "nota": " || ".join(sel["nota"].astype(str)),
        "n_trechos": len(sel),
    }


@functools.lru_cache(maxsize=1)
def precos_etanol_uf_mes() -> pd.DataFrame:
    """Preço médio de revenda do EHC (R$/l) por uf, ano, mês — ANP-SLP.

    Lê a planilha oficial (aba única, cabeçalho localizado pela linha 'MÊS'),
    filtra ETANOL HIDRATADO nos anos da janela e valida cobertura COMPLETA
    (27 UFs × 24 meses, sem NaN) e unidade R$/l.
    """
    MANIFEST.registra_arquivo(RAW_ANP_PRECOS_XLSX)
    bruto = pd.read_excel(RAW_ANP_PRECOS_XLSX, sheet_name=0, header=None)
    hdr = bruto.index[bruto[0].astype(str).str.strip() == "MÊS"]
    if len(hdr) != 1:
        raise ValueError("ANP-SLP: cabeçalho 'MÊS' não localizado (esperado 1)")
    df = bruto.iloc[hdr[0] + 1:].copy()
    df.columns = [str(c).strip() for c in bruto.iloc[hdr[0]]]
    df["MÊS"] = pd.to_datetime(df["MÊS"])
    df = df[(df["PRODUTO"].astype(str).str.strip() == ETANOL_PRODUTO_ANP)
            & (df["MÊS"].dt.year.isin(JANELA_RECEITA))].copy()
    unidades = set(df["UNIDADE DE MEDIDA"].astype(str).str.strip())
    if unidades != {"R$/l"}:
        raise ValueError(f"ANP-SLP: unidade inesperada p/ EHC: {unidades}")
    df["uf"] = df["ESTADO"].map(lambda x: _UF_NOME2SIGLA.get(_norm(x)))
    df = df.dropna(subset=["uf"])
    out = pd.DataFrame({
        "uf": df["uf"],
        "ano": df["MÊS"].dt.year.astype(int),
        "mes": df["MÊS"].dt.month.astype(int),
        "preco_rs_l": df["PREÇO MÉDIO REVENDA"].astype(float),
    }).sort_values(["uf", "ano", "mes"]).reset_index(drop=True)
    esperado = len(UFS) * len(JANELA_RECEITA) * 12
    if len(out) != esperado or out["preco_rs_l"].isna().any():
        raise ValueError(
            f"ANP-SLP: cobertura incompleta do EHC ({len(out)}/{esperado} "
            "células uf×mês)")
    fora = out[(out["preco_rs_l"] < _PRECO_MIN) | (out["preco_rs_l"] > _PRECO_MAX)]
    if not fora.empty:
        raise ValueError("ANP-SLP: preço de EHC fora do plausível "
                         f"[{_PRECO_MIN}; {_PRECO_MAX}] R$/l")
    return out


def deducao_etanol_uf_mes() -> pd.DataFrame:
    """deducao_icms_etanol_uf_mes.csv — dedução ad valorem no grão uf × mês.

    deducao_rs = volume_anp_m3 × 1000 [L] × preco_rs_l × aliquota vigente;
    volume_anp_m3 preserva o dado bruto ANP (mesma convenção do ad rem).
    """
    vol = volumes_anp_mensais()
    precos = precos_etanol_uf_mes().set_index(["uf", "ano", "mes"])["preco_rs_l"]
    linhas = []
    for uf in sorted(UFS):
        for ano in JANELA_RECEITA:
            for mes in range(1, 13):
                v = aliquota_vigente_etanol(uf, ano, mes)
                rate = float(v["aliquota"])
                sel = vol[(vol["uf"] == uf) & (vol["ano"] == ano)
                          & (vol["mes"] == mes)
                          & (vol["produto_anp"] == ETANOL_PRODUTO_ANP)]["volume_m3"]
                v_m3 = float(sel.sum())
                preco = float(precos.loc[(uf, ano, mes)])
                rateio = ("" if v["n_trechos"] == 1 else
                          f" (mês partido: {v['n_trechos']} vigências "
                          "ponderadas pelos dias)")
                linhas.append({
                    "uf": uf, "ano": ano, "mes": mes,
                    "produto": "ETANOL_HIDRATADO",
                    "volume_anp_m3": v_m3, "volume_l": v_m3 * 1000.0,
                    "preco_rs_l": preco, "aliquota": rate,
                    "n_vigencias_no_mes": v["n_trechos"],
                    "deducao_rs": v_m3 * 1000.0 * preco * rate,
                    "ato": v["ato"],
                    "formula": ("deducao_rs = volume_anp_m3 ×1000 L/m³ × "
                                "preco_medio_revenda_ANP-SLP × carga ad "
                                f"valorem vigente em {ano}-{mes:02d}"
                                f"{rateio} (R$ correntes)"),
                    "fonte": (f"{_FONTE_ANP_VENDAS} | {_FONTE_ANP_PRECOS} | "
                              f"{_FONTE_VIGENCIAS}"),
                })
    df = pd.DataFrame(linhas)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "deducao_icms_etanol_uf_mes.csv", index=False)
    return df


def deducao_etanol_uf() -> pd.DataFrame:
    """deducao_icms_etanol_uf.csv — dedução ad valorem do EHC por UF/ano.

    Agregado anual da dedução mensal, no esquema espelhado de
    combustiveis_uf.csv (consumo previsto: aferir.revenue.alvo_estadual_uf
    passa a subtrair receita_etanol_estimada — integração do orquestrador).
    """
    ded = deducao_etanol_uf_mes()
    icms = r_estadual().set_index(["uf", "ano"])["icms_bruto"]

    receita = ded.groupby(["uf", "ano"])["deducao_rs"].sum()
    vol_m3 = ded.groupby(["uf", "ano"])["volume_anp_m3"].sum()
    linhas = []
    for uf in sorted(UFS):
        for ano in JANELA_RECEITA:
            r = float(receita.loc[(uf, ano)])
            icms_uf = float(icms.loc[(uf, ano)])
            linhas.append({
                "uf": uf, "ano": ano,
                "receita_etanol_estimada": r,
                "share_do_icms": r / icms_uf,
                "vol_etanol_hidratado_m3": float(vol_m3.loc[(uf, ano)]),
                "formula": ("receita_etanol = Σ_mes [vol_mensal_EHC·1000·"
                            "preço_revenda_ANP-SLP(uf, mes)·carga_advalorem"
                            "(uf, mes)] (vigência por ato estadual; detalhe "
                            "em deducao_icms_etanol_uf_mes.csv); "
                            "share_do_icms = receita_etanol ÷ icms_bruto "
                            "(rubrica RREO, inclui FECP)"),
                "fonte": (f"{_FONTE_ANP_VENDAS} | {_FONTE_ANP_PRECOS} | "
                          f"{_FONTE_VIGENCIAS} | ICMS: r_estadual.csv"),
            })
    df = pd.DataFrame(linhas)
    if (df["receita_etanol_estimada"] <= 0).any():
        raise AssertionError("dedução de EHC não positiva em alguma UF-ano")
    if (df["share_do_icms"] >= 0.25).any():
        raise AssertionError("share do EHC no ICMS fora do plausível (< 0,25)")
    for ano in JANELA_RECEITA:
        nac = float(df[df["ano"] == ano]["receita_etanol_estimada"].sum())
        if not 6e9 <= nac <= 15e9:
            raise AssertionError(
                f"dedução nacional de EHC em {ano} fora da ordem de grandeza "
                f"[6; 15] R$ bi: {nac / 1e9:.2f}")
        MANIFEST.registra(
            f"etanol_deducao_advalorem_nacional_{ano}_Rbi",
            Num(nac / 1e9,
                "Σ_uf Σ_mes volume_ANP(EHC) × preço_revenda_ANP-SLP × carga "
                f"ad valorem vigente por UF no mês ({ano})",
                f"{_FONTE_ANP_VENDAS} | {_FONTE_ANP_PRECOS} | "
                f"{_FONTE_VIGENCIAS}", Label.DERIVADO, f"R$ bi {ano}"))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "deducao_icms_etanol_uf.csv", index=False)
    return df


if __name__ == "__main__":
    tab = deducao_etanol_uf()
    for ano in JANELA_RECEITA:
        nac = tab[tab["ano"] == ano]["receita_etanol_estimada"].sum() / 1e9
        print(f"dedução ad valorem EHC {ano}: {nac:.3f} R$ bi")
