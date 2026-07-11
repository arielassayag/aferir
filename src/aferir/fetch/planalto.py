"""Textos legais compilados (Planalto) — fetcher dos HTMLs integrais (L4/F18).

Quatro normas-pilar do pipeline, salvas com o HTML INTEGRAL publicado pelo
Planalto (páginas grandes; a LC 214 compilada passa de 5 MB):

 - LC 214/2025  — lei geral do IBS/CBS/IS (texto compilado);
 - LC 227/2026  — altera a LC 214 e reescreve a transição (arts. 361-365);
 - EC 132/2023  — emenda da reforma tributária do consumo;
 - Constituição — texto compilado (inclui ADCT, arts. 92-A/125-135 da
   transição referenciados via EC 132).

FONTE VIVA: o Planalto regrava o MESMO arquivo compilado quando normas
supervenientes alteram o texto (ex.: a própria LC 227 alterou a página da
LC 214). A idempotência é seed-first: se o HTML existe e o sha256 bate com o
sidecar, NÃO rebaixa — a vintage citada no artigo fica congelada e auditável
pelo sha256 do _meta.json. A verificação de vigência entre vintages é tarefa
do legal_map.csv (L4), não deste fetcher.

Validação mínima antes de publicar: HTTP 200, tamanho mínimo e marcador
textual da norma no corpo (decodificação cp1252 — encoding padrão das
páginas do Planalto). Escrita atômica (tmp + os.replace); sidecar
`<arquivo>._meta.json` com url, sha256, bytes, collected_at UTC e
status_http. datetime SÓ aqui (fetcher).

Uso: PYTHONPATH=src python3 -m aferir.fetch.planalto
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

RAW_PLANALTO = config.RAW / "normas" / "planalto"

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 300

# arquivo-destino -> (url, marcador textual obrigatório, bytes mínimos).
# Tamanhos verificados por download real em 2026-07-12: lcp214 ≈ 5,40 MB,
# lcp227 ≈ 1,33 MB, emc132 ≈ 0,51 MB, constituicao ≈ 1,84 MB — o piso é
# ~metade do observado, só para barrar página de erro/soft-404.
NORMAS: dict[str, tuple[str, str, int]] = {
    "lcp214.htm": (
        "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm",
        "LEI COMPLEMENTAR Nº 214", 2_500_000),
    "lcp227.htm": (
        "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp227.htm",
        "LEI COMPLEMENTAR Nº 227", 600_000),
    "emc132.htm": (
        "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/"
        "emc132.htm",
        "EMENDA CONSTITUCIONAL Nº 132", 250_000),
    "constituicao.htm": (
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        "ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS", 900_000),
    # LC 123/2006 (Estatuto do Simples Nacional) — insumo do A7/E1
    # (aferir.simples): DAS engloba ICMS/ISS (art. 13, VII-VIII), ST fora do
    # DAS (art. 13, §1º, XIII), repasse ao ente titular (art. 22) e vedações
    # setoriais (art. 17). Página compilada ≈ 1,1 MB em 2026-07-12.
    "lcp123.htm": (
        "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm",
        "LEI COMPLEMENTAR Nº 123", 500_000),
}


def _valida_html(raw: bytes, *, marcador: str, min_bytes: int,
                 rotulo: str) -> None:
    """Falha cedo se vier página de erro, redirect de login ou HTML truncado."""
    if len(raw) < min_bytes:
        raise ValueError(f"{rotulo}: HTML com {len(raw)} bytes "
                         f"(mínimo {min_bytes}) — provável página de erro")
    # Planalto publica em cp1252; a decodificação nunca levanta (256 pontos).
    texto = raw.decode("cp1252", errors="replace").upper()
    if marcador.upper() not in texto:
        raise ValueError(f"{rotulo}: marcador {marcador!r} ausente do HTML")


def _grava_meta(destino: Path, url: str, *, status_http: int | None,
                origem: str) -> None:
    meta = {
        "url": url,
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status_http": status_http,
        "origem": origem,
        "nota_fonte_viva": ("texto compilado: o Planalto regrava a página "
                            "quando norma superveniente altera o texto; "
                            "vintage congelada pela existência do arquivo"),
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, meta_path)


def fetch_norma(nome: str, *, force: bool = False) -> Path:
    """Baixa (seed-first) uma norma de NORMAS para data/raw/normas/planalto/."""
    url, marcador, min_bytes = NORMAS[nome]
    destino = RAW_PLANALTO / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.with_name(destino.name + "._meta.json")

    if destino.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(destino):
                return destino
        _valida_html(destino.read_bytes(), marcador=marcador,
                     min_bytes=min_bytes, rotulo=nome)
        _grava_meta(destino, url, status_http=None, origem="cache_local")
        return destino

    resp = requests.get(url, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    _valida_html(resp.content, marcador=marcador, min_bytes=min_bytes,
                 rotulo=nome)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    os.replace(tmp, destino)
    _grava_meta(destino, url, status_http=resp.status_code, origem="download")
    return destino


def fetch_all(*, force: bool = False) -> list[Path]:
    """Baixa (idempotente) as quatro normas-pilar."""
    return [fetch_norma(nome, force=force) for nome in NORMAS]


if __name__ == "__main__":
    for p in fetch_all():
        print("norma (Planalto):", p)
