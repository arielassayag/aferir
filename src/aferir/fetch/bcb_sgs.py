"""Fetcher BCB/SGS — séries mensais de 2021 da validação externa do SIFIM.

Fonte ABERTA, sem credencial: API de dados abertos do Banco Central
(https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados). Três séries
mensais, jan-dez/2021, consumidas por aferir.sifim_fbcf.fisim_pf_bcb_2021
(FISIM das famílias pelo lado dos empréstimos — âncora externa do resíduo
SIFIM, auditoria de nível de 13/07/2026, metadata/auditoria_nivel_2026_07_13.md):

  20541  Saldo da carteira de crédito — Pessoas físicas — Total (R$ milhões)
  25353  ICC — Indicador de Custo do Crédito — Pessoas físicas — Total
         (% a.a.; taxa do ESTOQUE, não das concessões)
  4189   Taxa de juros — Selic acumulada no mês anualizada base 252 (% a.a.)

Snapshot VERSIONADO em data/inputs/bcb_sgs_fisim_pf_2021.csv (CSV longo:
codigo, serie, data, valor, unidade — `valor` preservado como string LITERAL
da API, sem re-serialização de float). Exceção declarada à taxonomia
data/raw-vs-inputs: data/raw NÃO é versionado neste repositório e a validação
externa precisa reproduzir-se em clone puro — o snapshot tem 36 células e
carrega sidecar ._meta.json (url, sha256, collected_at) no padrão dos raws.

FONTE VIVA: o BCB pode revisar séries de crédito retroativamente — a
idempotência é pela EXISTÊNCIA do CSV (vintage congelada, sha256 no sidecar):
se o arquivo já existe, NADA é baixado. Paridade de uma vintage nova se afere
por igualdade numérica das 36 células consumidas, não por sha.

Idempotência: escrita atômica (tmp + rename). datetime SÓ no fetcher.
Execução: PYTHONPATH=src python3 -m aferir.fetch.bcb_sgs
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from aferir import config
from aferir.provenance import sha256_file

# Códigos SGS (nomes estáveis da API; validados por download real 2026-07-16)
SGS_SALDO_PF = 20541
SGS_ICC_PF = 25353
SGS_SELIC = 4189

ANO = 2021

# codigo -> (rotulo_curto, descricao_oficial, unidade)
SERIES_SGS: dict[int, tuple[str, str, str]] = {
    SGS_SALDO_PF: (
        "saldo_credito_pf",
        "Saldo da carteira de crédito - Pessoas físicas - Total",
        "R$ milhões",
    ),
    SGS_ICC_PF: (
        "icc_pf",
        "Indicador de Custo do Crédito (ICC) - Pessoas físicas - Total "
        "(taxa do estoque)",
        "% a.a.",
    ),
    SGS_SELIC: (
        "selic_anualizada",
        "Taxa de juros - Selic acumulada no mês anualizada base 252",
        "% a.a.",
    ),
}

BCB_SGS_URL_TPL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    f"?formato=json&dataInicial=01/01/{ANO}&dataFinal=31/12/{ANO}"
)

BCB_SGS_CSV = config.INPUTS / "bcb_sgs_fisim_pf_2021.csv"

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 120

_DESCRICAO = (
    "BCB/SGS, séries mensais jan-dez/2021: 20541 (saldo carteira de crédito "
    "PF, R$ mi), 25353 (ICC-PF, taxa do estoque, % a.a.), 4189 (Selic "
    "acumulada no mês anualizada, % a.a.) — validação externa do resíduo "
    "SIFIM (FISIM-PF lado-empréstimos), dado aberto, sem credencial"
)
_NOTA_FONTE_VIVA = (
    "fonte VIVA: o BCB pode revisar séries de crédito retroativamente; "
    "vintage congelada pela existência do CSV — paridade entre vintages "
    "afere-se por igualdade numérica das 36 células (3 séries × 12 meses), "
    "não por sha256"
)


def _grava_meta(destino: Path, *, status_http: int | None, origem: str) -> None:
    """Sidecar `<arquivo>._meta.json` (padrão dos fetchers do pacote)."""
    meta = {
        "url": {str(c): BCB_SGS_URL_TPL.format(codigo=c) for c in SERIES_SGS},
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status_http": status_http,
        "origem": origem,
        "descricao": _DESCRICAO,
        "nota_fonte_viva": _NOTA_FONTE_VIVA,
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, meta_path)


def _valida_serie(codigo: int, payload: list[dict]) -> None:
    """Falha alto se a série não tiver EXATAMENTE os 12 meses de 2021."""
    if len(payload) != 12:
        raise ValueError(f"SGS {codigo}: {len(payload)} observações "
                         f"(esperadas 12 de {ANO})")
    datas = [str(r.get("data", "")) for r in payload]
    esperadas = [f"01/{m:02d}/{ANO}" for m in range(1, 13)]
    if datas != esperadas:
        raise ValueError(f"SGS {codigo}: datas {datas} != jan-dez/{ANO}")
    for r in payload:
        float(r["valor"])                      # parseável; string preservada


def fetch_bcb_sgs_fisim_pf(*, force: bool = False) -> Path:
    """Baixa (seed-first, atômico) as 3 séries SGS de 2021 para o CSV longo.

    Rota local: se o CSV já existe e force=False, NÃO toca a rede (vintage
    congelada); apenas completa o sidecar ._meta.json a partir do arquivo
    local, caso falte.
    """
    BCB_SGS_CSV.parent.mkdir(parents=True, exist_ok=True)
    meta_path = BCB_SGS_CSV.with_name(BCB_SGS_CSV.name + "._meta.json")
    if BCB_SGS_CSV.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(BCB_SGS_CSV):
                return BCB_SGS_CSV
        _grava_meta(BCB_SGS_CSV, status_http=None, origem="cache_local")
        return BCB_SGS_CSV

    linhas: list[dict] = []
    status: int | None = None
    for codigo, (rotulo, _desc, unidade) in SERIES_SGS.items():
        url = BCB_SGS_URL_TPL.format(codigo=codigo)
        resp = requests.get(url, headers=_UA, timeout=TIMEOUT_S)
        resp.raise_for_status()
        status = resp.status_code
        payload = resp.json()
        _valida_serie(codigo, payload)
        for r in payload:
            linhas.append({"codigo": codigo, "serie": rotulo,
                           "data": str(r["data"]),
                           "valor": str(r["valor"]),   # literal da API
                           "unidade": unidade})
    df = pd.DataFrame(linhas,
                      columns=["codigo", "serie", "data", "valor", "unidade"])
    tmp = BCB_SGS_CSV.with_name(BCB_SGS_CSV.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, BCB_SGS_CSV)
    _grava_meta(BCB_SGS_CSV, status_http=status, origem="download")
    return BCB_SGS_CSV


def main() -> None:
    path = fetch_bcb_sgs_fisim_pf()
    df = pd.read_csv(path)
    print(f"{path}: {len(df)} linhas "
          f"({df['codigo'].nunique()} séries × 12 meses de {ANO})", flush=True)


if __name__ == "__main__":
    main()
