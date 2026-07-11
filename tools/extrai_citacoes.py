#!/usr/bin/env python3
"""Extração determinística das citações do manuscrito e QA 1:1 contra
docs/artigo/referencias.bib (item L5 da revisão).

Fontes varridas (na ordem, sempre as mesmas):
  - docs/artigo/*.md          corpo, capa e anexos (glob de 1º nível);
  - src/aferir/tables.py      strings de fonte/conceito das tabelas T1-T4;
  - data/inputs/comparadores.csv  coluna de fonte da Tabela C.1 (lida por
                              tables.py e renderizada no manuscrito).

Extração (regex, sem heurística de linguagem):
  1. parentética: "(Autor, 2020)", "(Autor; Autor, 2020)" e listas
     "(A, 2019; B; C, 2023)" — partes sem ano acumulam como coautores da
     próxima parte com ano (convenção do próprio artigo);
  2. narrativa: "Autor (2020)", "Autor e Autor (2020)";
  3. aliases explícitos (tabela ALIASES): normas citadas pela espécie e
     número (LC 214/2025, Res.-TCU 388/2026...) e notas técnicas citadas
     pela data (NT SERT de julho de 2024, SERT/MF de 23/08/2024) — cobrem
     a direção .bib -> corpo para entradas que não usam autor-data.

Casamento citação -> entrada: sobrenome(s)/sigla normalizados (sem acento,
casefold, sem sufixo Jr.) + ano. Ambiguidade (mesmo autor e ano em duas
entradas) só é aceita se resolvida em DESAMBIGUA; senão, falha ruidosa.

Saída: metadata/qa_citacoes_referencias.csv (separador ';'):
  chave;citada_em;status  com status em {ok, orfa, sem_referencia}.
  - uma linha por chave do .bib (ok se citada em algum arquivo; orfa senão);
  - uma linha por citação autor-data do corpo sem entrada (sem_referencia).

Uso:  PYTHONPATH=src python3 tools/extrai_citacoes.py
"""
from __future__ import annotations

import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from aferir.manuscript import _parse_bib  # noqa: E402

ARTIGO = ROOT / "docs" / "artigo"
BIB = ARTIGO / "referencias.bib"
TABLES_PY = ROOT / "src" / "aferir" / "tables.py"
COMPARADORES = ROOT / "data" / "inputs" / "comparadores.csv"
SAIDA = ROOT / "metadata" / "qa_citacoes_referencias.csv"

_ANO = r"(?:1[89]|20)\d{2}"
_PLACEHOLDER_RE = re.compile(r"\{\{csv:[^}]*\}\}")
_PAREN_RE = re.compile(r"\(([^()]{1,300})\)")
_PARTE_RE = re.compile(rf"\s*(.+?),\s*({_ANO})\b")
_NARRATIVA_RE = re.compile(
    rf"((?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'.\-]*)"
    rf"(?:\s+(?:e|de|da|do)\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'.\-]*"
    rf"|\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'.\-]*)*)"
    rf"\s+\(({_ANO})\)")

# entradas citadas no corpo por espécie/número (normas) ou por data (NTs),
# nunca por autor-data — regex -> chave do .bib (direção .bib -> corpo).
ALIASES: list[tuple[str, str]] = [
    ("brasil2023ec132", r"Emenda Constitucional nº 132|\bEC 132\b"),
    ("brasil2025lc214", r"\bLC 214\b|Lei Complementar nº 214"),
    ("brasil2026lc227", r"\bLC 227\b|Lei Complementar nº 227"),
    ("brasil2004decreto5059", r"Decreto 5\.059/2004"),
    ("brasil2026pldo2027",
     r"\bPLDO\b|Projeto de Lei de Diretrizes Orçamentárias"),
    ("cgibs2026res6", r"Res\. CGIBS nº 6/2026|Resolução CGIBS nº 6"),
    ("tcu2026res388", r"Res\.-TCU 388/2026|Resolução-TCU nº 388"),
    ("tcu2026res389", r"Res\.-TCU 389/2026|Resolução-TCU nº 389"),
    ("sert2023", r"SERT/MF ago/2023|de agosto de 2023"),
    ("sert2024",
     r"NT SERT(?! ?(?:de 23/08|ago))|SERT(?:/MF)? de julho de 2024"
     r"|SERT/MF jul/2024"),
    ("sert2024impacto",
     r"SERT/MF\s+de\s+23/08/2024|SERT/MF ago/2024|23 de agosto de 2024"),
    ("orairgobetti2019", r"TD 2530|Orair & Gobetti"),
    ("gobetti2023", r"CC-59|Gobetti, Orair & Monteiro"),
    ("cebreiro2025", r"Cebreiro et al\.|WP/2025/266"),
    ("ccif2019", r"CCiF NT v2\.2"),
    ("imbgo2023", r"IMB-GO \(2023\)"),
    ("cni2023", r"CNI/LCA"),
    ("siqueira2024", r"Siqueira, Nogueira & Luna"),
]

# mesmo autor institucional e mesmo ano em duas entradas: a citação
# autor-data "(SERT/MF, 2024)" refere-se à NT de julho (a de agosto é
# sempre citada pela data e casa pelos ALIASES).
DESAMBIGUA: dict[tuple[str, str], str] = {("sert/mf", "2024"): "sert2024"}


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.replace("’", "'").casefold()
    txt = re.sub(r"\bjr\.?", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip(" .")
    return txt


def _nomes_entrada(e: dict) -> set[str]:
    """Formas normalizadas pelas quais a entrada pode ser citada."""
    autor = e.get("author", "")
    nomes: set[str] = set()
    if autor.startswith("{") and autor.endswith("}"):
        v = autor[1:-1].strip()
        m = re.fullmatch(r"(.*?)\s*\[([^\]]+)\]", v)
        if m:
            nomes.add(_norm(m.group(2)))          # sigla: CCiF, SERT/MF...
            nomes.add(_norm(m.group(1)))
        else:
            nomes.add(_norm(v))
    else:
        sobren = [p.split(",")[0].strip() for p in autor.split(" and ")]
        nomes.add(_norm(sobren[0]))               # 1º autor (cobre "et al.")
        nomes.add(_norm("; ".join(sobren)))       # (A; B; C, ano)
        nomes.add(_norm(" e ".join(sobren)))      # narrativa "A e B (ano)"
    return {n for n in nomes if n}


def _texto_md(path: Path) -> str:
    txt = _PLACEHOLDER_RE.sub(" ", path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", txt)


def _citas_parenteticas(texto: str) -> list[tuple[str, str]]:
    citas: list[tuple[str, str]] = []
    for g in _PAREN_RE.finditer(texto):
        grupo = g.group(1)
        if not re.search(rf",\s*{_ANO}\b", grupo):
            continue
        acum: list[str] = []
        for parte in grupo.split(";"):
            m = _PARTE_RE.match(parte)
            if m:
                autor = "; ".join([*(a.strip() for a in acum),
                                   m.group(1).strip()])
                citas.append((autor, m.group(2)))
                acum = []
            else:
                acum.append(parte.strip())
    return citas


def _citas_narrativas(texto: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _NARRATIVA_RE.finditer(texto)]


def _casa(autor: str, ano: str, entradas: list[dict]) -> str | None:
    """Chave do .bib para a citação (autor, ano); None se não houver.

    A captura narrativa pode absorver palavra capitalizada anterior ao
    autor ("VIVAT de Keen e Smith (2000)"): se a forma completa não casar,
    tenta-se deterministicamente o sufixo, descartando uma palavra à
    esquerda por vez."""
    alvo = _norm(re.sub(r"\s+et al\.?$", "", autor.strip()))
    palavras = alvo.split(" ")
    for i in range(len(palavras)):
        sufixo = " ".join(palavras[i:])
        cand = [e["_key"] for e in entradas
                if e.get("year", "") == ano and sufixo in _nomes_entrada(e)]
        if len(cand) > 1:
            chave = DESAMBIGUA.get((sufixo, ano))
            if chave in cand:
                return chave
            raise ValueError(
                f"citação ambígua sem regra em DESAMBIGUA: ({autor}, {ano}) "
                f"-> {sorted(cand)}")
        if cand:
            return cand[0]
    return None


def gera_qa() -> list[dict]:
    """QA 1:1 — uma linha por chave do .bib (ok|orfa) + uma linha por
    citação autor-data sem entrada (sem_referencia). Determinístico."""
    entradas = _parse_bib(BIB)
    fontes_md = sorted(ARTIGO.glob("*.md"))
    aux = [(TABLES_PY.name, TABLES_PY.read_text(encoding="utf-8")),
           (COMPARADORES.name, COMPARADORES.read_text(encoding="utf-8"))]

    citada_em: dict[str, set[str]] = {e["_key"]: set() for e in entradas}
    sem_ref: dict[tuple[str, str], set[str]] = {}

    for path in fontes_md:
        texto = _texto_md(path)
        vistos: set[tuple[str, str]] = set()
        for autor, ano in (_citas_parenteticas(texto)
                           + _citas_narrativas(texto)):
            if (autor, ano) in vistos:
                continue
            vistos.add((autor, ano))
            chave = _casa(autor, ano, entradas)
            if chave:
                citada_em[chave].add(path.name)
            else:
                sem_ref.setdefault((autor, ano), set()).add(path.name)

    for nome_arq, texto in [*aux, *((p.name, _texto_md(p))
                                    for p in fontes_md)]:
        for chave, padrao in ALIASES:
            if chave not in citada_em:
                raise KeyError(f"ALIASES aponta chave inexistente: {chave}")
            if re.search(padrao, texto):
                citada_em[chave].add(nome_arq)

    linhas = [{"chave": e["_key"],
               "citada_em": ", ".join(sorted(citada_em[e["_key"]])),
               "status": "ok" if citada_em[e["_key"]] else "orfa"}
              for e in sorted(entradas, key=lambda e: e["_key"])]
    linhas += [{"chave": f"{autor} ({ano})",
                "citada_em": ", ".join(sorted(arqs)),
                "status": "sem_referencia"}
               for (autor, ano), arqs in sorted(sem_ref.items())]
    return linhas


def qa_csv_texto(linhas: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["chave", "citada_em", "status"],
                       delimiter=";", lineterminator="\n")
    w.writeheader()
    w.writerows(linhas)
    return buf.getvalue()


def main() -> None:
    linhas = gera_qa()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(qa_csv_texto(linhas), encoding="utf-8")
    n_ok = sum(1 for r in linhas if r["status"] == "ok")
    orfas = [r["chave"] for r in linhas if r["status"] == "orfa"]
    soltas = [r["chave"] for r in linhas if r["status"] == "sem_referencia"]
    print(f"{SAIDA.relative_to(ROOT)}: {n_ok} entradas citadas, "
          f"{len(orfas)} órfã(s) {orfas}, "
          f"{len(soltas)} citação(ões) sem entrada {soltas}")


if __name__ == "__main__":
    main()
