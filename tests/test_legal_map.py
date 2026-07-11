"""L4 — completude do mapa de dispositivos legais (metadata/legal_map.csv).

Contrato: TODO dispositivo citado no manuscrito (extraído automaticamente
pelo tools/extrai_dispositivos.py, cuja normalização está documentada no
próprio módulo: unidade = artigo/Anexo por norma, intervalos expandidos,
default LC 214/2025) precisa ter linha em metadata/legal_map.csv com a
mesma chave (norma, dispositivo). O mapa PODE conter linhas a mais
(normas citadas sem dispositivo, p.ex. Res.-TCU 388/2026); nunca a menos.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

from aferir import config

LEGAL_MAP = config.V2_ROOT / "metadata" / "legal_map.csv"
EXTRATOR = config.V2_ROOT / "tools" / "extrai_dispositivos.py"

_COLUNAS = ["dispositivo", "norma", "redacao", "verificado_em",
            "trecho_confirmatorio", "secoes_do_manuscrito"]


def _carrega_extrator():
    spec = importlib.util.spec_from_file_location("extrai_dispositivos",
                                                  EXTRATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _linhas_mapa() -> list[dict[str, str]]:
    with LEGAL_MAP.open(encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=";")
        assert leitor.fieldnames == _COLUNAS, (
            f"colunas do legal_map.csv fora do contrato: {leitor.fieldnames}")
        return list(leitor)


def test_legal_map_complete():
    """Nenhum dispositivo citado no manuscrito pode faltar no mapa."""
    extrator = _carrega_extrator()
    citados = extrator.extrai(config.V2_ROOT / "docs" / "artigo")
    mapa = {(r["norma"], r["dispositivo"]) for r in _linhas_mapa()}
    faltantes = sorted(set(citados) - mapa, key=extrator._ordem)
    assert not faltantes, (
        "dispositivos citados no manuscrito sem linha em legal_map.csv: "
        + "; ".join(f"{n} {d}" for n, d in faltantes))


def test_legal_map_campos_preenchidos():
    """Cada linha do mapa carrega verificação: raw + trecho + seções."""
    for r in _linhas_mapa():
        chave = f"{r['norma']} {r['dispositivo']}"
        assert r["redacao"] in {"original", "LC 227/2026", "propria"}, chave
        assert r["verificado_em"].strip(), chave
        assert len(r["trecho_confirmatorio"].strip()) >= 20, chave
        assert r["secoes_do_manuscrito"].strip(), chave
        if r["verificado_em"].startswith("data/raw/"):
            assert (config.V2_ROOT / r["verificado_em"]).exists(), (
                f"{chave}: arquivo raw ausente ({r['verificado_em']})")


def test_extrator_deterministico():
    """Duas execuções do extrator produzem exatamente o mesmo universo."""
    extrator = _carrega_extrator()
    a = extrator.extrai(config.V2_ROOT / "docs" / "artigo")
    b = extrator.extrai(config.V2_ROOT / "docs" / "artigo")
    assert a == b
