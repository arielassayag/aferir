"""Proveniência: todo número do pipeline carrega valor + fórmula + fonte.

Padrão herdado do v1 (dataclass Num) com duas correções estruturais:
 (i) rótulos fechados em Enum — não há string livre;
 (ii) o MANIFEST de execução é gerado do próprio grafo de Nums, nunca
     escrito à mão (a banca v1 encontrou proveniência desatualizada).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Label(str, Enum):
    OFICIAL = "OFICIAL"          # número publicado por órgão oficial (com URL)
    DADO = "DADO"                # lido de fonte primária aberta
    DERIVADO = "DERIVADO"        # calculado por fórmula a partir de DADO/OFICIAL
    CONVENCAO = "CONVENCAO"      # escolha metodológica declarada (fork)


@dataclass(frozen=True)
class Num:
    valor: float
    formula: str                 # expressão legível, ex.: "R_M / (B_M*(1-pi) - CB_M)"
    fonte: str                   # dispositivo legal, endpoint, arquivo ou Num de origem
    label: Label
    unidade: str = ""            # "R$ bi 2024", "p.p.", "% PIB"...

    def as_dict(self) -> dict:
        return {
            "valor": self.valor,
            "formula": self.formula,
            "fonte": self.fonte,
            "label": self.label.value,
            "unidade": self.unidade,
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def caminho_repo(path: Path) -> str:
    """Caminho RELATIVO à raiz do repositório (portátil e anônimo): manifestos
    nunca gravam caminho absoluto da máquina."""
    from aferir.config import V2_ROOT
    p = Path(path).resolve()
    try:
        return p.relative_to(V2_ROOT).as_posix()
    except ValueError:
        return p.name


@dataclass
class Manifest:
    """Acumula proveniência da execução e grava MANIFEST_RUN.json determinístico."""

    nums: dict[str, Num] = field(default_factory=dict)
    arquivos: dict[str, str] = field(default_factory=dict)   # path -> sha256

    def registra(self, chave: str, num: Num) -> Num:
        if chave in self.nums and self.nums[chave] != num:
            raise ValueError(f"proveniência conflitante para '{chave}'")
        self.nums[chave] = num
        return num

    def registra_arquivo(self, path: Path) -> None:
        self.arquivos[caminho_repo(path)] = sha256_file(path)

    def grava(self, path: Path) -> None:
        payload = {
            "nums": {k: v.as_dict() for k, v in sorted(self.nums.items())},
            "arquivos": dict(sorted(self.arquivos.items())),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )


MANIFEST = Manifest()
