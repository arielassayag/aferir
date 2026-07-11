"""Robustez econômica — camada de DADOS dos itens E4 e E5 do plano de revisão.

E4 (estacionariedade base/PIB). A comparação de uma base medida em 2024-25
com o gatilho estimado para 2033 pressupõe participação estável da base
tributável no PIB. A hipótese é nomeada pela identidade

    τ_2033 / τ_2024-25 = (base/PIB)_2024-25 ÷ (base/PIB)_2033 ,

registrada no MANIFEST como convenção (sob estacionariedade a razão vale 1).
Proxy aberta da participação: s = despesa de consumo das famílias ÷ PIB a
preços de mercado (SIDRA t/1846, v/585 R$ mi correntes, c11255 = 90707 PIB e
93404 consumo das famílias), somas de 4 trimestres por ano civil 2015-2025.
O módulo reporta a série anual, o s corrente da janela 2024-2025 (8 tri),
os extremos da década, os fatores de reescala s_extremo/s_corrente — que o
orquestrador aplica a B_C e B_ISFLSF nos cenários sens_base_pib_{min,max} —
e a elasticidade aproximada Δτ ≈ −τ·Δs/s nos dois extremos.

E5 (conformidade heterogênea por UF). Informalidade média 2024T1-2025T4 por
UF (PNAD Contínua, SIDRA t/8529, v/12466 %) e hiato de conformidade
heterogêneo

    γ_uf = γ̄ · [1 + β·(inf_uf − inf̄)/inf̄] ,  β ∈ {0,5; 1,0},

com γ̄ = 0,125 (config.GAP_CONFORMIDADE central) e inf̄ = média NACIONAL das
taxas de informalidade ponderada pela base ordinária B_ord de cada UF
(base_uf.csv) — ponderação declarada: a base de consumo é o peso relevante
porque γ incide sobre a base, não sobre pessoas ocupadas. Renormalização
multiplicativa k garante Σ γ_uf·B_ord ÷ Σ B_ord = γ̄ exato (o γ médio
nacional NÃO muda; só a distribuição espacial). A aplicação nos vetores por
esfera é do pipeline — este módulo entrega apenas os γ_uf validados.

Saídas (data/processed/): sens_base_pib.csv, informalidade_uf.csv,
sens_gamma_heterogeneo.csv — todas com colunas formula e fonte, e fonte com
o vintage integral da API (url + collected_at + sha256 do sidecar _meta.json
gravado pelo fetcher; nenhum datetime é gerado aqui).

Determinístico: reexecução byte-idêntica. Fontes vivas congeladas pelos
arquivos raw (SCN Trimestral revisa trimestres; PNADC reatualiza séries em
reponderações — ver docstrings dos fetchers aferir.fetch.ibge e
aferir.fetch.ibge_informalidade).

Executar: PYTHONPATH=src python3 -m aferir.robustez
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

import pandas as pd

from aferir import config
from aferir.provenance import MANIFEST, Label, Num

# ------------------------------------------------------------------ caminhos
RAW_CNT_1846 = config.RAW / "sidra" / "cnt_1846_decada.json"
RAW_INFORMALIDADE = (config.RAW / "sidra_informalidade" /
                     "informalidade_8529_2024_2025.json")

CSV_SENS_BASE_PIB = config.PROCESSED / "sens_base_pib.csv"
CSV_INFORMALIDADE_UF = config.PROCESSED / "informalidade_uf.csv"
CSV_SENS_GAMMA = config.PROCESSED / "sens_gamma_heterogeneo.csv"

# ------------------------------------------------------- convenções E4 (t/1846)
_COD_PIB = "90707"           # c11255: PIB a preços de mercado
_COD_CFAM = "93404"          # c11255: despesa de consumo das famílias
_ANOS_DECADA = tuple(range(2015, 2026))   # 11 anos civis, 44 trimestres
_ANOS_JANELA = (2024, 2025)               # janela de receita do pipeline

# ------------------------------------------------------- convenções E5 (t/8529)
GAMMA_BARRA = config.GAP_CONFORMIDADE["central"]   # 0,125 (corredor SERT/FMI)
BETAS = (0.5, 1.0)   # grade do plano de revisão (E5): β ∈ {0,5; 1,0}
_N_TRIMESTRES_INF = 8
_DOMINIO_GAMMA = (0.0, 0.5)  # mesmo domínio de aferir.gaps.hiato_total

# Mapeamento código IBGE (D1C) → (sigla, nome oficial). O nome é CONFERIDO
# contra D1N na leitura — o dicionário não pode divergir da fonte.
IBGE_UF: dict[str, tuple[str, str]] = {
    "11": ("RO", "Rondônia"), "12": ("AC", "Acre"), "13": ("AM", "Amazonas"),
    "14": ("RR", "Roraima"), "15": ("PA", "Pará"), "16": ("AP", "Amapá"),
    "17": ("TO", "Tocantins"), "21": ("MA", "Maranhão"), "22": ("PI", "Piauí"),
    "23": ("CE", "Ceará"), "24": ("RN", "Rio Grande do Norte"),
    "25": ("PB", "Paraíba"), "26": ("PE", "Pernambuco"),
    "27": ("AL", "Alagoas"), "28": ("SE", "Sergipe"), "29": ("BA", "Bahia"),
    "31": ("MG", "Minas Gerais"), "32": ("ES", "Espírito Santo"),
    "33": ("RJ", "Rio de Janeiro"), "35": ("SP", "São Paulo"),
    "41": ("PR", "Paraná"), "42": ("SC", "Santa Catarina"),
    "43": ("RS", "Rio Grande do Sul"), "50": ("MS", "Mato Grosso do Sul"),
    "51": ("MT", "Mato Grosso"), "52": ("GO", "Goiás"),
    "53": ("DF", "Distrito Federal"),
}

# Cenário central do painel nacional (mesma chave de pipeline.executa default)
_FILTRO_CENTRAL = {
    "cenario_gamma": "central", "psi": 0.0, "modo_redutor": "iso_carga",
    "is_cenario": "proxy_ipi_rfb", "ancora_federal": "liquida_rtn",
}


# ------------------------------------------------------------------ vintages
def _vintage(raw: Path) -> str:
    """Vintage integral da API a partir do sidecar `<arquivo>._meta.json`
    gravado pelo fetcher (url + collected_at + sha256) — nenhum datetime
    é gerado aqui; a data é a do download congelado."""
    sidecar = raw.parent / (raw.name + "._meta.json")
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    return (f"{meta['url']}; coletado em {meta['collected_at']}; "
            f"sha256 {meta['sha256']}")


@functools.lru_cache(maxsize=1)
def _fonte_1846() -> str:
    return ("IBGE SIDRA t/1846 (SCN Trimestral) v/585 R$ mi correntes, "
            "c11255={90707 PIB pm; 93404 despesa de consumo das famílias}, "
            "2015T1-2025T4; " + _vintage(RAW_CNT_1846) +
            "; cache data/raw/sidra/cnt_1846_decada.json")


@functools.lru_cache(maxsize=1)
def _fonte_8529() -> str:
    return ("IBGE SIDRA t/8529 (PNAD Contínua trimestral) v/12466 taxa de "
            "informalidade 14+ ocupados (%), n3 (27 UFs), 2024T1-2025T4; "
            + _vintage(RAW_INFORMALIDADE) +
            "; cache data/raw/sidra_informalidade/"
            "informalidade_8529_2024_2025.json")


# ==================================================================== E4
@functools.lru_cache(maxsize=1)
def _trimestres_1846() -> pd.DataFrame:
    """PIB e consumo das famílias trimestrais → DataFrame[tri, ano,
    pib_rs_mi, cfam_rs_mi] com exatamente 44 trimestres (2015T1-2025T4).

    Falha cedo se faltar trimestre, série ou vier duplicata (pivot estrito).
    """
    MANIFEST.registra_arquivo(RAW_CNT_1846)
    MANIFEST.registra_arquivo(RAW_CNT_1846.parent /
                              (RAW_CNT_1846.name + "._meta.json"))
    linhas = json.loads(RAW_CNT_1846.read_text(encoding="utf-8"))[1:]  # [0]=cabeçalho SIDRA
    df = pd.DataFrame({
        "tri": [r["D3C"] for r in linhas],
        "serie": [r["D4C"] for r in linhas],
        "valor": [float(r["V"]) for r in linhas],
    })
    series = set(df["serie"])
    if series != {_COD_PIB, _COD_CFAM}:
        raise ValueError(f"t/1846: séries inesperadas: {series}")
    piv = (df.pivot(index="tri", columns="serie", values="valor")  # estrito
             .rename(columns={_COD_PIB: "pib_rs_mi", _COD_CFAM: "cfam_rs_mi"})
             .reset_index().sort_values("tri", ignore_index=True))
    piv["ano"] = piv["tri"].str[:4].astype(int)
    n_esperado = 4 * len(_ANOS_DECADA)
    if len(piv) != n_esperado or piv[["pib_rs_mi", "cfam_rs_mi"]].isna().any().any():
        raise ValueError(f"t/1846: esperados {n_esperado} trimestres completos, "
                         f"obtidos {len(piv)}")
    por_ano = piv.groupby("ano").size()
    if sorted(por_ano.index) != list(_ANOS_DECADA) or (por_ano != 4).any():
        raise ValueError("t/1846: cobertura anual incompleta (4 tri/ano exigidos)")
    return piv


@functools.lru_cache(maxsize=1)
def serie_s_anual() -> pd.DataFrame:
    """Participação s = consumo das famílias ÷ PIB por ano civil (soma de
    4 trimestres correntes; razão de nominais — deflator cancela)."""
    q = _trimestres_1846()
    ann = q.groupby("ano", as_index=False)[["cfam_rs_mi", "pib_rs_mi"]].sum()
    ann["s"] = ann["cfam_rs_mi"] / ann["pib_rs_mi"]
    return ann


def s_corrente() -> Num:
    """s da janela de receita 2024-2025 (Σ 8 trimestres — razão agregada,
    não média das razões anuais)."""
    q = _trimestres_1846()
    j = q[q["ano"].isin(_ANOS_JANELA)]
    return MANIFEST.registra("e4_s_corrente_2024_2025", Num(
        float(j["cfam_rs_mi"].sum() / j["pib_rs_mi"].sum()),
        "Σ8tri consumo das famílias ÷ Σ8tri PIB, 2024T1-2025T4",
        _fonte_1846(), Label.DERIVADO, "razão consumo famílias/PIB"))


def extremos_decada() -> dict[str, Num]:
    """Mínimo e máximo de s na década 2015-2025, com os anos de ocorrência
    (empate: primeiro ano — determinístico via idxmin/idxmax)."""
    ann = serie_s_anual()
    i_min, i_max = int(ann["s"].idxmin()), int(ann["s"].idxmax())
    out = {}
    for rot, i in (("min", i_min), ("max", i_max)):
        ano = int(ann.loc[i, "ano"])
        out[rot] = MANIFEST.registra(f"e4_s_{rot}_decada", Num(
            float(ann.loc[i, "s"]),
            f"{'mín' if rot == 'min' else 'máx'}{{s_anual: 2015-2025}} "
            f"(ocorre em {ano})", _fonte_1846(), Label.DERIVADO,
            "razão consumo famílias/PIB"))
        out[f"ano_{rot}"] = ano
    return out


@functools.lru_cache(maxsize=1)
def tau_central_corrente_pp() -> Num:
    """Soma central corrente (CBS+IBS_E+IBS_M, p.p.) lida de
    aferir_nacional.csv — RE-BASELINE declarado: o painel nacional está em
    regeneração por outros itens da revisão; a elasticidade E4 deve ser
    relida do CSV regenerado (a razão Δτ/τ independe do nível)."""
    csv = config.PROCESSED / "aferir_nacional.csv"
    MANIFEST.registra_arquivo(csv)
    df = pd.read_csv(csv)
    m = pd.Series(True, index=df.index)
    for col, v in _FILTRO_CENTRAL.items():
        m &= df[col] == v
    sel = df[m]
    if len(sel) != 1:
        raise ValueError(f"aferir_nacional.csv: cenário central não é único "
                         f"({len(sel)} linhas para {_FILTRO_CENTRAL})")
    return MANIFEST.registra("e4_tau_central_corrente_pp", Num(
        float(sel["soma_pp"].iloc[0]),
        "soma_pp do cenário central (γ=0,125; ψ=0; iso_carga; proxy_ipi_rfb; "
        "liquida_rtn) — sujeito a re-baseline do painel nacional",
        "data/processed/aferir_nacional.csv", Label.DERIVADO, "p.p."))


def grava_sens_base_pib() -> pd.DataFrame:
    """Monta e grava sens_base_pib.csv (série anual + agregados E4).

    Linhas agregadas além da série (colunas chave/valor adicionadas ao
    esquema mínimo para identificá-las):
      * s_corrente (janela 2024-2025), s_min_decada, s_max_decada;
      * fator_reescala_{min,max} = s_extremo ÷ s_corrente — o orquestrador
        multiplica B_C e B_ISFLSF por esse fator nos cenários
        sens_base_pib_{min,max};
      * delta_tau_aprox_{min,max}_pp: Δτ ≈ −τ·Δs/s (τ = soma central);
      * tau_central_corrente_pp (nível de referência, re-baselinável);
      * identidade_estacionariedade = 1 (hipótese nomeada).
    """
    ann = serie_s_anual()
    s_cur = s_corrente()
    ext = extremos_decada()
    s_min, s_max = ext["min"], ext["max"]
    tau = tau_central_corrente_pp()

    fator, delta = {}, {}
    for rot, s_ext in (("min", s_min), ("max", s_max)):
        fator[rot] = MANIFEST.registra(f"e4_fator_reescala_{rot}", Num(
            s_ext.valor / s_cur.valor,
            f"s_{rot}_decada ÷ s_corrente — multiplicar B_C e B_ISFLSF no "
            f"cenário sens_base_pib_{rot}",
            "sens_base_pib.csv (t/1846)", Label.DERIVADO, "adimensional"))
        delta[rot] = MANIFEST.registra(f"e4_delta_tau_aprox_{rot}_pp", Num(
            -tau.valor * (s_ext.valor - s_cur.valor) / s_cur.valor,
            f"Δτ ≈ −τ·Δs/s; Δs = s_{rot}_decada − s_corrente; "
            "τ = soma central corrente (re-baselinável)",
            "sens_base_pib.csv + aferir_nacional.csv", Label.DERIVADO, "p.p."))

    identidade = MANIFEST.registra("e4_identidade_estacionariedade", Num(
        1.0,
        "τ_2033/τ_2024-25 = (base/PIB)_2024-25 ÷ (base/PIB)_2033 — sob a "
        "hipótese de participação estável da base no PIB a razão vale 1",
        "hipótese nomeada (plano de revisão E4); séries: " + _fonte_1846(),
        Label.CONVENCAO, "adimensional"))

    f_serie = "s = Σ4tri consumo das famílias ÷ Σ4tri PIB (ano civil, nominais)"
    linhas = [{
        "chave": "s_anual", "ano": str(int(r["ano"])),
        "cfam_rs_mi": r["cfam_rs_mi"], "pib_rs_mi": r["pib_rs_mi"],
        "s": r["s"], "valor": r["s"],
        "formula": f_serie, "fonte": _fonte_1846(),
    } for _, r in ann.iterrows()]

    j = _trimestres_1846()[lambda d: d["ano"].isin(_ANOS_JANELA)]
    agregados = [
        ("s_corrente", "2024-2025", float(j["cfam_rs_mi"].sum()),
         float(j["pib_rs_mi"].sum()), s_cur),
        ("s_min_decada", str(ext["ano_min"]), None, None, s_min),
        ("s_max_decada", str(ext["ano_max"]), None, None, s_max),
        ("fator_reescala_min", "", None, None, fator["min"]),
        ("fator_reescala_max", "", None, None, fator["max"]),
        ("delta_tau_aprox_min_pp", "", None, None, delta["min"]),
        ("delta_tau_aprox_max_pp", "", None, None, delta["max"]),
        ("tau_central_corrente_pp", "", None, None, tau),
        ("identidade_estacionariedade", "", None, None, identidade),
    ]
    for chave, ano, cfam, pib, num in agregados:
        linhas.append({
            "chave": chave, "ano": ano, "cfam_rs_mi": cfam, "pib_rs_mi": pib,
            "s": num.valor if chave.startswith("s_") else None,
            "valor": num.valor, "formula": num.formula, "fonte": num.fonte,
        })

    out = pd.DataFrame(linhas, columns=[
        "chave", "ano", "cfam_rs_mi", "pib_rs_mi", "s", "valor",
        "formula", "fonte"])
    out.to_csv(CSV_SENS_BASE_PIB, index=False)
    return out


# ==================================================================== E5
@functools.lru_cache(maxsize=1)
def informalidade_uf() -> pd.DataFrame:
    """Taxa média de informalidade por UF (média SIMPLES dos 8 trimestres
    2024T1-2025T4) → DataFrame[uf(código IBGE), sigla, taxa_media_pct,
    n_trimestres], ordenado por sigla.

    O mapeamento D1C→sigla é conferido contra o nome oficial D1N linha a
    linha — divergência aborta (o dicionário não pode desviar da fonte).
    """
    MANIFEST.registra_arquivo(RAW_INFORMALIDADE)
    MANIFEST.registra_arquivo(RAW_INFORMALIDADE.parent /
                              (RAW_INFORMALIDADE.name + "._meta.json"))
    linhas = json.loads(RAW_INFORMALIDADE.read_text(encoding="utf-8"))[1:]
    esperado = len(IBGE_UF) * _N_TRIMESTRES_INF
    if len(linhas) != esperado:
        raise ValueError(f"t/8529: esperadas {esperado} linhas, "
                         f"vieram {len(linhas)}")
    regs = []
    for r in linhas:
        cod = r["D1C"]
        if cod not in IBGE_UF:
            raise ValueError(f"t/8529: código de UF desconhecido: {cod}")
        sigla, nome = IBGE_UF[cod]
        if r["D1N"] != nome:
            raise ValueError(f"t/8529: D1C={cod} veio como '{r['D1N']}', "
                             f"dicionário diz '{nome}'")
        regs.append({"uf": int(cod), "sigla": sigla, "taxa": float(r["V"])})
    df = (pd.DataFrame(regs)
          .groupby(["uf", "sigla"], as_index=False)["taxa"]
          .agg(taxa_media_pct="mean", n_trimestres="size")
          .sort_values("sigla", ignore_index=True))
    if (df["n_trimestres"] != _N_TRIMESTRES_INF).any():
        raise ValueError("t/8529: UF sem os 8 trimestres completos")
    return df


@functools.lru_cache(maxsize=1)
def _b_ord() -> pd.Series:
    """Base ordinária B_ord por UF (base_uf.csv) — peso da média nacional e
    da renormalização (γ incide sobre a base de consumo, não sobre pessoas)."""
    csv = config.PROCESSED / "base_uf.csv"
    MANIFEST.registra_arquivo(csv)
    b = pd.read_csv(csv).set_index("uf")["B_ord"]
    if sorted(b.index) != sorted(config.UFS):
        raise ValueError("base_uf.csv: conjunto de UFs inesperado")
    if (b <= 0).any():
        raise ValueError("base_uf.csv: B_ord não positivo")
    return b


def informalidade_media_nacional() -> Num:
    """inf̄ = Σ inf_uf·B_ord_uf ÷ Σ B_ord_uf — média nacional ponderada pela
    base ordinária (ponderação DECLARADA; ver docstring do módulo)."""
    inf = informalidade_uf().set_index("sigla")["taxa_media_pct"]
    b = _b_ord()
    return MANIFEST.registra("e5_informalidade_media_nacional_pct", Num(
        float((inf * b).sum() / b.sum()),
        "Σ inf_uf·B_ord_uf ÷ Σ B_ord_uf (ponderada pela base ordinária)",
        _fonte_8529() + "; pesos: data/processed/base_uf.csv (B_ord)",
        Label.DERIVADO, "%"))


def gamma_heterogeneo(beta: float) -> pd.DataFrame:
    """γ_uf renormalizado para um β — DataFrame[uf(sigla), beta, gamma_uf].

    γ_bruto_uf = γ̄·[1+β·(inf_uf−inf̄)/inf̄]; k = γ̄ ÷ média ponderada de
    γ_bruto; γ_uf = k·γ_bruto_uf ⇒ Σ γ_uf·B_ord ÷ Σ B_ord = γ̄ exato (como
    inf̄ é ponderada pelos MESMOS pesos, k≈1 — só limpa poeira de float).
    Valida γ_uf ∈ (0; 0,5) para todas as UFs (domínio de gaps.hiato_total).
    """
    inf = informalidade_uf().set_index("sigla")["taxa_media_pct"]
    b = _b_ord()
    infbar = informalidade_media_nacional().valor
    bruto = GAMMA_BARRA * (1.0 + beta * (inf - infbar) / infbar)
    k = GAMMA_BARRA / float((bruto * b).sum() / b.sum())
    g = (k * bruto).sort_index()
    lo, hi = _DOMINIO_GAMMA
    if not ((g > lo) & (g < hi)).all():
        fora = g[(g <= lo) | (g >= hi)]
        raise ValueError(f"γ_uf fora de ({lo}; {hi}) para β={beta}: "
                         f"{fora.to_dict()}")
    MANIFEST.registra(f"e5_renormalizacao_k_beta_{beta:g}".replace(".", "_"),
                      Num(k, "γ̄ ÷ [Σ γ_bruto_uf·B_ord ÷ Σ B_ord]",
                          "informalidade_uf.csv + base_uf.csv",
                          Label.DERIVADO, "adimensional"))
    return pd.DataFrame({"uf": g.index, "beta": beta, "gamma_uf": g.values})


def grava_informalidade_uf() -> pd.DataFrame:
    """Grava informalidade_uf.csv (27 UFs, média simples de 8 trimestres)."""
    out = informalidade_uf().copy()
    out["formula"] = ("média simples dos 8 trimestres 2024T1-2025T4 da taxa "
                      "de informalidade (v/12466); uf = código IBGE (D1C)")
    out["fonte"] = _fonte_8529()
    out.to_csv(CSV_INFORMALIDADE_UF, index=False)
    return out


def grava_sens_gamma_heterogeneo() -> pd.DataFrame:
    """Grava sens_gamma_heterogeneo.csv (27 UFs × β∈{0,5;1,0} = 54 linhas).

    Entrega os γ_uf prontos e validados; a recomputação dos vetores por
    esfera com o dict {uf: γ_uf} é do pipeline (fora deste módulo).
    """
    partes = [gamma_heterogeneo(beta) for beta in BETAS]
    out = pd.concat(partes, ignore_index=True)
    out["formula"] = (
        "γ_uf = k·γ̄·[1 + β·(inf_uf − inf̄)/inf̄]; γ̄ = 0,125 "
        "(config.GAP_CONFORMIDADE central, corredor SERT/FMI); inf̄ = média "
        "nacional ponderada por B_ord; k renormaliza "
        "Σ γ_uf·B_ord ÷ Σ B_ord = γ̄ exato")
    out["fonte"] = (
        "data/processed/informalidade_uf.csv (SIDRA t/8529 v/12466, média "
        "2024T1-2025T4) + data/processed/base_uf.csv (B_ord); β∈{0,5;1,0} = "
        "grade do plano de revisão (E5)")
    out.to_csv(CSV_SENS_GAMMA, index=False)
    return out


CSV_VETORES_GAMMA_UF = config.PROCESSED / "sens_vetores_gamma_uf.csv"


def grava_sens_vetores_gamma_uf() -> pd.DataFrame:
    """E5: vetores por UF sob γ heterogêneo (β∈{0,5;1,0}) × central γ único.

    Reexecuta o sistema tri-esfera com o dict {uf: γ_uf} e reporta, por β e
    esfera: mediana e máximo de |Δτ_uf| vs o vetor central, nº de UFs acima
    da referência da esfera e nº de pisos do art. 371 vinculantes (piso =
    0,905 × referência da esfera do MESMO cenário — regra de tables.py).
    Grava também os vetores completos (uma linha por UF×β)."""
    from .pipeline import executa  # import tardio (robustez ← pipeline)

    def _vetores(gamma_uf: dict | None) -> tuple[pd.DataFrame, dict]:
        r = executa(gamma_uf=gamma_uf)
        v = pd.DataFrame({
            "uf": sorted(r["vetor_estadual"]),
            "tau_E_uf_pp": [r["vetor_estadual"][u] * 100
                            for u in sorted(r["vetor_estadual"])],
            "tau_M_uf_pp": [r["vetor_municipal"].get(u, float("nan")) * 100
                            for u in sorted(r["vetor_estadual"])],
        })
        ref = {"E": r["sol"].tau_E * 100, "M": r["sol"].tau_M * 100}
        return v, ref

    central_v, central_ref = _vetores(None)
    gam = pd.read_csv(CSV_SENS_GAMMA)
    linhas, resumo = [], []
    for beta in BETAS:
        g_uf = gam[gam["beta"] == beta].set_index("uf")["gamma_uf"].to_dict()
        v, ref = _vetores(g_uf)
        m = v.merge(central_v, on="uf", suffixes=("", "_central"))
        m["beta"] = beta
        linhas.append(m)
        for esf, col in (("E", "tau_E_uf_pp"), ("M", "tau_M_uf_pp")):
            delta = (m[col] - m[f"{col}_central"]).abs().dropna()
            piso = 0.905 * ref[esf]
            piso_c = 0.905 * central_ref[esf]
            resumo.append({
                "beta": beta, "esfera": esf,
                "mediana_abs_delta_pp": float(delta.median()),
                "max_abs_delta_pp": float(delta.max()),
                "n_uf_acima_ref": int((m[col] > ref[esf]).sum()),
                "n_uf_acima_ref_central": int(
                    (m[f"{col}_central"] > central_ref[esf]).sum()),
                "n_piso_vinculante": int((m[col] < piso).sum()),
                "n_piso_vinculante_central": int(
                    (m[f"{col}_central"] < piso_c).sum()),
            })
    vet = pd.concat(linhas, ignore_index=True)
    res = pd.DataFrame(resumo)
    res["uf"] = "RESUMO"
    out = pd.concat([vet, res], ignore_index=True)
    out["formula"] = (
        "vetores: pipeline.executa(gamma_uf={uf: γ_uf}) com γ_uf de "
        "sens_gamma_heterogeneo.csv; piso art. 371 = 0,905 × referência da "
        "esfera do próprio cenário (regra de tables.py); RESUMO = mediana/"
        "máx de |Δτ_uf| vs central, contagens acima da referência e pisos "
        "vinculantes")
    out["fonte"] = ("sens_gamma_heterogeneo.csv × pipeline tri-esfera "
                    "(plano de revisão, E5)")
    out.to_csv(CSV_VETORES_GAMMA_UF, index=False)
    return out


def main() -> None:
    import sys
    base = grava_sens_base_pib()
    inf = grava_informalidade_uf()
    gam = grava_sens_gamma_heterogeneo()
    pd.set_option("display.width", 160)
    print(base[["chave", "ano", "s", "valor"]].round(6).to_string(index=False))
    print()
    print(inf[["uf", "sigla", "taxa_media_pct"]].round(4).to_string(index=False))
    print()
    print(gam.pivot(index="uf", columns="beta", values="gamma_uf")
          .round(6).to_string())
    if "--vetores" in sys.argv[1:]:
        res = grava_sens_vetores_gamma_uf()
        print()
        print(res[res["uf"] == "RESUMO"]
              [["beta", "esfera", "mediana_abs_delta_pp", "max_abs_delta_pp",
                "n_uf_acima_ref", "n_piso_vinculante"]]
              .round(4).to_string(index=False))


if __name__ == "__main__":
    main()
