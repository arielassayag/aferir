"""Cashback (LC 214, arts. 112-120) — redutor de base por esfera.

Piso legal (art. 118): CBS 100% e IBS 20% em GLP-13kg, energia elétrica,
água/esgoto, gás canalizado e telecomunicações; 20%/20% nas demais aquisições.
Elegibilidade: famílias CadÚnico com renda ≤ ½ SM per capita — proxy de dados
abertos: decis 1-3 da POF (convenção herdada do v1, f_low ≈ 9,5-10,4% da
despesa; por UF varia de ~3% no DF a ~35% no MA).

Forma fechada: a devolução é proporcional ao imposto pago pelos elegíveis,
logo entra como dedução de base:  cb_base_s = Σ_g pct_s,g · L_g
onde L_g = base líquida (pós-hiatos) consumida pelos ELEGÍVEIS no grupo g
(g ∈ {piso, demais}).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class BaseElegivel:
    """Base líquida (pós π e γ_eff) consumida por famílias elegíveis, R$ bi."""

    piso: float     # itens do art. 118 §-piso (GLP, energia, água/esgoto, gás, telecom)
    demais: float


def cb_base(esfera: str, elegivel: BaseElegivel, take_up: float = 1.0) -> float:
    """Dedução de base da esfera pelo cashback (R$ bi).

    take_up: fração das famílias elegíveis que efetivamente recebe a
    devolução (multiplicativo na dedução). Default 1,0 = take-up integral —
    convenção do cálculo oficial (CadÚnico com concessão automática, LC 214,
    art. 114); take_up=0,8 é a sensibilidade declarada (E6).
    """
    if not 0.0 <= take_up <= 1.0:
        raise ValueError("take_up fora de [0; 1]")
    if esfera == "uniao":
        return take_up * (config.CASHBACK_CBS_PISO * elegivel.piso
                          + config.CASHBACK_CBS_DEMAIS * elegivel.demais)
    if esfera in ("estadual", "municipal"):
        return take_up * config.CASHBACK_IBS_UNIFORME * (elegivel.piso
                                                         + elegivel.demais)
    raise ValueError(f"esfera desconhecida: {esfera}")


def base_elegivel(
    b_c_liquida: float,
    f_low: float,
    share_piso: float,
    uplift_piso_low: float = 1.0,
) -> BaseElegivel:
    """Constrói a base elegível a partir de agregados POF.

    b_c_liquida: consumo das famílias líquido de π e γ_eff (R$ bi);
    f_low: share dos decis 1-3 na despesa;
    share_piso: share dos itens do piso na despesa total;
    uplift_piso_low: razão entre o share do piso na cesta dos decis 1-3 e o
      share na cesta média (≥1 — pobres gastam proporcionalmente mais em
      utilities; default 1,0 = convenção conservadora declarada, sensibilidade
      quando o corte item×decil da POF estiver disponível).
    """
    if not 0 <= f_low <= 1 or not 0 <= share_piso <= 1:
        raise ValueError("parâmetros fora do domínio")
    piso = b_c_liquida * f_low * share_piso * uplift_piso_low
    total_low = b_c_liquida * f_low
    return BaseElegivel(piso=min(piso, total_low), demais=max(total_low - piso, 0.0))


# ----------------------------------------------------- QA de custo (E6)
# ESPELHO de pipeline.ZFM_AM (pipeline.py é do orquestrador — não importar;
# manter sincronizado): adendo de política ZFM para o AM.
ZFM_AM_ESPELHO = 0.13

# Confronto oficial: NENHUMA fonte aberta publica o custo do cashback em R$
# (lacuna antecipada — superdocumento 10.3.4). O que existe: NT SERT jul/2024,
# Tabela 2, Cenário L = efeito de +0,36/0,39/0,41 p.p. (mín/média/máx) na
# alíquota-padrão, calculado sob o PLP 68/2024 original (CBS 50% em energia/
# água/esgoto); NT SERT ago/2024, Cenário J = +0,03/0,04/0,04 p.p. pela
# majoração a 100% (redação final da LC 214). Custo IMPLÍCITO ≈ Δτ × B*
# (base realizada implícita nas âncoras, aferir_ancoras.csv).
NT_SERT_CENARIO_L_PP = {"min": 0.36, "media": 0.39, "max": 0.41}
NT_SERT_CENARIO_J_PP = 0.04          # média — majoração 50%→100% CBS (LC 214)


def qa_custo_cashback(grava: bool = True):
    """qa_cashback_custo.csv — dedução de cashback e custo em R$ bi (janela)
    sob três variantes de elegibilidade/take-up, reproduzindo a chamada do
    pipeline central (γ=12,5%, ψ=0) SEM importá-lo: para cada UF de
    base_uf.csv, bc_liq = B_C×(1−π_combinado) e cb_base por esfera; troca-se
    apenas f_low (decis-3 → legal) e take_up. Custo em R$ = Σ_s τ_s^central ×
    CB_s (alíquotas centrais FIXAS — aproximação de 1ª ordem declarada; o
    efeito endógeno nas alíquotas é papel do pipeline, não deste QA).
    """
    import pandas as pd

    from .gaps import pi_combinado

    b = pd.read_csv(config.PROCESSED / "base_uf.csv")
    legal = pd.read_csv(config.PROCESSED / "pof_elegiveis_legal_uf.csv")
    b = b.merge(legal[["uf", "f_low_legal"]], on="uf", validate="1:1")

    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")].iloc[0]
    tau = {"uniao": c.tau_CBS_pp / 100, "estadual": c.tau_E_pp / 100,
           "municipal": c.tau_M_pp / 100}
    anc = pd.read_csv(config.PROCESSED / "aferir_ancoras.csv")
    b_star = float(anc["B_star_bi"].iloc[0])

    gamma = config.GAP_CONFORMIDADE["central"]

    def _deducao(col_f_low: str, take_up: float) -> dict[str, float]:
        cb = {s: 0.0 for s in config.ESFERAS}
        for _, r in b.iterrows():
            zfm = ZFM_AM_ESPELHO if r["uf"] == "AM" else 0.0
            pi = pi_combinado(r["pi_p"], gamma, 0.0, zfm)
            el = base_elegivel(r["B_C"] * (1 - pi), r[col_f_low],
                               r["share_piso"])
            for s in config.ESFERAS:
                cb[s] += cb_base(s, el, take_up)
        return cb

    custo_oficial = (NT_SERT_CENARIO_L_PP["media"]
                     + NT_SERT_CENARIO_J_PP) / 100 * b_star
    formula = ("CB_s = Σ_uf cb_base(s, base_elegivel(B_C×(1−π(π_p, γ=0,125, "
               "ψ=0, zfm_AM=0,13)), f_low, share_piso), take_up); custo = "
               "Σ_s τ_s^central × CB_s (τ fixos — 1ª ordem)")
    fonte = ("base_uf.csv + pof_elegiveis_legal_uf.csv + aferir_nacional.csv "
             "(central); LC 214, arts. 112-118")
    linhas = []
    for variante, col, tu in (("decis3_takeup_100", "f_low", 1.0),
                              ("legal_takeup_100", "f_low_legal", 1.0),
                              ("legal_takeup_80", "f_low_legal", 0.8)):
        cb = _deducao(col, tu)
        custo = sum(tau[s] * cb[s] for s in config.ESFERAS)
        linhas.append({
            "variante": variante, "take_up": tu,
            "cb_uniao_bi": cb["uniao"], "cb_estadual_bi": cb["estadual"],
            "cb_municipal_bi": cb["municipal"],
            "cb_total_bi": sum(cb.values()), "custo_rs_bi": custo,
            "desvio_pct_vs_oficial": 100 * (custo / custo_oficial - 1),
            "formula": formula, "fonte": fonte,
        })
    linhas.append({
        "variante": "oficial_nt_sert_implicito", "take_up": 1.0,
        "cb_uniao_bi": float("nan"), "cb_estadual_bi": float("nan"),
        "cb_municipal_bi": float("nan"), "cb_total_bi": float("nan"),
        "custo_rs_bi": custo_oficial, "desvio_pct_vs_oficial": 0.0,
        "formula": ("custo implícito = (0,39 + 0,04)/100 × B*; NENHUMA fonte "
                    "aberta publica custo do cashback em R$ — lacuna "
                    "declarada (PLDO 2027 Anexo IV.2: menção qualitativa)"),
        "fonte": ("NT SERT jul/2024, Tab. 2, Cenário L (elegibilidade = 1º "
                  "terço da distribuição de renda per capita; PLP 68 "
                  "original) + NT SERT ago/2024, Cenário J (majoração CBS "
                  "100% energia/água/esgoto); B* = aferir_ancoras.csv"),
    })
    qa = pd.DataFrame(linhas)
    if grava:
        qa.to_csv(config.PROCESSED / "qa_cashback_custo.csv", index=False)
    return qa


if __name__ == "__main__":
    qa = qa_custo_cashback(grava=True)
    print(qa[["variante", "take_up", "cb_total_bi", "custo_rs_bi",
              "desvio_pct_vs_oficial"]].round(2).to_string(index=False))
