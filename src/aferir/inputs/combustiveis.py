"""Combustíveis monofásicos — dedução ad rem MENSAL: volumes ANP × vigências CONFAZ.

Medição direta (sem multiplicadores livres — herda a decisão v1 de 2026-06-26),
agora reproduzível mês a mês (item A2 da revisão):
    deducao(uf, ano, mes, p) = volume_ANP(uf, ano, mes, p) × alíquota_vigente(p, mes)
com p ∈ {gasolina C, óleo diesel, GLP} e alíquota lida da TABELA DE VIGÊNCIAS
data/inputs/icms_adrem_vigencias.csv (uma linha por produto × período de
vigência, com convênio e URL). Todas as vigências da janela iniciam no dia 1º
do mês (verificado no código), logo a granularidade mensal é EXATA — em
particular, janeiro/2024 usa as alíquotas originais (Conv. 199/2022 e 15/2023)
e janeiro/2025 usa as dos Conv. 172/2023 e 173/2023, não as reajustadas que só
vigoram a partir de 1º de fevereiro de cada ano (Conv. 172-173/2023 e
126-127/2024).

Perímetro (declarado — item A2):
  * ICMS ad rem incide sobre a MISTURA COMERCIAL INTEGRAL: gasolina C
    (gasolina A + etanol anidro EAC) e óleo diesel B (diesel A + B100) têm
    alíquota única por litro da mistura (Conv. ICMS 15/2023 e 199/2022,
    cláusulas sétimas); GLP/GLGN por quilograma. ASSIMETRIA com a esfera
    federal: o PIS/Cofins ad rem incide apenas sobre a FRAÇÃO FÓSSIL da bomba
    (frações de blend declaradas em aferir.revenue).
  * Etanol HIDRATADO fica FORA da dedução ad rem: não é alcançado pelos
    convênios da monofasia (que cobrem gasolina+EAC, diesel+B100 e GLP/GLGN)
    e permanece no campo ad valorem — logo permanece na base POF e no
    numerador do ICMS.
  * GLP: o dado aberto ANP publica TODOS os volumes em m³ (metadados oficiais
    do conjunto, arquivados em data/raw/normas/anp_metadados/); a alíquota
    CONFAZ é em R$/kg, então a conversão m³→kg usa a densidade média oficial
    do Anuário Estatístico ANP 2023 (Fatores de conversão): 0,552 t/m³ a
    20 °C e 1 atm (fonte EPE/BEN) — substitui a convenção 550 kg/m³ do v1.

Fontes (data/raw + data/inputs):
  * ANP, Vendas de derivados de petróleo e biocombustíveis por UF (m³,
    mensal), data/raw/anp/vendas-combustiveis-m3-1990-2025.csv;
  * Convênios ICMS 199/2022, 15/2023, 172/2023, 173/2023, 126/2024, 127/2024
    (LC 192/2022) — textos arquivados em data/raw/normas/confaz/; alíquotas e
    vigências extraídas para data/inputs/icms_adrem_vigencias.csv.

Saídas:
  * deducao_icms_adrem_uf_mes.csv — grão uf × ano × mês × produto (auditável);
  * combustiveis_uf.csv — agregado uf × ano no ESQUEMA legado
    [uf, ano, receita_adrem_estimada, share_do_icms, vol_*_m3, formula, fonte]
    (consumido por aferir.revenue.alvo_estadual_uf).
share_do_icms = receita_adrem ÷ icms_bruto(uf, ano) (rubrica RREO, inclui FECP).
"""
from __future__ import annotations

import functools
import unicodedata

import pandas as pd

from aferir.config import (
    ADREM_PRODUTO_ANP,
    INPUTS,
    JANELA_RECEITA,
    PROCESSED,
    RAW_ANP_CSV,
    UFS,
)
from aferir.inputs.siconfi_estadual import r_estadual
from aferir.provenance import MANIFEST, Label, Num

# Tabela de vigências das alíquotas ad rem (extraída dos convênios arquivados).
VIGENCIAS_ADREM_CSV = INPUTS / "icms_adrem_vigencias.csv"

# Densidade média do GLP para converter m³ (dado aberto ANP) → kg (alíquota
# CONFAZ em R$/kg). Fonte OFICIAL: ANP, Anuário Estatístico 2023, "Fatores de
# conversão, densidades e poderes caloríficos inferiores" (valores médios de
# 2022; fonte primária EPE/Balanço Energético Nacional): GLP 0,552 t/m³ a
# 20 °C e 1 atm. PDF arquivado em data/raw/normas/anp_metadados/.
GLP_DENSIDADE_KG_M3_ANP = 552.0
_FONTE_GLP_DENS = (
    "ANP, Anuário Estatístico 2023, Fatores de conversão/densidades (GLP "
    "0,552 t/m³ a 20 °C e 1 atm; fonte EPE/BEN), https://www.gov.br/anp/"
    "pt-br/centrais-de-conteudo/publicacoes/anuario-estatistico/arquivos-"
    "anuario-estatistico-2023/outras-pecas-documentais/fatores-conversao.pdf; "
    "cache data/raw/normas/anp_metadados/anuario-2023-fatores-conversao.pdf")

_FONTE_ANP = ("ANP, Vendas de derivados de petróleo e biocombustíveis por UF "
              "(m³, mensal), https://www.gov.br/anp/pt-br/centrais-de-conteudo/"
              "dados-abertos/vendas-de-derivados-de-petroleo-e-biocombustiveis; "
              "cache local data/raw/anp/vendas-combustiveis-m3-1990-2025.csv")
_FONTE_VIGENCIAS = ("Alíquotas ad rem ICMS monofásico (LC 192/2022): Conv. ICMS "
                    "199/2022, 15/2023, 172/2023, 173/2023, 126/2024, 127/2024 "
                    "(textos em data/raw/normas/confaz/); tabela de vigências "
                    "data/inputs/icms_adrem_vigencias.csv")

_MES2NUM = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
            "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

_UF_NOME2SIGLA = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE",
    "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                   if unicodedata.category(c) != "Mn").upper().strip()


@functools.lru_cache(maxsize=1)
def vigencias_adrem() -> pd.DataFrame:
    """Tabela de vigências ad rem validada: exatamente 1 alíquota por
    produto × mês da janela; linhas de nota (aliquota_rs vazia) descartadas."""
    MANIFEST.registra_arquivo(VIGENCIAS_ADREM_CSV)
    df = pd.read_csv(VIGENCIAS_ADREM_CSV)
    df = df.dropna(subset=["aliquota_rs"]).copy()
    df["vigencia_inicio"] = pd.to_datetime(df["vigencia_inicio"])
    df["vigencia_fim"] = pd.to_datetime(df["vigencia_fim"])
    faltam = set(ADREM_PRODUTO_ANP) - set(df["produto"])
    if faltam:
        raise ValueError(f"vigências ad rem ausentes para {faltam}")
    for produto in ADREM_PRODUTO_ANP:
        sel = df[df["produto"] == produto]
        for ano in JANELA_RECEITA:
            for mes in range(1, 13):
                ini = pd.Timestamp(ano, mes, 1)
                fim = ini + pd.offsets.MonthEnd(0)
                cobre = sel[(sel["vigencia_inicio"] <= ini)
                            & (sel["vigencia_fim"] >= fim)]
                if len(cobre) != 1:
                    raise ValueError(
                        f"{produto} {ano}-{mes:02d}: {len(cobre)} vigências "
                        "cobrem o mês (exigido exatamente 1)")
                # granularidade mensal é exata: trocas de alíquota no dia 1º
                parcial = sel[(sel["vigencia_inicio"] > ini)
                              & (sel["vigencia_inicio"] <= fim)]
                if not parcial.empty:
                    raise ValueError(f"{produto}: vigência inicia no meio de "
                                     f"{ano}-{mes:02d} — grão mensal inválido")
    return df


def aliquota_vigente(produto: str, ano: int, mes: int) -> pd.Series:
    """Linha de vigência (aliquota_rs, unidade, convenio, fonte_url) do mês."""
    vig = vigencias_adrem()
    ini = pd.Timestamp(ano, mes, 1)
    fim = ini + pd.offsets.MonthEnd(0)
    sel = vig[(vig["produto"] == produto) & (vig["vigencia_inicio"] <= ini)
              & (vig["vigencia_fim"] >= fim)]
    return sel.iloc[0]


@functools.lru_cache(maxsize=1)
def volumes_anp_mensais() -> pd.DataFrame:
    """Volumes ANP (m³) por uf, ano, mês, produto ANP — janela legal, mensal."""
    MANIFEST.registra_arquivo(RAW_ANP_CSV)
    df = pd.read_csv(RAW_ANP_CSV, sep=";", encoding="utf-8-sig", decimal=",")
    cols = {_norm(c): c for c in df.columns}
    c_ano, c_mes, c_uf, c_prod, c_v = (cols["ANO"], cols["MES"],
                                       cols["UNIDADE DA FEDERACAO"],
                                       cols["PRODUTO"], cols["VENDAS"])
    df = df[df[c_ano].isin(JANELA_RECEITA)].copy()
    df["uf"] = df[c_uf].map(lambda x: _UF_NOME2SIGLA.get(_norm(x)))
    df["mes"] = df[c_mes].map(lambda x: _MES2NUM[_norm(x)])
    df["produto_anp"] = df[c_prod].map(_norm)
    df = df.dropna(subset=["uf"])
    g = (df.groupby(["uf", c_ano, "mes", "produto_anp"], as_index=False)[c_v]
           .sum().rename(columns={c_ano: "ano", c_v: "volume_m3"}))
    g["ano"] = g["ano"].astype(int)
    g["mes"] = g["mes"].astype(int)
    return g


def deducao_adrem_uf_mes() -> pd.DataFrame:
    """deducao_icms_adrem_uf_mes.csv — dedução ad rem no grão uf × mês × produto.

    volume/unidade acompanham a unidade da alíquota (L para gasolina C e
    diesel; kg para GLP), de modo que deducao_rs = volume × aliquota exata;
    volume_anp_m3 preserva o dado bruto ANP.
    """
    vol = volumes_anp_mensais()
    linhas = []
    for uf in sorted(UFS):
        for ano in JANELA_RECEITA:
            for mes in range(1, 13):
                for prod_confaz, prod_anp in sorted(ADREM_PRODUTO_ANP.items()):
                    v = aliquota_vigente(prod_confaz, ano, mes)
                    rate = float(v["aliquota_rs"])
                    sel = vol[(vol["uf"] == uf) & (vol["ano"] == ano)
                              & (vol["mes"] == mes)
                              & (vol["produto_anp"] == prod_anp)]["volume_m3"]
                    v_m3 = float(sel.sum())
                    if prod_confaz == "GLP_GLGN":     # R$/kg: m³ → kg (ANP 0,552 t/m³)
                        volume, unidade = v_m3 * GLP_DENSIDADE_KG_M3_ANP, "kg"
                        conv = f"×{GLP_DENSIDADE_KG_M3_ANP:.0f} kg/m³ (ANP 0,552 t/m³)"
                    else:                             # R$/L: m³ → litros
                        volume, unidade = v_m3 * 1000.0, "L"
                        conv = "×1000 L/m³"
                    linhas.append({
                        "uf": uf, "ano": ano, "mes": mes, "produto": prod_confaz,
                        "volume_anp_m3": v_m3, "volume": volume,
                        "unidade": unidade, "aliquota": rate,
                        "deducao_rs": volume * rate, "convenio": v["convenio"],
                        "formula": (f"deducao_rs = volume_anp_m3 {conv} × "
                                    f"aliquota vigente em {ano}-{mes:02d} "
                                    f"({unidade}; R$ correntes)"),
                        "fonte": f"{_FONTE_ANP} | {_FONTE_VIGENCIAS}",
                    })
    df = pd.DataFrame(linhas)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "deducao_icms_adrem_uf_mes.csv", index=False)
    return df


def combustiveis_uf() -> pd.DataFrame:
    """combustiveis_uf.csv — receita ad rem estimada e share do ICMS por UF/ano.

    Agregado anual da dedução mensal (esquema legado inalterado — consumido
    por aferir.revenue.alvo_estadual_uf e aferir.inputs.seed).
    """
    ded = deducao_adrem_uf_mes()
    icms = r_estadual().set_index(["uf", "ano"])["icms_bruto"]

    receita = (ded.groupby(["uf", "ano"])["deducao_rs"].sum())
    vol_m3 = (ded.pivot_table(index=["uf", "ano"], columns="produto",
                              values="volume_anp_m3", aggfunc="sum"))
    linhas = []
    for uf in sorted(UFS):
        for ano in JANELA_RECEITA:
            r = float(receita.loc[(uf, ano)])
            icms_uf = float(icms.loc[(uf, ano)])
            linhas.append({
                "uf": uf, "ano": ano,
                "receita_adrem_estimada": r,
                "share_do_icms": r / icms_uf,
                "vol_gasolina_c_m3": float(vol_m3.loc[(uf, ano), "GASOLINA_EAC"]),
                "vol_oleo_diesel_m3": float(vol_m3.loc[(uf, ano), "DIESEL_B100"]),
                "vol_glp_m3": float(vol_m3.loc[(uf, ano), "GLP_GLGN"]),
                "formula": ("receita_adrem = Σ_mes [vol_mensal_gasolina_c·1000"
                            "·aliq_gas(mes) + vol_mensal_diesel·1000·"
                            "aliq_diesel(mes) + vol_mensal_glp·"
                            f"{GLP_DENSIDADE_KG_M3_ANP:.0f}·aliq_glp(mes)] "
                            "(alíquota vigente no mês, R$ correntes do ano; "
                            "detalhe em deducao_icms_adrem_uf_mes.csv); "
                            "share_do_icms = receita_adrem ÷ icms_bruto "
                            "(rubrica RREO, inclui FECP)"),
                "fonte": (f"{_FONTE_ANP} | {_FONTE_VIGENCIAS} | "
                          f"GLP m³→kg: {_FONTE_GLP_DENS} | ICMS: r_estadual.csv"),
            })
    df = pd.DataFrame(linhas)
    if (df["share_do_icms"] <= 0).any() or (df["share_do_icms"] >= 0.6).any():
        raise AssertionError("share de combustíveis fora do plausível (0; 0,6)")
    MANIFEST.registra(
        "glp_densidade_kg_m3",
        Num(GLP_DENSIDADE_KG_M3_ANP, "densidade média do GLP (0,552 t/m³ × 1000)",
            _FONTE_GLP_DENS, Label.OFICIAL, "kg/m³"))
    MANIFEST.registra(
        "combustiveis_receita_adrem_nacional_2024_Rbi",
        Num(float(df[df["ano"] == 2024]["receita_adrem_estimada"].sum()) / 1e9,
            "Σ_uf Σ_mes volume_ANP(uf, mes) × alíquota ad rem vigente no mês (2024)",
            f"{_FONTE_ANP} | {_FONTE_VIGENCIAS}", Label.DERIVADO, "R$ bi 2024"))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "combustiveis_uf.csv", index=False)
    return df
