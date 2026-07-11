"""Gera metadata/diff_baseline.md: diff item a item contra a linha de base
congelada (metadata/baseline_revisao.json, commit 20d6e32) com a atribuição
de cada movimento às correções da revisão, medida pela própria grade.

Uso: PYTHONPATH=src python3 tools/gera_diff_baseline.py
Determinístico: tudo vem dos processados correntes + baseline congelada.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROCESSED = RAIZ / "data" / "processed"
BASELINE = RAIZ / "metadata" / "baseline_revisao.json"
SAIDA = RAIZ / "metadata" / "diff_baseline.md"


def main() -> None:
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    nac = pd.read_csv(PROCESSED / "aferir_nacional.csv")
    cen = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
              & (nac.modo_redutor == "iso_carga")].iloc[0]
    anc = pd.read_csv(PROCESSED / "aferir_ancoras.csv") \
        .set_index("variante_federal")["soma_pp"]
    met = pd.read_csv(PROCESSED / "metricas.csv").set_index("chave")["valor"]
    trava = pd.read_csv(PROCESSED / "trava_conforme.csv")
    tc = trava[trava.cenario_gamma == "central"].iloc[0]

    def linha_sens(rotulo: str) -> float | None:
        sel = nac[nac.cenario_gamma == rotulo]
        return float(sel["soma_pp"].iloc[0]) if len(sel) else None

    b_manchete = {k: float(v) for k, v in base["manchete_central_B"].items()}
    soma0, soma1 = b_manchete["soma_pp"], float(cen.soma_pp)

    # decomposição do movimento da soma central medida pela grade corrente:
    # cada Δ = central − sens_<reversão da correção> (efeito de MANTER a
    # correção); o resíduo agrupa A2/A3 (vigências) + A5 (perímetro G) +
    # interações, que não têm linha de reversão própria na grade.
    efeitos = {}
    for rotulo, nome in (("sens_sifim_incluido",
                          "E7.1 SIFIM imputado excluído da âncora"),
                         ("sens_fbcf_sem_redutores",
                          "E7.2 redutores imobiliários do art. 261")):
        s = linha_sens(rotulo)
        if s is not None:
            efeitos[nome] = soma1 - s
    residuo = (soma1 - soma0) - sum(efeitos.values())

    git_sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True,
                             cwd=RAIZ).stdout.strip()

    md = []
    md.append("# Diff contra a linha de base da revisão (Onda 0)")
    md.append("")
    md.append(f"Baseline: `{base['baseline_run_id'][:7]}` "
              f"(congelada em {base['data_congelamento']}). "
              f"Estado corrente: working tree sobre `{git_sha}`.")
    md.append("")
    md.append("## Manchete central (construção B, γ=12,5%, ψ=0, iso-carga)")
    md.append("")
    md.append("| componente | baseline | corrente | Δ (p.p.) |")
    md.append("|---|---:|---:|---:|")
    for chave, col in (("tau_CBS_pp", "tau_CBS_pp"), ("tau_E_pp", "tau_E_pp"),
                       ("tau_M_pp", "tau_M_pp"), ("soma_pp", "soma_pp")):
        v0, v1 = b_manchete[chave], float(cen[col])
        md.append(f"| {chave} | {v0:.4f} | {v1:.4f} | {v1 - v0:+.4f} |")
    md.append("")
    md.append("### Atribuição do movimento da soma (medida pela grade)")
    md.append("")
    md.append("| correção | Δ soma (p.p.) |")
    md.append("|---|---:|")
    for nome, d in efeitos.items():
        md.append(f"| {nome} | {d:+.4f} |")
    md.append(f"| A5 perímetro de G + A2/A3 vigências de combustíveis + "
              f"interações (resíduo) | {residuo:+.4f} |")
    md.append(f"| **total** | **{soma1 - soma0:+.4f}** |")
    md.append("")
    md.append("## Construção A (âncoras)")
    md.append("")
    md.append("| variante | baseline | corrente | Δ |")
    md.append("|---|---:|---:|---:|")
    for var, v0 in base["construcao_A_somas"].items():
        v1 = float(anc[var])
        md.append(f"| {var} | {float(v0):.4f} | {v1:.4f} | "
                  f"{v1 - float(v0):+.4f} |")
    md.append("")
    md.append("## Trava-conforme (γ central)")
    md.append("")
    lam0 = float(base["trava_conforme_amostra"][1]["lambda"])
    md.append(f"- λ*: {lam0:.4f} → {float(tc['lambda']):.4f} "
              "(o novo central, maior, exige encolhimento maior dos "
              "favorecimentos para fechar em 26,5%).")
    c0 = float(base["trava_conforme_amostra"][1]["custo_beneficios_rs_bi"])
    md.append(f"- Custo dos benefícios suprimidos: R$ {c0:.1f} bi → "
              f"R$ {float(tc['custo_beneficios_rs_bi']):.1f} bi/ano.")
    md.append("")
    md.append("## Métricas-chave")
    md.append("")
    md.append("| chave | baseline | corrente |")
    md.append("|---|---:|---:|")
    for chave, v0 in base["metricas_chave"].items():
        v1 = float(met[chave]) if chave in met.index else float("nan")
        md.append(f"| {chave} | {float(v0):.4f} | {v1:.4f} |")
    md.append("")
    md.append("As regressões protegidas do parecer (L7) e suas justificativas "
              "linha a linha estão em `metadata/qa_regressoes_parecer_l7.csv` "
              "(teste bloqueante `tests/test_regressoes_l7.py`).")
    md.append("")
    SAIDA.write_text("\n".join(md), encoding="utf-8")
    print("gravado", SAIDA)


if __name__ == "__main__":
    main()
