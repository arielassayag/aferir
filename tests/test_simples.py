"""Testes do A7/E1 - cunha do Simples Nacional (aferir.simples).

Estruturais + goldens dos artefatos: determinismo (reexecução gera bytes
idênticos aos artefatos em disco), sanidade de domínio (0 < ω < 0,5;
contribuições somam o agregado; r_simples > 0), contrato do orquestrador
(linha TOTAL de omega_simples.csv; chaves de r_simples_por_esfera) e
rastreabilidade (formula/fonte por linha; citações legais conferidas nos
textos compilados). Nenhum valor absoluto é pinado além de bandas largas
de ordem de grandeza declaradas nos próprios artefatos.
"""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from aferir import config, simples
from aferir.provenance import MANIFEST, sha256_file

_PORTE_ARQUIVOS = [
    f"pac_1399_{simples.ANO_PORTE}.json",
    f"pia_1839_{simples.ANO_PORTE}.json",
] + [f"pas_{t}_{simples.ANO_PORTE}.json"
     for t in (2611, 2624, 2635, 2650, 2665, 2676, 2695)]

_TEM_PORTE = all((simples.RAW_PORTE / a).exists() for a in _PORTE_ARQUIVOS)
_TEM_TRU = (config.PROCESSED / "tru_2021_usos.parquet").exists()
_TEM_LC123 = simples.LC123_HTML.exists()
_TEM_SN = simples.SN_XLSX.exists()
_TEM_EMENTARIO = all((simples.EMENTARIO_DIR
                      / f"ementario_receita_{a}.xlsx").exists()
                     for a in (2024, 2025))
_TEM_REGULAMENTO = simples.REGULAMENTO_PDF.exists()
_TEM_ALVOS = all((config.PROCESSED / n).exists() for n in
                 ("r_estadual.csv", "r_municipal_uf.csv",
                  "combustiveis_uf.csv", "fundos_estaduais.csv"))

_TEM_OMEGA_INSUMOS = _TEM_PORTE and _TEM_TRU and _TEM_LC123
_TEM_QA_INSUMOS = (_TEM_OMEGA_INSUMOS and _TEM_SN and _TEM_EMENTARIO
                   and _TEM_REGULAMENTO and _TEM_ALVOS)


def _defl() -> float:
    from aferir.revenue import deflator_2025
    return deflator_2025()


# ------------------------------------------------------------ ω: sanidade
@pytest.mark.skipif(not _TEM_OMEGA_INSUMOS,
                    reason="insumos de ω ausentes (porte/TRU/LC123)")
def test_omega_dominio_e_agregacao():
    df = simples.omega_simples(grava=False)
    total = df[df["atividade"] == "TOTAL"]
    assert len(total) == 1
    omega = float(total["contribuicao_omega"].iloc[0])
    # sanidade de domínio pedida na revisão: 0 < ω < 0,5
    assert 0.0 < omega < 0.5
    # contribuições somam o agregado
    parciais = df.loc[df["atividade"] != "TOTAL", "contribuicao_omega"].sum()
    assert math.isclose(parciais, omega, rel_tol=1e-12)
    # pesos dos produtos EM CAMPO somam 1 (partição completa da TRU)
    em_campo = df[(df["atividade"] != "TOTAL")
                  & (df["medida"] != "fora_do_campo")]
    assert math.isclose(em_campo["peso_consumo"].sum(), 1.0, rel_tol=1e-9)
    # shares medidos dentro de (0, 1); propensão B2C dentro de [0, 1]
    med = df[df["medida"].isin(("direta", "proxy_diferenca"))]
    assert ((med["share_pequenas"] > 0) & (med["share_pequenas"] < 1)).all()
    assert ((em_campo["propensao_b2c"] >= 0)
            & (em_campo["propensao_b2c"] <= 1.0 + 1e-12)).all()
    # fronteiras contribuem zero (cota inferior declarada)
    front = df[df["medida"].isin(("fronteira_sem_porte", "vedacao_legal"))]
    assert (front["contribuicao_omega"] == 0.0).all()
    assert len(front) > 0


@pytest.mark.skipif(not _TEM_OMEGA_INSUMOS,
                    reason="insumos de ω ausentes (porte/TRU/LC123)")
def test_omega_deterministico():
    a = simples.omega_simples(grava=False)
    b = simples.omega_simples(grava=False)
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.skipif(not (_TEM_OMEGA_INSUMOS and simples.CSV_OMEGA.exists()),
                    reason="omega_simples.csv ainda não gerado")
def test_omega_golden_byte_identico():
    """Reexecução reproduz o artefato em disco byte a byte (determinismo)."""
    regen = simples.omega_simples(grava=False).to_csv(index=False)
    assert regen == simples.CSV_OMEGA.read_text(encoding="utf-8")


@pytest.mark.skipif(not simples.CSV_OMEGA.exists(),
                    reason="omega_simples.csv ainda não gerado")
def test_omega_contrato_orquestrador():
    """Contrato lido pelo pipeline: linha TOTAL única com o ω nacional."""
    om = pd.read_csv(simples.CSV_OMEGA)
    sel = om.loc[om["atividade"] == "TOTAL", "contribuicao_omega"]
    assert len(sel) == 1
    assert math.isclose(float(sel.iloc[0]), simples.carrega_omega(),
                        rel_tol=1e-12)


@pytest.mark.skipif(not simples.CSV_OMEGA.exists(),
                    reason="omega_simples.csv ainda não gerado")
def test_omega_rastreabilidade_por_linha():
    om = pd.read_csv(simples.CSV_OMEGA)
    for col in ("formula", "fonte"):
        assert col in om.columns
        assert om[col].notna().all()
        assert (om[col].str.len() > 10).all()
    # regra do projeto: colunas/prosa sem travessão
    texto = simples.CSV_OMEGA.read_text(encoding="utf-8")
    assert "—" not in texto


@pytest.mark.skipif(not _TEM_OMEGA_INSUMOS,
                    reason="insumos de ω ausentes (porte/TRU/LC123)")
def test_omega_registra_manifest():
    simples.omega_simples(grava=False)
    assert "omega_simples_nacional" in MANIFEST.nums
    num = MANIFEST.nums["omega_simples_nacional"]
    assert 0.0 < num.valor < 0.5
    assert "PAC" in num.fonte and "TRU" in num.fonte


# --------------------------------------------------- r_simples (dois lados)
@pytest.mark.skipif(not (_TEM_SN and _TEM_ALVOS),
                    reason="XLSX RFB do Simples ou alvos ausentes")
def test_r_simples_positivo_e_sanidade():
    rs = simples.r_simples_por_esfera(_defl())
    assert set(rs) == {"r_simples_icms_bi", "r_simples_iss_bi",
                       "share_icms", "share_iss"}
    assert rs["r_simples_icms_bi"] > 0
    assert rs["r_simples_iss_bi"] > 0
    assert 0.0 < rs["share_icms"] < 0.5
    assert 0.0 < rs["share_iss"] < 0.5
    # estrutural: o Simples pesa proporcionalmente MAIS no ISS que no ICMS
    assert rs["share_iss"] > rs["share_icms"]


@pytest.mark.skipif(not (_TEM_SN and _TEM_ALVOS),
                    reason="XLSX RFB do Simples ou alvos ausentes")
def test_r_simples_deterministico_e_manifest():
    a = simples.r_simples_por_esfera(_defl())
    b = simples.r_simples_por_esfera(_defl())
    assert a == b
    for chave in ("r_simples_icms_bi", "r_simples_iss_bi",
                  "share_simples_icms_alvo_E", "share_simples_iss_alvo_M"):
        assert chave in MANIFEST.nums


@pytest.mark.skipif(not _TEM_SN, reason="XLSX RFB do Simples ausente")
def test_sn_xlsx_esferas_somam_total():
    sn = simples._sn_anual()
    assert {2024, 2025} <= set(sn.index)
    soma = sn[["uniao", "estados", "municipios"]].sum(axis=1)
    assert ((soma - sn["total"]).abs() <= 0.01 * sn["total"]).all()


# ------------------------------------------------------------- QA (E1b/E1c)
@pytest.mark.skipif(not _TEM_QA_INSUMOS, reason="insumos do QA ausentes")
def test_qa_estrutura_e_itens():
    qa = simples.qa_numeradores(grava=False)
    itens = set(qa["item"])
    assert {"iss_natureza_consolidada", "icms_natureza_consolidada",
            "ementario_varredura", "icms_simples_vs_numerador",
            "iss_simples_vs_numerador", "r_simples_icms_janela",
            "r_simples_iss_janela", "lacuna_abertura_uf_tributo",
            "desenho_oficial_dois_lados",
            "st_monofasia_fora_do_das"} <= itens
    # a lacuna 2024-2025 referencia a diligência F7
    lacuna = qa[qa["item"] == "lacuna_abertura_uf_tributo"].iloc[0]
    assert "F7" in lacuna["fonte"]
    # o cenário dois lados transcreve o dispositivo literal do Regulamento
    oficial = qa[qa["item"] == "desenho_oficial_dois_lados"].iloc[0]
    assert "Lei Complementar nº 123" in oficial["texto_literal"]
    assert "art. 600" in oficial["fonte"] or "600" in oficial["fonte"]
    for col in ("formula", "fonte"):
        assert qa[col].notna().all()


@pytest.mark.skipif(not (_TEM_QA_INSUMOS and simples.CSV_QA.exists()),
                    reason="qa_simples_numeradores.csv ainda não gerado")
def test_qa_golden_byte_identico():
    regen = simples.qa_numeradores(grava=False).to_csv(index=False)
    assert regen == simples.CSV_QA.read_text(encoding="utf-8")


@pytest.mark.skipif(not _TEM_EMENTARIO,
                    reason="Ementário STN 2024/2025 ausente")
def test_ementario_sem_natureza_simples_para_icms_iss():
    """Prova por exaustão: as únicas naturezas 'Simples' do Ementário são
    contribuições federais (12xx); ICMS/ISSQN ficam consolidados."""
    for ano in (2024, 2025):
        em = simples._ementario_varredura(ano)
        assert em["n_simples"] > 0
        assert all(nr.startswith("12") for nr in em["nrs_simples"])
        assert "Registra a arrecadação" in em["desc_icms"]
        assert "imposto sobre serviços" in em["desc_issqn"].lower()


# ----------------------------------------------------- citações e sidecars
@pytest.mark.skipif(not _TEM_LC123, reason="lcp123.htm ausente")
def test_citas_lc123_conferem_no_texto_compilado():
    simples._confere_lc123()      # levanta ValueError se citação não consta


@pytest.mark.skipif(not _TEM_REGULAMENTO,
                    reason="PDF do Regulamento do IBS ausente")
def test_citas_regulamento_conferem_no_pdf():
    simples._confere_regulamento()


@pytest.mark.skipif(not _TEM_PORTE, reason="payloads de porte ausentes")
def test_meta_sidecars_porte_integros():
    """_meta.json de cada raw de porte: sha256 batendo com o arquivo."""
    for nome in _PORTE_ARQUIVOS:
        arq = simples.RAW_PORTE / nome
        meta_path = arq.with_name(arq.name + "._meta.json")
        assert meta_path.exists(), f"sidecar ausente: {meta_path.name}"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["sha256"] == sha256_file(arq)


@pytest.mark.skipif(not _TEM_SN, reason="XLSX RFB do Simples ausente")
def test_meta_sidecar_sn_xlsx_integro():
    meta_path = simples.SN_XLSX.with_name(simples.SN_XLSX.name
                                          + "._meta.json")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["sha256"] == sha256_file(simples.SN_XLSX)
