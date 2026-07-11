"""Testes das figuras canônicas (F1-F4) — existência, dimensões, determinismo.

Pré-condição: pipeline executado (processados em data/processed/, tabelas em
data/outputs/) e `python3 -m aferir.figures` rodado ao menos uma vez (artefatos
canônicos em data/outputs/figures/).

Critérios (DESIGN §4 e edital PTN):
- PNG 300 dpi, 1800×1500 px (6,0×5,0 pol), sem timestamp nos metadados;
- determinismo byte-idêntico: duas execuções produzem os MESMOS bytes, e o
  artefato canônico em data/outputs/figures/ é reproduzido exatamente
  (staleness vira falha de teste — mesma disciplina dos invariantes);
- os números anotados na F3 (top-k, Gini) são consistentes com o processado
  auditado iss_concentracao.csv.
"""
from __future__ import annotations

import struct

import numpy as np
import pandas as pd
import pytest

from aferir import figures
from aferir.config import COD_IBGE_BRASILIA, FIGURES, PROCESSED

CASOS = [
    (figures.fig1_vetores_uf, "fig1_vetores_uf.png"),
    (figures.fig2_origem_destino, "fig2_origem_destino.png"),
    (figures.fig3_lorenz_iss, "fig3_lorenz_iss.png"),
    (figures.fig4_comparadores, "fig4_comparadores.png"),
    (figures.fig5_cenarios, "fig5_cenarios.png"),
    (figures.fig6_transicao, "fig6_transicao.png"),
    (figures.fig7_mapa_uf, "fig7_mapa_uf.png"),
]
# 400 dpi; F1 (7,2×7,4), F5 (7,2×6,4), F6 (7,2×8,2) e F7 (7,2×5,0 pol)
PX_ESPERADO = {
    "fig1_vetores_uf.png": (2880, 2960),
    "fig2_origem_destino.png": (2880, 2160),
    "fig3_lorenz_iss.png": (2880, 2160),
    "fig4_comparadores.png": (2880, 2160),
    "fig5_cenarios.png": (2880, 3000),
    "fig6_transicao.png": (2880, 3279),
    "fig7_mapa_uf.png": (2880, 2000),
}


def _png_dimensoes(dados: bytes) -> tuple[int, int]:
    assert dados[:8] == b"\x89PNG\r\n\x1a\n", "assinatura PNG inválida"
    return struct.unpack(">II", dados[16:24])


# ---------------------------------------------------------------- existência
@pytest.mark.parametrize("_func,nome", CASOS)
def test_existencia_e_dimensoes(_func, nome):
    path = FIGURES / nome
    assert path.exists(), f"artefato canônico ausente: {path}"
    largura, altura = _png_dimensoes(path.read_bytes())
    assert (largura, altura) == PX_ESPERADO[nome]


@pytest.mark.parametrize("_func,nome", CASOS)
def test_metadados_sem_timestamp(_func, nome):
    """Anonimato + determinismo: nenhum chunk de data/hora no PNG."""
    dados = (FIGURES / nome).read_bytes()
    assert b"tIME" not in dados
    assert b"Creation Time" not in dados


# ---------------------------------------------------------------- determinismo
@pytest.mark.parametrize("func,nome", CASOS)
def test_determinismo_byte_identico(func, nome, tmp_path):
    """Duas execuções → bytes idênticos; e idênticos ao artefato canônico
    (se divergir, o canônico está DESATUALIZADO: rode make figures)."""
    d1, d2 = tmp_path / "run1", tmp_path / "run2"
    b1 = func(out_dir=d1).read_bytes()
    b2 = func(out_dir=d2).read_bytes()
    assert b1 == b2, f"{nome}: execuções consecutivas divergem"
    assert b1 == (FIGURES / nome).read_bytes(), (
        f"{nome}: artefato canônico desatualizado (make figures)")


# ------------------------------------------- consistência das anotações (F3)
@pytest.fixture(scope="module")
def iss_2024() -> np.ndarray:
    p = pd.read_parquet(PROCESSED / "iss_municipio_2024.parquet")
    p = p[p["cod_ibge"] != COD_IBGE_BRASILIA]           # 5.569, ex-DF
    assert len(p) == 5_569
    return p["iss_liquida"].fillna(0.0).to_numpy()


def test_lorenz_propriedades(iss_2024):
    x, y = figures.lorenz(iss_2024)
    assert x[0] == 0.0 and y[0] == 0.0
    assert x[-1] == pytest.approx(1.0) and y[-1] == pytest.approx(1.0)
    assert (np.diff(y) >= -1e-12).all()                 # monotônica
    assert (y[1:-1] <= x[1:-1] + 1e-12).all()           # abaixo da diagonal


def test_anotacoes_f3_vs_processado_auditado(iss_2024):
    """Top-k e Gini exibidos na F3 batem com iss_concentracao.csv (2024).
    Os shares top-k são idênticos (omissos entram com zero — não alteram as
    somas); o Gini difere apenas pela cauda de zeros (tolerância 0,002)."""
    conc = pd.read_csv(PROCESSED / "iss_concentracao.csv")
    conc = conc[conc["ano"] == 2024]
    tops = conc[conc["serie"] == "share_top"].set_index("x")["y"]

    v = np.sort(iss_2024)
    for k in (1, 10, 100):
        assert v[-k:].sum() / v.sum() == pytest.approx(tops[float(k)], abs=1e-12)

    gini_declarantes = float(conc[conc["serie"] == "gini"]["y"].iloc[0])
    assert figures.gini(iss_2024) == pytest.approx(gini_declarantes, abs=2e-3)


def test_helpers_dominio():
    with pytest.raises(ValueError):
        figures.lorenz(np.array([]))
    with pytest.raises(ValueError):
        figures.lorenz(np.array([1.0, -0.5]))
    assert figures.gini(np.ones(100)) == pytest.approx(0.0, abs=1e-12)
