"""Testes do cenário sens_is_ampliado (item A4 — folga da cota inferior do IS).

Goldens medidos em 2026-07-12 sobre o cache congelado (raw estável — este
módulo NÃO pina alíquotas de saída do pipeline, que estão em re-baseline):
 - AMB (ANM), Valor Venda bruta+beneficiada: Ferro 2024 = 149.777.347.701,74
   | Carvão Mineral 2025 = 1.798.204.216,83 (R$ correntes).
 - ANP produção 2024: petróleo 195.397.266,852 m³ | gás 56.069.588.384 m³.
 - Preço de referência médio (média simples entre campos) jan/2024:
   petróleo 2.369,9698 R$/m³ (388 campos) | gás 1,175634 R$/m³ (412 campos).
 - Componentes no teto de 0,25% (art. 422, § 2º, red. LC 227), média janela
   deflacionada (δ=0,952229): ferro 0,378587 | carvão 0,004002 | petróleo
   1,255256 | gás 0,187436 | adicional total 1,825282 R$ bi 2024.

Testes que dependem de cache ausente são pulados (rode os fetchers antes).
"""
from __future__ import annotations

import pytest

from aferir import config
from aferir.is_ampliado import (
    ALIQ_IS_MINERAIS_TETO,
    AMB_SUBSTANCIAS_CAMPO,
    AMB_TABELAS,
    RAW_ANM,
    RAW_ANP_PROD,
    base_minerais_janela_bi,
    base_petroleo_gas_janela_bi,
    precos_referencia_mensais,
    producao_anp_mensal,
    sens_is_ampliado,
    valor_venda_amb,
)

_CACHE_AMB = all((RAW_ANM / t).exists() for t in AMB_TABELAS)
_CACHE_PROD = all((RAW_ANP_PROD / f).exists()
                  for f in ("producao-petroleo-m3.csv",
                            "producao-gas-natural-1000m3.csv"))
_CACHE_PRECOS = (len(list((RAW_ANP_PROD / "precos_petroleo").glob("*.xlsx")))
                 >= 24
                 and len(list((RAW_ANP_PROD / "precos_gas").glob("*.xlsx")))
                 >= 24)
_CACHE_IPCA = config.RAW_IPCA_1737.exists()
_CACHE_RFB = (config.RAW / "rfb"
              / config.RFB_XLSX_URL.rsplit("/", 1)[-1]).exists()
_PROCESSADOS = all((config.PROCESSED / f).exists()
                   for f in ("aferir_nacional.csv", "aferir_ancoras.csv"))

precisa_amb = pytest.mark.skipif(not _CACHE_AMB,
                                 reason="cache AMB/ANM ausente")
precisa_anp = pytest.mark.skipif(not (_CACHE_PROD and _CACHE_PRECOS),
                                 reason="cache ANP produção/preços ausente")
precisa_ipca = pytest.mark.skipif(not _CACHE_IPCA,
                                  reason="cache IPCA 1737 ausente")
precisa_tudo = pytest.mark.skipif(
    not (_CACHE_AMB and _CACHE_PROD and _CACHE_PRECOS and _CACHE_IPCA
         and _CACHE_RFB and _PROCESSADOS),
    reason="cenário completo exige caches AMB/ANP/IPCA/RFB e processados")


def _defl() -> float:
    from aferir.inputs.ipca_pib import deflator_para_2024
    return float(deflator_para_2024(2025).valor)


# ------------------------------------------------------------- parse dos raw
@precisa_amb
def test_amb_goldens_valor_venda():
    """Parse determinístico do AMB: totais medidos (bruta + beneficiada)."""
    vv = valor_venda_amb()
    por = vv.groupby(["substancia", "ano"])["valor_venda_rs"].sum()
    assert por[("Ferro", 2024)] == pytest.approx(149_777_347_701.74, rel=1e-9)
    assert por[("Carvão Mineral", 2025)] == pytest.approx(
        1_798_204_216.83, rel=1e-9)
    # janela completa e substâncias exatamente as do campo legal
    assert set(vv["substancia"]) == set(AMB_SUBSTANCIAS_CAMPO)
    assert set(vv["ano"]) == set(config.JANELA_RECEITA)


@precisa_anp
def test_anp_producao_goldens():
    """Produção nacional 2024 (m³) — golden extraído do raw congelado."""
    pet = producao_anp_mensal("petroleo")
    gas = producao_anp_mensal("gas_natural")
    assert len(pet) == len(gas) == 24
    assert pet[pet["ano"] == 2024]["volume_m3"].sum() == pytest.approx(
        195_397_266.852, rel=1e-9)
    assert gas[gas["ano"] == 2024]["volume_m3"].sum() == pytest.approx(
        56_069_588_384.0, rel=1e-9)


@precisa_anp
def test_anp_precos_referencia_goldens():
    """24 meses de preço por produto; média simples de jan/2024 medida."""
    for produto, preco, n in (("petroleo", 2369.9698275773194, 388),
                              ("gas_natural", 1.1756338106796116, 412)):
        prc = precos_referencia_mensais(produto)
        assert len(prc) == 24
        jan = prc[(prc["ano"] == 2024) & (prc["mes"] == 1)].iloc[0]
        assert jan["preco_medio_rs_m3"] == pytest.approx(preco, rel=1e-9)
        assert jan["n_campos"] == n
        assert (prc["preco_medio_rs_m3"] > 0).all()


# ------------------------------------------------------ componentes (R$ bi)
@precisa_amb
@precisa_ipca
def test_componentes_minerais():
    b = base_minerais_janela_bi(_defl())
    assert b["Ferro"] * ALIQ_IS_MINERAIS_TETO == pytest.approx(
        0.37858693578847546, rel=1e-9)
    assert b["Carvão Mineral"] * ALIQ_IS_MINERAIS_TETO == pytest.approx(
        0.004002445116482133, rel=1e-9)


@precisa_anp
@precisa_ipca
def test_componentes_petroleo_gas():
    b = base_petroleo_gas_janela_bi(_defl())
    assert b["petroleo"] * ALIQ_IS_MINERAIS_TETO == pytest.approx(
        1.255256103128907, rel=1e-9)
    assert b["gas_natural"] * ALIQ_IS_MINERAIS_TETO == pytest.approx(
        0.18743607190356718, rel=1e-9)


# --------------------------------------------------------- cenário completo
@precisa_tudo
def test_cenario_estrutura_e_fundamentos():
    df = sens_is_ampliado().set_index("componente")
    # perímetro legal completo — nenhum componente do art. 409, § 1º some
    for c in ("is_proxy_central", "minerais_ferro", "minerais_carvao",
              "petroleo_extracao", "gas_natural_extracao",
              "bebidas_acucaradas", "apostas_prognosticos_fantasy",
              "embarcacoes_aeronaves", "lgn", "demais_substancias_amb",
              "total_adicional_quantificado", "total_is_ampliado",
              "efeito_tau_cbs_sistema", "efeito_tau_cbs_ancora_legal"):
        assert c in df.index, c
    # toda linha com alíquota tem fundamento transcrito não vazio (art. 422)
    com_aliq = df[df["aliquota"].notna()]
    assert (com_aliq["aliquota"] == ALIQ_IS_MINERAIS_TETO).all()
    assert com_aliq["fundamento_aliquota"].str.contains(
        "art. 422", regex=False).all()
    assert com_aliq["fundamento_aliquota"].str.contains(
        "0,25%", regex=False).all()
    # colunas obrigatórias (formula e fonte incluídas)
    assert {"componente", "base_descricao", "base_rs_bi", "aliquota",
            "fundamento_aliquota", "valor_rs_bi", "periodo", "formula",
            "fonte", "status"} == set(df.reset_index().columns)


@precisa_tudo
def test_lacunas_sem_valor():
    """LACUNA/NAO_QUANTIFICADO/FORA_DO_CAMPO não carregam número inventado."""
    df = sens_is_ampliado()
    sem_num = df[df["status"].isin(
        ("LACUNA", "NAO_QUANTIFICADO", "FORA_DO_CAMPO"))]
    assert len(sem_num) >= 5
    assert sem_num["valor_rs_bi"].isna().all()
    assert sem_num["base_rs_bi"].isna().all()
    assert sem_num["aliquota"].isna().all()
    assert (sem_num["fundamento_aliquota"].str.len() > 0).all()


@precisa_tudo
def test_apostas_exclusao_justificada():
    """R2 da banca: a linha das apostas explicita a dupla fundamentação da
    exclusão (sem teto legal análogo ao art. 422, § 2º, que alcança só bens
    minerais extraídos; fonte oficial de GGR atrás de login gov.br,
    diligência F13) e não carrega número inventado."""
    df = sens_is_ampliado().set_index("componente")
    row = df.loc["apostas_prognosticos_fantasy"]
    assert row["status"] == "LACUNA"
    assert row["valor_rs_bi"] != row["valor_rs_bi"]      # NaN
    assert row["base_rs_bi"] != row["base_rs_bi"]        # NaN
    texto = " ".join(str(row[c]) for c in
                     ("base_descricao", "fundamento_aliquota", "fonte"))
    for exigido in ("EXCLUSÃO JUSTIFICADA", "art. 422", "lei ordinária",
                    "gov.br", "F13", "14.790", "art. 245",
                    "não confundir GGR"):
        assert exigido in texto, exigido


@precisa_tudo
def test_totais_consistentes():
    df = sens_is_ampliado().set_index("componente")
    adicional = df[df["status"] == "QUANTIFICADO"]["valor_rs_bi"].sum()
    assert adicional == pytest.approx(1.8252815559374318, rel=1e-9)
    assert df.loc["total_adicional_quantificado", "valor_rs_bi"] == \
        pytest.approx(adicional, rel=1e-12)
    proxy = df.loc["is_proxy_central", "valor_rs_bi"]
    assert df.loc["total_is_ampliado", "valor_rs_bi"] == \
        pytest.approx(proxy + adicional, rel=1e-12)
    # efeitos: sinal negativo e magnitude coerente com denominadores > base POF
    for c in ("efeito_tau_cbs_sistema", "efeito_tau_cbs_ancora_legal"):
        assert df.loc[c, "valor_rs_bi"] == pytest.approx(-adicional, rel=1e-12)
        assert "p.p." in df.loc[c, "base_descricao"]


@precisa_tudo
def test_csv_deterministico():
    """Duas execuções produzem bytes idênticos (determinismo)."""
    path = config.PROCESSED / "sens_is_ampliado.csv"
    sens_is_ampliado()
    b1 = path.read_bytes()
    sens_is_ampliado()
    assert path.read_bytes() == b1
