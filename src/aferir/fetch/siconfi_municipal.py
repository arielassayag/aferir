"""Fetcher SICONFI — receita de referência MUNICIPAL (ISS), exercícios 2024-2025.

Rota (DESIGN §2.3, Municípios):
  * Universo: 5.570 entes municipais do endpoint /entes (esfera 'M').
  * Numerador por município: DCA "Anexo I-C", conta 1.1.1.4.51.1.0 (ISSQN) —
    já consolida principal, multas e dívida ativa (LC 214, art. 350 §1º, III).
    Convenção de coluna: 'Receitas Brutas Realizadas' − 'Outras Deduções da
    Receita' (líquida de restituições; Deduções-FUNDEB não se aplicam ao ISS —
    invariante testa).
  * ISS do DF: somado a R_M (art. 350, III: "Municípios e do Distrito
    Federal"; referência do DF = soma, art. 349, II, 'c'), com fonte='RREO-DF'
    — rubrica ISSLiquidoExcetoTransferenciasEFUNDEB, TOTAL (ÚLTIMOS 12 MESES),
    RREO 6º bimestre Anexo 03. Cache v1 preferido; refetch id_ente=53 se
    ausente.
  * Omissos (⚑ F2): imputação conservadora = mediana do ISS líquido per
    capita dos declarantes do estrato populacional da própria UF × população
    do omisso; coluna separada (iss_imputado) preserva a variante
    zero-imputação.

Operação:
  * Idempotente e retomável: cache em data/raw/siconfi_municipal/, checkpoint
    parquet incremental por ano a cada 200 municípios; municípios já coletados
    não são refeitos.
  * Concorrência ≤4 (ThreadPoolExecutor) + limitador global de vazão; retry
    exponencial em 429/5xx e erros de rede.
  * _meta.json registra url, sha256 e collected_at (datetime SÓ aqui — o
    cálculo downstream é determinístico e livre de relógio).

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_municipal
          [--build-only] (só reconstrói os processados a partir do cache)
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from aferir.config import (
    CONTA_ISS_POS2022,
    JANELA_RECEITA,
    PROCESSED,
    RAW,
    SICONFI_API,
    UFS,
)
from aferir.provenance import caminho_repo, sha256_file

# ---------------------------------------------------------------- constantes
RAW_DIR = RAW / "siconfi_municipal"
META_PATH = RAW_DIR / "_meta.json"

ANEXO_DCA = "DCA-Anexo I-C"
# Na API o código vem prefixado por natureza: 'RO' = Receitas Orçamentárias.
COD_CONTA_ISS_API = "RO" + CONTA_ISS_POS2022          # 'RO1.1.1.4.51.1.0'
COL_BRUTA = "Receitas Brutas Realizadas"
COL_DEDUCOES_OUTRAS = "Outras Deduções da Receita"
COL_DEDUCOES_FUNDEB = "Deduções - FUNDEB"             # não se aplica ao ISS

# DF (RREO estadual, Anexo 03)
RREO_COD_CONTA_ISS = "ISSLiquidoExcetoTransferenciasEFUNDEB"
RREO_COLUNA_12M = "TOTAL (ÚLTIMOS 12 MESES)"
RREO_ANEXO_03 = "RREO-Anexo 03"

CHECKPOINT_EVERY = 200
MAX_WORKERS = 4
MIN_INTERVAL_S = 0.25          # limitador global: ≤4 req/s de pico
MAX_TENTATIVAS = 6
TIMEOUT_S = 120
RETRY_STATUS = {429, 500, 502, 503, 504}

# Estratos populacionais (convenção IBGE/Munic) para imputação de omissos.
ESTRATO_BINS = [0, 5_000, 10_000, 20_000, 50_000, 100_000, 500_000, float("inf")]
ESTRATO_LABELS = [
    "ate_5k", "5k_10k", "10k_20k", "20k_50k", "50k_100k", "100k_500k",
    "acima_500k",
]
ESTRATO_DESC = (
    "estratos populacionais (convencao IBGE/Munic): "
    "<=5k, 5-10k, 10-20k, 20-50k, 50-100k, 100-500k, >500k"
)

# status por município no cache bruto
STATUS_OK = "ok"                 # DCA presente, conta ISS presente
STATUS_DCA_SEM_ISS = "dca_sem_iss"  # DCA presente, conta ISS ausente (ISS=0)
STATUS_SEM_DCA = "sem_dca"       # ente não entregou a DCA do exercício (omisso)

_rate_lock = threading.Lock()
_last_request_t = [0.0]
_thread_local = threading.local()


# ---------------------------------------------------------------- HTTP
def _session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            "Accept": "application/json",
            "User-Agent": "aferir/2.0 (pesquisa; dados abertos SICONFI)",
        })
        _thread_local.session = s
    return _thread_local.session


def _throttle() -> None:
    """Limitador global de vazão: no máximo 1 requisição a cada MIN_INTERVAL_S."""
    with _rate_lock:
        wait = _last_request_t[0] + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_t[0] = time.monotonic()


def _get_json(endpoint: str, params: dict) -> dict:
    """GET com retry exponencial em 429/5xx e erros de rede."""
    url = f"{SICONFI_API}/{endpoint}"
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        _throttle()
        try:
            r = _session().get(url, params=params, timeout=TIMEOUT_S)
            if r.status_code in RETRY_STATUS:
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if tentativa == MAX_TENTATIVAS:
                raise RuntimeError(
                    f"SICONFI {endpoint} {params}: {exc} "
                    f"(apos {MAX_TENTATIVAS} tentativas)"
                ) from exc
            time.sleep(min(2.0 ** tentativa, 60.0))
    raise AssertionError("inalcancavel")


def _get_items(endpoint: str, params: dict) -> list[dict]:
    """Coleta paginada defensiva (ORDS: limit 5000 / hasMore)."""
    items: list[dict] = []
    offset = 0
    while True:
        payload = _get_json(endpoint, dict(params, offset=offset))
        batch = payload.get("items", [])
        items.extend(batch)
        if not payload.get("hasMore"):
            return items
        offset += len(batch)


# ---------------------------------------------------------------- meta
def _atualiza_meta(**novos_campos) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    meta.setdefault("fonte", "API SICONFI (Tesouro Nacional) — dados abertos, sem credencial")
    meta.setdefault("endpoint_entes", f"{SICONFI_API}/entes")
    meta.setdefault(
        "endpoint_dca",
        f"{SICONFI_API}/dca?an_exercicio={{ano}}&no_anexo={ANEXO_DCA}"
        "&id_ente={cod_ibge}",
    )
    meta.setdefault(
        "endpoint_rreo_df",
        f"{SICONFI_API}/rreo?an_exercicio={{ano}}&nr_periodo=6"
        "&co_tipo_demonstrativo=RREO&id_ente=53",
    )
    meta.setdefault("conta_iss", COD_CONTA_ISS_API)
    meta.setdefault("colunas", [COL_BRUTA, COL_DEDUCOES_OUTRAS])
    meta.update(novos_campos)
    meta["collected_at"] = datetime.now(timezone.utc).isoformat()
    meta["sha256"] = {
        p.name: sha256_file(p)
        for p in sorted(RAW_DIR.glob("*.parquet"))
    }
    META_PATH.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _grava_parquet_atomico(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- entes
def fetch_entes() -> pd.DataFrame:
    """Lista de entes do SICONFI (cacheada); universo municipal = esfera 'M'."""
    path = RAW_DIR / "entes.parquet"
    if path.exists():
        return pd.read_parquet(path)
    items = _get_items("entes", {})
    df = pd.DataFrame(items).sort_values("cod_ibge").reset_index(drop=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _grava_parquet_atomico(df, path)
    _atualiza_meta(n_entes=len(df))
    return df


def entes_municipais() -> pd.DataFrame:
    df = fetch_entes()
    mun = df[df["esfera"] == "M"].copy()
    mun["cod_ibge"] = mun["cod_ibge"].astype("int64")
    mun["populacao"] = mun["populacao"].astype("int64")
    return mun.sort_values("cod_ibge").reset_index(drop=True)


# ---------------------------------------------------------------- DCA municipal
def _linhas_dca_iss(ente: dict, ano: int) -> list[dict]:
    """Baixa a DCA Anexo I-C de um município e extrai a conta ISS."""
    base = {
        "exercicio": ano,
        "cod_ibge": int(ente["cod_ibge"]),
        "ente": ente["ente"],
        "uf": ente["uf"],
        "populacao": int(ente["populacao"]),
    }
    items = _get_items(
        "dca",
        {"an_exercicio": ano, "no_anexo": ANEXO_DCA, "id_ente": int(ente["cod_ibge"])},
    )
    if not items:
        return [dict(base, coluna="", cod_conta="", conta="", valor=float("nan"),
                     status=STATUS_SEM_DCA)]
    iss = [it for it in items if it.get("cod_conta") == COD_CONTA_ISS_API]
    if not iss:
        return [dict(base, coluna="", cod_conta="", conta="", valor=float("nan"),
                     status=STATUS_DCA_SEM_ISS)]
    return [
        dict(
            base,
            coluna=it.get("coluna"),
            cod_conta=it.get("cod_conta"),
            conta=it.get("conta"),
            valor=float(it.get("valor")),
            status=STATUS_OK,
        )
        for it in iss
    ]


def _caminho_cache(ano: int) -> Path:
    return RAW_DIR / f"dca_iss_{ano}.parquet"


def _ordena_cache(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.astype({"exercicio": "int64", "cod_ibge": "int64", "populacao": "int64"})
        .sort_values(["cod_ibge", "coluna"])
        .reset_index(drop=True)
    )


def fetch_dca_iss(ano: int) -> pd.DataFrame:
    """Coleta ISS (DCA I-C) de todos os municípios do ano, com checkpoints.

    Retomável: municípios já presentes no parquet do ano são pulados.
    """
    mun = entes_municipais()
    path = _caminho_cache(ano)
    if path.exists():
        cache = pd.read_parquet(path)
        feitos = set(cache["cod_ibge"].astype("int64"))
    else:
        cache = pd.DataFrame()
        feitos = set()

    pendentes = mun[~mun["cod_ibge"].isin(feitos)]
    print(f"[dca {ano}] universo={len(mun)} feitos={len(feitos)} "
          f"pendentes={len(pendentes)}", flush=True)
    if pendentes.empty:
        return _ordena_cache(cache)

    novas: list[dict] = []
    concluidos = 0
    t0 = time.monotonic()
    falhas: list[tuple[int, str]] = []

    def _persiste() -> None:
        nonlocal cache
        if not novas:
            return
        cache = _ordena_cache(pd.concat([cache, pd.DataFrame(novas)],
                                        ignore_index=True))
        novas.clear()
        _grava_parquet_atomico(cache, path)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futuros = {
            pool.submit(_linhas_dca_iss, ente._asdict(), ano): ente.cod_ibge
            for ente in pendentes.itertuples(index=False)
        }
        for fut in as_completed(futuros):
            cod = futuros[fut]
            try:
                novas.extend(fut.result())
            except Exception as exc:            # noqa: BLE001 — registrado e retomável
                falhas.append((cod, str(exc)))
                print(f"[dca {ano}] FALHA {cod}: {exc}", flush=True)
                continue
            concluidos += 1
            if concluidos % CHECKPOINT_EVERY == 0:
                _persiste()
                taxa = concluidos / (time.monotonic() - t0)
                print(f"[dca {ano}] checkpoint {concluidos}/{len(pendentes)} "
                      f"({taxa:.2f} municipios/s)", flush=True)

    _persiste()
    _atualiza_meta(**{f"n_municipios_{ano}": int(cache['cod_ibge'].nunique()),
                      f"falhas_{ano}": len(falhas)})
    dt = time.monotonic() - t0
    print(f"[dca {ano}] concluido: {concluidos} coletados, {len(falhas)} falhas, "
          f"{dt/60:.1f} min", flush=True)
    if falhas:
        print(f"[dca {ano}] reexecute o fetcher para retomar as falhas.", flush=True)
    return _ordena_cache(cache)


# ---------------------------------------------------------------- DF (RREO)
def iss_df_rreo(ano: int) -> tuple[float, str]:
    """ISS do DF (art. 350, III): RREO estadual, Anexo 03, total 12 meses.

    Cache idempotente em data/raw/siconfi_municipal/; se ausente, refetch
    id_ente=53 no endpoint público /rreo. Retorna (valor, caminho_da_fonte).
    """
    cache = RAW_DIR / f"rreo_DF_{ano}_6.parquet"
    if not cache.exists():
        items = _get_items("rreo", {
            "an_exercicio": ano,
            "nr_periodo": 6,
            "co_tipo_demonstrativo": "RREO",
            "id_ente": 53,
        })
        if not items:
            raise ValueError(f"RREO DF {ano}: API retornou vazio")
        _grava_parquet_atomico(pd.DataFrame(items), cache)
        _atualiza_meta()
    df = pd.read_parquet(cache)
    origem = caminho_repo(cache)

    sel = df[
        (df["cod_conta"] == RREO_COD_CONTA_ISS)
        & (df["coluna"] == RREO_COLUNA_12M)
        & (df["anexo"] == RREO_ANEXO_03)
    ]
    if len(sel) != 1:
        raise ValueError(
            f"RREO DF {ano}: esperava 1 linha ISS 12M no Anexo 03, achei {len(sel)}"
        )
    return float(sel["valor"].iloc[0]), origem


# ---------------------------------------------------------------- processados
def build_iss_municipio(ano: int) -> pd.DataFrame:
    """iss_municipio_{ano}.parquet — universo integral (5.570 linhas).

    iss_* = NaN para omissos (sem DCA); 0,0 para DCA entregue sem conta ISS.
    populacao canonica = /entes (mesma base para declarantes e omissos).
    """
    bruto = pd.read_parquet(_caminho_cache(ano))
    mun = entes_municipais()[["cod_ibge", "ente", "uf", "populacao"]]
    if set(bruto["cod_ibge"]) != set(mun["cod_ibge"]):
        faltam = set(mun["cod_ibge"]) - set(bruto["cod_ibge"])
        raise ValueError(f"cache {ano} incompleto: faltam {len(faltam)} municipios")

    ok = bruto[bruto["status"] == STATUS_OK]
    largo = (
        ok.pivot_table(index="cod_ibge", columns="coluna", values="valor",
                       aggfunc="sum")
        .reindex(columns=[COL_BRUTA, COL_DEDUCOES_OUTRAS])
        .fillna(0.0)
    )
    largo.columns = ["iss_bruta", "iss_deducoes_outras"]

    out = mun.merge(largo.reset_index(), on="cod_ibge", how="left")
    # DCA entregue sem conta ISS => ISS declarado igual a zero
    sem_iss = bruto.loc[bruto["status"] == STATUS_DCA_SEM_ISS, "cod_ibge"]
    zera = out["cod_ibge"].isin(set(sem_iss))
    out.loc[zera, ["iss_bruta", "iss_deducoes_outras"]] = 0.0
    out["iss_liquida"] = out["iss_bruta"] - out["iss_deducoes_outras"]

    out = out.sort_values("cod_ibge").reset_index(drop=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    _grava_parquet_atomico(out, PROCESSED / f"iss_municipio_{ano}.parquet")
    return out


def _imputa_omissos(painel: pd.DataFrame) -> pd.Series:
    """Imputação F2: mediana do ISS líquido per capita do estrato populacional
    da própria UF (declarantes) × população do omisso.

    Fallbacks declarados: (i) mediana per capita da UF; (ii) mediana nacional
    do estrato — usados apenas se o estrato da UF não tiver declarante.
    """
    p = painel.copy()
    p["estrato"] = pd.cut(p["populacao"], bins=ESTRATO_BINS,
                          labels=ESTRATO_LABELS, right=True)
    decl = p[p["iss_liquida"].notna()].copy()
    decl["iss_pc"] = decl["iss_liquida"] / decl["populacao"]

    med_uf_estrato = decl.groupby(["uf", "estrato"], observed=True)["iss_pc"].median()
    med_uf = decl.groupby("uf")["iss_pc"].median()
    med_estrato = decl.groupby("estrato", observed=True)["iss_pc"].median()

    imput = pd.Series(0.0, index=p.index)
    omissos = p[p["iss_liquida"].isna()]
    for idx, row in omissos.iterrows():
        chave = (row["uf"], row["estrato"])
        if chave in med_uf_estrato.index:
            pc = med_uf_estrato.loc[chave]
        elif row["uf"] in med_uf.index:
            pc = med_uf.loc[row["uf"]]
        else:
            pc = med_estrato.loc[row["estrato"]]
        imput.loc[idx] = float(pc) * float(row["populacao"])
    return imput


def build_r_municipal_uf() -> pd.DataFrame:
    """r_municipal_uf.csv — ISS por UF/ano, cobertura e imputação (⚑ F2).

    iss_liquida = somatório dos declarantes (variante SEM imputação);
    iss_imputado = adicional imputado aos omissos (variante COM imputação =
    iss_liquida + iss_imputado). DF entra com fonte='RREO-DF'.
    """
    formula_mun = (
        "iss_liquida = SUM_mun(bruta - deducoes_outras) [declarantes]; "
        "iss_imputado = SUM_omissos(mediana_pc(uf, estrato) * populacao); "
        + ESTRATO_DESC
    )
    fonte_mun = (
        f"SICONFI DCA '{ANEXO_DCA}', conta {COD_CONTA_ISS_API} (ISSQN), "
        f"colunas '{COL_BRUTA}' - '{COL_DEDUCOES_OUTRAS}'; universo e populacao: "
        f"{SICONFI_API}/entes (esfera M); LC 214 art. 350, III e par.1, III"
    )
    linhas = []
    for ano in JANELA_RECEITA:
        painel = pd.read_parquet(PROCESSED / f"iss_municipio_{ano}.parquet")
        # Brasília (5300108) não entrega DCA municipal: o ISS distrital vem
        # do RREO do GDF (linha própria abaixo) — exclui do painel DCA.
        painel = painel[painel["uf"] != "DF"]
        painel["imputado"] = _imputa_omissos(painel)
        for uf, g in painel.groupby("uf"):
            decl = g["iss_liquida"].notna()
            linhas.append({
                "uf": uf,
                "ano": ano,
                "iss_liquida": g.loc[decl, "iss_liquida"].sum(),
                "n_declarantes": int(decl.sum()),
                "n_universo": len(g),
                "cobertura_pct": round(100.0 * decl.sum() / len(g), 2),
                "iss_imputado": g["imputado"].sum(),
                "formula": formula_mun,
                "fonte": fonte_mun,
            })
        # DF: ISS do proprio ente distrital (art. 350, III; art. 349, II, 'c')
        valor_df, origem_df = iss_df_rreo(ano)
        linhas.append({
            "uf": "DF",
            "ano": ano,
            "iss_liquida": valor_df,
            "n_declarantes": 1,
            "n_universo": 1,
            "cobertura_pct": 100.0,
            "iss_imputado": 0.0,
            "formula": (
                f"cod_conta='{RREO_COD_CONTA_ISS}', coluna='{RREO_COLUNA_12M}', "
                f"anexo='{RREO_ANEXO_03}' (RREO 6o bim.); LC 214 art. 350, III"
            ),
            "fonte": "RREO-DF",
        })
    out = (
        pd.DataFrame(linhas)
        .sort_values(["ano", "uf"])
        .reset_index(drop=True)
    )
    assert sorted(out["uf"].unique()) == sorted(UFS)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "r_municipal_uf.csv", index=False)
    return out


def build_concentracao() -> pd.DataFrame:
    """iss_concentracao.csv — shares top 1/10/100, Gini e série de Lorenz.

    Universo: municípios declarantes (ex-DF, que não é município); a
    imputação por estrato não identifica municípios e fica fora da curva.
    series: 'share_top' (x=k, y=share), 'gini' (x=NaN, y=indice),
    'lorenz' (x=fracao acumulada de municipios em ordem crescente de ISS,
    y=fracao acumulada do ISS liquido).
    """
    fonte = (
        f"SICONFI DCA '{ANEXO_DCA}', conta {COD_CONTA_ISS_API}; declarantes, "
        "ex-DF (nao e municipio); ISS liquido = bruta - deducoes_outras"
    )
    linhas = []
    for ano in JANELA_RECEITA:
        painel = pd.read_parquet(PROCESSED / f"iss_municipio_{ano}.parquet")
        decl = painel[painel["iss_liquida"].notna()].copy()
        total = decl["iss_liquida"].sum()

        desc = decl.sort_values(["iss_liquida", "cod_ibge"],
                                ascending=[False, True])["iss_liquida"]
        for k in (1, 10, 100):
            linhas.append({
                "ano": ano, "serie": "share_top", "x": float(k),
                "y": desc.head(k).sum() / total,
                "formula": f"SUM(top {k} municipios) / SUM(declarantes)",
                "fonte": fonte,
            })

        asc = decl.sort_values(["iss_liquida", "cod_ibge"],
                               ascending=[True, True])["iss_liquida"]
        n = len(asc)
        x = pd.Series(range(1, n + 1), dtype="float64") / n
        y = asc.cumsum().reset_index(drop=True) / total
        gini = float(1.0 - sum(
            (y.iloc[i] + (y.iloc[i - 1] if i > 0 else 0.0)) * (1.0 / n)
            for i in range(n)
        ))
        linhas.append({
            "ano": ano, "serie": "gini", "x": float("nan"), "y": gini,
            "formula": "1 - SUM((y_i + y_{i-1}) * (x_i - x_{i-1})), Lorenz discreta",
            "fonte": fonte,
        })
        for i in range(n):
            linhas.append({
                "ano": ano, "serie": "lorenz", "x": float(x.iloc[i]),
                "y": float(y.iloc[i]),
                "formula": "cumsum(ISS asc)/total vs rank/n",
                "fonte": fonte,
            })
    out = pd.DataFrame(linhas)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "iss_concentracao.csv", index=False)
    return out


def build_cobertura() -> pd.DataFrame:
    """coverage_siconfi.csv — cobertura e imputação POR EXERCÍCIO (⚑ A6).

    Separa cobertura por CONTAGEM (declarantes/universo) de cobertura
    ECONÔMICA (participação do ISS nacional declarada, com o complemento
    imputado por mediana per capita de estrato). Declara a peça primária e a
    peça de validação de cada exercício: a DCA é a peça primária nos dois
    (2025 entregue em 2026); a MSC valida as sondas ao centavo (invariante
    I14) e o RREO distrital cobre o ISS do DF.
    """
    r = pd.read_csv(PROCESSED / "r_municipal_uf.csv")
    linhas = []
    for ano, g in r.groupby("ano"):
        decl, univ = int(g["n_declarantes"].sum()), int(g["n_universo"].sum())
        iss_d, iss_i = float(g["iss_liquida"].sum()), float(g["iss_imputado"].sum())
        linhas.append({
            "ano": int(ano),
            "n_declarantes": decl,
            "n_universo": univ,
            "cobertura_contagem_pct": 100.0 * decl / univ,
            "n_imputados": univ - decl,
            "iss_declarado_rs_bi": iss_d / 1e9,
            "iss_imputado_rs_bi": iss_i / 1e9,
            "cobertura_economica_pct": 100.0 * iss_d / (iss_d + iss_i),
            "participacao_imputada_pct": 100.0 * iss_i / (iss_d + iss_i),
            "peca_primaria": "DCA Anexo I-C (conta 1.1.1.4.51.1.0)",
            "peca_validacao": ("MSC (sondas ao centavo, invariante I14); "
                               "RREO Anexo 03 p/ ISS-DF"),
            "formula": ("cobertura_economica = ISS declarado / (declarado + "
                        "imputado); imputação = mediana per capita do estrato "
                        "populacional da própria UF × população do omisso"),
            "fonte": "r_municipal_uf.csv (SICONFI/DCA); LC 214 art. 350, III",
        })
    out = pd.DataFrame(linhas).sort_values("ano").reset_index(drop=True)
    out.to_csv(PROCESSED / "coverage_siconfi.csv", index=False)
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-only", action="store_true",
                    help="nao refaz fetch; so reconstroi os processados")
    ap.add_argument("--anos", type=int, nargs="*", default=list(JANELA_RECEITA))
    args = ap.parse_args()

    if not args.build_only:
        fetch_entes()
        for ano in args.anos:
            fetch_dca_iss(ano)

    for ano in args.anos:
        painel = build_iss_municipio(ano)
        decl = painel["iss_liquida"].notna()
        print(f"[{ano}] universo={len(painel)} declarantes={int(decl.sum())} "
              f"ISS liquido declarado = R$ {painel.loc[decl,'iss_liquida'].sum()/1e9:.3f} bi",
              flush=True)

    r_uf = build_r_municipal_uf()
    for ano in JANELA_RECEITA:
        g = r_uf[r_uf["ano"] == ano]
        print(f"[{ano}] R_M nacional (com DF): declarado R$ "
              f"{g['iss_liquida'].sum()/1e9:.3f} bi + imputado R$ "
              f"{g['iss_imputado'].sum()/1e9:.4f} bi; cobertura "
              f"{100.0*g['n_declarantes'].sum()/g['n_universo'].sum():.2f}%",
              flush=True)

    conc = build_concentracao()
    tops = conc[conc["serie"] == "share_top"]
    print(tops.pivot(index="ano", columns="x", values="y").to_string(), flush=True)

    cob = build_cobertura()
    print(cob[["ano", "cobertura_contagem_pct", "cobertura_economica_pct",
               "n_imputados", "participacao_imputada_pct"]]
          .round(3).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
