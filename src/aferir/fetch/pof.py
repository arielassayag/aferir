"""Microdados da POF 2017-2018 (IBGE FTP) — fetch dos 6 insumos brutos.

Alvo (config.RAW_POF_DIR = data/raw/pof/):
    dados_raw/ALUGUEL_ESTIMADO.txt     \\
    dados_raw/CADERNETA_COLETIVA.txt    |
    dados_raw/DESPESA_COLETIVA.txt      |  Dados_AAAAMMDD.zip
    dados_raw/DESPESA_INDIVIDUAL.txt    |
    dados_raw/MORADOR.txt              /
    doc/Dicionarios_de_variaveis.xls   —   Documentacao_AAAAMMDD.zip

Rota (dados abertos, sem credencial): índice HTTP do FTP do IBGE
(POF_MICRODADOS_URL). Os nomes dos zips carregam a data de release
(ex.: Dados_20230713.zip) e são DESCOBERTOS no índice a cada coleta —
nenhum nome de release hardcodado. Cada zip é baixado em diretório
TEMPORÁRIO e descartado: só os 6 membros consumidos por
aferir.inputs.pof persistem em data/raw/pof/ — localizados pelo basename
NORMALIZADO (acentos/espaços saneados; ver _normaliza), mesmo sob
subpastas internas do zip.

Integridade: o sha256 de cada arquivo extraído é conferido contra o pin
versionado em data/raw/pof/_meta.json (os mesmos hashes que identificam
os insumos lidos por aferir.inputs.pof). Release novo do IBGE ⇒ hash
diverge ⇒ o fetcher FALHA ruidosamente antes de gravar o destino —
re-pinar é decisão humana, nunca silenciosa.

Idempotência: com os 6 arquivos presentes o fetcher retorna SEM REDE
(o pipeline offline continua offline). Escrita atômica (tmp + os.replace);
_meta.json do domínio com url, sha256 e collected_at — datetime SÓ aqui
(fetcher), nunca no cálculo downstream.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from aferir import config
from aferir.provenance import sha256_file

POF_MICRODADOS_URL = (
    "https://ftp.ibge.gov.br/Orcamentos_Familiares/"
    "Pesquisa_de_Orcamentos_Familiares_2017_2018/Microdados/")

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}
TIMEOUT_S = 600                 # zips de ~200-300 MB no FTP do IBGE
_CHUNK = 1 << 20                # 1 MiB por leitura (download e extração)

# membros do zip de DADOS (basename) -> destino em <raiz>/dados_raw/
ARQUIVOS_DADOS = (
    "ALUGUEL_ESTIMADO.txt",
    "CADERNETA_COLETIVA.txt",
    "DESPESA_COLETIVA.txt",
    "DESPESA_INDIVIDUAL.txt",
    "MORADOR.txt",
)
# membro do zip de DOCUMENTAÇÃO (basename) -> destino em <raiz>/doc/
ARQUIVO_DICIONARIO = "Dicionarios_de_variaveis.xls"

# padrões dos zips no índice HTTP (a data de release AAAAMMDD está no nome;
# verificado em 2026-07: Dados_20230713.zip e Documentacao_20230713.zip)
_PADRAO_ZIP = {
    "dados": r'href="(Dados_[0-9]{8}\.zip)"',
    "documentacao": r'href="(Documentacao_[0-9]{8}\.zip)"',
}


def alvos(raiz: Path | None = None) -> dict[str, Path]:
    """Mapa basename -> caminho de destino sob `raiz` (default RAW_POF_DIR)."""
    raiz = raiz if raiz is not None else config.RAW_POF_DIR
    mapa = {nome: raiz / "dados_raw" / nome for nome in ARQUIVOS_DADOS}
    mapa[ARQUIVO_DICIONARIO] = raiz / "doc" / ARQUIVO_DICIONARIO
    return mapa


def _sha_esperados() -> dict[str, str]:
    """Pins sha256 dos 6 insumos, do _meta.json VERSIONADO do domínio.

    data/raw não é versionado, mas o _meta.json acompanha o repositório
    justamente para o replicador auditar a coleta byte a byte; sem ele a
    coleta não tem gabarito e o fetcher falha ruidosamente.
    """
    meta_path = config.RAW_POF_DIR / "_meta.json"
    if not meta_path.exists():
        raise RuntimeError(
            f"pin ausente: {meta_path} (versionado no repositório) é o "
            "gabarito sha256 da coleta POF — sem ele não há como conferir "
            "a integridade dos arquivos extraídos.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    esperados = {nome: info["sha256"]
                 for nome, info in meta.get("arquivos", {}).items()}
    faltam = set(alvos()) - set(esperados)
    if faltam:
        raise RuntimeError(f"{meta_path}: pins sha256 ausentes p/ {sorted(faltam)}")
    return esperados


def _zips_publicados() -> dict[str, str]:
    """Descobre no índice HTTP do FTP os nomes correntes dos zips.

    Se o IBGE publicar mais de um release simultâneo, toma o mais recente
    (nomes carregam AAAAMMDD ⇒ max lexicográfico); qualquer mudança de
    conteúdo é barrada adiante pelo gate de sha256.
    """
    r = requests.get(POF_MICRODADOS_URL, headers=_UA, timeout=TIMEOUT_S)
    r.raise_for_status()
    achados: dict[str, str] = {}
    for chave, padrao in _PADRAO_ZIP.items():
        nomes = sorted(set(re.findall(padrao, r.text)))
        if not nomes:
            raise RuntimeError(
                f"índice {POF_MICRODADOS_URL}: nenhum zip casa com {padrao!r} "
                "— layout do FTP do IBGE mudou?")
        achados[chave] = max(nomes)
    return achados


def _baixa_zip(nome: str, destino_dir: Path) -> Path:
    """Baixa <índice>/<nome> por streaming para o diretório temporário."""
    destino = destino_dir / nome
    with requests.get(POF_MICRODADOS_URL + nome, headers=_UA,
                      stream=True, timeout=TIMEOUT_S) as r:
        r.raise_for_status()
        with open(destino, "wb") as fh:
            for chunk in r.iter_content(_CHUNK):
                fh.write(chunk)
    return destino


def _normaliza(basename: str) -> str:
    """Basename canônico para casar membro do zip com o alvo local.

    Os nomes internos dos zips do IBGE vêm com acento/espaço em CP850, que o
    zipfile decodifica como CP437 (mojibake: 'ã' vira '╞'); o alvo local usa o
    nome saneado ('Dicionários de váriaveis.xls' → Dicionarios_de_variaveis.xls).
    Normalização: NFKD sem marcas combinantes, descarta não-ASCII residual,
    minúsculas, remove espaços e '_'. Ambiguidade é barrada pelo chamador.
    """
    s = unicodedata.normalize("NFKD", basename)
    s = "".join(c for c in s if c.isascii() and not unicodedata.combining(c))
    return s.casefold().replace(" ", "").replace("_", "")


def _membro_por_basename(zf: zipfile.ZipFile, procurados: set[str],
                         zip_nome: str) -> dict[str, str]:
    """Localiza cada arquivo procurado entre os membros do zip (subpastas
    incluídas), casando por basename NORMALIZADO (_normaliza). Falha se
    faltar ou se houver ambiguidade (dois membros casando o mesmo alvo)."""
    alvo_de = {_normaliza(nome): nome for nome in procurados}
    candidatos: dict[str, list[str]] = {}
    for membro in zf.namelist():
        chave = _normaliza(membro.rsplit("/", 1)[-1])
        if chave in alvo_de:
            candidatos.setdefault(alvo_de[chave], []).append(membro)
    faltam = procurados - set(candidatos)
    if faltam:
        raise RuntimeError(f"{zip_nome}: membros ausentes no zip: {sorted(faltam)}")
    duplicados = {b: m for b, m in candidatos.items() if len(m) > 1}
    if duplicados:
        raise RuntimeError(f"{zip_nome}: basenames ambíguos no zip: {duplicados}")
    return {b: m[0] for b, m in candidatos.items()}


def _extrai_conferido(zf: zipfile.ZipFile, membro: str, destino: Path,
                      sha_esperado: str, zip_nome: str) -> None:
    """Extrai `membro` para `destino` com escrita atômica e gate de sha256.

    O hash é conferido no .tmp ANTES do rename: divergência não deixa
    arquivo no destino (idempotência nunca aceita um bruto corrompido).
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    try:
        with zf.open(membro) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst, _CHUNK)
        sha = sha256_file(tmp)
        if sha != sha_esperado:
            raise RuntimeError(
                f"{zip_nome}/{membro}: sha256 divergente do pin em "
                f"data/raw/pof/_meta.json\n  esperado: {sha_esperado}\n"
                f"  obtido:   {sha}\n"
                "Release novo do IBGE? Re-pinar é decisão humana.")
        os.replace(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)


def _grava_meta(raiz: Path, zips: dict[str, str]) -> None:
    """_meta.json do domínio: url, sha256+bytes por arquivo, collected_at,
    e o release (nome+sha256) dos zips de origem descartados."""
    meta_path = raiz / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.setdefault("dominio", "pof")
    meta.setdefault("nota", (
        "microdados POF 2017-2018 extraídos dos zips oficiais do IBGE "
        "para data/raw/pof/ (aferir.fetch.pof); hashes abaixo identificam "
        "byte a byte os insumos lidos por aferir.inputs.pof"))
    meta["url"] = POF_MICRODADOS_URL
    # coleta parcial (só o zip com membros faltantes) não apaga o registro
    # do outro release: merge por nome de zip
    meta["zips"] = {**meta.get("zips", {}), **zips}
    meta["arquivos"] = {
        nome: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
        for nome, p in sorted(alvos(raiz).items())
    }
    meta["collected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fetch_pof(*, force: bool = False, raiz: Path | None = None) -> dict[str, Path]:
    """Garante os 6 insumos brutos da POF sob `raiz` (default RAW_POF_DIR).

    Idempotente: com todos presentes (e sem `force`), retorna SEM tocar a
    rede nem o _meta.json. Só baixa o(s) zip(s) de que faltarem membros.
    `raiz` alternativa serve à replicação/auditoria fora de data/raw/.
    """
    raiz = raiz if raiz is not None else config.RAW_POF_DIR
    destinos = alvos(raiz)
    if not force and all(p.exists() for p in destinos.values()):
        return destinos                      # caminho offline: zero rede

    esperados = _sha_esperados()
    releases = _zips_publicados()
    plano = (                                # (chave do zip, membros dele)
        ("dados", ARQUIVOS_DADOS),
        ("documentacao", (ARQUIVO_DICIONARIO,)),
    )
    zips_usados: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="aferir_pof_") as tmpdir:
        for chave, membros in plano:
            pendentes = {n for n in membros if force or not destinos[n].exists()}
            if not pendentes:
                continue                     # zip inteiro já satisfeito
            zip_nome = releases[chave]
            zip_path = _baixa_zip(zip_nome, Path(tmpdir))
            zips_usados[zip_nome] = sha256_file(zip_path)
            with zipfile.ZipFile(zip_path) as zf:
                membro_de = _membro_por_basename(zf, pendentes, zip_nome)
                for nome in sorted(pendentes):
                    _extrai_conferido(zf, membro_de[nome], destinos[nome],
                                      esperados[nome], zip_nome)
            zip_path.unlink()                # zip não é persistido
    _grava_meta(raiz, zips_usados)
    return destinos


if __name__ == "__main__":
    for nome, path in sorted(fetch_pof().items()):
        print(f"{nome}: {path}")
