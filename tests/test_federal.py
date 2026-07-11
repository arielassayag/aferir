"""Testes da camada federal (União): XLSX RFB, RTN/STN, IPEADATA, PIB SIDRA,
âncora CBS e proxy iso-carga do IS.

Golden numbers medidos em 2026-07-10 sobre o cache congelado:
 - XLSX RFB 2021: Cofins 286.499,276 | PIS/Pasep 79.784,022 | IPI 74.940,359
   | IOF 48.640,134 (R$ mi) — Cofins 2021 confere com IPEADATA (286.499,3).
 - RTN/STN Tabela 2.2 (líquida de restituições, caixa) 2021: IPI 71.286,107
   | Cofins 274.580,947 | PIS/Pasep 76.089,027 | IOF 49.128,422 (R$ mi).
 - PIB 2021 = 9.012.142 R$ mi (IBGE, soma dos 4 trimestres SIDRA 1846).
 - Âncora União (art. 353): média 2012-2021 = 5,126971% PIB (CENTRAL,
   convenção líquida-RTN, Tema 69) e 5,114299% PIB (bruta-RFB,
   sensibilidade); razão IOF-seguros 0,088234.
 - IS estimado (proxy iso-carga, LC 214 art. 409 + Anexo XVII): IPI
   fumo+bebidas+automóveis 2024 = 17.168,210 | 2025 = 18.936,710 R$ mi;
   média janela deflacionada = 17,600 R$ bi 2024.

Os testes leem o cache de data/raw/ (populado por `fetch_all`); se o cache
não existir, são pulados (rode as rotinas de fetch antes — make fetch).
"""
from __future__ import annotations

import csv
import re

import pandas as pd
import pytest

from aferir import config
from aferir.fetch import ibge, rfb_federal

_CACHE_RFB = (rfb_federal.RAW_RFB
              / config.RFB_XLSX_URL.rsplit("/", 1)[-1])
_CACHE_RTN = (rfb_federal.RAW_STN
              / config.RTN_XLSX_URL.rsplit("/", 1)[-1])
_CACHE_PIB = ibge.RAW_SIDRA / ibge._ARQ
_CACHE_IPEA = rfb_federal.RAW_IPEADATA / "SRF12_COFINS12.json"

precisa_xlsx = pytest.mark.skipif(not _CACHE_RFB.exists(),
                                  reason="cache XLSX RFB ausente (make fetch)")
precisa_rtn = pytest.mark.skipif(not _CACHE_RTN.exists(),
                                 reason="cache XLSX RTN/STN ausente (make fetch)")
precisa_pib = pytest.mark.skipif(not _CACHE_PIB.exists(),
                                 reason="cache SIDRA 1846 ausente (make fetch)")
precisa_ipea = pytest.mark.skipif(not _CACHE_IPEA.exists(),
                                  reason="cache IPEADATA ausente (make fetch)")


@pytest.mark.network
def test_fetch_idempotente_grava_meta():
    """fetch_all baixa (ou reusa) cache e grava _meta.json com url+sha256."""
    import json
    paths = rfb_federal.fetch_all()
    paths.append(ibge.fetch_sidra_pib())
    for p in paths:
        meta = json.loads(
            p.with_name(p.name + "._meta.json").read_text(encoding="utf-8"))
        assert set(meta) >= {"url", "sha256", "collected_at", "bytes"}
        assert meta["bytes"] == p.stat().st_size


# ------------------------------------------------------------- XLSX (rota 1)
@precisa_xlsx
def test_xlsx_2021_golden():
    df = rfb_federal.parse_rfb_receitas([2021]).set_index("ano")
    assert df.loc[2021, "cofins"] == pytest.approx(286499.276, abs=0.01)
    assert df.loc[2021, "pis_pasep"] == pytest.approx(79784.022, abs=0.01)
    assert df.loc[2021, "ipi"] == pytest.approx(74940.359, abs=0.01)
    assert df.loc[2021, "iof_total"] == pytest.approx(48640.134, abs=0.01)


@precisa_xlsx
def test_xlsx_janela_completa():
    anos = sorted(set(config.ANCORA_UNIAO) | set(config.JANELA_RECEITA))
    df = rfb_federal.parse_rfb_receitas(anos)
    assert list(df["ano"]) == anos
    assert list(df.columns) == ["ano", *config.RFB_XLSX_ROTULOS]
    assert (df.drop(columns="ano") > 0).all().all()
    # subcomponentes do proxy do IS nunca excedem o IPI total
    assert ((df["ipi_fumo"] + df["ipi_bebidas"] + df["ipi_automoveis"])
            < df["ipi"]).all()


# ------------------------------------------------ RTN/STN (âncora líquida)
@precisa_rtn
def test_rtn_2021_golden():
    """Golden da rota líquida-RTN (Tema 69): Tabela 2.2, ano 2021."""
    df = rfb_federal.parse_rtn_receitas([2021]).set_index("ano")
    assert df.loc[2021, "ipi"] == pytest.approx(71286.107, abs=0.01)
    assert df.loc[2021, "cofins"] == pytest.approx(274580.947, abs=0.01)
    assert df.loc[2021, "pis_pasep"] == pytest.approx(76089.027, abs=0.01)
    assert df.loc[2021, "iof_total"] == pytest.approx(49128.422, abs=0.01)


@precisa_rtn
@precisa_xlsx
def test_rtn_ordem_de_grandeza_vs_rfb():
    """As duas rotas abertas medem o MESMO objeto em conceitos distintos
    (líquida-caixa × bruta-arrecadação): desvio anual por tributo < 15%."""
    anos = list(config.ANCORA_UNIAO)
    rtn = rfb_federal.parse_rtn_receitas(anos).set_index("ano")
    rfb = rfb_federal.parse_rfb_receitas(anos).set_index("ano")
    for t in ("pis_pasep", "cofins", "ipi", "iof_total"):
        desvio = ((rtn[t] - rfb[t]).abs() / rfb[t]).max()
        assert desvio < 0.15, f"{t}: desvio {desvio:.3f}"


@precisa_rtn
def test_rtn_anos_ausentes_falha():
    with pytest.raises(ValueError, match="anos ausentes"):
        rfb_federal.parse_rtn_receitas([1990])


# ------------------------------------------------ IS: proxy iso-carga (IPI)
@precisa_xlsx
def test_is_estimado_golden():
    """IS estimado = IPI fumo+bebidas+automóveis, média janela deflacionada
    (cota inferior do IS — LC 214, art. 409 + Anexo XVII)."""
    from aferir.revenue import is_estimado_bi
    from aferir.inputs.ipca_pib import deflator_para_2024
    defl = float(deflator_para_2024(2025).valor)
    valor = is_estimado_bi(defl)
    soma_2024 = (8164.875547 + 3111.731289 + 5891.602735) / 1e3
    soma_2025 = (11190.707486 + 3207.984427 + 4538.018247) / 1e3
    assert valor == pytest.approx((soma_2024 + soma_2025 * defl) / 2, abs=1e-9)
    assert valor == pytest.approx(17.600, abs=0.001)


# ------------------------------------------- IPEADATA (fallback/triangulação)
@precisa_ipea
def test_ipeadata_cofins_2021_golden():
    """Golden do fallback: Cofins 2021 = 286.499,3 R$ mi (soma dos meses)."""
    serie = rfb_federal.ipeadata_anual("cofins", [2021])
    assert serie[2021] == pytest.approx(286499.3, abs=0.1)


@precisa_xlsx
@precisa_ipea
def test_crosscheck_xlsx_ipeadata():
    """As duas rotas abertas coincidem (mesma origem RFB) em toda a janela."""
    quadro = rfb_federal.crosscheck_ipeadata(tol_rel=1e-6)
    assert len(quadro) == 4 * 12  # 4 tributos × (10 anos âncora + 2 janela)
    assert quadro["diff_rel"].max() < 1e-9


# ----------------------------------------------------------------- PIB SIDRA
@precisa_pib
def test_pib_2021_golden():
    pib = ibge.pib_nominal_anual([2021]).set_index("ano")
    assert pib.loc[2021, "pib_rs_mi"] == pytest.approx(9_012_142, abs=1.0)


@precisa_pib
def test_pib_validacao_cruzada_contas_anuais():
    """Soma dos trimestres reproduz o PIB anual (5938 Σ UFs: 2022/2023)."""
    pib = ibge.pib_nominal_anual([2022, 2023, 2024, 2025]).set_index("ano")
    assert pib.loc[2022, "pib_rs_mi"] == pytest.approx(10_079_676, abs=10.0)
    assert pib.loc[2023, "pib_rs_mi"] == pytest.approx(10_943_344, abs=10.0)
    assert pib.loc[2024, "pib_rs_mi"] > 11_000_000
    assert pib.loc[2025, "pib_rs_mi"] > 12_000_000


# --------------------------------------------------- r_uniao / âncora art. 353
@precisa_xlsx
@precisa_pib
def test_r_uniao_consistencia():
    from aferir.inputs.uniao import r_uniao, razao_iof_seguros
    df = r_uniao()
    razao = razao_iof_seguros().valor
    assert razao == pytest.approx(0.088234162377, abs=1e-9)
    assert 0.05 < razao < 0.15
    recomposto = df["pis_pasep"] + df["cofins"] + df["ipi"] + df["iof_seguros"]
    assert (df["receita_ref_rs_mi"] - recomposto).abs().max() < 1e-6
    assert (df["iof_seguros"] - df["iof_total"] * razao).abs().max() < 1e-6
    assert {"formula", "fonte"} <= set(df.columns)          # proveniência
    assert df["fonte"].str.len().min() > 0


@precisa_xlsx
@precisa_rtn
@precisa_pib
def test_ancora_uniao_golden():
    from aferir.inputs.uniao import ancora_uniao
    a = ancora_uniao().set_index("metrica")["valor"]
    # central (Tema 69, líquida-RTN) e sensibilidade (bruta-RFB)
    assert a["media_pct_pib_2012_2021_liquida_rtn"] == pytest.approx(
        5.126971, abs=1e-4)
    assert a["media_pct_pib_2012_2021"] == pytest.approx(5.114299, abs=1e-4)
    assert a["delta_liquida_menos_bruta_pct_pib"] == pytest.approx(
        a["media_pct_pib_2012_2021_liquida_rtn"]
        - a["media_pct_pib_2012_2021"], abs=1e-9)
    assert a["media_pct_pib_2012_2021_sem_iof_seguros"] == pytest.approx(
        5.068043, abs=1e-4)
    # rateio IOF-seguros pesa < 0,05 p.p. da âncora (segunda ordem — C3)
    assert 0.0 < (a["media_pct_pib_2012_2021"]
                  - a["media_pct_pib_2012_2021_sem_iof_seguros"]) < 0.05
    # convenções abertas divergem pouco (< 0,05 p.p. do PIB) — Tema 69 MEDIDO
    assert abs(a["delta_liquida_menos_bruta_pct_pib"]) < 0.05


@precisa_xlsx
@precisa_rtn
@precisa_pib
def test_grava_processados_determinista(tmp_path, monkeypatch):
    """Duas gravações consecutivas produzem bytes idênticos."""
    from aferir.inputs import uniao
    monkeypatch.setattr(config, "PROCESSED", tmp_path)
    uniao.grava_processados()
    primeira = {p.name: p.read_bytes() for p in tmp_path.glob("*.csv")}
    uniao.grava_processados()
    segunda = {p.name: p.read_bytes() for p in tmp_path.glob("*.csv")}
    assert primeira == segunda
    assert set(primeira) == {"r_uniao.csv", "r_uniao_liquida.csv",
                             "pib_nominal.csv", "ancora_uniao.csv"}


# ------------------------------------------------- insumos transcritos (URLs)
def _le_csv(nome: str) -> list[dict]:
    with open(config.INPUTS / nome, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --------------------------- vigências federais (Decreto 5.059/2004 — A2/A3)
# Substitui a transcrição estática de pis_cofins_ad_rem.csv: a tabela de
# vigências (data/inputs/pis_cofins_combustiveis_vigencias.csv) é acessada
# via revenue._vigencias_federais(), que valida 24 meses × produto DEDUZIDO.
_DECRETO_5059 = (config.V2_ROOT / "data" / "raw" / "normas"
                 / "planalto_decretos" / "d5059.htm")
precisa_decreto = pytest.mark.skipif(
    not _DECRETO_5059.exists(),
    reason="texto do Decreto 5.059/2004 ausente (data/raw/normas)")


def _componentes_ato(ato: str) -> tuple[float, float] | None:
    """(PIS, Cofins) transcritos no campo `ato`, se presentes."""
    m = re.search(r"PIS R\$ (\d+,\d{2}) \+ Cofins R\$ (\d+,\d{2})", ato)
    if m is None:
        return None
    return tuple(float(v.replace(",", ".")) for v in m.groups())


def test_vigencias_federais_cobertura_mensal():
    """Todo mês da janela 2024-2025 tem EXATAMENTE 1 alíquota vigente por
    produto DEDUZIDO (verificado aqui célula a célula, além da validação
    interna de revenue._vigencias_federais)."""
    from aferir import revenue
    vig = revenue._vigencias_federais()
    ded = vig[vig["tratamento"] == "DEDUZIDO"]
    assert set(ded["produto"]) == {
        "gasolina_correntes", "oleo_diesel_correntes", "glp_domestico_p13",
    }
    for produto, sel in ded.groupby("produto"):
        for ano in config.JANELA_RECEITA:
            for mes in range(1, 13):
                ini = pd.Timestamp(ano, mes, 1)
                fim = ini + pd.offsets.MonthEnd(0)
                vigentes = sel[(sel["vigencia_inicio"] <= ini)
                               & (sel["vigencia_fim"] >= fim)]
                assert len(vigentes) == 1, (produto, ano, mes)


def test_vigencias_federais_valores_decreto_5059():
    """Alíquotas da janela = Decreto 5.059/2004 vigente (valores lidos da
    própria tabela em 12/07/2026): gasolina 792,50 R$/m³ (PIS 141,10 +
    Cofins 651,40), diesel 351,50 R$/m³ (62,61 + 288,89), GLP P13 zero
    (art. 2º, V). Consistência interna: PIS + Cofins do `ato` == total."""
    from aferir import revenue
    vig = revenue._vigencias_federais()
    tab = vig.set_index("produto")
    assert float(tab.loc["gasolina_correntes", "aliquota_rs"]) == \
        pytest.approx(792.50, abs=1e-9)
    assert tab.loc["gasolina_correntes", "unidade"] == "R$/m3"
    assert float(tab.loc["oleo_diesel_correntes", "aliquota_rs"]) == \
        pytest.approx(351.50, abs=1e-9)
    assert tab.loc["oleo_diesel_correntes", "unidade"] == "R$/m3"
    assert float(tab.loc["glp_domestico_p13", "aliquota_rs"]) == 0.0
    assert tab.loc["glp_domestico_p13", "unidade"] == "R$/t"
    assert "zero" in tab.loc["glp_domestico_p13", "ato"]
    for _, r in vig.iterrows():
        comp = _componentes_ato(str(r["ato"]))
        if comp is not None:  # linhas com componentes transcritos no ato
            assert comp[0] + comp[1] == pytest.approx(
                float(r["aliquota_rs"]), abs=1e-9), r["produto"]
        assert r["fonte_url"].startswith("https://www.planalto.gov.br/")
        assert "Decreto 5.059/2004" in str(r["ato"])
        assert str(r["nota"]).strip(), r["produto"]


def test_vigencias_federais_perimetro_nao_deduzido():
    """GLP granel e QAV documentados como NAO_DEDUZIDO (perímetro declarado:
    granel não separável em dado aberto; QAV é insumo do transporte aéreo,
    simetria com a base POF) — valores lidos da tabela em 12/07/2026."""
    from aferir import revenue
    vig = revenue._vigencias_federais()
    nao = vig[vig["tratamento"] == "NAO_DEDUZIDO"].set_index("produto")
    assert set(nao.index) == {"glp_exceto_domestico_13kg", "querosene_aviacao"}
    assert float(nao.loc["glp_exceto_domestico_13kg", "aliquota_rs"]) == \
        pytest.approx(167.70, abs=1e-9)
    assert nao.loc["glp_exceto_domestico_13kg", "unidade"] == "R$/t"
    assert float(nao.loc["querosene_aviacao", "aliquota_rs"]) == \
        pytest.approx(71.20, abs=1e-9)
    assert nao.loc["querosene_aviacao", "unidade"] == "R$/m3"
    # justificativa documentada na própria tabela
    assert "granel" in nao.loc["glp_exceto_domestico_13kg", "nota"]
    assert "QAV" in nao.loc["querosene_aviacao", "nota"]


@precisa_decreto
def test_vigencias_federais_contra_texto_decreto():
    """Cada componente PIS/Cofins transcrito no `ato` aparece literalmente
    no texto consolidado do Decreto 5.059/2004 (cache Planalto local)."""
    from aferir import revenue
    texto = _DECRETO_5059.read_text(encoding="latin-1", errors="replace")
    vig = revenue._vigencias_federais()
    conferidos = 0
    for _, r in vig.iterrows():
        comp = _componentes_ato(str(r["ato"]))
        if comp is None:
            continue
        for valor in re.search(
                r"PIS R\$ (\d+,\d{2}) \+ Cofins R\$ (\d+,\d{2})",
                str(r["ato"])).groups():
            assert valor in texto, (r["produto"], valor)
            conferidos += 1
    assert conferidos == 8  # 2 componentes × 4 produtos com ad rem > 0


def test_is_ipi_residual_transcricao():
    linhas = {r["item"]: r for r in _le_csv("is_ipi_residual.csv")}
    assert float(linhas["iof_seguros_acrescimo_meta"]["valor"]) == 5.4
    assert float(linhas["ipi_residual_zfm_liquido"]["valor"]) == 2.6
    assert float(linhas["fundos_estaduais_desconto_meta"]["valor"]) == 3.5
    # a projeção oficial do IS é fronteira OD/ADM: valor VAZIO + nota citando
    # o PLDO 2027 (Anexo IV.2) — não inventar número onde não há fonte.
    assert linhas["is_projecao_oficial_2027"]["valor"] == ""
    assert "PLDO 2027" in linhas["is_projecao_oficial_2027"]["fonte"]
    for r in linhas.values():
        assert r["url"].startswith("https://"), r["item"]
        assert r["pagina"], r["item"]
    # coerência com a constante de config usada na razão IOF-seguros
    assert (float(linhas["iof_seguros_acrescimo_meta"]["valor"]) * 1000.0
            == config.IOF_SEGUROS_META_SERT_RS_MI)
