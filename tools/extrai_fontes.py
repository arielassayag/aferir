"""Extrator LOCAL das quatro faces Helvetica Neue usadas pelas figuras.

Por que este script existe (fronteira do espelho público):
  * Helvetica Neue é fonte PROPRIETÁRIA da Apple, licenciada com o macOS —
    os TTFs em `assets/fonts/` NÃO acompanham o espelho público do projeto;
  * quem replica em macOS regenera os quatro pesos a partir da coleção do
    próprio sistema (`/System/Library/Fonts/HelveticaNeue.ttc`) com este
    script; o matplotlib não lê múltiplas faces de uma `.ttc`, daí a
    extração como TTFs autônomos;
  * sem os arquivos, `aferir.style` cai no fallback DejaVu Sans (embutida
    no matplotlib) — o pipeline segue replicável em qualquer SO, apenas
    com tipografia substituta nas figuras.

Padrões do projeto:
  * idempotente: TTF já presente no destino não é refeito;
  * escrita atômica (tmp + os.replace);
  * determinístico: mesmos bytes a cada execução — `recalcTimestamp=False`
    preserva o `head.modified` ORIGINAL da coleção (nenhum timestamp de
    geração entra no output) e o `reorderTables` default do fonttools
    grava as tabelas na ordem física canônica, sempre a mesma.
    Nota de auditoria: TTFs gerados antes deste script embutiam o instante
    da extração em `head.modified` (12 bytes: timestamp + 2 checksums
    derivados); a rasterização é idêntica, mas o sha256 difere.
  * import do fonttools SÓ dentro do main — o pacote `aferir` não depende
    dele; instale com `pip install fonttools` apenas para rodar este script.

Uso:
    python3 tools/extrai_fontes.py            # grava em assets/fonts/
    python3 tools/extrai_fontes.py --dest DIR # destino alternativo (teste)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Coleção do sistema (macOS). Fora do macOS não há o que extrair — o
# fallback DejaVu Sans de aferir.style cobre o ambiente.
TTC_SISTEMA = Path("/System/Library/Fonts/HelveticaNeue.ttc")

# Face pedida (nome PostScript, name ID 6 — estável entre versões do macOS)
# -> arquivo autônomo esperado por aferir.style._FACES.
FACES = {
    "HelveticaNeue": "HelveticaNeue-Regular.ttf",
    "HelveticaNeue-Medium": "HelveticaNeue-Medium.ttf",
    "HelveticaNeue-Bold": "HelveticaNeue-Bold.ttf",
    "HelveticaNeue-Light": "HelveticaNeue-Light.ttf",
}

DEST_PADRAO = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dest", type=Path, default=DEST_PADRAO,
        help=f"diretório de saída (default: {DEST_PADRAO})",
    )
    args = parser.parse_args(argv)

    if not TTC_SISTEMA.exists():
        print(
            f"AVISO: {TTC_SISTEMA} não existe (ambiente não-macOS?). "
            "Nada a extrair — as figuras usarão o fallback DejaVu Sans.",
            file=sys.stderr,
        )
        return 1

    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        print(
            "ERRO: fonttools ausente. Instale com:  pip install fonttools",
            file=sys.stderr,
        )
        return 1

    faltantes = {ps: nome for ps, nome in FACES.items()
                 if not (args.dest / nome).exists()}
    for nome in sorted(set(FACES.values()) - set(faltantes.values())):
        print(f"  ok (já existe): {args.dest / nome}")
    if not faltantes:
        return 0

    args.dest.mkdir(parents=True, exist_ok=True)

    # A coleção serve SÓ para mapear nome PostScript -> índice; a extração
    # em si usa TTFont(fontNumber=...), que copia as tabelas byte a byte
    # (medido: salvar direto do TTCollection RECOMPILA tabelas e altera
    # milhares de bytes; via TTFont o TTF reproduz o original).
    colecao = TTCollection(str(TTC_SISTEMA), lazy=True)
    indice_por_ps = {
        fonte["name"].getDebugName(6): i
        for i, fonte in enumerate(colecao.fonts)
    }
    colecao.close()

    ausentes = sorted(set(faltantes) - set(indice_por_ps))
    if ausentes:
        print(
            f"ERRO: faces {ausentes} não encontradas em {TTC_SISTEMA} "
            f"(disponíveis: {sorted(indice_por_ps)}).",
            file=sys.stderr,
        )
        return 1

    for ps, nome in sorted(faltantes.items()):
        destino = args.dest / nome
        tmp = destino.with_name(destino.name + ".tmp")
        # lazy=True: tabelas copiadas sem recompilar; recalcTimestamp=False:
        # head.modified ORIGINAL preservado (nenhum timestamp de geração).
        fonte = TTFont(
            str(TTC_SISTEMA), fontNumber=indice_por_ps[ps],
            lazy=True, recalcTimestamp=False,
        )
        fonte.save(str(tmp))               # reorderTables default: ordem canônica
        fonte.close()
        os.replace(tmp, destino)
        print(f"  extraída: {destino}  <-  {TTC_SISTEMA.name}[{ps}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
