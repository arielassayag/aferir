"""Taxa de informalidade por UF (IBGE SIDRA, tabela 8529) — insumo do γ heterogêneo (E5).

PNAD Contínua trimestral: v/12466 = "Taxa de informalidade das pessoas de 14
anos ou mais de idade ocupadas na semana de referência (%)" (1 casa decimal),
nível n3 (27 UFs), janela PINADA 202401-202504 (8 trimestres 2024T1-2025T4,
o biênio da janela de receita do pipeline). 27 × 8 = 216 linhas de dados.
Código da variável descoberto via desctabapi.aspx?c=8529 em 2026-07-12.

FONTE VIVA em revisões de ponderação: a partir de 15/08/2025 o IBGE passou a
divulgar o tema com a nova ponderação da NT 02/2025 e REATUALIZOU a série
histórica — trimestres já publicados podem mudar em reponderações futuras.
Por isso a idempotência é seed-first: se o JSON existe e o sha256 bate com o
sidecar, NÃO rebaixa (vintage congelada; paridade entre vintages afere-se
pelos valores, não pelo sha).

Escrita atômica (tmp + os.replace); sidecar `<arquivo>._meta.json` com url,
parametros, sha256, bytes, collected_at UTC e status_http. datetime SÓ aqui.

Uso: PYTHONPATH=src python3 -m aferir.fetch.ibge_informalidade
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

RAW_SIDRA_INFORMALIDADE = config.RAW / "sidra_informalidade"

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 180

_VARIAVEL = "12466"
_TRIMESTRES = tuple(f"{ano}0{t}" for ano in (2024, 2025) for t in (1, 2, 3, 4))
_N_UFS = 27

SIDRA_INFORMALIDADE_8529_URL = (
    "https://apisidra.ibge.gov.br/values/t/8529/n3/all/"
    f"v/{_VARIAVEL}/p/{_TRIMESTRES[0]}-{_TRIMESTRES[-1]}?formato=json")

_ARQ = "informalidade_8529_2024_2025.json"


def _valida_payload(linhas: list[dict]) -> None:
    """Falha cedo se faltar UF, trimestre ou vier variável errada."""
    esperado = _N_UFS * len(_TRIMESTRES)
    if len(linhas) != esperado:
        raise ValueError(f"SIDRA 8529: esperadas {esperado} linhas, "
                         f"vieram {len(linhas)}")
    variaveis = {row.get("D2C") for row in linhas}
    if variaveis != {_VARIAVEL}:
        raise ValueError(f"SIDRA 8529: variável inesperada: {variaveis}")
    por_trimestre: dict[str, set[str]] = {}
    for row in linhas:
        float(row["V"])                      # taxa deve ser numérica
        por_trimestre.setdefault(row["D3C"], set()).add(row["D1C"])
    incompletos = {t: len(por_trimestre.get(t, set())) for t in _TRIMESTRES
                   if len(por_trimestre.get(t, set())) != _N_UFS}
    if set(por_trimestre) != set(_TRIMESTRES) or incompletos:
        raise ValueError(f"SIDRA 8529: grade UF×trimestre incompleta: "
                         f"{incompletos or sorted(por_trimestre)}")


def _grava_meta(destino: Path, *, status_http: int | None, origem: str) -> None:
    meta = {
        "url": SIDRA_INFORMALIDADE_8529_URL,
        "parametros": {"tabela": 8529, "variavel": int(_VARIAVEL),
                       "periodos": list(_TRIMESTRES), "nivel": "n3"},
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status_http": status_http,
        "origem": origem,
        "nota_fonte_viva": ("reponderações da PNAD Contínua (ex.: NT 02/2025) "
                            "reatualizam trimestres já publicados; vintage "
                            "congelada pela existência do arquivo"),
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, meta_path)


def fetch_informalidade(*, force: bool = False) -> Path:
    """Baixa (seed-first) a taxa de informalidade por UF 2024T1-2025T4."""
    destino = RAW_SIDRA_INFORMALIDADE / _ARQ
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.with_name(destino.name + "._meta.json")

    if destino.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(destino):
                return destino
        bruto = json.loads(destino.read_text(encoding="utf-8"))
        _valida_payload(bruto[1:])
        _grava_meta(destino, status_http=None, origem="cache_local")
        return destino

    resp = requests.get(SIDRA_INFORMALIDADE_8529_URL, headers=_UA,
                        timeout=TIMEOUT_S)
    resp.raise_for_status()
    bruto = resp.json()
    # 1ª linha do payload apisidra = cabeçalho-descritor; dados = bruto[1:].
    _valida_payload(bruto[1:])
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    os.replace(tmp, destino)
    _grava_meta(destino, status_http=resp.status_code, origem="download")
    return destino


if __name__ == "__main__":
    print("informalidade 8529 (SIDRA):", fetch_informalidade())
