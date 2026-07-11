# METODOLOGIA — AFERIR (peça de auditabilidade)

**Escopo.** Este documento permite a um auditor externo reproduzir e
contestar cada número do pipeline sem acesso a esta conversa nem ao v1:
para cada grandeza declara o dispositivo legal, a fonte aberta (endpoint,
arquivo, rubrica/conta exata), a transformação e a direção do viés de cada
convenção. Valores citados referem-se à execução de 2026-07-12, pós-revisão
dos pareceres A1-A9/E1-E10/L1-L7 (`data/processed/MANIFEST_RUN.json`;
commits em `docs/CHANGELOG.md`; diff medido contra a linha de base
pré-revisão em `metadata/diff_baseline.md`, congelada em
`metadata/baseline_revisao.json`).

Regra de leitura: **todo número tem rótulo** — `OFICIAL` (publicado por
órgão oficial, com URL), `DADO` (lido de fonte primária aberta), `DERIVADO`
(fórmula sobre DADO/OFICIAL) ou `CONVENCAO` (escolha metodológica declarada,
fork ⚑). Nenhuma constante numérica vive fora de `src/aferir/config.py`.

---

## 1. Nomenclatura

| Símbolo | Significado | Onde nasce |
|---|---|---|
| τ_CBS, τ_E, τ_M | alíquotas de referência da União (CBS), estadual e municipal (IBS) | `rates.py` |
| R_s / Alvo_s | receita de referência da esfera s (art. 350) / alvo a repor pós-ajustes | `revenue.py` |
| B^ord | base ordinária de destino = B_C + B_ISFLSF + B_FBCF_NC (SEM compras governamentais) | `base.py` |
| B_C | consumo das famílias em campo, ex-combustíveis monofásicos | TRU 2021 × escala; shares POF |
| B_ISFLSF | consumo das ISFLSF (distribuído por população) | TRU 2021 |
| B_FBCF_NC | FBCF não-corporativa, m = 1,00 (art. 200 §4º) | TRU 2021 × share VTI/PIA |
| D_s | base líquida da esfera: B^ord·(1−π) − cb_base_s | `pipeline.py::_d_esfera` |
| G_s | compras governamentais da esfera (arts. 472-473) | `govpurchases.py` |
| σ | alíquota efetiva sobre compras públicas = (1−r)·(τ_U+τ_E+τ_M) — redução uniforme e proporcional do art. 472 (art. 473 §1º) | `rates.py` |
| π^p | hiato de política: Σ w_i(1−m_i)/Σ w_i, i ∉ F | `gaps.py`, matriz legal |
| m_i | multiplicador legal do item POF i ∈ {0; 0,30; 0,40; 0,60; 0,70; 1,00} | `matriz_pof_ibs_v5.csv` |
| flag F | item fora do campo de incidência (arts. 4º/6º) — sai da base, pesos renormalizados | matriz legal |
| γ / γ_eff | hiato de conformidade / γ·(1−ψ) | `gaps.py` |
| ψ | mitigação por split payment (cenário, fora do central — ⚑ F1) | `gaps.py` |
| zfm | adendo de política da ZFM (só AM, +0,13, aditivo a π^p) | `pipeline.py` |
| f_low | share dos decis 1-3 de renda per capita na despesa (proxy CadÚnico ≤ ½ SM) | POF, `pof_decis_uf.parquet` |
| share_piso | share dos itens do piso do art. 118 (energia, água/esgoto, gás canalizado, telecom) | POF × matriz |
| cb_base_s | dedução de base pelo cashback da esfera (art. 118) | `cashback.py` |
| ω | cunha do Simples no denominador: fração do consumo em campo suprida por optantes que permanecem no regime; medida aberta = 0,1037 (cota inferior) | `simples.py`, `omega_simples.csv` |
| γ_uf | hiato de conformidade heterogêneo por UF (informalidade PNADC, β ∈ {0,5; 1,0}; renormalizado ao γ̄ ponderado pela base) | `robustez.py`, `sens_gamma_heterogeneo.csv` |
| λ / λ_c | encolhimento dos regimes favorecidos (trava art. 475 §11); escalar no corte uniforme, por classe de regime nos perfis E3 | `trava.py`, `perfis_trava.py` |
| B\* | base realizada implícita nas âncoras oficiais = 12,30% PIB ÷ 26,47% | construção A |
| δ | deflator IPCA 2025→2024 = 0,9522290238225959 (média anual SIDRA 1737) | `ipca_pib.py` |
| escala biênio (consumo) | C_fam nominal (média 2024-25 em R$ 2024) ÷ C_fam 2021 = 1,3767888 (SIDRA 1846 c93404) — escala de B_C e, por proxy declarado, B_ISFLSF | `pipeline.py` |
| escala biênio (FBCF) | FBCF nominal (média 2024-25 em R$ 2024) ÷ FBCF 2021 = 1,2492014 (SIDRA 1846 c93406) — série própria da FBCF | `pipeline.py` |

Unidade padrão: **R$ bilhões a preços de 2024**, média da janela 2024-2025
(«média janela deflacionada»: (v_2024 + v_2025·δ)/2).

## 2. Identidade e sistema tri-esfera (arts. 472-473)

Nas aquisições de cada ente as alíquotas dos **demais** entes zeram e a do
comprador é a **soma** das três, pós-redutor (art. 473 §1º). Compras
governamentais G portanto saem da base ordinária de todas as esferas e viram
termo próprio:

```
Alvo_s = τ_s·D_s + σ·G_s ,   s ∈ {U, E, M}
σ      = (τ_U + τ_E + τ_M) − redutor        (art. 473 §1º c/ art. 370)
D_s    = B^ord·(1−π) − cb_base_s
```

Sistema **linear 3×3** nas τ, resolvido em forma fechada (`rates.py`).
Modos do redutor do art. 370 (⚑ F8):

- **iso-carga (central):** σ conhecido = carga tributária embutida hoje nas
  compras públicas, estimada pela TRU 2021 — mix do consumo intermediário
  das atividades do governo geral (8400, 8591, 8691) × impostos líquidos de
  subsídios sobre produtos ÷ oferta a preço de consumidor ⇒
  **σ̂ = 8,234%** (`tru_gov_carga.csv`, cenário `carga_embutida_gov_central_pct`;
  diagnósticos rejeitados no mesmo CSV: consumo final total do governo 0,195%
  — dominado por produção própria não-mercantil, produtos 84001/84002/85911/86911 —
  e consumo final ex-produção própria 4,316%). Com σ dado, o sistema
  **desacopla**: τ_s = (Alvo_s − σ·G_s)/D_s.
- **sem redutor:** redutor = 0; sistema 3×3 completo (matriz
  A[i][j] = D_i·1{i=j} + G_i).
- **redutor total:** σ = 0 (compras públicas não geram receita).

Domínio de sanidade embutido: 0 < τ_s < 0,60 (erro, não warning).
G_s^aq = naturezas de **aquisição** apenas, com perímetro em corredor
(revisão A5; elementos da Portaria Interm. STN/SOF 163/2001, grade completa
em `g_perimetros.csv`):

- **mín** = 3.3.90.{30, 39} (material de consumo e serviços PJ);
- **central** = 3.3.90.{30, 32, 33, 36, 37, 39, 40} — inclui material de
  distribuição gratuita, passagens/locomoção, serviços PF, locação de
  mão de obra e TIC; **CENTRAL do artigo, COM a natureza 36** (chave
  `natureza36`: serviços de PF podem estar fora do campo IBS/CBS pelo
  art. 6º, I — cenário `sens_natureza36_off` mede a chave: +0,05 p.p.);
- **máx** = central + 4.4.90.{51, 52} (obras e equipamentos — capital).

Folha fora do campo (art. 4º, mesmo fundamento da flag F); modalidade 90
(intra-orçamentárias 3.3.91 excluídas); estágio central Despesas Empenhadas
(Liquidadas = sensibilidade). O σ iso-carga é **por perímetro**
(`sigma_compras.csv`): custeio = 8,234% (mix do CI do governo geral, TRU
2021); no perímetro máx, a parcela de capital entra com carga própria dos
produtos de FBCF (σ_capital = 5,764%) ponderada pela composição de G ⇒
σ_máx = 7,676% (invariante I18). Efeitos medidos na soma: perímetro mín
+0,24 p.p.; máx −0,29 p.p. (`sens_g_min`/`sens_g_max`). O G-473 é
conceitualmente distinto do G-SNA do fechamento da
base nacional (papéis declarados; ver §14, pendência I12).

## 3. Âncoras temporais (art. 353 × arts. 361-365)

| Esfera | Dispositivo | Âncora legal | Implementação |
|---|---|---|---|
| União (CBS) | art. 353 (LC 214) | média da receita-referência/PIB **2012-2021** | `ANCORA_UNIAO = 2012…2021`; âncora central = **5,126971% do PIB** (convenção LÍQUIDA-RTN, Tema 69); bruta-RFB = 5,114299% (sensibilidade; Δ medido = +0,012672 p.p. do PIB) |
| Estados e Municípios (IBS) | arts. 361-365 (red. LC 227/2026) | média **2024-2026** | `ANCORA_SUBNACIONAL = [2024, 2025, 2026]`; janela efetiva `JANELA_RECEITA = [2024, 2025]` — **2026 indisponível em jul/2026, declarado** |

Consequência comunicada no artigo: a âncora federal repõe carga
**histórica** por decisão legal (art. 353) — τ_CBS não é comparável 1:1 com
exercícios ancorados em receita corrente (SERT 4,47% PIB é projeção
PLDO 2025). O invariante I10 reconcilia **decomposto**, nunca em soma única.

## 4. Receitas de referência por esfera (art. 350) — conta a conta

As colunas `formula`/`fonte` dos CSVs processados são a fonte primária desta
seção; aqui está a consolidação.

### 4.1 União — art. 350, I ('a'-'c') e art. 353

Arquivo: `data/processed/r_uniao.csv` (+ `ancora_uniao.csv`); código:
`fetch/rfb_federal.py`, `inputs/uniao.py`, `revenue.py::alvo_uniao`.

| Componente | Dispositivo | Fonte aberta e rubrica EXATA |
|---|---|---|
| PIS/Pasep | art. 350, I, 'a' | XLSX RFB "Arrecadação das receitas federais 1994 a 2025" (gov.br, sha256 691012ee…), linha `CONTRIBUIÇÃO PARA O PIS/PASEP`, coluna TOTAL da aba do ano. PIS **não separável** do Pasep na série aberta — sem perda: o dispositivo referencia a contribuição por inteiro |
| Cofins | art. 350, I, 'b' | mesma série, linha `COFINS - CONTRIB. P/ A SEGURIDADE SOCIAL` (golden: 2021 = 286.499,276 R$ mi, bate com IPEADATA) |
| IPI | art. 350, I (IPI) | linha `I.P.I-TOTAL` |
| IOF-Seguros | art. 350, I, 'c' | **sem decomposição aberta** (ver §15). Rota aberta: razão IOF-Seguros/IOF-total = 5.400 (NT SERT jul/2024, p. 3) ÷ 61.200,78 (IOF 2023, XLSX) = **0,088234**, aplicada à linha `IOF - I. S/ OPERAÇÕES FINANCEIRAS`; razão constante 2012-2021 e 2024-2025 (CONVENCAO; peso total do rateio na âncora: 0,046 p.p. do PIB) |
| Receita LÍQUIDA por tributo (Tema 69) | art. 353 (convenção da âncora) | RTN/STN, "Resultado do Tesouro Nacional — Série Histórica" (Tesouro Transparente/CKAN), **Tabela 2.2** (anual, R$ mi correntes): linhas `1.1.02 IPI`, `1.1.04 IOF`, `1.1.05 Cofins`, `1.1.06 PIS/Pasep` — conceito **caixa** (ingresso efetivo na Conta Única, nota 1/) e **líquida de restituições** (dicionário do dataset: Receita Líquida III=I−II deduz restituições dentro de I; incentivos = linha 1.2). Golden: IPI 2021 = 71.286,107 R$ mi. Vintage mai/2026, sha256 no `_meta.json` |
| Fallback/triangulação | — | IPEADATA OData4, séries SRF12_{PIS,COFINS,IPI,IOF}12 mensais anualizadas por soma; 48 comparações, dif. máx. 3,7e-16 (mesma origem RFB — triangulação de integridade, não de independência). RTN×RFB: desvio anual por tributo < 15% (conceitos distintos: caixa/líquida × arrecadação/bruta; parcelamentos REFIS/PERT alocados por tributo no RTN) |
| PIB | — | SIDRA 1846 (SCN Trimestral, v/585, c11255/90707), anual = Σ 4 trimestres; validação 2021 = 9.012.142 R$ mi |

Alvo (art. 353 §1º), em R$ bi 2024 na janela:

```
Alvo_U = âncora × PIB_janela − IPI_residual_ZFM − IS_estimado − PIS/Cofins-combustíveis
       = 5,126971% × 11.954,6  −  2,6  −  17,60  −  45,64  =  547,07
```

- **IPI residual ZFM** = 2,6 R$ bi líquido (NT SERT p. 4; brutos não
  publicados) — `data/inputs/is_ipi_residual.csv`.
- **IS estimado = 17,60 R$ bi** (proxy iso-carga com dado aberto): projeção
  oficial do Imposto Seletivo **inexistente em dado aberto** até 10/07/2026
  (PLDO 2027, Anexo IV.2, pp. 8 e 20); o central adota IS estimado =
  arrecadação corrente de IPI nos produtos do campo do IS — linhas
  `I.P.I-FUMO` (2024: 8.164,9; 2025: 11.190,7), `I.P.I-BEBIDAS` (3.111,7;
  3.208,0) e `I.P.I-AUTOMÓVEIS` (5.891,6; 4.538,0 R$ mi) do XLSX RFB, média
  janela deflacionada. O campo do IS é definido na LC 214 (art. 409 + Anexo
  XVII: fumo, bebidas, veículos — e ainda bebidas açucaradas, embarcações/
  aeronaves, bens minerais, prognósticos, que o proxy NÃO capta); alíquotas
  aguardam lei ordinária (art. 414) ⇒ o proxy é **cota inferior** do IS e
  τ_CBS segue **cota superior** nessa dimensão (direção declarada). Cenário
  IS = 0 vira sensibilidade (`aferir_nacional.csv`, `cenario_gamma =
  sens_is_zero`, coluna `is_cenario`); efeito isolado medido: **−0,442
  p.p.** na manchete. A **folga da cota inferior é quantificada** (revisão
  A4, `aferir.is_ampliado` → `sens_is_ampliado.csv`): minerais (ferro e
  carvão pelo Valor Venda do Anuário Mineral/ANM) e petróleo/gás (produção
  ANP × preço de referência das Res. ANP 874-875/2022) avaliados **no teto
  legal de 0,25%** (art. 422 §2º, red. LC 227) somam +1,83 R$ bi de IS ⇒
  cenário `sens_is_ampliado` (IS = 19,43 R$ bi): −0,05 p.p. na soma; os
  demais componentes do campo (bebidas açucaradas, embarcações/aeronaves,
  prognósticos) seguem sem alíquota citável — lacunas documentadas no CSV.
  Sobreposição potencial com a lista residual ZFM
  (produtos do campo do IS industrializados na ZFM, p.ex. concentrados e
  motocicletas) não é separável em dado aberto (NT não publica os brutos) —
  dupla dedução marginal possível, limitada aos 2,6 R$ bi, direção ↓
  contrabalançada pela cota inferior do proxy.
- **PIS/Cofins-combustíveis** deduzido simetricamente (regime monofásico),
  agora **mês a mês** (revisão A3, `revenue.deducao_federal_combustiveis_mes`
  → `deducao_federal_combustiveis_mes.csv`): volume ANP nacional do mês ×
  fração **fóssil** da bomba pelo blend VIGENTE no mês (E27→E30 e B14→B15;
  Res. CNPE 8/2023 e 9/2025 — a Lei 14.993/2024 autoriza) × alíquota ad rem
  vigente na tabela de vigências `data/inputs/pis_cofins_combustiveis_vigencias.csv`
  (Decreto 5.059/2004 e alteradores, com ato e URL por linha: gasolina
  792,50 R$/m³; diesel 351,50 R$/m³ — constantes em 2024-2025; as reduções
  quase-zero são de 2026, fora da janela). GLP entra com alíquota ZERO
  (botijão doméstico P13, art. 2º, V; granel não separável em dado aberto)
  e QAV é linha `NAO_DEDUZIDO` (insumo do transporte aéreo, não consumo
  final — simetria com a base POF). Etanol/biodiesel e GLP granel omitidos
  ⇒ dedução subestimada ⇒ viés ↑ em τ_CBS (coerente com o proxy
  do IS, cota inferior). Total na janela: 45,64 R$ bi.
  Nota: o regime ad rem é **opcional** (art. 23, Lei 10.865/2004) — a
  estimativa assume adesão generalizada, declarado.
- **Tema 69 — RESOLVIDO em dado aberto**: a convenção LÍQUIDA de
  restituições por tributo existe aberta (RTN/STN, Tabela 2.2) e é a âncora
  **CENTRAL** (5,126971% PIB); a bruta-RFB (5,114299%) vira sensibilidade
  (`cenario_gamma = sens_ancora_bruta`, coluna `ancora_federal`). O Δ medido
  é **+0,012672 p.p. do PIB** (líquida > bruta): nos anos de
  REFIS/PERT (2013, 2017-2018) a alocação por tributo dos parcelamentos no
  conceito caixa mais que compensa as restituições deduzidas — o suposto
  viés ↑ da bruta NÃO se confirma empiricamente; efeito isolado na manchete:
  **+0,038 p.p.** (sinal empírico, reportado como medido).

### 4.2 Estados — art. 350, II ('a'-'b') e §§1º-2º

Arquivos: `r_estadual.csv`, `fecp_uf.csv`, `fundos_estaduais.csv`,
`combustiveis_uf.csv`; código: `inputs/siconfi_estadual.py`,
`inputs/combustiveis.py`, `revenue.py::alvo_estadual_uf`.

| Componente | Dispositivo | Fonte aberta e rubrica EXATA |
|---|---|---|
| ICMS bruto | art. 350, II, 'a' | RREO Anexo 03, rubrica `ICMSLiquidoExcetoTransferenciasEFUNDEB`, período 6, coluna `TOTAL (ÚLTIMOS 12 MESES)` (API SICONFI `/rreo`). **Conceito medido**: arrecadação bruta líquida só de restituições, ANTES de FUNDEB e cota-parte, e **já inclui o FECP** |
| Triangulação DCA | — | identidade exata com DCA Anexo I-C: contas `1.1.1.4.50.1.0` (ICMS) + `1.1.1.4.50.2.0` (FECP), coluna Receitas Brutas Realizadas − Outras Deduções; desvio 0,0% em 54/54 UF-ano (invariante I4; tolerância 0,1% no leitor) |
| FECP | ADCT art. 82 §1º (via art. 350 §1º) | conta `1.1.1.4.50.2.0` — **decomposição, não adição** (já contido na rubrica RREO); separável em 22 UFs (ausente em AC/AP/PA/RR/SC); 2024 = 13,52 R$ bi (RJ 6,66) |
| Fundos estaduais | art. 350, II, 'b' e §2º, II | total **OFICIAL** 3,5 R$ bi (NT SERT jul/2024, p. 4: FETHAB-MT, FUNDERSUL-MS, FUNDEINFRA-GO); alocação por UF = **CONVENCAO** (proporcional ao ICMS médio 2021-2023 do DCA: MT 43,8% / GO 33,8% / MS 22,4%), corrigida por UF pela variação do ICMS (§2º, II); 2024 = 4,378 R$ bi. Excluídas contribuições migradas ao ADCT 136 (§2º, I); se os estados exercerem a opção do ADCT 136 par. único, os fundos SAEM da referência (fork condicional) |
| (−) ad rem combustíveis | art. 172 (monofasia) | dedução **mensal** (revisão A2, `inputs/combustiveis.py` → `deducao_icms_adrem_uf_mes.csv`, grão uf×ano×mês×produto): volumes ANP do mês × alíquota VIGENTE no mês, lida de `data/inputs/icms_adrem_vigencias.csv` (6 convênios com período e URL: Convs. ICMS 199/2022, 15/2023, 172/2023, 173/2023, 126/2024, 127/2024 — janeiro de cada ano usa a alíquota anterior; os reajustes vigoram em 1º/02). Mistura comercial INTEGRAL (gasolina C e diesel B — alíquota única por litro; assimetria declarada com a fração fóssil federal); GLP m³→kg pela densidade OFICIAL 0,552 t/m³ (Anuário ANP 2023, substitui a convenção 550 kg/m³ do v1). 2024 = 142,08 R$ bi (share do ICMS: mediana 19,7%; mín. RJ 12,2%; máx. TO 33,4%) |
| (−) ad valorem etanol hidratado | art. 172, VI (monofasia) | o EHC **É monofásico na LC 214** (art. 172, VI) — a leitura anterior ("etanol hidratado fora da monofasia") era um ERRO corrigido na auditoria de 2026-07: o que ocorre é que o EHC está **fora dos convênios ad rem da LC 192/2022** (Convs. 199/2022 e 15/2023 cobrem gasolina+EAC, diesel+B100 e GLP/GLGN) e por isso recolhe HOJE ICMS **ad valorem** — que deve sair do alvo simetricamente à remoção do produto TRU 19921 da base. Dedução **mensal** (`inputs/deducao_etanol.py` → `deducao_icms_etanol_uf_mes.csv` e `deducao_icms_etanol_uf.csv`): volumes ANP do mês × preço médio de revenda ANP-SLP (mensal, por UF; proxy aberto do PMPF) × carga ad valorem vigente por UF, lida de `data/inputs/icms_etanol_hidratado_vigencias.csv` (ato estadual citado linha a linha: alíquota específica de EHC, base reduzida — expressa como carga efetiva — ou modal da UF). 2024 = 11,0 R$ bi; 2025 = 11,9 R$ bi (SP ≈ 42% da dedução; cross-check TRU: consumo 19921 na janela × carga efetiva ≈ 12 R$ bi) |
| Simples-ICMS | art. 350 §1º, I | já dentro da rubrica SICONFI (não somado em separado); demonstração por ausência de natureza própria no Ementário STN 2024-2025 em `qa_simples_numeradores.csv` (revisão A7 — ICMS-Simples ≈ 3,6% do alvo estadual, `share_simples_icms_alvo_E`) |

```
Alvo_E = Σ_uf [ICMS bruto − ad rem ANP×CONFAZ − ad valorem EHC + fundos]
```

Nota de integração (auditoria 2026-07): a componente ad valorem do EHC é
MEDIDA por `inputs/deducao_etanol.py` (média da janela ≈ 11,4 R$ bi) e sai
do alvo em `revenue.py::alvo_estadual_uf`, que subtrai
`receita_etanol_estimada` de `deducao_icms_etanol_uf.csv` no mesmo desenho
da dedução ad rem (deflacionada e mediada na janela). Sem essa dedução o
alvo estadual carregava ICMS de um produto cuja base já fora removida
(assimetria de ~0,25 p.p. na soma das esferas).

Correção estrutural vs. v1 (achado de 2026-07-10): a rubrica RREO **já é
pré-cota-parte** — o gross-up algébrico de 4/3 do v1 era conceitualmente
equivocado e foi abolido; e o FECP **não** deve ser somado ao numerador
(dupla contagem), apenas decomposto.

### 4.3 Municípios — art. 350, III e §1º, III

Arquivos: `r_municipal_uf.csv`, `iss_municipio_{2024,2025}.parquet`,
`iss_concentracao.csv`; código: `fetch/siconfi_municipal.py`,
`revenue.py::alvo_municipal_uf`.

| Componente | Dispositivo | Fonte aberta e conta EXATA |
|---|---|---|
| ISS municipal | art. 350, III | DCA Anexo I-C por município (API SICONFI, universo `/entes` esfera M = exatamente 5.570), conta `RO1.1.1.4.51.1.0` (prefixo RO = Receitas Orçamentárias) — a conta pós-2022 do ementário **já consolida** principal, multas e dívida ativa (art. 350 §1º, III). Convenção de coluna: `Receitas Brutas Realizadas − Outras Deduções da Receita` (líquida de restituições; Deduções-FUNDEB não incidem sobre ISS — invariante testa) |
| Verificação ao centavo | — | SP capital 2024: ISS bruto = R$ 35.836.255.499,67 (≡ MSC dez/2024: 33.458,0 + 463,7 + 1.655,6 + 258,9 R$ mi) |
| ISS do DF | art. 350, III ("Municípios **e do Distrito Federal**") + art. 349, II, 'c' | RREO-DF Anexo 03, rubrica `ISSLiquidoExcetoTransferenciasEFUNDEB`, 12 meses: 2024 = R$ 3.472.401.821,22; 2025 = R$ 3.862.618.982,16 (fonte='RREO-DF' no CSV). DF entra no vetor estadual só com ICMS; a referência do DF é a soma |
| Fernando de Noronha | ADCT art. 15 (CF); LC 214 art. 14 §1º | ISS nas contas de PE (competência municipal exercida por PE) |
| Omissos (⚑ F2) | — | status por município: `ok` / `dca_sem_iss` (ISS = 0) / `sem_dca` (NaN). Imputação por mediana per capita dos declarantes do estrato populacional da própria UF (estratos IBGE/Munic) — **medida imaterial**: 0,077 R$ bi (2024) e 0,573 R$ bi (2025), ≤ 0,4% do ISS nacional; o central publica os declarantes (coluna `iss_imputado` preserva a variante) |
| Simples-ISS | art. 350 §1º, I | já dentro da conta consolidada 1.1.1.4.51.1.0; demonstração em `qa_simples_numeradores.csv` (revisão A7: Ementário STN sem natureza própria de ISS-Simples; repasse do DAS chega ao ente na conta ordinária) — ISS-Simples ≈ 15,4% do alvo municipal (`share_simples_iss_alvo_M`) |
| Cobertura | — | 2024: 99,2%; 2025: 96,0% (invariante I6 ≥ 90%; ⚑ F4 completude 2025 medida e declarada). Cobertura **econômica** por exercício (revisão A6, `coverage_siconfi.csv`: ISS declarado ÷ declarado+imputado): 2024 = 99,95%; 2025 = 99,64% (invariante I16 ≥ 99%); sensibilidade janela só-2024 na grade (`sens_janela_2024`: −0,06 p.p. na soma) |

```
Alvo_M = média janela deflacionada do ISS líquido (municípios + DF) = 145,59
```

Diagnóstico federativo derivado: Lorenz/Gini do ISS por município
(`iss_concentracao.csv`): top-1 = 25,7%, top-10 = 44,2%, top-100 = 71,8% do
ISS nacional 2024.

## 5. Base de destino (denominadores) e o bug corrigido

Arquivos: `tru_2021_usos.parquet`, `pof_despesa_item_uf.parquet`,
`base_uf.csv`; código: `inputs/tru.py`, `inputs/pof.py`, `base.py`.

**Âncoras nacionais (TRU 2021, nível 68 — última edição detalhada; NÃO
migrar para 2023):** consumo das famílias, ISFLSF e FBCF da tab2, com
fechamento interno Σ produtos ≡ linha Total (tolerância 0,5 R$ mi).
Escala ao biênio pela variação **nominal** do consumo das famílias
(SIDRA 1846): ×1,3767888.

**Remoções da âncora de consumo — NO LADO TRU** (`TRU_PRODUTOS_REMOVIDOS`):

| Produto TRU | Motivo | Dispositivo |
|---|---|---|
| 68002 Aluguel imputado | fora do campo — autoconsumo habitacional sem operação onerosa | art. 4º (convenção v5-22) |
| 97001 Serviços domésticos | fora do campo — família F da matriz | art. 4º |
| 19912 Gasoálcool, 19921 Etanol, 19916 Outros refino (GLP) | monofásicos, tratados à parte (simetria numerador/denominador) | art. 172 |

**Bug encontrado e corrigido (commit 886520d, "base TRU-side fix"):** a
primeira implementação deduzia da âncora TRU os **shares POF** dos itens
fora-do-campo e dos combustíveis (`C_fam_TRU × (1 − share_F − share_comb)`).
Isso é uma **dupla remoção**: os pesos POF são valores ao consumidor — cheios
de impostos e margens — e sua estrutura difere da TRU, de modo que a dedução
removia da âncora magnitudes (impostos/contribuições e níveis de aluguel
imputado/serviço doméstico) que a TRU já não contém naquela proporção. A
correção remove os **produtos TRU correspondentes** diretamente no lado TRU
e usa a POF somente para (i) distribuir B_C por UF e (ii) medir π^p. O
consumo fora-do-campo residual sem produto TRU próprio (jogos, cerimônias
etc.) permanece na âncora — viés declarado **para baixo** na alíquota.

**Ajustes de base da revisão E7** (`aferir.sifim_fbcf`; alavancas `sifim=`
e `fbcf_imob=` em `base.base_ordinaria_uf`, defaults centrais do
orquestrador):

- **E7.1 — SIFIM imputado EXCLUÍDO da âncora de consumo** (central
  `sifim='excluido'`; `ajuste_sifim.csv`). A TRU 2021 aloca o SIFIM DENTRO
  do produto 64801 (Intermediação financeira, seguros e previdência —
  consumo das famílias 396,49 R$ bi 2021), sem linha explícita (convenção
  do SCN ref. 2010, verificado nas 68_tab1/tab2). O serviço imputado NÃO é
  operação onerosa (fora do campo, art. 4º); o split imputado×explícito é
  estimado por resíduo — explícito medido na POF (tarifas, juros, seguros,
  previdência = 126,24 R$ bi escalados ao nível TRU) e imputado = 270,25
  R$ bi 2021 (CONVENCAO), deduzido da âncora no nível 2021 (372,07 R$ bi no
  biênio). Efeito medido: **+1,85 p.p.** na soma; a convenção anterior
  (SIFIM na base) vira sensibilidade `sens_sifim_incluido`. Coerente com o
  regime específico de serviços financeiros (alíquota uniforme nacional,
  Regulamento do IBS art. 600 §4º, I, 'b').
- **E7.2 — redutores imobiliários do art. 261 na FBCF-NC** (central
  `fbcf_imob='redutores'`; `ajuste_fbcf_imobiliaria.csv`). A parcela
  residencial NOVA da FBCF não-corporativa (identificada por composição:
  share de Edificações/41801 na FBCF TRU × share residencial das obras
  novas na PAIC 2021 = 26,66 R$ bi 2021) recebe alíquota reduzida em 50%
  (art. 261, caput) ⇒ m efetivo 0,5, Δbase = 13,33 R$ bi 2021. Efeito
  medido: **+0,12 p.p.**; a convenção anterior vira sensibilidade
  `sens_fbcf_sem_redutores`. Redutor social (art. 259) e redutor de ajuste
  (arts. 257-258) documentados no CSV sem efeito adicional na base.

Componentes por UF (R$ bi do biênio, preços 2024; totais da execução):

```
B_C       = [C_fam_TRU − removidos − SIFIM imputado (E7.1)] × escala_consumo,
            distribuído pelos shares POF                                             = 5.789,63
B_ISFLSF  = C_ISFLSF_TRU × escala_consumo (proxy C_fam — ISFLSF não separável no
            SCN trimestral; declarado), distribuído por população municipal SICONFI  =   158,40
B_FBCF_NC = FBCF_TRU × share_NC (0,1121464; convenção v1 VTI/PIA, m=1,00,
            art. 200 §4º, vendorada) × escala_FBCF (série própria SIDRA 1846
            c93406 = 1,2492 — a escala C_fam, 1,3768, sobreestimava ~10%;
            corrigido no parecer da banca 2026-07-10), líquida do redutor
            do art. 261 (E7.2)                                                       =   209,57
B^ord     =                                                                           6.157,59
```

**Camada POF reconstruída do zero** (`inputs/pof.py`): parser do dicionário
IBGE + leitor fixed-width + anualização oficial `V8000_DEFLA × V9011 ×
FATOR_ANUALIZACAO × PESO_FINAL` com gate estrito de V9011 por quadro.
Goldens: famílias = 69.017.704 (Σ PESO_FINAL); aluguel estimado médio
R$ 606,15/mês (SIDRA t/6970); cobertura da matriz = 100,0% da despesa.
**Achado sobre o v1 (não replicado):** o derivado v1 duplicava exatamente as
10.277 linhas do quadro 19 (serviços domésticos) — o Tradutor IBGE lista os
códigos 19xxx duas vezes e o merge v1 explodia o join — inflando a despesa
POF do v1 em +R$ 62,5 bi/ano (+1,72%). Deduplicado o v1, v2 e v1 batem a
0,0 por item×UF (teste pina o artefato).

## 6. Matriz legal vendorada (proveniência κ)

`data/inputs/matriz_pof_ibs_v5.csv` — 13.474 itens POF × tratamento legal:
`m_i` em seis níveis canônicos {0; 0,30; 0,40; 0,60; 0,70; 1,00}, flag F
(fora do campo), dispositivo (`art_lc_214_v3`, `art_res_cgibs_v3`) e
justificativa item a item. Insumo **derivado-indispensável commitado** com
nota de proveniência: construída no v1 por dupla codificação independente
com confiabilidade medida **κ_m = 0,637** (substantial) e **κ_F = 0,924**
para a flag F. O leitor (`gaps.py::carrega_matriz`) valida: zero
`codigo_pof` duplicado, m_i nos seis níveis, e ≤1% da despesa sem
correspondência (a execução mede 100,0% de cobertura). Validade legal
(0 itens sem dispositivo) é invariante herdado.

π^p nacional medido = **0,2504676** (por UF: 0,1877 a 0,3279), sobre a
despesa em campo ex-combustíveis, pesos renormalizados ex-F.

**Erro de classificação quantificado (revisão E2, `aferir.classificacao`).**
O artefato da dupla codificação foi vendorado byte a byte do v1
(`data/inputs/dupla_codificacao_2026_07.csv`: amostra estratificada de 470
itens, seed 42; avaliador 2 = LLM cego ao gabarito — limitação declarada;
κ_m = 0,637, κ_F = 0,924), fechando a lacuna de replicabilidade do κ citado.
Dele derivam (i) o diagnóstico de desacordo (`classificacao_divergencias.csv`:
110 itens divergentes, 4,0% da despesa da base π); (ii) dois **envelopes
determinísticos** de π^p (`envelope_classificacao.csv`: itens divergentes com
mín/máx(m₁, m₂); divergência F×não-F pela regra do limiar, rotulados pelo
RESULTADO — `env_classificacao_aliquotas_{min,max}` na grade: −0,17/+0,13
p.p. na soma); e (iii) o sorteio de classificação do bootstrap conjunto
(§18). Cota declarada: os envelopes e o sorteio cobrem SÓ os 470 itens
amostrados — a incerteza dos itens não amostrados não é capturada
(nota de honestidade em `qa_bootstrap_classificacao.json`).

## 7. Hiato de conformidade (corredor único) — fundamento art. 15

γ ∈ **[0,10; 0,15]**, central **0,125**: corredor da NT SERT/MF jul/2024
(convenção Hungria — 10% factível, 15% conservador); o ponto 12,5% é o hiato
de neutralidade **implícito** no FMI WP/2025/266 (rótulos exatos, sem
sinonímia). Corredor **único para as três esferas**, com fundamento
estrutural e não empírico: pelo art. 15 da LC 214 a alíquota de cada
operação é a **soma** das alíquotas das esferas **sobre base única** —
conformidade é propriedade **da operação**, não da esfera. As diferenças de
evasão legadas (ISS ≠ ICMS) já vivem nos numeradores, que são receita
**realizada**. Combinação (com ZFM aditivo, só AM = 0,13):

```
π = 1 − (1 − π^p − zfm) · (1 − γ·(1−ψ))
```

Duas extensões da revisão, ambas fora do central:

- **Estresse γ = 20% (E8)**: ponto acima do teto do corredor SERT, na grade
  (`cenario_gamma = estresse`): Σ = 35,88 — mede o custo de uma conformidade
  muito pior que a convenção conservadora (+3,08 p.p. sobre o central).
- **γ heterogêneo por UF (E5, `aferir.robustez`)**: γ_uf = k·γ̄·[1 +
  β·(inf_uf − inf̄)/inf̄], com informalidade média 2024T1-2025T4 por UF
  (PNADC, SIDRA 8529, `informalidade_uf.csv`), β ∈ {0,5; 1,0} e
  renormalização k que preserva o γ médio ponderado pela base (Σ γ_uf·B_ord
  ÷ Σ B_ord = γ̄ exato — só a distribuição espacial muda). Vetores por UF
  sob γ_uf em `sens_vetores_gamma_uf.csv` (γ_uf validados em
  `sens_gamma_heterogeneo.csv`); o agregado nacional não se move por
  construção.

## 8. ψ (split payment) como cenário — nunca no central (⚑ F1)

ψ ∈ {0; 0,30; 1,0} multiplica o γ efetivo (γ_eff = γ·(1−ψ)) e é reportado
**à parte** da manchete (T3/`aferir_nacional.csv`), com a banda internacional
(Polônia/Itália/Tchéquia) comunicada declarando **o que propaga**. Efeito
medido no central iso-carga: Σ 32,80 (ψ=0) → 31,46 (ψ=0,3) → 28,70 (ψ=1).
Monotonicidade é invariante (I2).

## 9. Cashback assimétrico (arts. 112-120)

Redutor de **base** por esfera, em forma fechada (a devolução é proporcional
ao imposto pago pelos elegíveis): `cb_base_s = Σ_g pct_{s,g} · L_g`, com
g ∈ {piso, demais} e L_g = base líquida consumida pelos elegíveis.

| Esfera | Piso art. 118 (energia elétrica, água/esgoto, gás canalizado, telecom) | Demais |
|---|---|---|
| CBS | **100%** | 20% |
| IBS estadual e municipal | 20% | 20% |

- Elegibilidade (CadÚnico, renda ≤ ½ SM per capita) aproximada por
  **decis 1-3 da POF** (f_low por UF: ~3% no DF a ~35% no MA; nacional
  0,0967) — proxy declarada de dado aberto, comparável ao 1º terço do
  Cenário L da NT SERT.
- **Critério LEGAL como cenário (revisão E6)**: o subcomando
  `aferir.inputs.pof legal` recomputa f_low e share_piso sob a elegibilidade
  literal dos arts. 112-113 (renda per capita ≤ ½ SM de 15/01/2018, nos
  microdados) → `pof_elegiveis_legal_uf.csv` e `cashback_elegibilidade.csv`
  (comparação por UF: shares de famílias e de pessoas elegíveis). Na grade:
  `sens_cashback_legal` (−0,30 p.p. na soma — menos despesa elegível que os
  decis 1-3) e `sens_cashback_legal_takeup80` (take-up 80%, alavanca
  `take_up` de `cashback.cb_base`; o central mantém take-up 1,0 = concessão
  automática, art. 114). O painel CECAD/CadÚnico não tem acesso
  programático estável (diligência F17 em `metadata/diligencias_fontes.csv`)
  — a elegibilidade administrada segue ADM.
- Itens do piso identificados por descrição na matriz (regex em
  `pipeline.py::PADRAO_PISO`); **GLP é monofásico** — fora da base ad
  valorem; seu cashback ocorre no ad rem (declarado).
- `uplift_piso_low = 1,0` (share do piso na cesta dos pobres = média):
  convenção conservadora; subestima a devolução do piso ⇒ viés ↓ em τ_CBS
  (segunda ordem).
- A assimetria 100%/20% explica τ_CBS ter D_U (3.980,75) menor que
  D_E = D_M (4.005,22).

## 10. Compras governamentais medidas (G_s) e realocação federativa

`g_perimetros.csv` (grade completa esfera × UF × ano × perímetro × chave da
natureza 36 × estágio — revisão A5; `g_esferas.csv` espelha o central, 58
linhas com formula/fonte), `g_municipal_sensibilidade.csv`,
`g_mun_estratos_2023.csv`. Média janela em R$ bi 2024, perímetro central COM
natureza 36 (§2): **G_U = 102,55**
(DCA União id_ente=1, Anexo I-D, paginação ORDS 5.000/hasMore),
**G_E = 193,06** (DCA 27 UFs; SP 35,50 em 2024), **G_M = 385,06** (amostra
capitais + top-200 população — 0 sem DCA em 2024, 1 omisso em 2025 — com
extrapolação pós-estratificada por per capita de estrato populacional da
subamostra municipal fixada de 2023 (composição pinada em
`data/inputs/amostra_dca_municipal.csv`), 2.833 municípios; corredor de sensibilidade
2024: S1 escala populacional 342,6 / S2 cota inferior amostra 170,1 / S3
Liquidadas 156,9 vs. central 390,2; perímetros mín/máx 2024: 353,4/512,6).
FINBRA em lote é **inacessível
programaticamente** (JSF sob hCaptcha; sem recurso ORDS/CKAN — verificado
10/07/2026). Brasília: G integralmente na esfera estadual (DCA única do GDF,
art. 349, II, 'c'); o rateio municipal por UF usa população ex-DF. DCA =
ente consolidado (adm. direta + indireta + estatais dependentes), perímetro
declarado e coerente entre esferas. A realocação federativa da carga
embutida (hoje difusa em ICMS/PIS/Cofins de fornecedores; amanhã receita do
ente comprador via σ) é reportada como achado, não como invariante.

## 11. Construções A e B — e a ponte entre elas

| | Construção A (âncora-consistente) | Construção B (identidade) |
|---|---|---|
| Base | B\* = 12,30% PIB ÷ 26,47% = **5.555,05 R$ bi** (base realizada implícita nas âncoras oficiais da NT SERT jul/2024 — embute a conformidade observada nas declarações) | D_s: B^ord (SNA potencial) − hiatos explícitos = **3.980,75 (U) / 4.005,22 (E/M)** |
| Numeradores | R_s art. 350 **cheios** (com combustíveis; pré-cashback), MAS federal LÍQUIDO de IS estimado + IPI residual nas DUAS variantes (art. 353 §1º — o 4,47% PIB da PLDO é projeção de PIS/Cofins+IPI e também contém as parcelas que IS e IPI residual continuarão arrecadando; dedução = 20,20 R$ bi = 0,364 p.p. de B*) | Alvos ajustados (ex-combustíveis simétrico; CBS − IPI residual − IS − PIS/Cofins-comb.; pós-cashback via D) |
| Resultado | CBS 10,67 / 9,26 (âncora legal líquida-RTN / meta PLDO 4,47%) + E 14,75 + M 2,62 ⇒ Σ **28,04 / 26,63** | central γ=12,5%: CBS 13,53 + E 16,43 + M 2,84 ⇒ Σ **32,80** |
| Natureza | comparável aos exercícios oficiais (validação externa: E 14,75 ≈ TD 2530 14,7; M 2,62 vs 2,0) | **cota superior declarada** — γ incide sobre a base potencial plena |

Rotulagem obrigatória das variantes (revisão L1, regras e fundamento em
`metadata/qa_rotulos_cenarios.csv`): o rótulo "rito" pertence
EXCLUSIVAMENTE à variante do art. 353 (âncora 2012-2021, líquida-RTN); a
variante PLDO é "comparável às estimativas oficiais" — o rito apresenta-se
primeiro. A revisão E7 (SIFIM/FBCF) move só a construção B: a construção A
não usa B^ord e fica inalterada (diff zero medido em
`metadata/diff_baseline.md`).

**A ponte:** B\* é ~39% maior que D (5.555 vs ~4.000 em média) porque a base
implícita nas âncoras já desconta a não-conformidade efetivamente observada
e não separa cashback/monofasia, enquanto a construção B parte do potencial
SNA e desconta cada cunha explicitamente (π^p, γ, cashback, combustíveis,
SIFIM imputado, redutor do art. 261).
A distância Σ_B − Σ_A (32,80 − 28,04 = 4,76 p.p.) é portanto decomposição de
convenções de base — não desacordo empírico — e o invariante I3b exige
A < B em todas as variantes. O artigo reporta as duas construções lado a
lado na T1 com colunas obrigatórias de comparabilidade (valor | ano-base |
desenho legal | conceito de receita | natureza).

## 12. Vetores indicativos por UF (leitura obrigatória)

τ_E^uf (τ_M^uf) = alíquota **uniforme hipotética** que reporia a receita de
referência da esfera no conjunto de entes da UF sobre a base de destino da
UF, com as demais esferas na referência nacional (`rates.py::vetor_indicativo`)
— **não** é alíquota que o ente fixaria. Equivalente monotônico do hiato
h_uf = R_s,uf − τ_s^nac·D_uf: τ_M^uf > τ_M^nac ⟺ o share da UF no ISS
(ORIGEM, LC 116 art. 3º) excede seu share no consumo (DESTINO) ⟺ conjunto
municipal perdedor líquido bruto da municipalização, antes das retenções
(arts. 109/110) e da cota-parte (art. 128). T2 acrescenta o teste do piso de
2033 (art. 371 + Anexo XVI: 90,5% da referência) — vinculante quando a
necessidade indicativa fica **abaixo** do piso. Medianas da execução:
τ_E^uf 17,09; τ_M^uf 1,64 (extremos: τ_E AM 40,07 / DF 8,60; τ_M SP 4,59 /
AP 0,70); 16 UFs acima da referência estadual; pisos vinculantes: 7 na
esfera E e 21 nos agregados municipais (`metricas_piso.csv`; deltas contra
a linha de base justificados linha a linha em
`metadata/qa_regressoes_parecer_l7.csv`, teste bloqueante
`tests/test_regressoes_l7.py`).

## 12-A. Trava-conforme (art. 475 §§10-11) e perfis de corte (E3)

`trava.py` resolve o problema inverso do gatilho: qual encolhimento uniforme
λ dos regimes favorecidos — m_i(λ) = m_i + λ·(1−m_i), i ∉ F; zfm(λ) =
0,13·(1−λ); cashback recomputado a cada λ — fecha Σ_s τ_s = 26,5%
(bisseção em [0; 1], tol 1e-6). No γ central: **λ\* = 0,742**, vetor
trava-conforme CBS 10,93 + E 13,27 + M 2,30, custo dos benefícios suprimidos
**R$ 251,9 bi/ano** valorados às alíquotas trava-conformes (R$ 311,8 bi às
centrais — as duas convenções são reportadas); π^p pós-λ\* = 0,065. Saídas:
`trava_conforme.csv`, `trava_vetor_uf.csv`, `MANIFEST_TRAVA.json`.

O corte uniforme é convenção de implementação do PLP do §11 — a lei obriga
o projeto de lei, não o desenho da redução. `perfis_trava.py` (revisão E3)
resolve o MESMO gatilho por classe de regime (classes derivadas da própria
matriz, `gaps.classifica_regime`, + pseudo-classe zfm), com solver próprio
sobre `pipeline.executa` e λ por classe via `lam: dict` em
`gaps.policy_gap_por_uf`:

- **P1_uniforme** — validação: reproduz `trava.py` bit a bit (identidade
  testada em `tests/test_perfis_trava.py`);
- **P2_protege_essenciais** — λ = 0 em cesta/alíquota-zero, saúde-60 e
  educação-60; λ único nas demais. **INFACTÍVEL só com o §11**: nem λ = 1
  fecha em 26,5% (Σ mínimo 29,97 no γ central; coluna `status` registra);
- **P3_regressividade** — classes ordenadas pelo índice pró-rico do
  benefício (share de w·(1−m) nos decis 8-10 ÷ decis 1-3, decis nacionais
  de renda per capita da POF, `incidencia_regimes_decil.csv`); corta da
  mais pró-rica à mais pró-pobre até fechar — custo praticamente igual ao
  uniforme.

Resultados por perfil × γ em `resultados_perfis_trava.csv`
(+ `perfis_trava.csv` com os λ_c).

## 13. Convenções ⚑ (forks do DESIGN §6) com direção do viés

| ⚑ | Fork | Central adotado | Alternativa reportada | Direção do viés do central |
|---|---|---|---|---|
| F1 | split payment | ψ = 0 fora do central; corredor γ SERT | ψ ∈ {0,3; 1,0} em T3 | τ ↑ (cota superior na dimensão conformidade) |
| F2 | omissos municipais | imputação por estrato **medida e imaterial** (≤0,4% do ISS); central publica declarantes | zero-imputação (= central, na prática) | τ_M ↓ marginal (numerador sem omissos) |
| F3 | τ_M por município | **descartado** — POF identifica só até UF | — | vira fronteira OD/ADM (C3) |
| F4 | DCA 2025 parcial | usar 2024+2025 com completude medida (96,0% em 2025) | só 2024 | τ_M ↓ marginal em 2025 |
| F5 | — não alocado no DESIGN rev. 2 — | | | |
| F6 | título do artigo | T1 | T2/T3 (DESIGN §9) | n/a |
| F7 | Simples | numeradores INCLUEM receita do Simples (art. 350 §1º, I; QA em `qa_simples_numeradores.csv`), mas optantes não recolhem τ pleno ⇒ Σ declarada como **cota inferior na dimensão Simples**. A cunha foi **medida** (revisão A7/E1, `aferir.simples`): ω = 0,1037 do consumo em campo suprido por pequenas empresas (PAC/PIA/PAS 2023 × TRU, `omega_simples.csv` — cota inferior: 74,2% do consumo tem porte aberto; setores sem pesquisa contribuem 0) | cenários na grade: `com_cunha_simples` (só denominador ×(1−ω): Σ 36,40, **+3,60 p.p.**) e `com_cunha_simples_dois_lados` (numeradores subnacionais também líquidos da parcela do Simples, espelho do Regulamento art. 600: Σ 35,11) | τ ↓ (cota inferior) |
| F8 | redutor art. 370 | iso-carga, σ̂ = 8,234% por perímetro (TRU; `sigma_compras.csv`) | sem redutor (Σ 29,23) / redutor total (Σ 34,20) | intermediário; Σ central ∈ [29,23; 34,20] |
| F9 | pseudônimo | novo (AFERIDOR) — não reusar o do v1 (vincularia v2→v1→autor) | manter | n/a (anonimato) |
| F10 | submissão | v2 único | v1+v2 com pseudônimos distintos | n/a (estratégia) |

Convenções centrais adicionais (todas com Num rotulado CONVENCAO ou nota nos
CSVs): IS por proxy iso-carga de IPI fumo/bebidas/automóveis = cota INFERIOR
do IS (↑ τ_CBS; cenário IS=0 em sens_is_zero, efeito −0,442 p.p. medido;
folga mensurável da cota em sens_is_ampliado, −0,05 p.p.);
dedução PIS/Cofins-combustíveis sem etanol/biodiesel
e sem GLP granel (↑ τ_CBS); razão IOF-Seguros constante (±; sensibilidade
±25% barata); âncora federal LÍQUIDA-RTN, Tema 69 (central; bruta-RFB em
sens_ancora_bruta, efeito +0,038 p.p. — sinal empírico: parcelamentos no
caixa superam restituições); fora-do-campo residual na âncora TRU (↓ τ);
uplift_piso = 1,0
(↓ τ_CBS, 2ª ordem); alocação dos fundos estaduais proporcional ao ICMS (±,
redistribui só entre MT/MS/GO); G no perímetro central COM natureza 36
(corredor mín/máx medido: +0,24/−0,29 p.p.; chave sem-36: +0,05 p.p.);
G_M pós-estratificado com corredor S1-S3
(± via σ·G_M, 2ª ordem sobre τ_M); rateio de G_M por população municipal
ex-DF (±); ZFM só no AM, aditivo 0,13 (convenção herdada v1, χ_AM STN);
densidade GLP 0,552 t/m³ (fator oficial do Anuário ANP 2023 — substitui a
convenção 550 kg/m³ do v1); split SIFIM imputado×explícito por resíduo
POF→TRU (E7.1); parcela residencial da FBCF-NC por composição
Edificações-TRU × share PAIC (E7.2); preço de petróleo/gás por média
nacional SIMPLES entre campos do mês (IS ampliado — ponderação por volume
impossível no dado aberto); corte <20 pessoas ocupadas como proxy do teto
de receita do Simples (ω, cota inferior); vintage populacional única
(exercício 2026) para
estratos 2024-2025; ISFLSF escalada pelo C_fam (proxy — SCN trimestral não
separa ISFLSF; ±, 2ª ordem); FBCF escalada pela série própria (SIDRA 1846
c93406; a escala C_fam sobreestimava B_FBCF_NC ⇒ τ ↓ ~0,15 p.p. em Σ —
corrigido no parecer da banca de 2026-07-10). O quadro consolidado das
direções de viés, com magnitude MEDIDA por cenário, é a Tabela 5 do artigo
(`data/outputs/t5_quadro_vies.csv` = `data/processed/quadro_direcoes_vies.csv`,
gerado por `tables.py` a partir da própria grade — revisão L7/E10).

## 14. Invariantes — saída real do gate

Gate estrito (`PYTHONPATH=src python3 -m aferir.invariants`; exit 1 bloqueia;
incluído em `make all`). Os invariantes testam **correção do pipeline**
(fechamentos, triangulações, domínios), nunca o desfecho político-fiscal —
a distância ao gatilho de 26,5% (art. 475 §11) é resultado reportado, não
invariante. Saída verbatim da execução desta revisão (2026-07-12):

```
[PASS] I0 cenário central único — 1 linha(s)
[PASS] I1 ordenação do corredor γ — 31.89 < 32.80 < 33.77
[PASS] I2 monotonicidade em ψ — 32.80 > 31.46 > 28.70
[PASS] I3 Σ ∈ [20; 36] p.p. (sanidade) — Σ = 32.80
[PASS] I3b construção A < construção B (todas as esferas) — A: [28.04, 26.63] < B: 32.80
[PASS] I4 consistência RREO×DCA ≤ 1% — máx 0.000%
[PASS] I5 janela 2024-2025 completa (3 esferas) — r_estadual/r_municipal/r_uniao
[PASS] I6 cobertura DCA municipal ≥ 90% — 2024: 99.2%; 2025: 96.0%
[PASS] I7 27 UFs nos vetores — 27 UFs
[PASS] I7b mediana estadual vs agregado (< 4 p.p.) — mediana 17.09 vs 16.43
[PASS] I10a União: ref. janela vs SERT 4,47% PIB (Δ < 1,5 p.p. do PIB) — 5.24% PIB (PLDO 2025 = projeção; nossa = observada)
[PASS] I10b subnacional: (ICMS+ISS)/PIB vs SERT 7,76% (Δ < 1 p.p.) — 8.03% PIB
[PASS] I15 sensibilidades federais (IS proxy; âncora Tema 69) — IS=0: 33.25 > central 32.80; âncora bruta: 32.77
[PASS] I14 sonda municipal ao centavo (SP capital DCA×MSC; ISS-DF RREO) — SP 2024 = R$ 35,836,255,499.67; DF 2024-25 conferem
[PASS] I16 cobertura econômica DCA ≥ 99% (2024 e 2025) — 2024: 99.95%; 2025: 99.64%
[PASS] I17 grade da revisão completa (A4-A7/E2/E4-E8) — 22 cenários presentes
[PASS] I18 σ por perímetro (max ≤ central = min; domínio) — min=8.2339%, central=8.2339%, max=7.6755%

GATE: todos os invariantes PASS
```

Dezessete invariantes bloqueantes. **Novos da revisão A/E/L**: I16
(cobertura ECONÔMICA municipal ≥ 99% por exercício — a cobertura por
contagem do I6 subestima a representatividade do valor, `coverage_siconfi.csv`,
revisão A6); I17 (grade completa: cada alavanca declarada no texto tem sua
linha em `aferir_nacional.csv` — 22 rótulos de cenário obrigatórios); e I18
(σ coerente com o perímetro de G: σ_máx ≤ σ_central = σ_mín, domínio — o
perímetro máx mistura capital com carga menor). O rótulo do I4 mudou de
"triangulação" para **"consistência RREO×DCA"** (revisão A1: RREO e DCA
saem do MESMO declarante ao SICONFI — é consistência interna, não validação
externa; a validação externa fica com STN/IPEA e comparadores rotulados).
O I15 (sensibilidades federais: linhas
`sens_is_zero`/`sens_ancora_bruta` presentes; IS=0 mecanicamente MAIOR que o
central; sinal da âncora livre — empírico) entrou na revisão de 2026-07-10,
assim como o I14 (municípios-sonda: SP capital na DCA
I-C 2024 ao centavo, triangulada com a MSC/parecer; ISS-DF no RREO Anexo 03),
PROMOVIDO da suíte de testes ao gate (golden numbers em
`config.py`, fonte única do gate e dos testes). Complementos que seguem na
**suíte de testes** (269 verdes nesta revisão, incluindo o teste bloqueante
das regressões protegidas `tests/test_regressoes_l7.py` contra
`metadata/qa_regressoes_parecer_l7.csv`), não no gate: soma nacional
do ISS em ordem de grandeza STN/IPEA (espírito do I13); goldens federais
(Cofins 2021) e POF (famílias, aluguel); vigências de combustíveis e mapa
legal (`test_combustiveis_vigencias.py`, `test_legal_map.py`); determinismo
byte a byte. Pendente
do DESIGN §2.8: I12 (fechamento B^ord + G-SNA ≈ âncora TRU com dedução
declarada) — abrir no gate quando o módulo de figuras consolidar o G-SNA.

## 15. Fronteira dados abertos × administrativos (C3) — por esfera

| Esfera | Insumo do cálculo oficial | Status | Evidência / rota aberta adotada |
|---|---|---|---|
| União | IOF-Seguros por modalidade | **ADM** | verificado em 3 fontes (10/07/2026) e rediligenciado em 12/07 (ReceitaData, dados abertos RFB, dados.gov.br — diligência F5 em `metadata/diligencias_fontes.csv`): XLSX RFB = linha única; Portal da Transparência = só IOF-OURO × IOF-DEMAIS; Análise da Arrecadação dez/2025 sem quadro. O cálculo oficial usa "arrecadação observada do IOF-Seguros" (metodologia TCU/RFB, p. 6). Rota aberta: razão da NT SERT p. 3 (5,4 bi ÷ 61,2 bi), peso 0,046 p.p. de PIB na âncora. Decomposição mensal por código de receita segue indisponível em dado aberto (fronteira OD/ADM declarada) |
| União | Projeção do Imposto Seletivo (art. 353 §1º) | **ADM (inexistente)** | PLDO 2027, Anexo IV.2, p. 8 ("aguarda-se … a nova legislação acerca do Imposto Seletivo") e p. 20 (bases projetadas = tributos substituídos). Rota aberta adotada: proxy iso-carga = IPI corrente em fumo/bebidas/automóveis (XLSX RFB), cota INFERIOR do campo do art. 409 ⇒ τ_CBS segue cota superior; a projeção oficial (rito RFB→TCU, Res.-TCU 388/2026) permanece ADM |
| União | Convenção líquida de restituições por tributo (Tema 69) | **OD (achado positivo)** | RTN/STN Tabela 2.2 publica a receita por tributo líquida de restituições (conceito caixa) — dado aberto BASTA; adotada como âncora CENTRAL (5,126971% PIB). O que segue ADM: a decomposição das COMPENSAÇÕES (que nunca transitam pelo caixa) e a conciliação fina caixa×arrecadação por tributo (parcelamentos REFIS/PERT) — Δ entre as duas rotas abertas medido (+0,0127 p.p. PIB) e reportado |
| Estados | Decomposição por fundo do art. 350, II, 'b' | **ADM** | NT SERT p. 4 publica só o total (3,5 bi); nenhuma conta FETHAB/FUNDERSUL/FUNDEINFRA nas receitas DCA dos 3 estados (verificado); a metodologia oficial dos fundos é ato do CGIBS homologado pelo TCU (**art. 350, §2º, III**) |
| Estados | FECP separável | **OD (achado positivo)** | conta DCA 1.1.1.4.50.2.0 identificável em 22 UFs — dado aberto BASTA para decompor o adicional-pobreza |
| Municípios | NFS-e nacional / ADN (base fina de serviços por município) | **ADM** | acesso público ao ambiente de dados nacional retorna **HTTP 403** (exige credenciamento) — verificado 10/07/2026. Rota aberta: DCA por município (universo 5.570) |
| Municípios | Dispersão intra-UF do consumo (τ_M por município) | **ADM** | a POF identifica gasto só até a UF ⇒ τ_M^uf é agregado por construção (⚑ F3 descartado); o vetor municipal fino exigiria dado administrativo de destino |
| Todas | Elegibilidade administrada do cashback (CadÚnico) | **ADM** | painel CECAD 2.0 é PHP dinâmico sem acesso programático estável (diligência F17, 12/07/2026). Rota aberta: critério legal ≤ ½ SM recomputado nos microdados da POF (`pof_elegiveis_legal_uf.csv`, cenário E6) |
| Todas | Porte por FATURAMENTO dos optantes do Simples (por CNAE) | **ADM** | as pesquisas estruturais abertas (PAC/PIA/PAS) só publicam porte por pessoal ocupado, e não cobrem agropecuária, saúde e ensino regular privados (diligência F14; RFB por CNAE indispensável). Rota aberta: ω = 0,1037, cota inferior declarada (`omega_simples.csv`, coluna `fonte_porte` linha a linha) |
| Todas | O próprio rito de cálculo oficial | **ADM** | Regulamento do IBS (Res. CGIBS 6/2026, arts. 598-609): cálculo sobre dados protegidos por sigilo fiscal; manual TCU/RFB da CBS autolimita-se ("não abrangendo … o IBS"). A rotina AFERIR é o espelho público desse rito — crosswalk módulo a módulo em `metadata/crosswalk_metodologia.csv` |
| Todas | Base realizada por declarações (ECF/NF-e) usada pelo oficial | **ADM** | aproximada em A pela base implícita nas âncoras (B\*) e em B pelo corredor γ sobre a base SNA |

As diligências de fonte da revisão (o que foi procurado, onde, quando e com
que desfecho) estão consolidadas em `metadata/diligencias_fontes.csv`; o
mapa dispositivo→norma citada, verificado contra os HTMLs compilados do
Planalto (`aferir.fetch.planalto`), está em `metadata/legal_map.csv`
(teste `tests/test_legal_map.py`).

## 16. Limitações (com direção do viés)

1. **IS por proxy iso-carga** no alvo da CBS — o proxy (IPI corrente em
   fumo/bebidas/automóveis, 17,60 R$ bi) é cota INFERIOR do IS ⇒ τ_CBS
   ainda superestimada (↑), mas menos que sob IS=0 (efeito medido −0,442
   p.p.); a folga mensurável da cota (minerais + petróleo/gás no teto do
   art. 422 §2º) vale −0,05 p.p. (`sens_is_ampliado`); a projeção oficial
   segue fronteira ADM. Sobreposição
   proxy×IPI-residual-ZFM não separável em dado aberto (≤ 2,6 R$ bi, ↓).
2. **Simples (F7)** — Σ é cota inferior nessa dimensão (↓); cunha MEDIDA
   ω = 0,1037 (ela própria cota inferior: 25,8% do consumo em campo sem
   pesquisa de porte aberta contribui zero) ⇒ cenário +3,60 p.p. na grade;
   banda externa +2,43/+3,4 p.p. (IMB-GO/CNI) segue citada como contraste.
3. **Construção B = cota superior de nível** (↑): γ aplicado sobre base
   potencial SNA plena; a leitura de nível deve usar a construção A e os
   comparadores rotulados.
4. **2026 ausente da âncora subnacional** (arts. 361-365 pedem média
   2024-2026) — direção indeterminada (±), declarada; janela 2024-2025
   (sensibilidade só-2024 medida: −0,06 p.p.).
5. **Estrutura de consumo POF 2017-18 / TRU 2021 escalada** — shares de UF e
   π^p com vintage defasado (±); a estacionariedade base/PIB implícita na
   comparação com o gatilho de 2033 é nomeada e estressada pelos extremos
   da década (E4, `sens_base_pib.csv`: +1,18/−0,70 p.p.).
6. **G_M extrapolado** de amostra (FINBRA bloqueado por hCaptcha) — corredor
   S1-S3 largo (156,9-390,2 R$ bi 2024, perímetro central); efeito de 2ª
   ordem via σ·G_M, maior sobre τ_M; corredor de perímetro mín/central/máx
   reportado à parte (A5).
7. **Fora-do-campo residual na âncora TRU** (jogos, cerimônias, sem produto
   TRU próprio) — base levemente sobreestimada ⇒ τ ↓.
8. **Razão IOF-Seguros constante** e **ad rem federal com adesão
   generalizada assumida** — (±), pesos pequenos e declarados.
9. **Elegibilidade do cashback por decis POF** (proxy do CadÚnico) e
   uplift_piso = 1,0 — cb subestimado no piso ⇒ τ_CBS ↓ (2ª ordem);
   critério legal ½ SM e take-up 80% medidos como cenários (E6: −0,30 e
   −0,38 p.p. respectivamente).
10. **Vetores por UF são indicativos** — alíquota uniforme hipotética de
    reposição, não previsão de alíquota fixada; dispersão intra-UF municipal
    fica fora do alcance de dados abertos (item da fronteira, não defeito
    do estimador).
11. **Erro de classificação da matriz legal** — envelopes determinísticos
    (−0,17/+0,13 p.p.) e bootstrap conjunto cobrem SÓ os 470 itens da
    amostra de dupla codificação; a incerteza dos 13.004 itens não
    amostrados não é capturada (±, declarado — §6 e §18); o avaliador 2 da
    dupla codificação é um LLM cego ao gabarito, não um segundo codificador
    humano (limitação declarada em `aferir.classificacao`).
12. **SIFIM imputado por resíduo** (E7.1) — split imputado×explícito
    depende da escala POF→TRU declarada; sensibilidade de escala (IPCA)
    reportada no próprio `ajuste_sifim.csv`; o ISS financeiro que deixaria
    o numerador municipal na mesma lógica tem break-even medido (2,8% do
    ISS) e segue fronteira ADM.

## 17. Proveniência e determinismo (mecânica)

- `provenance.Num` = (valor, formula, fonte, label, unidade); rótulos
  fechados em Enum; `Manifest.registra` recusa proveniência conflitante para
  a mesma chave; `MANIFEST_RUN.json` é gerado do grafo da execução (indent
  estável, chaves ordenadas) — a banca do v1 encontrou proveniência
  desatualizada escrita à mão; aqui isso é estruturalmente impossível.
- `_seed_manifest.json`: sha256 de cada arquivo bruto lido (TRU zip, IPCA,
  RREO-ICMS, DCA estaduais, ANP…), com caminho RELATIVO à raiz do repo —
  o replicador externo refaz `data/raw/` com `make fetch` (fetchers
  públicos em `fetch/*.py`, sem credencial) e audita a coleta pelos hashes.
- `datetime` só nos fetchers (`_meta.json`, `collected_at`); nenhuma fonte
  de aleatoriedade no caminho central; `SEED = 42` para bootstrap/MC da
  camada de incerteza (DESIGN §2.7). Re-execução de `make all` verificada
  **byte-idêntica** nos artefatos versionados.

## 18. Incerteza amostral (banda bootstrap POF)

`uncertainty.py` → `data/processed/banda_incerteza.csv`. Bootstrap de
conglomerados da POF 2017-18: reamostragem de UPAs (`COD_UPA`) dentro de
estratos (`ESTRATO_POF`) com reescalonamento de Rao & Wu (1988), B = 500
réplicas, `numpy.Generator(seed 42)` — determinístico. **O que a banda
propaga é declarado** (correção da crítica E2 do v1): SOMENTE a incerteza
amostral da POF que entra no pipeline via π^p_uf e f_low_uf, recomputados
réplica a réplica; todo o resto fica fixo no cenário central ⇒ a banda é
**cota inferior** na dimensão dos componentes propagados. Hedge declarado:
o Rao-Wu reamostra UPAs mantendo o `PESO_FINAL` pós-estratificado fixo (sem
re-calibração por réplica) — aproximação padrão cujo erro não é assinado;
irrelevante na escala do resultado (0,25 ≪ 1,88 p.p.). Resultado (p5-p95): Σ
[32,69; 32,94] p.p. — largura 0,25 p.p., contra 1,88 p.p. do corredor de
conformidade γ.

**Decomposição amostragem × classificação (revisão E2,
`make motor` roda `uncertainty --classificacao`).** Além da banda amostral
canônica, `roda_bootstrap_decomposto` reporta a soma sob TRÊS fontes, mesma
B = 500: (i) **amostragem** — Rao-Wu com classificação central fixa (largura
0,25 p.p.); (ii) **classificação** — pesos plenos fixos e, por réplica, cada
item DIVERGENTE da amostra de dupla codificação recebe a leitura do
codificador 1 ou 2 com probabilidade ½ (RNG PCG64 de fluxo independente;
largura 0,25 p.p.); (iii) **conjunto** — ambos na mesma réplica (largura
0,35 p.p.). Saídas: `qa_bootstrap_classificacao.json` (parâmetros, regra de
sorteio, agregados de desacordo e nota de honestidade) e o espelho CSV
`banda_incerteza_decomposta.csv` (placeholders do manuscrito); cota
declarada: o sorteio cobre só os 470 itens amostrados. Leitura obrigatória:
a incerteza dominante do exercício é de
**convenção** (γ, F7, F8), não amostral nem de classificação — as bandas
nunca se somam em um único intervalo.
