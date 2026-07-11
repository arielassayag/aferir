"""POF 2017-2018 (IBGE) — leitura reconstruída dos microdados fixed-width.

Reconstrução v2 (sem copiar código do v1), validada contra números publicados
pelo IBGE:
 - aluguel estimado médio mensal por família = R$ 606,15 (SIDRA t/6970);
 - total de famílias (Σ PESO_FINAL por UC única) = 69.017.704.

Fonte primária (dados abertos): IBGE, POF 2017-2018, microdados públicos em
https://ftp.ibge.gov.br/Orcamentos_Familiares/Pesquisa_de_Orcamentos_Familiares_2017_2018/Microdados/
(arquivos .txt fixed-width + "Dicionarios_de_variaveis.xls"). O cache local é
data/raw/pof/ (populado por `make fetch` — aferir.fetch.pof), com sha256 de
cada insumo registrado em data/raw/pof/_meta.json.

Convenção de anualização (IBGE, "Memória de Cálculo", FTP oficial; confirmada
no Dicionário de Variáveis):

    despesa_anual = V8000_DEFLA × V9011 × FATOR_ANUALIZACAO × PESO_FINAL

nos quadros em que V9011 (nº de meses, 0-12) é aplicável — Aluguel Estimado
(quadro 00, FATOR≡1), Despesa Coletiva quadros 10 e 19, Despesa Individual
quadros 44, 47, 48, 49 e 50 —; nos demais quadros V9011 não existe e o FATOR
anualiza sozinho (52 na caderneta; 12/4 nos quadros mensais/trimestrais).
V9011=0 (UC com menos de 1 mês) zera o registro (regra literal do dicionário).
O valor MENSAL usado nas validações é o anual dividido por 12.

Saídas em config.PROCESSED:
 - pof_despesa_item_uf.parquet  [codigo_pof, uf, despesa_anual_rs, formula, fonte]
 - pof_familias_uf.csv          [uf, familias, formula, fonte]
 - pof_decis_uf.parquet         [uf, decil_renda, despesa, formula, fonte]

Decis de renda: decis POPULACIONAIS nacionais de renda per capita
(peso = PESO_FINAL × nº de moradores da UC; MORADOR.txt), escala-invariantes.
A despesa dos decis EXCLUI o aluguel imputado (código 101) — fora do campo de
incidência (LC 214, art. 4º: sem operação onerosa), mesma convenção do f_low
do cashback (LC 214, arts. 112-118; proxy CadÚnico = decis 1-3).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from aferir.config import INPUTS, PROCESSED, RAW_POF_DIR
from aferir.provenance import MANIFEST, Label, Num, sha256_file

# ------------------------------------------------------------------ fontes
POF_URL = (
    "https://ftp.ibge.gov.br/Orcamentos_Familiares/"
    "Pesquisa_de_Orcamentos_Familiares_2017_2018/Microdados/"
)
POF_DADOS = RAW_POF_DIR / "dados_raw"
DICIONARIO = RAW_POF_DIR / "doc" / "Dicionarios_de_variaveis.xls"
META_RAW = RAW_POF_DIR / "_meta.json"

# arquivo .txt -> aba do Dicionário de Variáveis
ARQUIVOS = {
    "despesa_coletiva": ("DESPESA_COLETIVA.txt", "Despesa Coletiva"),
    "despesa_individual": ("DESPESA_INDIVIDUAL.txt", "Despesa Individual"),
    "caderneta_coletiva": ("CADERNETA_COLETIVA.txt", "Caderneta Coletiva"),
    "aluguel_estimado": ("ALUGUEL_ESTIMADO.txt", "Aluguel Estimado"),
    "morador": ("MORADOR.txt", "Morador"),
}

# Quadros com V9011 aplicável (Dicionário de Variáveis + Memória de Cálculo IBGE)
QUADROS_V9011 = {
    "aluguel_estimado": frozenset({0}),
    "despesa_coletiva": frozenset({10, 19}),
    "despesa_individual": frozenset({44, 47, 48, 49, 50}),
    "caderneta_coletiva": frozenset(),
}

CODIGO_ALUGUEL_IMPUTADO = 101                # V9001 do Aluguel Estimado (quadro 00)
DECIS_CASHBACK = 3                           # proxy CadÚnico: decis 1-3 (art. 113)

# ------------------------------------------------ critério LEGAL do cashback (E6)
# LC 214/2025, arts. 112-113: elegível a família inscrita no CadÚnico com
# renda familiar mensal per capita de até MEIO salário mínimo. Na POF, o
# análogo de dados abertos é RENDA_TOTAL/n_pessoas ≤ ½ SM vigente na data de
# referência da pesquisa. Data de referência = 15/01/2018, confirmada no
# Dicionário de Variáveis (aba Morador, PESO_FINAL: "ajustado às estimativas
# populacionais para 15 janeiro de 2018"; V8000_DEFLA/RENDA_TOTAL
# deflacionados à mesma data). RENDA_TOTAL é o "rendimento bruto total
# MENSAL da Unidade de Consumo" (Dicionário, aba Morador) — mesma unidade
# mensal do SM, sem conversão.
SALARIO_MINIMO_2018 = 954.00        # R$/mês — Decreto nº 9.255/2017, art. 1º
                                    # (vigência 1º/01/2018; cobre 15/01/2018)
LIMIAR_LEGAL_RPC = SALARIO_MINIMO_2018 / 2.0   # R$ 477,00/mês per capita

# ESPELHO de pipeline.PADRAO_PISO (pipeline.py é do orquestrador — não
# importar; manter sincronizado): itens do piso do art. 118 DENTRO da base
# ad valorem (GLP monofásico fica fora — cashback do GLP ocorre no ad rem).
PADRAO_PISO_ESPELHO = (
    r"ENERGIA ELETRICA|TAXA DE AGUA E ESGOTO|AGUA E ESGOTO|GAS ENCANADO|"
    r"GAS NATURAL ENCANADO|TELEFONE|CELULAR|INTERNET|PACOTE DE TELEFONIA|TV POR ASSINATURA")

# Código IBGE (2 dígitos) -> sigla da UF
UF_IBGE = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

FONTE = (
    "IBGE POF 2017-2018, microdados fixed-width ({arq}); layout: "
    "Dicionarios_de_variaveis.xls; anualização V8000_DEFLA×V9011×FATOR "
    "(Memória de Cálculo IBGE); " + POF_URL
)


# ------------------------------------------------------------------ raw meta
def registra_cache_raw() -> dict:
    """Grava data/raw/pof/_meta.json com url + sha256 dos brutos (idempotente).

    Os .txt chegam via `make fetch` (aferir.fetch.pof); aqui apenas congelamos
    a proveniência. `collected_at` só é gerado na PRIMEIRA execução (datetime
    nunca entra no cálculo).
    """
    if META_RAW.exists():
        return json.loads(META_RAW.read_text(encoding="utf-8"))
    from datetime import datetime, timezone  # só no caminho de coleta

    arquivos = {}
    for nome, (txt, _) in sorted(ARQUIVOS.items()):
        p = POF_DADOS / txt
        arquivos[txt] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    arquivos[DICIONARIO.name] = {
        "sha256": sha256_file(DICIONARIO),
        "bytes": DICIONARIO.stat().st_size,
    }
    meta = {
        "dominio": "pof",
        "url": POF_URL,
        "nota": (
            "microdados POF 2017-2018 extraídos dos zips oficiais do IBGE "
            "para data/raw/pof/ (aferir.fetch.pof); hashes abaixo identificam "
            "byte a byte os insumos lidos por aferir.inputs.pof"
        ),
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arquivos": arquivos,
    }
    META_RAW.parent.mkdir(parents=True, exist_ok=True)
    META_RAW.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


# ------------------------------------------------------------------ layout
def layout(aba: str) -> pd.DataFrame:
    """Extrai o layout (posição inicial, tamanho, decimais, código) de uma aba
    do Dicionário de Variáveis. O cabeçalho é a linha cujo 1º campo contém
    'Posição'; abaixo dele, cada linha válida tem posição/tamanho/código."""
    bruto = pd.read_excel(DICIONARIO, sheet_name=aba, header=None)
    inicio = None
    for idx in bruto.index:
        if "Posição" in str(bruto.iat[idx, 0]):
            inicio = idx + 1
            break
    if inicio is None:
        raise ValueError(f"aba '{aba}' sem linha de cabeçalho 'Posição'")
    regs = []
    for idx in range(inicio, len(bruto)):
        pos, tam, dec, cod = (bruto.iat[idx, j] for j in range(4))
        if pd.isna(pos) or pd.isna(tam) or pd.isna(cod):
            continue
        try:
            regs.append(
                {
                    "codigo": str(cod).strip(),
                    "pos": int(pos),
                    "tamanho": int(tam),
                    "decimais": 0 if pd.isna(dec) else int(dec),
                }
            )
        except (TypeError, ValueError):
            continue  # linhas de seção/nota no meio da aba
    return pd.DataFrame(regs)


def le_fixed_width(txt: Path, lay: pd.DataFrame, campos: list[str]) -> pd.DataFrame:
    """Lê `campos` de um .txt fixed-width segundo o layout do dicionário.

    Regra de escala do IBGE: os campos com decimais IMPLÍCITOS seriam
    divididos por 10^decimais, mas nos .txt da POF 2017-2018 os campos
    decimais trazem o ponto EXPLÍCITO — nesse caso o valor já está em nível
    e NÃO se divide (validação de nível: Σ PESO_FINAL ≈ 69.017.704 famílias).
    """
    faltam = set(campos) - set(lay["codigo"])
    if faltam:
        raise ValueError(f"{txt.name}: campos ausentes no layout: {sorted(faltam)}")
    sel = lay.set_index("codigo").loc[campos].reset_index()
    colspecs = [(p - 1, p - 1 + t) for p, t in zip(sel["pos"], sel["tamanho"])]
    df = pd.read_fwf(txt, colspecs=colspecs, names=campos, dtype=str,
                     encoding="latin-1")
    for _, reg in sel.iterrows():
        c = reg["codigo"]
        valores = pd.to_numeric(df[c].str.strip(), errors="coerce")
        ponto_explicito = df[c].str.contains(".", regex=False).any()
        if reg["decimais"] > 0 and not ponto_explicito:
            valores = valores / 10.0 ** reg["decimais"]
        df[c] = valores
    return df


# ------------------------------------------------------------------ leitura
_CAMPOS_DESPESA = ["UF", "ESTRATO_POF", "COD_UPA", "NUM_DOM", "NUM_UC",
                   "QUADRO", "V9001", "V8000_DEFLA", "FATOR_ANUALIZACAO",
                   "PESO_FINAL"]


def le_despesas() -> pd.DataFrame:
    """Empilha os 4 arquivos de despesa em nível micro, com a anualização IBGE.

    Colunas: uf, estrato_pof, cod_upa, num_dom, num_uc, quadro, codigo_pof,
    origem, despesa_anual_rs (= V8000_DEFLA × V9011_eff × FATOR × PESO_FINAL).
    estrato_pof/cod_upa identificam o desenho amostral (estrato × UPA) — insumo
    do bootstrap de conglomerados (aferir.uncertainty).
    """
    partes = []
    for origem in ("despesa_coletiva", "despesa_individual",
                   "caderneta_coletiva", "aluguel_estimado"):
        txt, aba = ARQUIVOS[origem]
        lay = layout(aba)
        tem_v9011 = bool(QUADROS_V9011[origem])
        campos = _CAMPOS_DESPESA + (["V9011"] if tem_v9011 else [])
        df = le_fixed_width(POF_DADOS / txt, lay, campos)
        df["origem"] = origem

        # V9011_eff: nº de meses nos quadros aplicáveis; 1 nos demais.
        if tem_v9011:
            aplicavel = df["QUADRO"].isin(QUADROS_V9011[origem])
            # gate: o dicionário diz que V9011 existe EXATAMENTE nesses quadros
            if df.loc[aplicavel, "V9011"].isna().any():
                raise AssertionError(
                    f"{txt}: V9011 nulo em quadro aplicável {sorted(QUADROS_V9011[origem])}"
                )
            if df.loc[~aplicavel, "V9011"].notna().any():
                raise AssertionError(f"{txt}: V9011 preenchido fora dos quadros aplicáveis")
            df["v9011_eff"] = df["V9011"].where(aplicavel, 1.0)
        else:
            df["v9011_eff"] = 1.0
        partes.append(df.drop(columns=["V9011"], errors="ignore"))

    micro = pd.concat(partes, ignore_index=True)
    micro["uf"] = micro["UF"].map(UF_IBGE)
    micro = micro.dropna(subset=["uf", "V8000_DEFLA", "PESO_FINAL"])
    micro["despesa_anual_rs"] = (
        micro["V8000_DEFLA"] * micro["v9011_eff"]
        * micro["FATOR_ANUALIZACAO"] * micro["PESO_FINAL"]
    )
    micro = micro.rename(columns={
        "ESTRATO_POF": "estrato_pof", "COD_UPA": "cod_upa",
        "NUM_DOM": "num_dom", "NUM_UC": "num_uc",
        "QUADRO": "quadro", "V9001": "codigo_pof",
    })
    micro["codigo_pof"] = micro["codigo_pof"].astype("int64")
    return micro[["uf", "estrato_pof", "cod_upa", "num_dom", "num_uc", "quadro",
                  "codigo_pof", "origem", "despesa_anual_rs"]]


def le_moradores() -> pd.DataFrame:
    """MORADOR.txt em nível de UC: uf, estrato, chave da UC, nº de moradores,
    PESO_FINAL e RENDA_TOTAL (constantes dentro da UC)."""
    txt, aba = ARQUIVOS["morador"]
    lay = layout(aba)
    mor = le_fixed_width(POF_DADOS / txt, lay,
                         ["UF", "ESTRATO_POF", "COD_UPA", "NUM_DOM", "NUM_UC",
                          "PESO_FINAL", "RENDA_TOTAL"])
    mor["uf"] = mor["UF"].map(UF_IBGE)
    uc = (
        mor.groupby(["uf", "COD_UPA", "NUM_DOM", "NUM_UC"], as_index=False)
        .agg(estrato_pof=("ESTRATO_POF", "first"),
             n_pessoas=("PESO_FINAL", "size"),
             peso_final=("PESO_FINAL", "first"),
             renda_total=("RENDA_TOTAL", "first"))
        .rename(columns={"COD_UPA": "cod_upa", "NUM_DOM": "num_dom",
                         "NUM_UC": "num_uc"})
    )
    return uc


# ------------------------------------------------------------------ decis
def decis_renda(uc: pd.DataFrame) -> pd.DataFrame:
    """Decis populacionais NACIONAIS de renda per capita (escala-invariantes).

    Peso populacional = PESO_FINAL × nº de moradores; ordenação por renda per
    capita com desempate determinístico pela chave da UC.
    """
    d = uc.copy()
    d["rpc"] = d["renda_total"] / d["n_pessoas"].clip(lower=1)
    d["pop_w"] = d["peso_final"] * d["n_pessoas"]
    d = d.sort_values(["rpc", "cod_upa", "num_dom", "num_uc"],
                      kind="mergesort").reset_index(drop=True)
    acum = d["pop_w"].cumsum() / d["pop_w"].sum()
    d["decil_renda"] = np.clip(np.ceil(acum * 10), 1, 10).astype(int)
    return d


# ------------------------------------------------------- critério legal (E6)
def classifica_elegivel_legal(uc: pd.DataFrame) -> pd.DataFrame:
    """Elegibilidade LEGAL do cashback por UC: rpc ≤ ½ SM de 15/01/2018.

    uc: saída de le_moradores(). Retorna cópia com rpc (R$/mês per capita),
    pop_w (peso populacional) e elegivel_legal (bool, limiar INCLUSIVO —
    'de até meio salário mínimo', LC 214, art. 113).
    """
    d = uc.copy()
    d["rpc"] = d["renda_total"] / d["n_pessoas"].clip(lower=1)
    d["pop_w"] = d["peso_final"] * d["n_pessoas"]
    d["elegivel_legal"] = d["rpc"] <= LIMIAR_LEGAL_RPC
    return d


def _codigos_piso_espelho() -> set[str]:
    """Códigos POF do piso do art. 118 (espelho de pipeline._codigos_piso)."""
    m = pd.read_csv(INPUTS / "matriz_pof_ibs_v5.csv", dtype={"codigo_pof": str})
    desc = m["descricao_pof"].fillna("").str.upper()
    return set(m.loc[desc.str.contains(PADRAO_PISO_ESPELHO, regex=True),
                     "codigo_pof"])


def constroi_elegiveis_legal(grava: bool = True) -> dict[str, pd.DataFrame]:
    """Elegibilidade legal (½ SM per capita) × proxy decis 1-3 — artefatos E6.

    Saídas (grava=True):
     - pof_elegiveis_legal_uf.csv  [uf, f_low_legal, share_familias_elegiveis,
                                    share_pessoas_elegiveis, formula, fonte]
     - cashback_elegibilidade.csv  comparação por UF + linha BR: f_low decis-3
       vs legal, delta, shares de famílias/pessoas e share do piso (art. 118)
       na cesta de cada público (espelho da definição do pipeline).

    NÃO altera pof_decis_uf.parquet nem o f_low central — o flip do cenário
    central é decisão do orquestrador (pipeline.monta_insumos).
    """
    from aferir.base import itens_combustiveis   # sem ciclo: base → gaps → config

    micro = le_despesas()
    uc = classifica_elegivel_legal(le_moradores())
    dec = decis_renda(uc)[["cod_upa", "num_dom", "num_uc", "decil_renda"]]
    uc = uc.merge(dec, on=["cod_upa", "num_dom", "num_uc"], validate="1:1")

    fonte_legal = (
        "IBGE POF 2017-2018 (MORADOR: RENDA_TOTAL mensal, deflação e pesos na "
        "data de referência 15/01/2018 — Dicionário de Variáveis, aba Morador); "
        "SM R$ 954,00 = Decreto nº 9.255/2017, art. 1º; LC 214, arts. 112-113 "
        "(renda familiar per capita de até ½ SM; take-up 100% implícito)"
    )

    # ---- despesa por UC na MESMA definição do f_low atual (ex-cód. 101) ----
    desp_uc = (
        micro[micro["codigo_pof"] != CODIGO_ALUGUEL_IMPUTADO]
        .groupby(["cod_upa", "num_dom", "num_uc"], as_index=False)["despesa_anual_rs"]
        .sum()
        .rename(columns={"despesa_anual_rs": "despesa"})
    )
    uc = uc.merge(desp_uc, on=["cod_upa", "num_dom", "num_uc"], how="left")
    uc["despesa"] = uc["despesa"].fillna(0.0)

    def _agrega(df: pd.DataFrame) -> dict:
        el = df["elegivel_legal"]
        return {
            "f_low_legal": df.loc[el, "despesa"].sum() / df["despesa"].sum(),
            "share_familias_elegiveis":
                df.loc[el, "peso_final"].sum() / df["peso_final"].sum(),
            "share_pessoas_elegiveis":
                df.loc[el, "pop_w"].sum() / df["pop_w"].sum(),
        }

    legal_uf = pd.DataFrame(
        [{"uf": u, **_agrega(g)} for u, g in uc.groupby("uf", sort=True)])
    legal_uf["formula"] = (
        "elegível ⇔ RENDA_TOTAL/moradores ≤ R$ 477,00 (½×954,00); f_low_legal "
        "= Σ despesa (ex-cód. 101) dos elegíveis ÷ Σ despesa da UF — MESMA "
        "definição de despesa do f_low decis 1-3; shares c/ peso PESO_FINAL "
        "(famílias) e PESO_FINAL×moradores (pessoas)"
    )
    legal_uf["fonte"] = fonte_legal

    # ---- comparação decis-3 × legal, com consumo do piso por público -------
    micro2 = micro.copy()
    micro2["codigo_pof"] = micro2["codigo_pof"].astype(str)
    comb = itens_combustiveis(micro2)
    piso = _codigos_piso_espelho()
    em_campo = micro2[~micro2["codigo_pof"].isin(comb)]
    por_uc = (
        em_campo.assign(despesa_piso=em_campo["despesa_anual_rs"]
                        .where(em_campo["codigo_pof"].isin(piso), 0.0))
        .groupby(["cod_upa", "num_dom", "num_uc"], as_index=False)
        .agg(despesa_campo=("despesa_anual_rs", "sum"),
             despesa_piso=("despesa_piso", "sum"))
    )
    uc = uc.merge(por_uc, on=["cod_upa", "num_dom", "num_uc"], how="left")
    uc[["despesa_campo", "despesa_piso"]] = \
        uc[["despesa_campo", "despesa_piso"]].fillna(0.0)

    def _linha(df: pd.DataFrame) -> dict:
        el = df["elegivel_legal"]
        d3 = df["decil_renda"] <= DECIS_CASHBACK
        return {
            "f_low_decis3": df.loc[d3, "despesa"].sum() / df["despesa"].sum(),
            "f_low_legal": df.loc[el, "despesa"].sum() / df["despesa"].sum(),
            "share_familias_elegiveis":
                df.loc[el, "peso_final"].sum() / df["peso_final"].sum(),
            "share_pessoas_elegiveis":
                df.loc[el, "pop_w"].sum() / df["pop_w"].sum(),
            "share_piso_decis3":
                df.loc[d3, "despesa_piso"].sum() / df.loc[d3, "despesa_campo"].sum(),
            "share_piso_legal":
                df.loc[el, "despesa_piso"].sum() / df.loc[el, "despesa_campo"].sum(),
        }

    linhas = [{"uf": u, **_linha(g)} for u, g in uc.groupby("uf", sort=True)]
    linhas.append({"uf": "BR", **_linha(uc)})
    comp = pd.DataFrame(linhas)
    comp["delta_f_low"] = comp["f_low_legal"] - comp["f_low_decis3"]
    comp = comp[["uf", "f_low_decis3", "f_low_legal", "delta_f_low",
                 "share_familias_elegiveis", "share_pessoas_elegiveis",
                 "share_piso_decis3", "share_piso_legal"]]
    comp["formula"] = (
        "decis3 = decis populacionais nacionais 1-3 (proxy atual); legal = "
        "rpc ≤ ½ SM 15/01/2018; f_low sobre despesa ex-cód. 101; share_piso = "
        "Σ despesa itens art. 118 (regex espelho de pipeline.PADRAO_PISO) ÷ "
        "Σ despesa em campo ex-combustíveis do PRÓPRIO público"
    )
    comp["fonte"] = fonte_legal + "; matriz data/inputs/matriz_pof_ibs_v5.csv"

    # ---- proveniência -------------------------------------------------------
    el = uc["elegivel_legal"]
    MANIFEST.registra("salario_minimo_2018", Num(
        SALARIO_MINIMO_2018, "salário mínimo nacional em 15/01/2018",
        "Decreto nº 9.255, de 29/12/2017, art. 1º (vigência 1º/01/2018)",
        Label.OFICIAL, "R$/mês"))
    MANIFEST.registra("pof_limiar_legal_rpc", Num(
        LIMIAR_LEGAL_RPC, "½ × salário mínimo de 15/01/2018 (LC 214, art. 113)",
        "Decreto nº 9.255/2017; LC 214, arts. 112-113", Label.DERIVADO,
        "R$/mês per capita (preços 15/01/2018)"))
    MANIFEST.registra("pof_f_low_nacional_legal", Num(
        float(uc.loc[el, "despesa"].sum() / uc["despesa"].sum()),
        "Σ despesa (ex-cód. 101) das UCs com rpc ≤ ½ SM ÷ Σ despesa",
        fonte_legal, Label.DERIVADO, "fração"))
    MANIFEST.registra("pof_familias_elegiveis_legal", Num(
        float(uc.loc[el, "peso_final"].sum()),
        "Σ PESO_FINAL das UCs com rpc ≤ ½ SM", fonte_legal,
        Label.DERIVADO, "famílias (2018)"))
    MANIFEST.registra("pof_pessoas_elegiveis_legal", Num(
        float(uc.loc[el, "pop_w"].sum()),
        "Σ PESO_FINAL×moradores das UCs com rpc ≤ ½ SM", fonte_legal,
        Label.DERIVADO, "pessoas (2018)"))

    saidas = {"legal_uf": legal_uf, "comparacao": comp}
    if grava:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        legal_uf.to_csv(PROCESSED / "pof_elegiveis_legal_uf.csv", index=False)
        comp.to_csv(PROCESSED / "cashback_elegibilidade.csv", index=False)
        for nome in ("pof_elegiveis_legal_uf.csv", "cashback_elegibilidade.csv"):
            MANIFEST.registra_arquivo(PROCESSED / nome)
    return saidas


# ------------------------------------------------------------------ pipeline
def constroi(grava: bool = True) -> dict[str, pd.DataFrame]:
    """Constrói e (opcionalmente) grava as três saídas processadas da POF."""
    registra_cache_raw()
    micro = le_despesas()
    uc = le_moradores()

    fonte_desp = FONTE.format(arq="DESPESA_COLETIVA+DESPESA_INDIVIDUAL+"
                                  "CADERNETA_COLETIVA+ALUGUEL_ESTIMADO")

    # ---- 1. despesa anual por item POF × UF (TODOS os itens) --------------
    item_uf = (
        micro.groupby(["codigo_pof", "uf"], as_index=False)["despesa_anual_rs"]
        .sum()
        .sort_values(["codigo_pof", "uf"], kind="mergesort")
        .reset_index(drop=True)
    )
    item_uf["formula"] = "Σ_uc V8000_DEFLA×V9011_eff×FATOR_ANUALIZACAO×PESO_FINAL"
    item_uf["fonte"] = fonte_desp

    # ---- 2. famílias (UCs expandidas) por UF ------------------------------
    fam_uf = (
        uc.groupby("uf", as_index=False)
        .agg(familias=("peso_final", "sum"))
        .sort_values("uf", kind="mergesort")
        .reset_index(drop=True)
    )
    fam_uf["formula"] = "Σ PESO_FINAL por UC única (COD_UPA,NUM_DOM,NUM_UC)"
    fam_uf["fonte"] = FONTE.format(arq="MORADOR")

    # ---- 3. despesa por UF × decil nacional de renda per capita -----------
    dec = decis_renda(uc)
    desp_uc = (
        micro[micro["codigo_pof"] != CODIGO_ALUGUEL_IMPUTADO]
        .groupby(["cod_upa", "num_dom", "num_uc"], as_index=False)["despesa_anual_rs"]
        .sum()
        .rename(columns={"despesa_anual_rs": "despesa"})
    )
    dec = dec.merge(desp_uc, on=["cod_upa", "num_dom", "num_uc"], how="left")
    dec["despesa"] = dec["despesa"].fillna(0.0)
    decis_uf = (
        dec.groupby(["uf", "decil_renda"], as_index=False)["despesa"]
        .sum()
        .sort_values(["uf", "decil_renda"], kind="mergesort")
        .reset_index(drop=True)
    )
    decis_uf["formula"] = (
        "Σ despesa_anual_rs (ex-aluguel imputado, cód. 101 — LC 214 art. 4º) "
        "por UF × decil populacional nacional de renda per capita "
        "(peso = PESO_FINAL×moradores)"
    )
    decis_uf["fonte"] = fonte_desp + "; renda/pesos: MORADOR"

    # ---- proveniência (Nums do grafo) --------------------------------------
    familias_total = float(fam_uf["familias"].sum())
    aluguel_anual = float(
        item_uf.loc[item_uf["codigo_pof"] == CODIGO_ALUGUEL_IMPUTADO,
                    "despesa_anual_rs"].sum()
    )
    aluguel_mensal_fam = aluguel_anual / 12.0 / familias_total
    low = decis_uf["decil_renda"] <= DECIS_CASHBACK
    f_low_nac = float(decis_uf.loc[low, "despesa"].sum() / decis_uf["despesa"].sum())

    MANIFEST.registra("pof_familias_total", Num(
        familias_total,
        "Σ PESO_FINAL por UC única (MORADOR)",
        FONTE.format(arq="MORADOR") + " | validação: IBGE POF 2017-2018 = 69.017.704",
        Label.DERIVADO, "famílias"))
    MANIFEST.registra("pof_aluguel_estimado_mensal_por_familia", Num(
        aluguel_mensal_fam,
        "Σ despesa_anual_rs(cód.101) / 12 / famílias",
        fonte_desp + " | validação: IBGE SIDRA t/6970 = R$ 606,15/mês",
        Label.DERIVADO, "R$/mês (preços 15/01/2018)"))
    MANIFEST.registra("pof_despesa_anual_total", Num(
        float(item_uf["despesa_anual_rs"].sum()),
        "Σ despesa_anual_rs (todos os itens/UFs)", fonte_desp,
        Label.DERIVADO, "R$/ano (preços 15/01/2018)"))
    MANIFEST.registra("pof_f_low_nacional_decis_1_3", Num(
        f_low_nac,
        f"Σ despesa decis 1-{DECIS_CASHBACK} / Σ despesa (ex-aluguel imputado)",
        "pof_decis_uf.parquet; LC 214 arts. 112-118 (proxy CadÚnico)",
        Label.DERIVADO, "fração"))

    saidas = {"despesa_item_uf": item_uf, "familias_uf": fam_uf,
              "decis_uf": decis_uf}
    if grava:
        PROCESSED.mkdir(parents=True, exist_ok=True)
        item_uf.to_parquet(PROCESSED / "pof_despesa_item_uf.parquet", index=False)
        fam_uf.to_csv(PROCESSED / "pof_familias_uf.csv", index=False)
        decis_uf.to_parquet(PROCESSED / "pof_decis_uf.parquet", index=False)
        for nome in ("pof_despesa_item_uf.parquet", "pof_familias_uf.csv",
                     "pof_decis_uf.parquet"):
            MANIFEST.registra_arquivo(PROCESSED / nome)
    return saidas


if __name__ == "__main__":
    import sys

    if "legal" in sys.argv[1:]:   # E6: só os artefatos do critério legal
        s = constroi_elegiveis_legal(grava=True)
        comp = s["comparacao"].set_index("uf")
        br = comp.loc["BR"]
        print(f"f_low nacional: decis-3 = {br['f_low_decis3']:.4f} | "
              f"legal (½ SM) = {br['f_low_legal']:.4f} "
              f"(Δ = {br['delta_f_low']:+.4f})")
        print(f"famílias elegíveis = {br['share_familias_elegiveis']:.4f}; "
              f"pessoas elegíveis = {br['share_pessoas_elegiveis']:.4f}")
        print(f"share_piso: decis-3 = {br['share_piso_decis3']:.4f} | "
              f"legal = {br['share_piso_legal']:.4f}")
        raise SystemExit(0)

    tabelas = constroi(grava=True)
    fam = float(tabelas["familias_uf"]["familias"].sum())
    it = tabelas["despesa_item_uf"]
    alug = float(it.loc[it["codigo_pof"] == CODIGO_ALUGUEL_IMPUTADO,
                        "despesa_anual_rs"].sum())
    print(f"famílias (Σ PESO_FINAL, UC única) = {fam:,.0f}")
    print(f"aluguel estimado médio mensal/família = R$ {alug / 12 / fam:,.4f}")
    print(f"despesa anual total ponderada = R$ {it['despesa_anual_rs'].sum():,.0f}")
    print(f"itens POF distintos = {it['codigo_pof'].nunique()}")
