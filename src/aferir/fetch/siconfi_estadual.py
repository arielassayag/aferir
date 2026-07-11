"""Fetcher SICONFI — DCA ESTADUAL (27 UFs), Anexo I-D (despesa por natureza).

Rota (DESIGN §3): cache idempotente em data/raw/siconfi_estadual/
(dca_{UF}_{ano}.parquet), com sha256 registrado em _seed_manifest.json.
Arquivos ausentes são materializados, na ordem: (1) do snapshot arquivístico
versionado no repositório (snapshot/dca_estadual_2019-2025.tar.gz, sha256
pinado, extração OFFLINE — parquets soltos não são versionados porque a
heurística texto/binário de espelhos anonimizadores pode corromper binários
de alta entropia servidos soltos, caso MEDIDO em 2026-07-12); (2) refetch
pela API pública, arquivo a arquivo. O replicador externo obtém os mesmos
dados com `main()` deste módulo em um clone sem o cache.

O DCA estadual do DF é a DCA única do GDF (art. 349, II, 'c'): as compras do
DF entram INTEGRALMENTE na esfera estadual — Brasília é excluída da esfera
municipal (config.COD_IBGE_BRASILIA).

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_estadual
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from aferir.config import (
    DCA_ANEXO_DESPESA,
    JANELA_RECEITA,
    RAW,
    RAW_DCA_ESTADUAL_DIR,
    SICONFI_API,
    UFS,
)
from aferir.fetch.siconfi_comum import (
    atualiza_meta,
    get_items_paginado,
    grava_parquet_atomico,
)
from aferir.provenance import caminho_repo, sha256_file

RAW_DIR = RAW / "siconfi_estadual"
SEED_MANIFEST = RAW_DIR / "_seed_manifest.json"

# Snapshot arquivístico versionado (rota canônica de materialização).
SNAPSHOT_TAR = RAW_DIR / "snapshot" / "dca_estadual_2019-2025.tar.gz"
SNAPSHOT_SHA256 = (
    "342f03b0f44440741ff8944fcd13c79d9a4ea704070742ea2d3d3bf0d844b8b0"
)

# Código IBGE de 2 dígitos das UFs (id_ente da API para estados) — IBGE/DTB.
COD_IBGE_UF = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
    "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27,
    "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41,
    "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}


def _registra_seed(path: Path) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if SEED_MANIFEST.exists():
        manifest = json.loads(SEED_MANIFEST.read_text(encoding="utf-8"))
    manifest[path.name] = {
        "path": caminho_repo(path),
        "sha256": sha256_file(path),
        "fonte": (
            f"{SICONFI_API}/dca?an_exercicio=<ano>&id_ente=<cod_uf> "
            "(API pública SICONFI, sem credencial)"
        ),
    }
    SEED_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def materializa_do_snapshot() -> int:
    """Extrai do snapshot versionado os dca_{UF}_{ano}.parquet AUSENTES.

    Verifica o sha256 pinado ANTES de extrair; membros fora do padrão são
    ignorados. Sem rede. Retorna o nº de arquivos extraídos (0 se o
    snapshot não existe ou nada falta).
    """
    import tarfile

    if not SNAPSHOT_TAR.exists():
        return 0
    digest = sha256_file(SNAPSHOT_TAR)
    if digest != SNAPSHOT_SHA256:
        raise RuntimeError(
            f"snapshot estadual: sha256 {digest[:16]}… diverge do pinado"
        )
    n = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(SNAPSHOT_TAR, "r:gz") as tar:
        for m in tar:
            nome = Path(m.name).name
            if not (m.isfile() and nome.startswith("dca_")
                    and nome.endswith(".parquet")):
                continue
            destino = RAW_DIR / nome
            if destino.exists():
                continue
            tmp = destino.with_name(nome + ".tmp")
            with open(tmp, "wb") as out:
                out.write(tar.extractfile(m).read())
            os.replace(tmp, destino)
            n += 1
    return n


def _refetch_dca_uf(uf: str, ano: int) -> Path:
    """Fallback: refetch da DCA completa da UF (todos os anexos, como o v1)."""
    path = RAW_DIR / f"dca_{uf}_{ano}.parquet"
    if path.exists():
        return path
    items, paginas = get_items_paginado(
        "dca", {"an_exercicio": ano, "id_ente": COD_IBGE_UF[uf]}
    )
    if not items:
        raise ValueError(f"DCA {uf} {ano}: API vazia")
    df = (
        pd.DataFrame(items)
        .sort_values(["anexo", "cod_conta", "coluna"])
        .reset_index(drop=True)
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    grava_parquet_atomico(df, path)
    atualiza_meta(
        RAW_DIR,
        endpoint_dca=f"{SICONFI_API}/dca?an_exercicio={{ano}}&id_ente={{cod_uf}}",
        **{f"n_paginas_{uf}_{ano}": paginas},
    )
    return path


def caminho_dca_estadual(uf: str, ano: int) -> Path:
    """Parquet da DCA da UF: cache local (hash registrado) ou refetch idempotente."""
    seed = RAW_DCA_ESTADUAL_DIR / f"dca_{uf}_{ano}.parquet"
    if seed.exists():
        _registra_seed(seed)
        return seed
    return _refetch_dca_uf(uf, ano)


def carrega_anexo_id(uf: str, ano: int) -> pd.DataFrame:
    df = pd.read_parquet(caminho_dca_estadual(uf, ano))
    sel = df[df["anexo"] == DCA_ANEXO_DESPESA].copy()
    if sel.empty:
        raise ValueError(f"DCA {uf} {ano}: sem {DCA_ANEXO_DESPESA}")
    return sel


def main() -> None:
    n = materializa_do_snapshot()
    if n:
        print(f"[estadual] snapshot: {n} parquets extraidos (offline)",
              flush=True)
    for ano in JANELA_RECEITA:
        for uf in UFS:
            sel = carrega_anexo_id(uf, ano)
            print(f"[estadual {uf} {ano}] {len(sel)} linhas Anexo I-D", flush=True)


if __name__ == "__main__":
    main()
