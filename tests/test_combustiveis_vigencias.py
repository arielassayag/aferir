"""Itens A2/A3 — dedução ad rem mês a mês com tabelas de vigências.

Cobre: (i) cobertura completa das vigências (24 meses × produto, exatamente
1 alíquota/mês); (ii) goldens anuais medidos (rel 1e-9); (iii) alíquota de
janeiro ≠ fevereiro (reajustes de 01/02 dos Conv. 172-173/2023 e
126-127/2024); (iv) determinismo byte a byte; (v) esquema legado de
combustiveis_uf.csv inalterado; (vi) perímetro declarado (etanol hidratado
fora do ad rem; QAV não deduzido na esfera federal).
"""
import math

import pandas as pd
import pytest

from aferir import config, revenue
from aferir.inputs import combustiveis

JANELA = list(config.JANELA_RECEITA)          # [2024, 2025]
PRODUTOS_ICMS = ["DIESEL_B100", "GASOLINA_EAC", "GLP_GLGN"]


# ------------------------------------------------------ vigências ICMS (A2)
def test_vigencias_cobertura_completa():
    vig = combustiveis.vigencias_adrem()      # valida 24 meses × produto
    assert set(PRODUTOS_ICMS) <= set(vig["produto"])
    for produto in PRODUTOS_ICMS:
        for ano in JANELA:
            for mes in range(1, 13):
                v = combustiveis.aliquota_vigente(produto, ano, mes)
                assert float(v["aliquota_rs"]) > 0


def test_vigencias_valores_dos_convenios():
    # valores literais extraídos dos textos arquivados em data/raw/normas/confaz/
    esperado = {
        # (produto, ano, mes): alíquota
        ("GASOLINA_EAC", 2024, 1): 1.2200,   # Conv. 15/2023, redação original
        ("GASOLINA_EAC", 2024, 2): 1.3721,   # Conv. 173/2023, a partir de 01.02.24
        ("GASOLINA_EAC", 2025, 1): 1.3721,   # ainda Conv. 173/2023 (até 31.01.25)
        ("GASOLINA_EAC", 2025, 2): 1.4700,   # Conv. 127/2024, a partir de 01.02.25
        ("DIESEL_B100", 2024, 1): 0.9456,    # Conv. 199/2022, redação original
        ("DIESEL_B100", 2024, 2): 1.0635,    # Conv. 172/2023
        ("DIESEL_B100", 2025, 1): 1.0635,
        ("DIESEL_B100", 2025, 2): 1.1200,    # Conv. 126/2024
        ("GLP_GLGN", 2024, 1): 1.2571,       # Conv. 199/2022, redação original
        ("GLP_GLGN", 2024, 2): 1.4139,       # Conv. 172/2023
        ("GLP_GLGN", 2025, 1): 1.4139,
        ("GLP_GLGN", 2025, 2): 1.3900,       # Conv. 126/2024 (GLP CAI em 2025)
    }
    for (produto, ano, mes), aliq in esperado.items():
        v = combustiveis.aliquota_vigente(produto, ano, mes)
        assert math.isclose(float(v["aliquota_rs"]), aliq, rel_tol=0, abs_tol=0)


def test_etanol_hidratado_declarado_fora():
    bruto = pd.read_csv(combustiveis.VIGENCIAS_ADREM_CSV)
    nota = bruto[bruto["produto"] == "ETANOL_HIDRATADO"]
    assert len(nota) == 1 and nota["aliquota_rs"].isna().all()
    # a linha de nota NÃO entra na tabela consumida pelo cálculo
    assert "ETANOL_HIDRATADO" not in set(combustiveis.vigencias_adrem()["produto"])


# ------------------------------------------------- dedução mensal ICMS (A2)
def test_deducao_mensal_janeiro_difere_de_fevereiro():
    ded = combustiveis.deducao_adrem_uf_mes()
    assert len(ded) == 27 * 2 * 12 * 3
    jan24 = ded[(ded.ano == 2024) & (ded.mes == 1)].set_index(["uf", "produto"])
    fev24 = ded[(ded.ano == 2024) & (ded.mes == 2)].set_index(["uf", "produto"])
    assert (jan24["aliquota"] != fev24["aliquota"]).all()
    jan25 = ded[(ded.ano == 2025) & (ded.mes == 1)].set_index(["uf", "produto"])
    fev25 = ded[(ded.ano == 2025) & (ded.mes == 2)].set_index(["uf", "produto"])
    assert (jan25["aliquota"] != fev25["aliquota"]).all()
    # identidade: deducao_rs = volume × aliquota, no grão mensal
    assert (ded["deducao_rs"] - ded["volume"] * ded["aliquota"]).abs().max() < 1e-6


def test_golden_deducao_adrem_anual():
    df = combustiveis.combustiveis_uf()
    # goldens MEDIDOS em 2026-07-12 (vigências mensais + densidade GLP 0,552
    # t/m³ do Anuário ANP 2023; antes: 143,3028/157,0233 bi com alíquota
    # única anual e 550 kg/m³)
    nac = df.groupby("ano")["receita_adrem_estimada"].sum()
    assert math.isclose(nac[2024], 142081275890.55356, rel_tol=1e-9)
    assert math.isclose(nac[2025], 156396601264.27054, rel_tol=1e-9)


def test_esquema_combustiveis_uf_inalterado():
    df = combustiveis.combustiveis_uf()
    assert list(df.columns) == [
        "uf", "ano", "receita_adrem_estimada", "share_do_icms",
        "vol_gasolina_c_m3", "vol_oleo_diesel_m3", "vol_glp_m3",
        "formula", "fonte"]
    assert len(df) == 54
    assert ((df["share_do_icms"] > 0) & (df["share_do_icms"] < 0.6)).all()


def test_determinismo_bytes():
    combustiveis.combustiveis_uf()            # escreve os 2 CSVs (ICMS)
    revenue.deducao_federal_combustiveis_mes()
    caminhos = [config.PROCESSED / "combustiveis_uf.csv",
                config.PROCESSED / "deducao_icms_adrem_uf_mes.csv",
                config.PROCESSED / "deducao_federal_combustiveis_mes.csv"]
    antes = {p.name: p.read_bytes() for p in caminhos}
    combustiveis.combustiveis_uf()
    revenue.deducao_federal_combustiveis_mes()
    for p in caminhos:
        assert p.read_bytes() == antes[p.name], f"{p.name} não determinístico"


# ------------------------------------------------- dedução federal (A3)
def test_vigencias_federais_cobertura_e_perimetro():
    vig = revenue._vigencias_federais()       # valida 24 meses × produto DEDUZIDO
    ded = vig[vig["tratamento"] == "DEDUZIDO"]
    assert set(ded["produto"]) == {"gasolina_correntes", "oleo_diesel_correntes",
                                   "glp_domestico_p13"}
    # QAV e GLP granel: perímetro documentado, NÃO deduzido
    nao = vig[vig["tratamento"] == "NAO_DEDUZIDO"]
    assert set(nao["produto"]) == {"querosene_aviacao", "glp_exceto_domestico_13kg"}
    # alíquotas constantes na janela (Decreto 5.059/2004 pleno em 2024-2025)
    assert math.isclose(
        float(ded[ded["produto"] == "gasolina_correntes"]["aliquota_rs"].iloc[0]),
        792.50)
    assert math.isclose(
        float(ded[ded["produto"] == "oleo_diesel_correntes"]["aliquota_rs"].iloc[0]),
        351.50)
    assert float(ded[ded["produto"] == "glp_domestico_p13"]["aliquota_rs"].iloc[0]) == 0.0


def test_golden_deducao_federal_anual():
    mensal = revenue.deducao_federal_combustiveis_mes()
    assert len(mensal) == 2 * 12 * 3
    por_ano = mensal.groupby("ano")["deducao_rs"].sum()
    # goldens MEDIDOS em 2026-07-12 com blends VIGENTES POR MÊS (Res. CNPE
    # 8/2023: B12 até fev/2024, B14 desde 01/03/2024; Res. CNPE 9/2025:
    # E30/B15 desde 01/08/2025) — substituem a média anual convencionada
    assert math.isclose(por_ano[2024], 46141967693.64484, rel_tol=1e-9)
    assert math.isclose(por_ano[2025], 47401900737.678, rel_tol=1e-9)
    # GLP contribui zero (P13, art. 2º, V, Decreto 5.059/2004)
    assert (mensal[mensal["produto"] == "glp_domestico_p13"]["deducao_rs"] == 0).all()


def test_pis_cofins_combustiveis_consome_vigencias():
    valor = revenue.pis_cofins_combustiveis(revenue.deflator_2025())
    # golden MEDIDO em 2026-07-12 (R$ bi 2024, média da janela deflacionada;
    # blends mensais Res. CNPE 8/2023 e 9/2025 — antes, com médias anuais
    # convencionadas, o valor era 45,4807)
    assert math.isclose(valor, 45.63971668020977, rel_tol=1e-9)


def test_blends_vigencias_mensais():
    # Res. CNPE 8/2023: B12 em jan-fev/2024, B14 desde 01/03/2024;
    # Res. CNPE 9/2025: E30 e B15 desde 01/08/2025 (Lei 14.993/2024)
    assert revenue.fracao_bio("biodiesel", 2024, 2) == 0.12
    assert revenue.fracao_bio("biodiesel", 2024, 3) == 0.14
    assert revenue.fracao_bio("biodiesel", 2025, 7) == 0.14
    assert revenue.fracao_bio("biodiesel", 2025, 8) == 0.15
    assert revenue.fracao_bio("etanol", 2025, 7) == 0.27
    assert revenue.fracao_bio("etanol", 2025, 8) == 0.30
