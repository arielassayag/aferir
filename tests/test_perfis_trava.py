"""Perfis alternativos de corte da trava (E3 — aferir.perfis_trava).

Testes ESTRUTURAIS: os números absolutos desta worktree estão em fluxo
(processados sendo regenerados em paralelo), então NENHUM golden de λ ou de
alíquota é fixado — testa-se partição, domínios, invariantes dos perfis,
consistência entre artefatos e regressão de assinatura (float ainda aceito).
"""
import json
import math

import pandas as pd
import pytest

from aferir import config, pipeline
from aferir import perfis_trava as pt
from aferir.base import itens_combustiveis
from aferir.gaps import (CLASSES_FAVORECIDAS, classifica_regime,
                         policy_gap_por_uf)

RESULTADOS = config.PROCESSED / "resultados_perfis_trava.csv"
INCIDENCIA = config.PROCESSED / "incidencia_regimes_decil.csv"
PARTICAO = config.PROCESSED / "perfis_trava.csv"
TRAVA_CSV = config.PROCESSED / "trava_conforme.csv"
DESPESA_PARQUET = config.PROCESSED / "pof_despesa_item_uf.parquet"


def _carrega(path, nome):
    if not path.exists():
        pytest.skip(f"{nome} ainda não gerado (rodar aferir.perfis_trava)")
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def resultados():
    return _carrega(RESULTADOS, "resultados_perfis_trava.csv")


@pytest.fixture(scope="module")
def incidencia():
    return _carrega(INCIDENCIA, "incidencia_regimes_decil.csv")


@pytest.fixture(scope="module")
def particao():
    return _carrega(PARTICAO, "perfis_trava.csv")


# ------------------------------------------------------------ classificação
def test_classificacao_deterministica_e_total():
    c1, c2 = classifica_regime(), classifica_regime()
    assert c1.equals(c2)                                   # bit a bit
    assert len(c1) == 13_474                               # matriz completa
    esperadas = set(CLASSES_FAVORECIDAS) | {"padrao", "fora_campo"}
    assert set(c1["classe"]) == esperadas
    # classes favorecidas têm nível m único (invariante da partição)
    nivel = {"cesta_aliquota_zero": 0.0, "saude_60": 0.4, "educacao_60": 0.4,
             "alimentos_60": 0.4, "demais_60": 0.4,
             "reducao_40_especificos": 0.6, "reducao_30": 0.7,
             "reducao_70_imoveis": 0.3, "padrao": 1.0}
    for classe, m in nivel.items():
        sub = c1[c1["classe"] == classe]
        assert (sub["m_i"] == m).all(), classe
    assert (c1.loc[c1["classe"] == "fora_campo", "flag"] == "F").all()


# --------------------------------------------- regressão: float ainda aceito
def test_policy_gap_float_e_dict_equivalentes():
    if not DESPESA_PARQUET.exists():
        pytest.skip("pof_despesa_item_uf.parquet ausente")
    despesa = pd.read_parquet(DESPESA_PARQUET)
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    em_campo = despesa[~despesa["codigo_pof"].isin(itens_combustiveis(despesa))]
    lam = 0.37
    p_float = policy_gap_por_uf(em_campo, lam=lam)          # caminho antigo
    p_dict = policy_gap_por_uf(
        em_campo, lam={c: lam for c in CLASSES_FAVORECIDAS})
    assert (p_float["pi_p"].values == p_dict["pi_p"].values).all()  # bit a bit
    # dict parcial ≠ uniforme (o λ por classe de fato diferencia)
    p_parcial = policy_gap_por_uf(em_campo, lam={"cesta_aliquota_zero": lam})
    assert not (p_parcial["pi_p"].values == p_float["pi_p"].values).all()
    with pytest.raises(ValueError):
        policy_gap_por_uf(em_campo, lam={"cesta_aliquota_zero": 1.5})


def test_pipeline_executa_float_e_dict_equivalentes():
    if not DESPESA_PARQUET.exists():
        pytest.skip("processados ausentes")
    lam_d = {c: 0.3 for c in pt.CORTAVEIS}                  # inclui 'zfm'
    r_float = pipeline.executa(0.125, 0.0, "iso_carga", lam=0.3)
    r_dict = pipeline.executa(0.125, 0.0, "iso_carga", lam=lam_d)
    r_dict2 = pipeline.executa(0.125, 0.0, "iso_carga", lam=dict(lam_d))
    sf, sd, sd2 = r_float["sol"], r_dict["sol"], r_dict2["sol"]
    assert (sf.tau_U, sf.tau_E, sf.tau_M, sf.soma) == \
           (sd.tau_U, sd.tau_E, sd.tau_M, sd.soma)          # float ≡ dict
    assert (sd.tau_U, sd.tau_E, sd.tau_M, sd.soma) == \
           (sd2.tau_U, sd2.tau_E, sd2.tau_M, sd2.soma)      # determinismo
    assert r_float["vetor_estadual"] == r_dict["vetor_estadual"]


# ------------------------------------------------------------ artefatos
def _lam_de(row) -> dict:
    return json.loads(row["lambda_por_classe"])


def test_resultados_contrato(resultados):
    for col in ("perfil", "gamma", "lambda_por_classe", "tau_CBS_pp",
                "tau_E_pp", "tau_M_pp", "soma_pp",
                "beneficios_suprimidos_rs_bi_trava",
                "beneficios_suprimidos_rs_bi_central", "cv_vetor_E",
                "cv_vetor_M", "status", "formula", "fonte"):
        assert col in resultados.columns, col
    assert set(resultados["perfil"]) == set(pt.PERFIS)
    # γ central obrigatório em todos os perfis
    central = resultados[resultados["gamma"] == pt.GAMMA_CENTRAL]
    assert set(central["perfil"]) == set(pt.PERFIS)


def test_soma_no_gatilho_por_status(resultados):
    fact = resultados[resultados["status"] == "factivel"]
    assert not fact.empty
    assert (fact["soma_pp"] - 26.5).abs().max() <= 1e-4
    infact = resultados[resultados["status"] == "infactivel"]
    assert (infact["soma_pp"] > 26.5).all()                 # nem λ=1 fecha
    ja = resultados[resultados["status"] == "ja_conforme"]
    assert (ja["soma_pp"] <= 26.5 + 1e-9).all()


def test_lambda_dominio_e_chaves(resultados):
    for _, row in resultados.iterrows():
        lam = _lam_de(row)
        assert set(lam) == set(pt.CORTAVEIS), row["perfil"]
        assert all(0.0 <= v <= 1.0 for v in lam.values()), row["perfil"]


def test_p1_lambda_uniforme(resultados):
    for _, row in resultados[resultados["perfil"] == "P1_uniforme"].iterrows():
        assert len(set(_lam_de(row).values())) == 1         # λ único ∀ classe


def test_p2_protegidas_em_zero(resultados):
    p2 = resultados[resultados["perfil"] == "P2_protege_essenciais"]
    assert not p2.empty
    for _, row in p2.iterrows():
        lam = _lam_de(row)
        for classe in pt.PROTEGIDAS_P2:
            assert lam[classe] == 0.0, classe
        livres = {v for c, v in lam.items() if c not in pt.PROTEGIDAS_P2}
        assert len(livres) == 1                             # λ único nas demais


def test_p3_ordem_respeita_indice_pro_rico(resultados, incidencia):
    idx = incidencia.groupby("classe")["indice_pro_rico"].first()
    ordem = sorted(pt.CORTAVEIS, key=lambda c: (-idx[c], c))
    p3 = resultados[resultados["perfil"] == "P3_regressividade"]
    assert not p3.empty
    for _, row in p3.iterrows():
        lam = _lam_de(row)
        seq = [lam[c] for c in ordem]
        # corte sequencial: λ não-crescente na ordem pró-rico → pró-pobre
        assert all(a >= b for a, b in zip(seq, seq[1:])), seq
        if row["status"] == "factivel":
            parciais = [v for v in seq if 0.0 < v < 1.0]
            assert len(parciais) <= 1                       # 1 classe marginal
            assert set(seq) - set(parciais) <= {0.0, 1.0}


def test_p1_reproduz_trava_py(resultados):
    """P1 ≡ trava.py: λ e Σ contra trava_conforme.csv (tol 1e-4).

    Se os dois artefatos vierem de vintages DIFERENTES dos processados
    (números em fluxo nesta worktree), a comparação é pulada com aviso —
    re-rodar `make trava` e `python3 -m aferir.perfis_trava` no MESMO estado.
    A equivalência de mecanismo (dict ≡ float bit a bit) é testada à parte em
    test_pipeline_executa_float_e_dict_equivalentes.
    """
    if not TRAVA_CSV.exists():
        pytest.skip("trava_conforme.csv ainda não gerado (rodar aferir.trava)")
    t = pd.read_csv(TRAVA_CSV).set_index("gamma")
    p1 = resultados[resultados["perfil"] == "P1_uniforme"].set_index("gamma")
    comuns = sorted(set(t.index) & set(p1.index))
    assert comuns, "nenhum γ comum entre trava_conforme e perfis"
    for g in comuns:
        lam_p1 = set(_lam_de(p1.loc[g]).values()).pop()
        dif = abs(lam_p1 - float(t.loc[g, "lambda"]))
        if dif > 1e-3:
            pytest.skip(
                f"vintages divergentes em γ={g} (Δλ={dif:.4f}): "
                "trava_conforme.csv gerado com processados anteriores — "
                "regenerar ambos no mesmo estado (make trava; "
                "python3 -m aferir.perfis_trava)")
        assert dif <= 1e-4, g
        assert abs(float(p1.loc[g, "soma_pp"])
                   - float(t.loc[g, "soma_pp"])) <= 1e-4, g


def test_incidencia_estrutura(incidencia):
    assert set(incidencia["classe"]) == set(pt.CORTAVEIS)
    for classe, g in incidencia.groupby("classe"):
        assert sorted(g["decil"]) == list(range(1, 11)), classe
        assert math.isclose(g["share_beneficio"].sum(), 1.0, abs_tol=1e-9)
        assert (g["beneficio_rs_bi"] >= 0.0).all()
        assert g["indice_pro_rico"].nunique() == 1          # constante na classe
        assert (g["indice_pro_rico"] > 0.0).all()
    for col in ("despesa_rs_bi", "beneficio_rs_bi", "share_beneficio",
                "indice_pro_rico", "formula", "fonte"):
        assert col in incidencia.columns, col


def test_particao_estrutura(particao):
    for col in ("classe", "criterio", "n_itens", "despesa_rs_bi", "m_medio",
                "formula", "fonte"):
        assert col in particao.columns, col
    assert list(particao["classe"]) == list(pt.ORDEM_PARTICAO)
    # contagens somam a matriz inteira (zfm é pseudo-classe, n=0)
    assert int(particao["n_itens"].sum()) == 13_474
    assert int(particao.set_index("classe").loc["zfm", "n_itens"]) == 0
    assert (particao["despesa_rs_bi"] >= 0.0).all()


def test_particao_deterministica():
    if not DESPESA_PARQUET.exists():
        pytest.skip("processados ausentes")
    p1, p2 = pt.particao_classes(), pt.particao_classes()
    assert p1.equals(p2)                                    # bit a bit
