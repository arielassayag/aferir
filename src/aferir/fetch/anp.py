"""Vendas de derivados de petróleo e biocombustíveis (ANP) — fetcher do CSV.

Fonte ABERTA, sem credencial: ANP, "Vendas de derivados de petróleo e
biocombustíveis" (dados abertos, gov.br) — vendas mensais por UF e produto,
em m³, arquivo único 1990-2025. Consumidor: aferir.inputs.combustiveis
(volumes 2024-2025 de GASOLINA C, ÓLEO DIESEL e GLP por UF — camada ad rem
do ICMS monofásico, LC 192/2022; sep=';', utf-8-sig, decimal=',').

FONTE VIVA: a ANP regrava o MESMO arquivo (mesmo nome) ao incorporar meses
correntes e revisões — o sha256 muda entre vintages. Por isso a idempotência
aqui é pela EXISTÊNCIA do CSV em data/raw/anp/ (vintage congelada, sha256 no
_meta.json): se o arquivo já existe, NADA é baixado — o pipeline offline
continua offline e determinístico. A paridade de uma vintage nova com a do
artigo se afere por igualdade NUMÉRICA das células consumidas, não por sha
(verificado em 2026-07-11: sha divergente da vintage 2026-06-26, porém
162/162 células idênticas — 27 UFs × 2 anos × 3 produtos; toda a diferença
confinada a linhas de ANO=2026, fora da janela legal 2024-2025).

Idempotência: cache em data/raw/anp/ com _meta.json (url, sha256,
collected_at). Escrita atômica (tmp + rename). datetime SÓ no fetcher.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

# Página do conjunto de dados (onde o link direto é publicado) e URL DIRETA
# do CSV — ambas verificadas por download real em 2026-07-11.
ANP_PAGINA_URL = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "vendas-de-derivados-de-petroleo-e-biocombustiveis")
ANP_CSV_URL = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "arquivos/vdpb/vendas-derivados-petroleo-e-etanol/"
    "vendas-combustiveis-m3-1990-2025.csv")

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 300

# Contrato mínimo com o consumidor (aferir.inputs.combustiveis): colunas do
# cabeçalho (sep=';', utf-8-sig) acessadas após normalização de acentos.
_COLUNAS_ESPERADAS = ("ANO", "UNIDADE DA FEDERAÇÃO", "PRODUTO", "VENDAS")

_FONTE = ("ANP, Vendas de derivados de petróleo e biocombustíveis por UF "
          "(m³, 1990-2025) — dados abertos, sem credencial")
_NOTA_FONTE_VIVA = (
    "fonte VIVA: a ANP regrava o mesmo arquivo com meses/revisões novos; "
    "paridade entre vintages afere-se por igualdade numérica dos volumes "
    "2024-2025 (GASOLINA C, ÓLEO DIESEL, GLP por UF), não por sha256")


def _valida_cabecalho(path: Path) -> None:
    """Falha cedo se o CSV baixado não tiver as colunas que o pipeline lê."""
    with open(path, encoding="utf-8-sig") as fh:
        cabecalho = [c.strip() for c in fh.readline().strip().split(";")]
    faltam = [c for c in _COLUNAS_ESPERADAS if c not in cabecalho]
    if faltam:
        raise ValueError(
            f"ANP CSV: colunas ausentes no cabeçalho: {faltam} "
            f"(cabeçalho lido: {cabecalho})")


def _grava_meta(destino: Path, collected_at: str, nota_coleta: str) -> None:
    """_meta.json do domínio (data/raw/anp/): url, sha256, collected_at."""
    meta_path = destino.parent / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({
        "fonte": _FONTE,
        "pagina": ANP_PAGINA_URL,
        "url": ANP_CSV_URL,
        "nota_fonte_viva": _NOTA_FONTE_VIVA,
        "nota_coleta": nota_coleta,
        "bytes": destino.stat().st_size,
        "sha256": {destino.name: sha256_file(destino)},
        "collected_at": collected_at,
    })
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")


def fetch_anp_csv(*, force: bool = False, destino: Path | None = None) -> Path:
    """Baixa (idempotente) o CSV de vendas ANP para data/raw/anp/.

    Se o CSV já existe e force=False, NÃO toca a rede (fonte viva: refazer o
    download trocaria a vintage congelada); apenas completa o _meta.json a
    partir do arquivo local, caso falte. `destino` só é parametrizado para
    testes — o pipeline usa sempre config.RAW_ANP_CSV.
    """
    if destino is None:
        destino = config.RAW_ANP_CSV
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.parent / "_meta.json"

    if destino.exists() and not force:
        if not meta_path.exists():
            # vintage pré-existente sem meta: registra sha/coleta sem rede;
            # collected_at inferido do mtime do arquivo (declarado na nota).
            mtime = datetime.fromtimestamp(destino.stat().st_mtime,
                                           tz=timezone.utc)
            _grava_meta(destino, mtime.isoformat(),
                        "collected_at inferido do mtime do CSV pré-existente "
                        "(vintage congelada; meta gravado a posteriori)")
        return destino

    resp = requests.get(ANP_CSV_URL, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    _valida_cabecalho(tmp)
    os.replace(tmp, destino)
    _grava_meta(destino, datetime.now(timezone.utc).isoformat(),
                "download direto da URL oficial (escrita atômica tmp+rename)")
    return destino


if __name__ == "__main__":
    print("ANP vendas de derivados (m³, 1990-2025):", fetch_anp_csv())
