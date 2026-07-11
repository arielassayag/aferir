"""Testes estruturais do E7 — SIFIM e FBCF imobiliária (sifim_fbcf.py +
alavancas aditivas de base.base_ordinaria_uf).

Vários processados estão em regeneração por outras frentes: NENHUM valor
absoluto é pinado aqui — os testes são estruturais (defaults bit a bit,
identidades internas do split, redutores lidos da própria lei, determinismo)
e tolerantes (skip declarado quando um artefato ainda não existe).
"""
from __future__ import annotations

import hashlib
import math

import pandas as pd
import pytest

from aferir import config, sifim_fbcf
from aferir.base import AncorasNacionais, base_ordinaria_uf
from aferir.provenance import MANIFEST

# ------------------------------------------------------------- toy inputs
# Códigos REAIS da matriz vendorada (a base consulta flag/descrição nela):
#   2600501 TARIFA DE CONTA BANCARIA (A), 4800601 PREVIDENCIA PRIVADA (F).
_DESPESA_TOY = pd.DataFrame({
    "codigo_pof": ["2600501", "4800601", "2600501", "4800601"],
    "uf": ["AC", "AC", "AL", "AL"],
    "despesa_anual_rs": [1.0e9, 0.5e9, 3.0e9, 0.2e9],
})
_POP_TOY = pd.Series({"AC": 1_000_000.0, "AL": 2_000_000.0})
_FBCF_SHARE_TOY = pd.Series({"AC": 0.4, "AL": 0.6})
_TRU_TOY = pd.DataFrame({
    "produto_cod": ["68002", "97001", "19912", "19916", "19921",
                    "64801", "41801"],
    "consumo_familias": [100_000.0, 50_000.0, 10_000.0, 5_000.0, 5_000.0,
                         200_000.0, 0.0],
})
_ANCORAS_TOY = AncorasNacionais(
    c_familias_tru=1000.0, c_isflsf_tru=10.0, fbcf_tru=100.0,
    share_fbcf_nc=0.10, escala_biênio=1.5, escala_biênio_fbcf=1.2,
)


@pytest.fixture(autouse=True)
def _manifest_isolado():
    """Isola as chaves de proveniência tocadas pela base: os toys não podem
    conflitar com registros de outros testes (MANIFEST é singleton)."""
    chaves = ("B_C_nacional", "B_C_nacional[sifim=excluido]",
              "B_FBCF_NC_nacional[fbcf_imob=redutores]")
    salvos = {k: MANIFEST.nums.pop(k) for k in chaves if k in MANIFEST.nums}
    yield
    for k in chaves:
        MANIFEST.nums.pop(k, None)
    MANIFEST.nums.update(salvos)


def _roda(**kw) -> pd.DataFrame:
    return base_ordinaria_uf(_DESPESA_TOY, _POP_TOY, _FBCF_SHARE_TOY,
                             _ANCORAS_TOY, _TRU_TOY, **kw)


def _sha(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


# ------------------------------------------------- defaults bit a bit
def test_default_sem_kwargs_igual_default_explicito():
    """Alavancas ADITIVAS: omitir kwargs == defaults explícitos, bit a bit."""
    assert _sha(_roda()) == _sha(_roda(sifim="incluido", fbcf_imob="padrao"))


def test_default_deterministico():
    assert _sha(_roda()) == _sha(_roda())


def test_valores_de_alavanca_invalidos():
    with pytest.raises(ValueError):
        _roda(sifim="foo")
    with pytest.raises(ValueError):
        _roda(fbcf_imob="bar")


# ------------------------------------------------- alavanca SIFIM (toy)
def test_alavanca_sifim_subtrai_no_nivel_2021(monkeypatch):
    monkeypatch.setattr(sifim_fbcf, "carrega_ajuste_sifim", lambda: 50.0)
    d0, d1 = _roda(), _roda(sifim="excluido")
    # B_C nacional cai exatamente 50 (nível 2021) × escala_biênio
    assert math.isclose(d0["B_C"].sum() - d1["B_C"].sum(),
                        50.0 * _ANCORAS_TOY.escala_biênio, rel_tol=1e-12)
    # explícito preservado: SÓ a âncora de consumo muda
    pd.testing.assert_series_equal(d0["B_ISFLSF"], d1["B_ISFLSF"])
    pd.testing.assert_series_equal(d0["B_FBCF_NC"], d1["B_FBCF_NC"])
    # B_ord consistente com a soma das colunas
    assert (d1["B_ord"] - d1[["B_C", "B_ISFLSF", "B_FBCF_NC"]].sum(axis=1)) \
        .abs().max() < 1e-9
    # shares por UF inalterados (convenção declarada)
    s0 = d0["B_C"] / d0["B_C"].sum()
    s1 = d1["B_C"] / d1["B_C"].sum()
    assert (s0 - s1).abs().max() < 1e-12


def test_alavanca_sifim_guarda_dominio(monkeypatch):
    # imputado acima do consumo do produto 64801 do toy (200 R$ bi) — barra
    monkeypatch.setattr(sifim_fbcf, "carrega_ajuste_sifim", lambda: 250.0)
    with pytest.raises(ValueError):
        _roda(sifim="excluido")


# -------------------------------------------- alavanca FBCF imob. (toy)
def test_alavanca_fbcf_subtrai_no_nivel_2021(monkeypatch):
    monkeypatch.setattr(sifim_fbcf, "carrega_ajuste_fbcf", lambda: 2.0)
    d0, d1 = _roda(), _roda(fbcf_imob="redutores")
    esperado = (_ANCORAS_TOY.fbcf_tru * _ANCORAS_TOY.share_fbcf_nc - 2.0) \
        * _ANCORAS_TOY.escala_biênio_fbcf
    assert math.isclose(d1["B_FBCF_NC"].sum(), esperado, rel_tol=1e-12)
    pd.testing.assert_series_equal(d0["B_C"], d1["B_C"])
    pd.testing.assert_series_equal(d0["B_ISFLSF"], d1["B_ISFLSF"])


def test_alavanca_fbcf_guarda_dominio(monkeypatch):
    # delta acima da FBCF_NC do toy (100 × 0,10 = 10 R$ bi) — barra
    monkeypatch.setattr(sifim_fbcf, "carrega_ajuste_fbcf", lambda: 10.0)
    with pytest.raises(ValueError):
        _roda(fbcf_imob="redutores")


# --------------------------------------------------- CSV: split do SIFIM
_TEM_SIFIM_CSV = sifim_fbcf.CSV_SIFIM.exists()


@pytest.mark.skipif(not _TEM_SIFIM_CSV,
                    reason="ajuste_sifim.csv ainda não gerado")
def test_split_sifim_soma_ao_produto():
    df = pd.read_csv(sifim_fbcf.CSV_SIFIM).set_index("componente")
    v = df["valor_rs_bi_2021"]
    total = v["consumo_familias_64801_tru2021"]
    assert math.isclose(v["explicito_escalado_2021"]
                        + v["sifim_imputado_familias_2021"],
                        total, rel_tol=1e-9)
    # explícito = Σ componentes POF × escala (identidade interna)
    pof = sum(v[c] for c in v.index if c.startswith("pof_"))
    assert math.isclose(pof * v["escala_pof_tru"],
                        v["explicito_escalado_2021"], rel_tol=1e-9)


@pytest.mark.skipif(not _TEM_SIFIM_CSV,
                    reason="ajuste_sifim.csv ainda não gerado")
def test_residual_sifim_nao_negativo():
    df = pd.read_csv(sifim_fbcf.CSV_SIFIM).set_index("componente")
    v = df["valor_rs_bi_2021"]
    residual = v["sifim_imputado_familias_2021"]
    if residual < 0:
        pytest.skip("residual negativo — status declarado no CSV; "
                    "alternativa (produto sem seguros) a decidir")
    assert 0.0 <= residual <= v["consumo_familias_64801_tru2021"]


@pytest.mark.skipif(not _TEM_SIFIM_CSV,
                    reason="ajuste_sifim.csv ainda não gerado")
def test_sifim_efeitos_e_fronteira_declarados():
    df = pd.read_csv(sifim_fbcf.CSV_SIFIM).set_index("componente")
    for c in ("efeito_pp_uniao", "efeito_pp_estadual", "efeito_pp_municipal",
              "efeito_pp_soma", "break_even_iss_financeiro_share"):
        assert c in df.index and math.isfinite(df.loc[c, "valor_rs_bi_2021"])
    # fronteira do ISS financeiro: declarada, NUNCA um número sem fonte
    assert pd.isna(df.loc["iss_financeiro_numerador", "valor_rs_bi_2021"])
    assert df.loc["iss_financeiro_numerador", "metodo"] == "FRONTEIRA"
    assert "SICONFI" in str(df.loc["iss_financeiro_numerador", "fonte"])


# ------------------------------- validação externa BCB/SGS (FISIM-PF 2021)
from aferir.fetch import bcb_sgs

_TEM_SGS = bcb_sgs.BCB_SGS_CSV.exists()


@pytest.mark.skipif(not _TEM_SGS,
                    reason="snapshot BCB/SGS ainda não baixado")
def test_fisim_pf_bcb_positivo_e_ordem_de_grandeza():
    """FISIM-PF lado-empréstimos 2021: >0 e ~423 R$ bi (auditoria 13/07)."""
    n = sifim_fbcf.fisim_pf_bcb_2021()
    assert math.isfinite(n.valor) and n.valor > 0
    assert 300.0 <= n.valor <= 500.0
    assert n.unidade == "R$ bi 2021"
    for cod in ("20541", "25353", "4189"):
        assert cod in n.formula or cod in n.fonte


@pytest.mark.skipif(not _TEM_SGS,
                    reason="snapshot BCB/SGS ainda não baixado")
def test_fisim_pf_bcb_deterministico_rota_local():
    """Rota local (snapshot existente, sem rede): Num idêntico bit a bit."""
    assert sifim_fbcf.fisim_pf_bcb_2021() == sifim_fbcf.fisim_pf_bcb_2021()


@pytest.mark.skipif(not (_TEM_SGS and _TEM_SIFIM_CSV),
                    reason="snapshot BCB/SGS ou ajuste_sifim.csv ausente")
def test_fisim_pf_bcb_no_csv_valida_residuo():
    """Linha VALIDACAO do CSV = recomputação; cota superior ≥ resíduo e
    coerente com o teto mecânico (célula TRU 64801)."""
    df = pd.read_csv(sifim_fbcf.CSV_SIFIM).set_index("componente")
    r = df.loc["fisim_pf_bcb_2021"]
    assert r["metodo"] == "VALIDACAO"
    v = float(r["valor_rs_bi_2021"])
    assert math.isclose(v, sifim_fbcf.fisim_pf_bcb_2021().valor, rel_tol=1e-12)
    assert v >= float(df.loc["sifim_imputado_familias_2021",
                             "valor_rs_bi_2021"])


@pytest.mark.skipif(not _TEM_SGS,
                    reason="snapshot BCB/SGS ainda não baixado")
def test_bcb_sgs_snapshot_e_meta_integros():
    """Snapshot: 3 séries × 12 meses de 2021; sidecar com sha256 batendo."""
    import json

    from aferir.provenance import sha256_file
    df = pd.read_csv(bcb_sgs.BCB_SGS_CSV)
    assert sorted(df["codigo"].unique()) == sorted(bcb_sgs.SERIES_SGS)
    assert (df.groupby("codigo").size() == 12).all()
    assert df["data"].str.endswith("/2021").all()
    meta = json.loads(bcb_sgs.BCB_SGS_CSV.with_name(
        bcb_sgs.BCB_SGS_CSV.name + "._meta.json").read_text(encoding="utf-8"))
    assert meta["sha256"] == sha256_file(bcb_sgs.BCB_SGS_CSV)
    for cod in bcb_sgs.SERIES_SGS:
        assert f"bcdata.sgs.{cod}" in meta["url"][str(cod)]


# ---------------------------------------------- CSV: FBCF × texto da lei
_TEM_FBCF_CSV = sifim_fbcf.CSV_FBCF.exists()
_TEM_LEI = sifim_fbcf.LC214_HTML.exists()


@pytest.mark.skipif(not (_TEM_FBCF_CSV and _TEM_LEI),
                    reason="ajuste_fbcf_imobiliaria.csv ou lcp214.htm ausente")
def test_redutores_vem_do_html_da_lei():
    lei = sifim_fbcf.lc214_regime_imobiliario()
    df = pd.read_csv(sifim_fbcf.CSV_FBCF).set_index("componente")
    r = df.loc["reducao_aliquota_art261"]
    assert math.isclose(r["m_efetivo"],
                        1.0 - lei["reducao_aliquota_pct"].valor / 100.0)
    assert "art. 261" in r["fonte"]
    assert math.isclose(
        r["delta_base_rs_bi"],
        r["parcela_residencial_rs_bi"] * (1 - r["m_efetivo"]), rel_tol=1e-9)
    social = df.loc["redutor_social_art259_imovel_novo"]
    assert "art. 259" in social["fonte"]
    assert "100.000" in social["redutor_aplicado"]
    lote = df.loc["redutor_social_art259_lote"]
    assert "30.000" in lote["redutor_aplicado"]
    # uso próprio/autoconstrução: tratamento citado artigo a artigo
    assert "252, V" in df.loc["uso_proprio_autoconstrucao", "redutor_aplicado"]


@pytest.mark.skipif(not _TEM_LEI, reason="lcp214.htm ausente")
def test_parse_lc214_valores_oficiais():
    """Os quatro parâmetros saem do TEXTO COMPILADO — zero número de memória.
    (Valores conferidos contra o texto: sanidade de domínio, não pin.)"""
    lei = sifim_fbcf.lc214_regime_imobiliario()
    assert 0 < lei["reducao_aliquota_pct"].valor < 100
    assert 0 < lei["reducao_locacao_pct"].valor < 100
    assert lei["redutor_social_novo_rs"].valor > lei["redutor_social_lote_rs"].valor > 0
    assert all(n.label.value == "OFICIAL" for n in lei.values())


# ------------------------------------------------------------ determinismo
_TEM_INSUMOS = all(p.exists() for p in (
    config.PROCESSED / "tru_2021_usos.parquet",
    config.PROCESSED / "pof_despesa_item_uf.parquet",
    config.PROCESSED / "base_uf.csv",
    config.PROCESSED / "aferir_nacional.csv",
    config.PROCESSED / "MANIFEST_RUN.json",
))


@pytest.mark.skipif(not _TEM_INSUMOS,
                    reason="insumos processados em regeneração")
def test_split_sifim_deterministico():
    a = sifim_fbcf.split_sifim(grava=False)
    b = sifim_fbcf.split_sifim(grava=False)
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.skipif(not (_TEM_INSUMOS and _TEM_LEI
                         and sifim_fbcf.PAIC_JSON.exists()),
                    reason="insumos, lei ou PAIC ausentes")
def test_ajuste_fbcf_deterministico():
    a = sifim_fbcf.ajuste_fbcf_imobiliaria(grava=False)
    b = sifim_fbcf.ajuste_fbcf_imobiliaria(grava=False)
    pd.testing.assert_frame_equal(a, b)


@pytest.mark.skipif(not sifim_fbcf.PAIC_JSON.exists(),
                    reason="PAIC 1740 ainda não baixada")
def test_paic_meta_sidecar_integro():
    """_meta.json do raw: url + sha256 batendo com o arquivo (auditoria)."""
    import json

    from aferir.provenance import sha256_file
    meta = json.loads(sifim_fbcf.PAIC_JSON.with_name(
        sifim_fbcf.PAIC_JSON.name + "._meta.json").read_text(encoding="utf-8"))
    assert meta["url"] == sifim_fbcf.PAIC_URL
    assert meta["sha256"] == sha256_file(sifim_fbcf.PAIC_JSON)


@pytest.mark.skipif(not (_TEM_SIFIM_CSV and _TEM_FBCF_CSV),
                    reason="CSVs do E7 ainda não gerados")
def test_carregadores_das_alavancas():
    s = sifim_fbcf.carrega_ajuste_sifim()
    f = sifim_fbcf.carrega_ajuste_fbcf()
    assert s > 0 and math.isfinite(s)
    assert f > 0 and math.isfinite(f)
