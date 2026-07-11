"""Fechamento 1:1 entre docs/artigo/referencias.bib e as citações do
manuscrito (item L5 da revisão): nenhuma entrada órfã na lista e nenhuma
citação autor-data sem entrada. A extração é a de tools/extrai_citacoes.py
(determinística; .md do artigo + strings de fonte de tables.py e da
Tabela C.1 em comparadores.csv), e o CSV de QA versionado em
metadata/qa_citacoes_referencias.csv deve espelhar o estado corrente."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from aferir import config
from aferir.manuscript import _parse_bib

ROOT = Path(__file__).resolve().parents[1]

# exceções DOCUMENTADAS ao 1:1 (ex.: norma citada apenas em nota).
# Hoje não há nenhuma: qualquer inclusão exige justificativa ao lado.
EXCECOES_ORFAS: set[str] = set()          # chaves do .bib sem citação
EXCECOES_SEM_REFERENCIA: set[str] = set()  # citações "Autor (ano)" sem entrada


def _extrai():
    spec = importlib.util.spec_from_file_location(
        "extrai_citacoes", ROOT / "tools" / "extrai_citacoes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bibliografia_1to1():
    qa = _extrai().gera_qa()
    orfas = {r["chave"] for r in qa
             if r["status"] == "orfa"} - EXCECOES_ORFAS
    sem_ref = {r["chave"] for r in qa
               if r["status"] == "sem_referencia"} - EXCECOES_SEM_REFERENCIA
    assert not orfas, (
        f"entradas do referencias.bib sem citação no manuscrito: "
        f"{sorted(orfas)}")
    assert not sem_ref, (
        f"citações autor-data do manuscrito sem entrada no referencias.bib: "
        f"{sorted(sem_ref)}")


def test_qa_csv_versionado_espelha_estado_corrente():
    """metadata/qa_citacoes_referencias.csv é regenerado a cada mudança de
    citação/entrada (PYTHONPATH=src python3 tools/extrai_citacoes.py)."""
    mod = _extrai()
    csv_path = ROOT / "metadata" / "qa_citacoes_referencias.csv"
    assert csv_path.exists(), "rode tools/extrai_citacoes.py"
    assert csv_path.read_text(encoding="utf-8") == mod.qa_csv_texto(
        mod.gera_qa()), "CSV de QA desatualizado: rode tools/extrai_citacoes.py"


def test_urls_com_urldate_uniforme():
    """Forma ABNT uniforme: toda entrada com url tem urldate AAAA-MM-DD
    (vira 'Acesso em:' no render); nenhuma entrada sem autor ou sem ano."""
    for e in _parse_bib(config.REFERENCIAS_BIB):
        chave = e["_key"]
        assert e.get("author"), f"{chave}: sem author"
        assert re.fullmatch(r"\d{4}", e.get("year", "")), f"{chave}: sem year"
        if e.get("url"):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.get("urldate", "")), (
                f"{chave}: url sem urldate AAAA-MM-DD (Acesso em: ausente)")
