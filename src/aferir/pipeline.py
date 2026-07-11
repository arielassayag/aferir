"""Orquestrador AFERIR: insumos processados → três alíquotas de referência.

Executar: PYTHONPATH=src python3 -m aferir.pipeline
Saídas em data/processed/: aferir_nacional.csv (cenários), aferir_vetor_uf.csv,
MANIFEST_RUN.json. Determinístico (nenhuma fonte de aleatoriedade no central).
"""
from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from . import config, revenue
from .base import AncorasNacionais, base_ordinaria_uf, itens_combustiveis
from .cashback import base_elegivel, cb_base
from .gaps import pi_combinado, policy_gap_por_uf
from .govpurchases import g_por_esfera_uf, populacao_municipal_uf, sigma_iso_carga
from .provenance import MANIFEST, Label, Num
from .rates import EsferaInput, resolve_tri_esfera, vetor_indicativo

BI = 1e9
ZFM_AM = 0.13   # adendo de política ZFM p/ AM (convenção herdada v1; χ_AM STN)

# Itens do piso do cashback (art. 118) DENTRO da base ad valorem: energia
# elétrica, água/esgoto, gás canalizado, telecomunicações. GLP é monofásico
# (fora da base ad valorem — cashback do GLP ocorre no ad rem, declarado).
PADRAO_PISO = (r"ENERGIA ELETRICA|TAXA DE AGUA E ESGOTO|AGUA E ESGOTO|GAS ENCANADO|"
               r"GAS NATURAL ENCANADO|TELEFONE|CELULAR|INTERNET|PACOTE DE TELEFONIA|TV POR ASSINATURA")


def _codigos_piso() -> set[str]:
    m = pd.read_csv(config.INPUTS / "matriz_pof_ibs_v5.csv", dtype={"codigo_pof": str})
    desc = m["descricao_pof"].fillna("").str.upper()
    return set(m.loc[desc.str.contains(PADRAO_PISO, regex=True), "codigo_pof"])


def _escala_bienio(defl: float,
                   janela: tuple[int, ...] | None = None) -> float:
    """C_fam nominal (média janela em R$ 2024) ÷ C_fam nominal 2021 (SIDRA 1846).

    Escala as âncoras de CONSUMO: C_fam e — proxy declarado, pois o SCN
    trimestral não separa ISFLSF — o consumo das ISFLSF. A FBCF tem escala
    própria (_escala_bienio_fbcf)."""
    from .fetch.ibge import consumo_familias_nominal  # série anual R$ mi
    from .govpurchases import media_janela_serie
    from .revenue import _sufixo_janela
    c = consumo_familias_nominal()
    escala = media_janela_serie(c, defl, janela) / float(c[2021])
    MANIFEST.registra("escala_bienio" + _sufixo_janela(janela), Num(
        escala, "média janela nominal ÷ C_fam_2021",
        "IBGE SIDRA 1846 v/585 c11255/93404 (consumo das famílias, nominal)",
        Label.DERIVADO, "razão"))
    return escala


def _escala_bienio_fbcf(defl: float,
                        janela: tuple[int, ...] | None = None) -> float:
    """FBCF nominal (média janela em R$ 2024) ÷ FBCF nominal 2021 (SIDRA 1846).

    Série própria c11255/93406 — a escala C_fam sobreestimava B_FBCF_NC
    (FBCF nominal cresceu menos que o consumo no biênio; achado da banca)."""
    from .fetch.ibge import fbcf_nominal  # série anual R$ mi
    from .govpurchases import media_janela_serie
    from .revenue import _sufixo_janela
    f = fbcf_nominal()
    escala = media_janela_serie(f, defl, janela) / float(f[2021])
    MANIFEST.registra("escala_bienio_fbcf" + _sufixo_janela(janela), Num(
        escala, "média janela nominal ÷ FBCF_2021",
        "IBGE SIDRA 1846 v/585 c11255/93406 (FBCF, nominal)",
        Label.DERIVADO, "razão"))
    return escala


def _ancoras(defl: float,
             janela: tuple[int, ...] | None = None) -> AncorasNacionais:
    tru = pd.read_parquet(config.PROCESSED / "tru_2021_usos.parquet")
    c_fam = float(tru["consumo_familias"].sum()) / 1e3          # R$ bi 2021
    c_isf = float(tru["consumo_isflsf"].sum()) / 1e3
    fbcf = float(tru["fbcf"].sum()) / 1e3

    # FBCF não-corporativa: convenção v1 (METODOLOGIA §3.2, VTI/PIA, m=1,00),
    # vendorada em data/inputs/fbcf_v1_uf.csv:
    # nível = Σ B_FBCF vendorado ÷ (FBCF_TRU × escala_v1=1,406037).
    MANIFEST.registra_arquivo(config.FBCF_V1_CSV)
    v1 = pd.read_csv(config.FBCF_V1_CSV)
    share_nc = float(v1["B_FBCF_Rbi"].sum()) / (fbcf * 1.406037)
    MANIFEST.registra("share_fbcf_nc", Num(
        share_nc, "Σ B_FBCF_v1 ÷ (FBCF_TRU2021 × 1,406037)",
        "convenção v1 (VTI/PIA, art. 200 §4º) vendorada", Label.CONVENCAO, "fração"))
    return AncorasNacionais(
        c_familias_tru=c_fam, c_isflsf_tru=c_isf, fbcf_tru=fbcf,
        share_fbcf_nc=share_nc, escala_biênio=_escala_bienio(defl, janela),
        escala_biênio_fbcf=_escala_bienio_fbcf(defl, janela),
    )


def monta_insumos(lam: float | Mapping[str, float] = 0.0,
                  is_estimado: float | None = None,
                  ancora_federal: str | None = None,
                  g_perimetro: str = "central",
                  natureza36: bool = True,
                  sifim: str = "excluido",
                  fbcf_imob: str = "redutores",
                  escala_base: float = 1.0,
                  cashback_criterio: str = "decis3",
                  matriz: pd.DataFrame | None = None,
                  janela: tuple[int, ...] | None = None) -> dict:
    """Insumos do sistema tri-esfera. lam = encolhimento dos regimes
    favorecidos (trava art. 475 §11): float = uniforme (trava.py);
    dict[classe → λ_c] = por classe de regime (perfis_trava.py, E3 —
    resolvido em gaps.policy_gap_por_uf); λ=0 = matriz legal vigente.
    is_estimado/ancora_federal: defaults CENTRAIS do alvo da União (IS =
    proxy iso-carga; âncora líquida-RTN); is_estimado=0.0, o IS ampliado
    (sens_is_ampliado.csv) e ancora_federal='bruta_rfb' são sensibilidades.

    Alavancas da revisão (defaults = CENTRAL do artigo):
      g_perimetro/natureza36 (A5): perímetro das compras governamentais e a
        chave da natureza 36 (g_perimetros.csv/sigma_compras.csv);
      sifim='excluido' (E7.1): a âncora de consumo NÃO contém o SIFIM
        imputado às famílias (serviço sem operação onerosa, fora do campo);
        'incluido' = convenção anterior, sensibilidade declarada;
      fbcf_imob='redutores' (E7.2): parcela residencial nova da FBCF-NC com
        alíquota reduzida em 50% (LC 214, art. 261); 'padrao' = sensibilidade;
      escala_base (E4): fator multiplicativo sobre B_C e B_ISFLSF (min/máx da
        participação consumo/PIB da década — sens_base_pib.csv);
      cashback_criterio (E6): 'decis3' = decis 1-3 (central; comparável ao
        1º terço do Cenário L da NT SERT) ou 'legal' = renda per capita
        ≤ ½ SM (arts. 112-113, pof_elegiveis_legal_uf.csv);
      matriz (E2): matriz legal alternativa (envelopes de classificação,
        aferir.classificacao) para π e para a fronteira F;
      janela (A6): (2024,) restringe alvos, G e escalas ao exercício 2024.
    """
    defl = revenue.deflator_2025()
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)

    # base por UF e hiato de política (ambos ex-combustíveis, ex-flag F)
    comb = itens_combustiveis(despesa)
    pi = policy_gap_por_uf(despesa[~despesa["codigo_pof"].isin(comb)],
                           lam=lam, matriz=matriz)

    # população por UF: universo municipal SICONFI (inclui Brasília, esfera M)
    entes_pop = populacao_municipal_uf()
    v1 = pd.read_csv(config.FBCF_V1_CSV)
    fbcf_shares = v1.set_index("uf")["B_FBCF_Rbi"]
    fbcf_shares = fbcf_shares / fbcf_shares.sum()

    from .revenue import _sufixo_janela
    tru = pd.read_parquet(config.PROCESSED / "tru_2021_usos.parquet")
    b = base_ordinaria_uf(despesa, entes_pop, fbcf_shares,
                          _ancoras(defl, janela), tru,
                          sifim=sifim, fbcf_imob=fbcf_imob, matriz=matriz,
                          sufixo_chave=_sufixo_janela(janela))
    if escala_base != 1.0:
        # E4: reescala só as âncoras de CONSUMO (B_FBCF_NC tem série própria)
        b[["B_C", "B_ISFLSF"]] *= escala_base
        b["B_ord"] = b[["B_C", "B_ISFLSF", "B_FBCF_NC"]].sum(axis=1)
    b = b.merge(pi[["uf", "pi_p"]], on="uf", validate="1:1")

    # f_low e share do piso (cashback) por UF
    if cashback_criterio == "decis3":
        decis = pd.read_parquet(config.PROCESSED / "pof_decis_uf.parquet")
        tot = decis.groupby("uf")["despesa"].sum()
        low = decis[decis["decil_renda"] <= 3].groupby("uf")["despesa"].sum()
        f_low = (low / tot).rename("f_low")

        piso_cod = _codigos_piso()
        em_campo = despesa[~despesa["codigo_pof"].isin(comb)]
        tot_uf = em_campo.groupby("uf")["despesa_anual_rs"].sum()
        piso_uf = em_campo[em_campo["codigo_pof"].isin(piso_cod)] \
            .groupby("uf")["despesa_anual_rs"].sum()
        share_piso = (piso_uf / tot_uf).rename("share_piso")
        b = b.merge(f_low, left_on="uf", right_index=True) \
             .merge(share_piso, left_on="uf", right_index=True)
    elif cashback_criterio == "legal":
        el = pd.read_csv(config.PROCESSED / "cashback_elegibilidade.csv")
        el = el.rename(columns={"f_low_legal": "f_low",
                                "share_piso_legal": "share_piso"})
        b = b.merge(el[["uf", "f_low", "share_piso"]], on="uf", validate="1:1")
    else:
        raise ValueError(f"cashback_criterio inválido: {cashback_criterio!r}")

    alvos_e = revenue.alvo_estadual_uf(defl, janela)
    alvo_m = revenue.alvo_municipal_uf(defl, janela)
    alvo_u = revenue.alvo_uniao(defl, is_estimado=is_estimado,
                                ancora_federal=ancora_federal, janela=janela)
    g = g_por_esfera_uf(defl, perimetro=g_perimetro, natureza36=natureza36,
                        janela=janela)

    return {"defl": defl, "b": b, "alvos_e": alvos_e, "alvo_m": alvo_m,
            "alvo_u": alvo_u, "g": g,
            "sigma_iso": sigma_iso_carga(g_perimetro)}


def _d_esfera(b: pd.DataFrame, esfera: str, gamma: float, psi: float,
              zfm_uf: str | None = "AM",
              lam: float | Mapping[str, float] = 0.0,
              take_up: float = 1.0,
              gamma_uf: Mapping[str, float] | None = None,
              omega_cunha: float = 0.0) -> pd.Series:
    """D_s por UF: base ordinária líquida de hiatos e cashback (R$ bi).

    lam (trava art. 475 §11): o adendo ZFM é favorecimento de política e
    encolhe na MESMA proporção dos m_i — zfm(λ) = zfm·(1−λ); com lam por
    classe (dict, E3), a pseudo-classe é 'zfm': zfm(λ) = zfm·(1−λ_zfm),
    λ_zfm = lam.get('zfm', 0.0). O cashback é recomputado aqui a cada λ
    (base líquida maior ⇒ dedução maior).
    NOTA: b deve ter sido montado com o MESMO λ (monta_insumos(lam)).

    take_up (E6): fração das famílias elegíveis que recebe a devolução.
    gamma_uf (E5): γ heterogêneo por UF (dict uf → γ_uf, renormalizado para
    preservar o γ médio ponderado pela base — aferir.robustez); None = γ único.
    omega_cunha (A7/E1): fração do consumo em campo suprida por optantes do
    Simples que permanecem no regime (cunha no denominador): o consumo
    líquido de hiatos é multiplicado por (1−ω) antes do cashback.
    """
    lam_zfm = lam.get("zfm", 0.0) if isinstance(lam, Mapping) else lam
    if not 0.0 <= omega_cunha < 1.0:
        raise ValueError("omega_cunha fora de [0; 1)")
    out = {}
    for _, r in b.iterrows():
        g_uf = float(gamma_uf[r["uf"]]) if gamma_uf is not None else gamma
        zfm = ZFM_AM * (1.0 - lam_zfm) if (zfm_uf and r["uf"] == "AM") else 0.0
        pi = pi_combinado(r["pi_p"], g_uf, psi, zfm)
        n_cons = (r["B_C"] + r["B_ISFLSF"]) * (1 - pi) * (1 - omega_cunha)
        n = n_cons + r["B_FBCF_NC"] * (1 - g_uf * (1 - psi))
        bc_liq = r["B_C"] * (1 - pi) * (1 - omega_cunha)
        el = base_elegivel(bc_liq, r["f_low"], r["share_piso"])
        out[r["uf"]] = n - cb_base(esfera, el, take_up)
    return pd.Series(out).sort_index()


def executa(gamma: float = 0.125, psi: float = 0.0, modo: str = "iso_carga",
            lam: float | Mapping[str, float] = 0.0,
            is_estimado: float | None = None,
            ancora_federal: str | None = None,
            g_perimetro: str = "central", natureza36: bool = True,
            sifim: str = "excluido", fbcf_imob: str = "redutores",
            escala_base: float = 1.0, cashback_criterio: str = "decis3",
            take_up: float = 1.0,
            matriz: pd.DataFrame | None = None,
            janela: tuple[int, ...] | None = None,
            gamma_uf: Mapping[str, float] | None = None,
            omega_cunha: float = 0.0,
            deduz_simples_alvos: bool = False) -> dict:
    ins = monta_insumos(lam, is_estimado=is_estimado,
                        ancora_federal=ancora_federal,
                        g_perimetro=g_perimetro, natureza36=natureza36,
                        sifim=sifim, fbcf_imob=fbcf_imob,
                        escala_base=escala_base,
                        cashback_criterio=cashback_criterio,
                        matriz=matriz, janela=janela)
    if deduz_simples_alvos:
        # A7 'dois lados' (espelho do desenho oficial, Regulamento art. 600):
        # numeradores líquidos da parcela do Simples que permanece no regime.
        from .simples import r_simples_por_esfera
        r_simples = r_simples_por_esfera(ins["defl"])
        ins["alvos_e"] = ins["alvos_e"].copy()
        ins["alvos_e"]["alvo_ex_comb"] *= 1.0 - r_simples["share_icms"]
        ins["alvo_m"] = ins["alvo_m"] * (1.0 - r_simples["share_iss"])
    b, g = ins["b"], ins["g"]

    d = {s: _d_esfera(b, s, gamma, psi, lam=lam, take_up=take_up,
                      gamma_uf=gamma_uf, omega_cunha=omega_cunha)
         for s in ("uniao", "estadual", "municipal")}
    alvo_e_uf = ins["alvos_e"]["alvo_ex_comb"].sort_index()
    alvo_m_uf = ins["alvo_m"].sort_index().reindex(d["municipal"].index).fillna(0.0)
    g_e = g["estadual"].sort_index().reindex(d["estadual"].index).fillna(0.0)
    g_m = g["municipal"].sort_index().reindex(d["municipal"].index).fillna(0.0)

    sol = resolve_tri_esfera(
        EsferaInput(ins["alvo_u"]["alvo"], float(d["uniao"].sum()), g["uniao"]),
        EsferaInput(float(alvo_e_uf.sum()), float(d["estadual"].sum()), float(g_e.sum())),
        EsferaInput(float(alvo_m_uf.sum()), float(d["municipal"].sum()), float(g_m.sum())),
        modo=modo, sigma_iso=ins["sigma_iso"] if modo == "iso_carga" else None,
    )

    kw = dict(modo=modo, sigma_iso=ins["sigma_iso"] if modo == "iso_carga" else None)
    vet_e = {u: vetor_indicativo(float(alvo_e_uf[u]), float(d["estadual"][u]),
                                 float(g_e[u]), sol.tau_U + sol.tau_M, **kw)
             for u in alvo_e_uf.index}
    vet_m = {u: vetor_indicativo(float(alvo_m_uf[u]), float(d["municipal"][u]),
                                 float(g_m[u]), sol.tau_U + sol.tau_E, **kw)
             for u in alvo_m_uf.index if alvo_m_uf[u] > 0}
    return {"sol": sol, "vetor_estadual": vet_e, "vetor_municipal": vet_m,
            "insumos": ins, "d": d, "gamma": gamma, "psi": psi, "lam": lam}


def construcao_ancoras(ins: dict) -> pd.DataFrame:
    """Construção (A) âncora-consistente (espelho do v1/Code 16, tri-esfera):

    B* = meta oficial de arrecadação (12,30% do PIB, NT SERT jul/2024) ÷
    alíquota combinada oficial (26,47%) — base REALIZADA implícita nas
    âncoras. τ_s^A = R_s (conceito art. 350 CHEIO, com combustíveis) ÷ B*.
    Federal em duas variantes: âncora legal 2012-2021 e meta PLDO (4,47% PIB).
    Em AMBAS, o numerador federal é LÍQUIDO de IS estimado e IPI residual
    ZFM (art. 353, §1º: o alvo da CBS desconta as receitas que permanecem —
    o 4,47% do PIB da PLDO é projeção de PIS/Cofins+IPI e, portanto, também
    contém as parcelas que o IS e o IPI residual continuarão arrecadando;
    deduzi-las é a mesma correção, declarada). Combustíveis e cashback
    seguem CHEIOS — essa é a diferença conceitual A×B, não o art. 353.
    """
    defl = ins["defl"]
    pib = ins["alvo_u"]["pib_janela"]
    b_star = 0.1230 * pib / 0.2647
    r_e_cheio = float((ins["alvos_e"]["icms_bruto"] + ins["alvos_e"]["fundos"]).sum())
    r_m = float(ins["alvo_m"].sum())
    deducao_353 = ins["alvo_u"]["is_estimado"] + ins["alvo_u"]["ipi_residual"]
    r_u_legal = ins["alvo_u"]["bruto_ancorado"] - deducao_353
    r_u_pldo = 0.0447 * pib - deducao_353
    linhas = []
    for rotulo, r_u in (("ancora_legal_2012_2021", r_u_legal),
                        ("meta_pldo_4_47", r_u_pldo)):
        linhas.append({
            "variante_federal": rotulo,
            "B_star_bi": b_star,
            "tau_CBS_pp": 100 * r_u / b_star,
            "tau_E_pp": 100 * r_e_cheio / b_star,
            "tau_M_pp": 100 * r_m / b_star,
            "soma_pp": 100 * (r_u + r_e_cheio + r_m) / b_star,
            "deducao_art353_bi": deducao_353,
            "formula": ("τ_s = [R_s(art. 350, cheio) − IS_estimado − "
                        "IPI_residual (só União, art. 353 §1º)] ÷ "
                        "[12,30% PIB ÷ 26,47%]"),
            "fonte": ("NT SERT jul/2024 (meta e alíquota; IPI residual p. 4); "
                      "PLDO 2025 via NT (4,47% PIB = projeção PIS/Cofins+IPI); "
                      "IS: proxy iso-carga IPI (LC 214 art. 409 + Anexo XVII)"),
        })
    return pd.DataFrame(linhas)


def _grava_metricas(central: dict, vet: pd.DataFrame,
                    anc: pd.DataFrame, sens: dict | None = None,
                    nac: pd.DataFrame | None = None) -> None:
    """metricas.csv — números de prosa do manuscrito (chave → valor)."""
    ins = central["insumos"]
    b = ins["b"]
    soma_b_pp = central["sol"].soma * 100
    anc_ix = anc.set_index("variante_federal")["soma_pp"]
    conc = pd.read_csv(config.PROCESSED / "iss_concentracao.csv")
    top = conc[(conc["ano"] == 2024) & (conc["serie"] == "share_top")] \
        .set_index("x")["y"]
    rm = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    iss_uf = rm.groupby("uf")["iss_liquida"].sum()
    ref_e_pp = central["sol"].tau_E * 100
    linhas = [
        ("pi_p_nacional", float(MANIFEST.nums["pi_p_nacional"].valor),
         "Σ w_i(1−m_i)/Σ w_i, i∉F, ex-combustíveis", "matriz v5 × POF"),
        ("mediana_tau_E_uf", float(vet["tau_E_uf_pp"].median()),
         "mediana do vetor estadual", "aferir_vetor_uf.csv"),
        ("mediana_tau_M_uf", float(vet["tau_M_uf_pp"].median()),
         "mediana do vetor municipal", "aferir_vetor_uf.csv"),
        ("n_uf_acima_ref_E", float((vet["tau_E_uf_pp"] > ref_e_pp).sum()),
         "nº de UFs com τ_E^uf > referência estadual central",
         "aferir_vetor_uf.csv × aferir_nacional.csv"),
        ("cv_tau_E_uf", float(vet["tau_E_uf_pp"].std(ddof=1)
                              / vet["tau_E_uf_pp"].mean()),
         "desvio-padrão (ddof=1) ÷ média do vetor estadual (27 UFs)",
         "aferir_vetor_uf.csv"),
        ("cv_tau_M_uf", float(vet["tau_M_uf_pp"].std(ddof=1)
                              / vet["tau_M_uf_pp"].mean()),
         "desvio-padrão (ddof=1) ÷ média do vetor municipal",
         "aferir_vetor_uf.csv"),
        ("delta_B_A_pldo_pp",
         float(soma_b_pp - anc_ix["meta_pldo_4_47"]),
         "Σ_B(central) − Σ_A(variante PLDO 4,47% PIB)",
         "aferir_nacional.csv × aferir_ancoras.csv"),
        ("delta_B_A_ancora_pp",
         float(soma_b_pp - anc_ix["ancora_legal_2012_2021"]),
         "Σ_B(central) − Σ_A(âncora legal 2012-2021)",
         "aferir_nacional.csv × aferir_ancoras.csv"),
        ("top1_iss", 100 * float(top[1.0]), "share do maior município no ISS 2024",
         "iss_concentracao.csv"),
        ("top10_iss", 100 * float(top[10.0]), "share top-10", "iss_concentracao.csv"),
        ("top100_iss", 100 * float(top[100.0]), "share top-100", "iss_concentracao.csv"),
        ("share_sp_iss", 100 * float(iss_uf["SP"] / iss_uf.sum()),
         "ISS dos municípios de SP / nacional (janela)", "r_municipal_uf.csv"),
        ("share_sp_base", 100 * float(
            b.set_index("uf")["B_ord"]["SP"] / b["B_ord"].sum()),
         "base de destino de SP / nacional", "base_uf.csv"),
        ("g_municipal_janela", float(ins["g"]["municipal"].sum()),
         "aquisições municipais, média janela (R$ bi 2024)", "g_esferas.csv"),
        ("cobertura_dca_2024", float(rm[rm["ano"] == 2024]["cobertura_pct"].mean()),
         "cobertura média DCA municipal 2024", "r_municipal_uf.csv"),
        ("escala_bienio", float(MANIFEST.nums["escala_bienio"].valor),
         "C_fam janela / C_fam 2021", "SIDRA 1846 c93404"),
        ("escala_bienio_fbcf", float(MANIFEST.nums["escala_bienio_fbcf"].valor),
         "FBCF janela / FBCF 2021", "SIDRA 1846 c93406"),
        ("is_estimado_bi", float(ins["alvo_u"]["is_estimado"]),
         "proxy iso-carga do IS: IPI fumo+bebidas+automóveis, média janela "
         "deflacionada (cota inferior do IS)",
         "XLSX RFB (linhas I.P.I-*); LC 214 art. 409 + Anexo XVII"),
        ("ancora_federal_liquida_pct_pib",
         float(ins["alvo_u"]["ancora_pct_pib"]),
         "âncora art. 353 na convenção líquida-RTN (central, Tema 69)",
         "ancora_uniao.csv (RTN/STN Tabela 2.2)"),
        ("deducao_art353_em_A_pp",
         100 * float(anc["deducao_art353_bi"].iloc[0] / anc["B_star_bi"].iloc[0]),
         "(IS_estimado + IPI_residual) ÷ B* — efeito da correção art. 353 §1º "
         "sobre τ_CBS^A nas DUAS variantes",
         "aferir_ancoras.csv"),
    ]
    if sens:
        for rotulo, chave, desc in (
                ("sens_is_zero", "efeito_is_proxy_pp",
                 "Σ(central) − Σ(IS=0): efeito isolado do proxy iso-carga do "
                 "IS na manchete (negativo = IS reduz τ_CBS)"),
                ("sens_ancora_bruta", "efeito_ancora_liquida_pp",
                 "Σ(central, âncora líquida-RTN) − Σ(âncora bruta-RFB): "
                 "efeito isolado da convenção Tema 69 (sinal empírico)")):
            linhas.append((chave,
                           float(soma_b_pp - sens[rotulo]["sol"].soma * 100),
                           desc, "aferir_nacional.csv (linhas sens_*)"))
    # ponte A×B publicável (auditoria R-nível): Σ_B − Σ_A(comparável) =
    # efeito γ (central − hiato_zero) + variante da âncora federal
    # (rito − comparável) + resíduo conceitual NOMEADO (base realizada ×
    # potencial + numerador cheio/IS na construção A).
    if nac is not None:
        hz = nac[(nac["cenario_gamma"] == "hiato_zero") & (nac["psi"] == 0.0)
                 & (nac["modo_redutor"] == "iso_carga")]["soma_pp"].iloc[0]
        ponte_gamma = float(soma_b_pp - hz)
        ponte_anc = float(anc_ix["ancora_legal_2012_2021"]
                          - anc_ix["meta_pldo_4_47"])
        ponte_total = float(soma_b_pp - anc_ix["meta_pldo_4_47"])
        linhas.append(("ponte_b_a_total_pp", ponte_total,
                       "Σ_B(central) − Σ_A(comparável, meta PLDO)",
                       "aferir_nacional.csv × aferir_ancoras.csv"))
        linhas.append(("ponte_b_a_gamma_pp", ponte_gamma,
                       "efeito do hiato de conformidade: Σ_B(central) − "
                       "Σ_B(γ=0)", "aferir_nacional.csv"))
        linhas.append(("ponte_b_a_ancora_pp", ponte_anc,
                       "efeito da variante federal: Σ_A(rito) − "
                       "Σ_A(comparável)", "aferir_ancoras.csv"))
        linhas.append(("ponte_b_a_residuo_pp",
                       ponte_total - ponte_gamma - ponte_anc,
                       "resíduo conceitual da ponte: base realizada × "
                       "potencial e numerador cheio/IS da construção A",
                       "derivado das três linhas ponte_b_a_*"))
    linhas.append((
        "delta_A_variantes_pp",
        float(anc_ix["ancora_legal_2012_2021"] - anc_ix["meta_pldo_4_47"]),
        "Σ_A(rito, âncora legal 2012-2021) − Σ_A(comparável, meta PLDO)",
        "aferir_ancoras.csv"))
    cov = pd.read_csv(config.PROCESSED / "coverage_siconfi.csv")
    for ano in (2024, 2025):
        c_ano = cov[cov["ano"] == ano].iloc[0]
        linhas.append((
            f"cobertura_econ_{ano}", float(c_ano["cobertura_economica_pct"]),
            "ISS declarado ÷ (declarado + imputado), participação econômica",
            "coverage_siconfi.csv (A6)"))
    if nac is not None:
        sens_g = nac[nac["cenario_gamma"].isin(
            ("central", "sens_g_min", "sens_g_max", "sens_natureza36_off"))
            & (nac["psi"] == 0.0) & (nac["modo_redutor"] == "iso_carga")]
        linhas.append((
            "amplitude_g_municipal_pp",
            float(sens_g["tau_M_pp"].max() - sens_g["tau_M_pp"].min()),
            "máx − mín de τ_M no corredor de perímetros de G (central, "
            "g_min, g_max, natureza 36 desligada)",
            "aferir_nacional.csv (A5)"))
        soma_por = sens_g.set_index("cenario_gamma")["soma_pp"]
        linhas.append((
            "amplitude_g_soma_pp",
            float(soma_por.max() - soma_por.min()),
            "máx − mín da SOMA no corredor de perímetros de G",
            "aferir_nacional.csv (A5)"))
    pd.DataFrame(linhas, columns=["chave", "valor", "formula", "fonte"]) \
        .to_csv(config.PROCESSED / "metricas.csv", index=False)


def _linha_grade(r: dict, rotulo: str, gamma: float, psi: float, modo: str,
                 is_c: str, anc: str, formula: str) -> dict:
    s = r["sol"]
    return {
        "gamma": gamma, "cenario_gamma": rotulo, "psi": psi,
        "modo_redutor": modo, "is_cenario": is_c, "ancora_federal": anc,
        "tau_CBS_pp": s.tau_U * 100,
        "tau_E_pp": s.tau_E * 100, "tau_M_pp": s.tau_M * 100,
        "soma_pp": s.soma * 100, "sigma_pp": s.sigma * 100,
        "formula": formula,
        "fonte": "AFERIR — ver MANIFEST_RUN.json",
    }


def _sens_levers() -> list[tuple[str, dict, str]]:
    """Sensibilidades da revisão (uma alavanca por vez, γ central, ψ=0,
    iso-carga): rótulo, kwargs de executa e fórmula da linha da grade."""
    # E4: fatores direto das funções de robustez (raw SIDRA 1846 — evita
    # dependência do sens_base_pib.csv, que é regravado APÓS o pipeline).
    from .robustez import extremos_decada, s_corrente
    s_cur = s_corrente().valor
    ext = extremos_decada()
    f_min = ext["min"].valor / s_cur
    f_max = ext["max"].valor / s_cur
    isa = pd.read_csv(config.PROCESSED / "sens_is_ampliado.csv")
    is_ampl = float(isa.loc[isa["componente"] == "total_is_ampliado",
                            "valor_rs_bi"].iloc[0])

    return [
        ("sens_g_min", dict(g_perimetro="min"),
         "A5: G no perímetro mínimo (3.3.90.30+39) com σ correspondente"),
        ("sens_g_max", dict(g_perimetro="max"),
         "A5: G no perímetro máximo (custeio ampliado + 4.4.90.51/52), σ recalibrado p/ capital"),
        ("sens_natureza36_off", dict(natureza36=False),
         "A5: perímetro central SEM a natureza 36 (serviços de PF fora do campo)"),
        ("sens_sifim_incluido", dict(sifim="incluido"),
         "E7.1: convenção anterior — SIFIM imputado permanece na âncora de consumo"),
        ("sens_fbcf_sem_redutores", dict(fbcf_imob="padrao"),
         "E7.2: convenção anterior — FBCF residencial nova sem o redutor do art. 261"),
        ("sens_base_pib_min", dict(escala_base=f_min),
         f"E4: consumo/PIB no mínimo da década (fator {f_min:.6f}, sens_base_pib.csv)"),
        ("sens_base_pib_max", dict(escala_base=f_max),
         f"E4: consumo/PIB no máximo da década (fator {f_max:.6f}, sens_base_pib.csv)"),
        ("sens_cashback_legal", dict(cashback_criterio="legal"),
         "E6: elegibilidade legal (renda per capita ≤ ½ SM, arts. 112-113), take-up 100%"),
        ("sens_cashback_legal_takeup80",
         dict(cashback_criterio="legal", take_up=0.8),
         "E6: elegibilidade legal com take-up de 80%"),
        ("sens_janela_2024", dict(janela=(2024,)),
         "A6: alvos, G e escalas restritos ao exercício 2024 (peça ratificada)"),
        ("sens_is_ampliado", dict(is_estimado=is_ampl),
         f"A4: IS ampliado = proxy central + minerais/petróleo e gás quantificados ({is_ampl:.2f} R$ bi; sens_is_ampliado.csv)"),
    ]


def _sens_classificacao(despesa: pd.DataFrame) -> list[tuple[str, dict, str]]:
    """E2: envelopes determinísticos da dupla codificação (matrizes
    contrafactuais — aferir.classificacao)."""
    from .classificacao import matriz_envelope, pi_p_central_nacional
    comb = itens_combustiveis(despesa)
    em_campo = despesa[~despesa["codigo_pof"].isin(comb)]
    pi_ref = pi_p_central_nacional(em_campo)
    return [
        ("env_classificacao_aliquotas_min",
         dict(matriz=matriz_envelope("pi_baixo", pi_ref)),
         "E2: divergências da dupla codificação no menor 1−m (base máxima ⇒ alíquotas mínimas)"),
        ("env_classificacao_aliquotas_max",
         dict(matriz=matriz_envelope("pi_alto", pi_ref)),
         "E2: divergências da dupla codificação no maior 1−m (base mínima ⇒ alíquotas máximas)"),
    ]


def main() -> None:
    linhas, vetores = [], []
    central = None
    # γ=0 (hiato_zero) é diagnóstico: conversão integral da base potencial —
    # cota inferior do corredor de conformidade, reportado na grade/Figura 5.
    # γ=0,20 (estresse, E8): hiato acima do corredor — emergentes/sistema
    # atual podem exceder o teto de 15% (risco assimétrico declarado em 4.5).
    for gamma, rotulo_g in ((0.0, "hiato_zero"), (0.10, "factivel"),
                            (0.125, "central"), (0.15, "conservador"),
                            (0.20, "estresse")):
        for psi in (0.0, 0.30, 1.0):
            for modo in ("iso_carga", "sem_redutor", "redutor_total"):
                if (psi, modo) != (0.0, "iso_carga") and rotulo_g != "central":
                    continue  # grade completa só no γ central
                r = executa(gamma, psi, modo)
                s = r["sol"]
                linhas.append({
                    "gamma": gamma, "cenario_gamma": rotulo_g, "psi": psi,
                    "modo_redutor": modo,
                    "is_cenario": "proxy_ipi_rfb",
                    "ancora_federal": config.ANCORA_FEDERAL_CENTRAL,
                    "tau_CBS_pp": s.tau_U * 100,
                    "tau_E_pp": s.tau_E * 100, "tau_M_pp": s.tau_M * 100,
                    "soma_pp": s.soma * 100, "sigma_pp": s.sigma * 100,
                    "formula": "sistema arts. 350-369 + 472-473 (rates.py)",
                    "fonte": "AFERIR — ver MANIFEST_RUN.json",
                })
                if (gamma, psi, modo) == (0.125, 0.0, "iso_carga"):
                    central = r
    if central is None:
        raise RuntimeError("cenário central ausente")

    # Sensibilidades federais no γ central (ψ=0, iso-carga), uma de cada vez:
    # IS=0 (convenção antiga — sem o proxy iso-carga do IS) e âncora federal
    # bruta-RFB (convenção antiga do Tema 69). Rótulos próprios de
    # cenario_gamma preservam a unicidade dos filtros do cenário central.
    sens = {}
    for rotulo_s, kw, is_c, anc in (
            ("sens_is_zero", {"is_estimado": 0.0}, "zero",
             config.ANCORA_FEDERAL_CENTRAL),
            ("sens_ancora_bruta", {"ancora_federal": "bruta_rfb"},
             "proxy_ipi_rfb", "bruta_rfb")):
        r = executa(0.125, 0.0, "iso_carga", **kw)
        sens[rotulo_s] = r
        linhas.append(_linha_grade(
            r, rotulo_s, 0.125, 0.0, "iso_carga", is_c, anc,
            "sistema arts. 350-369 + 472-473 (rates.py)"))

    # ------------------- sensibilidades da revisão (uma alavanca por vez)
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    for rotulo_s, kw, formula in _sens_levers() + _sens_classificacao(despesa):
        r = executa(0.125, 0.0, "iso_carga", **kw)
        is_c = ("ampliado" if rotulo_s == "sens_is_ampliado"
                else "proxy_ipi_rfb")
        linhas.append(_linha_grade(
            r, rotulo_s, 0.125, 0.0, "iso_carga", is_c,
            config.ANCORA_FEDERAL_CENTRAL,
            f"sistema arts. 350-369 + 472-473 (rates.py); {formula}"))

    # A7/E1: cunha do Simples no denominador (ω de omega_simples.csv) e o
    # espelho 'dois lados' do desenho oficial (numeradores líquidos do
    # Simples, Regulamento do IBS art. 600). Cenários de GRADE — o central
    # permanece sem a cunha, com a direção declarada (cota inferior de B
    # nessa dimensão qualificada no texto).
    omega_csv = config.PROCESSED / "omega_simples.csv"
    if omega_csv.exists():
        from .simples import carrega_omega
        omega = carrega_omega()
        r = executa(0.125, 0.0, "iso_carga", omega_cunha=omega)
        linhas.append(_linha_grade(
            r, "com_cunha_simples", 0.125, 0.0, "iso_carga",
            "proxy_ipi_rfb", config.ANCORA_FEDERAL_CENTRAL,
            ("sistema arts. 350-369 + 472-473 (rates.py); A7/E1: consumo em "
             f"campo × (1−ω), ω = {omega:.4f} (omega_simples.csv: porte "
             "PAC/PAS/PIA × propensão B2C da TRU)")))
        r = executa(0.125, 0.0, "iso_carga", omega_cunha=omega,
                    deduz_simples_alvos=True)
        linhas.append(_linha_grade(
            r, "com_cunha_simples_dois_lados", 0.125, 0.0, "iso_carga",
            "proxy_ipi_rfb", config.ANCORA_FEDERAL_CENTRAL,
            ("sistema arts. 350-369 + 472-473 (rates.py); A7/E1 dois lados: "
             "cunha ω no denominador E numeradores líquidos do Simples "
             "(espelho do Regulamento do IBS, art. 600)")))

    for uf in sorted(central["vetor_estadual"]):
        vetores.append({
            "uf": uf,
            "tau_E_uf_pp": central["vetor_estadual"][uf] * 100,
            "tau_M_uf_pp": central["vetor_municipal"].get(uf, float("nan")) * 100,
        })

    nac = pd.DataFrame(linhas)
    vet = pd.DataFrame(vetores)
    anc = construcao_ancoras(central["insumos"])
    nac.to_csv(config.PROCESSED / "aferir_nacional.csv", index=False)
    # E8: recorte do corredor de conformidade com o estresse γ=20% calculado
    # pelo pipeline (nenhuma extrapolação manual).
    corredor = nac[nac["cenario_gamma"].isin(
        ("factivel", "central", "conservador", "estresse"))
        & (nac["psi"] == 0.0) & (nac["modo_redutor"] == "iso_carga")]
    corredor.to_csv(config.PROCESSED / "sens_gamma_10_12_5_15_20.csv",
                    index=False)
    vet.to_csv(config.PROCESSED / "aferir_vetor_uf.csv", index=False)
    anc.to_csv(config.PROCESSED / "aferir_ancoras.csv", index=False)
    central["insumos"]["b"].to_csv(config.PROCESSED / "base_uf.csv", index=False)
    _grava_metricas(central, vet, anc, sens, nac)
    MANIFEST.grava(config.PROCESSED / "MANIFEST_RUN.json")
    print(anc[["variante_federal", "tau_CBS_pp", "tau_E_pp", "tau_M_pp",
               "soma_pp"]].round(2).to_string(index=False))

    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")].iloc[0]
    print(f"CENTRAL (γ=12,5%, ψ=0, iso-carga): CBS {c.tau_CBS_pp:.2f} + "
          f"E {c.tau_E_pp:.2f} + M {c.tau_M_pp:.2f} = {c.soma_pp:.2f} p.p.")
    print(vet.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
