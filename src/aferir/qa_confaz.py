"""Item A1.2 — validação externa: ICMS CONFAZ × RREO por UF-ano (2024-2025).

Diligência F1 destravada: o Boletim de Arrecadação dos Tributos Estaduais
(CONFAZ) chegou como arquivo MANUAL da interface do dados.gov.br (fetch-manual,
§10.4; sha256 no sidecar) — extração de 23/06/2026, "com pendências" declaradas
no próprio cabeçalho. Diferentemente do confronto RREO×DCA×MSC (autodeclarações
do mesmo ente ao SICONFI = invariantes de CONSISTÊNCIA), o boletim CONFAZ é
apuração reportada pelas SEFAZs em outro sistema — a comparação vale como
VALIDAÇÃO EXTERNA de ordem de grandeza, ainda que não seja fonte independente
do fisco estadual.

Grava data/processed/qa_confaz_vs_rreo.csv: por UF-ano, ICMS do boletim (soma
dos meses da coluna de total do ICMS) × ICMS RREO (icms_bruto de r_estadual.csv,
rubrica "ICMSLiquidoExcetoTransferenciasEFUNDEB") e o desvio percentual, com
PONTES conceituais testadas UF a UF quando o desvio excede 1%:

  (i)  +DAIC   — o boletim separa a dívida ativa de ICMS em coluna própria
       (DAIC); a rubrica RREO/DCA consolida principal+multas+DA
       (conta 1.1.1.4.50.1.0). Teste: somar DAIC ao boletim.
  (ii) −FECP   — o RREO INCLUI o adicional FECP (identidade DCA 54/54,
       fecp_uf.csv); parte das UFs reporta o boletim SEM o adicional
       (caso RJ, onde o FECP ≈ 11% do ICMS). Teste: deduzir a FECP bruta
       da DCA do lado RREO.
  (iii) pendências — o cabeçalho declara carga incompleta; meses com total
       < 50% da mediana mensal do próprio UF-ano são marcados como
       pendentes (p.ex. SC dez/2024 ≈ R$ 0,02 bi).

Resíduos não fechados por (i)-(iii) ficam registrados como hipóteses
(caixa×competência; restituições — o RREO é líquido de restituições, o
boletim aparenta caixa bruto) — fronteira do que o dado aberto permite.

Meses de 2026 existem no arquivo e ficam FORA: a janela do artigo é 2024-2025
(config.JANELA_RECEITA).

Avaliação A2.5 (combustíveis): a função `avaliacao_adrem_cnae` mede a razão
entre a dedução ad rem estimada (deducao_icms_adrem_uf_mes.csv) e o ICMS da
Divisão CNAE 19 (coque/derivados de petróleo E biocombustíveis) do boletim.
DECISÃO (deliberada): qa_adrem_vs_confaz.csv NÃO é gravado — o ICMS por CNAE
do RECOLHEDOR não identifica o ICMS-combustíveis do PRODUTO: (a) a monofasia
concentra recolhimento em refino/distribuição, mas distribuidoras (CNAE 46.81,
dentro da Divisão 46 = TODO o atacado) e varejo (47.3, dentro da 47) não são
separáveis; (b) a Divisão 19 inclui usinas de etanol/biodiesel (etanol
hidratado está FORA do ad rem) e derivados não-combustíveis; (c) a razão
medida por UF-ano varia de 0,8× a 58× (mediana ≈ 2), com saltos de
atribuição entre anos (MT, ES, AM, PR) — a ponte não é defensável nem como
ordem de grandeza por UF. A série CONFAZ que permitiria a reconciliação
(va_icms_combustiveis, aba "arrecadacao por setor") termina em 2023, fora da
janela — fronteira de dados abertos declarada no Anexo B.

CLI: PYTHONPATH=src python3 -m aferir.qa_confaz
"""
from __future__ import annotations

import pandas as pd

from . import config
from .provenance import MANIFEST, Label, Num

QA_CSV = config.PROCESSED / "qa_confaz_vs_rreo.csv"

# limiar do item A1 (implementação 3): investigar desvios acima de 1%
LIMIAR_INVESTIGA_PCT = 1.0
# mês pendente: total do ICMS < 50% da mediana mensal do próprio UF-ano
FRACAO_MES_PENDENTE = 0.5

_COL_UF = "Descrição da UF"
_COL_ICMS_TOTAL = "TOTAL DO ICMS"          # prefixo (nome traz espaço duplo)
_COL_DAIC = "DAIC"                          # dívida ativa de ICMS
_COL_DIV19 = "Divisão: 19"                  # coque/derivados/biocombustíveis

_FONTE_CONFAZ = (
    "CONFAZ, Boletim de Arrecadação dos Tributos Estaduais, aba 'arrecadação "
    "por CNAE' (extração 23/06/2026, 'com pendências' — cabeçalho do arquivo); "
    "obtido pela interface do dados.gov.br (conjunto boletim-de-arrecadacao-"
    "dos-tributos-estaduais; API autenticada — rota fetch-manual §10.4); "
    "arquivo congelado data/raw/confaz/20260623_dados-abertos.xlsx "
    "(sha256 no sidecar ._meta.json)")
_FONTE_RREO = (
    "SICONFI RREO Anexo 03 via data/processed/r_estadual.csv (icms_bruto = "
    "rubrica ICMSLiquidoExcetoTransferenciasEFUNDEB, inclui FECP e consolida "
    "dívida ativa; FECP = dca_fecp_bruta, DCA Anexo I-C conta 1.1.1.4.50.2.0)")


def _coluna(df: pd.DataFrame, prefixo: str) -> str:
    """Localiza coluna pelo prefixo do rótulo oficial; falha alto se ausente."""
    achadas = [c for c in df.columns if str(c).startswith(prefixo)]
    if len(achadas) != 1:
        raise ValueError(f"coluna com prefixo '{prefixo}': esperada 1, "
                         f"achadas {achadas}")
    return achadas[0]


def carrega_confaz_cnae() -> pd.DataFrame:
    """Aba 'arrecadação por CNAE' validada e deduplicada, janela 2024-2025.

    Validações bloqueantes: cabeçalho com a data de extração esperada;
    duplicatas (UF, co_periodo) só se byte-idênticas (o arquivo traz o AC
    2024-2025 em linhas duplicadas idênticas); 27 UFs × 12 meses por ano.
    """
    MANIFEST.registra_arquivo(config.RAW_CONFAZ_XLSX)
    nota = pd.read_excel(config.RAW_CONFAZ_XLSX, sheet_name=config.CONFAZ_ABA_CNAE,
                         header=None, nrows=1).iloc[0, 0]
    if config.CONFAZ_EXTRACAO not in str(nota) or "pendencias" not in str(nota):
        raise ValueError(f"cabeçalho inesperado no boletim CONFAZ: {nota!r}")

    df = pd.read_excel(config.RAW_CONFAZ_XLSX, sheet_name=config.CONFAZ_ABA_CNAE,
                       header=1)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df["id_uf"].notna()].copy()
    df["uf"] = df[_COL_UF].astype(str).str.strip()
    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)

    col_tot = _coluna(df, _COL_ICMS_TOTAL)
    dup = df.duplicated(subset=["uf", "co_periodo"], keep=False)
    if dup.any():
        variantes = (df[dup].groupby(["uf", "co_periodo"])[col_tot]
                     .nunique())
        if (variantes > 1).any():
            raise ValueError("duplicatas (UF, co_periodo) com valores "
                             f"DIVERGENTES no boletim: {variantes[variantes > 1]}")
        df = df.drop_duplicates(subset=["uf", "co_periodo"])

    df = df[df["ano"].isin(config.JANELA_RECEITA)].copy()
    if sorted(df["uf"].unique()) != config.UFS:
        raise ValueError("boletim CONFAZ sem as 27 UFs na janela 2024-2025")
    meses = df.groupby(["uf", "ano"])["mes"].nunique()
    if (meses != 12).any():
        raise ValueError(f"UF-ano sem 12 meses no boletim: {meses[meses != 12]}")
    return df


def _pontes(row: pd.Series) -> list[tuple[str, float]]:
    """Desvios percentuais (CONFAZ vs. RREO) sob cada ponte conceitual."""
    c, d, r, f = (row["icms_confaz_rs"], row["daic_confaz_rs"],
                  row["icms_rreo_rs"], row["fecp_dca_rs"])
    return [
        ("sem_ajuste", (c / r - 1.0) * 100.0),
        ("confaz+DAIC", ((c + d) / r - 1.0) * 100.0),
        ("rreo-FECP", (c / (r - f) - 1.0) * 100.0),
        ("confaz+DAIC e rreo-FECP", ((c + d) / (r - f) - 1.0) * 100.0),
    ]


def _investigacao(row: pd.Series) -> str:
    """Texto de investigação (item A1, implementação 3) para desvios > 1%."""
    if abs(row["desvio_pct"]) <= LIMIAR_INVESTIGA_PCT:
        return ""
    partes = []
    if row["meses_pendentes"] > 0:
        partes.append(
            f"carga incompleta declarada no boletim ({row['meses_pendentes']} "
            f"mes(es) pendente(s): {row['meses_pendentes_lista']}) — desvio "
            "negativo esperado; comparação inconclusiva nesta vintage")
    if (row["ponte_melhor"] != "sem_ajuste"
            and abs(row["desvio_pos_ponte_pct"]) <= LIMIAR_INVESTIGA_PCT):
        partes.append(
            f"ponte conceitual fecha: {row['ponte_melhor']} reduz o desvio de "
            f"{row['desvio_pct']:.2f}% para {row['desvio_pos_ponte_pct']:.2f}% "
            "(DAIC: RREO/DCA consolidam divida ativa que o boletim separa; "
            "FECP: RREO inclui o adicional que esta UF nao reporta no boletim)")
    elif abs(row["desvio_pos_ponte_pct"]) > LIMIAR_INVESTIGA_PCT:
        residual = ("boletim ACIMA do RREO: consistente com caixa bruto de "
                    "restituicoes no boletim (o RREO e liquido de restituicoes) "
                    "e/ou caixa×competencia"
                    if row["desvio_pos_ponte_pct"] > 0 else
                    "boletim ABAIXO do RREO: consistente com pendencia de carga "
                    "distribuida nos meses (vintage 'com pendencias') e/ou "
                    "caixa×competencia")
        partes.append(
            f"sem ponte que feche em dado aberto (melhor: {row['ponte_melhor']}"
            f", {row['desvio_pos_ponte_pct']:.2f}%); {residual}")
    return "; ".join(partes)


def qa_confaz_vs_rreo() -> pd.DataFrame:
    """Confronto CONFAZ×RREO por UF-ano + resumo (mediana e máximo de |desvio|).

    Grava data/processed/qa_confaz_vs_rreo.csv (determinístico byte a byte).
    """
    confaz = carrega_confaz_cnae()
    col_tot = _coluna(confaz, _COL_ICMS_TOTAL)
    col_daic = _coluna(confaz, _COL_DAIC)

    # meses pendentes: total mensal < 50% da mediana mensal do próprio UF-ano
    mediana_mes = confaz.groupby(["uf", "ano"])[col_tot].transform("median")
    confaz["pendente"] = confaz[col_tot] < FRACAO_MES_PENDENTE * mediana_mes

    g = (confaz.groupby(["uf", "ano"])
         .agg(meses_confaz=("mes", "nunique"),
              meses_pendentes=("pendente", "sum"),
              icms_confaz_rs=(col_tot, "sum"),
              daic_confaz_rs=(col_daic, "sum"))
         .reset_index())
    listas = (confaz[confaz["pendente"]]
              .sort_values("mes")
              .groupby(["uf", "ano"])["mes"]
              .agg(lambda s: "+".join(str(int(m)) for m in s))
              .rename("meses_pendentes_lista").reset_index())
    g = g.merge(listas, on=["uf", "ano"], how="left")
    g["meses_pendentes_lista"] = g["meses_pendentes_lista"].fillna("")

    r = pd.read_csv(config.PROCESSED / "r_estadual.csv")
    r = r[r["ano"].isin(config.JANELA_RECEITA)][
        ["uf", "ano", "icms_bruto", "dca_fecp_bruta"]].rename(
        columns={"icms_bruto": "icms_rreo_rs", "dca_fecp_bruta": "fecp_dca_rs"})
    r["fecp_dca_rs"] = r["fecp_dca_rs"].fillna(0.0)
    m = g.merge(r, on=["uf", "ano"], validate="one_to_one")

    nomes = {"sem_ajuste": "desvio_pct", "confaz+DAIC": "desvio_mais_daic_pct",
             "rreo-FECP": "desvio_ex_fecp_pct",
             "confaz+DAIC e rreo-FECP": "desvio_mais_daic_ex_fecp_pct"}
    for i, row in m.iterrows():
        pontes = _pontes(row)
        for ponte, desvio in pontes:
            m.loc[i, nomes[ponte]] = desvio
        melhor = min(pontes, key=lambda p: abs(p[1]))
        m.loc[i, "ponte_melhor"] = melhor[0]
        m.loc[i, "desvio_pos_ponte_pct"] = melhor[1]
    m["investigacao"] = m.apply(_investigacao, axis=1)
    m["estatistica"] = "uf_ano"
    m["formula"] = (
        "icms_confaz_rs = Σ 12 meses da coluna 'TOTAL DO ICMS  TOTAL DA SEÇÃO' "
        "(R$ correntes; duplicatas idênticas deduplicadas); desvio_pct = "
        "(icms_confaz_rs/icms_rreo_rs − 1)×100; pontes: +DAIC soma a dívida "
        "ativa de ICMS do boletim; −FECP deduz dca_fecp_bruta do RREO; "
        "mês pendente = total mensal < 50% da mediana mensal do UF-ano")
    m["fonte"] = _FONTE_CONFAZ + " | " + _FONTE_RREO
    m = m.sort_values(["uf", "ano"]).reset_index(drop=True)

    # ------------------------------------------------ resumo (item A1, impl. 5)
    resumo = []
    for ano in sorted(config.JANELA_RECEITA):
        sel = m[m["ano"] == ano]
        med = float(sel["desvio_pct"].abs().median())
        imax = sel["desvio_pct"].abs().idxmax()
        vmax = float(sel.loc[imax, "desvio_pct"])
        uf_max = sel.loc[imax, "uf"]
        med_pos = float(sel["desvio_pos_ponte_pct"].abs().median())
        max_pos = float(sel["desvio_pos_ponte_pct"].abs().max())
        base = {
            "uf": "BR", "ano": ano, "meses_confaz": 12,
            "meses_pendentes": int(sel["meses_pendentes"].sum()),
            "meses_pendentes_lista": "", "icms_confaz_rs": float("nan"),
            "daic_confaz_rs": float("nan"), "icms_rreo_rs": float("nan"),
            "fecp_dca_rs": float("nan"), "desvio_mais_daic_pct": float("nan"),
            "desvio_ex_fecp_pct": float("nan"),
            "desvio_mais_daic_ex_fecp_pct": float("nan"), "ponte_melhor": "",
            "fonte": _FONTE_CONFAZ + " | " + _FONTE_RREO,
        }
        resumo.append(base | {
            "estatistica": "mediana_ano", "desvio_pct": med,
            "desvio_pos_ponte_pct": med_pos,
            "investigacao": "",
            "formula": ("mediana de |desvio_pct| das 27 UFs no ano; "
                        "desvio_pos_ponte_pct = mediana de |desvio| após a "
                        "melhor ponte de cada UF")})
        resumo.append(base | {
            "estatistica": "maximo_ano", "desvio_pct": abs(vmax),
            "desvio_pos_ponte_pct": max_pos,
            "investigacao": (f"máximo atingido por {uf_max} "
                             f"({vmax:.2f}% sem ajuste)"),
            "formula": ("máximo de |desvio_pct| das 27 UFs no ano; "
                        "desvio_pos_ponte_pct = máximo de |desvio| após a "
                        "melhor ponte de cada UF")})
        MANIFEST.registra(f"qa_confaz_rreo_mediana_{ano}", Num(
            med, "mediana de |desvio %| CONFAZ×RREO, 27 UFs",
            "boletim CONFAZ (fetch-manual F1) × SICONFI RREO An.03",
            Label.DERIVADO, "%"))
        MANIFEST.registra(f"qa_confaz_rreo_maximo_{ano}", Num(
            abs(vmax), f"máximo de |desvio %| CONFAZ×RREO ({uf_max})",
            "boletim CONFAZ (fetch-manual F1) × SICONFI RREO An.03",
            Label.DERIVADO, "%"))

    out = pd.concat([m, pd.DataFrame(resumo)], ignore_index=True)
    colunas = ["uf", "ano", "estatistica", "meses_confaz", "meses_pendentes",
               "meses_pendentes_lista", "icms_confaz_rs", "daic_confaz_rs",
               "icms_rreo_rs", "fecp_dca_rs", "desvio_pct",
               "desvio_mais_daic_pct", "desvio_ex_fecp_pct",
               "desvio_mais_daic_ex_fecp_pct", "ponte_melhor",
               "desvio_pos_ponte_pct", "investigacao", "formula", "fonte"]
    out = out[colunas]
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_csv(QA_CSV, index=False)
    return out


def avaliacao_adrem_cnae() -> pd.DataFrame:
    """Avaliação A2.5 — dedução ad rem × ICMS da Divisão CNAE 19 (por UF-ano).

    Medição de diagnóstico, NÃO gravada como artefato de reconciliação (ver
    docstring do módulo): o CNAE do recolhedor não identifica o produto. As
    linhas 'BR' agregam o nacional. Retorna o DataFrame para inspeção e para
    os testes; nenhum CSV é escrito.
    """
    confaz = carrega_confaz_cnae()
    col19 = _coluna(confaz, _COL_DIV19)
    g = (confaz.groupby(["uf", "ano"])[col19].sum()
         .rename("icms_div19_rs").reset_index())
    ded = pd.read_csv(config.PROCESSED / "deducao_icms_adrem_uf_mes.csv")
    da = (ded[ded["ano"].isin(config.JANELA_RECEITA)]
          .groupby(["uf", "ano"])["deducao_rs"].sum()
          .rename("deducao_adrem_rs").reset_index())
    m = g.merge(da, on=["uf", "ano"], validate="one_to_one")
    br = (m.groupby("ano")[["icms_div19_rs", "deducao_adrem_rs"]]
          .sum().reset_index())
    br.insert(0, "uf", "BR")
    m = pd.concat([m, br], ignore_index=True)
    m["razao_adrem_div19"] = m["deducao_adrem_rs"] / m["icms_div19_rs"]
    return m.sort_values(["uf", "ano"]).reset_index(drop=True)


def main() -> None:
    out = qa_confaz_vs_rreo()
    resumo = out[out["estatistica"] != "uf_ano"]
    print("qa_confaz_vs_rreo.csv gravado em", QA_CSV)
    print(resumo[["ano", "estatistica", "desvio_pct",
                  "desvio_pos_ponte_pct", "investigacao"]]
          .to_string(index=False))
    acima = out[(out["estatistica"] == "uf_ano")
                & (out["desvio_pct"].abs() > LIMIAR_INVESTIGA_PCT)]
    print(f"\nUF-anos com |desvio| > {LIMIAR_INVESTIGA_PCT}%: {len(acima)}")
    print(acima[["uf", "ano", "desvio_pct", "ponte_melhor",
                 "desvio_pos_ponte_pct"]].to_string(index=False))

    a25 = avaliacao_adrem_cnae()
    br = a25[a25["uf"] == "BR"]
    print("\nAvaliação A2.5 (diagnóstico; qa_adrem_vs_confaz.csv NÃO gravado"
          " — ver docstring do módulo):")
    print(br.to_string(index=False))
    q = a25[a25["uf"] != "BR"]["razao_adrem_div19"]
    print(f"razão por UF-ano: mín {q.min():.2f}× | mediana {q.median():.2f}× "
          f"| máx {q.max():.2f}× — CNAE do recolhedor ≠ ICMS do produto; "
          "ponte indefensável por UF")


if __name__ == "__main__":
    main()
