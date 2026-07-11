"""TRU nível 68 (IBGE) — fetcher do zip 2010-2021 das Tabelas de Recursos e Usos.

Fonte: FTP público do IBGE (dados abertos, sem credencial), Contas Nacionais,
Sistema de Contas Nacionais, vintage 2021 — a última edição DETALHADA
(128 produtos × 68 atividades; a série detalhada foi suspensa na mudança de
ano-base 2010→2021 — NÃO migrar para 2023). A página institucional
correspondente é config.TRU_URL; a URL direta (TRU_ZIP_URL) foi verificada
por download real em 2026-07-11 (sha256 idêntico ao cache byte a byte:
bce3e745591015ec0f4943851400b37f590950064be1456cab38e62ea3a0582c).

Idempotência: se config.RAW_TRU_ZIP já existe, NADA é baixado — o pipeline
offline continua offline. Escrita atômica (tmp + os.replace) do zip e do
_meta.json. O _meta.json do domínio (data/raw/sidra/) é atualizado por
leia-merge-escreva (padrão atualiza_meta de siconfi_comum): entradas de
OUTROS arquivos do domínio nunca são apagadas. datetime SÓ aqui (fetcher);
o cálculo downstream (aferir.inputs.tru) é livre de relógio e de rede.

Uso: PYTHONPATH=src python3 -m aferir.fetch.tru
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

# URL DIRETA e estável no FTP aberto do IBGE (diretório
# .../2021/tabelas_xls/tabelas_de_recursos_e_usos/ — vintage 2021 do SCN).
TRU_ZIP_URL = (
    "https://ftp.ibge.gov.br/Contas_Nacionais/Sistema_de_Contas_Nacionais/"
    "2021/tabelas_xls/tabelas_de_recursos_e_usos/nivel_68_2010_2021_xls.zip")

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 300

# Membros do zip efetivamente consumidos por aferir.inputs.tru
# (tab1 = oferta/impostos; tab2 = demanda/consumo intermediário).
_MEMBROS_OBRIGATORIOS = (
    f"68_tab1_{config.TRU_ANO}.xls",
    f"68_tab2_{config.TRU_ANO}.xls",
)


def _valida_zip(path: Path) -> None:
    """Falha cedo se o zip não é íntegro ou não traz as tabelas do TRU_ANO."""
    with zipfile.ZipFile(path) as z:
        nomes = set(z.namelist())
        faltam = [m for m in _MEMBROS_OBRIGATORIOS if m not in nomes]
        if faltam:
            raise ValueError(f"zip TRU sem membros esperados: {faltam}")
        defeituoso = z.testzip()
        if defeituoso is not None:
            raise ValueError(f"zip TRU com CRC inválido em: {defeituoso}")


def _le_meta(meta_path: Path) -> dict:
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def _atualiza_meta_dominio(destino: Path, *, origem: str) -> None:
    """_meta.json do domínio (data/raw/sidra/): leia-merge-escreva.

    Só a entrada deste zip é (re)escrita sob "arquivos"; chaves de outros
    arquivos do domínio e chaves de topo pré-existentes são preservadas
    (mesmo espírito de atualiza_meta em siconfi_comum). Escrita atômica.
    """
    meta_path = destino.parent / "_meta.json"
    meta = _le_meta(meta_path)
    meta.setdefault("dominio", destino.parent.name)
    meta.setdefault(
        "fonte", "FTP público do IBGE (dados abertos, sem credencial)")
    arquivos = meta.setdefault("arquivos", {})
    arquivos[destino.name] = {
        "url": TRU_ZIP_URL,
        "pagina_institucional": config.TRU_URL,
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        # "download" = baixado nesta execução; "cache_local" = arquivo já
        # presente (entrada registrada sem rede, para auditoria do replicador).
        "origem": origem,
    }
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, meta_path)


def fetch_tru_zip(*, force: bool = False) -> Path:
    """Baixa (idempotente) o zip da TRU nível 68 2010-2021 para RAW_TRU_ZIP.

    Se o arquivo já existe e force=False, NÃO toca a rede: valida o cache e
    apenas registra a entrada no _meta.json do domínio caso ainda não exista.
    """
    destino = config.RAW_TRU_ZIP
    meta_path = destino.parent / "_meta.json"
    if destino.exists() and not force:
        if destino.name not in _le_meta(meta_path).get("arquivos", {}):
            _valida_zip(destino)
            _atualiza_meta_dominio(destino, origem="cache_local")
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(TRU_ZIP_URL, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    _valida_zip(tmp)               # valida ANTES do rename: nunca publica lixo
    os.replace(tmp, destino)
    _atualiza_meta_dominio(destino, origem="download")
    return destino


if __name__ == "__main__":
    print("TRU nível 68 (IBGE):", fetch_tru_zip())
