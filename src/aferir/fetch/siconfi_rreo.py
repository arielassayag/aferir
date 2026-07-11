"""Fetcher SICONFI — RREO Anexo 03: ICMS líquido por UF na janela legal.

Reconstrói data/raw/siconfi_rreo/icms_uf_2024_2025.csv pela API pública do
SICONFI (endpoint rreo, sem credencial): para cada UF × ano da janela legal
(config.JANELA_RECEITA), lê o Anexo 03 do 6º bimestre e extrai, na coluna
"TOTAL (ÚLTIMOS 12 MESES)" (exercício fechado, R$ correntes):

  * ICMSLiquidoExcetoTransferenciasEFUNDEB — ICMS já líquido da cota-parte
    municipal (25%, CF art. 158, IV) e da retenção FUNDEB (20%, CF art.
    212-A, II); o gross-up algébrico é feito downstream (inputs.siconfi_estadual);
  * DeducaoDeReceitaParaFormacaoDoFUNDEB — dedução FUNDEB TOTAL do ente
    (todas as receitas-base, não só ICMS), em valor absoluto (convenção v1;
    a API publica o valor já positivo — verificado em 2026-07-11);
  * ISSLiquidoExcetoTransferenciasEFUNDEB — só o DF (CF art. 147: tributos
    municipais competem ao DF; rubrica ausente no Anexo 03 das demais UFs).

Rota (DESIGN §3): cache idempotente — se o CSV alvo existe, NADA é refeito
(o pipeline offline continua offline). Refetch integral (27 UFs × anos da
janela) apenas se o arquivo faltar, com escrita atômica (tmp + rename) e
_meta.json no diretório do domínio (url, sha256, collected_at). datetime SÓ
aqui (fetcher), nunca no cálculo.

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_rreo
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from aferir.config import JANELA_RECEITA, RAW_RREO_ICMS_CSV, SICONFI_API
from aferir.fetch.siconfi_comum import get_items_paginado
from aferir.fetch.siconfi_estadual import COD_IBGE_UF
from aferir.provenance import sha256_file

# RREO Anexo 03 (Demonstrativo da Receita Corrente Líquida), 6º bimestre:
# a coluna "TOTAL (ÚLTIMOS 12 MESES)" do período 6 (nov-dez) cobre o
# exercício encerrado — mesma extração canônica do v1 (janela legal).
ANEXO = "RREO-Anexo 03"
NR_PERIODO = 6                    # 6º bimestre (nov-dez)
COLUNA_TOTAL_12M = "12 MESES"     # casa só "TOTAL (ÚLTIMOS 12 MESES)" no Anexo 03

# cod_conta das rubricas consumidas (identificadores estáveis da API SICONFI;
# validados contra a API em 2026-07-11 — 1 ocorrência por UF × ano × coluna).
RUBRICA_ICMS_LIQ = "ICMSLiquidoExcetoTransferenciasEFUNDEB"
RUBRICA_DEDUCAO_FUNDEB = "DeducaoDeReceitaParaFormacaoDoFUNDEB"
RUBRICA_ISS_LIQ = "ISSLiquidoExcetoTransferenciasEFUNDEB"   # só DF

# Layout EXATO do CSV consumido por aferir.inputs.siconfi_estadual.
COLUNAS_CSV = [
    "uf",
    "ano",
    "icms_liquido_ex_fundeb_cotaparte_rs",
    "deducao_fundeb_total_rs",
    "iss_liquido_ex_fundeb_rs",
    "fonte",
]


def _valor_rubrica(items: list[dict], uf: str, ano: int, rubrica: str,
                   *, absoluto: bool = False) -> float:
    """Valor ÚNICO da rubrica na coluna TOTAL (ÚLTIMOS 12 MESES).

    Falha alto se a rubrica estiver ausente ou ambígua — auditabilidade
    exige exatamente uma linha por (UF, ano, rubrica, coluna).
    """
    valores = [
        float(it["valor"])
        for it in items
        if str(it.get("cod_conta")) == rubrica
        and COLUNA_TOTAL_12M in str(it.get("coluna", ""))
        and it.get("valor") is not None
    ]
    if len(valores) != 1:
        raise ValueError(
            f"RREO {uf} {ano}: rubrica {rubrica} com {len(valores)} "
            f"ocorrências na coluna '{COLUNA_TOTAL_12M}' (esperada 1): {valores}"
        )
    return abs(valores[0]) if absoluto else valores[0]


def _linha_uf(uf: str, ano: int, fonte: str) -> dict:
    """Coleta o Anexo 03 da UF/ano na API e extrai as três rubricas."""
    items, _ = get_items_paginado(
        "rreo",
        {
            "an_exercicio": ano,
            "nr_periodo": NR_PERIODO,
            "co_tipo_demonstrativo": "RREO",
            "no_anexo": ANEXO,
            "id_ente": COD_IBGE_UF[uf],
        },
    )
    if not items:
        raise ValueError(f"RREO {uf} {ano} bimestre {NR_PERIODO}: API vazia")
    return {
        "uf": uf,
        "ano": ano,
        "icms_liquido_ex_fundeb_cotaparte_rs": _valor_rubrica(
            items, uf, ano, RUBRICA_ICMS_LIQ),
        "deducao_fundeb_total_rs": _valor_rubrica(
            items, uf, ano, RUBRICA_DEDUCAO_FUNDEB, absoluto=True),
        "iss_liquido_ex_fundeb_rs": _valor_rubrica(
            items, uf, ano, RUBRICA_ISS_LIQ) if uf == "DF" else None,
        "fonte": fonte,
    }


def _grava_csv_atomico(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _grava_meta(path: Path) -> None:
    """_meta.json do domínio: endpoint-padrão, sha256 do CSV, collected_at."""
    meta_path = path.parent / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.setdefault(
        "fonte", "API SICONFI (Tesouro Nacional) — dados abertos, sem credencial"
    )
    meta.update(
        {
            "url": (
                f"{SICONFI_API}/rreo?an_exercicio=<ano>&nr_periodo={NR_PERIODO}"
                f"&co_tipo_demonstrativo=RREO&no_anexo={ANEXO}&id_ente=<cod_uf>"
            ),
            "anexo": ANEXO,
            "anos": list(JANELA_RECEITA),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "sha256": {path.name: sha256_file(path)},
        }
    )
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fetch_rreo_icms_csv() -> Path:
    """CSV alvo (config.RAW_RREO_ICMS_CSV): cache idempotente ou refetch integral.

    Se o arquivo já existe, retorna SEM tocar na rede. Senão coleta as 27 UFs
    × anos da janela legal (throttle ~4 req/s em siconfi_comum) e grava o CSV
    no layout canônico, com a coluna fonte citando endpoint e data de coleta.
    """
    if RAW_RREO_ICMS_CSV.exists():
        return RAW_RREO_ICMS_CSV

    coletado = datetime.now(timezone.utc).date().isoformat()
    fonte = (
        f"SICONFI RREO Anexo 03, periodo {NR_PERIODO} (bimestre nov-dez), "
        f"coluna TOTAL (ULTIMOS 12 MESES), R$ correntes; "
        f"{SICONFI_API}/rreo; coletado {coletado} (aferir.fetch.siconfi_rreo)"
    )
    linhas = []
    for uf in sorted(COD_IBGE_UF, key=COD_IBGE_UF.get):   # ordem IBGE (layout v1)
        for ano in JANELA_RECEITA:
            linha = _linha_uf(uf, ano, fonte)
            linhas.append(linha)
            print(
                f"[rreo {uf} {ano}] icms_liq="
                f"{linha['icms_liquido_ex_fundeb_cotaparte_rs']:.2f}",
                flush=True,
            )

    df = pd.DataFrame(linhas, columns=COLUNAS_CSV)
    esperado = len(COD_IBGE_UF) * len(JANELA_RECEITA)
    if len(df) != esperado:
        raise AssertionError(f"RREO: {len(df)} linhas coletadas != {esperado}")
    if (df["icms_liquido_ex_fundeb_cotaparte_rs"] <= 0).any():
        raise AssertionError("RREO: ICMS líquido não-positivo em alguma UF/ano")

    _grava_csv_atomico(df, RAW_RREO_ICMS_CSV)
    _grava_meta(RAW_RREO_ICMS_CSV)
    return RAW_RREO_ICMS_CSV


def main() -> None:
    path = fetch_rreo_icms_csv()
    df = pd.read_csv(path)
    anos = sorted(int(a) for a in df["ano"].unique())
    print(f"{path}: {len(df)} linhas ({df['uf'].nunique()} UFs × {anos})",
          flush=True)


if __name__ == "__main__":
    main()
