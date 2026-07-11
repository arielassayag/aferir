"""IPCA número-índice (IBGE SIDRA, tabela 1737) — fetcher do deflator legal.

Baixa a variável 2266 (IPCA - Número-índice, base: dezembro de 1993 = 100),
nível Brasil, mensal, e grava data/raw/sidra/ipca_1737.parquet no layout
consumido por aferir.inputs.ipca_pib: colunas str da própria API, das quais
o leitor usa APENAS D3N ("janeiro 2013" — o ano é o 2º token) e V (valor).
Deflator(ano→2024) downstream = média dos 12 índices de 2024 ÷ média dos 12
índices do ano; golden number de paridade: deflator 2025→2024 = 0,952229023823.

Janela PINADA 201301-202512 na própria URL: a tabela 1737 é viva (o IBGE
publica um mês novo a cada divulgação), e uma janela aberta ("p/all" ou
"p/last") mudaria os bytes do arquivo a cada re-execução, quebrando o
determinismo (mesmos insumos ⇒ mesmos outputs) e o sha256 congelado no
manifesto. 2013-2025 cobre todos os anos deflacionados pelo pipeline
(FUNDOS_JANELA_BASE 2021-2023 e JANELA_RECEITA 2024-2025, com ANO_PRECOS =
2024 exigindo os 12 meses de 2024 e 2025) — números-índice de meses já
publicados são imutáveis, então a janela fechada devolve sempre o mesmo
payload.

Idempotência: se config.RAW_IPCA_1737 já existe, NÃO refaz e NÃO toca a
rede (o pipeline offline continua offline). Escrita atômica (tmp + rename);
sidecar ipca_1737.parquet._meta.json no diretório do domínio (data/raw/sidra,
mesma convenção dos demais arquivos SIDRA) com url, sha256, bytes e
collected_at. datetime SÓ aqui (fetcher), nunca no cálculo.

Nota de auditoria: o cache herdado do v1 traz colunas extras de proveniência
(_source, _dataset, ...) e omite os códigos MC/D2C/D3C; D3N e V — os únicos
campos consumidos — são byte a byte idênticos ao payload da API (verificado
em 2026-07-11 nos 156 meses de 2013-2025).
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

# v/2266 = "IPCA - Número-índice (base: dezembro de 1993 = 100)" — conferido
# contra o campo D2N do cache local. n1/all = nível Brasil (série nacional).
SIDRA_IPCA_1737_URL = ("https://apisidra.ibge.gov.br/values/t/1737/n1/all/"
                       "v/2266/p/201301-202512?formato=json")
_VARIAVEL_ESPERADA = "IPCA - Número-índice (base: dezembro de 1993 = 100)"
_ANOS_JANELA = range(2013, 2026)      # 201301-202512 ⇒ 13 anos × 12 meses
_N_MESES = 12

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 180


def _valida_payload(linhas: list[dict]) -> None:
    """Falha cedo se a API devolver variável errada ou janela incompleta."""
    variaveis = {row.get("D2N") for row in linhas}
    if variaveis != {_VARIAVEL_ESPERADA}:
        raise ValueError(f"SIDRA 1737: variável inesperada: {variaveis}")
    meses_por_ano: dict[int, int] = {}
    for row in linhas:
        float(row["V"])               # todo valor deve ser numérico
        ano = int(str(row["D3N"]).split()[1])   # "janeiro 2013" → 2013
        meses_por_ano[ano] = meses_por_ano.get(ano, 0) + 1
    incompletos = {a: meses_por_ano.get(a, 0) for a in _ANOS_JANELA
                   if meses_por_ano.get(a, 0) != _N_MESES}
    if incompletos:
        raise ValueError(f"SIDRA 1737: anos sem 12 meses: {incompletos}")


def fetch_sidra_ipca(*, force: bool = False) -> Path:
    """Baixa (idempotente) o IPCA 1737 e grava o parquet + _meta sidecar.

    Se o parquet-alvo já existe (e force=False), retorna sem rede.
    """
    destino = config.RAW_IPCA_1737
    if destino.exists() and not force:
        return destino

    resp = requests.get(SIDRA_IPCA_1737_URL, headers=_UA, timeout=TIMEOUT_S)
    resp.raise_for_status()
    bruto = resp.json()
    # A primeira linha do payload apisidra é o cabeçalho-descritor
    # (D3N = "Mês", V = "Valor"): descartada — só as 156 linhas de dados.
    linhas = bruto[1:]
    _valida_payload(linhas)

    # Todas as colunas da API preservadas como str (layout consumível:
    # o leitor downstream usa D3N e V; o resto fica para auditoria).
    df = pd.DataFrame(linhas, dtype=str)

    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, destino)

    meta = {
        "url": SIDRA_IPCA_1737_URL,
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    return destino


if __name__ == "__main__":
    print("IPCA 1737 (SIDRA):", fetch_sidra_ipca())
