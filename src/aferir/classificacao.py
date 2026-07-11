"""Erro de classificação POF×LC 214 — dupla codificação e envelopes (E2).

A matriz legal (data/inputs/matriz_pof_ibs_v5.csv, 13.474 itens) é o coração
do hiato de política π^p. A concordância entre codificadores independentes é
apenas moderada (κ_m = 0,637), logo o intervalo do estudo não pode propagar
só a amostragem da POF: este módulo mede a despesa em desacordo, constrói
envelopes determinísticos de π^p e fornece os insumos do sorteio de
classificação do bootstrap conjunto (aferir.uncertainty).

DESENHO AMOSTRAL da dupla codificação (documentado do v1, script
13b_dupla_codificacao_kappa.py e design 2026-07-05, Fase D):
  - amostra ESTRATIFICADA de 470 itens da matriz final V5, estratos m×flag,
    alocação proporcional com mínimo de 12 itens por estrato, seed = 42;
  - avaliador 2 = modelo de linguagem (LLM) CEGO ao gabarito, instruído
    apenas com o texto legal (LC 214/2025, red. LC 227/2026, e anexos) e o
    manual de codificação — julgamento independente, registrado em
    2026-07-06 (colunas avaliador e data do artefato);
  - métricas medidas no v1: κ_m = 0,637 (Cohen ponderado linear, 448 itens
    em campo por ambos) e κ_F = 0,924 (F vs não-F, 470 itens);
  - LIMITAÇÃO DECLARADA: o avaliador 2 não é humano; a dupla codificação
    humana permanece como refinamento futuro. O valor do exercício é a
    independência do julgamento (cegueira), não a espécie do julgador.

Artefato vendorado BYTE A BYTE do v1 (fecha a lacuna de replicabilidade do
κ citado no manuscrito): data/inputs/dupla_codificacao_2026_07.csv
(sha256 pinado em tests/test_classificacao.py).

AMOSTRA DIRIGIDA PELO PESO (R6 da banca, 2026-07-13): a amostra
estratificada cobre só ~10,8% da despesa da base de π^p (cota inferior
declarada). Complemento determinístico: os itens da base de π^p (flag≠F,
m válido, ex-combustíveis monofásicos) foram ordenados pela despesa
nacional decrescente (desempate por codigo_pof) até acumular 50% do
denominador de π^p (53 itens); os 46 ausentes da amostra original foram
RECODIFICADOS ÀS CEGAS pelo MESMO protocolo do avaliador 2 (LLM cego ao
gabarito, instruído apenas com codigo_pof + descricao_pof + o quadro
legal da LC 214/2025) e vendorados em
data/inputs/dupla_codificacao_dirigida_2026_07.csv (sha256 pinado).
A amostra COMBINADA (original ∪ dirigida, dedup com a original
prevalecendo) passa a alimentar divergências, envelopes e o sorteio de
classificação do bootstrap; κ é reportado por amostra e combinado
(kappas()). O resíduo não amostrado fica DELIMITADO à cauda de itens de
baixo peso (< 47% da despesa da base).

ENVELOPES DETERMINÍSTICOS (duas matrizes-contrafactuais; só itens
divergentes mudam):
  - itens divergentes EM CAMPO por ambos: m := min(m1, m2) num envelope e
    m := max(m1, m2) no outro (menor m ⇒ maior 1−m ⇒ π^p MAIOR ⇒ base
    líquida menor ⇒ alíquotas MAIORES);
  - divergência F×não-F (regra do limiar, CONVENÇÃO declarada): a leitura
    em campo eleva π^p sse (1−m_campo) > π^p central nacional; o envelope
    que busca π^p ALTO adota a leitura que eleva π^p e o envelope de π^p
    BAIXO adota a oposta, nas DUAS direções (F na matriz × F no avaliador 2).
Os envelopes são ROTULADOS PELO RESULTADO medido nas alíquotas
(envelope_aliquotas_min = menor π^p; envelope_aliquotas_max = maior π^p),
não pela regra geradora.

Saídas: data/processed/classificacao_divergencias.csv
        data/processed/envelope_classificacao.csv

Executar: PYTHONPATH=src python3 -m aferir.classificacao
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .base import itens_combustiveis
from .gaps import carrega_matriz, policy_gap_por_uf
from .provenance import MANIFEST, Label, Num

DUPLA_CSV = config.INPUTS / "dupla_codificacao_2026_07.csv"
DUPLA_DIRIGIDA_CSV = config.INPUTS / "dupla_codificacao_dirigida_2026_07.csv"
DIVERGENCIAS_CSV = config.PROCESSED / "classificacao_divergencias.csv"
ENVELOPE_CSV = config.PROCESSED / "envelope_classificacao.csv"

NIVEIS_M = (0.0, 0.30, 0.40, 0.60, 0.70, 1.0)   # níveis canônicos de m

_FONTE_DUPLA = ("data/inputs/dupla_codificacao_2026_07.csv (vendorado do v1; "
                "amostra estratificada m×flag de 470 itens, mínimo 12/estrato, "
                "seed 42; avaliador 2 = LLM cego ao gabarito, 2026-07-06) + "
                "data/inputs/dupla_codificacao_dirigida_2026_07.csv (R6: "
                "46 itens do top-50% da despesa da base de π^p ausentes da "
                "amostra original, recodificados às cegas pelo mesmo "
                "protocolo, 2026-07-13) × data/inputs/matriz_pof_ibs_v5.csv")


def carrega_dupla_codificacao() -> pd.DataFrame:
    """Amostra ESTRATIFICADA original (470 itens, vendorada do v1):
    codigo_pof -> (m_av2, flag_av2, disp.)."""
    a = pd.read_csv(DUPLA_CSV, dtype={"codigo_pof": str})
    esperadas = ["codigo_pof", "m_avaliador2", "flag_avaliador2",
                 "dispositivo_avaliador2", "avaliador", "data"]
    if list(a.columns) != esperadas:
        raise ValueError("colunas inesperadas na dupla codificação")
    if a["codigo_pof"].duplicated().any():
        raise ValueError("dupla codificação com codigo_pof duplicado")
    if not a["flag_avaliador2"].isin(["A", "B", "C", "F"]).all():
        raise ValueError("flag do avaliador 2 fora do alfabeto A/B/C/F")
    return a


def carrega_dupla_codificacao_dirigida() -> pd.DataFrame:
    """Amostra DIRIGIDA PELO PESO (R6): itens do top-50% da despesa da base
    de π^p ausentes da amostra original, recodificados às cegas (protocolo
    idêntico ao do avaliador 2 original; ver docstring do módulo)."""
    a = pd.read_csv(DUPLA_DIRIGIDA_CSV, dtype={"codigo_pof": str})
    esperadas = ["codigo_pof", "m_avaliador2", "flag_avaliador2",
                 "dispositivo_avaliador2", "avaliador", "data",
                 "metodo", "formula", "fonte"]
    if list(a.columns) != esperadas:
        raise ValueError("colunas inesperadas na dupla codificação dirigida")
    if a["codigo_pof"].duplicated().any():
        raise ValueError("dupla codificação dirigida com codigo_pof duplicado")
    if not a["flag_avaliador2"].isin(["A", "B", "C", "F"]).all():
        raise ValueError("flag do avaliador 2 fora do alfabeto A/B/C/F")
    if not a["metodo"].eq("dirigida_peso_top50").all():
        raise ValueError("metodo inesperado na amostra dirigida")
    if not a["m_avaliador2"].isin(list(NIVEIS_M)).all():
        raise ValueError("m do avaliador 2 fora dos seis níveis canônicos")
    if not a.loc[a["flag_avaliador2"].eq("F"), "m_avaliador2"].eq(1.0).all():
        raise ValueError("flag F sem m=1,00 (convenção da amostra original)")
    return a


def carrega_amostras(qual: str = "combinada") -> pd.DataFrame:
    """Amostra(s) da dupla codificação, com coluna `amostra`.

    qual ∈ {"original", "dirigida", "combinada"}; combinada = original ∪
    dirigida, DEDUPLICADA por codigo_pof com a ORIGINAL prevalecendo
    (por construção a dirigida só contém itens fora da original — a
    prevalência é verificada, não presumida). Ordenada por codigo_pof."""
    cols = ["codigo_pof", "m_avaliador2", "flag_avaliador2",
            "dispositivo_avaliador2", "avaliador", "data"]
    if qual not in ("original", "dirigida", "combinada"):
        raise ValueError("qual deve ser 'original', 'dirigida' ou 'combinada'")
    o = carrega_dupla_codificacao()[cols].assign(amostra="original")
    if qual == "original":
        return o.sort_values("codigo_pof").reset_index(drop=True)
    d = (carrega_dupla_codificacao_dirigida()[cols]
         .assign(amostra="dirigida_peso_top50"))
    if qual == "dirigida":
        return d.sort_values("codigo_pof").reset_index(drop=True)
    comb = pd.concat([o, d[~d["codigo_pof"].isin(set(o["codigo_pof"]))]],
                     ignore_index=True)
    if comb["codigo_pof"].duplicated().any():
        raise AssertionError("amostra combinada com codigo_pof duplicado")
    return comb.sort_values("codigo_pof").reset_index(drop=True)


def divergencias(qual: str = "combinada") -> pd.DataFrame:
    """Itens da amostra `qual` em que os codificadores DIVERGEM (matriz
    central × avaliador 2), com tipologia:

      m_diverge     — ambos em campo (flag ≠ F) e m1 ≠ m2;
      campo_diverge — exatamente um dos dois codifica F (fora do campo);
      ambos         — campo diverge E os m registrados também diferem.

    Retorna [codigo_pof, descricao_pof, m_v3, m_av2, flag_v3, flag_av2,
    dispositivo_av2, tipo_divergencia, amostra], ordenado por codigo_pof.
    Default = amostra COMBINADA (original + dirigida R6).
    """
    a = carrega_amostras(qual)
    m = pd.read_csv(config.INPUTS / "matriz_pof_ibs_v5.csv",
                    dtype={"codigo_pof": str})
    m = m[["codigo_pof", "descricao_pof", "m_i_v3", "flag_v3"]]
    df = a.merge(m, on="codigo_pof", how="left", validate="1:1")
    if df["flag_v3"].isna().any():
        raise ValueError("item da amostra ausente na matriz v5")

    f1 = df["flag_v3"].eq("F")
    f2 = df["flag_avaliador2"].eq("F")
    campo_div = f1 != f2
    m_div = ~f1 & ~f2 & (df["m_i_v3"] != df["m_avaliador2"])
    m_registrado_dif = (df["m_i_v3"].notna() & df["m_avaliador2"].notna()
                        & (df["m_i_v3"] != df["m_avaliador2"]))

    df["tipo_divergencia"] = np.select(
        [campo_div & m_registrado_dif, campo_div, m_div],
        ["ambos", "campo_diverge", "m_diverge"], default="")
    out = (df[df["tipo_divergencia"] != ""]
           .rename(columns={"m_i_v3": "m_v3", "m_avaliador2": "m_av2",
                            "flag_avaliador2": "flag_av2",
                            "dispositivo_avaliador2": "dispositivo_av2"})
           [["codigo_pof", "descricao_pof", "m_v3", "m_av2", "flag_v3",
             "flag_av2", "dispositivo_av2", "tipo_divergencia", "amostra"]]
           .sort_values("codigo_pof").reset_index(drop=True))
    return out


# ------------------------------------------------------------------- kappa
def _cohen_kappa(a: np.ndarray, b: np.ndarray, cats: list,
                 ponderacao_linear: bool = False) -> float:
    """Cohen 1960 (bruto) / Cohen 1968 (ponderado linear no índice ordinal)
    — mesma implementação do v1 (Code/13b_dupla_codificacao_kappa.py)."""
    idx = {c: i for i, c in enumerate(cats)}
    M = np.zeros((len(cats), len(cats)))
    for x, y in zip(a, b):
        M[idx[x], idx[y]] += 1.0
    n = M.sum()
    if n == 0:
        return float("nan")
    P = M / n
    marg_a, marg_b = P.sum(axis=1), P.sum(axis=0)
    if not ponderacao_linear:
        po, pe = float(np.trace(P)), float(marg_a @ marg_b)
    else:
        k = len(cats)
        W = 1.0 - np.abs(np.subtract.outer(np.arange(k), np.arange(k))) / (k - 1)
        po = float((W * P).sum())
        pe = float((W * np.outer(marg_a, marg_b)).sum())
    return float((po - pe) / (1.0 - pe)) if pe < 1.0 else float("nan")


def kappas(qual: str = "combinada") -> dict:
    """Concordância matriz central × avaliador 2 na amostra `qual`:

      kappa_m_raw_ex_F    — Cohen 1960 no m (6 níveis), universo em que
                            AMBOS codificam em campo (flag ≠ F);
      kappa_m_linear_ex_F — Cohen 1968 ponderado linear (ordinal), idem;
      kappa_F_binario     — Cohen 1960 em F vs não-F, amostra inteira;
      n / n_em_campo      — tamanhos dos universos.

    Mesmas definições do v1 (13b) — a amostra original reproduz
    κ_m=0,637137 / linear 0,670573 / κ_F=0,923494."""
    a = carrega_amostras(qual)
    m = pd.read_csv(config.INPUTS / "matriz_pof_ibs_v5.csv",
                    dtype={"codigo_pof": str})
    df = a.merge(m[["codigo_pof", "m_i_v3", "flag_v3"]], on="codigo_pof",
                 how="left", validate="1:1")
    if df["flag_v3"].isna().any():
        raise ValueError("item da amostra ausente na matriz v5")
    f1 = df["flag_v3"].eq("F").to_numpy()
    f2 = df["flag_avaliador2"].eq("F").to_numpy()
    campo = ~f1 & ~f2
    cats = [f"{v:.2f}" for v in NIVEIS_M]
    a_m = df["m_i_v3"].map(lambda v: f"{float(v):.2f}").to_numpy()[campo]
    b_m = df["m_avaliador2"].map(lambda v: f"{float(v):.2f}").to_numpy()[campo]
    return {
        "kappa_m_raw_ex_F": _cohen_kappa(a_m, b_m, cats),
        "kappa_m_linear_ex_F": _cohen_kappa(a_m, b_m, cats, True),
        "kappa_F_binario": _cohen_kappa(f1.astype(int), f2.astype(int), [0, 1]),
        "n": int(len(df)),
        "n_em_campo_ambos": int(campo.sum()),
    }


# ------------------------------------------------------------- envelopes
def pi_p_central_nacional(despesa_em_campo: pd.DataFrame) -> float:
    """π^p nacional com a matriz central (limiar da regra F×não-F)."""
    m = carrega_matriz()
    em = despesa_em_campo.merge(m, on="codigo_pof", how="left")
    em = em[(em["flag"] != "F") & em["m_i"].notna()]
    return float((em["despesa_anual_rs"] * (1 - em["m_i"])).sum()
                 / em["despesa_anual_rs"].sum())


def matriz_envelope(direcao: str, pi_ref: float) -> pd.DataFrame:
    """Matriz-contrafactual do envelope: cada item divergente recebe a
    leitura que empurra π^p na `direcao` ("pi_alto" | "pi_baixo").

    Regras (docstring do módulo): em campo por ambos → min/max(m); F×não-F
    → regra do limiar com pi_ref (= π^p central nacional): a leitura em
    campo eleva π^p sse (1−m_campo) > pi_ref.
    """
    if direcao not in ("pi_alto", "pi_baixo"):
        raise ValueError("direcao deve ser 'pi_alto' ou 'pi_baixo'")
    m = carrega_matriz().set_index("codigo_pof")
    for _, r in divergencias().iterrows():
        c = r["codigo_pof"]
        F1, F2 = r["flag_v3"] == "F", r["flag_av2"] == "F"
        if not F1 and not F2:                       # m_diverge
            vals = (float(r["m_v3"]), float(r["m_av2"]))
            m.loc[c, "m_i"] = min(vals) if direcao == "pi_alto" else max(vals)
        else:                                       # F×não-F (limiar)
            m_campo = float(r["m_av2"] if F1 else r["m_v3"])
            flag_campo = r["flag_av2"] if F1 else r["flag_v3"]
            campo_eleva = (1.0 - m_campo) > pi_ref
            em_campo = campo_eleva == (direcao == "pi_alto")
            if em_campo:
                m.loc[c, "flag"] = flag_campo
                m.loc[c, "m_i"] = m_campo
            else:
                m.loc[c, "flag"] = "F"
                m.loc[c, "m_i"] = np.nan
    return m.reset_index()


def envelope_pi(despesa_item_uf: pd.DataFrame) -> pd.DataFrame:
    """π^p central e dos dois envelopes, por UF e nacional (linha BR).

    despesa_item_uf: despesa EM CAMPO do pipeline (ex-combustíveis
    monofásicos) — mesmo insumo de gaps.policy_gap_por_uf no pipeline.
    Colunas rotuladas pelo RESULTADO: envelope_aliquotas_min = menor π^p
    (base líquida maior); envelope_aliquotas_max = maior π^p.
    """
    pi_ref = pi_p_central_nacional(despesa_item_uf)

    def _pi(matriz: pd.DataFrame | None) -> pd.Series:
        por_uf = policy_gap_por_uf(despesa_item_uf, matriz=matriz)
        s = por_uf.set_index("uf")["pi_p"]
        m = carrega_matriz() if matriz is None else matriz
        em = despesa_item_uf.merge(m[["codigo_pof", "m_i", "flag"]],
                                   on="codigo_pof", how="left")
        em = em[(em["flag"] != "F") & em["m_i"].notna()]
        s.loc["BR"] = float((em["despesa_anual_rs"] * (1 - em["m_i"])).sum()
                            / em["despesa_anual_rs"].sum())
        return s

    central = _pi(None)
    alto = _pi(matriz_envelope("pi_alto", pi_ref))
    baixo = _pi(matriz_envelope("pi_baixo", pi_ref))

    # rotula pelo resultado medido no agregado nacional
    if alto.loc["BR"] < baixo.loc["BR"]:
        alto, baixo = baixo, alto
    out = pd.DataFrame({
        "uf": central.index,
        "pi_p_central": central.values,
        "pi_p_envelope_aliquotas_min": baixo.reindex(central.index).values,
        "pi_p_envelope_aliquotas_max": alto.reindex(central.index).values,
    })
    out["delta_aliquotas_min_pp"] = 100 * (out["pi_p_envelope_aliquotas_min"]
                                           - out["pi_p_central"])
    out["delta_aliquotas_max_pp"] = 100 * (out["pi_p_envelope_aliquotas_max"]
                                           - out["pi_p_central"])
    out["formula"] = (
        "π^p = Σ w(1−m)/Σ w em campo ex-combustíveis; envelopes: itens "
        "divergentes com min/max(m1,m2); F×não-F pela regra do limiar "
        f"(1−m_campo ≷ π^p central nacional = {pi_ref:.6f}); rótulo pelo "
        "RESULTADO (menor π^p = alíquotas mínimas)")
    out["fonte"] = _FONTE_DUPLA
    return out.reset_index(drop=True)


# ------------------------------------------------- despesa em desacordo
def tabela_divergencias(despesa_item_uf: pd.DataFrame
                        ) -> tuple[pd.DataFrame, dict]:
    """CSV item a item da despesa em desacordo + agregados de honestidade.

    despesa_item_uf: pof_despesa_item_uf.parquet COMPLETO (todos os itens);
    a exclusão de combustíveis/flag F entra só na métrica share_da_base
    (denominador = despesa em campo ex-combustíveis da matriz central).

    Agregados (dict): % de itens da amostra em desacordo; % da despesa
    AMOSTRADA em desacordo; cobertura da amostra (combinada e por amostra)
    sobre a despesa TOTAL e sobre a base de π^p; κ por amostra e combinado.
    A incerteza de classificação dos itens NÃO amostrados segue não
    capturada, mas o resíduo é DELIMITADO: a amostra dirigida (R6) garante
    que todo item do top-50% da despesa da base foi dupla-codificado.
    """
    d = despesa_item_uf.copy()
    d["codigo_pof"] = d["codigo_pof"].astype(str)
    d_nac = d.groupby("codigo_pof")["despesa_anual_rs"].sum()

    m = carrega_matriz()
    comb = itens_combustiveis(d)
    em_campo = m[(m["flag"] != "F") & m["m_i"].notna()]
    cod_base = set(em_campo["codigo_pof"]) - comb
    den_pi = float(d_nac[d_nac.index.isin(cod_base)].sum())

    a = carrega_amostras("combinada")
    div = divergencias().copy()
    div["despesa_anual_rs"] = div["codigo_pof"].map(d_nac).fillna(0.0)
    div["share_da_base"] = div["despesa_anual_rs"] / den_pi
    div = (div.sort_values(["despesa_anual_rs", "codigo_pof"],
                           ascending=[False, True]).reset_index(drop=True))
    div["formula"] = ("despesa_anual_rs = Σ_uf despesa POF do item; "
                      "share_da_base = despesa do item ÷ denominador nacional "
                      "de π^p (em campo, ex-combustíveis, matriz central)")
    div["fonte"] = _FONTE_DUPLA + "; data/processed/pof_despesa_item_uf.parquet"

    def _cob_base(codigos: pd.Series) -> float:
        na_base = codigos[codigos.isin(cod_base)]
        return float(d_nac.reindex(na_base).fillna(0.0).sum()) / den_pi

    desp_amostra = float(d_nac.reindex(a["codigo_pof"]).fillna(0.0).sum())
    desp_div = float(div["despesa_anual_rs"].sum())
    originais = a.loc[a["amostra"].eq("original"), "codigo_pof"]
    dirigidos = a.loc[a["amostra"].ne("original"), "codigo_pof"]
    cobertura = _cob_base(a["codigo_pof"])
    agregados = {
        "n_amostra": int(len(a)),
        "n_amostra_original": int(len(originais)),
        "n_amostra_dirigida": int(len(dirigidos)),
        "n_divergentes": int(len(div)),
        "n_por_tipo": div["tipo_divergencia"].value_counts().to_dict(),
        "n_divergentes_por_amostra":
            div["amostra"].value_counts().to_dict(),
        "pct_itens_em_desacordo": len(div) / len(a),
        "pct_despesa_amostrada_em_desacordo": desp_div / desp_amostra,
        "cobertura_amostra_despesa_total": desp_amostra / float(d_nac.sum()),
        "cobertura_amostra_base_pi": cobertura,
        "cobertura_amostra_base_pi_original": _cob_base(originais),
        "cobertura_amostra_base_pi_dirigida": _cob_base(dirigidos),
        "despesa_divergente_sobre_base_pi": desp_div / den_pi,
        "kappas": {q: kappas(q)
                   for q in ("original", "dirigida", "combinada")},
        "nota_honestidade": (
            "Amostra combinada (estratificada + dirigida pelo peso, R6): "
            "todo item do top-50% da despesa da base de π^p foi "
            f"dupla-codificado; cobertura de {cobertura:.1%} da despesa da "
            "base. A incerteza de classificação do resíduo não amostrado "
            f"({1 - cobertura:.1%} da despesa da base, cauda de itens de "
            "baixo peso individual) segue não capturada pelos envelopes e "
            "pelo bootstrap conjunto — resíduo DELIMITADO, declarar no "
            "manuscrito."),
    }
    return div, agregados


def main() -> None:
    despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    despesa["codigo_pof"] = despesa["codigo_pof"].astype(str)
    comb = itens_combustiveis(despesa)

    div, ag = tabela_divergencias(despesa)
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    div.to_csv(DIVERGENCIAS_CSV, index=False)

    env = envelope_pi(despesa[~despesa["codigo_pof"].isin(comb)])
    env.to_csv(ENVELOPE_CSV, index=False)

    MANIFEST.registra_arquivo(DUPLA_CSV)
    MANIFEST.registra_arquivo(DUPLA_DIRIGIDA_CSV)
    MANIFEST.registra_arquivo(DIVERGENCIAS_CSV)
    MANIFEST.registra_arquivo(ENVELOPE_CSV)
    MANIFEST.registra("classificacao_n_divergentes", Num(
        float(ag["n_divergentes"]), "itens da amostra combinada com m ou "
        "campo divergente", _FONTE_DUPLA, Label.DERIVADO, "itens"))
    MANIFEST.registra("classificacao_cobertura_base_pi", Num(
        ag["cobertura_amostra_base_pi"],
        "despesa dos itens amostrados (combinada) em campo ÷ denominador "
        "nacional de π^p", _FONTE_DUPLA, Label.DERIVADO, "fração"))
    MANIFEST.registra("classificacao_kappa_m_combinada", Num(
        ag["kappas"]["combinada"]["kappa_m_raw_ex_F"],
        "Cohen 1960 bruto no m (6 níveis), ambos em campo, amostra combinada",
        _FONTE_DUPLA, Label.DERIVADO, ""))
    MANIFEST.registra("classificacao_regra_limiar", Num(
        0.0, "F×não-F nos envelopes: leitura em campo eleva π^p sse "
        "(1−m_campo) > π^p central nacional", _FONTE_DUPLA,
        Label.CONVENCAO, ""))

    br = env.set_index("uf").loc["BR"]
    print(f"gravado: {DIVERGENCIAS_CSV}")
    print(f"gravado: {ENVELOPE_CSV}")
    print(f"amostra combinada: {ag['n_amostra']} itens "
          f"({ag['n_amostra_original']} estratificados + "
          f"{ag['n_amostra_dirigida']} dirigidos pelo peso, R6)")
    print(f"itens em desacordo: {ag['n_divergentes']}/{ag['n_amostra']} "
          f"({ag['pct_itens_em_desacordo']:.1%}); por tipo: {ag['n_por_tipo']}; "
          f"por amostra: {ag['n_divergentes_por_amostra']}")
    print(f"despesa amostrada em desacordo: "
          f"{ag['pct_despesa_amostrada_em_desacordo']:.1%}; cobertura da "
          f"amostra: {ag['cobertura_amostra_despesa_total']:.1%} da despesa "
          f"total, {ag['cobertura_amostra_base_pi']:.1%} da base de π^p "
          f"(original {ag['cobertura_amostra_base_pi_original']:.1%} + "
          f"dirigida {ag['cobertura_amostra_base_pi_dirigida']:.1%})")
    for q in ("original", "dirigida", "combinada"):
        k = ag["kappas"][q]
        print(f"kappa [{q}]: m bruto {k['kappa_m_raw_ex_F']:.4f}, "
              f"m linear {k['kappa_m_linear_ex_F']:.4f}, "
              f"F binário {k['kappa_F_binario']:.4f} "
              f"(n={k['n']}, em campo por ambos={k['n_em_campo_ambos']})")
    print(f"π^p nacional: envelope_aliquotas_min "
          f"{br['pi_p_envelope_aliquotas_min']:.6f} "
          f"({br['delta_aliquotas_min_pp']:+.3f} p.p.) ≤ central "
          f"{br['pi_p_central']:.6f} ≤ envelope_aliquotas_max "
          f"{br['pi_p_envelope_aliquotas_max']:.6f} "
          f"({br['delta_aliquotas_max_pp']:+.3f} p.p.)")


if __name__ == "__main__":
    main()
