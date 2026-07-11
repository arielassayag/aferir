"""Fetcher SICONFI — DCA MUNICIPAL Anexo I-D (despesa por natureza), AMOSTRA.

Compras governamentais municipais (LC 214, arts. 472-473). O lote FINBRA
("Despesas Orçamentárias", escopo Municípios) está indisponível para coleta
programática em 07/2026: a página JSF exige hCaptcha e não há endpoint ORDS
nem recurso CKAN equivalente (verificado em 10/07/2026). FALLBACK declarado
(missão/DESIGN §3): amostra estratificada = capitais + G473_AMOSTRA_TOP_N
maiores municípios por população (fonte: /entes, esfera M) — a extrapolação
para o universo é feita em aferir.inputs.gov_aquisicoes (pós-estratificação
por per-capita de estrato, com sensibilidades declaradas).

Exclusão: Brasília (COD_IBGE_BRASILIA) — a DCA do GDF é única e as compras do
DF entram integralmente na esfera estadual (art. 349, II, 'c').

Operação: idempotente e retomável (parquet consolidado por ano, checkpoint a
cada 25 municípios); paginação ORDS defensiva; _meta.json com url, sha256 e
collected_at (datetime SÓ aqui).

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_municipal_g
"""
from __future__ import annotations

import time

import pandas as pd

from aferir.config import (
    COD_IBGE_BRASILIA,
    DCA_ANEXO_DESPESA,
    G473_AMOSTRA_TOP_N,
    JANELA_RECEITA,
    RAW,
    SICONFI_API,
)
from aferir.fetch.siconfi_comum import (
    atualiza_meta,
    get_items_paginado,
    grava_parquet_atomico,
)
from aferir.fetch.siconfi_municipal import entes_municipais

RAW_DIR = RAW / "siconfi_municipal_g"
CHECKPOINT_EVERY = 25

STATUS_OK = "ok"
STATUS_SEM_DCA = "sem_dca"      # ente não entregou a DCA do exercício


def amostra_g() -> pd.DataFrame:
    """Amostra: capitais ∪ top-N população (esfera M), exclusive Brasília.

    Determinística dado o cache /entes (as 26 capitais estaduais pertencem ao
    top-200 por população — verificado em 10/07/2026; a união é explícita por
    robustez a vintages futuros do cache).
    """
    mun = entes_municipais()
    mun = mun[mun["cod_ibge"] != COD_IBGE_BRASILIA]
    capitais = mun[mun["capital"].astype(str).str.strip() == "1"]
    maiores = mun.sort_values(
        ["populacao", "cod_ibge"], ascending=[False, True]
    ).head(G473_AMOSTRA_TOP_N)
    amostra = (
        pd.concat([capitais, maiores])
        .drop_duplicates("cod_ibge")
        .sort_values("cod_ibge")
        .reset_index(drop=True)
    )
    return amostra


def caminho_dca_g(ano: int):
    return RAW_DIR / f"dca_g_amostra_{ano}_ID.parquet"


def fetch_dca_g_amostra(ano: int) -> pd.DataFrame:
    """Anexo I-D dos municípios da amostra no exercício `ano` (retomável)."""
    amostra = amostra_g()
    path = caminho_dca_g(ano)
    if path.exists():
        cache = pd.read_parquet(path)
        feitos = set(cache["cod_ibge_ente"].astype("int64"))
    else:
        cache = pd.DataFrame()
        feitos = set()

    pendentes = amostra[~amostra["cod_ibge"].isin(feitos)]
    print(
        f"[g mun {ano}] amostra={len(amostra)} feitos={len(feitos)} "
        f"pendentes={len(pendentes)}",
        flush=True,
    )
    if pendentes.empty:
        return cache

    novas: list[dict] = []
    t0 = time.monotonic()

    def _persiste() -> None:
        nonlocal cache
        if not novas:
            return
        cache = (
            pd.concat([cache, pd.DataFrame(novas)], ignore_index=True)
            .sort_values(["cod_ibge_ente", "cod_conta", "coluna"])
            .reset_index(drop=True)
        )
        novas.clear()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        grava_parquet_atomico(cache, path)

    for i, ente in enumerate(pendentes.itertuples(index=False), start=1):
        base = {
            "cod_ibge_ente": int(ente.cod_ibge),
            "ente": ente.ente,
            "uf_ente": ente.uf,
            "populacao_ente": int(ente.populacao),
        }
        items, _ = get_items_paginado(
            "dca",
            {
                "an_exercicio": ano,
                "no_anexo": DCA_ANEXO_DESPESA,
                "id_ente": int(ente.cod_ibge),
            },
        )
        if not items:
            novas.append(
                dict(base, coluna="", cod_conta="", conta="",
                     valor=float("nan"), status=STATUS_SEM_DCA)
            )
        else:
            novas.extend(
                dict(
                    base,
                    coluna=it.get("coluna"),
                    cod_conta=it.get("cod_conta"),
                    conta=it.get("conta"),
                    valor=float(it.get("valor")),
                    status=STATUS_OK,
                )
                for it in items
            )
        if i % CHECKPOINT_EVERY == 0:
            _persiste()
            taxa = i / (time.monotonic() - t0)
            print(f"[g mun {ano}] {i}/{len(pendentes)} ({taxa:.2f} mun/s)",
                  flush=True)

    _persiste()
    atualiza_meta(
        RAW_DIR,
        endpoint_dca=(
            f"{SICONFI_API}/dca?an_exercicio={{ano}}"
            f"&no_anexo={DCA_ANEXO_DESPESA}&id_ente={{cod_ibge}}"
        ),
        metodo=(
            "amostra capitais + top-200 populacao (fallback FINBRA/hCaptcha); "
            "universo e populacao: /entes esfera M, ex-Brasilia"
        ),
        **{f"n_municipios_{ano}": int(cache["cod_ibge_ente"].nunique())},
    )
    print(f"[g mun {ano}] concluido em {(time.monotonic()-t0)/60:.1f} min",
          flush=True)
    return cache


def main() -> None:
    for ano in JANELA_RECEITA:
        df = fetch_dca_g_amostra(ano)
        sem = df[df["status"] == STATUS_SEM_DCA]["cod_ibge_ente"].nunique()
        print(f"[g mun {ano}] {df['cod_ibge_ente'].nunique()} municipios "
              f"({sem} sem DCA)", flush=True)


if __name__ == "__main__":
    main()
