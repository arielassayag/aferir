"""Trava do art. 475, §§10-11 (LC 214) — o mecanismo LEGAL que garante Σ ≤ 26,5%.

Se a soma das alíquotas de referência estimadas para 2033 superar 26,5%
(§10), o Poder Executivo deve encaminhar PLP que reduza os regimes
diferenciados/favorecidos para recolocar a soma no gatilho (§11). Este
módulo INVERTE o dispositivo: resolve a fração λ* ∈ [0; 1] de encolhimento
UNIFORME dos favorecimentos que tornaria a construção B trava-conforme —
λ* é o "percentual de encolhimento dos regimes favorecidos que o PLP do
§11 teria de entregar".

Mecanismo (construção B; ψ=0; iso-carga; γ na grade do corredor SERT):
  m_i(λ) = m_i + λ·(1−m_i)  — itens em campo: o favorecimento (1−m_i)
                              encolhe na proporção λ (gaps.py, param. lam);
  flag F intocada           — fora do campo (arts. 4º/6º) não é regime
                              favorecido, o §11 não o alcança;
  zfm(λ) = zfm·(1−λ)        — o adendo ZFM (AM) é favorecimento de política
                              e segue a mesma proporção (pipeline._d_esfera);
  cashback recomputado      — a base líquida cresce com λ, logo a dedução do
                              art. 118 cresce junto (recalculada na malha).
π^p(λ) é recomputado por UF de pof_despesa_item_uf ⋈ matriz legal
(identidade implicada, verificada em teste: π^p(λ) = (1−λ)·π^p).

λ*: Σ_s τ_s(λ*) = 26,5% por bisseção determinística em [0; 1], tol 1e-6.
Σ(λ) é estritamente decrescente (D_s(λ) cresce com λ e o acréscimo de
cashback é de 2ª ordem), então a raiz é única.

Custo dos benefícios suprimidos (derivação da fórmula):
  Em iso-carga cada esfera desacopla — τ_s(λ)·D_s(λ) = Alvo_s − σ·G_s, com
  G e σ independentes de λ (iso-receita em λ). O benefício que os regimes
  favorecidos perdem é o imposto que a base des-favorecida passa a recolher
  às alíquotas trava-conformes:

      custo(λ*) = Σ_s τ_s(λ*) · [D_s(λ*) − D_s(0)]      (R$ bi 2024, janela)

  Da iso-receita segue a identidade (verificada em teste):

      τ_s(λ*)·[D_s(λ*) − D_s(0)] = [τ_s(0) − τ_s(λ*)]·D_s(0)

  isto é, o custo suprimido equivale exatamente ao alívio de alíquota
  concedido ao restante da base vigente.

Executar: PYTHONPATH=src python3 -m aferir.trava  (após aferir.pipeline)
Saídas: data/processed/trava_conforme.csv (grade γ ∈ {10; 12,5; 15}%),
data/processed/trava_vetor_uf.csv (vetores por UF no γ central),
data/processed/MANIFEST_TRAVA.json.
"""
from __future__ import annotations

import pandas as pd

from . import config, pipeline
from .base import itens_combustiveis
from .gaps import policy_gap_por_uf
from .provenance import MANIFEST, Label, Num

GATILHO = config.TRAVA_SOMA_REFERENCIAS       # 0,265 — art. 475, §11
TOL_LAMBDA = 1e-6
GAMMA_CENTRAL = config.GAP_CONFORMIDADE["central"]

FORMULA = ("m_i(λ)=m_i+λ·(1−m_i) i∉F; zfm(λ)=zfm·(1−λ); cashback recomputado; "
           "λ*: Σ_s τ_s(λ*)=26,5% (bisseção em [0;1], tol 1e-6); "
           "custo=Σ_s τ_s(λ*)·[D_s(λ*)−D_s(0)]")
FONTE = ("LC 214/2025, art. 475, §§10-11; matriz_pof_ibs_v5.csv × POF; "
         "construção B (ψ=0, iso-carga) — AFERIR")


def _executa(gamma: float, lam: float) -> dict:
    """Construção B no cenário da trava: ψ=0, redutor iso-carga."""
    return pipeline.executa(gamma=gamma, psi=0.0, modo="iso_carga", lam=lam)


def resolve_lambda(gamma: float = GAMMA_CENTRAL,
                   tol: float = TOL_LAMBDA) -> dict:
    """Resolve λ* tal que Σ τ_s(λ*) = 26,5% (bisseção determinística).

    Retorna {"lam", "r_star" (executa em λ*), "r_0" (executa em λ=0),
    "soma_0", "soma_1"} — r_0 alimenta o custo dos benefícios e soma_0/1
    dão a leitura em p.p. do custo total dos favorecimentos.
    """
    r0 = _executa(gamma, 0.0)
    if r0["sol"].soma <= GATILHO:                 # já trava-conforme
        return {"lam": 0.0, "r_star": r0, "r_0": r0,
                "soma_0": r0["sol"].soma, "soma_1": None}
    r1 = _executa(gamma, 1.0)
    if r1["sol"].soma > GATILHO:
        raise ValueError(
            f"Σ(λ=1)={r1['sol'].soma:.4%} > 26,5%: suprimir favorecimentos "
            "não basta — a trava exigiria medidas além do §11")

    lo, hi = 0.0, 1.0                             # Σ(lo) > 26,5% ≥ Σ(hi)
    while hi - lo > tol:
        mid = (lo + hi) / 2.0
        if _executa(gamma, mid)["sol"].soma > GATILHO:
            lo = mid
        else:
            hi = mid
    lam_star = (lo + hi) / 2.0
    return {"lam": lam_star, "r_star": _executa(gamma, lam_star), "r_0": r0,
            "soma_0": r0["sol"].soma, "soma_1": r1["sol"].soma}


def pi_p_nacional_pos_lambda(lam: float) -> float:
    """π^p nacional recomputado da matriz com m_i(λ) (ex-combustíveis, i∉F)."""
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    comb = itens_combustiveis(despesa)
    pi = policy_gap_por_uf(despesa[~despesa["codigo_pof"].isin(comb)], lam=lam)
    return float((pi["pi_p"] * pi["despesa_em_campo"]).sum()
                 / pi["despesa_em_campo"].sum())


def custo_beneficios_bi(res: dict) -> float:
    """Custo dos benefícios suprimidos: Σ_s τ_s(λ*)·[D_s(λ*)−D_s(0)], R$ bi 2024."""
    s = res["r_star"]["sol"]
    taus = {"uniao": s.tau_U, "estadual": s.tau_E, "municipal": s.tau_M}
    return float(sum(
        taus[e] * (float(res["r_star"]["d"][e].sum())
                   - float(res["r_0"]["d"][e].sum()))
        for e in taus))


def resolve_grade(tol: float = TOL_LAMBDA) -> dict[str, dict]:
    """λ* para a grade do corredor de conformidade γ ∈ {10; 12,5; 15}%."""
    return {rotulo: resolve_lambda(g, tol)
            for rotulo, g in config.GAP_CONFORMIDADE.items()}


def main() -> None:
    grade = resolve_grade()

    linhas = []
    for rotulo, res in grade.items():
        gamma = config.GAP_CONFORMIDADE[rotulo]
        s = res["r_star"]["sol"]
        linhas.append({
            "gamma": gamma,
            "cenario_gamma": rotulo,
            "lambda": res["lam"],
            "tau_CBS_pp": s.tau_U * 100,
            "tau_E_pp": s.tau_E * 100,
            "tau_M_pp": s.tau_M * 100,
            "soma_pp": s.soma * 100,
            "pi_p_pos_lambda": pi_p_nacional_pos_lambda(res["lam"]),
            "custo_beneficios_rs_bi": custo_beneficios_bi(res),
            "formula": FORMULA,
            "fonte": FONTE,
        })
    conforme = pd.DataFrame(linhas)
    conforme.to_csv(config.PROCESSED / "trava_conforme.csv", index=False)

    # R5 (parecer): λ herda integralmente a incerteza da soma central — a
    # elasticidade implícita na própria grade (corredor de γ) é o número de
    # política relevante, não o λ pontual. Δλ/Δsoma entre os extremos do
    # corredor, com as somas SEM trava lidas de aferir_nacional.csv.
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    livre = nac[(nac["psi"] == 0.0) & (nac["modo_redutor"] == "iso_carga")] \
        .set_index("cenario_gamma")["soma_pp"]
    lam_ix = conforme.set_index("cenario_gamma")["lambda"]
    d_lam = float(lam_ix["conservador"] - lam_ix["factivel"])
    d_soma = float(livre["conservador"] - livre["factivel"])
    met = pd.DataFrame([
        ("elasticidade_lambda_pp_por_ponto_soma", 100 * d_lam / d_soma,
         "100 × [λ*(γ=15%) − λ*(γ=10%)] ÷ [Σ_livre(γ=15%) − Σ_livre(γ=10%)]",
         "trava_conforme.csv × aferir_nacional.csv (corredor de γ)"),
        ("lambda_corredor_min_pct", 100 * float(lam_ix["factivel"]),
         "λ* no piso do corredor (γ=10%)", "trava_conforme.csv"),
        ("lambda_corredor_max_pct", 100 * float(lam_ix["conservador"]),
         "λ* no teto do corredor (γ=15%)", "trava_conforme.csv"),
        ("lambda_central_pct", 100 * float(lam_ix["central"]),
         "λ* central (γ=12,5%)", "trava_conforme.csv"),
        ("soma_livre_corredor_min_pp", float(livre["factivel"]),
         "Σ sem trava no piso do corredor", "aferir_nacional.csv"),
        ("soma_livre_corredor_max_pp", float(livre["conservador"]),
         "Σ sem trava no teto do corredor", "aferir_nacional.csv"),
    ], columns=["chave", "valor", "formula", "fonte"])
    met.to_csv(config.PROCESSED / "metricas_trava.csv", index=False)

    central = grade["central"]
    r_star = central["r_star"]
    vetores = [{
        "uf": uf,
        "tau_E_uf_pp": r_star["vetor_estadual"][uf] * 100,
        "tau_M_uf_pp": r_star["vetor_municipal"].get(uf, float("nan")) * 100,
        "lambda": central["lam"],
        "gamma": GAMMA_CENTRAL,
        "formula": "vetor_indicativo (DESIGN §2.6) com D_uf(λ*); demais "
                   "esferas na referência nacional trava-conforme",
        "fonte": FONTE,
    } for uf in sorted(r_star["vetor_estadual"])]
    vet = pd.DataFrame(vetores)
    vet.to_csv(config.PROCESSED / "trava_vetor_uf.csv", index=False)

    MANIFEST.registra("trava_encolhimento_uniforme", Num(
        1.0,
        "m_i(λ)=m_i+λ·(1−m_i) com o MESMO λ para todo i∉F; zfm(λ)=zfm·(1−λ)",
        "convenção de implementação do PLP do §11 (a lei obriga o projeto, "
        "não prescreve o desenho da redução; uniforme = sem priorização "
        "setorial sem base legal)", Label.CONVENCAO, "indicador"))
    MANIFEST.registra("lambda_trava_central", Num(
        central["lam"],
        "λ*: Σ_s τ_s(λ*) = 26,5% (bisseção, tol 1e-6; γ=12,5%, ψ=0, iso-carga)",
        "LC 214, art. 475, §§10-11; pipeline AFERIR", Label.DERIVADO,
        "fração dos favorecimentos"))
    MANIFEST.registra("custo_beneficios_trava_central", Num(
        custo_beneficios_bi(central),
        "Σ_s τ_s(λ*)·[D_s(λ*)−D_s(0)] = Σ_s [τ_s(0)−τ_s(λ*)]·D_s(0)",
        "identidade iso-receita (trava.py); LC 214, art. 475, §11",
        Label.DERIVADO, "R$ bi 2024"))
    MANIFEST.registra("custo_favorecimentos_pp", Num(
        (central["soma_0"] - central["soma_1"]) * 100,
        "Σ(λ=0) − Σ(λ=1): custo TOTAL dos regimes favorecidos em p.p. da "
        "soma das referências (γ central)",
        "análogo interno ao +4,96 p.p. da NT SERT jul/2024", Label.DERIVADO,
        "p.p."))
    MANIFEST.grava(config.PROCESSED / "MANIFEST_TRAVA.json")

    print(conforme[["cenario_gamma", "lambda", "tau_CBS_pp", "tau_E_pp",
                    "tau_M_pp", "soma_pp", "pi_p_pos_lambda",
                    "custo_beneficios_rs_bi"]].round(4).to_string(index=False))
    print(f"\nTRAVA (γ central): λ* = {central['lam']:.6f} — o PLP do art. "
          f"475, §11 teria de encolher {central['lam']:.1%} dos favorecimentos"
          f"; custo = R$ {custo_beneficios_bi(central):.1f} bi/ano (janela); "
          f"custo total dos favorecimentos = "
          f"{(central['soma_0'] - central['soma_1']) * 100:.2f} p.p.")


if __name__ == "__main__":
    main()
