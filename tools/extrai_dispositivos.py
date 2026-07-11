"""Extrator determinístico dos dispositivos legais citados no manuscrito (L4).

Varre docs/artigo/*.md e emite a lista canônica de dispositivos citados,
um por linha, no formato `norma;dispositivo;arquivos`. É ESTE script que
define o universo que metadata/legal_map.csv precisa cobrir: o teste
tests/test_legal_map.py falha se qualquer dispositivo aqui extraído não
tiver linha no mapa.

Normalização documentada (contrato do teste):
  * a unidade canônica é o ARTIGO (ou o Anexo em algarismo romano) por
    norma; parágrafos, incisos e alíneas citados no texto ("art. 475,
    §11", "art. 350, II, 'b'") resolvem-se ao artigo que os encabeça;
  * menções soltas a parágrafo sem artigo na mesma citação ("o §11
    obriga") não gera token novo: o artigo já foi citado ao lado;
  * intervalos e enumerações expandem-se artigo a artigo ("arts. 349-369",
    "arts. 109-117 e 128", "arts. 4º e 12");
  * atribuição de norma, nesta ordem: (1) prefixo explícito ("LC 227/2026,
    arts. ...", "ADCT, art. ..."); (2) sufixo explícito ("arts. 109-110 da
    LC 227/2026", "art. 82 do ADCT", "Anexo XVII da LC 214"); (3) padrão
    (default): LC 214/2025, norma-base do manuscrito;
  * "LC 214" e "LC 214/2025" são a mesma norma (idem 227); "Res. CGIBS
    nº 6/2026" normaliza para "Res. CGIBS 6/2026";
  * Anexos legais são apenas os de numeração ROMANA com 2+ caracteres
    ("Anexo XVI", "Anexo XVII"); "Anexo A/B/C/D" são anexos internos do
    próprio artigo e "Anexo 03" é caderno do RREO — ambos ignorados;
  * normas citadas sem dispositivo (Res.-TCU 388/2026 e 389/2026, Decreto
    5.059/2004, EC 132/2023) não são extraídas por este regex; o
    legal_map.csv as cobre em linhas próprias, além do mínimo exigido.

Determinismo: entrada lida em ordem lexicográfica de nome de arquivo,
saída ordenada por (norma, tipo, número). Sem rede, sem datetime.

Uso: cd ~/IBS/v2 && PYTHONPATH=src python3 tools/extrai_dispositivos.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
DOCS = V2_ROOT / "docs" / "artigo"

# ---------------------------------------------------------------- normas
# padrão regex -> nome canônico
_NORMAS = [
    (r"LC\s+214(?:/2025)?", "LC 214/2025"),
    (r"LC\s+227(?:/2026)?", "LC 227/2026"),
    (r"LC\s+123(?:/2006)?", "LC 123/2006"),
    (r"ADCT|Ato\s+das\s+Disposições\s+Constitucionais\s+Transitórias",
     "ADCT"),
    (r"Res\.\s*CGIBS\s*nº\s*6/2026", "Res. CGIBS 6/2026"),
]
_NORMA_RE = "|".join(f"(?:{p})" for p, _ in _NORMAS)
_DEFAULT = "LC 214/2025"

# lista de artigos: número (com º opcional), intervalos por hífen e
# enumerações por vírgula-dígito ou " e " — sem engolir incisos romanos
# (", II"), parágrafos (", §1º") nem alíneas (', "b"')
_NUM = r"\d+º?"
_LIST = rf"{_NUM}(?:\s*-\s*{_NUM})?(?:(?:,\s*(?=\d)|\s+e\s+(?=\d)){_NUM}(?:\s*-\s*{_NUM})?)*"
_ROMANO = r"[IVXL]{2,}"

_PADRAO = re.compile(
    rf"(?:(?P<pre>{_NORMA_RE}),?\s+(?P<pre_arts>arts?\.\s+{_LIST})"
    rf"|(?P<pos_arts>arts?\.\s+{_LIST})\s+d[aoe]s?\s+(?P<pos>{_NORMA_RE})"
    rf"|Anexo\s+(?P<anexo_pos>{_ROMANO})\s+da\s+(?P<anexo_norma>{_NORMA_RE})"
    rf"|Anexo\s+(?P<anexo>{_ROMANO})"
    rf"|(?P<bare>arts?\.\s+{_LIST}))"
)


def _canon_norma(txt: str) -> str:
    for padrao, nome in _NORMAS:
        if re.fullmatch(padrao, txt):
            return nome
    raise ValueError(f"norma não reconhecida: {txt!r}")


def _expande(lista: str) -> list[int]:
    """'349-369 e 472-473' -> [349, ..., 369, 472, 473] (determinístico)."""
    nums: list[int] = []
    for a, b in re.findall(rf"({_NUM})(?:\s*-\s*({_NUM}))?", lista):
        ini = int(a.rstrip("º"))
        fim = int(b.rstrip("º")) if b else ini
        if fim < ini:
            raise ValueError(f"intervalo invertido: {lista!r}")
        nums.extend(range(ini, fim + 1))
    return nums


def extrai(docs_dir: Path = DOCS) -> dict[tuple[str, str], list[str]]:
    """Retorna {(norma, dispositivo): [arquivos .md, ordenados]}."""
    achados: dict[tuple[str, str], set[str]] = {}
    for md in sorted(docs_dir.glob("*.md")):
        texto = re.sub(r"\s+", " ", md.read_text(encoding="utf-8"))
        for m in _PADRAO.finditer(texto):
            if m.group("pre"):
                norma, corpo = _canon_norma(m.group("pre")), m.group("pre_arts")
            elif m.group("pos"):
                norma, corpo = _canon_norma(m.group("pos")), m.group("pos_arts")
            elif m.group("anexo_pos"):
                chave = (_canon_norma(m.group("anexo_norma")),
                         f"Anexo {m.group('anexo_pos')}")
                achados.setdefault(chave, set()).add(md.name)
                continue
            elif m.group("anexo"):
                achados.setdefault((_DEFAULT, f"Anexo {m.group('anexo')}"),
                                   set()).add(md.name)
                continue
            else:
                norma, corpo = _DEFAULT, m.group("bare")
            lista = re.sub(r"^arts?\.\s+", "", corpo)
            for n in _expande(lista):
                achados.setdefault((norma, f"art. {n}"), set()).add(md.name)
    return {k: sorted(v) for k, v in achados.items()}


def _ordem(chave: tuple[str, str]) -> tuple[str, int, int]:
    norma, disp = chave
    if disp.startswith("art. "):
        return (norma, 0, int(disp.removeprefix("art. ")))
    romanos = {"I": 1, "V": 5, "X": 10, "L": 50}
    algarismos = disp.removeprefix("Anexo ")
    valor, anterior = 0, 0
    for c in reversed(algarismos):
        v = romanos[c]
        valor += v if v >= anterior else -v
        anterior = max(anterior, v)
    return (norma, 1, valor)


def main() -> int:
    mapa = extrai()
    for (norma, disp) in sorted(mapa, key=_ordem):
        print(f"{norma};{disp};{','.join(mapa[(norma, disp)])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
