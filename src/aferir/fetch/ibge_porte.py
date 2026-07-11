"""Porte empresarial (IBGE SIDRA) — PAC 1399, PIA 1839 e PAS (7 tabelas de receita).

Insumo do ω do Simples (A7/E1): participação das empresas de menor porte na
receita, por atividade. Três pesquisas estruturais, último ano publicado = 2023:

 - PAC t/1399  — Receita operacional líquida (v/643, Mil Reais) por divisão de
   comércio (c11065: Total, veículos/peças/motos, atacado, varejo) × faixas de
   pessoal ocupado (c319: Total, Até 19, 20-49, 50-99, 100-249, 250-499, 500+),
   nível Brasil. 4 × 7 = 28 células.
 - PIA t/1839  — Receita líquida de vendas total (v/806, Mil Reais) por tipo de
   indústria (c9117: Total, extrativas, transformação) × faixas de pessoal
   (c319: Total, Até 4, 5-29, 30-49, 50-99, 100-249, 250-499, 500+). 3 × 8 = 24.
 - PAS         — a PAS NÃO publica receita por faixas graduadas de pessoal
   (verificado 2026-07-12 em desctabapi e metadados dos agregados): o recorte
   aberto é "Total" × "Empresas com 20 ou mais pessoas ocupadas" (estrato certo
   da amostra), em 7 tabelas de receita por segmento (CNAE 2.0) — a parcela
   `<20 pessoas` sai por DIFERENÇA total − 20+, nunca por faixas fictícias.
   Variável comum v/643 (Receita operacional líquida, Mil Reais).

Códigos descobertos via desctabapi.aspx e /api/v3/agregados/{t}/metadados em
2026-07-12; janela PINADA p/2023 (pesquisas estruturais: ano fechado não muda).

Idempotência seed-first: se o JSON já existe e o sha256 bate com o sidecar,
não rebaixa (pipeline offline continua offline). Escrita atômica (tmp +
os.replace); sidecar `<arquivo>._meta.json` com url, parametros, sha256,
bytes, collected_at UTC e status_http. datetime SÓ aqui (fetcher).

Uso: PYTHONPATH=src python3 -m aferir.fetch.ibge_porte
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

RAW_SIDRA_PORTE = config.RAW / "sidra_porte"

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 180

ANO_PORTE = 2023        # último ano publicado das três pesquisas estruturais

# ------------------------------------------------------------------ PAC/PIA
# v/643 = "Receita operacional líquida (Mil Reais)"; c11065 divisão de
# comércio (4 categorias); c319 faixas de pessoal ocupado (7 na PAC).
PAC_1399_URL = ("https://apisidra.ibge.gov.br/values/t/1399/n1/all/v/643/"
                f"p/{ANO_PORTE}/c11065/all/c319/all?formato=json")
# v/806 = "Receita líquida de vendas - total (Mil Reais)"; c9117 tipo de
# indústria (3 categorias); c319 faixas de pessoal ocupado (8 na PIA).
PIA_1839_URL = ("https://apisidra.ibge.gov.br/values/t/1839/n1/all/v/806/"
                f"p/{ANO_PORTE}/c9117/all/c319/all?formato=json")

# ------------------------------------------------------------------ PAS
# Tabela SIDRA -> (código da classificação, nº de categorias, segmento).
# Cada classificação traz "1. Total(+aberturas 1.x)" e "2. Empresas com 20 ou
# mais pessoas ocupadas(+aberturas 2.x)" — o recorte total × 20+ vem no MESMO
# payload. v/643 comum às 7 tabelas.
PAS_TABELAS: dict[int, tuple[int, int, str]] = {
    2611: (12356, 27, "serviços prestados às famílias"),
    2624: (12357, 31, "serviços de informação e comunicação"),
    2635: (12358, 38, "serviços profissionais, administrativos e complementares"),
    2650: (12359, 42, "transportes, serviços auxiliares aos transportes e correios"),
    2665: (12360, 6, "atividades imobiliárias"),
    2676: (12361, 10, "serviços de manutenção e reparação"),
    2695: (12362, 8, "outras atividades de serviços"),
}


def _pas_url(tabela: int) -> str:
    classificacao = PAS_TABELAS[tabela][0]
    return (f"https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/643/"
            f"p/{ANO_PORTE}/c{classificacao}/all?formato=json")


def _valida_payload(linhas: list[dict], *, variavel: str, n_linhas: int,
                    rotulo: str) -> None:
    """Falha cedo se a API devolver variável, ano ou grade inesperados."""
    if len(linhas) != n_linhas:
        raise ValueError(f"{rotulo}: esperadas {n_linhas} linhas de dados, "
                         f"vieram {len(linhas)}")
    variaveis = {row.get("D2C") for row in linhas}
    if variaveis != {variavel}:
        raise ValueError(f"{rotulo}: variável inesperada: {variaveis}")
    anos = {row.get("D3C") for row in linhas}
    if anos != {str(ANO_PORTE)}:
        raise ValueError(f"{rotulo}: ano inesperado: {anos}")


def _fetch_json(url: str, destino: Path, *, variavel: str, n_linhas: int,
                parametros: dict, force: bool = False) -> Path:
    """Baixa (seed-first) um payload apisidra e grava JSON + sidecar _meta.

    Se o arquivo já existe e o sha256 confere com o sidecar, NÃO toca a rede.
    Arquivo pré-existente sem sidecar é validado e registrado sem rede
    (origem cache_local).
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.with_name(destino.name + "._meta.json")

    if destino.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(destino):
                return destino
        bruto = json.loads(destino.read_text(encoding="utf-8"))
        _valida_payload(bruto[1:], variavel=variavel, n_linhas=n_linhas,
                        rotulo=destino.name)
        _grava_meta(destino, url, parametros, status_http=None,
                    origem="cache_local")
        return destino

    resp = requests.get(url, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    bruto = resp.json()
    # 1ª linha do payload apisidra = cabeçalho-descritor; dados = bruto[1:].
    _valida_payload(bruto[1:], variavel=variavel, n_linhas=n_linhas,
                    rotulo=destino.name)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    os.replace(tmp, destino)
    _grava_meta(destino, url, parametros, status_http=resp.status_code,
                origem="download")
    return destino


def _grava_meta(destino: Path, url: str, parametros: dict, *,
                status_http: int | None, origem: str) -> None:
    meta = {
        "url": url,
        "parametros": parametros,
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status_http": status_http,
        # "download" = baixado nesta execução; "cache_local" = arquivo já
        # presente (registro sem rede, para auditoria do replicador).
        "origem": origem,
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, meta_path)


def fetch_pac(*, force: bool = False) -> Path:
    """PAC 1399: receita operacional líquida × divisão × faixa (2023)."""
    return _fetch_json(
        PAC_1399_URL, RAW_SIDRA_PORTE / f"pac_1399_{ANO_PORTE}.json",
        variavel="643", n_linhas=28,
        parametros={"tabela": 1399, "variavel": 643, "periodo": ANO_PORTE,
                    "c11065": "all", "c319": "all", "nivel": "n1"},
        force=force)


def fetch_pia(*, force: bool = False) -> Path:
    """PIA 1839: receita líquida de vendas × tipo de indústria × faixa (2023)."""
    return _fetch_json(
        PIA_1839_URL, RAW_SIDRA_PORTE / f"pia_1839_{ANO_PORTE}.json",
        variavel="806", n_linhas=24,
        parametros={"tabela": 1839, "variavel": 806, "periodo": ANO_PORTE,
                    "c9117": "all", "c319": "all", "nivel": "n1"},
        force=force)


def fetch_pas(tabela: int, *, force: bool = False) -> Path:
    """PAS: receita operacional líquida total × 20+ do segmento (2023)."""
    classificacao, n_categorias, _segmento = PAS_TABELAS[tabela]
    return _fetch_json(
        _pas_url(tabela), RAW_SIDRA_PORTE / f"pas_{tabela}_{ANO_PORTE}.json",
        variavel="643", n_linhas=n_categorias,
        parametros={"tabela": tabela, "variavel": 643, "periodo": ANO_PORTE,
                    f"c{classificacao}": "all", "nivel": "n1"},
        force=force)


def fetch_all(*, force: bool = False) -> list[Path]:
    """Baixa (idempotente) PAC + PIA + as 7 tabelas PAS."""
    paths = [fetch_pac(force=force), fetch_pia(force=force)]
    for tabela in PAS_TABELAS:
        paths.append(fetch_pas(tabela, force=force))
    return paths


if __name__ == "__main__":
    for p in fetch_all():
        print("porte IBGE:", p)
