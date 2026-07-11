"""TRU 2021 nível 68 — usos por produto e carga embutida nas compras públicas.

Fonte: IBGE, Tabelas de Recursos e Usos nível 68 (128 produtos × 68 atividades),
data/raw/sidra/nivel_68_2010_2021_xls.zip (tab1/tab2, ano 2021 — última
edição DETALHADA; não migrar para 2023).

Saídas (data/processed):
  * tru_2021_usos.parquet — por produto: consumo das famílias, consumo do
    governo, ISFLSF, FBCF, exportações, variação de estoque, importações,
    oferta a preço de consumidor, impostos líquidos de subsídios sobre produtos
    (total/ICMS/IPI/importação), CI das atividades do governo geral (mix de
    absorção das COMPRAS públicas) e t_embutida = impostos líquidos ÷ oferta pc.
  * tru_gov_carga.csv — carga tributária embutida hoje nas aquisições do
    governo (calibra o redutor iso-carga do art. 370 da LC 214 — FORK F8):
    central = mix do consumo intermediário das atividades 8400/8591/8691;
    diagnósticos = mix do consumo final do governo (com e sem produção
    própria); componentes de CAPITAL (revisão A5) = t_embutida dos produtos
    de FBCF, cesta de construção (p/ 4.4.90.51) e de máquinas/equipamentos
    (p/ 4.4.90.52) — a mistura por perímetro fica em sigma_compras.csv
    (aferir.inputs.gov_aquisicoes.constroi_sigma_compras).

Layout dos .xls (verificado em 2026-07-10 contra o zip, sha256 no manifest):
linhas 5..132 = 128 produtos; linha 134 = Total (usada como fechamento interno).
tab1/oferta col.: 2=oferta pc, 5=imp. importação, 6=IPI, 7=ICMS, 8=outros
impostos líq., 9=total impostos líquidos, 10=oferta pb. tab2/demanda col.:
2=exportação, 3=governo, 4=ISFLSF, 5=famílias, 6=FBCF, 7=var. estoque.
"""
from __future__ import annotations

import functools
import io
import zipfile

import pandas as pd

from aferir.config import (
    PROCESSED,
    RAW_TRU_ZIP,
    TRU_ANO,
    TRU_ATIVIDADES_GOV,
    TRU_PRODUTOS_PRODUCAO_PROPRIA_GOV,
    TRU_URL,
)
from aferir.provenance import MANIFEST, Label, Num

_FONTE = f"IBGE TRU {TRU_ANO} nível 68 ({TRU_URL}); cache local {RAW_TRU_ZIP.name}"
_PRODUTOS = slice(5, 133)   # 128 produtos
_LINHA_TOTAL = 134

# Cestas de FBCF para o σ de CAPITAL das compras públicas (revisão A5).
# Enumeração literal dos produtos da TRU nível 68 com FBCF ≠ 0 (auditável no
# tru_2021_usos.parquet), particionados por natureza do elemento de despesa
# (Portaria Interm. STN/SOF 163/2001, Anexo II):
#   4.4.90.51 (obras e instalações) → produtos da CONSTRUÇÃO (atividade 41):
TRU_PRODUTOS_FBCF_CONSTRUCAO = ("41801", "41802", "41803")
#   4.4.90.52 (equipamentos e material permanente) → BENS industriais duráveis
#   (indústria de transformação, códigos 25001-31802). Fora da cesta, por
#   convenção declarada: 33001 (manutenção/instalação = serviço), 62801/71801/
#   71802 (intangíveis — software é elemento 40, P&D/engenharia não são
#   material permanente), 01xxx/02801 (ativos biológicos), 06801/16001/24912
#   (insumos/serviços de apoio, não bens de capital adquiridos prontos).
TRU_PRODUTOS_FBCF_MAQUINAS = (
    "25001", "26001", "26002", "26003", "26004", "27001", "27002",
    "28001", "28002", "28003", "29911", "29912", "30001", "31801", "31802",
)


def _num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce").fillna(0.0)


@functools.lru_cache(maxsize=1)
def _sheets() -> dict[str, pd.DataFrame]:
    MANIFEST.registra_arquivo(RAW_TRU_ZIP)
    z = zipfile.ZipFile(RAW_TRU_ZIP)
    tab1 = pd.ExcelFile(io.BytesIO(z.read(f"68_tab1_{TRU_ANO}.xls")))
    tab2 = pd.ExcelFile(io.BytesIO(z.read(f"68_tab2_{TRU_ANO}.xls")))
    return {
        "oferta": tab1.parse("oferta", header=None),
        "importacao": tab1.parse("importacao", header=None),
        "demanda": tab2.parse("demanda", header=None),
        "ci": tab2.parse("CI", header=None),
    }


def _fechamento(nome: str, soma_produtos: float, total_planilha: float) -> None:
    """Invariante: Σ produtos == linha Total da planilha (tolerância 0,5 R$ mi)."""
    if abs(soma_produtos - total_planilha) > 0.5:
        raise AssertionError(
            f"TRU {TRU_ANO} '{nome}': Σ produtos = {soma_produtos:.1f} difere do "
            f"Total da planilha = {total_planilha:.1f} — layout mudou?")


@functools.lru_cache(maxsize=1)
def usos_2021() -> pd.DataFrame:
    """Usos por produto (R$ mi correntes de 2021), com fechamento interno."""
    sh = _sheets()
    of, im, dm, ci = sh["oferta"], sh["importacao"], sh["demanda"], sh["ci"]

    df = pd.DataFrame({
        "produto_cod": of.iloc[_PRODUTOS, 0].astype(str).values,
        "produto_desc": of.iloc[_PRODUTOS, 1].astype(str).values,
        "oferta_preco_consumidor": _num(of.iloc[_PRODUTOS, 2]).values,
        "imposto_importacao": _num(of.iloc[_PRODUTOS, 5]).values,
        "ipi": _num(of.iloc[_PRODUTOS, 6]).values,
        "icms": _num(of.iloc[_PRODUTOS, 7]).values,
        "outros_impostos_liquidos": _num(of.iloc[_PRODUTOS, 8]).values,
        "impostos_liquidos_produtos": _num(of.iloc[_PRODUTOS, 9]).values,
        "importacoes": _num(im.iloc[_PRODUTOS, 2]).values,
        "exportacoes": _num(dm.iloc[_PRODUTOS, 2]).values,
        "consumo_governo": _num(dm.iloc[_PRODUTOS, 3]).values,
        "consumo_isflsf": _num(dm.iloc[_PRODUTOS, 4]).values,
        "consumo_familias": _num(dm.iloc[_PRODUTOS, 5]).values,
        "fbcf": _num(dm.iloc[_PRODUTOS, 6]).values,
        "variacao_estoque": _num(dm.iloc[_PRODUTOS, 7]).values,
    })
    # Mix de absorção das COMPRAS públicas: consumo intermediário das
    # atividades do governo geral (8400 adm. pública, 8591 educação pública,
    # 8691 saúde pública), colunas identificadas pelo código no cabeçalho.
    hdr = ci.iloc[3].fillna("").astype(str)
    cols_gov = [j for j, h in enumerate(hdr)
                if h.split("\n")[0] in TRU_ATIVIDADES_GOV]
    if len(cols_gov) != len(TRU_ATIVIDADES_GOV):
        raise AssertionError(
            f"TRU CI: esperadas {len(TRU_ATIVIDADES_GOV)} atividades do governo, "
            f"encontradas {len(cols_gov)} — cabeçalho mudou?")
    df["ci_atividades_gov"] = sum(
        _num(ci.iloc[_PRODUTOS, j]).values for j in cols_gov)
    # t_embutida: fração de impostos sobre produtos no valor a preço de
    # consumidor de cada produto (0 quando não há oferta).
    df["t_embutida"] = (df["impostos_liquidos_produtos"]
                        / df["oferta_preco_consumidor"]).fillna(0.0)

    # Fechamentos internos contra a linha Total das planilhas.
    for nome, col, plan, j in (
        ("oferta pc", "oferta_preco_consumidor", of, 2),
        ("impostos líquidos", "impostos_liquidos_produtos", of, 9),
        ("exportações", "exportacoes", dm, 2),
        ("consumo governo", "consumo_governo", dm, 3),
        ("consumo famílias", "consumo_familias", dm, 5),
        ("FBCF", "fbcf", dm, 6),
    ):
        _fechamento(nome, float(df[col].sum()),
                    float(pd.to_numeric(plan.iloc[_LINHA_TOTAL, j])))
    return df


def grava_usos_parquet() -> pd.DataFrame:
    """Escreve tru_2021_usos.parquet com colunas de proveniência."""
    df = usos_2021().copy()
    df["formula"] = ("leitura direta TRU tab1(oferta/importacao)+tab2(demanda/CI) "
                     "2021; t_embutida = impostos_liquidos_produtos/"
                     "oferta_preco_consumidor; ci_atividades_gov = Σ CI das "
                     f"atividades {'/'.join(TRU_ATIVIDADES_GOV)}")
    df["fonte"] = _FONTE
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / "tru_2021_usos.parquet", index=False)
    return df


def carga_embutida_gov() -> dict[str, Num]:
    """Carga tributária embutida nas aquisições do governo (art. 370, iso-carga).

    Central (compras públicas): média de t_embutida ponderada pelo consumo
    intermediário das atividades do governo geral — é o que o governo COMPRA
    do mercado (art. 473: naturezas de aquisição; folha e produção própria
    fora). Diagnósticos: consumo final do governo com e sem os produtos de
    produção própria não-mercantil (84001/84002/85911/86911).
    """
    df = usos_2021()
    t = df["t_embutida"]

    def _media_ponderada(peso: pd.Series) -> float:
        return float((peso * t).sum() / peso.sum())

    own = df["produto_cod"].isin(TRU_PRODUTOS_PRODUCAO_PROPRIA_GOV)
    central = _media_ponderada(df["ci_atividades_gov"])
    diag_consumo = _media_ponderada(df["consumo_governo"])
    diag_compras_finais = _media_ponderada(df.loc[~own, "consumo_governo"])

    nums = {
        "carga_embutida_gov_central_pct": MANIFEST.registra(
            "carga_embutida_gov_central_pct",
            Num(central * 100.0,
                "Σ_p CI_gov_p·t_p / Σ_p CI_gov_p; CI_gov = consumo intermediário "
                f"das atividades {'/'.join(TRU_ATIVIDADES_GOV)}; t_p = impostos "
                "líquidos de subsídios sobre produtos ÷ oferta a preço de "
                "consumidor (TRU 2021)",
                _FONTE, Label.DERIVADO, "% do valor das compras")),
        "carga_embutida_gov_consumo_total_pct": MANIFEST.registra(
            "carga_embutida_gov_consumo_total_pct",
            Num(diag_consumo * 100.0,
                "Σ_p G_p·t_p / Σ_p G_p; G = consumo final do governo (inclui "
                "produção própria não-mercantil — diagnóstico, NÃO usar como "
                "redutor)", _FONTE, Label.DERIVADO, "% do consumo do governo")),
        "carga_embutida_gov_consumo_ex_producao_propria_pct": MANIFEST.registra(
            "carga_embutida_gov_consumo_ex_producao_propria_pct",
            Num(diag_compras_finais * 100.0,
                "Σ_p G_p·t_p / Σ_p G_p excluindo produtos "
                f"{'/'.join(TRU_PRODUTOS_PRODUCAO_PROPRIA_GOV)} (produção "
                "própria); diagnóstico do consumo final adquirido de terceiros",
                _FONTE, Label.DERIVADO, "% do consumo adquirido")),
    }
    return nums


def carga_embutida_fbcf() -> dict[str, Num]:
    """Carga embutida nos produtos de FBCF — componentes do σ de CAPITAL (A5).

    σ_51 (obras e instalações): t_embutida ponderada pela FBCF dos produtos de
    construção. σ_52 (equipamentos/material permanente): idem, cesta de bens
    industriais duráveis. A mistura por perímetro (pesos 51/52 medidos na
    composição de G) é feita em gov_aquisicoes.constroi_sigma_compras.
    """
    df = usos_2021()
    t, w = df["t_embutida"], df["fbcf"]

    def _media(produtos: tuple[str, ...]) -> float:
        m = df["produto_cod"].isin(produtos)
        return float((w[m] * t[m]).sum() / w[m].sum())

    nums = {
        "carga_embutida_fbcf_construcao_pct": MANIFEST.registra(
            "carga_embutida_fbcf_construcao_pct",
            Num(_media(TRU_PRODUTOS_FBCF_CONSTRUCAO) * 100.0,
                "Σ_p FBCF_p·t_p / Σ_p FBCF_p; p em produtos de construção "
                f"{'/'.join(TRU_PRODUTOS_FBCF_CONSTRUCAO)} (cesta do elemento "
                "4.4.90.51 — obras e instalações)",
                _FONTE, Label.DERIVADO, "% do valor das obras")),
        "carga_embutida_fbcf_maquinas_pct": MANIFEST.registra(
            "carga_embutida_fbcf_maquinas_pct",
            Num(_media(TRU_PRODUTOS_FBCF_MAQUINAS) * 100.0,
                "Σ_p FBCF_p·t_p / Σ_p FBCF_p; p em bens industriais duráveis "
                f"{'/'.join(TRU_PRODUTOS_FBCF_MAQUINAS)} (cesta do elemento "
                "4.4.90.52 — equipamentos e material permanente; convenção "
                "declarada: exclui serviços, intangíveis e ativos biológicos)",
                _FONTE, Label.CONVENCAO, "% do valor dos equipamentos")),
    }
    return nums


def grava_gov_carga_csv() -> pd.DataFrame:
    """Escreve tru_gov_carga.csv [cenario, carga_embutida_estimada_pct, formula, fonte].

    Compatibilidade: as três linhas originais (central + diagnósticos)
    permanecem com as mesmas chaves/colunas; as linhas de capital (A5) são
    ADICIONADAS ao final."""
    nums = {**carga_embutida_gov(), **carga_embutida_fbcf()}
    linhas = []
    papel = {
        "carga_embutida_gov_central_pct": "central (mix CI do governo geral — redutor iso-carga F8)",
        "carga_embutida_gov_consumo_total_pct": "diagnóstico (consumo final total do governo)",
        "carga_embutida_gov_consumo_ex_producao_propria_pct": "diagnóstico (consumo final ex-produção própria)",
        "carga_embutida_fbcf_construcao_pct": "componente de capital σ_51 (obras e instalações — A5)",
        "carga_embutida_fbcf_maquinas_pct": "componente de capital σ_52 (equipamentos/material permanente — A5)",
    }
    for chave, num in nums.items():
        linhas.append({
            "cenario": chave,
            "papel": papel[chave],
            "carga_embutida_estimada_pct": num.valor,
            "formula": num.formula,
            "fonte": num.fonte,
        })
    out = pd.DataFrame(linhas)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROCESSED / "tru_gov_carga.csv", index=False)
    return out
