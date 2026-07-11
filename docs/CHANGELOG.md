# CHANGELOG — AFERIR

Formato: histórico por data, com hash curto dos commits do git local
(`git -C ~/IBS/v2 log --oneline`). O v2 nasceu como reconstrução completa do
pipeline v1 (`~/IBS/Code`, intacto e congelado), ampliando o escopo de uma
alíquota estadual para o sistema tri-esfera CBS + IBS-E + IBS-M.

## 2026-07-13 — segunda rodada de revisão por parecer (R1-R8 + auditoria de nível)

Segunda passada de banca sobre a versão revisada. Central da construção B de
32,80 para **32,53 p.p.** (CBS 13,53 + IBS-E 16,15 + IBS-M 2,85); trava
λ = 0,710, custo R$ 241 bi/ano.

- **Etanol hidratado (achado da auditoria de nível):** o EHC é monofásico na
  LC 214 (art. 172, VI) e a base já o excluía, mas o ICMS ad valorem que ele
  recolhe hoje (fora dos convênios ad rem) permanecia no alvo estadual. Nova
  dedução simétrica (~R$ 11,2 bi/ano) com tabela curada
  `data/inputs/icms_etanol_hidratado_vigencias.csv` (27 UFs, ato citado linha
  a linha: 17 UFs com alíquota específica de EHC, 10 na modal; trocas em
  MG/MA/RN/PI datadas por ato dentro da janela), fetcher `fetch.anp_precos`
  (preços de revenda ANP-SLP) e módulo `inputs.deducao_etanol`. Efeito
  −0,25 p.p. em τ_E. Autocontradição da METODOLOGIA corrigida.
- **Auditoria adversarial do nível (R do autor):** seis verificadores céticos,
  um por alavanca, com refutação cruzada. Cinco adequadas com validação externa
  (SIFIM imputado coberto pelo FISIM-PF calculado das séries do BCB; âncoras de
  consumo reproduzidas em precisão de máquina contra o bruto do IBGE e a API
  viva). Registro citável em `metadata/auditoria_nivel_2026_07_13.md`.
- **CONFAZ×RREO executado (R8):** boletim de arrecadação do dados.gov.br
  (`data/raw/confaz/`, fetch-manual) + módulo `qa_confaz` +
  `qa_confaz_vs_rreo.csv`: desvio mediano 0,46%/0,36% após pontes de dívida
  ativa e FECP; ponte de combustíveis por CNAE avaliada e recusada. Diligência
  F1 de LACUNA para RESOLVIDO_PARCIAL.
- **Recodificação dirigida pelo peso (R6):**
  `data/inputs/dupla_codificacao_dirigida_2026_07.csv` (46 itens do top-50% da
  despesa; κ dirigida 0,90, combinada 0,66). Cobertura da dupla codificação de
  10,8% para 53,2% da base; banda conjunta assimétrica para cima; resíduo
  delimitado à cauda de itens de baixo peso.
- **Apostas (R2):** exclusão do IS ampliado com justificativa dupla expressa
  (sem teto legal ancorável; GGR atrás de login, diligência F13); entrada
  bibliográfica da SPA/MF.
- **Fechos:** rótulos da Tabela C.1 sem parênteses aninhados (R7a); vírgula
  decimal e faixas com sinal no quadro de vieses (R7b); elasticidade de λ em
  `metricas_trava.csv` (R5); ponte A×B fechada numericamente
  (`ponte_b_a_*` em `metricas.csv`); nota da transição 80/90% e legenda da
  Figura 7 desambiguada (R3); universo municipal 5.570/5.569 conciliado (R4);
  imputação municipal somada ao alvo; invariante bloqueante I19 (legal_map);
  gate de 19 invariantes. Artigo entregue como unidade final integral (sem
  linguagem de comparação entre versões).

## 2026-07-10 — dia 1: do design à primeira execução completa

Oito commits em um dia, com camadas de dados construídas em sessões
paralelas e integradas no núcleo.

### Fase 1 — scaffold e design

- **`12ee2a2`** (13:02) `scaffold: pacote aferir (config, provenance, design doc)`
  — pacote `aferir` com `config.py` (único lugar de caminhos/janelas/constantes,
  todas com fonte) e `provenance.py` (Num/Label/Manifest gerado do grafo).
- **`a80d5a0`** (13:18) `design rev.2: incorpora parecer adversarial 4 lentes`
  — DESIGN.md revisado após parecer (lentes jurídica, dados, método, PTN);
  achados altos todos endereçados: IS/IPI residual no alvo da CBS (art. 353),
  módulo de compras governamentais (arts. 472-473) comum às três esferas,
  Simples e FECP nos numeradores, ISS-DF em R_M (art. 350, III), Tema 69
  como sensibilidade, rotas de dados verificadas (RFB XLSX HTTP 200; API
  SICONFI medida ~1 req/s), estratégia PTN (forks F9/F10).

### Fase 2 — núcleo puro

- **`6e3e1be`** (13:25) `núcleo puro: sistema tri-esfera (art. 473 linear 3x3),
  cashback assimétrico art. 118, hiatos; matriz v5 vendorada; 7 testes verdes`
  — `rates.py` (sistema linear com três modos do redutor art. 370),
  `cashback.py` (100%/20% CBS × 20% IBS), `gaps.py` (π^p da matriz legal +
  corredor γ), matriz POF×LC 214 v5 commitada com proveniência κ.

### Fase 3 — camada de dados (sessões paralelas) e integração

Notas de implementação por frente: federal (RFB XLSX + IPEADATA + âncora
5,114299% PIB; achado IOF-Seguros sem decomposição aberta; correção da
premissa "IS ≈ 0,13% PIB FMI" — aquilo é ZFM+cashback), municipal (fetch DCA
dos 5.570 municípios, conta RO1.1.1.4.51.1.0, golden SP ao centavo), compras
governamentais (G por esfera; FINBRA em lote inacessível → amostra top-200 +
pós-estratificação), POF do zero (achado: derivado v1 duplicava o quadro 19,
+1,72% de despesa), TRU/SICONFI-estadual/IPCA/ANP (achado: rubrica RREO já
inclui FECP e é pré-cota-parte — gross-up 4/3 do v1 abolido).

- **`4ced823`** (13:57) `integração: revenue/govpurchases/pipeline + camada de
  dados da onda 1 (federal, gov, POF reconstruída, TRU/SICONFI); smoke-test
  verde ex-municipal`.
- **`18528c7`** (13:59) `tabelas T1-T3, comparadores externos com fonte,
  invariantes gate (I0-I10)` — T1 com colunas obrigatórias de
  comparabilidade (ano-base, desenho legal, natureza);
  `data/inputs/comparadores.csv` com URL por comparador.

### Fase 4 — primeira execução e correções

- **`886520d`** (14:38) `primeira execução completa: central B=31,29
  (CBS 13,10+E 15,45+M 2,73), construção A âncoras 26,99-28,38
  (E 14,75≈TD2530, M 2,62); base TRU-side fix; 12 invariantes PASS`
  — **bug corrigido**: a âncora de consumo deduzia shares POF
  (fora-do-campo + combustíveis), dupla-removendo magnitudes que a TRU já
  não contém; remoção passou para o lado TRU (produtos 68002/97001/
  19912/19921/19916). Detalhe em METODOLOGIA.md §5.
- **`c09da84`** (14:41) `corrige DF no builder municipal (RREO-DF única
  fonte), FUNDEB espúrio como imaterialidade, universo ex-Brasília;
  50 testes verdes + 13 invariantes PASS`.
- **`fab4c6c`** (17:35) `teste POF: comparação direta com v1 pós-correção do
  quadro 19 (thread paralela aplicou dedup no v1)` — paridade v2×v1
  deduplicado: diferença 0,0 por item×UF.

### Estado ao fim do dia

- Pipeline verde offline em clone limpo; gate completo PASS (12 checagens
  I0-I10b; saída verbatim em METODOLOGIA.md §14); 50 testes verdes.
- Central (γ=12,5%, ψ=0, iso-carga): **CBS 13,10 + E 15,45 + M 2,73 =
  31,29 p.p.** (construção B, cota superior); construção A âncoras:
  **26,99-28,38** (E 14,75; M 2,62).
- Achados de auditoria sobre o v1 (não replicados no v2, candidatos a
  erratum): duplicação do quadro 19 da POF (+1,72% de despesa) e gross-up
  4/3 do ICMS (rubrica RREO já é pré-cota).

### Após os commits (esta sessão de documentação)

- `Makefile`: alvo `all` passou a executar também `aferir.tables` e
  `aferir.invariants`, cumprindo o contrato descrito no próprio comentário
  do alvo ("insumos -> alíquotas -> tabelas -> invariantes"); re-execução
  verificada byte-idêntica nos artefatos versionados.
- Sessão paralela do manuscrito estendeu `pipeline.py` com saídas
  `metricas.csv` (números de prosa, chave → valor com formula/fonte) e
  `base_uf.csv` (B^ord por UF), iniciou `docs/artigo/` (fontes Markdown com
  placeholders `{{csv:...}}` — zero número digitado) e adicionou:
  `uncertainty.py` (banda amostral POF, bootstrap Rao-Wu B=500 seed 42 →
  `banda_incerteza.csv`; Σ p5-p95 [31,18; 31,42], cota inferior declarada),
  `figures.py` (F1-F4 em PNG 300 dpi determinísticos, sem timestamp) e
  `manuscript.py` (renderizador DOCX puro — em desenvolvimento; nesta
  revisão `make manuscript` ainda não conclui). Suíte: 57 testes verdes.
- Novos documentos: `README.md`, `docs/METODOLOGIA.md`, `docs/CHANGELOG.md`
  (este arquivo).

### Pendências abertas (rumo aos gates de 20/07 e 03/08)

1. Fetchers de rede completos para TRU/POF/ANP/IPCA/RREO (`make fetch`
   integral em clone limpo, sem seed v1).
2. Invariante I12 (fechamento B^ord + G-SNA ≈ âncora TRU) no gate;
   I13/I14 promovidos de testes a gate se o custo compensar.
3. Camada de incerteza: bootstrap POF implementado (B=500; DESIGN §2.7
   previa B=1000 — convenção declarada); MC conjunto N=10.000 pendente.
4. Sensibilidades declaradas a implementar: Tema 69 (âncora líquida),
   razão IOF-Seguros ±25%, IS como cenário (0 / SERT-implícito /
   FMI-endógeno), θ do Simples.
5. Concluir `manuscript.py` (gerador DOCX = único entregável; `make
   manuscript` verde); espelho anônimo e varredura de metadados (13/08).

## 2026-07-10 — frente distribuição legal 2033 (sessão paralela)

- **`aferir/distribuicao.py`** (novo): distribuição do produto do IBS em 2033
  conforme o rito da transição federativa — retenção de 90% distribuída por
  coeficientes de receita média 2019-2026 (ADCT art. 131; LC 227 arts. 109 e
  114-116), seguro-receita de 5% da parcela não retida com nivelamento
  sequencial exato das menores razões (ADCT art. 132; LC 227 arts. 110 e 117,
  cap de 3× per capita §§3º-6º), parcela-destino de 9,5% (proxy shares de
  B^ord) e cota-parte municipal de 25% só sobre a parcela-destino estadual
  (ADCT 131, §3º; CF 158, IV, 'b'; critérios do art. 128 inertes no nível UF).
  Receita média: estados DCA 2019-2025 (0,75·ICMS + FECP integral, ADCT 82
  §1º, + fundos art. 115, I, 'b'); municípios ISS + 0,25·ICMS — ISS 2019-2023
  por estimador de razão da subamostra v1 (2.844 entes; 8 UFs sem amostra
  retropoladas por índice nacional, declarado em coluna); 2026 indisponível.
  Saídas: `distribuicao_2033.csv` (27 UF × E/M: referência, recebido, 4
  componentes, suficiência), `distribuicao_2033_metricas.csv`,
  `distribuicao_rm_historica.csv`. Validação externa: ISS nacional 2022
  estimado 111,3 R$ bi vs IPEA CC60 ~107.
- Resultado (produto 965,0 R$ bi 2024): suficiência mediana 97,9%, p10-p90
  [90,0; 107,6]; mínimo 86,4% (TO-M); 5/54 agregados UF-esfera abaixo de
  90,5% (TO/PI/RR/ES/SC municipais); seguro concentrado nos perdedores
  estruturais de destino (AM-E 1,95 de 4,83 R$ bi do pool). A retenção
  congela a geografia de 2019-2025 — a tensão residual vem da deriva DENTRO
  da janela (ad rem 2023+, dinamismo do ISS) e do vazamento de 9,5% ao
  destino; o piso do art. 371 (90,5%, Anexo XVI) disciplina a FIXAÇÃO de
  alíquota própria e não é violado pela transição nem pelos vetores
  indicativos (contrafactual 2078+). Leitura completa: scratchpad
  impl/distribuicao.md.
- `config.py`: constantes RETENCAO_2033, SEGURO_RECEITA_PCT,
  COTA_PARTE_MUNICIPAL, SEGURO_CAP_PER_CAPITA, JANELA_RECEITA_MEDIA (com
  fonte legal); `Makefile`: alvo `distribuicao`; testes:
  `tests/test_distribuicao.py` (14 verdes — conservação, percentuais legais,
  nivelamento, cota-parte, determinismo).

## 2026-07-10 (noite) — frente IS + âncora líquida (Tema 69) + art. 353 na construção A

Correções da esfera federal, todas com fonte e mecanismo DA LEI (zero
calibração a alvo). Manchete central B: **31,44 → 31,06** (CBS 13,16 →
12,78; E 15,52 e M 2,75 inalterados). Construção A: legal **28,38 → 28,04**;
PLDO **26,99 → 26,63**.

- **IS por proxy iso-carga (−0,416 p.p., efeito isolado medido):**
  `revenue.is_estimado_bi` lê as linhas `I.P.I-FUMO/BEBIDAS/AUTOMÓVEIS` do
  XLSX RFB (`RFB_XLSX_ROTULOS` estendido; 2024 = 17.168,2 e 2025 =
  18.936,7 R$ mi; média janela deflacionada = **17,60 R$ bi**) — produtos
  do campo do IS (LC 214, art. 409 + Anexo XVII). Proxy = cota INFERIOR do
  IS (campo mais amplo; alíquotas aguardam lei ordinária) ⇒ τ_CBS segue
  cota superior. `alvo_uniao` usa o proxy por default; IS=0 virou
  sensibilidade (`aferir_nacional.csv`, linha `sens_is_zero`, coluna
  `is_cenario`).
- **Âncora líquida — Tema 69 RESOLVIDO em dado aberto (+0,036 p.p.):**
  série líquida de restituições POR TRIBUTO localizada no RTN/STN
  (Tesouro Transparente/CKAN, Tabela 2.2, conceito caixa; fetcher/parser
  novos em `fetch/rfb_federal.py`; cache `data/raw/stn/`, vintage mai/2026).
  Âncora central = **5,126971% PIB** (líquida-RTN); bruta-RFB (5,114299%)
  = sensibilidade (`sens_ancora_bruta`, coluna `ancora_federal`). Δ medido
  **+0,0127 p.p. do PIB** — o suposto viés ↑ da bruta NÃO se confirma:
  nos anos de REFIS/PERT a alocação de parcelamentos no caixa supera as
  restituições (sinal empírico, reportado como medido). Saída nova
  `r_uniao_liquida.csv`.
- **Construção A líquida de IS + IPI residual (−0,364 p.p. em τ_CBS^A):**
  `pipeline.construcao_ancoras` deduz IS estimado + IPI residual do
  numerador federal nas DUAS variantes (art. 353 §1º; a meta PLDO 4,47%
  PIB é projeção de PIS/Cofins+IPI e também contém essas parcelas —
  declarado na coluna formula/fonte e coluna nova `deducao_art353_bi`).
- Invariante novo **I15** (sensibilidades federais presentes; IS=0
  mecanicamente > central; sinal da âncora livre). Métricas novas em
  `metricas.csv`: `is_estimado_bi`, `ancora_federal_liquida_pct_pib`,
  `deducao_art353_em_A_pp`, `efeito_is_proxy_pp`, `efeito_ancora_liquida_pp`.
  Goldens novos em `tests/test_federal.py` (RTN 2021; IS 17,600; âncoras).
  Pendência nº 4 da lista acima: Tema 69 e cenário do IS CONCLUÍDOS;
  seguem razão IOF ±25% e θ do Simples.
- Docs atualizados: METODOLOGIA §§3, 4.1, 8, 11, 13-16; DESIGN §2.3;
  artigo (03_metodologia, 04_resultados, 90_anexos); pins de teste
  31,44 → 31,06.

## 2026-07-11 — consolidação do espelho público de replicação

Preparação do repositório para publicação como espelho anônimo (100%
replicável em clone limpo, sem nenhuma dependência externa ao repo):

- **Internalização integral dos insumos brutos**: eliminadas TODAS as
  referências ao cache do pipeline v1 (`V1_RAW`/`V1_OUTPUTS` removidos do
  config). Os brutos vivem em `data/raw/` (fora do git, hashes nos
  `_meta.json`) e cada domínio ganhou fetcher público idempotente:
  `fetch.tru` (zip IBGE, sha byte-idêntico verificado contra o FTP),
  `fetch.sidra_ipca` (SIDRA 1737, janela pinada 201301-202512; deflator
  golden 0,952229023823 reproduzido a 12 casas), `fetch.anp` (fonte viva;
  162/162 células consumidas idênticas na vintage atual), `fetch.pof`
  (zips oficiais do FTP; 6/6 membros extraídos byte-idênticos aos pins),
  `fetch.siconfi_rreo` (Anexo 03; 162/162 campos ao centavo) e
  `fetch.siconfi_municipal_dca` (subamostra 2019-2023 com composição
  PINADA em `data/inputs/amostra_dca_municipal.csv`, 14.192 pares, com
  guarda de integridade no fetch).
- **Convenções vendoradas**: `data/inputs/fbcf_v1_uf.csv` (vetor B_FBCF da
  convenção v1, único consumo do antigo `destination_base.csv`) e
  `data/inputs/icms_adrem_confaz.csv` (tabela legal curada, atos citados).
- **Anonimização dos manifestos**: `provenance.caminho_repo` grava caminho
  RELATIVO à raiz em `MANIFEST_RUN/TRAVA`, `_seed_manifest` e `_meta`
  (zero caminho de máquina em qualquer arquivo versionado).
- **Reconstrução verificada do zero**: `data/processed/` apagado e
  reconstruído só dos brutos internalizados — 24 arquivos byte-idênticos,
  14 diferindo APENAS em colunas textuais de proveniência, ZERO divergência
  numérica; gate de invariantes completo PASS; figuras byte-idênticas.
- **Consolidação**: removidos `divulgacao.py` e `data/outputs/divulgacao/`
  (peças com números desatualizados, fora do Makefile); Makefile
  reorganizado (`fetch` cobre os 11 fetchers; `dados` = brutos→processados;
  `all` = `dados` + motor + gate); teste de paridade POF×v1 agora opcional
  via `AFERIR_V1_POF_DESPESA` (o espelho não contém o v1).
- **Fontes tipográficas**: TTFs Helvetica Neue (proprietários) fora do
  espelho (`.gitignore`); `tools/extrai_fontes.py` + `make fontes` extraem
  do macOS com rasterização verificada byte-idêntica; fallback DejaVu.
- **Organização**: README de replicação reescrito (fontes de dados ×
  fetchers, estrutura, resultados, verificação), LICENSE (MIT, pseudônimo
  AFERIDOR) e CITATION.cff novos.

## 2026-07-12 — snapshot arquivístico da subamostra municipal

A verificação em clone limpo (rota de API real, 14.192 pares) MEDIU a
instabilidade da fonte viva: 1 par pinado (4219150-SC, 2019; 851 linhas em
maio) passou a retornar VAZIO na API, e 12 de 13.377 pares reconferidos
voltaram com valores RETIFICADOS na origem. Consequência de desenho: a
subamostra fixada passa a ser distribuída como snapshot arquivístico
(subamostra_dca_municipal_2019-2023.tar.gz, 214 MB, sha256
95c4da89bf531040…, release do espelho), rota CANÔNICA do fetcher; a API
segue implementada como re-derivação documentada, com falha ruidosa para
pares retificados. Extração testada byte a byte; POF no clone limpo baixou
e verificou 6/6 membros contra os pins.

### Verificação final da replicação (2026-07-12)

Clone limpo do espelho publicado, ambiente virtual novo com
requirements.lock, `make fontes` + `make fetch` reais (POF do FTP do IBGE +
snapshot do release) + `make all` + figuras + manuscrito + testes:
**38/38 processados, 7/7 figuras, 4/4 tabelas e MANUSCRIPT.docx
byte-idênticos** aos do desenvolvimento; gate integral PASS; 136 testes
verdes. Replicação 100% confirmada de ponta a ponta.

## 2026-07-12 — decisão final: espelho pelo anonymous.4open.science

- Anexo D com o endereço definitivo do espelho anônimo
  (anonymous.4open.science/r/aferir-E5DC); gate de submissão passa.
- Snapshot da subamostra municipal VERSIONADO no repositório
  (data/raw/siconfi_municipal_dca/snapshot/, 3 partes + SHA256SUMS; mesma
  vintage e mesmo sha256 do release): a replicação da subamostra ficou
  OFFLINE e a vista anônima passou a conter TODOS os insumos exceto a POF
  (que o `make fetch` baixa do FTP do IBGE com hash verificado).
- Varredura de anonimato ampliada (novos padrões) e varredura PROFUNDA das
  colunas string de todos os 14,4 mil arquivos brutos: zero ocorrência de
  identidade do autor; as únicas coincidências são nomes oficiais de dois
  municípios brasileiros nos dados do SICONFI (homônimos parciais; a
  integridade do dado oficial é preservada — nada foi editado).
- README: replicação documentada pelas duas vias (download zip da vista
  anônima durante o cegamento; git clone fora dele), idênticas byte a byte.

### Blindagem dos binários na vista anônima (2026-07-12)

A verificação pela via do avaliador (download do zip da vista anônima +
replicação completa) MEDIU um modo de falha do espelho anonimizado: a
heurística texto/binário do serviço transformou exatamente 1 dos ~800
binários servidos soltos (uma DCA estadual, 67→97 KB, parquet corrompido),
por coincidência de conteúdo — nenhuma relação com os termos de redação
(testado). Correção estrutural: as DCAs estaduais passam a viajar como
snapshot arquivístico (snapshot/dca_estadual_2019-2025.tar.gz, sha256
pinado, extração offline pelo fetcher), formato que comprovadamente
atravessa a anonimização byte a byte, como o snapshot municipal.

## 2026-07-12/13 — revisão profunda pós-pareceres (A1-A9 / E1-E10 / L1-L7)

Revisão integral orientada por três pareceres externos (auditor fiscal,
economista acadêmico, legislador especializado) consolidados em
`super_documento_revisao.md`, executada em ondas com linha de base
congelada ANTES da primeira correção (Onda 0: `metadata/baseline_revisao.json`,
run `20d6e32` pinado por sha256 dos manifestos) e diff automatizado ao final
(`metadata/diff_baseline.md`).

### Manchete

Central da construção B (γ=12,5%, ψ=0, iso-carga): **31,06 → 32,80 p.p.**
(CBS 13,53 + IBS-E 16,43 + IBS-M 2,84; σ̂ = 8,234%). Atribuição medida pela
grade: SIFIM imputado excluído da âncora de consumo (E7.1) **+1,85**;
redutores imobiliários do art. 261 (E7.2) **+0,12**; perímetro de G ampliado
+ vigências de combustíveis + interações (A5/A2/A3, resíduo) **−0,22**.
Construção A INTACTA (28,04 / 26,63 — não usa B^ord; diff zero medido).
Trava-conforme: λ\* 0,537 → **0,742** (custo dos benefícios suprimidos
R$ 193,6 → **251,9 bi/ano**); vetores: medianas τ_E^uf 17,09 / τ_M^uf 1,64,
16 UFs acima da referência estadual, pisos do art. 371 vinculantes 7 (E) e
21 (M) — regressões intencionais justificadas linha a linha em
`metadata/qa_regressoes_parecer_l7.csv` (teste bloqueante
`tests/test_regressoes_l7.py`).

### Numeradores e deduções (bloco A)

- **A2 — ICMS ad rem por vigência mensal**: `data/inputs/icms_adrem_vigencias.csv`
  (6 convênios CONFAZ com período e URL; janeiro usa a alíquota anterior —
  reajustes vigoram em 1º/02) × volumes ANP mensais ⇒
  `deducao_icms_adrem_uf_mes.csv` (grão uf×ano×mês×produto); mistura
  comercial integral; etanol hidratado fora da monofasia; GLP m³→kg pela
  densidade oficial 0,552 t/m³ (Anuário ANP 2023). Dedução 2024:
  143,30 → 142,08 R$ bi.
- **A3 — PIS/Cofins-combustíveis mês a mês**:
  `data/inputs/pis_cofins_combustiveis_vigencias.csv` (Decreto 5.059/2004 e
  alteradores; QAV = linha NAO_DEDUZIDO) com fração fóssil pelo blend
  VIGENTE no mês (Res. CNPE 8/2023 e 9/2025: B14→B15, E27→E30) ⇒
  `deducao_federal_combustiveis_mes.csv`; dedução da janela 45,48 → 45,64
  R$ bi. Os insumos anuais `icms_adrem_confaz.csv` e `pis_cofins_ad_rem.csv`
  foram REMOVIDOS (substituídos pelas tabelas de vigências).
- **A4 — IS ampliado** (`aferir.is_ampliado` → `sens_is_ampliado.csv`):
  folga mensurável da cota inferior do proxy — minerais (Valor Venda
  ANM) e petróleo/gás (produção ANP × preços de referência) no teto legal
  de 0,25% (art. 422 §2º): +1,83 R$ bi de IS ⇒ −0,05 p.p. na soma.
- **A5 — perímetro de compras governamentais em corredor**
  (`g_perimetros.csv`, `sigma_compras.csv`): mín/central/máx (elementos da
  Portaria 163/2001) + chave da natureza 36; central passa a
  3.3.90.{30,32,33,36,37,39,40} ⇒ G_U 102,55 / G_E 193,06 / G_M 385,06
  R$ bi; σ por perímetro (máx = 7,676% com carga própria de capital);
  cenários `sens_g_min`/`sens_g_max`/`sens_natureza36_off`.
- **A6 — cobertura econômica por exercício** (`coverage_siconfi.csv`):
  2024 = 99,95%, 2025 = 99,64% (novo invariante I16 ≥ 99%); cenário
  `sens_janela_2024` (−0,06 p.p.).
- **A7 (com E1) — cunha do Simples fechada nas duas pontas**
  (`aferir.simples`): ω = 0,1037 do consumo em campo suprido por pequenas
  (PAC/PIA/PAS 2023 × TRU, `omega_simples.csv`, cota inferior declarada) ⇒
  cenários `com_cunha_simples` (+3,60 p.p.) e
  `com_cunha_simples_dois_lados`; QA dos numeradores
  (`qa_simples_numeradores.csv`): Ementário STN sem natureza própria de
  ISS/ICMS-Simples — as contas consolidadas JÁ os contêm.

### Robustez econômica (bloco E)

- **E2 — erro de classificação da matriz legal** (`aferir.classificacao`):
  dupla codificação vendorada byte a byte
  (`data/inputs/dupla_codificacao_2026_07.csv`, 470 itens, κ_m = 0,637);
  envelopes determinísticos na grade (−0,17/+0,13 p.p.) e bootstrap
  decomposto amostragem × classificação × conjunto (B=500) em
  `qa_bootstrap_classificacao.json` + `banda_incerteza_decomposta.csv`.
- **E3 — perfis de corte da trava** (`aferir.perfis_trava` →
  `resultados_perfis_trava.csv`): P1 uniforme (valida a trava bit a bit),
  P2 protege essenciais (**INFACTÍVEL só com o §11** — nem λ=1 fecha em
  26,5%), P3 por regressividade do benefício (fecha com custo ≈ uniforme).
- **E4 — estacionariedade base/PIB nomeada e estressada**
  (`aferir.robustez` → `sens_base_pib.csv`): extremos da década ⇒
  `sens_base_pib_min/max` (+1,18/−0,70 p.p.).
- **E5 — γ heterogêneo por UF**: informalidade PNADC (SIDRA 8529) com
  renormalização que preserva o γ médio ⇒ `sens_gamma_heterogeneo.csv` e
  vetores em `sens_vetores_gamma_uf.csv`.
- **E6 — cashback pelo critério legal**: `aferir.inputs.pof legal` recomputa
  a elegibilidade literal (≤ ½ SM per capita) ⇒ `pof_elegiveis_legal_uf.csv`,
  `cashback_elegibilidade.csv`; cenários `sens_cashback_legal` (−0,30 p.p.)
  e take-up 80% (−0,38 p.p.).
- **E7 — SIFIM e FBCF imobiliária quantificados** (`aferir.sifim_fbcf`):
  E7.1 SIFIM imputado (270,25 R$ bi 2021, split por resíduo POF→TRU) SAI da
  âncora — CENTRAL flipado, +1,85 p.p. (convenção anterior vira
  `sens_sifim_incluido`); E7.2 redutor de 50% do art. 261 na parcela
  residencial nova da FBCF-NC — CENTRAL flipado, +0,12 p.p.
- **E8 — estresse de conformidade**: γ = 20% na grade (Σ 35,88).

### Camada jurídica e de reporte (bloco L)

- `metadata/legal_map.csv`: mapa dispositivo→norma com trecho confirmatório,
  verificado contra os HTMLs compilados baixados pelo novo
  `aferir.fetch.planalto` (LC 214, LC 227, EC 132, CF/ADCT; vintage
  congelada por sha256); teste `test_legal_map.py`.
- Rotulagem das construções disciplinada (`metadata/qa_rotulos_cenarios.csv`:
  "rito" só para o art. 353; PLDO = "comparável às estimativas oficiais");
  checagem citações×referências (`metadata/qa_citacoes_referencias.csv`).
- **Quadro consolidado de direções de viés** (L7/E10): T5 do artigo,
  gerado da própria grade (`tables.py::t5_quadro_vies` →
  `data/outputs/t5_quadro_vies.csv` = `quadro_direcoes_vies.csv`).
- Diligências de fonte datadas (`metadata/diligencias_fontes.csv`, F1-F27)
  e a lacuna do IOF-Seguros por modalidade documentada como fronteira OD/ADM.

### Infraestrutura

- Grade de `aferir_nacional.csv`: 22 rótulos de cenário (invariante novo
  I17); gate com 17 checagens (novos I16/I17/I18; I4 renomeado
  "consistência RREO×DCA" — A1); alavancas da revisão como parâmetros de
  `pipeline.monta_insumos`/`executa` com defaults centrais (DESIGN §10).
- `Makefile`: `fetch` ganha `planalto`, `ibge_porte`, `ibge_informalidade`
  (14 fetchers); `dados` ganha `inputs.pof legal`; `motor` encadeia
  `classificacao → sifim_fbcf → is_ampliado → simples → pipeline →
  uncertainty --classificacao → trava → perfis_trava → robustez --vetores →
  cashback → distribuicao → tables → invariants` (efeitos re-baselináveis:
  segunda passada de `make all` converge byte a byte — DESIGN §10.3).
- Suíte: 269 testes verdes (novos: vigências, perímetros de G, Simples,
  classificação, SIFIM/FBCF, IS ampliado, perfis da trava, robustez,
  cashback legal, mapa legal, bibliografia, regressões L7).
- Docs atualizados: README (fontes×fetchers, estrutura, resultados,
  metadata/), METODOLOGIA (§§1, 2, 4-9, 10, 11, 12, 12-A, 13-16, 18),
  DESIGN (rev. 3, §10), este CHANGELOG.
