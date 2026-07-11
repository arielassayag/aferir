"""Invariantes verificáveis — gate estrito (exit 1 bloqueia o fluxo).

Testam a CORREÇÃO do pipeline (fechamentos, consistências entre peças declaratórias, domínios), nunca
o desfecho político-fiscal (a distância ao gatilho de 26,5% é resultado
reportado, não invariante — DESIGN §2.8).
"""
from __future__ import annotations

import sys

import pandas as pd

from . import config

FALHAS: list[str] = []


def _check(nome: str, ok: bool, detalhe: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {nome} — {detalhe}")
    if not ok:
        FALHAS.append(nome)


def main() -> None:
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    vet = pd.read_csv(config.PROCESSED / "aferir_vetor_uf.csv")
    re_ = pd.read_csv(config.PROCESSED / "r_estadual.csv")
    rm = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    ru = pd.read_csv(config.PROCESSED / "r_uniao.csv")
    pib = pd.read_csv(config.PROCESSED / "pib_nominal.csv").set_index("ano")["pib_rs_mi"]

    central = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
                  & (nac.modo_redutor == "iso_carga")]
    _check("I0 cenário central único", len(central) == 1, f"{len(central)} linha(s)")
    c = central.iloc[0]

    # I1 domínio e ordenação do corredor de conformidade
    grade = nac[(nac.psi == 0.0) & (nac.modo_redutor == "iso_carga")]
    somas = grade.set_index("cenario_gamma")["soma_pp"]
    _check("I1 ordenação do corredor γ",
           somas["factivel"] < somas["central"] < somas["conservador"],
           f"{somas['factivel']:.2f} < {somas['central']:.2f} < {somas['conservador']:.2f}")

    # I2 ψ reduz a alíquota monotonicamente (γ central, iso-carga)
    por_psi = nac[(nac.cenario_gamma == "central") & (nac.modo_redutor == "iso_carga")] \
        .set_index("psi")["soma_pp"]
    _check("I2 monotonicidade em ψ",
           por_psi[0.0] > por_psi[0.30] > por_psi[1.0],
           f"{por_psi[0.0]:.2f} > {por_psi[0.30]:.2f} > {por_psi[1.0]:.2f}")

    # I3 sanity-gate da soma — verifica CORREÇÃO do cômputo, não aderência à
    # literatura (a construção B é cota superior declarada; a comparação de
    # nível vive na T1/ponte). Faixa: [20; 36].
    _check("I3 Σ ∈ [20; 36] p.p. (sanidade)", 20.0 <= c.soma_pp <= 36.0,
           f"Σ = {c.soma_pp:.2f}")

    # I3b ordenação das construções: (A) âncora-consistente < (B) identidade
    # (a base implícita nas âncoras oficiais embute conformidade declarada ECF)
    anc = pd.read_csv(config.PROCESSED / "aferir_ancoras.csv")
    _check("I3b construção A < construção B (todas as esferas)",
           bool((anc["soma_pp"] < c.soma_pp).all()),
           f"A: {anc['soma_pp'].round(2).tolist()} < B: {c.soma_pp:.2f}")

    # I4 consistência intra-SICONFI RREO×DCA (autodeclarações do mesmo ente:
    # valida pipeline e coerência interna, não exatidão econômica — A1)
    desv = re_["desvio_rreo_dca_pct"].abs().max()
    _check("I4 consistência RREO×DCA ≤ 1%", desv <= 1.0, f"máx {desv:.3f}%")

    # I5 janela completa nas três esferas
    ok5 = (set(config.JANELA_RECEITA) <= set(re_["ano"])
           and set(config.JANELA_RECEITA) <= set(rm["ano"])
           and set(config.JANELA_RECEITA) <= set(ru["ano"]))
    _check("I5 janela 2024-2025 completa (3 esferas)", ok5, "r_estadual/r_municipal/r_uniao")

    # I6 cobertura municipal
    cob = rm.groupby("ano")["cobertura_pct"].mean()
    _check("I6 cobertura DCA municipal ≥ 90%", bool((cob >= 90).all()),
           "; ".join(f"{a}: {v:.1f}%" for a, v in cob.items()))

    # I7 vetores cobrem 27 UFs e mediana coerente com o agregado
    _check("I7 27 UFs nos vetores", len(vet) == 27, f"{len(vet)} UFs")
    med_e = vet["tau_E_uf_pp"].median()
    _check("I7b mediana estadual vs agregado (< 4 p.p.)",
           abs(med_e - c.tau_E_pp) < 4.0, f"mediana {med_e:.2f} vs {c.tau_E_pp:.2f}")

    # I10 reconciliação DECOMPOSTA com a meta SERT (janelas distintas DECLARADAS)
    ref_u_pct = ru[ru["ano"].isin(config.JANELA_RECEITA)]["pct_pib"].mean()
    _check("I10a União: ref. janela vs SERT 4,47% PIB (Δ < 1,5 p.p. do PIB)",
           abs(ref_u_pct - 4.47) < 1.5, f"{ref_u_pct:.2f}% PIB (PLDO 2025 = projeção; nossa = observada)")
    icms = re_.groupby("ano")["icms_bruto"].sum()
    iss = rm.groupby("ano").apply(
        lambda g: g.filter(like="iss").sum(numeric_only=True).max(), include_groups=False)
    sub_pct = ((icms + iss) / (pib * 1e6) * 100).loc[config.JANELA_RECEITA].mean()
    _check("I10b subnacional: (ICMS+ISS)/PIB vs SERT 7,76% (Δ < 1 p.p.)",
           abs(sub_pct - 7.76) < 1.0, f"{sub_pct:.2f}% PIB")

    # I15 sensibilidades federais (IS e âncora Tema 69) presentes e coerentes:
    # IS=0 é MECANICAMENTE maior que o central (alvo federal maior); a
    # diferença de âncora reproduz Δâncora×PIB no alvo (sinal EMPÍRICO — não
    # se impõe direção à convenção líquida×bruta).
    sens = nac[(nac.psi == 0.0) & (nac.modo_redutor == "iso_carga")] \
        .set_index("cenario_gamma")
    tem_sens = {"sens_is_zero", "sens_ancora_bruta"} <= set(sens.index)
    ok15 = (tem_sens
            and sens.at["sens_is_zero", "soma_pp"] > c.soma_pp
            and sens.at["sens_is_zero", "is_cenario"] == "zero"
            and sens.at["sens_ancora_bruta", "ancora_federal"] == "bruta_rfb")
    _check("I15 sensibilidades federais (IS proxy; âncora Tema 69)", bool(ok15),
           (f"IS=0: {sens.at['sens_is_zero', 'soma_pp']:.2f} > central "
            f"{c.soma_pp:.2f}; âncora bruta: "
            f"{sens.at['sens_ancora_bruta', 'soma_pp']:.2f}") if tem_sens
           else "linhas sens_* ausentes")

    # I14 municípios-sonda: match AO CENTAVO do painel municipal contra fonte
    # independente (DESIGN §2.8) — SP capital na DCA I-C 2024 (triangulada
    # MSC/parecer) e ISS-DF no RREO Anexo 03 (Brasília fora do painel DCA).
    painel24 = pd.read_parquet(config.PROCESSED / "iss_municipio_2024.parquet")
    sp = painel24.set_index("cod_ibge").loc[config.SONDA_SP_CAPITAL_COD_IBGE]
    ok_sp = abs(float(sp["iss_bruta"])
                - config.SONDA_SP_CAPITAL_2024_ISS_BRUTA) <= 0.005
    desvios_df = []
    for ano, esperado in config.SONDA_DF_ISS_RREO.items():
        linha = rm[(rm["uf"] == "DF") & (rm["ano"] == ano)]
        desvios_df.append(len(linha) == 1 and
                          abs(float(linha["iss_liquida"].iloc[0]) - esperado) <= 0.005)
    _check("I14 sonda municipal ao centavo (SP capital DCA×MSC; ISS-DF RREO)",
           ok_sp and all(desvios_df),
           f"SP 2024 = R$ {float(sp['iss_bruta']):,.2f}; DF 2024-25 conferem")

    # I16 cobertura ECONÔMICA municipal por exercício (A6): a cobertura por
    # contagem pode esconder omissões relevantes — a econômica, não.
    cov = pd.read_csv(config.PROCESSED / "coverage_siconfi.csv")
    ok16 = (set(cov["ano"]) >= {2024, 2025}
            and bool((cov["cobertura_economica_pct"] >= 99.0).all()))
    _check("I16 cobertura econômica DCA ≥ 99% (2024 e 2025)", ok16,
           "; ".join(f"{int(r.ano)}: {r.cobertura_economica_pct:.2f}%"
                     for r in cov.itertuples()))

    # I17 grade da revisão completa: cada alavanca declarada no texto tem a
    # sua linha calculada pelo pipeline (nenhuma sensibilidade manual).
    esperados = {"hiato_zero", "factivel", "central", "conservador",
                 "estresse", "sens_is_zero", "sens_ancora_bruta",
                 "sens_g_min", "sens_g_max", "sens_natureza36_off",
                 "sens_sifim_incluido", "sens_fbcf_sem_redutores",
                 "sens_base_pib_min", "sens_base_pib_max",
                 "sens_cashback_legal", "sens_cashback_legal_takeup80",
                 "sens_janela_2024", "sens_is_ampliado",
                 "env_classificacao_aliquotas_min",
                 "env_classificacao_aliquotas_max"}
    if (config.PROCESSED / "omega_simples.csv").exists():
        esperados |= {"com_cunha_simples", "com_cunha_simples_dois_lados"}
    faltam = esperados - set(nac["cenario_gamma"])
    _check("I17 grade da revisão completa (A4-A7/E2/E4-E8)", not faltam,
           f"faltam: {sorted(faltam)}" if faltam
           else f"{len(esperados)} cenários presentes")

    # I19 mapa jurídico completo (L4/R3): todo dispositivo citado no
    # manuscrito tem linha verificada em metadata/legal_map.csv — o gate
    # falha se uma citação nova entrar sem conferência no texto compilado.
    import subprocess
    import sys as _sys
    raiz = config.V2_ROOT
    saida = subprocess.run(
        [_sys.executable, str(raiz / "tools" / "extrai_dispositivos.py")],
        capture_output=True, text=True, cwd=raiz)
    if saida.returncode != 0:
        _check("I19 legal_map cobre todo dispositivo citado", False,
               f"extrator falhou: {saida.stderr.strip()[:120]}")
    else:
        citados = {tuple(l.split(";")[:2])
                   for l in saida.stdout.strip().splitlines() if ";" in l}
        lm = pd.read_csv(raiz / "metadata" / "legal_map.csv", sep=";")
        mapeados = {(str(r["norma"]), str(r["dispositivo"]))
                    for _, r in lm.iterrows()}
        orfaos = citados - mapeados
        _check("I19 legal_map cobre todo dispositivo citado", not orfaos,
               (f"{len(citados)} citados, todos mapeados" if not orfaos
                else f"sem conferência: {sorted(orfaos)[:4]}"))

    # I18 σ coerente com o perímetro de G (A5): σ_max mistura capital
    # (t_embutida menor) ⇒ σ_max ≤ σ_central = σ_min; todos em (0; 0,12).
    sig = pd.read_csv(config.PROCESSED / "sigma_compras.csv") \
        .set_index("perimetro")["sigma"]
    ok18 = (bool(((sig > 0) & (sig < 0.12)).all())
            and sig["max"] <= sig["central"] + 1e-12
            and abs(sig["central"] - sig["min"]) < 1e-12)
    _check("I18 σ por perímetro (max ≤ central = min; domínio)", ok18,
           ", ".join(f"{k}={v:.4%}" for k, v in sig.items()))

    if FALHAS:
        print(f"\nGATE: {len(FALHAS)} invariante(s) em FALHA: {FALHAS}")
        sys.exit(1)
    print("\nGATE: todos os invariantes PASS")


if __name__ == "__main__":
    main()
