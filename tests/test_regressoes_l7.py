"""L7 — invariantes da revisão: o que já foi conferido não pode regredir.

Duas camadas:
  1. proposições JURÍDICAS/qualitativas (composição do piso do cashback com
     telecomunicações; §11 como dever de propor lei complementar; IPI
     residual da ZFM deduzido do alvo da CBS; calendário anual do art. 349)
     — verificadas contra código e texto;
  2. proposições NUMÉRICAS re-baselinadas em metadata/qa_regressoes_parecer_l7.csv
     (valores esperados APÓS a revisão, com o baseline 20d6e32 arquivado e a
     justificativa da mudança linha a linha) — verificadas contra os
     processados correntes.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
PROCESSED = RAIZ / "data" / "processed"
ARTIGO = RAIZ / "docs" / "artigo"
QA_CSV = RAIZ / "metadata" / "qa_regressoes_parecer_l7.csv"


def _texto_artigo() -> str:
    return "\n".join(p.read_text(encoding="utf-8")
                     for p in sorted(ARTIGO.glob("*.md")))


# ---------------------------------------------------------------- jurídicas
def test_cashback_piso_inclui_telecom():
    """Art. 118: piso do cashback inclui telecomunicações (regex do pipeline)."""
    from aferir.pipeline import PADRAO_PISO
    for termo in ("TELEFONE", "CELULAR", "INTERNET", "ENERGIA ELETRICA",
                  "AGUA E ESGOTO", "GAS ENCANADO"):
        assert termo in PADRAO_PISO


def test_paragrafo_11_dever_de_propor():
    """§11 do art. 475 = dever de ENVIAR/PROPOR PLP, não corte por ato próprio."""
    t = _texto_artigo()
    assert re.search(r"art\.\s*475[^.]*§\s*11|§\s*11[^.]*art\.\s*475"
                     r"|§11|§§10-11|§§\s*10\s*e\s*11", t), "menção ao §11 sumiu"
    assert re.search(r"projeto de lei complementar|propor lei complementar"
                     r"|encaminh\w+ (o )?projeto", t, re.IGNORECASE), \
        "o texto deve manter o §11 como dever de propor PLP"


def test_ipi_residual_zfm_deduzido():
    """Nuance da ZFM: IPI residual permanece e é deduzido do alvo da CBS."""
    ipi = pd.read_csv(RAIZ / "data" / "inputs" / "is_ipi_residual.csv")
    v = float(ipi.loc[ipi["item"] == "ipi_residual_zfm_liquido", "valor"].iloc[0])
    assert v > 0
    import inspect

    from aferir import revenue
    assert "ipi_res" in inspect.getsource(revenue.alvo_uniao)


def test_calendario_art_349_presente():
    t = _texto_artigo()
    assert "art. 349" in t or "art. 349" in t.replace("arts.", "art.")


# ---------------------------------------------------------------- numéricas
@pytest.mark.skipif(not QA_CSV.exists(),
                    reason="qa_regressoes_parecer_l7.csv ainda não gerado")
def test_regressoes_numericas_l7():
    qa = pd.read_csv(QA_CSV, sep=";")
    obrigatorias = {"n_uf_acima_ref_E", "n_piso_vinc_E", "n_piso_vinc_M",
                    "piso_E_trava_pp", "piso_M_trava_pp", "suf_min_E",
                    "trava_lambda_central"}
    assert obrigatorias <= set(qa["proposicao"]), \
        f"faltam proposições: {obrigatorias - set(qa['proposicao'])}"

    met = pd.read_csv(PROCESSED / "metricas.csv").set_index("chave")["valor"]
    piso = pd.read_csv(PROCESSED / "metricas_piso.csv").set_index("chave")["valor"]
    dist = pd.read_csv(PROCESSED / "metricas_dist.csv").set_index("chave")["valor"]
    trava = pd.read_csv(PROCESSED / "trava_conforme.csv")
    lam = float(trava.loc[trava["cenario_gamma"] == "central", "lambda"].iloc[0])

    fontes = {"metricas": met, "metricas_piso": piso, "metricas_dist": dist}
    for r in qa.itertuples():
        esperado = float(r.valor_esperado)
        if r.proposicao == "trava_lambda_central":
            atual = lam
        else:
            atual = float(fontes[r.fonte_processada][r.proposicao])
        assert math.isclose(atual, esperado, rel_tol=1e-9, abs_tol=1e-9), (
            f"L7 regressão em {r.proposicao}: atual {atual!r} != esperado "
            f"{esperado!r} (baseline 20d6e32: {r.valor_baseline}; "
            f"justificativa registrada: {r.justificativa}). Mudou de novo? "
            "Atualize o CSV com run_id e justificativa — nunca silencie.")
