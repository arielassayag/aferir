"""Tabelas canônicas do artigo (CSV em data/outputs/, consumidas pelo
gerador do manuscrito — zero número digitado no texto).

T1: manchete tri-esfera × comparadores (com colunas obrigatórias de
    comparabilidade — DESIGN §2.5: ano-base, desenho legal, natureza).
T2: vetores indicativos por UF (τ_E^uf, τ_M^uf) + hiato vs referência única.
T3: cenários (γ corredor × ψ × modo do redutor).
T4: decomposição dos alvos (receita de referência por esfera, art. 350).
"""
from __future__ import annotations

import pandas as pd

from . import config


def t1_manchete(nacional: pd.DataFrame) -> pd.DataFrame:
    central = nacional[(nacional.cenario_gamma == "central") & (nacional.psi == 0.0)
                       & (nacional.modo_redutor == "iso_carga")].iloc[0]
    fac = nacional[(nacional.cenario_gamma == "factivel") & (nacional.psi == 0.0)
                   & (nacional.modo_redutor == "iso_carga")].iloc[0]
    con = nacional[(nacional.cenario_gamma == "conservador") & (nacional.psi == 0.0)
                   & (nacional.modo_redutor == "iso_carga")].iloc[0]

    trava = pd.read_csv(config.PROCESSED / "trava_conforme.csv")
    tc = trava[trava["cenario_gamma"] == "central"].iloc[0]
    trava_row = pd.DataFrame([{
        "fonte": "AFERIR, trava-conforme: construção B com o PLP redutor "
                 "do art. 475, §11",
        "ano_publicacao": 2026,
        "total_pp": tc.soma_pp, "cbs_pp": tc.tau_CBS_pp,
        "ibs_pp": tc.tau_E_pp + tc.tau_M_pp,
        "ibs_estadual_pp": tc.tau_E_pp, "ibs_municipal_pp": tc.tau_M_pp,
        "ano_base_dados": "2024-2025 (âncora União 2012-2021)",
        "desenho_legal": "LC 214 + LC 227, com o PLP redutor do §11 (λ)",
        "natureza": "estimado condicional (dados abertos)",
        "conceito_nota": ("hipóteses idênticas às da construção B central, "
                          "mais o mecanismo do §11: regimes favorecidos "
                          f"encolhidos em λ = {tc['lambda']:.3f} (custo R$ "
                          f"{tc.custo_beneficios_rs_bi:.0f} bi/ano) até "
                          "Σ = 26,5% exatos; é o ajuste que o art. 475, "
                          "§11, obriga"),
        "url": "espelho anônimo (Anexo D)",
    }])

    este = pd.DataFrame([{
        "fonte": "AFERIR, construção B: identidade sobre dados abertos "
                 "(cota superior), cenário central",
        "ano_publicacao": 2026,
        "total_pp": central.soma_pp, "cbs_pp": central.tau_CBS_pp,
        "ibs_pp": central.tau_E_pp + central.tau_M_pp,
        "ibs_estadual_pp": central.tau_E_pp, "ibs_municipal_pp": central.tau_M_pp,
        "ano_base_dados": "2024-2025 (âncora União 2012-2021)",
        "desenho_legal": "LC 214 + LC 227 (arts. 349-369, 472-473)",
        "natureza": "estimado (dados abertos)",
        "conceito_nota": ("base POTENCIAL de destino TRU 2021/POF (consumo "
                          "das famílias + ISFLSF + FBCF não corporativa); "
                          f"conformidade γ = 12,5%, corredor [{fac.soma_pp:.2f}; "
                          f"{con.soma_pp:.2f}]; sem split payment (ψ = 0); "
                          "redutor de compras públicas por carga equivalente "
                          f"(σ̂ = {central.sigma_pp:.2f}%, TRU 2021); "
                          "pós-cashback art. 118; "
                          "ex-combustíveis monofásicos (simétrico); âncora "
                          "federal líquida-RTN 2012-2021 (Tema 69); IS por "
                          "aproximação de carga do IPI (cota inferior do IS, "
                          "logo CBS cota superior); sem cunha do Simples "
                          "(soma em cota inferior nessa dimensão)"),
        "url": "espelho anônimo (Anexo D)",
    }])
    anc = pd.read_csv(config.PROCESSED / "aferir_ancoras.csv")
    a_rows = []
    for _, r in anc.iterrows():
        legal = "legal" in r.variante_federal
        nota_fed = ("parcela federal reposta pela média histórica 2012-2021 "
                    "que o art. 353 determina (embute a carga do IPI e o "
                    "regime anterior ao Tema 69)" if legal else
                    "parcela federal ancorada na projeção corrente do PLDO "
                    "(4,47% do PIB)")
        a_rows.append({
            "fonte": ("AFERIR, construção A, rito (âncora legal do "
                      "art. 353)" if legal else
                      "AFERIR, construção A, comparável às oficiais "
                      "(meta do PLDO)"),
            "ano_publicacao": 2026,
            "total_pp": r.soma_pp, "cbs_pp": r.tau_CBS_pp,
            "ibs_pp": r.tau_E_pp + r.tau_M_pp,
            "ibs_estadual_pp": r.tau_E_pp, "ibs_municipal_pp": r.tau_M_pp,
            "ano_base_dados": "2024-2025",
            "desenho_legal": "LC 214 + LC 227 (receitas art. 350 cheias)",
            "natureza": "estimado (base implícita nas âncoras oficiais)",
            "conceito_nota": ("mesmos numeradores do art. 350 sobre a base "
                              "EFETIVA implícita nas âncoras oficiais "
                              "(B* = 12,30% do PIB ÷ 26,47%, NT SERT "
                              "jul/2024, base já líquida de conformidade, "
                              "favorecimentos e cashback); com combustíveis; "
                              "numerador federal líquido de IS estimado e "
                              f"IPI residual (art. 353, §1º); {nota_fed}"),
            "url": "espelho anônimo (Anexo D)",
        })
    comp = pd.read_csv(config.INPUTS / "comparadores.csv")
    return pd.concat([trava_row, este, pd.DataFrame(a_rows), comp],
                     ignore_index=True)


def t4_distribuicao() -> pd.DataFrame:
    """T4: distribuição legal 2033 por UF×esfera + métricas em metricas_dist.csv."""
    d = pd.read_csv(config.PROCESSED / "distribuicao_2033.csv")
    e = d[d.esfera == "E"]
    m = d[d.esfera == "M"]
    metricas = [
        ("suf_mediana", float(d["suficiencia_pct"].median())),
        ("suf_mediana_E", float(e["suficiencia_pct"].median())),
        ("suf_mediana_M", float(m["suficiencia_pct"].median())),
        ("suf_min_E", float(e["suficiencia_pct"].min())),
        ("suf_max_E", float(e["suficiencia_pct"].max())),
        ("suf_min_M", float(m["suficiencia_pct"].min())),
        ("n_abaixo_905", int((d["suficiencia_pct"] < 90.5).sum())),
        ("n_abaixo_100", int((d["suficiencia_pct"] < 100.0).sum())),
        ("n_agregados", int(len(d))),
        ("suf_am_e", float(e.loc[e.uf == "AM", "suficiencia_pct"].iloc[0])),
    ]
    pd.DataFrame(metricas, columns=["chave", "valor"]).assign(
        formula="derivado de distribuicao_2033.csv",
        fonte="aferir.distribuicao (ADCT 131-132; LC 227 arts. 109-117, 128)",
    ).to_csv(config.PROCESSED / "metricas_dist.csv", index=False)
    return d


def t2_vetores(vetor_uf: pd.DataFrame, nacional: pd.DataFrame) -> pd.DataFrame:
    central = nacional[(nacional.cenario_gamma == "central") & (nacional.psi == 0.0)
                       & (nacional.modo_redutor == "iso_carga")].iloc[0]
    v = vetor_uf.copy()
    v["hiato_E_pp"] = v["tau_E_uf_pp"] - central.tau_E_pp
    v["hiato_M_pp"] = v["tau_M_uf_pp"] - central.tau_M_pp
    v["soma_indicativa_pp"] = (central.tau_CBS_pp + v["tau_E_uf_pp"]
                               + v["tau_M_uf_pp"].fillna(central.tau_M_pp))
    # piso da alíquota própria (art. 371 + Anexo XVI): 2033 = 90,5% da
    # referência de cada esfera — vinculante quando a necessidade indicativa
    # fica ABAIXO. Vetor EXEQUÍVEL = censura inferior no piso:
    # τ̃ = max(τ_indicativo, 0,905·τ_ref) — seção 3.4 do artigo.
    v["piso_2033_E_pp"] = 0.905 * central.tau_E_pp
    v["piso_2033_M_pp"] = 0.905 * central.tau_M_pp
    v["piso_vinculante_E"] = v["tau_E_uf_pp"] < v["piso_2033_E_pp"]
    v["piso_vinculante_M"] = v["tau_M_uf_pp"] < v["piso_2033_M_pp"]
    v["tau_E_exequivel_pp"] = v[["tau_E_uf_pp", "piso_2033_E_pp"]].max(axis=1)
    v["tau_M_exequivel_pp"] = v[["tau_M_uf_pp", "piso_2033_M_pp"]].max(axis=1)
    return v


def metricas_piso(v: pd.DataFrame, nacional: pd.DataFrame) -> pd.DataFrame:
    """Métricas do piso do art. 371 (2033 = 90,5% da referência da esfera),
    sob a referência central da construção B e sob a trava-conforme —
    consumidas por placeholder no texto (metricas_piso.csv)."""
    central = nacional[(nacional.cenario_gamma == "central") & (nacional.psi == 0.0)
                       & (nacional.modo_redutor == "iso_carga")].iloc[0]
    trava = pd.read_csv(config.PROCESSED / "trava_conforme.csv")
    tc = trava[trava["cenario_gamma"] == "central"].iloc[0]
    fonte = ("LC 214/2025, art. 371 + Anexo XVI; vetores: aferir_vetor_uf.csv; "
             "referências: aferir_nacional.csv / trava_conforme.csv")
    piso_e, piso_m = 0.905 * central.tau_E_pp, 0.905 * central.tau_M_pp
    piso_e_tc, piso_m_tc = 0.905 * tc.tau_E_pp, 0.905 * tc.tau_M_pp
    ufs_e = ", ".join(sorted(v.loc[v["piso_vinculante_E"], "uf"]))
    met = [
        ("piso_E_pp", piso_e, "0,905 × τ_E de referência (central B)"),
        ("piso_M_pp", piso_m, "0,905 × τ_M de referência (central B)"),
        ("n_piso_vinc_E", float(v["piso_vinculante_E"].sum()),
         f"nº de UFs com τ_E indicativo < piso (central B): {ufs_e}"),
        ("n_piso_vinc_M", float(v["piso_vinculante_M"].sum()),
         "nº de agregados municipais com τ_M indicativo < piso (central B)"),
        ("piso_E_trava_pp", piso_e_tc, "0,905 × τ_E trava-conforme"),
        ("piso_M_trava_pp", piso_m_tc, "0,905 × τ_M trava-conforme"),
        ("n_piso_vinc_E_trava", float((v["tau_E_uf_pp"] < piso_e_tc).sum()),
         "nº de UFs com τ_E indicativo < piso sob a referência trava-conforme"),
        ("n_piso_vinc_M_trava", float((v["tau_M_uf_pp"] < piso_m_tc).sum()),
         "nº de agregados municipais < piso sob a referência trava-conforme"),
    ]
    out = pd.DataFrame(met, columns=["chave", "valor", "formula"]).assign(fonte=fonte)
    out.to_csv(config.PROCESSED / "metricas_piso.csv", index=False)
    return out


def t5_quadro_vies(nac: pd.DataFrame) -> pd.DataFrame:
    """T5 (§8.4 do plano de revisão): Quadro de Direções de Viés — cada
    convenção com lado afetado, sinal MEDIDO sobre a alíquota (Δsoma da
    grade, p.p.) e status. Anexo C."""
    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")].iloc[0]

    def delta(rotulo: str) -> float | None:
        sel = nac[nac["cenario_gamma"] == rotulo]
        if sel.empty:
            return None
        return float(sel["soma_pp"].iloc[0] - c.soma_pp)

    def fmt(rotulo: str, inverte: bool = False) -> tuple[str, str]:
        """(sinal, magnitude) do efeito da CONVENÇÃO ROTULADA sobre a
        alíquota: inverte=False quando o rótulo descreve o próprio cenário
        sens_* (Δ = cenário − central); inverte=True quando o rótulo
        descreve a convenção MANTIDA no central (Δ = central − cenário)."""
        d = delta(rotulo)
        if d is None:
            return "pendente", "pendente (cenário ausente da grade)"
        d_om = d if not inverte else -d
        sinal = "para baixo" if d_om < 0 else "para cima"
        return sinal, f"{abs(d_om):.2f}".replace(".", ",") + " p.p. na soma (medida)"

    linhas = []

    def add(convencao, afeta, rotulo_ou_sinal, status, inverte=False,
            magnitude=None):
        if magnitude is None:
            sinal, mag = fmt(rotulo_ou_sinal, inverte)
        else:
            sinal, mag = rotulo_ou_sinal, magnitude
        linhas.append({"convencao": convencao, "afeta": afeta,
                       "sinal_na_aliquota": sinal, "magnitude": mag,
                       "status": status})

    add("cunha do Simples omitida (optantes no denominador)", "denominador",
        "com_cunha_simples", "cenário na grade; central declarado cota "
        "inferior nessa dimensão", inverte=True)
    add("SIFIM imputado na âncora de consumo", "denominador",
        "sens_sifim_incluido", "corrigido no central (E7.1); convenção "
        "anterior vira sensibilidade", inverte=False)
    add("FBCF residencial sem o redutor do art. 261", "denominador",
        "sens_fbcf_sem_redutores", "corrigido no central (E7.2)",
        inverte=False)
    add("elegibilidade legal do cashback (½ SM per capita) em vez dos "
        "decis 1-3", "denominador líquido", "sens_cashback_legal",
        "cenário na grade; central = decis 1-3 (comparável ao 1º terço da "
        "NT SERT)", inverte=False)
    add("G no perímetro mínimo (sem TIC/locações/capital)",
        "módulo de compras", "sens_g_min", "corredor calculado (A5)",
        inverte=False)
    add("G no perímetro máximo (com obras e equipamentos)",
        "módulo de compras", "sens_g_max", "corredor calculado (A5)",
        inverte=False)
    add("natureza 36 integralmente dentro do campo", "módulo de compras",
        "sens_natureza36_off", "chave calculada (A5)", inverte=True)
    add("IS restrito ao proxy iso-carga do IPI", "numerador CBS",
        "sens_is_ampliado", "cenário ampliado quantificado (A4); apostas "
        "excluídas com justificativa dupla: sem teto legal ancorável (o "
        "art. 422, § 2º, alcança só bens minerais extraídos; demais "
        "alíquotas em lei ordinária) e GGR oficial da SPA/MF atrás de "
        "login gov.br (diligência F13); embarcações e aeronaves seguem "
        "não quantificadas (art. 421)", inverte=True)
    add("conformidade no teto do corredor e além (γ=20%)", "base líquida",
        "estresse", "estresse calculado pelo pipeline (E8)", inverte=False)
    add("classificação POF×LC 214 (desacordo dos codificadores)",
        "denominador", "para ambos os lados",
        "envelopes e bootstrap conjunto calculados (E2)",
        magnitude=(f"{(delta('env_classificacao_aliquotas_min') or 0):+.2f}".replace(".", ",")
                   + " a "
                   + f"{(delta('env_classificacao_aliquotas_max') or 0):+.2f}".replace(".", ",")
                   + " p.p. na soma (envelopes)"))
    add("participação consumo/PIB corrente projetada para 2033",
        "denominador", "para ambos os lados",
        "extremos da década calculados (E4)",
        magnitude=(f"{(delta('sens_base_pib_max') or 0):+.2f}".replace(".", ",")
                   + " a "
                   + f"{(delta('sens_base_pib_min') or 0):+.2f}".replace(".", ",")
                   + " p.p. na soma (mín/máx da década)"))
    add("razão IOF-Seguros constante", "numerador CBS", "incerto",
        "fronteira administrativa declarada, diligência registrada (A8); sensibilidade ±1/4",
        magnitude="±1/4 da razão constante (0,0882 do IOF total)")
    add("janela 2024-2025 com 2025 não ratificado", "alvos e G",
        "sens_janela_2024", "delta só-2024 calculado (A6)", inverte=True)
    out = pd.DataFrame(linhas)
    out["formula"] = ("Δsoma = soma_pp(cenário) − soma_pp(central) na grade; "
                      "sinal reportado = efeito da OMISSÃO da correção")
    out["fonte"] = "aferir_nacional.csv (grade da revisão)"
    return out


def main() -> None:
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    vet = pd.read_csv(config.PROCESSED / "aferir_vetor_uf.csv")
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    t1_manchete(nac).to_csv(config.OUTPUTS / "t1_manchete.csv", index=False)
    t2 = t2_vetores(vet, nac)
    t2.to_csv(config.OUTPUTS / "t2_vetores_uf.csv", index=False)
    metricas_piso(t2, nac)
    nac.to_csv(config.OUTPUTS / "t3_cenarios.csv", index=False)
    t4_distribuicao().to_csv(config.OUTPUTS / "t4_distribuicao.csv", index=False)
    t5 = t5_quadro_vies(nac)
    t5.to_csv(config.OUTPUTS / "t5_quadro_vies.csv", index=False)
    t5.to_csv(config.PROCESSED / "quadro_direcoes_vies.csv", index=False)
    print("tabelas T1-T5 gravadas em", config.OUTPUTS)


if __name__ == "__main__":
    main()
