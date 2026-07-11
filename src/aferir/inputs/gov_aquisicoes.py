"""Compras governamentais G por esfera (LC 214, arts. 472-473) — camada de dados.

Constrói, a partir dos caches SICONFI (DCA Anexo I-D):
  * data/processed/g_perimetros.csv — G por esfera × PERÍMETRO de elementos de
    despesa × chave da natureza 36 × estágio (revisão A5);
  * data/processed/g_esferas.csv — perímetro CENTRAL do artigo (custeio
    ampliado COM a natureza 36), estágio Despesas Empenhadas;
  * data/processed/g_municipal_sensibilidade.csv — corredor S1-S3 + variantes
    por perímetro;
  * data/processed/sigma_compras.csv — σ do redutor iso-carga (art. 370)
    coerente com cada perímetro (custeio × capital — ver aferir.inputs.tru).

Perímetros (elementos de despesa da Portaria Interministerial STN/SOF
163/2001, Anexo II; MTO cap. 4, item 4.6.2.1.4):
  * G_min     = 3.3.90.{30,39} — material de consumo e serviços PJ;
  * G_central = 3.3.90.{30,32,33,37,39,40} — custeio ampliado (32 material p/
    distribuição gratuita, 33 passagens e locomoção, 37 locação de mão de
    obra, 40 serviços de TIC-PJ);
  * G_max     = G_central + 4.4.90.{51,52} — obras e instalações e
    equipamentos/material permanente (capital).
  * natureza 3.3.90.36 (serviços de terceiros — PESSOA FÍSICA) é CHAVE
    dentro/fora em todos os perímetros: PF pode estar fora do campo de
    incidência regular do IBS/CBS (não contribuinte). O central do artigo
    é G_central COM a natureza 36.
  * 4.4.90.40 (TIC-PJ em capital) NÃO entra em nenhum perímetro: o elemento
    40 é serviço de TIC, não contraparte automática de capital (A5, item 2).

ADAPTAÇÃO DECLARADA (verificada nos caches em 12/07/2026): a DCA do SICONFI
é CONSOLIDADA por ente (coluna `instituicao` única — 'Governo Federal' /
'Governo do Estado de X'), SEM abertura administração direta × autarquias ×
estatais dependentes. Os perímetros diferem, portanto, apenas pelo conjunto
de elementos de despesa; a distinção institucional do superdocumento
(central = adm. direta+autarquias+fundações; max = consolidado c/ estatais
dependentes) NÃO é observável em dado aberto — fronteira OD/ADM.

União = DCA id_ente=1; Estados = DCA das 27 UFs; Municípios = amostra
capitais+top-200 com extrapolação PÓS-ESTRATIFICADA para o universo:

    G_M(ano) = G_amostra(ano) + Σ_s pop_resto_s × gpc_s(2023) × infl(ano)

onde gpc_s(2023) = Σ G_i / Σ pop_i por estrato populacional na subamostra
municipal FIXADA de 2023 (composição pinada em
data/inputs/amostra_dca_municipal.csv) e infl(ano) = razão de crescimento
medida nos municípios da amostra presentes também na subamostra, POR
variante (perímetro × natureza 36). Aproximação DECLARADA (fallback FINBRA).

Estágio central = Despesas Empenhadas (convenção FINBRA); Despesas
Liquidadas como sensibilidade (municípios: só a amostra, cota inferior).
Valores em R$ correntes do exercício (a deflação ocorre no motor).

Determinístico: mesmos caches ⇒ mesmos bytes nos CSVs (sem datetime aqui).

Execução: PYTHONPATH=src python3 -m aferir.inputs.gov_aquisicoes
"""
from __future__ import annotations

import functools
import glob
from pathlib import Path

import pandas as pd

from aferir.config import (
    COD_IBGE_BRASILIA,
    DCA_ANEXO_DESPESA,
    ESTAGIO_G473,
    ESTAGIO_G473_SENSIBILIDADE,
    G473_ANO_ESTRATOS,
    G473_ESTRATOS_POP,
    JANELA_RECEITA,
    PROCESSED,
    RAW_DCA_MUN_DIR,
    SICONFI_API,
    UFS,
)
from aferir.fetch.siconfi_estadual import carrega_anexo_id
from aferir.fetch.siconfi_municipal import entes_municipais
from aferir.fetch.siconfi_municipal_g import (
    STATUS_OK,
    amostra_g,
    caminho_dca_g,
)
from aferir.fetch.siconfi_uniao import caminho_dca_uniao
from aferir.provenance import MANIFEST, Label, Num

# ------------------------------------------------------------- perímetros (A5)
# Elementos de despesa: Portaria Interministerial STN/SOF 163/2001, Anexo II
# (atualizada; elemento 40 incluído pela Portaria Conjunta STN/SOF 103/2021);
# MTO cap. 4, item 4.6.2.1.4. Modalidade 90 (aplicações diretas);
# intra-orçamentárias (33.91/44.91) excluídas.
NATUREZA_PF = "3.3.90.36"                 # serviços de terceiros — pessoa física
NATUREZAS_CUSTEIO_MIN = ("3.3.90.30", "3.3.90.39")
NATUREZAS_CUSTEIO_AMPLIADO = (
    "3.3.90.30", "3.3.90.32", "3.3.90.33", "3.3.90.37", "3.3.90.39", "3.3.90.40",
)
NATUREZAS_CAPITAL = ("4.4.90.51", "4.4.90.52")
PERIMETROS = {
    "min": NATUREZAS_CUSTEIO_MIN,
    "central": NATUREZAS_CUSTEIO_AMPLIADO,
    "max": NATUREZAS_CUSTEIO_AMPLIADO + NATUREZAS_CAPITAL,
}
CHAVES_N36 = ("com36", "sem36")
ESTAGIOS = {"empenhadas": ESTAGIO_G473,
            "liquidadas": ESTAGIO_G473_SENSIBILIDADE}

NATUREZAS_TODAS = tuple(sorted(set(PERIMETROS["max"]) | {NATUREZA_PF}))
# Na API o cod_conta vem como 'DO' + natureza a 8 dígitos + '.00.00' (nível de
# elemento — os desdobramentos .80/.91/.99 SOMAM no elemento; usar só o pai).
COD_CONTA = {nat: f"DO{nat}.00.00" for nat in NATUREZAS_TODAS}
COLS_NATUREZA = {nat: "g_" + nat.replace(".", "") for nat in NATUREZAS_TODAS}
# -> g_339030, g_339032, g_339033, g_339036, g_339037, g_339039, g_339040,
#    g_449051, g_449052
COLS_ORDENADAS = [COLS_NATUREZA[n] for n in NATUREZAS_TODAS]


def naturezas_de(perimetro: str, natureza36: bool = True) -> tuple[str, ...]:
    """Naturezas do perímetro, com a chave da natureza 36 (PF) dentro/fora."""
    nats = set(PERIMETROS[perimetro])
    if natureza36:
        nats.add(NATUREZA_PF)
    return tuple(sorted(nats))


def _cols_de(perimetro: str, natureza36: bool) -> list[str]:
    return [COLS_NATUREZA[n] for n in naturezas_de(perimetro, natureza36)]


FONTE_DCA = (
    f"SICONFI DCA '{DCA_ANEXO_DESPESA}' ({SICONFI_API}/dca); LC 214 arts. "
    "472-473 (aquisições; folha fora, art. 4o); elementos de despesa Portaria "
    "Interm. STN/SOF 163/2001 Anexo II (MTO 4.6.2.1.4); DCA CONSOLIDADA do "
    "ente (instituicao unica — sem abertura adm. direta x estatais "
    "dependentes; perimetros diferem apenas pelo conjunto de elementos)"
)


def _formula_perimetro(perimetro: str, natureza36: bool, estagio: str) -> str:
    nats = "+".join(naturezas_de(perimetro, natureza36))
    return (f"G_{perimetro} = SUM(valor | cod_conta in elementos {nats}, "
            f"coluna='{ESTAGIOS[estagio]}')")


ESTRATO_LABELS = ["ate_5k", "5k_10k", "10k_20k", "20k_50k", "50k_100k", "acima_100k"]

MUN_DCA_GLOB = str(RAW_DCA_MUN_DIR / f"dca_mun_*_{G473_ANO_ESTRATOS}.parquet")


# ---------------------------------------------------------------- helpers
def _valores_naturezas(df: pd.DataFrame, estagio_label: str) -> dict[str, float]:
    """Valor de cada elemento-alvo num Anexo I-D (um ente/exercício)."""
    sel = df[df["coluna"] == estagio_label]
    out = {}
    for nat, cod in COD_CONTA.items():
        out[COLS_NATUREZA[nat]] = float(sel.loc[sel["cod_conta"] == cod, "valor"].sum())
    return out


def _soma_cols(vals: dict[str, float] | pd.Series, cols: list[str]) -> float:
    return float(sum(vals[c] for c in cols))


# ---------------------------------------------------------------- União
def medicoes_uniao(anos: list[int]) -> pd.DataFrame:
    """Elementos-alvo da União por ano × estágio (DCA id_ente=1)."""
    linhas = []
    for ano in anos:
        df = pd.read_parquet(caminho_dca_uniao(ano))
        for estagio, label in ESTAGIOS.items():
            linhas.append({
                "esfera": "uniao", "uf": "BR", "ano": ano, "estagio": estagio,
                **_valores_naturezas(df, label),
            })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- Estados
def medicoes_estadual(anos: list[int]) -> pd.DataFrame:
    """Elementos-alvo das 27 UFs por ano × estágio (DCA integral)."""
    linhas = []
    for ano in anos:
        for uf in UFS:
            sel = carrega_anexo_id(uf, ano)
            for estagio, label in ESTAGIOS.items():
                linhas.append({
                    "esfera": "estadual", "uf": uf, "ano": ano,
                    "estagio": estagio, **_valores_naturezas(sel, label),
                })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- Municípios
@functools.lru_cache(maxsize=1)
def _subamostra_2023() -> pd.DataFrame:
    """Elementos-alvo por município na subamostra fixada de 2023 (empenhadas).

    Stream: um parquet por vez, guardando só os 9 elementos + população
    (memória O(n municípios), não O(n linhas))."""
    arquivos = sorted(glob.glob(MUN_DCA_GLOB))
    if not arquivos:
        raise FileNotFoundError(f"subamostra municipal ausente (make fetch): {MUN_DCA_GLOB}")
    linhas = []
    cols = ["anexo", "cod_conta", "coluna", "valor", "cod_ibge", "populacao"]
    for f in arquivos:
        d = pd.read_parquet(f, columns=cols)
        cod = int(d["cod_ibge"].iloc[0])
        pop = int(d["populacao"].iloc[0])
        dd = d[d["anexo"] == DCA_ANEXO_DESPESA]
        if dd.empty:                      # ente sem Anexo I-D no exercício
            continue
        linhas.append({"cod_ibge": cod, "populacao": pop,
                       **_valores_naturezas(dd, ESTAGIO_G473)})
    return pd.DataFrame(linhas).sort_values("cod_ibge").reset_index(drop=True)


def estratos_v1_2023() -> pd.DataFrame:
    """gpc por estrato populacional × elemento na subamostra aleatória v1 (2023).

    Ratio estimator por estrato: gpc_s = Σ G_i / Σ pop_i (municípios da
    subamostra fixada FORA da amostra capitais+top-200). Cacheado em
    data/processed/g_mun_estratos_2023.csv; o cache é invalidado se não tiver
    as colunas do perímetro ampliado (revisão A5)."""
    path = PROCESSED / f"g_mun_estratos_{G473_ANO_ESTRATOS}.csv"
    if path.exists():
        cached = pd.read_csv(path)
        if "gpc_g_449052" in cached.columns:
            return cached

    excluir = set(amostra_g()["cod_ibge"].astype(int)) | {COD_IBGE_BRASILIA}
    base = _subamostra_2023()
    base = base[~base["cod_ibge"].isin(excluir)].copy()
    base["g_aquisicoes"] = base[_cols_de("central", True)].sum(axis=1)
    base["estrato"] = pd.cut(
        base["populacao"], bins=list(G473_ESTRATOS_POP), labels=ESTRATO_LABELS,
        right=True,
    )
    agg = (
        base.groupby("estrato", observed=True)
        .agg(
            n_municipios=("cod_ibge", "nunique"),
            pop_total=("populacao", "sum"),
            **{c: (c, "sum") for c in COLS_ORDENADAS + ["g_aquisicoes"]},
        )
        .reset_index()
    )
    for c in COLS_ORDENADAS + ["g_aquisicoes"]:
        agg[f"gpc_{c}"] = agg[c] / agg["pop_total"]
    agg["fonte"] = (
        f"subamostra municipal fixada ({len(base)} municipios ex-amostra, "
        f"dca_mun_*_{G473_ANO_ESTRATOS}.parquet, composicao em "
        f"data/inputs/amostra_dca_municipal.csv, API {SICONFI_API}/dca)"
    )
    agg["formula"] = ("gpc_s = SUM(G_i)/SUM(pop_i) por estrato populacional e "
                      "elemento; g_aquisicoes = perimetro central COM natureza 36")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    agg.to_csv(path, index=False)
    return agg


def _g_amostra(ano: int, estagio: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(elementos-alvo por município medido na amostra, municípios sem DCA)."""
    bruto = pd.read_parquet(caminho_dca_g(ano))
    ok = bruto[bruto["status"] == STATUS_OK]
    linhas = []
    for cod, d in ok.groupby("cod_ibge_ente"):
        linhas.append({
            "cod_ibge": int(cod),
            "populacao": int(d["populacao_ente"].iloc[0]),
            **_valores_naturezas(d, ESTAGIOS[estagio]),
        })
    medidos = pd.DataFrame(linhas).sort_values("cod_ibge").reset_index(drop=True)
    sem_dca = bruto[bruto["status"] != STATUS_OK][
        ["cod_ibge_ente", "populacao_ente"]
    ].drop_duplicates()
    return medidos, sem_dca


def _inflator(medidos: pd.DataFrame, cols: list[str]) -> tuple[float, int]:
    """Crescimento 2023→ano do perímetro `cols` medido nos municípios da
    amostra presentes na subamostra fixada (mesmo estágio Empenhadas)."""
    sub = _subamostra_2023()
    comuns = sorted(set(medidos["cod_ibge"]) & set(sub["cod_ibge"]))
    if not comuns:
        return 1.0, 0
    g23 = float(sub.loc[sub["cod_ibge"].isin(comuns), cols].sum().sum())
    g_ano = float(medidos.loc[medidos["cod_ibge"].isin(comuns), cols].sum().sum())
    if g23 <= 0:
        return 1.0, len(comuns)
    return g_ano / g23, len(comuns)


def _extrapola(medidos: pd.DataFrame, estratos: pd.DataFrame,
               pop_resto: pd.Series, cols: list[str]) -> tuple[float, float, int]:
    """(G extrapolado do resto, inflator, n_comuns) para o perímetro `cols`."""
    infl, n_comuns = _inflator(medidos, cols)
    idx = estratos.set_index("estrato")
    gpc = sum(idx[f"gpc_{c}"] for c in cols)
    ext = float((pop_resto * gpc).dropna().sum()) * infl
    return ext, infl, n_comuns


def g_municipal(anos: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(linhas centrais p/ g_esferas, sensibilidade S1-S3+perímetros,
    linhas municipais p/ g_perimetros)."""
    estratos = estratos_v1_2023()
    universo = entes_municipais()
    universo = universo[universo["cod_ibge"] != COD_IBGE_BRASILIA]

    centrais, sens, perims = [], [], []
    for ano in anos:
        medidos, _ = _g_amostra(ano, "empenhadas")
        liq, _ = _g_amostra(ano, "liquidadas")
        # resto = universo − municípios MEDIDOS no ano (amostrados omissos
        # recaem na extrapolação por estrato)
        resto = universo[~universo["cod_ibge"].isin(set(medidos["cod_ibge"]))].copy()
        resto["estrato"] = pd.cut(
            resto["populacao"], bins=list(G473_ESTRATOS_POP),
            labels=ESTRATO_LABELS, right=True,
        )
        pop_resto = resto.groupby("estrato", observed=True)["populacao"].sum()

        pop_amostra = int(medidos["populacao"].sum())
        pop_univ = int(universo["populacao"].sum())
        share_pop = pop_amostra / pop_univ

        # ---- todas as células perímetro × natureza36 (empenhadas extrapoladas
        #      + liquidadas amostra) para g_perimetros.csv
        centrais_variante = {}
        for perimetro in PERIMETROS:
            for chave in CHAVES_N36:
                n36 = chave == "com36"
                cols = _cols_de(perimetro, n36)
                g_am = float(medidos[cols].sum().sum())
                ext, infl, n_comuns = _extrapola(medidos, estratos, pop_resto, cols)
                central = g_am + ext
                centrais_variante[(perimetro, chave)] = {
                    "central": central, "amostra": g_am, "infl": infl,
                    "n_comuns": n_comuns,
                    "liquidadas_amostra": float(liq[cols].sum().sum()),
                }
                perims.append({
                    "esfera": "municipal", "uf": "BR", "ano": ano,
                    "perimetro": perimetro, "natureza36": chave,
                    "estagio": "empenhadas", "valor_rs": central,
                    "formula": (
                        "G_M = SUM(amostra) + SUM_s(pop_resto_s*gpc_s_2023)"
                        f"*infl({infl:.4f}); "
                        + _formula_perimetro(perimetro, n36, "empenhadas")
                    ),
                    "fonte": FONTE_DCA + "; amostra capitais+top200 + "
                    "subamostra aleatoria v1 2023 (pos-estratificacao)",
                })
                perims.append({
                    "esfera": "municipal", "uf": "BR", "ano": ano,
                    "perimetro": perimetro, "natureza36": chave,
                    "estagio": "liquidadas",
                    "valor_rs": centrais_variante[(perimetro, chave)]
                    ["liquidadas_amostra"],
                    "formula": ("G_M = SUM(amostra) SEM extrapolacao (cota "
                                "inferior, sensibilidade S3); "
                                + _formula_perimetro(perimetro, n36, "liquidadas")),
                    "fonte": FONTE_DCA + "; amostra capitais+top200 (sem "
                    "extrapolacao — cota inferior declarada)",
                })

        # ---- linha central de g_esferas.csv: perímetro central COM 36,
        #      empenhadas, extrapolação por elemento com o inflator central
        cols_central = _cols_de("central", True)
        infl_c = centrais_variante[("central", "com36")]["infl"]
        n_comuns = centrais_variante[("central", "com36")]["n_comuns"]
        idx = estratos.set_index("estrato")
        por_elemento = {}
        for c in cols_central:
            ext_c = float((pop_resto * idx[f"gpc_{c}"]).dropna().sum()) * infl_c
            por_elemento[c] = float(medidos[c].sum()) + ext_c
        centrais.append({
            "esfera": "municipal", "uf": "BR", "ano": ano,
            **{c: por_elemento.get(c, 0.0) for c in COLS_ORDENADAS},
            "g_aquisicoes": sum(por_elemento.values()),
            "estagio": ESTAGIO_G473,
            "metodo": (
                f"amostra capitais+top200 ({len(medidos)} medidos; "
                f"{share_pop:.1%} da populacao municipal ex-DF) + extrapolacao "
                f"pos-estratificada (gpc {G473_ANO_ESTRATOS} x pop resto x "
                f"infl={infl_c:.4f}, n_comuns={n_comuns}); APROXIMACAO declarada "
                "(fallback FINBRA/hCaptcha) — sensibilidades em "
                "g_municipal_sensibilidade.csv"
            ),
            "formula": (
                "G_M = SUM(amostra) + SUM_s(pop_resto_s*gpc_s_2023)*infl; "
                + _formula_perimetro("central", True, "empenhadas")
            ),
            "fonte": FONTE_DCA + "; amostra + subamostra aleatoria v1 2023",
        })

        # ---- sensibilidade: variantes herdadas (S1-S3, agora no novo central)
        #      + corredor por perímetro
        cc = centrais_variante[("central", "com36")]
        sens.extend([
            {"ano": ano, "variante": "central_pos_estratificada",
             "g_aquisicoes": cc["central"],
             "formula": "G_amostra + extrapolacao por estrato x inflator "
             "(perimetro central COM natureza 36)",
             "fonte": FONTE_DCA},
            {"ano": ano, "variante": "S1_escala_populacional",
             "g_aquisicoes": cc["amostra"] / share_pop,
             "formula": f"G_amostra / share_pop ({share_pop:.4f}); perimetro "
             "central COM natureza 36",
             "fonte": FONTE_DCA},
            {"ano": ano, "variante": "S2_cota_inferior_amostra",
             "g_aquisicoes": cc["amostra"],
             "formula": "G_amostra sem extrapolacao (cota inferior); perimetro "
             "central COM natureza 36",
             "fonte": FONTE_DCA},
            {"ano": ano, "variante": "S3_liquidadas_amostra",
             "g_aquisicoes": cc["liquidadas_amostra"],
             "formula": f"G_amostra, estagio '{ESTAGIO_G473_SENSIBILIDADE}'; "
             "perimetro central COM natureza 36",
             "fonte": FONTE_DCA},
        ])
        for perimetro in PERIMETROS:
            for chave in CHAVES_N36:
                v = centrais_variante[(perimetro, chave)]
                sens.append({
                    "ano": ano,
                    "variante": f"perimetro_{perimetro}_{chave}",
                    "g_aquisicoes": v["central"],
                    "formula": ("G_amostra + extrapolacao por estrato x "
                                f"inflator ({v['infl']:.4f}); "
                                + _formula_perimetro(perimetro,
                                                     chave == "com36",
                                                     "empenhadas")),
                    "fonte": FONTE_DCA,
                })
    return pd.DataFrame(centrais), pd.DataFrame(sens), pd.DataFrame(perims)


# ---------------------------------------------------------------- g_perimetros
def _perimetros_de_medicoes(med: pd.DataFrame) -> pd.DataFrame:
    """Grade perímetro × natureza36 × estágio a partir das medições diretas
    (União/Estados — DCA integral do ente)."""
    linhas = []
    for _, r in med.iterrows():
        for perimetro in PERIMETROS:
            for chave in CHAVES_N36:
                n36 = chave == "com36"
                cols = _cols_de(perimetro, n36)
                linhas.append({
                    "esfera": r["esfera"], "uf": r["uf"], "ano": r["ano"],
                    "perimetro": perimetro, "natureza36": chave,
                    "estagio": r["estagio"],
                    "valor_rs": _soma_cols(r, cols),
                    "formula": _formula_perimetro(perimetro, n36, r["estagio"]),
                    "fonte": FONTE_DCA + (
                        "; id_ente=1 (Governo Federal)" if r["esfera"] == "uniao"
                        else f"; id_ente={r['uf']}"
                        + ("; DCA unica do GDF — inclui funcoes municipais "
                           "(art. 349, II, 'c')" if r["uf"] == "DF" else "")
                    ),
                })
    return pd.DataFrame(linhas)


COLUNAS_PERIMETROS = [
    "esfera", "uf", "ano", "perimetro", "natureza36", "estagio",
    "valor_rs", "unidade", "formula", "fonte",
]

# ---------------------------------------------------------------- saída
COLUNAS_G = [
    "esfera", "uf", "ano", "g_aquisicoes",
    "g_339030", "g_339032", "g_339033", "g_339036", "g_339037", "g_339039",
    "g_339040",
    "unidade", "estagio", "metodo", "formula", "fonte",
]


def constroi_g_esferas(anos: list[int] | None = None) -> pd.DataFrame:
    anos = anos or list(JANELA_RECEITA)
    uni = medicoes_uniao(anos)
    est = medicoes_estadual(anos)
    mun_central, sens, mun_perims = g_municipal(anos)

    # ---- g_perimetros.csv (grade completa das 3 esferas)
    gper = pd.concat(
        [_perimetros_de_medicoes(uni), _perimetros_de_medicoes(est), mun_perims],
        ignore_index=True,
    )
    gper["unidade"] = "R$ correntes do exercicio"
    gper = (
        gper[COLUNAS_PERIMETROS]
        .sort_values(["ano", "esfera", "uf", "perimetro", "natureza36", "estagio"])
        .reset_index(drop=True)
    )
    PROCESSED.mkdir(parents=True, exist_ok=True)
    gper.to_csv(PROCESSED / "g_perimetros.csv", index=False, float_format="%.2f")

    # ---- g_esferas.csv: NOVO central do artigo = perímetro central COM a
    #      natureza 36, estágio Empenhadas (revisão A5)
    cols_central = _cols_de("central", True)
    direto = pd.concat([uni, est], ignore_index=True)
    direto = direto[direto["estagio"] == "empenhadas"].copy()
    direto["g_aquisicoes"] = direto[cols_central].sum(axis=1)
    direto["estagio"] = ESTAGIO_G473
    direto["metodo"] = direto["esfera"].map({
        "uniao": "DCA integral do ente (id_ente=1)",
        "estadual": "DCA integral do ente (hash em _seed_manifest.json)",
    })
    direto["formula"] = _formula_perimetro("central", True, "empenhadas")
    direto["fonte"] = FONTE_DCA + direto.apply(
        lambda r: "; id_ente=1 (Governo Federal)" if r["esfera"] == "uniao"
        else f"; id_ente={r['uf']}"
        + ("; DCA unica do GDF — inclui funcoes municipais (art. 349, II, 'c')"
           if r["uf"] == "DF" else ""), axis=1)

    df = pd.concat([direto, mun_central], ignore_index=True)
    df["unidade"] = "R$ correntes do exercicio"
    df = (
        df[COLUNAS_G]
        .sort_values(["ano", "esfera", "uf"])
        .reset_index(drop=True)
    )
    df.to_csv(PROCESSED / "g_esferas.csv", index=False, float_format="%.2f")
    sens.to_csv(PROCESSED / "g_municipal_sensibilidade.csv", index=False,
                float_format="%.2f")

    for ano in anos:
        d = df[df["ano"] == ano]
        for esfera in ("uniao", "estadual", "municipal"):
            valor = float(d.loc[d["esfera"] == esfera, "g_aquisicoes"].sum())
            MANIFEST.registra(
                f"g_{esfera}_{ano}",
                Num(
                    valor=valor,
                    formula=_formula_perimetro("central", True, "empenhadas")
                    if esfera != "municipal"
                    else "G_amostra + extrapolacao pos-estratificada "
                    "(perimetro central COM natureza 36)",
                    fonte=FONTE_DCA,
                    label=Label.DADO if esfera != "municipal" else Label.DERIVADO,
                    unidade="R$ correntes",
                ),
            )
    MANIFEST.registra_arquivo(PROCESSED / "g_esferas.csv")
    MANIFEST.registra_arquivo(PROCESSED / "g_perimetros.csv")

    constroi_sigma_compras(uni, est, mun_central)
    return df


# ---------------------------------------------------------------- σ por perímetro
def constroi_sigma_compras(uni: pd.DataFrame | None = None,
                           est: pd.DataFrame | None = None,
                           mun_central: pd.DataFrame | None = None) -> pd.DataFrame:
    """sigma_compras.csv — σ do redutor iso-carga (art. 370) POR perímetro.

    σ_custeio = carga embutida no mix do CI das atividades do governo geral
    (TRU 2021 — inalterado, aferir.inputs.tru.carga_embutida_gov). σ_capital =
    média de σ_51 (produtos de construção) e σ_52 (máquinas/equipamentos)
    ponderada pela participação dos elementos 4.4.90.51 e 4.4.90.52 no capital
    de G (3 esferas, média da janela deflacionada, empenhadas, COM natureza
    36). σ_perimetro = média de σ_custeio e σ_capital ponderada pela
    composição custeio/capital do perímetro (min/central: capital = 0).
    """
    from aferir.inputs.ipca_pib import deflator_para_2024
    from aferir.inputs.tru import carga_embutida_fbcf, carga_embutida_gov

    if uni is None or est is None or mun_central is None:
        anos = list(JANELA_RECEITA)
        uni = medicoes_uniao(anos)
        est = medicoes_estadual(anos)
        mun_central, _, _ = g_municipal(anos)

    # composição custeio × capital: 3 esferas, empenhadas, média da janela
    # deflacionada p/ ANO_PRECOS. Capital municipal: extrapolação por elemento
    # já embutida em mun_central (gpc por estrato). mun_central NÃO tem capital
    # (é o perímetro central) — os elementos de capital municipais vêm da
    # mesma pós-estratificação, medidos aqui diretamente.
    defl = {2024: 1.0, 2025: deflator_para_2024(2025).valor}
    med = pd.concat([uni[uni["estagio"] == "empenhadas"],
                     est[est["estagio"] == "empenhadas"]], ignore_index=True)

    def _janela(df: pd.DataFrame, col: str) -> float:
        s = df.groupby("ano")[col].sum()
        return float(sum(s.get(a, 0.0) * defl[a] for a in JANELA_RECEITA) / 2)

    # municipal: reusar g_municipal (extrapolado por elemento no g_esferas
    # central) — capital municipal extrapolado pela grade de perímetros:
    # G_max − G_central com36, por ano (pós-estratificado, empenhadas).
    gper = pd.read_csv(PROCESSED / "g_perimetros.csv")
    mun = gper[(gper["esfera"] == "municipal") & (gper["natureza36"] == "com36")
               & (gper["estagio"] == "empenhadas")]
    mun_max = mun[mun["perimetro"] == "max"].set_index("ano")["valor_rs"]
    mun_cen = mun[mun["perimetro"] == "central"].set_index("ano")["valor_rs"]
    cap_mun = float(sum((mun_max[a] - mun_cen[a]) * defl[a]
                        for a in JANELA_RECEITA) / 2)

    g51 = _janela(med, COLS_NATUREZA["4.4.90.51"])
    g52 = _janela(med, COLS_NATUREZA["4.4.90.52"])
    # partição 51/52 do capital municipal: mesma proporção gpc da subamostra
    w51_sub = estratos_v1_2023()
    s51 = float(w51_sub["g_449051"].sum())
    s52 = float(w51_sub["g_449052"].sum())
    g51 += cap_mun * s51 / (s51 + s52)
    g52 += cap_mun * s52 / (s51 + s52)

    nums_gov = carga_embutida_gov()
    nums_fbcf = carga_embutida_fbcf()
    sig_cust = nums_gov["carga_embutida_gov_central_pct"].valor / 100.0
    sig_51 = nums_fbcf["carga_embutida_fbcf_construcao_pct"].valor / 100.0
    sig_52 = nums_fbcf["carga_embutida_fbcf_maquinas_pct"].valor / 100.0
    w51 = g51 / (g51 + g52)
    sig_cap = w51 * sig_51 + (1.0 - w51) * sig_52

    linhas = []
    for perimetro in PERIMETROS:
        cols_cust = _cols_de(perimetro, True)
        cols_cust = [c for c in cols_cust
                     if c not in (COLS_NATUREZA["4.4.90.51"],
                                  COLS_NATUREZA["4.4.90.52"])]
        cust = float(sum(_janela(med, c) for c in cols_cust))
        # custeio municipal do perímetro (com36, empenhadas, janela)
        mun_p = mun[mun["perimetro"] == perimetro].set_index("ano")["valor_rs"]
        cust_mun = float(sum(mun_p[a] * defl[a] for a in JANELA_RECEITA) / 2)
        if perimetro == "max":
            cust_mun -= cap_mun
        cust += cust_mun
        cap = (g51 + g52) if perimetro == "max" else 0.0
        peso_cust = cust / (cust + cap)
        peso_cap = 1.0 - peso_cust
        sigma = peso_cust * sig_cust + peso_cap * sig_cap
        linhas.append({
            "perimetro": perimetro,
            "sigma": sigma,
            "peso_custeio": peso_cust,
            "peso_capital": peso_cap,
            "sigma_custeio": sig_cust,
            "sigma_capital": sig_cap,
            "formula": (
                "sigma = peso_custeio*sigma_custeio + peso_capital*sigma_capital; "
                "sigma_custeio = mix CI do governo geral (TRU 2021, F8); "
                f"sigma_capital = w51*sigma_51 + w52*sigma_52 (w51={w51:.4f}, "
                "participacao de 4.4.90.51/52 no capital de G, 3 esferas, "
                "media janela 2024-25 deflacionada, empenhadas, com natureza 36); "
                "pesos custeio/capital = composicao do perimetro nas 3 esferas"
            ),
            "fonte": ("IBGE TRU 2021 nivel 68 (t_embutida por produto) x "
                      "SICONFI DCA Anexo I-D (composicao de G); "
                      "LC 214 art. 370 (iso-carga)"),
        })
        MANIFEST.registra(
            f"sigma_compras_{perimetro}_pct",
            Num(sigma * 100.0, linhas[-1]["formula"], linhas[-1]["fonte"],
                Label.DERIVADO, "% do valor das compras"),
        )
    out = pd.DataFrame(linhas)
    out.to_csv(PROCESSED / "sigma_compras.csv", index=False)
    MANIFEST.registra_arquivo(PROCESSED / "sigma_compras.csv")
    return out


def main() -> None:
    df = constroi_g_esferas()
    for ano in sorted(df["ano"].unique()):
        d = df[df["ano"] == ano]
        u = d.loc[d["esfera"] == "uniao", "g_aquisicoes"].sum()
        e = d.loc[d["esfera"] == "estadual", "g_aquisicoes"].sum()
        m = d.loc[d["esfera"] == "municipal", "g_aquisicoes"].sum()
        print(f"[{ano}] G central uniao R$ {u/1e9:.2f} bi | estadual (27 UFs) "
              f"R$ {e/1e9:.2f} bi | municipal R$ {m/1e9:.2f} bi", flush=True)
    sig = pd.read_csv(PROCESSED / "sigma_compras.csv")
    for _, r in sig.iterrows():
        print(f"[sigma] {r['perimetro']}: {r['sigma']*100:.4f}% "
              f"(custeio {r['sigma_custeio']*100:.4f}% x {r['peso_custeio']:.3f}"
              f" + capital {r['sigma_capital']*100:.4f}% x {r['peso_capital']:.3f})",
              flush=True)


if __name__ == "__main__":
    main()
