"""Fetcher SICONFI — DCA MUNICIPAL integral da subamostra FIXADA (2019-2023).

Subamostra aleatória v1 de municípios (composição PINADA em
data/inputs/amostra_dca_municipal.csv: cod_ibge,uf,ano — 14.192 pares
ente×exercício, 2.843 municípios em 18 UFs). Ela alimenta dois consumidores:
  * aferir.distribuicao (_iss_amostra_por_uf): ISS líquido 2019-2023 do
    estimador de razão ancorado em 2024 (Anexo I-C, conta ISS, colunas
    'Receitas Brutas Realizadas' − 'Outras Deduções da Receita');
  * aferir.inputs.gov_aquisicoes (estratos_v1_2023/_inflator): per-capita de
    compras por estrato populacional (Anexo I-D, naturezas 3.3.90.30/36/39).

A composição é FIXADA para garantir replicabilidade: refazer o sorteio
mudaria o estimador. Por isso o fetcher NÃO amostra — apenas materializa a
composição pinada, um parquet por ente×exercício
(data/raw/siconfi_municipal_dca/dca_mun_{cod_ibge}_{ano}.parquet).

Esquema: a API /dca retorna 11 campos (exercicio, instituicao, cod_ibge, uf,
anexo, rotulo, coluna, cod_conta, conta, valor, populacao) — confirmado na
prática em 2026-07-11 (refetch real de 3166600/2023 e 3304557/2023 idêntico
ao cache nos campos consumidos: linhas dos Anexos I-C/I-D ao centavo e mesma
populacao). Os seeds v1 carregam 4 colunas extras de proveniência
(_source/_dataset/_table_id/_collected_at_utc) que nenhum consumidor lê;
o refetch grava as 11 colunas canônicas da API.

ROTAS de materialização, na ordem:
 0. AFERIR_SUBAMOSTRA_TAR: caminho local de um tar já obtido (auditoria).
 1. PARTES VERSIONADAS (canônica, OFFLINE): o snapshot integral vem
    fatiado dentro do próprio repositório em
    data/raw/siconfi_municipal_dca/snapshot/*.parte-* (SHA256SUMS ao lado);
    o fetcher concatena, verifica o sha256 pinado e extrai — replicação da
    subamostra sem nenhum acesso à rede.
 2. RELEASE do espelho: mesmo tar como asset de release (URL derivada do
    remote origin em runtime), fallback para cópias sem as partes.
 3. API pública (re-derivação): mesma rota da coleta original, par a par.
    Motivo MEDIDO para o snapshot: a API /dca é uma base VIVA — o par
    4219150 (SC) 2019, coletado com 851 linhas em 2026-05, passou a
    retornar VAZIO em 2026-07-12, e 12 de 13.377 pares reconferidos
    voltaram RETIFICADOS. O snapshot congela a vintage usada pelo artigo;
    pares retificados na API falham ruidosamente apontando o snapshot.

Operação (DESIGN §3-4): idempotente (arquivo existente NÃO é refeito — o
pipeline offline continua offline); escrita atômica; retomável (um parquet
por par: reexecutar continua de onde parou); ao final, GUARDA de integridade:
o conjunto de arquivos do diretório deve ser EXATAMENTE a composição pinada
(falha ruidosa se faltar ou sobrar). _meta.json com url, sha256 e
collected_at — datetime SÓ aqui, nunca no cálculo.

Execução: PYTHONPATH=src python3 -m aferir.fetch.siconfi_municipal_dca
"""
from __future__ import annotations

import os
import tarfile
import tempfile
import time
from pathlib import Path

import pandas as pd
import requests

from aferir.config import (
    AMOSTRA_DCA_MUN_CSV,
    RAW_DCA_MUN_DIR,
    SICONFI_API,
)
from aferir.fetch.siconfi_comum import (
    atualiza_meta,
    get_items_paginado,
    grava_parquet_atomico,
)
from aferir.fetch.siconfi_estadual import COD_IBGE_UF
from aferir.provenance import caminho_repo, sha256_file

# UF esperada pelo prefixo (2 dígitos) do código IBGE — validação da composição.
_UF_POR_PREFIXO = {cod: uf for uf, cod in COD_IBGE_UF.items()}

# Colunas canônicas do parquet (ordem e nomes da API /dca; os consumidores
# leem subconjuntos: uf/cod_ibge/cod_conta/coluna/valor e
# anexo/cod_conta/coluna/valor/cod_ibge/populacao).
COLUNAS_DCA = [
    "exercicio", "instituicao", "cod_ibge", "uf", "anexo", "rotulo",
    "coluna", "cod_conta", "conta", "valor", "populacao",
]

PROGRESSO_A_CADA = 100

# Snapshot pinado da subamostra. Rota canônica = partes versionadas no
# repositório (SNAPSHOT_DIR); fallback = asset de release do espelho, com a
# URL derivada do remote `origin` em tempo de execução (nenhuma
# conta/hospedagem fica gravada no código). Sobreponível por
# AFERIR_SUBAMOSTRA_TAR (tar local) ou AFERIR_SUBAMOSTRA_URL (URL
# alternativa). O sha256 pinado é verificado em QUALQUER rota antes de
# extrair.
SNAPSHOT_DIR = RAW_DCA_MUN_DIR / "snapshot"
ARQUIVO_RELEASE_TAG = "v1.0.0"
ARQUIVO_RELEASE_NOME = "subamostra_dca_municipal_2019-2023.tar.gz"
ARQUIVO_RELEASE_SHA256 = (
    "95c4da89bf531040bd985d08439c49df6ca7af0c9a15c0cab4157574663f57fe"
)
ARQUIVO_TIMEOUT_S = 900


def _url_release() -> str:
    """URL do asset de release, derivada do remote `origin` deste clone."""
    alt = os.environ.get("AFERIR_SUBAMOSTRA_URL")
    if alt:
        return alt
    import re
    import subprocess

    from aferir.config import V2_ROOT
    r = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True, text=True, cwd=V2_ROOT,
    )
    origem = r.stdout.strip()
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", origem)
    if not m:
        raise RuntimeError(
            "remote origin não aponta para um espelho no GitHub; defina "
            "AFERIR_SUBAMOSTRA_URL ou AFERIR_SUBAMOSTRA_TAR"
        )
    return (f"https://github.com/{m.group(1)}/{m.group(2)}/releases/"
            f"download/{ARQUIVO_RELEASE_TAG}/{ARQUIVO_RELEASE_NOME}")


def _materializa_do_arquivo(faltantes: set[str]) -> int:
    """Extrai da rota arquivística os parquets AUSENTES; retorna o nº extraído.

    O tar (release do espelho, ou caminho local em AFERIR_SUBAMOSTRA_TAR) tem
    o sha256 pinado verificado ANTES de qualquer extração; membros fora do
    padrão dca_mun_*.parquet são ignorados (defesa contra path traversal).
    Evidência que motivou a rota (2026-07-12): a API viva devolveu vazio para
    1 par pinado e valores retificados para 12 de 13.377 pares reconferidos.
    """
    local = os.environ.get("AFERIR_SUBAMOSTRA_TAR")
    partes = sorted(SNAPSHOT_DIR.glob(f"{ARQUIVO_RELEASE_NOME}.parte-*"))
    tmp_baixado: Path | None = None
    try:
        if local:
            tar_path = Path(local)
            print("[dca mun] snapshot: tar local (AFERIR_SUBAMOSTRA_TAR)",
                  flush=True)
        elif partes:
            # Rota canônica: partes versionadas no repo — nenhuma rede.
            fd, tmp = tempfile.mkstemp(suffix=".tar.gz")
            os.close(fd)
            tmp_baixado = Path(tmp)
            with open(tmp_baixado, "wb") as fh:
                for p in partes:
                    fh.write(p.read_bytes())
            tar_path = tmp_baixado
            print(f"[dca mun] snapshot: {len(partes)} partes locais "
                  "remontadas (offline)", flush=True)
        else:
            fd, tmp = tempfile.mkstemp(suffix=".tar.gz")
            os.close(fd)
            tmp_baixado = Path(tmp)
            with requests.get(_url_release(), stream=True,
                              timeout=ARQUIVO_TIMEOUT_S) as r:
                r.raise_for_status()
                with open(tmp_baixado, "wb") as fh:
                    for pedaco in r.iter_content(1 << 20):
                        fh.write(pedaco)
            tar_path = tmp_baixado
            print("[dca mun] snapshot: baixado do release do espelho",
                  flush=True)
        digest = sha256_file(tar_path)
        if digest != ARQUIVO_RELEASE_SHA256:
            raise RuntimeError(
                f"snapshot da subamostra: sha256 {digest[:16]}… diverge do pinado"
            )
        n = 0
        RAW_DCA_MUN_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tar_path, "r:gz") as tar:
            for m in tar:
                nome = Path(m.name).name
                if not (m.isfile() and nome.startswith("dca_mun_")
                        and nome.endswith(".parquet")):
                    continue
                if nome not in faltantes:
                    continue
                fobj = tar.extractfile(m)
                destino = RAW_DCA_MUN_DIR / nome
                tmp2 = destino.with_name(nome + ".tmp")
                with open(tmp2, "wb") as out:
                    out.write(fobj.read())
                os.replace(tmp2, destino)
                n += 1
        return n
    finally:
        if tmp_baixado is not None:
            tmp_baixado.unlink(missing_ok=True)


# ---------------------------------------------------------------- composição
def composicao_pinada() -> pd.DataFrame:
    """Composição fixada da subamostra (cod_ibge, uf, ano), validada.

    Guardas: colunas exatas, sem pares (cod_ibge, ano) duplicados e UF
    coerente com o prefixo IBGE de 2 dígitos do código do município.
    """
    comp = pd.read_csv(AMOSTRA_DCA_MUN_CSV)
    if list(comp.columns) != ["cod_ibge", "uf", "ano"]:
        raise ValueError(
            f"{AMOSTRA_DCA_MUN_CSV.name}: colunas inesperadas {list(comp.columns)}"
        )
    comp = comp.astype({"cod_ibge": "int64", "ano": "int64"})
    dup = comp.duplicated(["cod_ibge", "ano"])
    if dup.any():
        raise ValueError(
            f"{AMOSTRA_DCA_MUN_CSV.name}: {int(dup.sum())} pares duplicados"
        )
    uf_esperada = (comp["cod_ibge"] // 100_000).map(_UF_POR_PREFIXO)
    ruins = comp[comp["uf"] != uf_esperada]
    if not ruins.empty:
        raise ValueError(
            f"{AMOSTRA_DCA_MUN_CSV.name}: UF incoerente com o codigo IBGE em "
            f"{len(ruins)} linhas (ex.: {ruins.head(3).to_dict('records')})"
        )
    return comp.sort_values(["cod_ibge", "ano"]).reset_index(drop=True)


def caminho_dca_mun(cod_ibge: int, ano: int) -> Path:
    return RAW_DCA_MUN_DIR / f"dca_mun_{cod_ibge}_{ano}.parquet"


# ---------------------------------------------------------------- refetch
def fetch_dca_mun(cod_ibge: int, uf: str, ano: int) -> Path:
    """DCA integral (todos os anexos) de um ente×exercício, idempotente.

    Se o parquet já existe em data/raw, retorna sem rede. A composição
    pinada só contém entes que ENTREGARAM a DCA do exercício: API vazia ou
    identificação divergente é falha ruidosa (nunca arquivo silencioso).
    """
    path = caminho_dca_mun(cod_ibge, ano)
    if path.exists():
        return path
    items, _ = get_items_paginado(
        "dca", {"an_exercicio": ano, "id_ente": cod_ibge}
    )
    if not items:
        raise ValueError(
            f"DCA municipal {cod_ibge} ({uf}) {ano}: API vazia — par pinado "
            "retificado/retirado na origem desde a coleta (base viva). Use a "
            "rota arquivística (snapshot pinado no release do espelho)"
        )
    df = pd.DataFrame(items)
    faltam = set(COLUNAS_DCA) - set(df.columns)
    if faltam:
        raise ValueError(
            f"DCA municipal {cod_ibge} {ano}: API sem campos {sorted(faltam)}"
        )
    df = (
        df[COLUNAS_DCA]
        .astype({"exercicio": "int64", "cod_ibge": "int64",
                 "populacao": "int64", "valor": "float64"})
        .sort_values(["anexo", "cod_conta", "coluna"])
        .reset_index(drop=True)
    )
    ids = df[["exercicio", "cod_ibge", "uf"]].drop_duplicates()
    if len(ids) != 1 or ids.iloc[0].tolist() != [ano, cod_ibge, uf]:
        raise ValueError(
            f"DCA municipal {cod_ibge} ({uf}) {ano}: identificacao divergente "
            f"na resposta da API: {ids.to_dict('records')}"
        )
    RAW_DCA_MUN_DIR.mkdir(parents=True, exist_ok=True)
    grava_parquet_atomico(df, path)
    return path


# ---------------------------------------------------------------- guarda
def verifica_composicao_exata(comp: pd.DataFrame | None = None) -> int:
    """O diretório deve conter EXATAMENTE os parquets da composição pinada.

    Falha ruidosa se faltar (coleta incompleta) ou sobrar (arquivo fora da
    composição contaminaria os globs dca_mun_* dos consumidores). Retorna o
    número de arquivos conferidos.
    """
    comp = composicao_pinada() if comp is None else comp
    esperados = {
        f"dca_mun_{int(r.cod_ibge)}_{int(r.ano)}.parquet"
        for r in comp.itertuples(index=False)
    }
    presentes = {p.name for p in RAW_DCA_MUN_DIR.glob("dca_mun_*.parquet")}
    faltam = sorted(esperados - presentes)
    sobram = sorted(presentes - esperados)
    if faltam or sobram:
        raise RuntimeError(
            f"subamostra municipal != composicao pinada "
            f"({AMOSTRA_DCA_MUN_CSV.name}): faltam {len(faltam)} "
            f"(ex.: {faltam[:5]}), sobram {len(sobram)} (ex.: {sobram[:5]})"
        )
    return len(esperados)


# ---------------------------------------------------------------- main
def main() -> None:
    comp = composicao_pinada()
    pendentes = [
        r for r in comp.itertuples(index=False)
        if not caminho_dca_mun(int(r.cod_ibge), int(r.ano)).exists()
    ]
    print(
        f"[dca mun] composicao pinada={len(comp)} pares | "
        f"presentes={len(comp) - len(pendentes)} | pendentes={len(pendentes)}",
        flush=True,
    )

    # Rota 1 (canônica): snapshot arquivístico pinado. Se indisponível
    # (offline, release inacessível), cai para a re-derivação pela API.
    if pendentes:
        faltantes = {
            f"dca_mun_{int(r.cod_ibge)}_{int(r.ano)}.parquet" for r in pendentes
        }
        try:
            n_arq = _materializa_do_arquivo(faltantes)
            print(f"[dca mun] rota arquivistica: {n_arq} parquets extraidos "
                  "do snapshot pinado", flush=True)
        except Exception as exc:
            print(f"[dca mun] rota arquivistica indisponivel ({exc}); "
                  "re-derivando da API publica", flush=True)
        pendentes = [
            r for r in comp.itertuples(index=False)
            if not caminho_dca_mun(int(r.cod_ibge), int(r.ano)).exists()
        ]

    t0 = time.monotonic()
    for i, r in enumerate(pendentes, start=1):
        fetch_dca_mun(int(r.cod_ibge), str(r.uf), int(r.ano))
        if i % PROGRESSO_A_CADA == 0:
            taxa = i / (time.monotonic() - t0)
            print(f"[dca mun] {i}/{len(pendentes)} ({taxa:.2f} pares/s)",
                  flush=True)

    if pendentes:  # datetime/sha256 só quando houve coleta (offline fica offline)
        atualiza_meta(
            RAW_DCA_MUN_DIR,
            endpoint_dca=f"{SICONFI_API}/dca?an_exercicio={{ano}}&id_ente={{cod_ibge}}",
            composicao={
                "path": caminho_repo(AMOSTRA_DCA_MUN_CSV),
                "sha256": sha256_file(AMOSTRA_DCA_MUN_CSV),
            },
            metodo=(
                "subamostra aleatoria FIXADA (2019-2023); o fetcher nao "
                "amostra — materializa a composicao pinada, DCA integral por "
                "ente x exercicio; rota canonica = snapshot arquivistico "
                "(release do espelho, sha256 pinado); API = re-derivacao"
            ),
            snapshot={
                "asset": ARQUIVO_RELEASE_NOME,
                "tag": ARQUIVO_RELEASE_TAG,
                "sha256": ARQUIVO_RELEASE_SHA256,
            },
            n_coletados_nesta_execucao=len(pendentes),
        )

    n = verifica_composicao_exata(comp)
    print(f"[dca mun] guarda OK: {n} parquets == composicao pinada "
          f"({len(pendentes)} coletados nesta execucao)", flush=True)


if __name__ == "__main__":
    main()
