"""Configuração única do AFERIR: caminhos, janelas legais, constantes.

Toda constante numérica carregada aqui declara fonte. Nenhum outro módulo
pode hardcodar caminho, ano ou parâmetro — auditabilidade exige um só lugar.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- caminhos
V2_ROOT = Path(__file__).resolve().parents[2]          # ~/IBS/v2
RAW = V2_ROOT / "data" / "raw"
PROCESSED = V2_ROOT / "data" / "processed"
INPUTS = V2_ROOT / "data" / "inputs"
OUTPUTS = V2_ROOT / "data" / "outputs"
FIGURES = OUTPUTS / "figures"

SEED = 42

# ---------------------------------------------------------------- janelas legais
# LC 214/2025, arts. 349-369 (Seção "Da Fixação das Alíquotas de Referência"),
# com a redação dada pela LC 227/2026 aos arts. 361-365.
ANCORA_UNIAO = list(range(2012, 2022))   # art. 353: média receita-ref União/PIB 2012-2021
ANCORA_SUBNACIONAL = [2024, 2025, 2026]  # arts. 361-365 (red. LC 227): média 2024-2026
JANELA_RECEITA = [2024, 2025]            # 2026 indisponível em jul/2026 — declarado
ANO_PRECOS = 2024                        # todos os fluxos expressos em R$ de 2024

# ---------------------------------------------------------------- esferas
ESFERAS = ("uniao", "estadual", "municipal")

# Receita de referência por esfera — LC 214, art. 350 (incisos I a III)
RECEITA_REFERENCIA = {
    "uniao": "PIS + Cofins (CF 195, I, 'b' e IV) + IPI + IOF-seguros",
    "estadual": "ICMS bruto + fundos estaduais condicionais (média 2021-2023)",
    "municipal": "ISS (inclui Simples, multas e dívida ativa do imposto)",
}

# ---------------------------------------------------------------- SICONFI
SICONFI_API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
# Ementário da receita (DCA Anexo I-C): quebra 2021→2022
CONTA_ISS_POS2022 = "1.1.1.4.51.1.0"     # ISS a partir do exercício 2022
CONTA_ISS_ATE2021 = "1.1.1.8.02.3.0"     # ISS até 2021 (não usado na janela legal)
CONTA_COTA_ICMS = "1.7.2.1.50.0.0"       # cota-parte ICMS (diagnóstico federativo)
CONTA_ICMS_POS2022 = "1.1.1.4.50.1.0"    # ICMS (principal+multas+DA consolidados)
CONTA_ICMS_ATE2021 = "1.1.1.8.02.1.0"    # ICMS no ementário até 2021
CONTA_FECP_POS2022 = "1.1.1.4.50.2.0"    # Adicional ICMS - Fundo Est. Combate à Pobreza
CONTA_FECP_ATE2021 = "1.1.1.8.02.2.0"    # idem, ementário até 2021

# ---------------------------------------------------------------- dados brutos (data/raw)
# Arquivos de FONTES ABERTAS baixados pelos fetchers deste pacote (`make fetch`)
# em endpoints públicos, sem credencial. data/raw NÃO é versionado: apenas os
# _meta/_manifest.json (sha256 por arquivo) acompanham o repositório, para que
# o replicador audite a coleta byte a byte. NENHUM caminho fora da raiz do repo.
RAW_TRU_ZIP = RAW / "sidra" / "nivel_68_2010_2021_xls.zip"
RAW_IPCA_1737 = RAW / "sidra" / "ipca_1737.parquet"
RAW_RREO_ICMS_CSV = RAW / "siconfi_rreo" / "icms_uf_2024_2025.csv"
RAW_DCA_ESTADUAL_DIR = RAW / "siconfi_estadual"         # dca_{UF}_{ano}.parquet
RAW_DCA_MUN_DIR = RAW / "siconfi_municipal_dca"         # dca_mun_{cod}_{ano}.parquet
RAW_ANP_CSV = RAW / "anp" / "vendas-combustiveis-m3-1990-2025.csv"
RAW_ANP_PRECOS_XLSX = RAW / "anp_precos" / "mensal-estados-desde-jan2013.xlsx"
RAW_POF_DIR = RAW / "pof"                               # dados_raw/*.txt + doc/*.xls
# CONFAZ, Boletim de Arrecadação dos Tributos Estaduais — arquivo obtido
# MANUALMENTE pela interface do dados.gov.br (fetch-manual, §10.4): o painel
# não expõe export estável e a API CKAN exige autenticação (F1). Vintage
# congelada com pendências declaradas; sha256 no sidecar ._meta.json.
RAW_CONFAZ_XLSX = RAW / "confaz" / "20260623_dados-abertos.xlsx"
CONFAZ_ABA_CNAE = "arrecadação por CNAE"                # 2024-01 a 2026-06
CONFAZ_EXTRACAO = "23/06/2026"                          # data literal do cabeçalho

# Insumos CURADOS versionados em data/inputs (não-fetcháveis por natureza):
# tabelas legais transcritas com ato citado linha a linha e convenções v1
# vendoradas — cada arquivo declara fórmula e fonte por linha/coluna.
FBCF_V1_CSV = INPUTS / "fbcf_v1_uf.csv"                 # convenção v1 (PIA-VTI × TRU)
AMOSTRA_DCA_MUN_CSV = INPUTS / "amostra_dca_municipal.csv"  # composição pinada 2019-2023

# ---------------------------------------------------------------- TRU 2021 (nível 68)
# TRU 2021 = última edição DETALHADA (128 produtos × 68 atividades); a série
# detalhada foi suspensa na mudança de ano-base — NÃO migrar para 2023.
TRU_URL = ("https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/"
           "9052-sistema-de-contas-nacionais-brasil.html — Tabelas de Recursos e "
           "Usos, nível 68, 2010-2021 (nivel_68_2010_2021_xls.zip)")
TRU_ANO = 2021
# Produtos de produção própria não-mercantil do governo (excluídos do mix de
# COMPRAS públicas): adm. pública, previdência/assistência, educação e saúde públicas.
TRU_PRODUTOS_PRODUCAO_PROPRIA_GOV = ("84001", "84002", "85911", "86911")
# Atividades do governo geral na TRU (colunas do consumo intermediário, tab2/CI):
# mix de absorção usado no redutor iso-carga do art. 370 (FORK F8).
TRU_ATIVIDADES_GOV = ("8400", "8591", "8691")

# ---------------------------------------------------------------- fundos estaduais
# LC 214/2025, art. 350, II, 'b' e §2º; NT SERT/MF de 01/07/2024, p. 4:
# três fundos elegíveis (FETHAB-MT, FUNDERSUL-MS, FUNDEINFRA-GO), somando
# R$ 3,5 bi (FETHAB+FUNDERSUL no ano-base 2018; FUNDEINFRA deflacionado IPCA
# em 2023). A NT NÃO publica a decomposição por fundo — fronteira OD/ADM.
NT_SERT_JUL2024_URL = (
    "https://www.gov.br/fazenda/pt-br/acesso-a-informacao/acoes-e-programas/"
    "reforma-tributaria/regulamentacao-da-reforma-tributaria/"
    "lei-geral-do-ibs-da-cbs-e-do-imposto-seletivo/notas/"
    "nota-tecnica-aliquotas_2024-07-01_sertmf-1.pdf")
NT_SERT_JUL2024_PAGINA_FUNDOS = 4
FUNDOS_ESTADUAIS_TOTAL_RS = 3.5e9        # R$ 3,5 bi — NT SERT jul/2024, p. 4
FUNDOS_ESTADUAIS = {                     # UF -> fundo identificado na NT (p. 4)
    "MT": "FETHAB",
    "MS": "FUNDERSUL",
    "GO": "FUNDEINFRA",
}
FUNDOS_JANELA_BASE = (2021, 2022, 2023)  # art. 350, §2º, II: média 2021-2023

# ---------------------------------------------------------------- combustíveis
# Densidade do GLP: usar GLP_DENSIDADE_KG_M3_ANP (0,552 t/m³, fator oficial
# ANP) em inputs/combustiveis.py — a convenção v1 (550) foi substituída na
# revisão A2 junto com a tabela mensal de vigências (icms_adrem_vigencias.csv).
# Produto CONFAZ (icms_adrem_vigencias.csv) → produto ANP (vendas m³, normalizado)
ADREM_PRODUTO_ANP = {
    "GASOLINA_EAC": "GASOLINA C",
    "DIESEL_B100": "OLEO DIESEL",
    "GLP_GLGN": "GLP",
}
# Etanol hidratado combustível (EHC): monofásico na LC 214 (art. 172, VI),
# mas FORA dos convênios ad rem da LC 192/2022 (199/2022 e 15/2023 cobrem
# gasolina+EAC, diesel+B100 e GLP/GLGN) — hoje recolhe ICMS AD VALOREM.
# Dedução própria no alvo estadual: volumes ANP × preço médio ao consumidor
# (ANP-SLP mensal por UF) × alíquota ad valorem vigente por UF
# (inputs/deducao_etanol.py; tabela de vigências curada em data/inputs/).
ETANOL_PRODUTO_ANP = "ETANOL HIDRATADO"
ETANOL_VIGENCIAS_CSV = INPUTS / "icms_etanol_hidratado_vigencias.csv"

# ------------------------------------------------- receita federal (União, CBS)
# Rota primária: XLSX "Arrecadação das receitas federais 1994 a 2025" (RFB,
# gov.br — dado aberto, R$ milhões correntes, uma aba por ano). A série NÃO
# explicita a convenção de dedução de restituições/compensações (Tema 69):
# tratada como "bruta-RFB" e DECLARADA em ancora_uniao.csv. A convenção
# LÍQUIDA por tributo existe em dado aberto no RTN/STN (ver RTN_XLSX_URL) e
# é a CENTRAL da âncora; a bruta-RFB vira sensibilidade.
RFB_XLSX_URL = (
    "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/"
    "receitadata/arrecadacao/serie-historica/"
    "arrecadacao-das-receitas-federais-1994-a-2025.xlsx")
# Rótulos EXATOS das linhas no XLSX (verificados estáveis em 2012-2025).
# PIS não é separável do Pasep na série aberta — e não precisa: o art. 350, I,
# 'a' da LC 214 referencia a "contribuição para o PIS/Pasep" por inteiro.
# As três linhas I.P.I-* alimentam o proxy iso-carga do Imposto Seletivo
# (LC 214, art. 409 e Anexo XVII: fumo, bebidas e veículos estão no campo
# do IS) — ver revenue.is_estimado_bi.
RFB_XLSX_ROTULOS = {
    "pis_pasep": "CONTRIBUIÇÃO PARA O PIS/PASEP",
    "cofins": "COFINS - CONTRIB. P/ A SEGURIDADE SOCIAL",
    "ipi": "I.P.I-TOTAL",
    "iof_total": "IOF - I. S/ OPERAÇÕES FINANCEIRAS",
    "ipi_fumo": "I.P.I-FUMO",
    "ipi_bebidas": "I.P.I-BEBIDAS",
    "ipi_automoveis": "I.P.I-AUTOMÓVEIS",
}

# ---------------------------------------------- RTN/STN (âncora LÍQUIDA, Tema 69)
# Resultado do Tesouro Nacional — Série Histórica (Tesouro Transparente/CKAN,
# dado aberto máquina-legível). Tabela 2.2 (anual, R$ mi correntes) publica a
# receita POR TRIBUTO no conceito caixa ("ingresso efetivo na Conta Única",
# nota 1/ da tabela), LÍQUIDA de restituições: o dicionário de metodologia
# (recurso "Dicionário de Conceitos e Metodologia de Cálculo" do mesmo
# dataset) define RECEITA LÍQUIDA (III = I − II) como "receita bruta ...
# deduzidas as restituições, os incentivos fiscais e as transferências
# constitucionais", sendo II apenas transferências e os incentivos a linha
# 1.2 — logo as linhas 1.1.xx de tributos já são líquidas de restituições.
# É a série aberta que materializa a convenção oficial (RTN) do Tema 69 e
# vira a âncora CENTRAL do art. 353; a bruta-RFB fica como sensibilidade.
# Replicabilidade: o nome do arquivo carrega a vintage (mai26); o endpoint
# CKAN /download serve a vintage corrente; sha256 congelado no _meta.json
# (vintage desta execução: mai/2026, last_modified 2026-06-29).
RTN_XLSX_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "ab56485b-9c40-4efb-8563-9ce3e1973c4b/resource/"
    "527ccdb1-3059-42f3-bf23-b5e3ab4c6dc6/download/seriehistoricamai26.xlsx")
RTN_ABA_ANUAL = "2.2"              # Tabela 2.2 — anual, R$ mi correntes
# Prefixos dos rótulos das linhas por tributo na Tabela 2.2 (coluna A).
# "1.1.02 " com espaço ao final evita casar as sublinhas 1.1.02.x do IPI.
RTN_ROTULOS = {
    "ipi": "1.1.02 ",
    "iof_total": "1.1.04",
    "cofins": "1.1.05",
    "pis_pasep": "1.1.06",
}
# Convenção da âncora federal do CENTRAL (a alternativa vira sensibilidade
# em aferir_nacional.csv, coluna ancora_federal): "liquida_rtn" | "bruta_rfb".
ANCORA_FEDERAL_CENTRAL = "liquida_rtn"
# Fallback/validação cruzada: IPEADATA OData4 (séries mensais SRF em R$ mi;
# anualizar por SOMA; Cofins 2021 = 286.499,3 R$ mi — golden number).
IPEADATA_ODATA_URL = (
    "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{sercodigo}')")
IPEADATA_SERCODIGOS = {
    "pis_pasep": "SRF12_PIS12",
    "cofins": "SRF12_COFINS12",
    "ipi": "SRF12_IPI12",
    "iof_total": "SRF12_IOF12",
}

# IOF-Seguros (art. 350, I, 'c'): NÃO há decomposição aberta máquina-legível do
# IOF por modalidade — verificado em 2026-07-10 no XLSX RFB (linha única), no
# Portal da Transparência (naturezas: só IOF-OURO × IOF-DEMAIS OPERAÇÕES) e na
# Análise da Arrecadação dez/2025 (sem quadro por modalidade). O cálculo oficial
# usa "arrecadação observada do IOF-Seguros" (metodologia TCU/RFB, p. 6) = dado
# administrativo → fronteira OD/ADM (C3). Rota aberta: razão IOF-seguros/IOF-total
# de quadro publicado (NT SERT jul/2024, p. 3: R$ 5,4 bi) aplicada à série aberta.
IOF_SEGUROS_META_SERT_RS_MI = 5_400.0    # R$ 5,4 bi — NT SERT jul/2024, p. 3
NT_SERT_JUL2024_PAGINA_IOF_SEGUROS = 3
# Convenção (declarada): denominador = IOF-total do último exercício ENCERRADO
# antes da NT (2023); razão mantida constante em 2012-2021 e 2024-2025.
RAZAO_IOF_SEGUROS_ANO_DENOMINADOR = 2023

# PIB nominal anual (SIDRA 1846, SCN Trimestral, PIB pm a preços correntes,
# soma dos 4 trimestres; única fonte aberta tempestiva para 2024-2025 — as
# Contas Regionais/anuais param antes do biênio; validação: 2021 = 9.012.142
# R$ mi). Rota herdada do v1 (validada contra SIDRA 5938 em 2022-2023).
SIDRA_PIB_1846_URL = ("https://apisidra.ibge.gov.br/values/t/1846/n1/all/"
                      "v/585/p/all/c11255/90707?formato=json")

# Metodologia oficial da CBS (TCU/RFB) e PLDO 2027 — fontes dos insumos do
# alvo do art. 353 (IS e IPI residual) transcritos em data/inputs/.
TCU_METODOLOGIA_CBS_URL = (
    "https://sites.tcu.gov.br/recursos/reforma-tributaria/"
    "Metodologia%20CBS%20Aliquota%20de%20Referencia%20e%20Redutor.pdf")
PLDO2027_ANEXO_IV2_URL = (
    "https://www.gov.br/planejamento/pt-br/assuntos/orcamento/orcamentos-anuais/"
    "2027/pldo/anexo-iv-02-metas-fiscais.pdf")

# ---------------------------------------------------------------- conformidade
# Corredor oficial de hiato de conformidade (NT SERT/MF jul/2024: 10% factível,
# 15% conservador — âncora Hungria 2018-19); ponto FMI WP/2025/266 = 12,5%.
GAP_CONFORMIDADE = {"factivel": 0.10, "central": 0.125, "conservador": 0.15}

# Split payment: cenários discretos (fora do central — ver DESIGN §2.2, F1)
PSI_CENARIOS = (0.0, 0.30, 1.0)

# ---------------------------------------------------------------- cashback (art. 118)
CASHBACK_IBS_UNIFORME = 0.20      # IBS: 20% uniforme (estadual e municipal)
CASHBACK_CBS_PISO = 1.00          # CBS: 100% em GLP/energia/água-esgoto/gás/telecom
CASHBACK_CBS_DEMAIS = 0.20        # CBS: 20% nas demais aquisições

# ------------------------------------------- compras governamentais (art. 473)
# G_s^aq = naturezas de AQUISIÇÃO apenas (DESIGN §2.1): material de consumo,
# serviços de terceiros PF e PJ. Folha fora do campo (LC 214, art. 4º).
# Modalidade 90 (aplicações diretas); intra-orçamentárias (3.3.91) excluídas.
DCA_ANEXO_DESPESA = "DCA-Anexo I-D"       # despesa por natureza (SICONFI DCA)
# Perímetros de G (revisão A5) vivem em inputs/gov_aquisicoes.py
# (NATUREZAS_CUSTEIO_MIN/AMPLIADO, NATUREZAS_CAPITAL); estágios da DCA:
ESTAGIO_G473 = "Despesas Empenhadas"      # convenção: total empenhado no exercício
ESTAGIO_G473_SENSIBILIDADE = "Despesas Liquidadas"
COD_IBGE_UNIAO = 1                        # id_ente da União na API SICONFI
COD_IBGE_BRASILIA = 5300108               # DF: G integralmente na esfera estadual
                                          # (DCA única do GDF; art. 349, II, 'c')
# Fallback municipal (FINBRA em lote indisponível — JSF sob hCaptcha em 07/2026):
# amostra = capitais + G473_AMOSTRA_TOP_N maiores municípios por população;
# extrapolação pós-estratificada por per-capita de estrato populacional
# (estratos medidos na subamostra aleatória v1 de 2023, dca_mun_*, hash registrado).
G473_AMOSTRA_TOP_N = 200
G473_ESTRATOS_POP = (0, 5_000, 10_000, 20_000, 50_000, 100_000, float("inf"))
G473_ANO_ESTRATOS = 2023                  # último ano da subamostra municipal v1

# ---------------------------------------------------------------- travas
TRAVA_SOMA_REFERENCIAS = 0.265    # art. 475 §11: gatilho de PLP redutor (soma 2033)

# ------------------------------------- distribuição do IBS em 2033 (transição)
# Cadeia legal (texto literal verificado em References/legal/ do v1):
# EC 132/2023, ADCT arts. 131-132; LC 227/2026, arts. 104-117; CF art. 158, IV
# ('a' = cota-parte do ICMS legado; 'b' = cota-parte municipal do IBS
# estadual); LC 227/2026, art. 128 (critérios da cota-parte do IBS).
RETENCAO_2033 = 0.90              # LC 227 art. 109, II; ADCT art. 131, §1º, II
SEGURO_RECEITA_PCT = 0.05         # LC 227 art. 110, I: 5% do produto APÓS a
                                  # retenção do art. 109 (⇒ 0,5% do produto em 2033)
COTA_PARTE_MUNICIPAL = 0.25       # CF art. 158, IV
SEGURO_CAP_PER_CAPITA = 3.0       # LC 227 art. 117, §§3º-6º: receita média
                                  # ajustada ≤ 3× a média per capita da esfera
# LC 227 art. 115, §2º, I: valores anuais de 2019 a 2026. Anos efetivamente
# DISPONÍVEIS nos dados abertos em jul/2026 (declarado, mesmo espírito de
# JANELA_RECEITA): estados DCA 2019-2025 (fetch.siconfi_estadual); municípios DCA 2019-2023
# (subamostra aleatória v1, 2.844 entes, 8 UFs ausentes) + 2024-2025 (universo).
JANELA_RECEITA_MEDIA_LEGAL = list(range(2019, 2027))
JANELA_RECEITA_MEDIA = list(range(2019, 2026))

# ------------------------------------------- municípios-sonda (invariante I14)
# Golden numbers verificados manualmente AO CENTAVO contra fonte independente
# (DESIGN §2.8, I14): ISS bruto de São Paulo capital na DCA Anexo I-C 2024
# (triangulado com a MSC/parecer da revisão) e ISS do DF no RREO Anexo 03
# (total 12 meses; Brasília não entra no painel DCA municipal — RREO-DF).
SONDA_SP_CAPITAL_COD_IBGE = 3550308
SONDA_SP_CAPITAL_2024_ISS_BRUTA = 35_836_255_499.67   # R$, DCA I-C 2024
SONDA_DF_ISS_RREO = {                                 # R$, RREO Anexo 03
    2024: 3_472_401_821.22,
    2025: 3_862_618_982.16,
}

# ---------------------------------------------------------------- manuscrito
# Fontes de conteúdo (Markdown) e saída DOCX do gerador (aferir.manuscript).
ARTIGO = V2_ROOT / "docs" / "artigo"            # NN_secao.md (ordem lexicográfica)
ARTIGO_EXEMPLO = ARTIGO / "exemplo"             # amostra que cobre TODA a sintaxe
REFERENCIAS_BIB = ARTIGO / "referencias.bib"    # bibliografia (ABNT no gerador)
MANUSCRIPT_DOCX = OUTPUTS / "MANUSCRIPT.docx"   # entregável único (DESIGN §4)

# Edital do 31º Prêmio Tesouro Nacional 2026 (itens 5.10 e 8.1.x):
EDITAL_FONTE = "Arial"                 # 8.1.3 — Arial em tema, estilos e runs
EDITAL_FONTE_PT = 12                   # corpo 12 pt
EDITAL_ENTRELINHAS = 1.5               # w:line = 360 (um e meio)
EDITAL_MARGEM_SUP_ESQ_CM = 3.0         # margens superior e esquerda
EDITAL_MARGEM_INF_DIR_CM = 2.0         # margens inferior e direita
EDITAL_RESUMO_MAX_PALAVRAS = 150       # 8.1.6 — Resumo E Abstract
EDITAL_MAX_PALAVRAS_CHAVE = 5          # até 5 palavras-chave (PT e EN)
EDITAL_N_JEL = 3                       # 3 códigos JEL
EDITAL_CITACAO_RECUO_CM = 4.0          # citação direta >3 linhas (NBR 10520)
EDITAL_CITACAO_FONTE_PT = 10
FIGURA_LARGURA_CM = 15.5               # contrato [[FIG:...]]
TABELA_FONTE_PT = 9                    # convenção v1 (gate de 20 pp)

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
]
