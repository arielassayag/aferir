"""Utilitários comuns aos fetchers SICONFI do módulo G (art. 473).

Padrões (DESIGN §3-4):
  * paginação OBRIGATÓRIA no ORDS (limite 5.000 itens; hasMore/offset);
  * idempotência: cache em data/raw/<dominio>/; arquivos existentes não são
    refeitos; _meta.json registra url, sha256 e collected_at;
  * datetime SÓ no fetcher — o cálculo downstream é livre de relógio.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from aferir.config import SICONFI_API
from aferir.provenance import sha256_file

MIN_INTERVAL_S = 0.25          # vazão máxima ~4 req/s (medida do design review)
MAX_TENTATIVAS = 6
TIMEOUT_S = 120
RETRY_STATUS = {429, 500, 502, 503, 504}

_last_request_t = [0.0]
_session_holder: list[requests.Session] = []


def _session() -> requests.Session:
    if not _session_holder:
        s = requests.Session()
        s.headers.update({
            "Accept": "application/json",
            "User-Agent": "aferir/2.0 (pesquisa; dados abertos SICONFI)",
        })
        _session_holder.append(s)
    return _session_holder[0]


def _throttle() -> None:
    wait = _last_request_t[0] + MIN_INTERVAL_S - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_t[0] = time.monotonic()


def get_json(endpoint: str, params: dict) -> dict:
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


def get_items_paginado(endpoint: str, params: dict) -> tuple[list[dict], int]:
    """Coleta TODAS as páginas do ORDS (limit 5.000/hasMore/offset).

    Retorna (itens, n_paginas). A União exige >1 página no DCA Anexo I-D.
    """
    items: list[dict] = []
    offset = 0
    paginas = 0
    while True:
        payload = get_json(endpoint, dict(params, offset=offset))
        batch = payload.get("items", [])
        items.extend(batch)
        paginas += 1
        if not payload.get("hasMore"):
            return items, paginas
        offset += len(batch)


def grava_parquet_atomico(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def atualiza_meta(raw_dir: Path, **novos_campos) -> None:
    """_meta.json do domínio: url-padrão, sha256 de cada parquet, collected_at."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    meta_path = raw_dir / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.setdefault(
        "fonte", "API SICONFI (Tesouro Nacional) — dados abertos, sem credencial"
    )
    meta.update(novos_campos)
    meta["collected_at"] = datetime.now(timezone.utc).isoformat()
    meta["sha256"] = {
        p.name: sha256_file(p) for p in sorted(raw_dir.glob("*.parquet"))
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
