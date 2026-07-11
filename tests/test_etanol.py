"""Dedução ad valorem do etanol hidratado (EHC) — achado da auditoria 2026-07.

O EHC é monofásico na LC 214 (art. 172, VI) e a base já o remove (TRU 19921
fora da âncora; itens POF de etanol fora das shares), mas está FORA dos
convênios ad rem da LC 192/2022 e recolhe ICMS AD VALOREM — que precisa sair
do alvo estadual simetricamente. Cobre: (i) estrutura da tabela curada de
vigências (27 UFs × 24 meses, exatamente 1 carga/mês, ato citado linha a
linha, cobertura específica×modal declarada); (ii) preços ANP-SLP completos
e plausíveis; (iii) dedução positiva e menor que o ICMS bruto de cada UF;
(iv) ordem de grandeza nacional (6-15 R$ bi/ano); (v) determinismo byte a
byte; (vi) simetria com a base (19921 removido; itens POF de etanol fora).
"""
import math

import pandas as pd

from aferir import config
from aferir.inputs import deducao_etanol

JANELA = list(config.JANELA_RECEITA)          # [2024, 2025]


# ------------------------------------------------- tabela curada (vigências)
def test_vigencias_estrutura_e_cobertura_mensal():
    vig = deducao_etanol.vigencias_etanol()   # valida 27 UFs × 24 meses
    assert set(vig["uf"]) == set(config.UFS)
    for uf in config.UFS:
        for ano in JANELA:
            for mes in range(1, 13):
                v = deducao_etanol.aliquota_vigente_etanol(uf, ano, mes)
                assert 0.05 < float(v["aliquota"]) < 0.30
                assert str(v["ato"]).strip()
                assert str(v["fonte_url"]).startswith("http")


def test_vigencias_colunas_e_atos():
    bruto = pd.read_csv(config.ETANOL_VIGENCIAS_CSV)
    assert {"uf", "aliquota", "vigencia_inicio", "vigencia_fim", "ato",
            "fonte_url", "nota"} <= set(bruto.columns)
    linhas = bruto.dropna(subset=["aliquota"])
    # ato normativo citado LINHA A LINHA (nenhuma vigência sem ato)
    assert linhas["ato"].astype(str).str.strip().ne("").all()
    assert linhas["fonte_url"].astype(str).str.startswith("http").all()


def test_cobertura_especifica_vs_modal_declarada():
    """A honestidade da tabela: UFs sem ato específico de EHC usam a MODAL
    com nota explícita; a linha-síntese BR declara a contagem."""
    bruto = pd.read_csv(config.ETANOL_VIGENCIAS_CSV)
    sintese = bruto[bruto["uf"] == "BR"]
    assert len(sintese) == 1 and sintese["aliquota"].isna().all()
    assert "COBERTURA" in str(sintese["nota"].iloc[0])
    linhas = bruto.dropna(subset=["aliquota"])
    modais = set(linhas.loc[linhas["nota"].astype(str)
                            .str.contains("modal", case=False), "uf"])
    especificas = set(linhas["uf"]) - modais
    # a contagem declarada na síntese bate com as linhas
    nota = str(sintese["nota"].iloc[0])
    assert f"{len(especificas)} UFs com ato específico" in nota
    assert f"{len(modais)} UFs na alíquota modal" in nota
    # a linha-síntese NÃO entra na tabela consumida pelo cálculo
    assert "BR" not in set(deducao_etanol.vigencias_etanol()["uf"])


# ------------------------------------------------------- preços ANP-SLP
def test_precos_cobertura_completa_e_plausivel():
    pre = deducao_etanol.precos_etanol_uf_mes()
    assert len(pre) == 27 * 2 * 12
    assert not pre["preco_rs_l"].isna().any()
    assert ((pre["preco_rs_l"] > 2.0) & (pre["preco_rs_l"] < 8.0)).all()


# ------------------------------------------------------------ dedução
def test_deducao_positiva_e_menor_que_icms_bruto():
    from aferir.inputs.siconfi_estadual import r_estadual
    ded = deducao_etanol.deducao_etanol_uf()
    assert len(ded) == 54
    assert (ded["receita_etanol_estimada"] > 0).all()
    icms = r_estadual().set_index(["uf", "ano"])["icms_bruto"]
    for _, r in ded.iterrows():
        assert r["receita_etanol_estimada"] < icms.loc[(r["uf"], r["ano"])]
    assert (ded["share_do_icms"] < 0.25).all()


def test_ordem_de_grandeza_nacional():
    ded = deducao_etanol.deducao_etanol_uf()
    for ano in JANELA:
        nac = float(ded[ded["ano"] == ano]["receita_etanol_estimada"].sum())
        assert 6e9 <= nac <= 15e9, f"{ano}: {nac/1e9:.2f} R$ bi"


def test_identidade_mensal():
    ded = deducao_etanol.deducao_etanol_uf_mes()
    assert len(ded) == 27 * 2 * 12
    err = (ded["deducao_rs"]
           - ded["volume_l"] * ded["preco_rs_l"] * ded["aliquota"]).abs()
    assert err.max() < 1e-6


def test_determinismo_bytes():
    deducao_etanol.deducao_etanol_uf()        # escreve os 2 CSVs
    caminhos = [config.PROCESSED / "deducao_icms_etanol_uf.csv",
                config.PROCESSED / "deducao_icms_etanol_uf_mes.csv"]
    antes = {p.name: p.read_bytes() for p in caminhos}
    deducao_etanol.vigencias_etanol.cache_clear()
    deducao_etanol.precos_etanol_uf_mes.cache_clear()
    deducao_etanol.deducao_etanol_uf()
    for p in caminhos:
        assert p.read_bytes() == antes[p.name], f"{p.name} não determinístico"


def test_meses_partidos_rateio_por_dias():
    """Trocas fora do dia 1º (MA 19/02/2024 e 23/02/2025; RN 20/03/2025)
    entram pela média ponderada pelos dias — convenção declarada."""
    rn = deducao_etanol.aliquota_vigente_etanol("RN", 2025, 3)
    assert rn["n_trechos"] == 2
    assert math.isclose(rn["aliquota"],
                        (19 * 0.153324 + 12 * 0.20) / 31, rel_tol=1e-12)
    ma24 = deducao_etanol.aliquota_vigente_etanol("MA", 2024, 2)   # bissexto
    assert ma24["n_trechos"] == 2
    assert math.isclose(ma24["aliquota"],
                        (18 * 0.20 + 11 * 0.22) / 29, rel_tol=1e-12)
    ma25 = deducao_etanol.aliquota_vigente_etanol("MA", 2025, 2)
    assert ma25["n_trechos"] == 2
    assert math.isclose(ma25["aliquota"],
                        (22 * 0.22 + 6 * 0.23) / 28, rel_tol=1e-12)
    # mês não partido: carga exata da vigência única (MG após 01/03/2024)
    mg = deducao_etanol.aliquota_vigente_etanol("MG", 2024, 3)
    assert mg["n_trechos"] == 1 and mg["aliquota"] == 0.1308


def test_golden_deducao_etanol_anual():
    df = deducao_etanol.deducao_etanol_uf()
    nac = df.groupby("ano")["receita_etanol_estimada"].sum()
    # goldens MEDIDOS em 2026-07-13 (volumes ANP vintage 2026-06-26 × preços
    # ANP-SLP vintage 2026-07-13 × tabela curada de vigências com atos)
    assert math.isclose(nac[2024], 11000261304.938343, rel_tol=1e-9)
    assert math.isclose(nac[2025], 11906235824.505823, rel_tol=1e-9)


# ------------------------------------------------- simetria com a base
def test_simetria_base_alvo():
    """O produto TRU do etanol (19921) está removido da âncora e os itens POF
    de etanol fora das shares — a dedução ad valorem fecha a simetria no ALVO."""
    from aferir.base import TRU_PRODUTOS_REMOVIDOS
    assert "19921" in TRU_PRODUTOS_REMOVIDOS
