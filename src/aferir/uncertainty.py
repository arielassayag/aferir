"""Banda de incerteza AMOSTRAL da POF 2017-2018 — bootstrap de conglomerados.

Método: bootstrap de reamostragem de UPAs (COD_UPA) dentro de estratos
(ESTRATO_POF), com reescalonamento de Rao & Wu (1988): em cada estrato h com
n_h UPAs, sorteiam-se n_h−1 UPAs com reposição e o peso de cada UPA é
multiplicado por [n_h/(n_h−1)] × (nº de vezes sorteada); estratos com n_h=1
ficam fixos (variância não identificável — declarado). B=500 réplicas,
numpy Generator com seed 42 — determinístico.

O QUE A BANDA PROPAGA (correção da crítica E2 do v1 — toda banda declara o
que propaga): SOMENTE a incerteza amostral da POF que entra no pipeline por
duas estatísticas, recomputadas réplica a réplica POR UF e nacionalmente:
  - π^p  (hiato de política: Σ w·d_i·(1−m_i) / Σ w·d_i, itens em campo,
          ex-combustíveis monofásicos — matriz POF×LC 214 v5);
  - f_low (share dos decis populacionais 1-3 na despesa ex-aluguel imputado —
          proxy CadÚnico do cashback, arts. 112-118).
Tudo o mais fica FIXO no cenário central (γ=12,5%, ψ=0, iso-carga): âncoras
TRU, shares POF de B_C, share_piso, ISFLSF, FBCF, receitas SICONFI/RFB, G e
σ̂. A banda é portanto COTA INFERIOR da incerteza amostral total da POF.

TRÊS fontes de incerteza comunicadas SEPARADAMENTE (nunca somadas — DESIGN
§2.7): (1) amostral POF = esta banda (estocástica); (2) conformidade γ =
corredor determinístico SERT [10%; 15%]; (3) política ψ = cenários discretos
{0; 0,3; 1}. A decomposição é impressa por `comunica()`.

INCERTEZA DE CLASSIFICAÇÃO (E2 desta revisão — dupla codificação κ_m=0,637,
aferir.classificacao): além da banda amostral, este módulo decompõe a
incerteza em TRÊS intervalos (roda_bootstrap_decomposto):
  (i)   amostragem — comportamento atual (Rao-Wu, classificação central fixa);
  (ii)  classificação — pesos plenos fixos; em cada réplica, cada item
        DIVERGENTE da amostra de dupla codificação recebe a leitura do
        codificador 1 ou 2 com probabilidade 1/2 (regra de desempate:
        sorteio único por réplica×item, RNG PCG64 com SeedSequence
        derivada [seed, 1] — fluxo independente do sorteio Rao-Wu);
  (iii) conjunto — Rao-Wu + sorteio de classificação na mesma réplica.
A execução canônica (B=500) é disparada por main(incluir_classificacao=True)
e grava qa_bootstrap_classificacao.json; banda_incerteza.csv permanece a
banda amostral canônica. UNIVERSO DO SORTEIO (R6): a amostra COMBINADA da
dupla codificação — 470 itens estratificados + 46 dirigidos pelo peso
(todo item do top-50% da despesa da base de π^p; aferir.classificacao).
O resíduo não amostrado segue não perturbado, mas fica DELIMITADO à cauda
de itens de baixo peso (< 47% da despesa da base).

Saída: data/processed/banda_incerteza.csv
       [componente, p5, p50, p95, largura, formula, fonte].
       data/processed/qa_bootstrap_classificacao.json (decomposição E2).

Executar: PYTHONPATH=src python3 -m aferir.uncertainty
(a primeira execução constrói o cache UPA×estrato dos microdados, ~4 min).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .base import itens_combustiveis
from .gaps import carrega_matriz
from .pipeline import _d_esfera, monta_insumos
from .provenance import MANIFEST, Label, Num
from .rates import EsferaInput, resolve_tri_esfera

B_REPLICAS = 500
DECIS_LOW = 3                      # proxy CadÚnico: decis 1-3 (art. 113)
CACHE_UPA = config.PROCESSED / "pof_boot_upa.parquet"
CACHE_UC = config.PROCESSED / "pof_boot_uc.parquet"
BANDA_CSV = config.PROCESSED / "banda_incerteza.csv"
QA_CLASSIFICACAO_JSON = config.PROCESSED / "qa_bootstrap_classificacao.json"

_FONTE_POF = ("IBGE POF 2017-2018, microdados (desenho ESTRATO_POF × COD_UPA); "
              "matriz data/inputs/matriz_pof_ibs_v5.csv; "
              "bootstrap Rao-Wu (1988), m_h = n_h−1")


# ------------------------------------------------------------------- cache
def constroi_cache(grava: bool = True) -> dict[str, pd.DataFrame]:
    """Cache do bootstrap em nível de UPA (lento ~4 min: relê os microdados).

    upa: [estrato_pof, cod_upa, uf, num_pi, den_pi] — universo = UPAs do
         MORADOR; num_pi = Σ d·(1−m_i) e den_pi = Σ d nos itens EM CAMPO
         (flag≠F, m_i válido, ex-combustíveis) — mesmos filtros de
         gaps.policy_gap_por_uf sobre a despesa ex-combustíveis do pipeline.
    uc:  [estrato_pof, cod_upa, num_dom, num_uc, uf, rpc, pop_w, despesa] —
         pré-ordenado por (rpc, chave da UC) como em pof.decis_renda; despesa
         ex-aluguel imputado (cód. 101).
    """
    from .inputs.pof import CODIGO_ALUGUEL_IMPUTADO, le_despesas, le_moradores

    micro = le_despesas()
    uc = le_moradores()

    # ---- universo de UPAs (MORADOR) --------------------------------------
    upas = (uc.groupby(["estrato_pof", "cod_upa"], as_index=False)
              .agg(uf=("uf", "first")))
    if upas["cod_upa"].duplicated().any():
        raise AssertionError("COD_UPA repetido entre estratos — chave inválida")

    # ---- lado item: num/den de π^p por UPA (filtros do pipeline) ----------
    item = (micro.groupby(["estrato_pof", "cod_upa", "uf", "codigo_pof"],
                          as_index=False)["despesa_anual_rs"].sum())
    item["codigo_pof"] = item["codigo_pof"].astype(str)
    sobra = set(item["cod_upa"]) - set(upas["cod_upa"])
    if sobra:
        raise AssertionError(f"{len(sobra)} UPAs com despesa fora do MORADOR")
    comb = itens_combustiveis(item)
    em = item[~item["codigo_pof"].isin(comb)].merge(
        carrega_matriz(), on="codigo_pof", how="left", validate="m:1")
    em = em[(em["flag"] != "F") & em["m_i"].notna()]
    em = em.assign(num_pi=em["despesa_anual_rs"] * (1 - em["m_i"]))
    por_upa = (em.groupby(["estrato_pof", "cod_upa"], as_index=False)
                 .agg(num_pi=("num_pi", "sum"),
                      den_pi=("despesa_anual_rs", "sum")))
    upa = (upas.merge(por_upa, on=["estrato_pof", "cod_upa"], how="left")
               .fillna({"num_pi": 0.0, "den_pi": 0.0})
               .sort_values(["estrato_pof", "cod_upa"], kind="mergesort")
               .reset_index(drop=True))

    # ---- lado UC: renda per capita, peso populacional e despesa ----------
    desp_uc = (micro[micro["codigo_pof"] != CODIGO_ALUGUEL_IMPUTADO]
               .groupby(["cod_upa", "num_dom", "num_uc"], as_index=False)
               ["despesa_anual_rs"].sum()
               .rename(columns={"despesa_anual_rs": "despesa"}))
    d = uc.copy()
    d["rpc"] = d["renda_total"] / d["n_pessoas"].clip(lower=1)
    d["pop_w"] = d["peso_final"] * d["n_pessoas"]
    d = d.merge(desp_uc, on=["cod_upa", "num_dom", "num_uc"], how="left")
    d["despesa"] = d["despesa"].fillna(0.0)
    d = (d.sort_values(["rpc", "cod_upa", "num_dom", "num_uc"], kind="mergesort")
          .reset_index(drop=True))
    uc_boot = d[["estrato_pof", "cod_upa", "num_dom", "num_uc", "uf",
                 "rpc", "pop_w", "despesa"]]

    if grava:
        config.PROCESSED.mkdir(parents=True, exist_ok=True)
        upa.to_parquet(CACHE_UPA, index=False)
        uc_boot.to_parquet(CACHE_UC, index=False)
        MANIFEST.registra_arquivo(CACHE_UPA)
        MANIFEST.registra_arquivo(CACHE_UC)
    return {"upa": upa, "uc": uc_boot}


def carrega_cache() -> dict[str, pd.DataFrame]:
    if CACHE_UPA.exists() and CACHE_UC.exists():
        return {"upa": pd.read_parquet(CACHE_UPA),
                "uc": pd.read_parquet(CACHE_UC)}
    return constroi_cache(grava=True)


# ------------------------------------------------------------------- pesos
def pesos_rao_wu(upa: pd.DataFrame, B: int, seed: int) -> np.ndarray:
    """Multiplicadores bootstrap (B, n_upa) — Rao & Wu (1988), m_h = n_h−1.

    `upa` deve vir ordenado por (estrato_pof, cod_upa) — estratos são blocos
    contíguos, percorridos em ordem fixa: mesma seed ⇒ mesma matriz.
    """
    estratos = upa["estrato_pof"].to_numpy()
    if not (np.diff(estratos) >= 0).all():
        raise ValueError("cache de UPAs fora de ordem por estrato")
    rng = np.random.default_rng(seed)
    W = np.ones((B, len(upa)))
    _, inicio = np.unique(estratos, return_index=True)
    limites = np.append(inicio, len(upa))
    for i0, i1 in zip(limites[:-1], limites[1:]):
        n_h = int(i1 - i0)
        if n_h < 2:
            continue                       # estrato de 1 UPA: peso fixo
        sorteios = rng.integers(0, n_h, size=(B, n_h - 1))
        contagem = np.zeros((B, n_h))
        np.add.at(contagem,
                  (np.repeat(np.arange(B), n_h - 1), sorteios.ravel()), 1.0)
        W[:, i0:i1] = contagem * (n_h / (n_h - 1))
    return W


# -------------------------------------------------------------- estatísticas
def estatisticas_replicas(cache: dict[str, pd.DataFrame],
                          W: np.ndarray) -> dict[str, np.ndarray]:
    """π^p e f_low por réplica: nacionais (B,) e por UF (B, 27)."""
    ufs = sorted(config.UFS)
    pos_uf = {u: i for i, u in enumerate(ufs)}

    upa = cache["upa"]
    num = upa["num_pi"].to_numpy()
    den = upa["den_pi"].to_numpy()
    ind = np.zeros((len(upa), len(ufs)))
    ind[np.arange(len(upa)), upa["uf"].map(pos_uf).to_numpy()] = 1.0
    num_uf = W @ (ind * num[:, None])
    den_uf = W @ (ind * den[:, None])

    uc = cache["uc"]
    col_upa = {c: i for i, c in enumerate(upa["cod_upa"].to_numpy())}
    upa_de_uc = uc["cod_upa"].map(col_upa).to_numpy()
    uf_de_uc = uc["uf"].map(pos_uf).to_numpy()
    pop_w = uc["pop_w"].to_numpy()
    desp = uc["despesa"].to_numpy()

    B = W.shape[0]
    f_uf = np.empty((B, len(ufs)))
    f_nac = np.empty(B)
    for b in range(B):
        w = W[b, upa_de_uc]
        acum = np.cumsum(pop_w * w)
        acum = acum / acum[-1]
        decil = np.clip(np.ceil(acum * 10), 1, 10)
        low = decil <= DECIS_LOW
        dw = desp * w
        tot = np.bincount(uf_de_uc, weights=dw, minlength=len(ufs))
        baixo = np.bincount(uf_de_uc, weights=dw * low, minlength=len(ufs))
        f_uf[b] = baixo / tot
        f_nac[b] = dw[low].sum() / dw.sum()

    return {"pi_uf": num_uf / den_uf, "pi_nac": (W @ num) / (W @ den),
            "f_low_uf": f_uf, "f_low_nac": f_nac, "ufs": np.array(ufs)}


# ------------------------------------ classificação (E2): sorteio conjunto
def deltas_classificacao_upa() -> pd.DataFrame:
    """Δ de contribuição por UPA × item DIVERGENTE ao trocar a classificação
    do codificador 1 (matriz central) pela do codificador 2.

    Relê os microdados (~4 min) porque o cache pof_boot_upa.parquet agrega o
    detalhe de item. Mesmos filtros do cache: universo MORADOR,
    ex-combustíveis monofásicos; contribuição sob F ou m ausente = (0, 0).

    Retorna [cod_upa, codigo_pof, d_num, d_den]:
      d_num = d·(1−m2)·1[flag2≠F] − d·(1−m1)·1[flag1≠F, m1 válido]
      d_den = d·1[flag2≠F] − d·1[flag1≠F, m1 válido]
    """
    from .classificacao import divergencias
    from .inputs.pof import le_despesas

    div = divergencias()
    micro = le_despesas()
    micro["codigo_pof"] = micro["codigo_pof"].astype(str)
    comb = itens_combustiveis(micro)
    if div["codigo_pof"].isin(comb).any():
        raise AssertionError("item divergente monofásico — fora do π^p, revisar")
    d = (micro[micro["codigo_pof"].isin(set(div["codigo_pof"]))]
         .groupby(["cod_upa", "codigo_pof"], as_index=False)
         ["despesa_anual_rs"].sum()
         .merge(div, on="codigo_pof", validate="m:1"))

    em1 = d["flag_v3"].ne("F") & d["m_v3"].notna()
    em2 = d["flag_av2"].ne("F") & d["m_av2"].notna()
    w = d["despesa_anual_rs"]
    d["d_num"] = (w * (1 - d["m_av2"].fillna(1.0))).where(em2, 0.0) \
        - (w * (1 - d["m_v3"].fillna(1.0))).where(em1, 0.0)
    d["d_den"] = w.where(em2, 0.0) - w.where(em1, 0.0)
    return d[["cod_upa", "codigo_pof", "d_num", "d_den"]]


def sorteio_classificacao(itens: list[str], B: int, seed: int) -> np.ndarray:
    """Matriz Z (B × n_itens) ∈ {0; 1}: Z[b, j] = 1 ⇔ a réplica b adota a
    leitura do CODIFICADOR 2 para o j-ésimo item divergente (ordem = itens,
    ordenados por codigo_pof); 0 mantém o codificador 1 (matriz central).

    Regra de desempate: Bernoulli(1/2) por réplica×item, sorteio único.
    RNG determinístico: Generator(PCG64(SeedSequence([seed, 1]))) — chave
    derivada distinta da do Rao-Wu (default_rng(seed)), fluxos independentes;
    mesma seed ⇒ mesma matriz Z, indexada [réplica, item].
    """
    if list(itens) != sorted(itens):
        raise ValueError("itens do sorteio fora de ordem canônica")
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, 1])))
    return rng.integers(0, 2, size=(B, len(itens))).astype(float)


def pi_replicas_com_classificacao(cache: dict[str, pd.DataFrame],
                                  W: np.ndarray, deltas: pd.DataFrame,
                                  Z: np.ndarray,
                                  itens: list[str]) -> dict[str, np.ndarray]:
    """π^p por réplica com sorteio de classificação: nacionais (B,) e por
    UF (B, 27). Numerador/denominador da réplica b:
      N_b = Σ_upa W[b,upa]·(num_pi + Σ_j Z[b,j]·d_num[upa,j]);  idem D_b.
    Z=0 reproduz estatisticas_replicas (classificação central)."""
    ufs = sorted(config.UFS)
    upa = cache["upa"]
    num = upa["num_pi"].to_numpy()
    den = upa["den_pi"].to_numpy()
    ind = np.zeros((len(upa), len(ufs)))
    ind[np.arange(len(upa)), upa["uf"].map(
        {u: i for i, u in enumerate(ufs)}).to_numpy()] = 1.0

    sobra = set(deltas["cod_upa"]) - set(upa["cod_upa"])
    if sobra:
        raise AssertionError(f"{len(sobra)} UPAs dos deltas fora do cache")
    Dn = (deltas.pivot_table(index="cod_upa", columns="codigo_pof",
                             values="d_num", aggfunc="sum", fill_value=0.0)
          .reindex(index=upa["cod_upa"], columns=itens, fill_value=0.0)
          .fillna(0.0).to_numpy())
    Dd = (deltas.pivot_table(index="cod_upa", columns="codigo_pof",
                             values="d_den", aggfunc="sum", fill_value=0.0)
          .reindex(index=upa["cod_upa"], columns=itens, fill_value=0.0)
          .fillna(0.0).to_numpy())

    Sn = W * (Z @ Dn.T)                       # (B, n_upa): ajuste ponderado
    Sd = W * (Z @ Dd.T)
    num_uf = W @ (ind * num[:, None]) + Sn @ ind
    den_uf = W @ (ind * den[:, None]) + Sd @ ind
    return {"pi_uf": num_uf / den_uf,
            "pi_nac": (W @ num + Sn.sum(axis=1)) / (W @ den + Sd.sum(axis=1))}


def roda_bootstrap_decomposto(B: int = B_REPLICAS, seed: int = config.SEED,
                              ins: dict | None = None,
                              cache: dict[str, pd.DataFrame] | None = None,
                              deltas: pd.DataFrame | None = None,
                              ) -> tuple[pd.DataFrame, dict]:
    """DECOMPOSIÇÃO E2 — três intervalos por componente:
    fonte_incerteza ∈ {amostragem_pof, classificacao, conjunto}.

    Retorna (bandas [fonte_incerteza, componente, p5, p50, p95, largura,
    formula, fonte], réplicas por fonte). NÃO grava banda_incerteza.csv."""
    from .classificacao import divergencias

    cache = cache if cache is not None else carrega_cache()
    ins = ins if ins is not None else monta_insumos()
    deltas = deltas if deltas is not None else deltas_classificacao_upa()
    itens = sorted(divergencias()["codigo_pof"])
    n_upa = len(cache["upa"])

    W = pesos_rao_wu(cache["upa"], B, seed)
    Z = sorteio_classificacao(itens, B, seed)
    est = estatisticas_replicas(cache, W)
    c0 = estatisticas_replicas(cache, np.ones((1, n_upa)))   # central exato

    r_cl = pi_replicas_com_classificacao(cache, np.ones((B, n_upa)),
                                          deltas, Z, itens)
    r_cj = pi_replicas_com_classificacao(cache, W, deltas, Z, itens)
    fontes = {
        "amostragem_pof": (
            est["pi_uf"], est["pi_nac"], est["f_low_uf"], est["f_low_nac"],
            "Rao-Wu, classificação central fixa (banda canônica)"),
        "classificacao": (
            r_cl["pi_uf"], r_cl["pi_nac"],
            np.repeat(c0["f_low_uf"], B, axis=0),
            np.repeat(c0["f_low_nac"], B),
            "pesos plenos fixos; sorteio codificador 1/2 (prob. 1/2) nos "
            "itens divergentes"),
        "conjunto": (
            r_cj["pi_uf"], r_cj["pi_nac"],
            est["f_low_uf"], est["f_low_nac"],
            "Rao-Wu + sorteio de classificação na mesma réplica"),
    }
    boot = (f"bootstrap decomposto E2, B={B}, seed {seed}; sorteio de "
            "classificação: PCG64(SeedSequence([seed, 1])), prob. 1/2 por "
            "réplica×item divergente; universo: amostra COMBINADA da dupla "
            "codificação (470 estratificados + 46 dirigidos pelo peso, R6 — "
            "resíduo não amostrado delimitado à cauda de baixo peso)")
    linhas, replicas = [], {}
    for fonte, (pi_uf, pi_nac, fl_uf, fl_nac, desc) in fontes.items():
        taus = propaga_taus(ins, pi_uf, fl_uf)
        comps = {"pi_p_nacional": pi_nac, "f_low_nacional": fl_nac,
                 **{c: taus[c].to_numpy() for c in
                    ("tau_CBS_pp", "tau_E_pp", "tau_M_pp", "soma_pp")}}
        replicas[fonte] = comps
        for nome, v in comps.items():
            p5, p50, p95 = np.percentile(v, [5, 50, 95])
            linhas.append({
                "fonte_incerteza": fonte, "componente": nome, "p5": p5,
                "p50": p50, "p95": p95, "largura": p95 - p5,
                "formula": f"{nome} por réplica — {desc}",
                "fonte": _FONTE_POF + "; " + boot})
    return pd.DataFrame(linhas), replicas


def grava_qa_classificacao(bandas: pd.DataFrame, B: int, seed: int,
                           agregados: dict, execucao: str,
                           extras: dict | None = None,
                           path=QA_CLASSIFICACAO_JSON) -> None:
    """qa_bootstrap_classificacao.json: parâmetros + intervalos da
    decomposição E2 + agregados de desacordo (determinístico, sem timestamp)."""
    import json

    intervalos: dict = {}
    for _, r in bandas.iterrows():
        intervalos.setdefault(r["componente"], {})[r["fonte_incerteza"]] = {
            "p5": float(r["p5"]), "p50": float(r["p50"]),
            "p95": float(r["p95"]), "largura": float(r["largura"])}
    payload = {
        "execucao": execucao,
        "parametros": {
            "B": B, "seed": seed,
            "regra_sorteio": (
                "cada item divergente recebe a leitura do codificador 2 com "
                "probabilidade 1/2 por réplica (senão codificador 1 = matriz "
                "central); RNG PCG64(SeedSequence([seed, 1])), independente "
                "do fluxo Rao-Wu; Z indexada [réplica, item ordenado]"),
            "universo_sorteio": (
                "itens divergentes da amostra COMBINADA de dupla codificação "
                "(data/inputs/dupla_codificacao_2026_07.csv, estratificada, + "
                "data/inputs/dupla_codificacao_dirigida_2026_07.csv, dirigida "
                "pelo peso R6: top-50% da despesa da base de π^p; dedup com a "
                "original prevalecendo) — itens NÃO amostrados não são "
                "perturbados; resíduo DELIMITADO à cauda de itens de baixo "
                "peso (< 47% da despesa da base)"),
        },
        "desacordo": agregados,
        "intervalos": intervalos,
    }
    if extras:
        payload.update(extras)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    # CSV espelho para os placeholders do manuscrito ({{csv:...}} não lê JSON):
    # uma linha por fonte de incerteza × componente (E2, seção 4.5).
    dec = bandas.copy()
    dec["formula"] = (
        "bootstrap Rao-Wu (B=" + str(B) + ", seed=" + str(seed) + "): "
        "amostragem_pof = só pesos; classificacao = só sorteio 1/2 dos itens "
        "divergentes (pesos centrais); conjunto = ambos na mesma réplica")
    dec["fonte"] = ("qa_bootstrap_classificacao.json (parâmetros e regra de "
                    "desempate); dupla codificação combinada: "
                    "data/inputs/dupla_codificacao_2026_07.csv + "
                    "data/inputs/dupla_codificacao_dirigida_2026_07.csv (R6)")
    dec.to_csv(config.PROCESSED / "banda_incerteza_decomposta.csv",
               index=False)


# --------------------------------------------------------------- propagação
def propaga_taus(ins: dict, pi_uf: np.ndarray, f_low_uf: np.ndarray,
                 gamma: float = 0.125, psi: float = 0.0) -> pd.DataFrame:
    """Recomputa a identidade nacional (iso-carga central) réplica a réplica,
    substituindo SOMENTE π^p_uf e f_low_uf nos insumos centrais (espelho de
    pipeline.executa: _d_esfera + resolve_tri_esfera)."""
    b0 = ins["b"]
    if list(b0["uf"]) != sorted(config.UFS):
        raise AssertionError("insumos b fora da ordem canônica de UFs")
    g = ins["g"]
    alvo_e_uf = ins["alvos_e"]["alvo_ex_comb"].sort_index()

    linhas = []
    for k in range(pi_uf.shape[0]):
        bb = b0.copy()
        bb["pi_p"] = pi_uf[k]
        bb["f_low"] = f_low_uf[k]
        d = {s: _d_esfera(bb, s, gamma, psi)
             for s in ("uniao", "estadual", "municipal")}
        alvo_m_uf = (ins["alvo_m"].sort_index()
                     .reindex(d["municipal"].index).fillna(0.0))
        g_e = g["estadual"].sort_index().reindex(d["estadual"].index).fillna(0.0)
        g_m = g["municipal"].sort_index().reindex(d["municipal"].index).fillna(0.0)
        sol = resolve_tri_esfera(
            EsferaInput(ins["alvo_u"]["alvo"], float(d["uniao"].sum()), g["uniao"]),
            EsferaInput(float(alvo_e_uf.sum()), float(d["estadual"].sum()),
                        float(g_e.sum())),
            EsferaInput(float(alvo_m_uf.sum()), float(d["municipal"].sum()),
                        float(g_m.sum())),
            modo="iso_carga", sigma_iso=ins["sigma_iso"],
        )
        linhas.append({"tau_CBS_pp": sol.tau_U * 100, "tau_E_pp": sol.tau_E * 100,
                       "tau_M_pp": sol.tau_M * 100, "soma_pp": sol.soma * 100})
    return pd.DataFrame(linhas)


# -------------------------------------------------------------------- banda
def roda_bootstrap(B: int = B_REPLICAS, seed: int = config.SEED,
                   ins: dict | None = None,
                   cache: dict[str, pd.DataFrame] | None = None,
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Banda [componente, p5, p50, p95, largura, formula, fonte] + réplicas."""
    cache = cache if cache is not None else carrega_cache()
    ins = ins if ins is not None else monta_insumos()

    W = pesos_rao_wu(cache["upa"], B, seed)
    est = estatisticas_replicas(cache, W)
    taus = propaga_taus(ins, est["pi_uf"], est["f_low_uf"])

    boot = f"bootstrap Rao-Wu UPA×ESTRATO_POF, B={B}, seed {seed}"
    fonte_tau = (
        _FONTE_POF + f"; {boot}; PROPAGA SÓ π^p_uf e f_low_uf — demais "
        "insumos fixos no central γ=12,5%, ψ=0, iso-carga (cota inferior "
        "da incerteza amostral POF); fontes centrais: MANIFEST_RUN.json")
    comps = [
        ("pi_p_nacional",
         est["pi_nac"],
         "Σ w_b·d_i·(1−m_i) / Σ w_b·d_i, itens em campo ex-combustíveis",
         _FONTE_POF + f"; {boot}"),
        ("f_low_nacional",
         est["f_low_nac"],
         f"share dos decis populacionais 1-{DECIS_LOW} na despesa "
         "(ex-aluguel imputado), decis recomputados por réplica",
         _FONTE_POF + f"; {boot}"),
        ("tau_CBS_pp", taus["tau_CBS_pp"].to_numpy(),
         "τ_U(b) = (Alvo_U − σ̂·G_U)/D_U(π^p_uf(b), f_low_uf(b))", fonte_tau),
        ("tau_E_pp", taus["tau_E_pp"].to_numpy(),
         "τ_E(b) = (Alvo_E − σ̂·G_E)/D_E(π^p_uf(b), f_low_uf(b))", fonte_tau),
        ("tau_M_pp", taus["tau_M_pp"].to_numpy(),
         "τ_M(b) = (Alvo_M − σ̂·G_M)/D_M(π^p_uf(b), f_low_uf(b))", fonte_tau),
        ("soma_pp", taus["soma_pp"].to_numpy(),
         "Σ(b) = τ_U(b) + τ_E(b) + τ_M(b)", fonte_tau),
    ]
    linhas = []
    for nome, v, formula, fonte in comps:
        p5, p50, p95 = np.percentile(v, [5, 50, 95])
        linhas.append({"componente": nome, "p5": p5, "p50": p50, "p95": p95,
                       "largura": p95 - p5, "formula": formula, "fonte": fonte})
    return pd.DataFrame(linhas), taus


def _registra_manifest(banda: pd.DataFrame, cache: dict[str, pd.DataFrame],
                       B: int) -> None:
    """Proveniência da banda CANÔNICA (a publicada em banda_incerteza.csv)."""
    s = banda.set_index("componente")
    n_h_min = int(cache["upa"].groupby("estrato_pof").size().min())
    fonte = str(s.at["soma_pp", "fonte"])
    MANIFEST.registra("bootstrap_pof_B", Num(
        float(B), "nº de réplicas bootstrap", _FONTE_POF, Label.CONVENCAO, ""))
    MANIFEST.registra("bootstrap_pof_soma_p5", Num(
        float(s.at["soma_pp", "p5"]), "percentil 5 de Σ(b)", fonte,
        Label.DERIVADO, "p.p."))
    MANIFEST.registra("bootstrap_pof_soma_p95", Num(
        float(s.at["soma_pp", "p95"]), "percentil 95 de Σ(b)", fonte,
        Label.DERIVADO, "p.p."))
    MANIFEST.registra("bootstrap_pof_n_h_minimo", Num(
        float(n_h_min), "menor nº de UPAs por estrato (n_h=1 ficaria fixo, "
        "sem variância — não ocorre na POF 2017-18)", _FONTE_POF,
        Label.DADO, "UPAs"))


# ------------------------------------------------------------- comunicação
def comunica(banda: pd.DataFrame) -> None:
    """Decomposição das TRÊS fontes de incerteza sobre Σ (correção E2 do v1:
    cada banda declara o que propaga; as fontes NÃO se somam)."""
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    iso = nac[nac.modo_redutor == "iso_carga"]
    cor = iso[iso.psi == 0.0].set_index("cenario_gamma")["soma_pp"]
    psi = iso[iso.cenario_gamma == "central"].set_index("psi")["soma_pp"]
    s = banda.set_index("componente")

    print("=== BANDA DE INCERTEZA — Σ = τ_CBS + τ_E + τ_M (p.p.) ===")
    print("Três fontes, comunicadas SEPARADAMENTE (não se somam):")
    print(f"1. AMOSTRAL POF (bootstrap Rao-Wu UPA×estrato; propaga SÓ π^p e "
          f"f_low; demais insumos fixos no central):\n"
          f"   Σ ∈ [{s.at['soma_pp', 'p5']:.2f}; {s.at['soma_pp', 'p95']:.2f}] "
          f"(p5-p95), mediana {s.at['soma_pp', 'p50']:.2f}, "
          f"largura {s.at['soma_pp', 'largura']:.2f} p.p.")
    print(f"2. CONFORMIDADE γ (corredor determinístico SERT [10%; 15%]):\n"
          f"   Σ ∈ [{cor['factivel']:.2f}; {cor['conservador']:.2f}], "
          f"largura {cor['conservador'] - cor['factivel']:.2f} p.p.")
    print(f"3. POLÍTICA ψ (split payment, cenários discretos):\n"
          f"   Σ = {psi[0.0]:.2f} (ψ=0) → {psi[0.30]:.2f} (ψ=0,3) → "
          f"{psi[1.0]:.2f} (ψ=1), amplitude {psi[0.0] - psi[1.0]:.2f} p.p.")
    lg = float(cor["conservador"] - cor["factivel"])
    la = float(s.at["soma_pp", "largura"])
    veredito = ("dominada pelo corredor γ (esperado)" if la < lg
                else "NÃO é menor que o corredor γ — ACHADO, reportar")
    print(f"Leitura: a incerteza amostral da POF ({la:.2f} p.p.) é "
          f"{'menor' if la < lg else 'MAIOR/igual'} que a paramétrica de "
          f"conformidade ({lg:.2f} p.p.) — {veredito}.")
    print(f"π^p nacional: [{s.at['pi_p_nacional', 'p5']:.4f}; "
          f"{s.at['pi_p_nacional', 'p95']:.4f}], mediana "
          f"{s.at['pi_p_nacional', 'p50']:.4f}; f_low nacional: "
          f"[{s.at['f_low_nacional', 'p5']:.4f}; "
          f"{s.at['f_low_nacional', 'p95']:.4f}].")


def main(incluir_classificacao: bool = False) -> None:
    """Banda amostral canônica (sempre) e, com incluir_classificacao=True,
    a decomposição E2 canônica (B=B_REPLICAS) em
    qa_bootstrap_classificacao.json — relê os microdados (~+4 min)."""
    cache = carrega_cache()
    ins = monta_insumos()
    banda, _ = roda_bootstrap(B=B_REPLICAS, seed=config.SEED,
                              ins=ins, cache=cache)
    _registra_manifest(banda, cache, B_REPLICAS)
    banda.to_csv(BANDA_CSV, index=False)
    MANIFEST.registra_arquivo(BANDA_CSV)
    print(f"gravado: {BANDA_CSV}")
    print(banda[["componente", "p5", "p50", "p95", "largura"]]
          .round(4).to_string(index=False))
    comunica(banda)

    if incluir_classificacao:
        from .classificacao import tabela_divergencias

        bandas, _ = roda_bootstrap_decomposto(B=B_REPLICAS, seed=config.SEED,
                                              ins=ins, cache=cache)
        despesa = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
        _, agregados = tabela_divergencias(despesa)
        grava_qa_classificacao(bandas, B_REPLICAS, config.SEED, agregados,
                               execucao=f"canonica_B{B_REPLICAS}")
        MANIFEST.registra_arquivo(QA_CLASSIFICACAO_JSON)
        print(f"gravado: {QA_CLASSIFICACAO_JSON}")
        print(bandas[["fonte_incerteza", "componente", "p5", "p50", "p95",
                      "largura"]].round(4).to_string(index=False))


if __name__ == "__main__":
    import sys
    main(incluir_classificacao="--classificacao" in sys.argv)
