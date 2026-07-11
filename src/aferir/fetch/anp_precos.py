"""Preços médios mensais de revenda por UF (ANP-SLP) — fetcher do XLSX.

Fonte ABERTA, sem credencial: ANP, Sistema de Levantamento de Preços (SLP),
"Série Histórica do Levantamento de Preços — Mensal — Estados (desde janeiro
de 2013)" (gov.br) — preço médio de REVENDA (ao consumidor) por mês, UF e
produto, em R$/l. Consumidor: aferir.inputs.deducao_etanol (preço do ETANOL
HIDRATADO 2024-2025 por UF×mês — dedução ad valorem do EHC no alvo estadual;
o EHC é monofásico na LC 214, art. 172, VI, mas está fora dos convênios
ad rem da LC 192/2022, logo recolhe ICMS ad valorem HOJE).

FONTE VIVA: a ANP regrava o MESMO arquivo (mesmo nome) ao incorporar meses
correntes — o sha256 muda entre vintages. Idempotência pela EXISTÊNCIA do
XLSX em data/raw/anp_precos/ (vintage congelada, sha256 no _meta.json): se o
arquivo já existe, NADA é baixado. A paridade de uma vintage nova se afere
por igualdade NUMÉRICA das células consumidas (ETANOL HIDRATADO, 27 UFs ×
24 meses de 2024-2025), não por sha — mesmo protocolo do fetch.anp.

Idempotência: cache em data/raw/anp_precos/ com _meta.json (url, sha256,
collected_at). Escrita atômica (tmp + rename). datetime SÓ no fetcher.
"""
from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

# Página da série histórica (onde o link é publicado) e URL DIRETA do XLSX —
# ambas verificadas por download real em 2026-07-13.
ANP_PRECOS_PAGINA_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/precos-revenda-e-de-distribuicao-combustiveis/"
    "serie-historica-do-levantamento-de-precos")
ANP_PRECOS_XLSX_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/precos-revenda-e-de-distribuicao-combustiveis/shlp/mensal/"
    "mensal-estados-desde-jan2013.xlsx")

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 300

_FONTE = ("ANP-SLP, Série Histórica do Levantamento de Preços — Mensal — "
          "Estados (desde jan/2013), preço médio de revenda em R$/l — dado "
          "aberto, sem credencial")
_NOTA_FONTE_VIVA = (
    "fonte VIVA: a ANP regrava o mesmo arquivo com meses novos; paridade "
    "entre vintages afere-se por igualdade numérica dos preços consumidos "
    "(ETANOL HIDRATADO, 27 UFs × 24 meses de 2024-2025), não por sha256")


def _valida_xlsx(path: Path) -> None:
    """Falha cedo se o download não for um XLSX válido (zip OOXML)."""
    if not zipfile.is_zipfile(path):
        raise ValueError(f"ANP preços: {path.name} não é um XLSX válido")


def _grava_meta(destino: Path, collected_at: str, nota_coleta: str) -> None:
    """_meta.json do domínio (data/raw/anp_precos/): url, sha256, coleta."""
    meta_path = destino.parent / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({
        "fonte": _FONTE,
        "pagina": ANP_PRECOS_PAGINA_URL,
        "url": ANP_PRECOS_XLSX_URL,
        "nota_fonte_viva": _NOTA_FONTE_VIVA,
        "nota_coleta": nota_coleta,
        "bytes": destino.stat().st_size,
        "sha256": {destino.name: sha256_file(destino)},
        "collected_at": collected_at,
    })
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")


def fetch_anp_precos_xlsx(*, force: bool = False,
                          destino: Path | None = None) -> Path:
    """Baixa (idempotente) o XLSX de preços mensais para data/raw/anp_precos/.

    Se o XLSX já existe e force=False, NÃO toca a rede (fonte viva: refazer o
    download trocaria a vintage congelada); apenas completa o _meta.json a
    partir do arquivo local, caso falte. `destino` só é parametrizado para
    testes — o pipeline usa sempre config.RAW_ANP_PRECOS_XLSX.
    """
    if destino is None:
        destino = config.RAW_ANP_PRECOS_XLSX
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.parent / "_meta.json"

    if destino.exists() and not force:
        if not meta_path.exists():
            mtime = datetime.fromtimestamp(destino.stat().st_mtime,
                                           tz=timezone.utc)
            _grava_meta(destino, mtime.isoformat(),
                        "collected_at inferido do mtime do XLSX pré-existente "
                        "(vintage congelada; meta gravado a posteriori)")
        return destino

    resp = requests.get(ANP_PRECOS_XLSX_URL, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    _valida_xlsx(tmp)
    os.replace(tmp, destino)
    _grava_meta(destino, datetime.now(timezone.utc).isoformat(),
                "download direto da URL oficial (escrita atômica tmp+rename)")
    return destino


if __name__ == "__main__":
    print("ANP-SLP preços mensais por UF (R$/l, desde 2013):",
          fetch_anp_precos_xlsx())
