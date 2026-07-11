"""PIB nominal anual (IBGE) — fetcher SIDRA 1846 + agregação determinística.

PIB a preços de mercado, valores correntes (R$ milhões), trimestral (SCN
Trimestral, tabela 1846, v/585, c11255/90707, nível Brasil). PIB anual =
soma dos 4 trimestres. Justificativa da rota (herdada do v1, validada):
as Contas Nacionais anuais/regionais param antes de 2024-2025; o SCN
Trimestral é a única fonte aberta tempestiva, e a soma dos trimestres
reproduz o PIB anual publicado (2021 = 9.012.142 R$ mi; 2022-2023 conferem
com SIDRA 5938 Σ UFs a menos de 0,01 R$ bi).

Idempotência: cache em data/raw/sidra/ com _meta.json (url, sha256,
collected_at). datetime SÓ no fetcher.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aferir import config
from aferir.fetch.rfb_federal import _download

RAW_SIDRA = config.RAW / "sidra"
_ARQ = "pib_1846_n1_v585_c90707.json"
_ARQ_CFAM = "cfam_1846_n1_v585_c93404.json"
_ARQ_FBCF = "fbcf_1846_n1_v585_c93406.json"

# Despesa de consumo das famílias, valores correntes (mesma tabela 1846;
# categoria c11255/93404) — numerador/denominador da escala TRU→biênio
# das âncoras de CONSUMO (C_fam e, por proxy declarado, ISFLSF).
SIDRA_CFAM_1846_URL = ("https://apisidra.ibge.gov.br/values/t/1846/n1/all/"
                       "v/585/p/all/c11255/93404?formato=json")

# Formação bruta de capital fixo, valores correntes (mesma tabela 1846;
# categoria c11255/93406) — escala PRÓPRIA da âncora FBCF (parecer da banca:
# a escala C_fam sobreestimava B_FBCF_NC; a FBCF nominal cresceu menos).
SIDRA_FBCF_1846_URL = ("https://apisidra.ibge.gov.br/values/t/1846/n1/all/"
                       "v/585/p/all/c11255/93406?formato=json")

_N_TRIMESTRES = 4


def fetch_sidra_pib(*, force: bool = False) -> Path:
    """Baixa (idempotente) a série trimestral do PIB pm corrente (SIDRA 1846)."""
    return _download(config.SIDRA_PIB_1846_URL, RAW_SIDRA / _ARQ, force=force)


def _serie_anual_1846(url: str, arquivo: str) -> pd.Series:
    """Série anual (R$ mi correntes) = soma dos 4 trimestres da SIDRA 1846.

    Retorna Series ano→valor (só anos com 4 trimestres completos).
    """
    path = _download(url, RAW_SIDRA / arquivo)
    bruto = json.loads(path.read_text(encoding="utf-8"))
    linhas = []
    for row in bruto[1:]:
        v = row.get("V")
        if v in (None, "", "..", "...", "-"):
            continue
        linhas.append({"ano": int(str(row["D3N"]).split()[-1]), "v": float(v)})
    df = pd.DataFrame(linhas)
    por_ano = df.groupby("ano").agg(total=("v", "sum"), n=("v", "size"))
    completos = por_ano[por_ano["n"] == _N_TRIMESTRES]
    return completos["total"]


def consumo_familias_nominal() -> pd.Series:
    """Consumo das famílias nominal anual (R$ mi) — SIDRA 1846, c11255/93404."""
    return _serie_anual_1846(SIDRA_CFAM_1846_URL, _ARQ_CFAM)


def fbcf_nominal() -> pd.Series:
    """FBCF nominal anual (R$ mi) — SIDRA 1846, c11255/93406."""
    return _serie_anual_1846(SIDRA_FBCF_1846_URL, _ARQ_FBCF)


def pib_nominal_anual(anos: list[int]) -> pd.DataFrame:
    """PIB nominal anual (R$ mi correntes) = soma dos 4 trimestres SIDRA 1846."""
    path = fetch_sidra_pib()
    bruto = json.loads(path.read_text(encoding="utf-8"))
    # primeira linha do payload apisidra = cabeçalho de rótulos
    linhas = []
    for row in bruto[1:]:
        v = row.get("V")
        if v in (None, "", "..", "...", "-"):
            continue
        # D3N = "1º trimestre 2021" — o ano é o último token
        linhas.append({"ano": int(str(row["D3N"]).split()[-1]), "v": float(v)})
    df = pd.DataFrame(linhas)
    por_ano = df.groupby("ano").agg(pib_rs_mi=("v", "sum"), n=("v", "size"))
    incompletos = {int(a): int(n) for a, n in por_ano["n"].items()
                   if a in anos and n != _N_TRIMESTRES}
    if incompletos:
        raise ValueError(f"SIDRA 1846: anos sem 4 trimestres: {incompletos}")
    faltantes = set(anos) - set(por_ano.index)
    if faltantes:
        raise ValueError(f"SIDRA 1846: anos ausentes: {sorted(faltantes)}")
    out = por_ano.loc[sorted(anos), ["pib_rs_mi"]].reset_index()
    out["ano"] = out["ano"].astype(int)
    return out


# ------------------------------------------------------- série decenal (E4)
# PIB pm (c11255/90707) e Despesa de consumo das famílias (c11255/93404),
# valores correntes (v/585, R$ mi), trimestral, num ÚNICO payload — insumo do
# teste de estacionariedade base/PIB (E4). Janela PINADA 201501-202504
# (11 anos × 4 trimestres × 2 categorias = 88 linhas): a tabela 1846 é viva,
# e uma janela aberta mudaria os bytes a cada re-execução; trimestres já
# publicados podem ser REVISADOS pelo SCN Trimestral, então a idempotência é
# seed-first (vintage congelada pela existência do arquivo; sha no sidecar).
SIDRA_CNT_1846_DECADA_URL = (
    "https://apisidra.ibge.gov.br/values/t/1846/n1/all/v/585/"
    "p/201501-202504/c11255/90707,93404?formato=json")
_ARQ_CNT_DECADA = "cnt_1846_decada.json"
_CATS_DECADA = {"90707", "93404"}          # códigos D4C esperados no payload
_N_TRIMESTRES_DECADA = 44                  # 2015T1-2025T4


def serie_decenal_1846(*, force: bool = False) -> Path:
    """Baixa (seed-first) PIB + consumo das famílias trimestrais 2015T1-2025T4.

    Grava data/raw/sidra/cnt_1846_decada.json (arquivo NOVO — não toca os
    JSONs 1846 existentes) + sidecar _meta.json. Escrita atômica.
    """
    import os
    from datetime import datetime, timezone

    import requests

    from aferir.provenance import sha256_file

    destino = RAW_SIDRA / _ARQ_CNT_DECADA
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta_path = destino.with_name(destino.name + "._meta.json")

    def _valida(linhas: list[dict]) -> None:
        esperado = _N_TRIMESTRES_DECADA * len(_CATS_DECADA)
        if len(linhas) != esperado:
            raise ValueError(f"SIDRA 1846 década: esperadas {esperado} "
                             f"linhas, vieram {len(linhas)}")
        if {r.get("D4C") for r in linhas} != _CATS_DECADA:
            raise ValueError("SIDRA 1846 década: categorias c11255 inesperadas")
        por_cat: dict[str, int] = {}
        for r in linhas:
            float(r["V"])                  # todo valor deve ser numérico
            por_cat[r["D4C"]] = por_cat.get(r["D4C"], 0) + 1
        errados = {c: n for c, n in por_cat.items()
                   if n != _N_TRIMESTRES_DECADA}
        if errados:
            raise ValueError(f"SIDRA 1846 década: trimestres faltando: {errados}")

    def _grava_meta(status_http: int | None, origem: str) -> None:
        meta = {
            "url": SIDRA_CNT_1846_DECADA_URL,
            "parametros": {"tabela": 1846, "variavel": 585,
                           "periodos": "201501-202504",
                           "c11255": sorted(_CATS_DECADA), "nivel": "n1"},
            "sha256": sha256_file(destino),
            "bytes": destino.stat().st_size,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "status_http": status_http,
            "origem": origem,
            "nota_fonte_viva": ("o SCN Trimestral revisa trimestres já "
                                "publicados; vintage congelada pela "
                                "existência do arquivo"),
        }
        tmp = meta_path.with_name(meta_path.name + ".tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                                  sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, meta_path)

    if destino.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(destino):
                return destino
        _valida(json.loads(destino.read_text(encoding="utf-8"))[1:])
        _grava_meta(None, "cache_local")
        return destino

    resp = requests.get(SIDRA_CNT_1846_DECADA_URL,
                        headers={"User-Agent": "Mozilla/5.0 (aferir; rotina "
                                 "publica de dados abertos)"}, timeout=180)
    resp.raise_for_status()
    # 1ª linha do payload apisidra = cabeçalho-descritor; dados = [1:].
    _valida(resp.json()[1:])
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(resp.content)
    os.replace(tmp, destino)
    _grava_meta(resp.status_code, "download")
    return destino


# ------------------------------------------------------------------ malha UF
# Malha territorial estadual (API de Malhas v3 do IBGE, GeoJSON, qualidade
# intermediária) — insumo do mapa coroplético dos vetores por UF. Fonte
# pública, sem credencial; cache idempotente em data/raw/ibge_malhas/.
MALHA_UF_URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
                "?intrarregiao=UF&qualidade=intermediaria"
                "&formato=application/vnd.geo+json")
_ARQ_MALHA = "malha_br_uf_intermediaria.geojson"

# Código IBGE da UF -> sigla (DTB/IBGE — tabela oficial de códigos)
COD_UF_SIGLA = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA",
                "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE",
                "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE",
                "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
                "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT",
                "52": "GO", "53": "DF"}


def malha_uf() -> dict:
    """GeoJSON da malha estadual (27 feições, propriedade `codarea`)."""
    path = _download(MALHA_UF_URL, config.RAW / "ibge_malhas" / _ARQ_MALHA)
    g = json.loads(path.read_text(encoding="utf-8"))
    feats = g.get("features", [])
    if len(feats) != 27:
        raise ValueError(f"malha UF: esperadas 27 feições, vieram {len(feats)}")
    codigos = {f["properties"]["codarea"] for f in feats}
    if codigos != set(COD_UF_SIGLA):
        raise ValueError("malha UF: códigos IBGE não batem com a DTB")
    return g


if __name__ == "__main__":
    print("PIB anual (SIDRA 1846):", fetch_sidra_pib())
    print("malha UF (IBGE Malhas v3):", config.RAW / "ibge_malhas" / _ARQ_MALHA)
    malha_uf()
