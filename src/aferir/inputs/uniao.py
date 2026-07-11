"""Receita de referência da UNIÃO e âncora da CBS (LC 214, arts. 350, I e 353).

Constrói, a partir do cache dos fetchers (aferir.fetch.rfb_federal e
aferir.fetch.ibge) e dos insumos transcritos (data/inputs/is_ipi_residual.csv):

  processed/r_uniao.csv         [ano, pis_pasep, cofins, ipi, iof_total, ...,
                                 razao_iof_seguros, iof_seguros,
                                 receita_ref_rs_mi, pct_pib, formula, fonte]
  processed/r_uniao_liquida.csv [idem, convenção LÍQUIDA-RTN (Tema 69)]
  processed/pib_nominal.csv     [ano, pib_rs_mi, fonte]
  processed/ancora_uniao.csv    [metrica, valor, unidade, formula, fonte, nota]

Convenções DECLARADAS (não relitigáveis sem fork):
 - PIS/Pasep conjunto: a série aberta não separa PIS de Pasep; o art. 350, I,
   'a' referencia a contribuição por inteiro — sem perda.
 - IOF-Seguros: não existe decomposição aberta máquina-legível do IOF por
   modalidade (fronteira OD/ADM; o cálculo oficial usa a "arrecadação
   observada do IOF-Seguros" — metodologia TCU/RFB, p. 6). Rota aberta:
   razão = R$ 5,4 bi (NT SERT jul/2024, p. 3) ÷ IOF-total 2023 (XLSX RFB),
   constante em toda a janela.
 - Convenção de receita (Tema 69): a série RFB 1994-2025 não explicita
   dedução de restituições ("bruta-RFB"). A convenção LÍQUIDA por tributo
   EXISTE em dado aberto: RTN/STN, Tabela 2.2 (conceito caixa — ingresso
   efetivo na Conta Única, líquida de restituições; ver config.RTN_XLSX_URL).
   Central da âncora = LÍQUIDA-RTN; bruta-RFB = sensibilidade declarada
   (aferir_nacional.csv, coluna ancora_federal). As duas rotas diferem
   também pela alocação por tributo dos parcelamentos (REFIS/PERT) e pelo
   regime de caixa — diferença medida e declarada em ancora_uniao.csv.

Determinismo: nenhum datetime, nenhum acesso à rede fora dos fetchers
(que só baixam se o cache não existir).
"""
from __future__ import annotations

import functools

import pandas as pd

from aferir import config
from aferir.fetch.ibge import pib_nominal_anual
from aferir.fetch.rfb_federal import parse_rfb_receitas, parse_rtn_receitas
from aferir.provenance import MANIFEST, Label, Num

_FONTE_XLSX = ("RFB, Arrecadação das receitas federais 1994 a 2025 "
               f"(R$ mi correntes; aba do ano, coluna TOTAL), {config.RFB_XLSX_URL}")
_FONTE_PIB = ("IBGE, SCN Trimestral — SIDRA t/1846 v/585 c11255/90707 (PIB pm, "
              "valores correntes, R$ mi); PIB anual = soma dos 4 trimestres; "
              f"{config.SIDRA_PIB_1846_URL}")
_FONTE_SERT_P3 = ("NT SERT/MF de 01/07/2024, p. 3 (IOF-Seguros = R$ 5,4 bi), "
                  f"{config.NT_SERT_JUL2024_URL}")
_FONTE_TCU_P6 = ("TCU/RFB, Metodologia da Alíquota de Referência da CBS e "
                 "Redutor, p. 6 (IOF-Seguros observado = dado administrativo), "
                 f"{config.TCU_METODOLOGIA_CBS_URL}")
_FONTE_RTN = ("STN, Resultado do Tesouro Nacional — Série Histórica, Tabela "
              "2.2 (anual, R$ mi correntes; conceito caixa — ingresso efetivo "
              "na Conta Única, nota 1/; líquida de restituições conforme o "
              "Dicionário de Conceitos do dataset: Receita Líquida III=I−II "
              "deduz restituições dentro de I), "
              f"{config.RTN_XLSX_URL}")

_ANOS_R = sorted(set(config.ANCORA_UNIAO) | set(config.JANELA_RECEITA))
_ANOS_PIB = list(range(config.ANCORA_UNIAO[0], config.JANELA_RECEITA[-1] + 1))


@functools.lru_cache(maxsize=1)
def razao_iof_seguros() -> Num:
    """Razão IOF-seguros/IOF-total (convenção declarada — ver docstring)."""
    ano_den = config.RAZAO_IOF_SEGUROS_ANO_DENOMINADOR
    iof_den = float(
        parse_rfb_receitas([ano_den]).set_index("ano").loc[ano_den, "iof_total"])
    razao = config.IOF_SEGUROS_META_SERT_RS_MI / iof_den
    return MANIFEST.registra(
        "razao_iof_seguros",
        Num(razao,
            f"5.400 R$ mi (NT SERT jul/2024, p. 3) / IOF-total {ano_den} "
            f"({iof_den:,.2f} R$ mi, XLSX RFB)",
            f"{_FONTE_SERT_P3}; {_FONTE_XLSX}; fronteira OD/ADM: {_FONTE_TCU_P6}",
            Label.CONVENCAO, "adimensional"))


@functools.lru_cache(maxsize=1)
def r_uniao() -> pd.DataFrame:
    """Série anual da receita de referência da União (R$ mi correntes)."""
    df = parse_rfb_receitas(_ANOS_R)
    pib = pib_nominal_anual(_ANOS_R).set_index("ano")["pib_rs_mi"]
    razao = razao_iof_seguros().valor
    df["razao_iof_seguros"] = razao
    df["iof_seguros"] = df["iof_total"] * razao
    df["receita_ref_rs_mi"] = (df["pis_pasep"] + df["cofins"] + df["ipi"]
                               + df["iof_seguros"])
    df["pct_pib"] = 100.0 * df["receita_ref_rs_mi"] / df["ano"].map(pib)
    df["formula"] = ("receita_ref = PIS/Pasep + Cofins + IPI + razão×IOF_total; "
                     "pct_pib = 100×receita_ref/PIB(SIDRA 1846)")
    df["fonte"] = f"{_FONTE_XLSX}; razão IOF-seguros: {_FONTE_SERT_P3}; PIB: {_FONTE_PIB}"
    for _, r in df.iterrows():
        MANIFEST.registra(
            f"r_uniao_{int(r['ano'])}",
            Num(float(r["receita_ref_rs_mi"]),
                "PIS/Pasep + Cofins + IPI + razão×IOF_total",
                _FONTE_XLSX, Label.DERIVADO, "R$ mi correntes"))
    return df


@functools.lru_cache(maxsize=1)
def r_uniao_liquida() -> pd.DataFrame:
    """Receita de referência da União na convenção LÍQUIDA-RTN (Tema 69).

    Mesma composição do art. 350, I (PIS/Pasep + Cofins + IPI + razão×IOF),
    lida da Tabela 2.2 do RTN/STN — líquida de restituições, conceito caixa.
    Só os anos da âncora (art. 353): a razão IOF-Seguros é a MESMA convenção
    da rota bruta (NT SERT p. 3 ÷ IOF-total 2023), declarada.
    """
    df = parse_rtn_receitas(list(config.ANCORA_UNIAO))
    pib = pib_nominal_anual(list(config.ANCORA_UNIAO)).set_index("ano")["pib_rs_mi"]
    razao = razao_iof_seguros().valor
    df["razao_iof_seguros"] = razao
    df["iof_seguros"] = df["iof_total"] * razao
    df["receita_ref_rs_mi"] = (df["pis_pasep"] + df["cofins"] + df["ipi"]
                               + df["iof_seguros"])
    df["pct_pib"] = 100.0 * df["receita_ref_rs_mi"] / df["ano"].map(pib)
    df["formula"] = ("receita_ref_liq = PIS/Pasep + Cofins + IPI + razão×IOF "
                     "(linhas 1.1.06/1.1.05/1.1.02/1.1.04 da Tabela 2.2 RTN); "
                     "pct_pib = 100×receita_ref_liq/PIB(SIDRA 1846)")
    df["fonte"] = (f"{_FONTE_RTN}; razão IOF-seguros: {_FONTE_SERT_P3}; "
                   f"PIB: {_FONTE_PIB}")
    for _, r in df.iterrows():
        MANIFEST.registra(
            f"r_uniao_liquida_{int(r['ano'])}",
            Num(float(r["receita_ref_rs_mi"]),
                "PIS/Pasep + Cofins + IPI + razão×IOF (líquida-RTN)",
                _FONTE_RTN, Label.DERIVADO, "R$ mi correntes"))
    return df


@functools.lru_cache(maxsize=1)
def pib_nominal() -> pd.DataFrame:
    """PIB nominal anual 2012-2025 (R$ mi correntes) com fonte."""
    df = pib_nominal_anual(_ANOS_PIB)
    df["fonte"] = _FONTE_PIB
    for _, r in df.iterrows():
        MANIFEST.registra(
            f"pib_nominal_{int(r['ano'])}",
            Num(float(r["pib_rs_mi"]), "Σ 4 trimestres SIDRA 1846 (v/585)",
                _FONTE_PIB, Label.DADO, "R$ mi correntes"))
    return df


def ancora_uniao() -> pd.DataFrame:
    """Âncora do art. 353: média 2012-2021 da receita de referência / PIB.

    Duas convenções ABERTAS, ambas publicadas: LÍQUIDA-RTN (central — Tema
    69, restituições deduzidas por tributo) e bruta-RFB (sensibilidade).
    """
    df = r_uniao().set_index("ano")
    anos = config.ANCORA_UNIAO
    pib = pib_nominal_anual(anos).set_index("ano")["pib_rs_mi"]
    media = float(df.loc[anos, "pct_pib"].mean())
    sem_iof = float((100.0 * (df.loc[anos, "pis_pasep"] + df.loc[anos, "cofins"]
                              + df.loc[anos, "ipi"]) / pib).mean())
    media_liq = float(r_uniao_liquida().set_index("ano")
                      .loc[anos, "pct_pib"].mean())
    nota_historica = (
        "A âncora repõe carga HISTÓRICA 2012-2021 por decisão legal "
        "(art. 353, §1º, II) — não comparável 1:1 com exercícios ancorados "
        "em receita corrente (SERT 4,47% PIB é projeção PLDO 2025 de "
        "PIS/Cofins+IPI 2025-2028).")
    nota_liquida = (
        "CENTRAL (Tema 69): convenção LÍQUIDA-RTN — receita por tributo "
        "líquida de restituições, conceito caixa (ingresso efetivo na Conta "
        "Única, Tabela 2.2 do RTN/STN). Difere da bruta-RFB também pela "
        "alocação por tributo dos parcelamentos (REFIS/PERT) e pelo regime "
        "de caixa; a diferença medida (líquida − bruta) é publicada na "
        "métrica delta_liquida_menos_bruta_pct_pib. " + nota_historica)
    nota_bruta = (
        "SENSIBILIDADE: convenção 'bruta-RFB' — a série XLSX 1994-2025 não "
        "explicita dedução de restituições/compensações (Tema 69); central "
        "= líquida-RTN (aferir_nacional.csv, coluna ancora_federal). "
        + nota_historica)
    MANIFEST.registra(
        "ancora_uniao_media_pct_pib_2012_2021",
        Num(media, "média_t∈2012-2021 [100×(PIS/Pasep+Cofins+IPI+razão×IOF_total)_t/PIB_t]",
            f"{_FONTE_XLSX}; {_FONTE_PIB}; {_FONTE_SERT_P3}",
            Label.DERIVADO, "% PIB"))
    MANIFEST.registra(
        "ancora_uniao_liquida_rtn_media_pct_pib_2012_2021",
        Num(media_liq, "média_t∈2012-2021 [100×(PIS/Pasep+Cofins+IPI+razão×IOF)_t"
            "/PIB_t], convenção líquida-RTN (Tema 69)",
            f"{_FONTE_RTN}; {_FONTE_PIB}; {_FONTE_SERT_P3}",
            Label.DERIVADO, "% PIB"))
    linhas = [
        {"metrica": "media_pct_pib_2012_2021_liquida_rtn", "valor": media_liq,
         "unidade": "% PIB",
         "formula": ("média_t∈2012-2021 [100×(PIS/Pasep + Cofins + IPI + "
                     "razão×IOF_total)_t / PIB_t], receitas líquidas-RTN"),
         "fonte": f"{_FONTE_RTN}; {_FONTE_PIB}; razão: {_FONTE_SERT_P3}",
         "nota": nota_liquida},
        {"metrica": "media_pct_pib_2012_2021", "valor": media, "unidade": "% PIB",
         "formula": ("média_t∈2012-2021 [100×(PIS/Pasep + Cofins + IPI + "
                     "razão×IOF_total)_t / PIB_t]"),
         "fonte": f"{_FONTE_XLSX}; {_FONTE_PIB}; razão: {_FONTE_SERT_P3}",
         "nota": nota_bruta},
        {"metrica": "delta_liquida_menos_bruta_pct_pib",
         "valor": media_liq - media, "unidade": "p.p. do PIB",
         "formula": "media_liquida_rtn − media_bruta_rfb",
         "fonte": f"{_FONTE_RTN}; {_FONTE_XLSX}",
         "nota": ("diferença de convenção MEDIDA (Tema 69): restituições "
                  "(↓ líquida) vs alocação de parcelamentos/caixa (↑ líquida "
                  "em anos de REFIS/PERT) — sinal empírico, não imposto")},
        {"metrica": "media_pct_pib_2012_2021_sem_iof_seguros", "valor": sem_iof,
         "unidade": "% PIB",
         "formula": "média_t∈2012-2021 [100×(PIS/Pasep + Cofins + IPI)_t / PIB_t]",
         "fonte": f"{_FONTE_XLSX}; {_FONTE_PIB}",
         "nota": "diagnóstico: peso do rateio IOF-seguros na âncora"},
        {"metrica": "razao_iof_seguros", "valor": razao_iof_seguros().valor,
         "unidade": "adimensional", "formula": razao_iof_seguros().formula,
         "fonte": razao_iof_seguros().fonte,
         "nota": ("CONVENCAO — razão constante 2012-2021 e 2024-2025; a "
                  "decomposição anual verdadeira exige dado administrativo "
                  "(fronteira OD/ADM, C3)")},
    ]
    return pd.DataFrame(linhas)


def grava_processados() -> dict[str, "pd.DataFrame"]:
    """Escreve os três CSVs em data/processed/ (determinístico, %.6f)."""
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    saidas = {
        "r_uniao.csv": r_uniao(),
        "r_uniao_liquida.csv": r_uniao_liquida(),
        "pib_nominal.csv": pib_nominal(),
        "ancora_uniao.csv": ancora_uniao(),
    }
    for nome, df in saidas.items():
        destino = config.PROCESSED / nome
        df.to_csv(destino, index=False, float_format="%.6f")
        MANIFEST.registra_arquivo(destino)
    return saidas


if __name__ == "__main__":
    for nome, df in grava_processados().items():
        print(f"== {nome} ({len(df)} linhas)")
        print(df.to_string(max_colwidth=60))
