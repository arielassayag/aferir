"""Receitas de referência por esfera (LC 214, art. 350) e alvos ancorados.

Tudo em R$ bi de 2024, média da janela 2024-2025 (art. 361-365: âncora
subnacional é a média 2024-2026 — 2026 indisponível em jul/2026, declarado).

Convenções centrais (todas declaradas no artigo):
- Combustíveis monofásicos saem SIMETRICAMENTE do alvo (receita ad rem
  estimada por volumes ANP × alíquotas ad rem vigentes) e da base (itens POF
  de combustíveis) — a alíquota calculada é a AD VALOREM padrão.
- União (art. 353): alvo = âncora 2012-2021 (%PIB; central = convenção
  LÍQUIDA-RTN, Tema 69; bruta-RFB = sensibilidade) × PIB da janela
  − IPI residual ZFM (R$ 2,6 bi, NT SERT p. 4) − IS estimado (proxy
  iso-carga: arrecadação corrente de IPI nos produtos do campo do IS —
  fumo, bebidas, veículos, LC 214 art. 409 + Anexo XVII; alíquotas do IS
  aguardam lei ordinária ⇒ o proxy é COTA INFERIOR do IS e τ_CBS segue
  COTA SUPERIOR nessa dimensão; IS=0 vira sensibilidade)
  − PIS/Cofins-combustíveis.
- Estados: ICMS bruto (rubrica RREO; JÁ INCLUI FECP — identidade DCA 54/54)
  − ad rem estadual + fundos do art. 350, II, 'b' (§2º, II).
- Municípios: ISS (conta 1.1.1.4.51.1.0, já consolida multas/DA) + ISS do DF
  (art. 350, III).
"""
from __future__ import annotations

import pandas as pd

from . import config
from .govpurchases import deflaciona_media_janela, media_janela_serie
from .provenance import MANIFEST, Label, Num

BI = 1e9

# Frações de biocombustível na bomba (combustível fóssil = base do ad rem
# federal), POR VIGÊNCIA MENSAL. Atos: Resolução CNPE nº 8/2023 (B14 a
# partir de 01/03/2024; nível anterior B12, cf. Res. CNPE nº 3/2023) e
# Resolução CNPE nº 9, de 25/06/2025 (E30 e B15 a partir de 01/08/2025;
# níveis anteriores E27 e B14), sob a Lei nº 14.993/2024.
# Formato: (fração, primeiro mês 'AAAA-MM', último mês 'AAAA-MM').
BLENDS_VIGENCIAS = {
    "etanol": (
        (0.27, "2024-01", "2025-07"),
        (0.30, "2025-08", "2025-12"),
    ),
    "biodiesel": (
        (0.12, "2024-01", "2024-02"),
        (0.14, "2024-03", "2025-07"),
        (0.15, "2025-08", "2025-12"),
    ),
}


def fracao_bio(bio: str, ano: int, mes: int) -> float:
    """Fração de biocombustível vigente no mês (BLENDS_VIGENCIAS)."""
    chave = f"{ano}-{mes:02d}"
    for frac, ini, fim in BLENDS_VIGENCIAS[bio]:
        if ini <= chave <= fim:
            return frac
    raise ValueError(f"blend de {bio} sem vigência em {chave}")


def deflator_2025() -> float:
    from .inputs.ipca_pib import deflator_para_2024
    return float(deflator_para_2024(2025).valor)


def pib_janela_bi(defl: float, janela: tuple[int, ...] | None = None) -> float:
    pib = pd.read_csv(config.PROCESSED / "pib_nominal.csv").set_index("ano")["pib_rs_mi"]
    return media_janela_serie(pib, defl, janela) / 1e3


def _sufixo_janela(janela: tuple[int, ...] | None) -> str:
    """Sufixo de chave do MANIFEST quando a janela NÃO é a central (A6)."""
    if janela is None or tuple(janela) == tuple(config.JANELA_RECEITA):
        return ""
    return "[janela=" + "+".join(str(a) for a in janela) + "]"


def alvo_municipal_uf(defl: float,
                      janela: tuple[int, ...] | None = None) -> pd.Series:
    r = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    # cobertura econômica COM imputação (A6): o painel municipal imputa os
    # omissos (mediana per capita do estrato da própria UF) — o alvo soma
    # declarado + imputado, como o texto declara (sem fallback silencioso).
    col = "iss_total_com_imputacao"
    if col not in r.columns:
        if "iss_imputado" not in r.columns:
            raise ValueError("r_municipal_uf.csv sem iss_imputado")
        r[col] = r["iss_liquida"].fillna(0.0) + r["iss_imputado"].fillna(0.0)
    m = deflaciona_media_janela(r, col, defl, ["uf"], janela).set_index("uf")[col] / BI
    MANIFEST.registra("R_M_nacional" + _sufixo_janela(janela), Num(
        float(m.sum()), f"média janela deflacionada de {col} (municípios+DF)",
        "SICONFI DCA municipal + RREO-DF; LC 214 art. 350, III", Label.DERIVADO,
        "R$ bi 2024"))
    return m


def alvo_estadual_uf(defl: float,
                     janela: tuple[int, ...] | None = None) -> pd.DataFrame:
    r = pd.read_csv(config.PROCESSED / "r_estadual.csv")
    comb = pd.read_csv(config.PROCESSED / "combustiveis_uf.csv")
    fundos = pd.read_csv(config.PROCESSED / "fundos_estaduais.csv")
    # EHC é monofásico (LC 214, art. 172): a base o exclui e o alvo deduz o
    # ICMS ad valorem que ele recolhe HOJE (fora dos convênios ad rem) —
    # volumes ANP × preço ANP-SLP × alíquota vigente por UF (tabela de
    # vigências com ato citado linha a linha; achado da auditoria de nível).
    etanol = pd.read_csv(config.PROCESSED / "deducao_icms_etanol_uf.csv")

    icms = deflaciona_media_janela(r, "icms_bruto", defl, ["uf"],
                                   janela).set_index("uf")["icms_bruto"]
    adrem = deflaciona_media_janela(comb, "receita_adrem_estimada", defl,
                                    ["uf"], janela).set_index("uf")["receita_adrem_estimada"]
    etano = deflaciona_media_janela(etanol, "receita_etanol_estimada", defl,
                                    ["uf"], janela).set_index("uf")["receita_etanol_estimada"]
    fnd = deflaciona_media_janela(fundos, "fundos_rs", defl, ["uf"], janela) \
        .set_index("uf")["fundos_rs"].reindex(icms.index).fillna(0.0)

    out = pd.DataFrame({
        "icms_bruto": icms / BI,
        "adrem_combustiveis": adrem.reindex(icms.index).fillna(0.0) / BI,
        "etanol_advalorem": etano.reindex(icms.index).fillna(0.0) / BI,
        "fundos": fnd / BI,
    })
    out["alvo_ex_comb"] = (out["icms_bruto"] - out["adrem_combustiveis"]
                           - out["etanol_advalorem"] + out["fundos"])
    if (out["alvo_ex_comb"] <= 0).any():
        raise ValueError("alvo estadual não positivo em alguma UF")
    MANIFEST.registra("R_E_nacional_ex_comb" + _sufixo_janela(janela), Num(
        float(out["alvo_ex_comb"].sum()),
        "Σ_uf [ICMS bruto − ad rem ANP×CONFAZ − ad valorem EHC + fundos art. 350,II,'b']",
        "SICONFI RREO An.03 + ANP + CONFAZ + NT SERT p.4", Label.DERIVADO,
        "R$ bi 2024"))
    return out


# Tabela de vigências federais (Decreto 5.059/2004 + alteradores, textos em
# data/raw/normas/planalto_decretos/) — item A3 da revisão.
PIS_COFINS_VIGENCIAS_CSV = (config.V2_ROOT / "data" / "inputs"
                            / "pis_cofins_combustiveis_vigencias.csv")

# produto da tabela federal → (produto ANP, biocombustível da mistura; a
# fração vigente no mês é deduzida do volume porque o ad rem federal incide
# só na fração FÓSSIL — assimetria com o ICMS ad rem, que incide sobre a
# mistura comercial integral).
_FEDERAL_PRODUTO_ANP = {
    "gasolina_correntes": ("GASOLINA C", "etanol"),
    "oleo_diesel_correntes": ("OLEO DIESEL", "biodiesel"),
    "glp_domestico_p13": ("GLP", None),      # sem blend; alíquota zero (P13)
}


def _vigencias_federais() -> pd.DataFrame:
    """Vigências PIS/Cofins ad rem validadas: 1 alíquota por produto
    DEDUZIDO × mês da janela 2024-2025 (linhas NAO_DEDUZIDO são perímetro
    documentado — GLP granel e QAV — e não entram no cálculo)."""
    MANIFEST.registra_arquivo(PIS_COFINS_VIGENCIAS_CSV)
    df = pd.read_csv(PIS_COFINS_VIGENCIAS_CSV)
    df["vigencia_inicio"] = pd.to_datetime(df["vigencia_inicio"])
    df["vigencia_fim"] = pd.to_datetime(df["vigencia_fim"])
    ded = df[df["tratamento"] == "DEDUZIDO"]
    if set(_FEDERAL_PRODUTO_ANP) != set(ded["produto"]):
        raise ValueError("produtos DEDUZIDO ≠ mapa _FEDERAL_PRODUTO_ANP")
    for produto in _FEDERAL_PRODUTO_ANP:
        sel = ded[ded["produto"] == produto]
        for ano in config.JANELA_RECEITA:
            for mes in range(1, 13):
                ini = pd.Timestamp(ano, mes, 1)
                fim = ini + pd.offsets.MonthEnd(0)
                if len(sel[(sel["vigencia_inicio"] <= ini)
                           & (sel["vigencia_fim"] >= fim)]) != 1:
                    raise ValueError(f"{produto} {ano}-{mes:02d}: vigência "
                                     "federal ausente/duplicada")
    return df


def deducao_federal_combustiveis_mes() -> pd.DataFrame:
    """deducao_federal_combustiveis_mes.csv — dedução federal mês a mês.

    deducao(ano, mes, p) = volume_ANP_nacional(ano, mes, p) × fração fóssil
    × alíquota ad rem vigente no mês (Decreto 5.059/2004 e alteradores —
    constante em 2024-2025, tabela de vigências documenta; as reduções
    quase-zero de diesel/QAV são de 2026, fora da janela). Fração fóssil:
    blend VIGENTE NO MÊS (BLENDS_VIGENCIAS; Res. CNPE 8/2023 e 9/2025).
    GLP entra com alíquota ZERO (item POF = botijão doméstico P13, art. 2º,
    V do Decreto 5.059/2004; granel não separável em dado aberto). QAV NÃO é
    deduzido: a dedução é simétrica à exclusão dos itens POF de combustíveis
    da base — QAV é insumo do transporte aéreo, não consumo final das
    famílias (linha NAO_DEDUZIDO na tabela de vigências).
    """
    from .inputs.combustiveis import GLP_DENSIDADE_KG_M3_ANP, volumes_anp_mensais
    vig = _vigencias_federais()
    ded = vig[vig["tratamento"] == "DEDUZIDO"]
    vol = (volumes_anp_mensais()
           .groupby(["ano", "mes", "produto_anp"], as_index=False)["volume_m3"]
           .sum())
    linhas = []
    for ano in config.JANELA_RECEITA:
        for mes in range(1, 13):
            ini = pd.Timestamp(ano, mes, 1)
            fim = ini + pd.offsets.MonthEnd(0)
            for produto, (prod_anp, bio) in sorted(_FEDERAL_PRODUTO_ANP.items()):
                v = ded[(ded["produto"] == produto)
                        & (ded["vigencia_inicio"] <= ini)
                        & (ded["vigencia_fim"] >= fim)].iloc[0]
                rate, unidade = float(v["aliquota_rs"]), str(v["unidade"])
                v_m3 = float(vol[(vol["ano"] == ano) & (vol["mes"] == mes)
                                 & (vol["produto_anp"] == prod_anp)]
                             ["volume_m3"].sum())
                frac = 1.0 - (fracao_bio(bio, ano, mes) if bio else 0.0)
                if unidade == "R$/t":                 # GLP: m³ → t (ANP 0,552 t/m³)
                    base = v_m3 * frac * GLP_DENSIDADE_KG_M3_ANP / 1000.0
                    conv = "×0,552 t/m³ (ANP)"
                else:                                 # R$/m3
                    base = v_m3 * frac
                    conv = "em m³"
                linhas.append({
                    "ano": ano, "mes": mes, "produto": produto,
                    "volume_anp_m3": v_m3, "fracao_fossil": frac,
                    "base_tributavel": base, "unidade": unidade,
                    "aliquota_rs": rate, "deducao_rs": base * rate,
                    "ato": v["ato"],
                    "formula": ("deducao_rs = volume_anp_m3 × fracao_fossil "
                                f"(blend vigente no mês) {conv} × "
                                f"aliquota vigente em {ano}-{mes:02d}"),
                    "fonte": ("ANP (volumes mensais por UF, agregados) | "
                              "Decreto 5.059/2004 + alteradores (tabela "
                              "data/inputs/pis_cofins_combustiveis_vigencias"
                              ".csv; textos data/raw/normas/planalto_decretos/)"
                              " | blends mensais: Res. CNPE 8/2023 (B14 "
                              "01/03/2024) e 9/2025 (E30/B15 01/08/2025), "
                              "Lei 14.993/2024"),
                })
    df = pd.DataFrame(linhas)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.PROCESSED / "deducao_federal_combustiveis_mes.csv",
              index=False)
    return df


def pis_cofins_combustiveis(defl: float,
                            janela: tuple[int, ...] | None = None) -> float:
    """Parcela combustíveis de PIS/Cofins (deduzida simetricamente do alvo da
    União): volumes ANP mensais × ad rem federais VIGENTES no mês sobre a
    fração FÓSSIL da bomba (deducao_federal_combustiveis_mes). A dedução
    opera na JANELA 2024-2025, sobre o alvo CORRENTE da CBS — não sobre a
    âncora histórica 2012-2021 (%PIB), que permanece intacta. Etanol e
    biodiesel omitidos (ad rem próprios menores) e GLP granel a zero ⇒
    dedução subestimada ⇒ τ_CBS cota superior — coerente com o proxy
    iso-carga do IS (cota inferior do IS). QAV não deduzido (simetria com a
    base POF — ver deducao_federal_combustiveis_mes)."""
    mensal = deducao_federal_combustiveis_mes()
    por_ano = mensal.groupby("ano")["deducao_rs"].sum() / BI
    valor = media_janela_serie(por_ano, defl, janela)
    MANIFEST.registra("piscofins_combustiveis" + _sufixo_janela(janela), Num(
        valor, "Σ_mes volumes ANP fósseis × ad rem federais vigentes no mês "
        "(E27/E30, B14/B15; GLP=0 no P13; QAV não deduzido)",
        "ANP + Decreto 5.059/2004 e alteradores (vigências 2024-2025) + "
        "Lei 14.993/2024", Label.DERIVADO, "R$ bi 2024"))
    return valor


def is_estimado_bi(defl: float,
                   janela: tuple[int, ...] | None = None) -> float:
    """Imposto Seletivo estimado por proxy iso-carga (R$ bi 2024, janela).

    Convenção declarada: IS estimado = arrecadação CORRENTE de IPI nos
    produtos do campo do IS (fumo, bebidas e veículos — LC 214, art. 409 e
    Anexo XVII), linhas I.P.I-FUMO/BEBIDAS/AUTOMÓVEIS do XLSX RFB, média da
    janela 2024-2025 deflacionada. As alíquotas do IS aguardam lei ordinária
    (art. 414) ⇒ o proxy é COTA INFERIOR do IS (o campo legal é mais amplo:
    bebidas açucaradas, embarcações/aeronaves, bens minerais, prognósticos;
    e a carga do IS sobre fumo/bebidas tende a exceder a do IPI atual),
    mantendo τ_CBS como cota superior — direção declarada.
    """
    from .fetch.rfb_federal import parse_rfb_receitas
    df = parse_rfb_receitas(list(config.JANELA_RECEITA)).set_index("ano")
    cols = ["ipi_fumo", "ipi_bebidas", "ipi_automoveis"]
    por_ano = df[cols].sum(axis=1) / 1e3          # R$ mi -> R$ bi correntes
    valor = media_janela_serie(por_ano, defl, janela)
    MANIFEST.registra("is_estimado_proxy_ipi" + _sufixo_janela(janela), Num(
        valor,
        "média janela deflacionada de (I.P.I-FUMO + I.P.I-BEBIDAS + "
        "I.P.I-AUTOMÓVEIS); proxy iso-carga = cota INFERIOR do IS",
        "XLSX RFB 1994-2025 (linhas I.P.I-*); campo do IS: LC 214, art. 409 "
        "+ Anexo XVII (alíquotas aguardam lei ordinária, art. 414)",
        Label.DERIVADO, "R$ bi 2024"))
    return valor


_ANCORA_METRICA = {
    "liquida_rtn": "media_pct_pib_2012_2021_liquida_rtn",
    "bruta_rfb": "media_pct_pib_2012_2021",
}


def alvo_uniao(defl: float, is_estimado: float | None = None,
               ancora_federal: str | None = None,
               janela: tuple[int, ...] | None = None) -> dict[str, float]:
    """Alvo da CBS (art. 353 §1º). Defaults CENTRAIS: IS = proxy iso-carga
    (is_estimado_bi) e âncora LÍQUIDA-RTN; IS=0 e bruta-RFB = sensibilidades."""
    if ancora_federal is None:
        ancora_federal = config.ANCORA_FEDERAL_CENTRAL
    ancora = pd.read_csv(config.PROCESSED / "ancora_uniao.csv")
    pct = float(ancora.loc[ancora["metrica"] == _ANCORA_METRICA[ancora_federal],
                           "valor"].iloc[0]) / 100.0
    extras = pd.read_csv(config.V2_ROOT / "data" / "inputs" / "is_ipi_residual.csv")
    ipi_res = float(extras.loc[extras["item"] == "ipi_residual_zfm_liquido",
                               "valor"].iloc[0])
    is_cenario = "proxy_ipi_rfb" if is_estimado is None else "informado"
    if is_estimado is None:
        is_estimado = is_estimado_bi(defl, janela)

    pib = pib_janela_bi(defl, janela)
    bruto = pct * pib
    comb = pis_cofins_combustiveis(defl, janela)
    alvo = bruto - ipi_res - is_estimado - comb
    central = (is_cenario == "proxy_ipi_rfb"
               and ancora_federal == config.ANCORA_FEDERAL_CENTRAL
               and _sufixo_janela(janela) == "")
    chave = ("alvo_CBS" if central
             else (f"alvo_CBS_sens[{ancora_federal};is={is_cenario};"
                   f"is_bi={is_estimado:.4f}]" + _sufixo_janela(janela)))
    MANIFEST.registra(chave, Num(
        alvo,
        f"âncora 2012-2021 (%PIB, {ancora_federal}) × PIB janela − IPI "
        f"residual ZFM − IS estimado ({is_cenario}) "
        "− PIS/Cofins-combustíveis",
        "LC 214 art. 353; RTN/STN Tab. 2.2 (líquida) e RFB XLSX; NT SERT "
        "p.4; IS: LC 214 art. 409 + Anexo XVII (proxy = cota inferior)",
        Label.DERIVADO, "R$ bi 2024"))
    return {"alvo": alvo, "bruto_ancorado": bruto, "ipi_residual": ipi_res,
            "is_estimado": is_estimado, "piscofins_combustiveis": comb,
            "pib_janela": pib, "ancora_pct_pib": pct * 100.0,
            "ancora_federal": ancora_federal, "is_cenario": is_cenario}
