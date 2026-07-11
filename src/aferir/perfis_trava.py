"""Perfis alternativos de corte da trava do art. 475, §11 (LC 214) — E3.

O corte UNIFORME do trava.py (λ único para todos os favorecimentos) é uma
convenção de implementação do PLP do §11 — a lei obriga o projeto de lei,
não prescreve o desenho da redução. Benefícios têm incidências distintas por
produto e renda; este módulo resolve o MESMO gatilho (Σ_s τ_s = 26,5%) sob
três perfis de corte POR CLASSE de regime:

  P1_uniforme      — validação: todas as classes no MESMO λ; reproduz o
                     trava.py bit a bit (a bisseção usa a mesma malha e o
                     caminho dict com λ idêntico por classe é idêntico ao
                     caminho float — testado em test_perfis_trava.py);
  P2_protege_essenciais — λ=0 em cesta básica/alíquota zero, saúde-60 e
                     educação-60; λ único bisseccionado nas DEMAIS classes
                     (inclusive a pseudo-classe zfm); se nem λ=1 fechar em
                     26,5%, a infactibilidade é registrada (coluna status);
  P3_regressividade — classes ordenadas pelo índice pró-rico do BENEFÍCIO
                     (share do benefício w_i·(1−m_i) nos decis 8-10 ÷ share
                     nos decis 1-3; decis populacionais NACIONAIS de renda
                     per capita da POF); corta sequencialmente da classe mais
                     pró-rica à mais pró-pobre (λ=1 classe a classe; λ
                     parcial bisseccionado na classe marginal) até fechar.

Classes de regime: derivadas DA PRÓPRIA MATRIZ legal (gaps.classifica_regime;
partição por m_i × conteúdo de tratamento_ibs_v3), mais a pseudo-classe 'zfm'
(adendo de política do AM — pipeline.ZFM_AM, encolhido em pipeline._d_esfera
via lam.get('zfm')). O solver é PRÓPRIO (não altera trava.py): bisseção
determinística do grau t∈[0;1] do perfil, tol 1e-6, sobre pipeline.executa
(construção B: ψ=0, iso-carga), com cashback recomputado a cada λ.

Valoração dos benefícios suprimidos (duas convenções, ambas reportadas):
  às alíquotas TRAVA-CONFORMES:  custo = Σ_s τ_s(λ*)·[D_s(λ*)−D_s(0)]
  às alíquotas CENTRAIS (nota):  custo = Σ_s τ_s(0) ·[D_s(λ*)−D_s(0)]
No perfil uniforme, a primeira coincide com trava.custo_beneficios_bi
(identidade iso-receita testada em test_trava.py).

Incidência distributiva: despesa por item×decil nacional construída dos
microdados (aferir.inputs.pof.le_despesas) juntados ao decil de renda per
capita por UC — replicado deterministicamente de pof_boot_uc.parquet com a
MESMA regra de aferir.inputs.pof.decis_renda (ordenação por rpc com desempate
pela chave da UC; peso populacional pop_w). Valores em R$ de 15/01/2018
(preços POF): a incidência usa apenas SHARES, invariantes ao nível de preços.

Executar: PYTHONPATH=src python3 -m aferir.perfis_trava  (após aferir.pipeline)
Saídas em data/processed/: perfis_trava.csv (partição das classes),
incidencia_regimes_decil.csv (benefício por classe×decil + índice pró-rico),
resultados_perfis_trava.csv (perfis × γ ∈ {10; 12,5; 15}%).
"""
from __future__ import annotations

import json
import time
from collections.abc import Mapping

import numpy as np
import pandas as pd

from . import config, pipeline
from .base import itens_combustiveis
from .gaps import (CLASSES_FAVORECIDAS, MATRIZ_PATH, _RE_ALIMENTOS_60,
                   _RE_EDUCACAO_60, _RE_SAUDE_60, classifica_regime)

GATILHO = config.TRAVA_SOMA_REFERENCIAS       # 0,265 — art. 475, §11
TOL_LAMBDA = 1e-6                             # mesma tolerância do trava.py
GAMMA_CENTRAL = config.GAP_CONFORMIDADE["central"]
BI = 1e9

CLASSE_ZFM = "zfm"
CORTAVEIS = CLASSES_FAVORECIDAS + (CLASSE_ZFM,)   # alcance do PLP do §11
PROTEGIDAS_P2 = ("cesta_aliquota_zero", "saude_60", "educacao_60")

DECIS_POBRES = (1, 2, 3)                      # mesmos decis do proxy CadÚnico
DECIS_RICOS = (8, 9, 10)

PERFIS = ("P1_uniforme", "P2_protege_essenciais", "P3_regressividade")

# Ordem canônica de reporte da partição (favorecidas + zfm + sem favorecimento)
ORDEM_PARTICAO = CORTAVEIS + ("padrao", "fora_campo")

# critério textual (regra determinística) por classe — perfis_trava.csv
CRITERIOS = {
    "cesta_aliquota_zero": ("flag≠F e m_i=0,00 — alíquota zero/imunidade "
                            "(cesta básica nacional Anexo I; hortícolas, "
                            "frutas e ovos Anexo XV; livros CF art. 150, VI, d)"),
    "saude_60": ("flag≠F e m_i=0,40 e tratamento_ibs_v3 casa regex saúde "
                 f"(precedência 1): {_RE_SAUDE_60}"),
    "educacao_60": ("flag≠F e m_i=0,40 e tratamento_ibs_v3 casa regex educação "
                    f"(precedência 2): {_RE_EDUCACAO_60}"),
    "alimentos_60": ("flag≠F e m_i=0,40 e tratamento_ibs_v3 casa regex alimentos "
                     f"(precedência 3): {_RE_ALIMENTOS_60}"),
    "demais_60": ("flag≠F e m_i=0,40 sem casar os regex anteriores (higiene "
                  "pessoal/limpeza Anexos VIII e X, serviços funerários, "
                  "cuidados a idosos — Anexo III)"),
    "reducao_40_especificos": ("flag≠F e m_i=0,60 — regimes específicos com "
                               "redução de 40% (bares/restaurantes, hotelaria, "
                               "turismo, transporte coletivo)"),
    "reducao_30": ("flag≠F e m_i=0,70 — redução de 30% (profissões "
                   "regulamentadas, art. 127; planos veterinários)"),
    "reducao_70_imoveis": ("flag≠F e m_i=0,30 — regime de bens imóveis: "
                           "locação/arrendamento (redução de 70%)"),
    "padrao": "flag≠F e m_i=1,00 — regime geral, sem favorecimento (λ inócuo)",
    "fora_campo": ("flag=F — fora do campo de incidência (arts. 4º/6º); o "
                   "§11 do art. 475 não o alcança"),
    CLASSE_ZFM: ("pseudo-classe: adendo de política da ZFM (só AM), "
                 "zfm=0,13 (pipeline.ZFM_AM, convenção herdada v1; χ_AM STN); "
                 "zfm(λ)=0,13·(1−λ_zfm) em pipeline._d_esfera"),
}

FORMULA_RESULT = (
    "m_i(λ_c)=m_i+λ_c·(1−m_i) i∉F (λ_c por classe — gaps.classifica_regime); "
    "zfm(λ_zfm)=0,13·(1−λ_zfm); cashback recomputado; bisseção do grau t do "
    "perfil t.q. Σ_s τ_s=26,5% (tol 1e-6); custo_trava=Σ_s τ_s(λ*)·[D_s(λ*)−"
    "D_s(0)]; custo_central=Σ_s τ_s(0)·[D_s(λ*)−D_s(0)]; cv=dp(ddof=1)÷média "
    "do vetor indicativo por UF")
FONTE_RESULT = (
    "LC 214/2025, art. 475, §§10-11; matriz_pof_ibs_v5.csv × POF 2017-2018; "
    "construção B (ψ=0, iso-carga) — AFERIR, perfis E3 do parecer")
FONTE_INCIDENCIA = (
    "IBGE POF 2017-2018 (microdados via aferir.inputs.pof.le_despesas; decis "
    "populacionais nacionais de renda per capita — pof_boot_uc.parquet, regra "
    "de aferir.inputs.pof.decis_renda); matriz_pof_ibs_v5.csv; LC 214/2025")


# ------------------------------------------------------------ solver (memo)
_MEMO: dict[tuple, dict] = {}


def _chave_lam(lam: float | Mapping[str, float]) -> tuple:
    """Chave canônica do memo: entradas nulas de um dict são inócuas."""
    if isinstance(lam, Mapping):
        return tuple(sorted((c, float(v)) for c, v in lam.items()
                            if float(v) != 0.0))
    return ("__float__", float(lam))


def _executa(gamma: float, lam: float | Mapping[str, float]) -> dict:
    """Construção B no cenário da trava (ψ=0, iso-carga), com memoização."""
    chave = (float(gamma), _chave_lam(lam))
    if chave not in _MEMO:
        _MEMO[chave] = pipeline.executa(gamma=gamma, psi=0.0,
                                        modo="iso_carga", lam=lam)
    return _MEMO[chave]


def _bisseca_t(gamma: float, lam_de_t, tol: float = TOL_LAMBDA) -> dict:
    """Bisseção determinística do grau t∈[0;1] do perfil (mesma malha do
    trava.py: lo/hi com Σ(lo)>26,5%≥Σ(hi); t*=(lo+hi)/2).

    lam_de_t: t → dict[classe → λ_c]. Retorna {"t", "lam", "status",
    "r_star", "r_0"}; status ∈ {ja_conforme, factivel, infactivel}.
    """
    r0 = _executa(gamma, 0.0)
    if r0["sol"].soma <= GATILHO:                 # já trava-conforme
        return {"t": 0.0, "lam": lam_de_t(0.0), "status": "ja_conforme",
                "r_star": r0, "r_0": r0}
    r1 = _executa(gamma, lam_de_t(1.0))
    if r1["sol"].soma > GATILHO:                  # nem o corte pleno fecha
        return {"t": 1.0, "lam": lam_de_t(1.0), "status": "infactivel",
                "r_star": r1, "r_0": r0}
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if _executa(gamma, lam_de_t(mid))["sol"].soma > GATILHO:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2.0
    return {"t": t, "lam": lam_de_t(t), "status": "factivel",
            "r_star": _executa(gamma, lam_de_t(t)), "r_0": r0}


def resolve_p1(gamma: float = GAMMA_CENTRAL) -> dict:
    """P1 uniforme: λ_c ≡ t em TODAS as classes cortáveis (validação ≡ trava.py)."""
    return _bisseca_t(gamma, lambda t: {c: t for c in CORTAVEIS})


def resolve_p2(gamma: float = GAMMA_CENTRAL) -> dict:
    """P2 protege essenciais: λ=0 em cesta/alíquota zero, saúde-60 e
    educação-60; λ_c ≡ t nas demais classes cortáveis (inclusive zfm)."""
    return _bisseca_t(
        gamma,
        lambda t: {c: (0.0 if c in PROTEGIDAS_P2 else t) for c in CORTAVEIS})


def resolve_p3(gamma: float, ordem: tuple[str, ...],
               tol: float = TOL_LAMBDA) -> dict:
    """P3 corte por regressividade: percorre `ordem` (da classe mais pró-rica
    à mais pró-pobre), fixando λ=1 classe a classe; na primeira classe cujo
    corte pleno fecha Σ ≤ 26,5% (classe MARGINAL), bissecciona o λ parcial.

    Retorna {"t", "lam", "status", "classe_marginal", "r_star", "r_0"}.
    """
    if set(ordem) != set(CORTAVEIS):
        raise ValueError("ordem do P3 deve conter exatamente as classes cortáveis")
    r0 = _executa(gamma, 0.0)
    if r0["sol"].soma <= GATILHO:
        return {"t": 0.0, "lam": {}, "status": "ja_conforme",
                "classe_marginal": None, "r_star": r0, "r_0": r0}
    plenas: list[str] = []
    for classe in ordem:
        def lam_de_t(t: float, _plenas=tuple(plenas), _c=classe) -> dict:
            d = {c: 1.0 for c in _plenas}
            d[_c] = t
            return d
        if _executa(gamma, lam_de_t(1.0))["sol"].soma <= GATILHO:
            lo, hi = 0.0, 1.0
            while hi - lo > tol:
                mid = (lo + hi) / 2.0
                if _executa(gamma, lam_de_t(mid))["sol"].soma > GATILHO:
                    lo = mid
                else:
                    hi = mid
            t = (lo + hi) / 2.0
            return {"t": t, "lam": lam_de_t(t), "status": "factivel",
                    "classe_marginal": classe,
                    "r_star": _executa(gamma, lam_de_t(t)), "r_0": r0}
        plenas.append(classe)
    lam = {c: 1.0 for c in CORTAVEIS}             # nem o corte total fecha
    return {"t": 1.0, "lam": lam, "status": "infactivel",
            "classe_marginal": None, "r_star": _executa(gamma, lam), "r_0": r0}


# ------------------------------------------------------------ métricas
def custos_beneficios_bi(res: dict) -> tuple[float, float]:
    """(custo às alíquotas trava-conformes, custo às alíquotas centrais):
    Σ_s τ_s(λ*)·ΔD_s e Σ_s τ_s(0)·ΔD_s, ΔD_s = D_s(λ*)−D_s(0), R$ bi 2024."""
    s_star, s_0 = res["r_star"]["sol"], res["r_0"]["sol"]
    taus_star = {"uniao": s_star.tau_U, "estadual": s_star.tau_E,
                 "municipal": s_star.tau_M}
    taus_0 = {"uniao": s_0.tau_U, "estadual": s_0.tau_E,
              "municipal": s_0.tau_M}
    dd = {e: float(res["r_star"]["d"][e].sum()) - float(res["r_0"]["d"][e].sum())
          for e in taus_star}
    return (float(sum(taus_star[e] * dd[e] for e in dd)),
            float(sum(taus_0[e] * dd[e] for e in dd)))


def _cv(vetor: dict[str, float]) -> float:
    """Coeficiente de variação (desvio-padrão ddof=1 ÷ média) do vetor por UF."""
    s = pd.Series(vetor, dtype=float)
    return float(s.std(ddof=1) / s.mean())


def lam_completo(lam: Mapping[str, float]) -> dict[str, float]:
    """λ por classe com TODAS as cortáveis explícitas (ausente ⇒ 0,0)."""
    return {c: float(lam.get(c, 0.0)) for c in CORTAVEIS}


# ------------------------------------------------------------ partição (CSV 1)
def particao_classes() -> pd.DataFrame:
    """perfis_trava.csv: definição das classes com contagem, despesa e m médio.

    despesa_rs_bi = Σ despesa POF nacional dos itens da classe, EX-combustíveis
    monofásicos (universo da base ordinária), R$ bi/ano a preços de 15/01/2018;
    para a pseudo-classe zfm, é a despesa EM CAMPO do AM (base do adendo).
    """
    classes = classifica_regime()
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    comb = itens_combustiveis(despesa)
    d = despesa[~despesa["codigo_pof"].isin(comb)] \
        .merge(classes, on="codigo_pof", how="left", validate="m:1")

    linhas = []
    for classe in ORDEM_PARTICAO:
        if classe == CLASSE_ZFM:
            em_campo_am = d[(d["uf"] == "AM") & (d["flag"] != "F")
                            & d["m_i"].notna()]
            linhas.append({
                "classe": classe, "criterio": CRITERIOS[classe],
                "n_itens": 0,
                "despesa_rs_bi": float(em_campo_am["despesa_anual_rs"].sum()) / BI,
                "m_medio": float("nan"),
            })
            continue
        g = d[d["classe"] == classe]
        n = int((classes["classe"] == classe).sum())
        desp = float(g["despesa_anual_rs"].sum())
        m_medio = (float((g["despesa_anual_rs"] * g["m_i"]).sum() / desp)
                   if desp > 0 else float("nan"))
        linhas.append({"classe": classe, "criterio": CRITERIOS[classe],
                       "n_itens": n, "despesa_rs_bi": desp / BI,
                       "m_medio": m_medio})
    out = pd.DataFrame(linhas)
    out["formula"] = (
        "classe: gaps.classifica_regime (m_i × tratamento_ibs_v3 da matriz); "
        "n_itens: contagem na matriz (13.474 itens); despesa_rs_bi: Σ despesa "
        "POF nacional do item, ex-combustíveis monofásicos, R$ bi/ano preços "
        "15/01/2018; m_medio: Σ w·m_i ÷ Σ w (w=despesa); zfm: despesa em "
        "campo do AM (base do adendo zfm=0,13)")
    out["fonte"] = ("matriz_pof_ibs_v5.csv; pof_despesa_item_uf.parquet "
                    "(IBGE POF 2017-2018); LC 214/2025; " + FONTE_RESULT)
    return out


# ------------------------------------------------------- incidência (CSV 2)
def _decil_por_uc() -> pd.DataFrame:
    """Decil populacional nacional de renda per capita por UC, replicado
    deterministicamente de pof_boot_uc.parquet com a MESMA regra de
    aferir.inputs.pof.decis_renda (ordenação por rpc com desempate pela chave
    da UC, mergesort; acumulação do peso populacional pop_w)."""
    uc = pd.read_parquet(config.PROCESSED / "pof_boot_uc.parquet")
    uc = uc.sort_values(["rpc", "cod_upa", "num_dom", "num_uc"],
                        kind="mergesort").reset_index(drop=True)
    acum = uc["pop_w"].cumsum() / uc["pop_w"].sum()
    uc["decil_renda"] = np.clip(np.ceil(acum * 10), 1, 10).astype(int)
    return uc[["cod_upa", "num_dom", "num_uc", "decil_renda"]]


def despesa_item_decil() -> pd.DataFrame:
    """Despesa POF por item×decil nacional (+ uf), dos microdados.

    Junta aferir.inputs.pof.le_despesas (nível micro, anualização IBGE) ao
    decil de renda per capita por UC (_decil_por_uc). Retorna
    [codigo_pof, uf, decil_renda, despesa_anual_rs] agregado.
    """
    from .inputs.pof import le_despesas
    micro = le_despesas()
    dec = _decil_por_uc()
    m = micro.merge(dec, on=["cod_upa", "num_dom", "num_uc"],
                    how="left", validate="m:1")
    perda = m["decil_renda"].isna().mean()
    if perda > 0.001:
        raise ValueError(f"{perda:.3%} dos registros micro sem decil (>0,1%)")
    m = m.dropna(subset=["decil_renda"])
    m["decil_renda"] = m["decil_renda"].astype(int)
    m["codigo_pof"] = m["codigo_pof"].astype(str)
    return (m.groupby(["codigo_pof", "uf", "decil_renda"], as_index=False)
            ["despesa_anual_rs"].sum()
            .sort_values(["codigo_pof", "uf", "decil_renda"], kind="mergesort")
            .reset_index(drop=True))


def incidencia_regimes_decil(item_decil: pd.DataFrame) -> pd.DataFrame:
    """incidencia_regimes_decil.csv: benefício w_i·(1−m_i) por classe×decil.

    Universo: itens EM CAMPO (flag≠F), ex-combustíveis monofásicos, com
    correspondência na matriz — o mesmo de gaps.policy_gap_por_uf. Para a
    pseudo-classe zfm, benefício_d = 0,13 × despesa em campo do AM no decil d.
    indice_pro_rico = share do benefício nos decis 8-10 ÷ share nos decis 1-3.
    """
    classes = classifica_regime()
    comb = itens_combustiveis(item_decil)
    d = item_decil[~item_decil["codigo_pof"].isin(comb)] \
        .merge(classes, on="codigo_pof", how="left", validate="m:1")
    em_campo = d[(d["flag"] != "F") & d["m_i"].notna()]

    linhas = []
    for classe in CORTAVEIS:
        if classe == CLASSE_ZFM:
            g = em_campo[em_campo["uf"] == "AM"] \
                .groupby("decil_renda")["despesa_anual_rs"].sum() \
                .reindex(range(1, 11), fill_value=0.0)
            beneficio = pipeline.ZFM_AM * g
        else:
            sub = em_campo[em_campo["classe"] == classe]
            g = sub.groupby("decil_renda")["despesa_anual_rs"].sum() \
                .reindex(range(1, 11), fill_value=0.0)
            beneficio = sub.assign(b=sub["despesa_anual_rs"] * (1.0 - sub["m_i"])) \
                .groupby("decil_renda")["b"].sum() \
                .reindex(range(1, 11), fill_value=0.0)
        total_b = float(beneficio.sum())
        share = beneficio / total_b
        indice = (float(share.loc[list(DECIS_RICOS)].sum())
                  / float(share.loc[list(DECIS_POBRES)].sum()))
        for dec in range(1, 11):
            linhas.append({
                "classe": classe, "decil": dec,
                "despesa_rs_bi": float(g.loc[dec]) / BI,
                "beneficio_rs_bi": float(beneficio.loc[dec]) / BI,
                "share_beneficio": float(share.loc[dec]),
                "indice_pro_rico": indice,
            })
    out = pd.DataFrame(linhas)
    out["formula"] = (
        "beneficio_cd = Σ_{i∈classe} w_id·(1−m_i), w_id = despesa POF nacional "
        "item×decil (em campo, ex-combustíveis; R$ bi/ano preços 15/01/2018); "
        "zfm: beneficio_d = 0,13·despesa_em_campo_AM_d; share = beneficio_cd ÷ "
        "Σ_d beneficio_cd; indice_pro_rico = share(decis 8-10) ÷ share(decis "
        "1-3); decis populacionais nacionais de renda per capita")
    out["fonte"] = FONTE_INCIDENCIA
    return out


def ordem_pro_rico(incidencia: pd.DataFrame) -> tuple[str, ...]:
    """Ordem de corte do P3: classes cortáveis da mais pró-rica à mais
    pró-pobre (desempate determinístico pelo nome da classe)."""
    idx = (incidencia.groupby("classe")["indice_pro_rico"].first()
           .reindex(list(CORTAVEIS)))
    if idx.isna().any():
        raise ValueError("classe cortável sem índice pró-rico na incidência")
    ordenado = sorted(idx.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(c for c, _ in ordenado)


# ------------------------------------------------------------ resultados
def linha_resultado(perfil: str, gamma: float, res: dict) -> dict:
    """Linha de resultados_perfis_trava.csv para um perfil resolvido."""
    s = res["r_star"]["sol"]
    custo_trava, custo_central = custos_beneficios_bi(res)
    return {
        "perfil": perfil,
        "gamma": gamma,
        "lambda_por_classe": json.dumps(
            lam_completo(res["lam"]), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False),
        "tau_CBS_pp": s.tau_U * 100,
        "tau_E_pp": s.tau_E * 100,
        "tau_M_pp": s.tau_M * 100,
        "soma_pp": s.soma * 100,
        "beneficios_suprimidos_rs_bi_trava": custo_trava,
        "beneficios_suprimidos_rs_bi_central": custo_central,
        "cv_vetor_E": _cv(res["r_star"]["vetor_estadual"]),
        "cv_vetor_M": _cv(res["r_star"]["vetor_municipal"]),
        "status": res["status"],
        "formula": FORMULA_RESULT,
        "fonte": FONTE_RESULT,
    }


def main() -> None:
    t_inicio = time.time()

    part = particao_classes()
    part.to_csv(config.PROCESSED / "perfis_trava.csv", index=False)

    t0 = time.time()
    item_decil = despesa_item_decil()
    inc = incidencia_regimes_decil(item_decil)
    inc.to_csv(config.PROCESSED / "incidencia_regimes_decil.csv", index=False)
    t_incidencia = time.time() - t0
    ordem = ordem_pro_rico(inc)

    solvers = {
        "P1_uniforme": lambda g: resolve_p1(g),
        "P2_protege_essenciais": lambda g: resolve_p2(g),
        "P3_regressividade": lambda g: resolve_p3(g, ordem),
    }
    linhas, tempos = [], {}
    for perfil in PERFIS:
        for rotulo in ("factivel", "central", "conservador"):
            gamma = config.GAP_CONFORMIDADE[rotulo]
            t0 = time.time()
            res = solvers[perfil](gamma)
            tempos[(perfil, rotulo)] = time.time() - t0
            linhas.append(linha_resultado(perfil, gamma, res))
    resultados = pd.DataFrame(linhas)
    resultados.to_csv(config.PROCESSED / "resultados_perfis_trava.csv",
                      index=False)

    # ---------------- console: diagnóstico e custo de execução ----------------
    print("Partição das classes (perfis_trava.csv):")
    print(part[["classe", "n_itens", "despesa_rs_bi", "m_medio"]]
          .round(2).to_string(index=False))
    idx = inc.groupby("classe")["indice_pro_rico"].first() \
        .reindex(list(ordem))
    print("\nÍndice pró-rico (ordem de corte do P3):")
    print(idx.round(3).to_string())
    print("\nResultados (resultados_perfis_trava.csv):")
    print(resultados[["perfil", "gamma", "soma_pp", "tau_CBS_pp", "tau_E_pp",
                      "tau_M_pp", "beneficios_suprimidos_rs_bi_trava",
                      "cv_vetor_E", "cv_vetor_M", "status"]]
          .round(4).to_string(index=False))
    for (perfil, rotulo), dt in tempos.items():
        print(f"tempo {perfil} γ={rotulo}: {dt:.1f} s")
    print(f"incidência item×decil (microdados): {t_incidencia:.1f} s")
    print(f"total: {time.time() - t_inicio:.1f} s")


if __name__ == "__main__":
    main()
