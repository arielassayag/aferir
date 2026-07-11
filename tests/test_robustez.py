"""Testes estruturais de aferir.robustez (itens E4/E5 do plano de revisão).

Pré-condição: aferir_nacional.csv e base_uf.csv em data/processed/ (insumos
lidos pelo módulo). NÃO há golden absoluto de alíquota aqui — o painel
nacional está em re-baseline por outros itens da revisão; testa-se
estrutura, sanidade, invariantes de construção (renormalização exata,
ordenação γ×informalidade, domínio) e determinismo em bytes.
"""
from __future__ import annotations

import pandas as pd
import pytest

from aferir import robustez
from aferir.config import PROCESSED, UFS
from aferir.provenance import MANIFEST, Label

_INSUMOS = (PROCESSED / "aferir_nacional.csv", PROCESSED / "base_uf.csv")

_S_SANIDADE = (0.55, 0.70)      # corredor histórico plausível de s no Brasil
_INF_SANIDADE = (5.0, 80.0)     # taxa de informalidade plausível (%)


def _limpa_caches() -> None:
    for fn in (robustez._trimestres_1846, robustez.serie_s_anual,
               robustez.tau_central_corrente_pp, robustez.informalidade_uf,
               robustez._b_ord, robustez._fonte_1846, robustez._fonte_8529):
        fn.cache_clear()


@pytest.fixture(scope="module")
def artefatos() -> dict[str, pd.DataFrame]:
    for csv in _INSUMOS:
        if not csv.exists():
            pytest.skip(f"insumo ausente: {csv.name} (rodar o pipeline antes)")
    return {
        "base_pib": robustez.grava_sens_base_pib(),
        "informalidade": robustez.grava_informalidade_uf(),
        "gamma": robustez.grava_sens_gamma_heterogeneo(),
    }


def _valor(df: pd.DataFrame, chave: str) -> float:
    sel = df.loc[df["chave"] == chave, "valor"]
    assert len(sel) == 1, f"chave '{chave}' deve ser única (obtidas {len(sel)})"
    return float(sel.iloc[0])


# ==================================================================== E4
def test_consome_44_trimestres(artefatos):
    q = robustez._trimestres_1846()
    assert len(q) == 44
    assert not q[["pib_rs_mi", "cfam_rs_mi"]].isna().any().any()
    assert (q.groupby("ano").size() == 4).all()
    assert sorted(q["ano"].unique()) == list(range(2015, 2026))


def test_s_dentro_do_corredor_de_sanidade(artefatos):
    ann = robustez.serie_s_anual()
    assert len(ann) == 11
    lo, hi = _S_SANIDADE
    assert ((ann["s"] > lo) & (ann["s"] < hi)).all(), ann["s"].to_dict()
    assert lo < robustez.s_corrente().valor < hi


def test_extremos_ordenados_com_corrente(artefatos):
    """mín < corrente < máx (dados de vintage congelada — igualdade exigiria
    declaração explícita e revisão deste teste)."""
    ext = robustez.extremos_decada()
    s_cur = robustez.s_corrente().valor
    assert ext["min"].valor < s_cur < ext["max"].valor
    assert 2015 <= ext["ano_min"] <= 2025 and 2015 <= ext["ano_max"] <= 2025
    assert ext["ano_min"] != ext["ano_max"]


def test_estrutura_sens_base_pib(artefatos):
    df = pd.read_csv(robustez.CSV_SENS_BASE_PIB)
    assert list(df.columns) == ["chave", "ano", "cfam_rs_mi", "pib_rs_mi",
                                "s", "valor", "formula", "fonte"]
    assert (df["chave"] == "s_anual").sum() == 11
    esperadas = {"s_anual", "s_corrente", "s_min_decada", "s_max_decada",
                 "fator_reescala_min", "fator_reescala_max",
                 "delta_tau_aprox_min_pp", "delta_tau_aprox_max_pp",
                 "tau_central_corrente_pp", "identidade_estacionariedade"}
    assert set(df["chave"]) == esperadas
    assert df["formula"].notna().all() and df["fonte"].notna().all()
    # vintage integral da API presente na fonte da série
    fonte_serie = df.loc[df["chave"] == "s_anual", "fonte"].iloc[0]
    for token in ("apisidra.ibge.gov.br", "sha256", "coletado em"):
        assert token in fonte_serie, token


def test_fatores_e_elasticidade_consistentes(artefatos):
    df = pd.read_csv(robustez.CSV_SENS_BASE_PIB)
    s_cur = _valor(df, "s_corrente")
    s_min, s_max = _valor(df, "s_min_decada"), _valor(df, "s_max_decada")
    tau = _valor(df, "tau_central_corrente_pp")
    assert _valor(df, "fator_reescala_min") == pytest.approx(
        s_min / s_cur, abs=1e-12)
    assert _valor(df, "fator_reescala_max") == pytest.approx(
        s_max / s_cur, abs=1e-12)
    assert _valor(df, "fator_reescala_min") < 1.0 < _valor(
        df, "fator_reescala_max")
    assert _valor(df, "delta_tau_aprox_min_pp") == pytest.approx(
        -tau * (s_min - s_cur) / s_cur, abs=1e-12)
    assert _valor(df, "delta_tau_aprox_max_pp") == pytest.approx(
        -tau * (s_max - s_cur) / s_cur, abs=1e-12)
    # base menor ⇒ alíquota sobe (sinal da elasticidade)
    assert _valor(df, "delta_tau_aprox_min_pp") > 0
    assert _valor(df, "delta_tau_aprox_max_pp") < 0


def test_identidade_no_manifest(artefatos):
    num = MANIFEST.nums["e4_identidade_estacionariedade"]
    assert num.label is Label.CONVENCAO
    assert num.valor == 1.0
    assert "(base/PIB)_2024-25" in num.formula


# ==================================================================== E5
def test_estrutura_informalidade_uf(artefatos):
    df = pd.read_csv(robustez.CSV_INFORMALIDADE_UF)
    assert list(df.columns) == ["uf", "sigla", "taxa_media_pct",
                                "n_trimestres", "formula", "fonte"]
    assert len(df) == 27
    assert sorted(df["sigla"]) == sorted(UFS)
    assert (df["n_trimestres"] == 8).all()
    lo, hi = _INF_SANIDADE
    assert ((df["taxa_media_pct"] > lo) & (df["taxa_media_pct"] < hi)).all()
    # mapeamento D1C→sigla (amostras nas 3 pontas do código IBGE)
    m = df.set_index("sigla")["uf"]
    assert (m["RO"], m["SP"], m["DF"]) == (11, 35, 53)


def test_renormalizacao_exata(artefatos):
    gam = pd.read_csv(robustez.CSV_SENS_GAMMA)
    assert len(gam) == 54 and set(gam["beta"]) == {0.5, 1.0}
    b = pd.read_csv(PROCESSED / "base_uf.csv").set_index("uf")["B_ord"]
    for beta, grp in gam.groupby("beta"):
        g = grp.set_index("uf")["gamma_uf"]
        media = float((g * b).sum() / b.sum())
        assert abs(media - robustez.GAMMA_BARRA) < 1e-12, (beta, media)


def test_gamma_no_dominio(artefatos):
    gam = pd.read_csv(robustez.CSV_SENS_GAMMA)
    assert ((gam["gamma_uf"] > 0.0) & (gam["gamma_uf"] < 0.5)).all()


def test_gamma_ordenado_com_informalidade(artefatos):
    """β>0 ⇒ γ_uf é função afim crescente de inf_uf: correlação de postos
    perfeita por construção (ranks idênticos)."""
    gam = pd.read_csv(robustez.CSV_SENS_GAMMA)
    inf = (pd.read_csv(robustez.CSV_INFORMALIDADE_UF)
           .set_index("sigla")["taxa_media_pct"])
    for beta, grp in gam.groupby("beta"):
        g = grp.set_index("uf")["gamma_uf"]
        assert (g.rank() == inf.reindex(g.index).rank()).all(), beta


def test_determinismo_bytes(artefatos):
    antes = {p: p.read_bytes() for p in (
        robustez.CSV_SENS_BASE_PIB, robustez.CSV_INFORMALIDADE_UF,
        robustez.CSV_SENS_GAMMA)}
    _limpa_caches()
    robustez.grava_sens_base_pib()
    robustez.grava_informalidade_uf()
    robustez.grava_sens_gamma_heterogeneo()
    for p, conteudo in antes.items():
        assert p.read_bytes() == conteudo, f"não determinístico: {p.name}"


def test_sem_caminho_absoluto_nem_nome_proprio(artefatos):
    for p in (robustez.CSV_SENS_BASE_PIB, robustez.CSV_INFORMALIDADE_UF,
              robustez.CSV_SENS_GAMMA):
        txt = p.read_text(encoding="utf-8")
        assert "/Users" not in txt and "\\Users" not in txt, p.name
