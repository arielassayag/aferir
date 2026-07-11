"""Cunha do Simples Nacional (revisão A7/E1) - denominador e numeradores.

O manuscrito afirma que ISS-Simples e ICMS-Simples estão nos numeradores e
trata a participação dos optantes na base como fronteira administrativa.
Este módulo fecha as duas pontas com dados abertos:

(a) DENOMINADOR - ω (omega_simples.csv): fração do consumo das famílias em
    campo suprida por empresas de menor porte (proxy aberta dos optantes).
    Por atividade: participação das pequenas na receita (PAC 1399 para
    comércio, faixa "Até 19"; PIA 1839 para indústria, faixas "Até 4"+"5 a
    29", corte até 29 pessoas, o mais próximo disponível; PAS, 7 tabelas,
    recorte binário total x "20 ou mais" - a parcela <20 sai por DIFERENÇA,
    limitação estrutural declarada, diligência F14), ponderada pelo consumo
    das famílias dos produtos TRU 2021 correspondentes:

        ω = Σ_a s_a · CF_a / C_campo ,

    com s_a = share das pequenas na receita da atividade a, CF_a = consumo
    das famílias dos produtos mapeados em a e C_campo = consumo das famílias
    em campo (exclui base.TRU_PRODUTOS_REMOVIDOS e o produto 64801, regime
    específico de serviços financeiros, Regulamento do IBS art. 600, §4º,
    I, 'b'). A propensão B2C (CF_a/oferta_a) é reportada por linha: a
    ponderação pelo consumo já faz o corte B2C sob a hipótese DECLARADA de
    que a participação das pequenas nas vendas às famílias iguala sua
    participação na receita total da atividade. Produtos sem pesquisa de
    porte aberta (agropecuária, saúde e ensino regular privados, utilities)
    contribuem ZERO - ω é COTA INFERIOR nessa dimensão; setores vedados aos
    optantes (energia elétrica, locação de imóveis próprios) contribuem
    zero por dispositivo literal da LC 123 (art. 17, VII e XV); produtos em
    ST/monofasia ficam fora do DAS (LC 123, art. 13, §1º, XIII, 'a').
    Corte <20 pessoas como proxy do teto de receita do Simples (R$ 4,8 mi,
    LC 123, art. 3º, II): convenção declarada, sem recorte aberto por
    faturamento nas pesquisas estruturais.

(b) NUMERADORES - QA (qa_simples_numeradores.csv): demonstra que as contas
    consolidadas usadas nos numeradores (ISSQN 1.1.1.4.51.1.0; ICMS
    1.1.1.4.50.1.0) JÁ CONTÊM a parcela do Simples: o Ementário da Receita
    (STN, 2024 e 2025) não possui natureza própria para ISS-Simples nem
    ICMS-Simples (varredura exaustiva: as únicas aberturas "Simples" são de
    contribuições federais, códigos 12xx), e o repasse do DAS chega ao ente
    titular como receita do próprio imposto (LC 123, arts. 13, VII-VIII, e
    22, I-II). A ordem de grandeza é conferida contra o XLSX aberto da RFB
    (arrecadação do Simples por esfera de destino; abertura por UF/tributo
    2024-2025 sem CSV direto - diligência F7).

(c) DOIS LADOS (desenho oficial): o Regulamento do IBS (Res. CGIBS 6/2026)
    manda a receita de referência INCLUIR a parcela do Simples (art. 599,
    §1º, I) e depois DEDUZI-LA antes do cálculo das alíquotas de referência
    (art. 600, §4º, II). r_simples_por_esfera entrega ICMS-Simples e
    ISS-Simples da janela (R$ bi 2024) e os shares dos alvos para o
    orquestrador montar o cenário que deduz numerador E denominador
    (pipeline.executa(deduz_simples_alvos=True)).

Uso: PYTHONPATH=src python3 -m aferir.simples
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd

from . import config
from .base import TRU_PRODUTOS_REMOVIDOS
from .govpurchases import media_janela_serie
from .provenance import MANIFEST, Label, Num

BI = 1e9

# ------------------------------------------------------------------ insumos
RAW_PORTE = config.RAW / "sidra_porte"
SN_XLSX = config.RAW / "rfb" / "sn_arrecadacao_ate_jan26.xlsx"
SN_XLSX_PAGINA = ("https://www8.receita.fazenda.gov.br/SimplesNacional/"
                  "ConteudoApoio/Arrecadacao/EstatisticasArrecadacao.aspx")
EMENTARIO_DIR = config.RAW / "normas" / "stn_ementario"
EMENTARIO_PAGINA = ("https://www.gov.br/tesouronacional/pt-br/contabilidade-"
                    "e-custos/federacao/ementario-da-classificacao-por-"
                    "natureza-de-receita-tabela-de-codigos")
LC123_HTML = config.RAW / "normas" / "planalto" / "lcp123.htm"
REGULAMENTO_PDF = (config.RAW / "normas" / "cgibs"
                   / "res_cgibs_6_2026_regulamento_ibs.pdf")

CSV_OMEGA = config.PROCESSED / "omega_simples.csv"
CSV_QA = config.PROCESSED / "qa_simples_numeradores.csv"

ANO_PORTE = 2023          # último ano publicado de PAC/PIA/PAS (estruturais)

# Regime específico de serviços financeiros (alíquota uniforme nacional,
# Regulamento art. 600, §4º, I, 'b'): produto TRU fora dos PESOS de ω,
# coerente com o central do pipeline (sifim='excluido').
PRODUTO_FINANCEIRO = "64801"

# ------------------------------------------------- atividades mapeadas em ω
# (nome, produtos TRU, spec do share, medida, fonte_porte)
# spec: ("pac", divisao) | ("pia", tipo) | ("pas", tabela, [(sub_total,
# sub_20mais), ...]) - PAS por diferença total menos 20+ no MESMO nível.
_PROD_TRANSF = (
    "10911", "10912", "10913", "10914", "10915", "10916", "10921", "10931",
    "10932", "10933", "10934", "10935", "10936", "10937", "11001", "12001",
    "13001", "13002", "13003", "14001", "15001", "16001", "17001", "17002",
    "18001", "20911", "20912", "20913", "20914", "20921", "20922", "20923",
    "20931", "21001", "22001", "22002", "23001", "23002", "23003", "24911",
    "24912", "24921", "24922", "25001", "26001", "26002", "26003", "26004",
    "27001", "27002", "28001", "28002", "28003", "29911", "29912", "29921",
    "30001", "31801", "31802", "33001",
)
_FONTE_PAC = (f"IBGE PAC 1399/{ANO_PORTE}, receita operacional líquida "
              "(v643), faixa 'Até 19' pessoas ocupadas")
_FONTE_PIA = (f"IBGE PIA-Empresa 1839/{ANO_PORTE}, receita líquida de "
              "vendas (v806), faixas 'Até 4' + '5 a 29' (corte até 29 "
              "pessoas, o mais próximo do <20 das demais pesquisas)")


def _fonte_pas(tabela: int) -> str:
    return (f"IBGE PAS {tabela}/{ANO_PORTE}, receita operacional líquida "
            "(v643), parcela <20 pessoas por diferença: total menos "
            "'Empresas com 20 ou mais pessoas ocupadas' (diligência F14)")


ATIVIDADES: tuple[tuple, ...] = (
    ("industria_transformacao", _PROD_TRANSF,
     ("pia", "Indústrias de transformação"), "direta", _FONTE_PIA),
    ("industria_extrativa", ("05801", "05802", "06801", "07911", "07921"),
     ("pia", "Indústrias extrativas"), "direta", _FONTE_PIA),
    ("comercio_reparacao_veiculos", ("45001",),
     ("pac", "Comércio de veículos, peças e motocicletas"), "direta",
     _FONTE_PAC),
    ("comercio_atacado_varejo_margem", ("46801",),
     ("pac", "Comércio varejista"), "direta",
     _FONTE_PAC + "; margens de comércio da TRU alocadas aos produtos "
     "(consumo das famílias do produto 46801 = 0): a cunha do varejo sobre "
     "bens fica embutida no preço ao consumidor e NÃO é separável no "
     "processado - subcaptura declarada (cota inferior)"),
    ("alojamento", ("55001",),
     ("pas", 2611, (("1.1 Serviços de alojamento",
                     "2.1 Serviços de alojamento"),)),
     "proxy_diferenca", _fonte_pas(2611)),
    ("alimentacao_fora_do_domicilio", ("56001",),
     ("pas", 2611, (("1.2 Serviços de alimentação",
                     "2.2 Serviços de alimentação"),)),
     "proxy_diferenca", _fonte_pas(2611)),
    ("cultura_recreacao_esporte", ("90801",),
     ("pas", 2611, (("1.3 Atividades culturais, recreativas e esportivas",
                     "2.3 Atividades culturais, recreativas e esportivas"),)),
     "proxy_diferenca", _fonte_pas(2611)),
    ("servicos_pessoais", ("94803",),
     ("pas", 2611, (("1.4 Serviços pessoais", "2.4 Serviços pessoais"),)),
     "proxy_diferenca", _fonte_pas(2611)),
    ("telecomunicacoes", ("61001",),
     ("pas", 2624, (("1.1 Telecomunicações", "2.1 Telecomunicações"),)),
     "proxy_diferenca", _fonte_pas(2624)),
    ("tecnologia_da_informacao", ("62801",),
     ("pas", 2624, (("1.2 Tecnologia da informação",
                     "2.2 Tecnologia da informação"),)),
     "proxy_diferenca", _fonte_pas(2624)),
    ("audiovisual", ("59801",),
     ("pas", 2624, (("1.3 Serviços audiovisuais",
                     "2.3 Serviços audiovisuais"),)),
     "proxy_diferenca", _fonte_pas(2624)),
    ("edicao_livros_jornais", ("58001",),
     ("pas", 2624, (("1.4 Edição e edição integrada à impressão",
                     "2.4 Edição e edição integrada à impressão"),)),
     "proxy_diferenca", _fonte_pas(2624)),
    ("servicos_tecnico_profissionais", ("69801", "71802", "73801"),
     ("pas", 2635, (("1.1 Serviços técnico-profissionais",
                     "2.1 Serviços técnicos-profissionais"),)),
     "proxy_diferenca", _fonte_pas(2635)),
    ("alugueis_nao_imobiliarios", ("77001",),
     ("pas", 2635, (("1.2 Aluguéis não imobiliários e gestão de ativos "
                     "intangíveis não financeiros",
                     "2.2 Aluguéis não imobiliários e gestão de ativos "
                     "intangíveis não financeiros"),)),
     "proxy_diferenca", _fonte_pas(2635)),
    ("vigilancia_seguranca", ("80001",),
     ("pas", 2635, (("1.5 Serviços de investigação, vigilância, segurança "
                     "e transporte de valores",
                     "2.5 Serviços de investigação, vigilância, segurança "
                     "e transporte de valores"),)),
     "proxy_diferenca", _fonte_pas(2635)),
    ("condominios_servicos_edificios", ("78801",),
     ("pas", 2635, (("1.6 Serviços para edificios e atividades "
                     "paisagisticas",
                     "2.6 Serviços para edificios e atividades "
                     "paisagisticas"),)),
     "proxy_diferenca", _fonte_pas(2635) + "; o produto TRU mistura "
     "condomínios (não-empresa) com serviços para edifícios - "
     "correspondência parcial declarada"),
    ("escritorio_apoio_administrativo", ("78802",),
     ("pas", 2635, (("1.7 Serviços de escritório e apoio administrativo",
                     "2.7 Serviços de escritório e apoio administrativo"),)),
     "proxy_diferenca", _fonte_pas(2635)),
    ("transporte_rodoviario_passageiros", ("49002",),
     ("pas", 2650, (("1.1.2.1 Transporte rodoviário de passageiros",
                     "2.1.2.1 Transporte rodoviário de passageiros"),)),
     "proxy_diferenca", _fonte_pas(2650) + "; produto TRU 49002 inclui "
     "metroferroviário e táxi - share do rodoviário de passageiros aplicado "
     "ao produto inteiro, correspondência parcial declarada"),
    ("transporte_rodoviario_cargas", ("49001",),
     ("pas", 2650, (("1.1.2.2 Transporte rodoviário de cargas",
                     "2.1.2.2 Transporte rodoviário de cargas"),)),
     "proxy_diferenca", _fonte_pas(2650)),
    ("transporte_aquaviario", ("50001",),
     ("pas", 2650, (("1.1.4 Transporte aquaviário",
                     "2.1.4 Transporte aquaviário"),)),
     "proxy_diferenca", _fonte_pas(2650)),
    ("transporte_aereo", ("51001",),
     ("pas", 2650, (("1.1.5 Transporte aéreo", "2.1.5 Transporte aéreo"),)),
     "proxy_diferenca", _fonte_pas(2650)),
    ("armazenamento_auxiliares_transporte", ("52801",),
     ("pas", 2650, (("1.1.6 Armazenamento e atividades auxiliares ao "
                     "transporte",
                     "2.1.6 Armazenamento e atividades auxiliares ao "
                     "transporte"),)),
     "proxy_diferenca", _fonte_pas(2650)),
    ("correio_entrega", ("52802",),
     ("pas", 2650, (("1.2 Correios e outras atividades de entrega",
                     "2.2 - Correios e outras atividades de entrega"),)),
     "proxy_diferenca", _fonte_pas(2650)),
    ("manutencao_bens_pessoais_domesticos", ("94802",),
     ("pas", 2676, (("1.2 Manutenção e reparação de equipamentos de "
                     "informática e comunicação",
                     "2.2 Manutenção e reparação de equipamentos de "
                     "informática e comunicação"),
                    ("1.3 Manutenção e reparação de objetos pessoais e "
                     "domésticos",
                     "2.3 Manutenção e reparação de objetos pessoais e "
                     "domésticos"))),
     "proxy_diferenca", _fonte_pas(2676)),
)

# ---------------------------------------- fronteiras (contribuição zero)
# (nome, produtos, medida, justificativa com fonte literal)
FRONTEIRAS: tuple[tuple, ...] = (
    ("agropecuaria_pesca_silvicultura",
     ("01911", "01912", "01913", "01914", "01915", "01916", "01917",
      "01918", "01919", "01921", "01922", "01923", "01924", "02801",
      "02802"), "fronteira_sem_porte",
     "as pesquisas estruturais de empresas do IBGE (PAC/PAS/PIA) não cobrem "
     "a agropecuária; produtor rural pessoa física fora do quadro de "
     "empresas; contribuição 0 = cota inferior declarada"),
    ("combustiveis_st_monofasia",
     ("19911", "19913", "19914", "19915"), "vedacao_legal",
     "ICMS fora do DAS nas operações 'sujeitas ao regime de substituição "
     "tributária, tributação concentrada em uma única etapa (monofásica)' "
     "envolvendo 'combustíveis e lubrificantes' (LC 123, art. 13, §1º, "
     "XIII, 'a'): a operação do optante não desloca arrecadação padrão "
     "nesses produtos; gasoálcool, etanol e GLP (19912/19921/19916) já "
     "estão fora do campo de C (base.TRU_PRODUTOS_REMOVIDOS)"),
    ("energia_eletrica_gas", ("35001",), "vedacao_legal",
     "vedado ao Simples: empresa 'que seja geradora, transmissora, "
     "distribuidora ou comercializadora de energia elétrica' (LC 123, "
     "art. 17, VII); parcela gás/utilidades sem pesquisa de porte aberta, "
     "contribuição 0 declarada"),
    ("agua_esgoto_residuos", ("36801",), "fronteira_sem_porte",
     "PAS 2695 cobre só esgoto/resíduos (CNAE 37-39); captação e "
     "distribuição de água (CNAE 36) sem pesquisa de porte aberta e "
     "parcela não separável no produto TRU; contribuição 0 = cota inferior"),
    ("construcao", ("41801", "41802", "41803"), "fronteira_sem_porte",
     "consumo das famílias nulo na TRU (edificações e obras vão para FBCF); "
     "peso zero por construção"),
    ("aluguel_efetivo_imobiliarias", ("68001",), "vedacao_legal",
     "vedado ao Simples: empresa 'que realize atividade de locação de "
     "imóveis próprios' (LC 123, art. 17, XV, redação da LC 214/2025); "
     "locadores majoritariamente pessoas físicas; a PAS 2665 mede 66,3 por "
     "cento <20 pessoas na atividade imobiliária EMPRESARIAL, não aplicado "
     "(intermediação, permitida, não separável no produto TRU)"),
    ("pesquisa_desenvolvimento", ("71801",), "fronteira_sem_porte",
     "consumo das famílias nulo na TRU; sem porte aberto"),
    ("educacao_privada_regular", ("85921",), "fronteira_sem_porte",
     "a PAS 2611 cobre apenas ensino continuado (idiomas, artes, esportes); "
     "ensino REGULAR privado sem pesquisa de porte aberta - dado "
     "administrativo (RFB por CNAE) indispensável; contribuição 0 = cota "
     "inferior declarada"),
    ("saude_privada", ("86921",), "fronteira_sem_porte",
     "nenhuma tabela da PAS cobre saúde; porte da saúde privada só em dado "
     "administrativo (RFB por CNAE) - fronteira OD/ADM; contribuição 0 = "
     "cota inferior declarada"),
    ("servicos_associativos", ("94801",), "fronteira_sem_porte",
     "organizações patronais, sindicais e associativas sem fins lucrativos: "
     "fora do universo empresarial das pesquisas estruturais e do Simples"),
    ("producao_propria_governo", ("84001", "84002", "85911", "86911"),
     "fronteira_sem_porte",
     "produção não-mercantil do governo (consumo das famílias nulo na TRU)"),
)

# ------------------------------------------ citações literais (verificadas)
# Cada trecho é CONFERIDO contra o texto compilado local antes de ir ao
# artefato (zero número ou citação sem fonte literal).
_CITA_LC123 = {
    "art13_VII": ("VII - Imposto sobre Operações Relativas à Circulação de "
                  "Mercadorias e Sobre Prestações de Serviços de Transporte "
                  "Interestadual e Intermunicipal e de Comunicação - ICMS"),
    "art13_VIII": ("VIII - Imposto sobre Serviços de Qualquer Natureza - "
                   "ISS"),
    "art13_p1_XIII_a": ("sujeitas ao regime de substituição tributária, "
                        "tributação concentrada em uma única etapa "
                        "(monofásica)"),
    "art17_VII": ("que seja geradora, transmissora, distribuidora ou "
                  "comercializadora de energia elétrica"),
    "art17_XV": "que realize atividade de locação de imóveis próprios",
    "art22_I": "Município ou Distrito Federal, do valor correspondente ao ISS",
    "art22_II": "Estado ou Distrito Federal, do valor correspondente ao ICMS",
}
_CITA_REGULAMENTO = {
    "art599_p1_I": ("A receita dos tributos referidos nos incisos I e II do "
                    "caput deste artigo será apurada de modo a incluir: "
                    "I - a receita obtida na forma da Lei Complementar "
                    "nº 123, de 14 de dezembro de 2006"),
    "art600_p4": ("Devem ser deduzidas das receitas de referência referidas "
                  "nos incisos I e II do art. 599, antes do cálculo das "
                  "alíquotas de referência, as seguintes receitas:"),
    "art600_p4_II": ("II - provenientes de operações realizadas na forma da "
                     "Lei Complementar nº 123, de 14 de dezembro de 2006"),
}


# ================================================================ leitura
def _payload(nome: str) -> list[dict]:
    path = RAW_PORTE / f"{nome}_{ANO_PORTE}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} ausente - rode PYTHONPATH=src python3 -m "
            "aferir.fetch.ibge_porte")
    MANIFEST.registra_arquivo(path)
    return json.loads(path.read_text(encoding="utf-8"))[1:]


def _v(rows: list[dict], d4: str, d5: str | None = None) -> float:
    for r in rows:
        if r.get("D4N") == d4 and (d5 is None or r.get("D5N") == d5):
            return float(r["V"])
    raise KeyError(f"categoria não encontrada no payload: {(d4, d5)}")


def _share_porte(spec: tuple) -> float:
    """Participação das pequenas na receita da atividade, conforme spec."""
    if spec[0] == "pac":
        rows = _payload("pac_1399")
        s = _v(rows, spec[1], "Até 19") / _v(rows, spec[1], "Total")
    elif spec[0] == "pia":
        rows = _payload("pia_1839")
        s = ((_v(rows, spec[1], "Até 4") + _v(rows, spec[1], "5 a 29"))
             / _v(rows, spec[1], "Total"))
    elif spec[0] == "pas":
        rows = _payload(f"pas_{spec[1]}")
        tot = sum(_v(rows, par[0]) for par in spec[2])
        g20 = sum(_v(rows, par[1]) for par in spec[2])
        if g20 > tot:
            raise ValueError(f"PAS {spec[1]}: 20+ excede o total em {spec[2]}")
        s = 1.0 - g20 / tot
    else:
        raise ValueError(f"spec de porte desconhecida: {spec[0]}")
    if not 0.0 < s < 1.0:
        raise ValueError(f"share de pequenas fora de (0,1): {s} em {spec}")
    return s


def _formula_share(spec: tuple) -> str:
    if spec[0] == "pac":
        return f"share = receita 'Até 19' / Total ({spec[1]})"
    if spec[0] == "pia":
        return f"share = receita ('Até 4' + '5 a 29') / Total ({spec[1]})"
    pares = "; ".join(p[0] for p in spec[2])
    return f"share = 1 - receita 20+/total em [{pares}]"


def _tru() -> pd.DataFrame:
    path = config.PROCESSED / "tru_2021_usos.parquet"
    MANIFEST.registra_arquivo(path)
    return pd.read_parquet(path).set_index("produto_cod")


def _texto_normalizado(bruto: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", bruto)
    return re.sub(r"(&nbsp;|\s)+", " ", txt)


def _confere_lc123() -> None:
    """Garante que toda citação da LC 123 usada nos artefatos consta do
    texto compilado local (Planalto)."""
    if not LC123_HTML.exists():
        raise FileNotFoundError(
            f"{LC123_HTML} ausente - rode PYTHONPATH=src python3 -m "
            "aferir.fetch.planalto")
    MANIFEST.registra_arquivo(LC123_HTML)
    txt = _texto_normalizado(
        LC123_HTML.read_bytes().decode("cp1252", errors="replace"))
    for chave, trecho in _CITA_LC123.items():
        if trecho not in txt:
            raise ValueError(f"citação {chave} não encontrada em lcp123.htm")


def _confere_regulamento() -> None:
    """Confere as citações do Regulamento do IBS no PDF oficial local
    (Res. CGIBS 6/2026, arts. 599-600, páginas 185-206)."""
    from pypdf import PdfReader
    if not REGULAMENTO_PDF.exists():
        raise FileNotFoundError(f"{REGULAMENTO_PDF} ausente")
    MANIFEST.registra_arquivo(REGULAMENTO_PDF)
    reader = PdfReader(REGULAMENTO_PDF)
    txt = re.sub(r"\s+", " ", " ".join(
        reader.pages[i].extract_text() or "" for i in range(185, 206)))
    for chave, trecho in _CITA_REGULAMENTO.items():
        if re.sub(r"\s+", " ", trecho) not in txt:
            raise ValueError(f"citação {chave} não encontrada no "
                             "Regulamento do IBS (pp. 186-206 do PDF)")


# ================================================================ ω (A7/E1a)
def omega_simples(grava: bool = True) -> pd.DataFrame:
    """omega_simples.csv - cunha do Simples no denominador, por atividade.

    Linha TOTAL: contribuicao_omega = ω nacional (contrato lido pelo
    orquestrador). Partição completa dos 128 produtos TRU conferida em
    tempo de construção (mapeados + fronteiras + fora do campo).
    """
    _confere_lc123()
    tru = _tru()

    mapeados = [p for _, prods, *_ in ATIVIDADES for p in prods]
    fronteira = [p for _, prods, *_ in FRONTEIRAS for p in prods]
    fora = list(TRU_PRODUTOS_REMOVIDOS) + [PRODUTO_FINANCEIRO]
    todos = mapeados + fronteira + fora
    if len(todos) != len(set(todos)):
        raise ValueError("produto TRU mapeado em mais de uma linha")
    if set(todos) != set(tru.index):
        faltam = set(tru.index) - set(todos)
        sobram = set(todos) - set(tru.index)
        raise ValueError(f"partição incompleta da TRU: faltam {sorted(faltam)}"
                         f", sobram {sorted(sobram)}")

    c_campo = float(tru.loc[~tru.index.isin(fora), "consumo_familias"].sum())
    fonte_tru = ("IBGE TRU 2021 nível 68 (tru_2021_usos.parquet); campo = "
                 "consumo das famílias exceto 68002/97001/19912/19921/19916 "
                 "(base.TRU_PRODUTOS_REMOVIDOS) e 64801 (regime específico "
                 "de serviços financeiros, Regulamento do IBS art. 600, "
                 "§4º, I, 'b')")

    linhas = []
    for nome, prods, spec, medida, fonte_porte in ATIVIDADES:
        cf = float(tru.loc[list(prods), "consumo_familias"].sum())
        oferta = float(tru.loc[list(prods),
                               "oferta_preco_consumidor"].sum())
        share = _share_porte(spec)
        peso = cf / c_campo
        linhas.append({
            "atividade": nome,
            "fonte_porte": fonte_porte,
            "medida": medida,
            "share_pequenas": share,
            "propensao_b2c": cf / oferta if oferta > 0 else 0.0,
            "peso_consumo": peso,
            "contribuicao_omega": peso * share,
            "produtos_tru": "+".join(prods),
            "formula": (f"{_formula_share(spec)}; peso_consumo = "
                        "Σ consumo_familias(produtos)/C_campo; "
                        "propensao_b2c = Σ consumo_familias/Σ oferta; "
                        "contribuicao = peso_consumo x share_pequenas"),
            "fonte": f"{fonte_porte} | {fonte_tru}",
        })
    for nome, prods, medida, motivo in FRONTEIRAS:
        cf = float(tru.loc[list(prods), "consumo_familias"].sum())
        oferta = float(tru.loc[list(prods),
                               "oferta_preco_consumidor"].sum())
        linhas.append({
            "atividade": nome,
            "fonte_porte": "sem pesquisa de porte aplicável",
            "medida": medida,
            "share_pequenas": float("nan"),
            "propensao_b2c": cf / oferta if oferta > 0 else 0.0,
            "peso_consumo": cf / c_campo,
            "contribuicao_omega": 0.0,
            "produtos_tru": "+".join(prods),
            "formula": "contribuicao = 0 (motivo na fonte)",
            "fonte": f"{motivo} | {fonte_tru}",
        })
    for prod in fora:
        motivo = ("regime específico de serviços financeiros, alíquota "
                  "uniforme nacional (Regulamento do IBS, art. 600, §4º, "
                  "I, 'b'); coerente com sifim='excluido' no central"
                  if prod == PRODUTO_FINANCEIRO else
                  "fora do campo de C no pipeline "
                  "(base.TRU_PRODUTOS_REMOVIDOS)")
        linhas.append({
            "atividade": f"fora_do_campo_{prod}",
            "fonte_porte": "nao se aplica",
            "medida": "fora_do_campo",
            "share_pequenas": float("nan"),
            "propensao_b2c": float("nan"),
            "peso_consumo": float("nan"),
            "contribuicao_omega": 0.0,
            "produtos_tru": prod,
            "formula": "produto excluído de C_campo (pesos e contribuição)",
            "fonte": f"{motivo} | {fonte_tru}",
        })

    df = pd.DataFrame(linhas)
    omega = float(df["contribuicao_omega"].sum())
    peso_em_campo = float(df.loc[df["medida"] != "fora_do_campo",
                                 "peso_consumo"].sum())
    cobertura = float(df.loc[df["medida"].isin(("direta",
                                                "proxy_diferenca")),
                             "peso_consumo"].sum())
    if abs(peso_em_campo - 1.0) > 1e-9:
        raise ValueError(f"pesos em campo não somam 1: {peso_em_campo}")
    if not 0.0 < omega < 0.5:
        raise ValueError(f"omega fora do domínio de sanidade (0, 0,5): "
                         f"{omega}")

    df.loc[len(df)] = {
        "atividade": "TOTAL",
        "fonte_porte": "PAC 1399 + PIA 1839 + PAS (7 tabelas), 2023",
        "medida": "agregado",
        "share_pequenas": float("nan"),
        "propensao_b2c": float("nan"),
        "peso_consumo": peso_em_campo,
        "contribuicao_omega": omega,
        "produtos_tru": f"{len(mapeados)} mapeados + {len(fronteira)} "
                        f"fronteira + {len(fora)} fora do campo",
        "formula": ("omega = Σ_a share_pequenas_a x peso_consumo_a; "
                    f"cobertura com porte aberto = {cobertura:.4f} do "
                    "consumo em campo; produtos sem porte aberto "
                    "contribuem 0 (COTA INFERIOR declarada)"),
        "fonte": ("IBGE PAC/PIA/PAS 2023 x TRU 2021; corte <20 pessoas "
                  "como proxy do teto de receita do Simples (LC 123, art. "
                  "3º, II) - convenção declarada; vedações setoriais: LC "
                  "123, art. 17, VII e XV; ST/monofasia: art. 13, §1º, "
                  "XIII, 'a' (texto compilado Planalto, lcp123.htm)"),
    }

    MANIFEST.registra("omega_simples_nacional", Num(
        omega,
        "Σ_a share_pequenas_a x CF_a / C_campo (atividades PAC/PIA/PAS "
        "mapeadas na TRU; sem porte aberto = 0, cota inferior)",
        "IBGE PAC 1399, PIA 1839 e PAS 2611/2624/2635/2650/2665/2676/2695 "
        "(2023) x TRU 2021 nível 68; LC 123 arts. 3º, 13, 17",
        Label.DERIVADO, "fração do consumo em campo"))
    MANIFEST.registra("omega_simples_cobertura_porte", Num(
        cobertura,
        "Σ peso_consumo das atividades com porte aberto (PAC/PIA/PAS)",
        "omega_simples.csv", Label.DERIVADO, "fração do consumo em campo"))
    if grava:
        _grava_csv(df, CSV_OMEGA)
    return df


def carrega_omega() -> float:
    """ω nacional lido de omega_simples.csv (linha TOTAL) - contrato do
    orquestrador (pipeline.executa(omega_cunha=...))."""
    df = pd.read_csv(CSV_OMEGA)
    v = df.loc[df["atividade"] == "TOTAL", "contribuicao_omega"]
    if len(v) != 1:
        raise ValueError("omega_simples.csv sem linha TOTAL única")
    return float(v.iloc[0])


# ==================================================== numeradores (A7/E1b-c)
def _sn_anual() -> pd.DataFrame:
    """Arrecadação anual do Simples por esfera de destino (R$ mi correntes;
    XLSX aberto da RFB). ESTADOS = ICMS-Simples; MUNICÍPIOS = ISS-Simples
    (repasse do produto do DAS ao ente titular, LC 123, art. 22, I-II)."""
    if not SN_XLSX.exists():
        raise FileNotFoundError(f"{SN_XLSX} ausente")
    MANIFEST.registra_arquivo(SN_XLSX)
    bruto = pd.read_excel(SN_XLSX, sheet_name="ANUAL", header=None)
    dados = bruto.iloc[7:].dropna(how="all")
    dados.columns = ["ano", "uniao", "estados", "municipios", "total"]
    dados = dados[pd.to_numeric(dados["ano"], errors="coerce").notna()]
    dados = dados.astype(float)
    dados["ano"] = dados["ano"].astype(int)
    soma = dados[["uniao", "estados", "municipios"]].sum(axis=1)
    if (abs(soma - dados["total"]) > 0.01 * dados["total"]).any():
        raise ValueError("XLSX RFB: colunas por esfera não somam o total")
    return dados.set_index("ano")


def r_simples_por_esfera(defl: float,
                         janela: tuple[int, ...] | None = None) -> dict:
    """ICMS-Simples e ISS-Simples da janela (R$ bi 2024) e shares dos alvos.

    Consumido pelo orquestrador no cenário 'dois lados' (espelho do
    Regulamento do IBS, art. 600, §4º, II: a parcela do Simples é deduzida
    das receitas de referência antes do cálculo das alíquotas): o pipeline
    multiplica alvo_E e alvo_M por (1 - share), o que subtrai exatamente
    r_simples nacional distribuindo proporcionalmente entre UFs (a RFB não
    publica a abertura por UF - diligência F7).
    """
    from .revenue import alvo_estadual_uf, alvo_municipal_uf
    sn = _sn_anual()
    r_icms = media_janela_serie(sn["estados"], defl, janela) / 1e3
    r_iss = media_janela_serie(sn["municipios"], defl, janela) / 1e3
    if not (r_icms > 0 and r_iss > 0):
        raise ValueError("r_simples não positivo")

    alvo_e = float(alvo_estadual_uf(defl, janela)["alvo_ex_comb"].sum())
    alvo_m = float(alvo_municipal_uf(defl, janela).sum())
    share_icms = r_icms / alvo_e
    share_iss = r_iss / alvo_m
    for nome, s in (("share_icms", share_icms), ("share_iss", share_iss)):
        if not 0.0 < s < 0.5:
            raise ValueError(f"{nome} fora do domínio de sanidade: {s}")

    sufixo = ("" if janela is None
              or tuple(janela) == tuple(config.JANELA_RECEITA)
              else "[janela=" + "+".join(str(a) for a in janela) + "]")
    fonte_sn = ("XLSX RFB 'SN ARRECADAÇÃO ATÉ JAN 26' (aba ANUAL, R$ mi "
                f"correntes; página {SN_XLSX_PAGINA}); repasse por esfera: "
                "LC 123, art. 22, I-II")
    MANIFEST.registra("r_simples_icms_bi" + sufixo, Num(
        r_icms, "média janela deflacionada da coluna ESTADOS (ICMS-Simples)",
        fonte_sn, Label.DERIVADO, "R$ bi 2024"))
    MANIFEST.registra("r_simples_iss_bi" + sufixo, Num(
        r_iss, "média janela deflacionada da coluna MUNICÍPIOS (ISS-Simples)",
        fonte_sn, Label.DERIVADO, "R$ bi 2024"))
    MANIFEST.registra("share_simples_icms_alvo_E" + sufixo, Num(
        share_icms, "r_simples_icms_bi / Σ alvo_ex_comb estadual",
        fonte_sn + " | revenue.alvo_estadual_uf", Label.DERIVADO, "fração"))
    MANIFEST.registra("share_simples_iss_alvo_M" + sufixo, Num(
        share_iss, "r_simples_iss_bi / Σ alvo municipal",
        fonte_sn + " | revenue.alvo_municipal_uf", Label.DERIVADO, "fração"))
    return {"r_simples_icms_bi": r_icms, "r_simples_iss_bi": r_iss,
            "share_icms": share_icms, "share_iss": share_iss}


def _ementario_varredura(ano: int) -> dict:
    """Varredura exaustiva do Ementário da Receita (STN): descrição literal
    das naturezas do ICMS/ISSQN e prova por exaustão de que não existe
    natureza própria para a parcela do Simples desses impostos."""
    path = EMENTARIO_DIR / f"ementario_receita_{ano}.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"{path} ausente")
    MANIFEST.registra_arquivo(path)
    df = pd.read_excel(path, sheet_name=f"ENR - {ano} ", header=None,
                       dtype=str)
    df.columns = ["C", "O", "E", "D1", "DD2", "D3", "T", "NR",
                  "Especificacao", "Portaria", "Descricao", "Norma",
                  "Status"]
    df = df[df["NR"].notna() & df["NR"].str.fullmatch(r"\d{8}")]

    def _desc(nr: str) -> str:
        sel = df[df["NR"] == nr]
        if len(sel) != 1:
            raise ValueError(f"Ementário {ano}: natureza {nr} não é única")
        return re.sub(r"\s+", " ", str(sel["Descricao"].iloc[0])).strip()

    mask = (df["Descricao"].fillna("").str.contains("Simples", case=False)
            | df["Especificacao"].fillna("").str.contains("Simples",
                                                          case=False))
    nrs_simples = sorted(df.loc[mask, "NR"])
    fora_12 = [n for n in nrs_simples if not n.startswith("12")]
    if fora_12:
        raise ValueError(f"Ementário {ano}: naturezas 'Simples' fora das "
                         f"contribuições federais 12xx: {fora_12}")
    return {"ano": ano, "n_naturezas": int(len(df)),
            "desc_icms": _desc("11145010"), "desc_issqn": _desc("11145110"),
            "n_simples": len(nrs_simples), "nrs_simples": nrs_simples}


def qa_numeradores(grava: bool = True) -> pd.DataFrame:
    """qa_simples_numeradores.csv - demonstração do mapeamento contábil dos
    numeradores e cenário 'dois lados' (desenho oficial)."""
    _confere_lc123()
    _confere_regulamento()
    from .revenue import deflator_2025
    defl = deflator_2025()

    em = {ano: _ementario_varredura(ano) for ano in (2024, 2025)}
    sn = _sn_anual()
    r_est = pd.read_csv(config.PROCESSED / "r_estadual.csv")
    r_mun = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    rs = r_simples_por_esfera(defl)

    fonte_ementario = ("Ementário da Receita Orçamentária (STN), edições "
                       "2024 e 2025 (data/raw/normas/stn_ementario/; página "
                       f"{EMENTARIO_PAGINA})")
    fonte_sn = ("XLSX RFB 'SN ARRECADAÇÃO ATÉ JAN 26', aba ANUAL, R$ mi "
                f"correntes (página {SN_XLSX_PAGINA})")
    linhas = []

    linhas.append({
        "item": "iss_natureza_consolidada", "ano": "2024-2025",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": f"NR 11145110 (1.1.1.4.51.1.0): "
                         f"'{em[2024]['desc_issqn']}'",
        "formula": ("a parcela do Simples do ISS entra na natureza "
                    "consolidada do próprio imposto: o DAS inclui o ISS "
                    "(LC 123, art. 13, VIII) e o produto é repassado ao "
                    "'Município ou Distrito Federal, do valor "
                    "correspondente ao ISS' (art. 22, I); o Ementário não "
                    "possui natureza própria para ISS-Simples (varredura "
                    "exaustiva na linha ementario_varredura); logo a conta "
                    "DCA 1.1.1.4.51.1.0 usada em r_municipal_uf.csv JÁ "
                    "CONTÉM o ISS-Simples"),
        "fonte": fonte_ementario + "; LC 123/2006 arts. 13 e 22 (texto "
                 "compilado Planalto, lcp123.htm); Regulamento do IBS, "
                 "art. 599, §1º, I",
    })
    linhas.append({
        "item": "icms_natureza_consolidada", "ano": "2024-2025",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": f"NR 11145010 (1.1.1.4.50.1.0): "
                         f"'{em[2024]['desc_icms']}'",
        "formula": ("idem para o ICMS: DAS inclui o ICMS (LC 123, art. 13, "
                    "VII), repasse ao 'Estado ou Distrito Federal, do valor "
                    "correspondente ao ICMS' (art. 22, II); sem natureza "
                    "própria de ICMS-Simples no Ementário; a rubrica RREO "
                    "usada em r_estadual.csv triangula com a DCA "
                    "1.1.1.4.50.1.0 + 1.1.1.4.50.2.0 (identidade 54/54) e, "
                    "portanto, JÁ CONTÉM o ICMS-Simples"),
        "fonte": fonte_ementario + "; LC 123/2006 arts. 13 e 22; "
                 "r_estadual.csv (triangulação RREO x DCA)",
    })
    linhas.append({
        "item": "ementario_varredura", "ano": "2024-2025",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": (f"2024: {em[2024]['n_simples']} naturezas citam "
                          f"'Simples' em {em[2024]['n_naturezas']} do "
                          f"Ementário; 2025: {em[2025]['n_simples']} em "
                          f"{em[2025]['n_naturezas']}; TODAS são "
                          "contribuições federais (códigos 12xx: Cofins, "
                          "PIS/Pasep, CSLL, CPP); nenhuma abre ICMS-Simples "
                          "ou ISS-Simples"),
        "formula": ("prova por exaustão: sem natureza própria, o repasse do "
                    "DAS só pode estar nas naturezas consolidadas "
                    "1.1.1.4.50.1.0 (ICMS) e 1.1.1.4.51.1.0 (ISSQN)"),
        "fonte": fonte_ementario,
    })

    for ano in (2024, 2025):
        icms_uf = float(r_est.loc[r_est["ano"] == ano, "icms_bruto"].sum())
        sn_icms = float(sn.loc[ano, "estados"]) / 1e3
        linhas.append({
            "item": "icms_simples_vs_numerador", "ano": str(ano),
            "valor_rs_bi": sn_icms,
            "referencia_rs_bi": icms_uf / BI,
            "share_pct": 100.0 * sn_icms / (icms_uf / BI),
            "texto_literal": "",
            "formula": ("ICMS-Simples (coluna ESTADOS do XLSX RFB) vs Σ_uf "
                        "icms_bruto do numerador (r_estadual.csv), R$ "
                        "correntes do ano; ordem de grandeza compatível com "
                        "parcela contida (2,9 a 3,0 por cento do ICMS)"),
            "fonte": fonte_sn + "; r_estadual.csv (SICONFI RREO Anexo 03)",
        })
        iss_uf = float(r_mun.loc[r_mun["ano"] == ano, "iss_liquida"].sum()
                       + r_mun.loc[r_mun["ano"] == ano,
                                   "iss_imputado"].sum())
        sn_iss = float(sn.loc[ano, "municipios"]) / 1e3
        linhas.append({
            "item": "iss_simples_vs_numerador", "ano": str(ano),
            "valor_rs_bi": sn_iss,
            "referencia_rs_bi": iss_uf / BI,
            "share_pct": 100.0 * sn_iss / (iss_uf / BI),
            "texto_literal": "",
            "formula": ("ISS-Simples (coluna MUNICÍPIOS do XLSX RFB) vs "
                        "Σ_uf (iss_liquida + iss_imputado) do numerador "
                        "(r_municipal_uf.csv, municípios + DF), R$ "
                        "correntes do ano; ordem de grandeza compatível "
                        "com parcela contida (15 por cento do ISS)"),
            "fonte": fonte_sn + "; r_municipal_uf.csv (SICONFI DCA, conta "
                     "1.1.1.4.51.1.0; DF via RREO)",
        })

    linhas.append({
        "item": "r_simples_icms_janela", "ano": "2024-2025",
        "valor_rs_bi": rs["r_simples_icms_bi"],
        "referencia_rs_bi": rs["r_simples_icms_bi"] / rs["share_icms"],
        "share_pct": 100.0 * rs["share_icms"],
        "texto_literal": "",
        "formula": ("média janela deflacionada (v2024 + v2025 x defl)/2 da "
                    "coluna ESTADOS; referência = Σ alvo_ex_comb estadual "
                    "(R$ bi 2024); share aplicável ao cenário dois lados"),
        "fonte": fonte_sn + "; revenue.alvo_estadual_uf",
    })
    linhas.append({
        "item": "r_simples_iss_janela", "ano": "2024-2025",
        "valor_rs_bi": rs["r_simples_iss_bi"],
        "referencia_rs_bi": rs["r_simples_iss_bi"] / rs["share_iss"],
        "share_pct": 100.0 * rs["share_iss"],
        "texto_literal": "",
        "formula": ("média janela deflacionada da coluna MUNICÍPIOS; "
                    "referência = Σ alvo municipal (R$ bi 2024); share "
                    "aplicável ao cenário dois lados"),
        "fonte": fonte_sn + "; revenue.alvo_municipal_uf",
    })
    linhas.append({
        "item": "lacuna_abertura_uf_tributo", "ano": "2024-2025",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": "",
        "formula": ("a RFB publica em CSV/XLSX direto apenas a repartição "
                    "nacional UNIÃO x ESTADOS x MUNICÍPIOS; os quadros "
                    "ICMS/ISS por UF 2024-2025 estão em app dinâmico sem "
                    "arquivo direto - o cenário dois lados distribui a "
                    "dedução proporcionalmente aos alvos por UF (convenção "
                    "declarada até a resposta da diligência)"),
        "fonte": ("diligência F7 (metadata/diligencias_fontes.csv): pedido "
                  "de abertura registrado; fronteira OD/ADM"),
    })
    linhas.append({
        "item": "desenho_oficial_dois_lados", "ano": "vigente",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": ("art. 599, §1º: '" + _CITA_REGULAMENTO["art599_p1_I"]
                          + "'; art. 600, §4º: '"
                          + _CITA_REGULAMENTO["art600_p4"] + " (...) "
                          + _CITA_REGULAMENTO["art600_p4_II"] + "'"),
        "formula": ("o desenho oficial INCLUI a parcela do Simples na "
                    "receita de referência e a DEDUZ antes do cálculo das "
                    "alíquotas de referência; o espelho no pipeline é "
                    "executa(deduz_simples_alvos=True), combinado com a "
                    "cunha ω no denominador (omega_simples.csv)"),
        "fonte": ("Regulamento do IBS, Res. CGIBS 6/2026, arts. 599 e 600 "
                  "(PDF oficial em data/raw/normas/cgibs/, citações "
                  "conferidas por extração de texto)"),
    })
    linhas.append({
        "item": "st_monofasia_fora_do_das", "ano": "vigente",
        "valor_rs_bi": float("nan"), "referencia_rs_bi": float("nan"),
        "share_pct": float("nan"),
        "texto_literal": ("LC 123, art. 13, §1º, XIII, 'a': operações '"
                          + _CITA_LC123["art13_p1_XIII_a"]
                          + "' (combustíveis, energia, cigarros, bebidas "
                          "etc.) ficam FORA do DAS"),
        "formula": ("sem dupla contagem entre a dedução ad rem de "
                    "combustíveis (alvo ex-comb) e r_simples_icms: o ICMS "
                    "de combustíveis não transita pelo DAS"),
        "fonte": "LC 123/2006 (texto compilado Planalto, lcp123.htm)",
    })

    df = pd.DataFrame(linhas)
    if grava:
        _grava_csv(df, CSV_QA)
    return df


# ================================================================ IO
def _grava_csv(df: pd.DataFrame, path: Path) -> None:
    """Escrita atômica e determinística (tmp + os.replace)."""
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


if __name__ == "__main__":
    om = omega_simples(grava=True)
    qa = qa_numeradores(grava=True)
    tot = om[om["atividade"] == "TOTAL"].iloc[0]
    print(f"omega nacional = {tot['contribuicao_omega']:.5f} "
          f"(cobertura com porte aberto no consumo em campo: ver formula)")
    print(om[om["medida"].isin(("direta", "proxy_diferenca"))]
          [["atividade", "share_pequenas", "peso_consumo",
            "contribuicao_omega"]].to_string(index=False))
    print()
    print(qa[["item", "ano", "valor_rs_bi", "referencia_rs_bi",
              "share_pct"]].to_string(index=False))
    print(f"\nartefatos: {CSV_OMEGA}\n           {CSV_QA}")
