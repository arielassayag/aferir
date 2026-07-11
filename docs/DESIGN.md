# DESIGN v2 — As Três Alíquotas da Federação

**Artigo:** *As Três Alíquotas da Federação: calibração ex-ante das alíquotas de
referência da CBS e do IBS e o equilíbrio interfederativo sob dados abertos*
(título T1; alternativas em §9).
**Alvo:** 31º Prêmio Tesouro Nacional 2026 — Artigos em Finanças Públicas, Tema 3
(Federalismo Fiscal e Equilíbrio Interfederativo). Deadline 17/08/2026, 23h59.
**Status:** rev. 3 (2026-07-12) — rev. 2 incorporou o parecer adversarial de
4 lentes (jurídica, dados, método, PTN); a rev. 3 incorpora a revisão
profunda dos pareceres A1-A9/E1-E10/L1-L7 (`super_documento_revisao.md`;
decisões de desenho novas em §10). Forks ⚑.
**Relação com o v1:** `~/IBS/Code` e `maniscrito.docx` INTACTOS. O v2 vive em
`~/IBS/v2/` (git próprio) e reconstrói código e texto do zero.

---

## 0. Por que reformular (diagnóstico)

1. **O vácuo é real e reconhecido pela fonte oficial.** O manual TCU/RFB da CBS
   autolimita-se ("não abrangendo temas correlatos, como o IBS"); nenhuma fonte
   publica o split estadual×municipal do IBS (TD 2530 e CCiF só agregados por
   esfera). Em 10/07/2026 o Senado não fixou nenhuma alíquota de referência
   (ciclo CBS-2027: RFB→TCU até 14/09/2026, Res.-TCU 388/2026); a 1ª resolução
   do IBS só no ciclo 2028. O artigo antecipa publicamente, com dados abertos,
   o que o rito oficial produzirá sob sigilo fiscal.
2. **Tema 3 pede federação, não uma esfera.** Subtemas 1-5 cobertos; a alíquota
   por operação é a SOMA estadual+municipal no destino (LC 214, art. 15).
3. **Precedente no PTN.** Reforma já premiada (1º/2024 EGC; 3º/2025 Alcântara e
   Silva). Diferenciação ancorada no eixo robusto: **ele toma a alíquota como
   parâmetro dado; nós a calculamos como objeto** (frases prontas em §5.1).

## 1. Tese e contribuições (TRÊS manchetes)

**Tese:** sob a EC 132, a suficiência fiscal de cada ente deixa de depender da
própria base e passa a depender de três alíquotas de referência fixadas
nacionalmente sobre uma base única. Com dados 100% abertos é possível antecipar
a ordem de grandeza das três referências e medir, ente a ente, a tensão
federativa que a referência única terá de absorver. O que os dados abertos NÃO
alcançam é demarcado com precisão — a fronteira OD/ADM é resultado.

- **C1. As três alíquotas** — primeira estimativa pública tri-esfera (τ_CBS,
  τ_E, τ_M) sob a arquitetura legal (arts. 349-369, red. LC 227), com os
  vetores indicativos por ente (27 τ_E^uf; 27 τ_M^uf agregados) como MEIO;
  inclui o split estadual×municipal inédito.
- **C2. O equilíbrio interfederativo quantificado** — hiato de reposição por
  UF sob referência única (quem depende das retenções 109/110), teste do piso
  81%/90,5% (art. 371/Anexo XVI), concentração do ISS (Lorenz municipal) com
  contrafactual de destino: a redistribuição embutida na municipalização.
- **C3. A fronteira dados abertos × administrativos** — transversal: quadro
  OD/ADM por esfera na metodologia + exibições empíricas (NFS-e/ADN 403;
  IOF-seguros sem decomposição aberta; fundos §2º III; Res. CGIBS 6 arts.
  598-609 sob sigilo).
- Validação (não contribuição): crosswalk módulo-a-módulo com a metodologia
  TCU/RFB da CBS — painel de ⅓ de página no corpo, tabela completa em Anexo.

## 2. Arquitetura metodológica

### 2.1 Motor único, três esferas

Espelho legal (arts. 350-369) define numeradores e âncoras; motor de identidade
converte em alíquota. As três esferas compartilham: base B (legislação única),
matriz POF×LC 214 (13.474 itens, m_i idênticos), expurgos v3.4, convenção do
aluguel (v5-22), janela legal. Diferenças:

| Dimensão | CBS (União) | IBS estadual | IBS municipal |
|---|---|---|---|
| R_s (art. 350) | PIS+Cofins+IPI+IOF-seguros | ICMS bruto + fundos art. 350,II,'b' | ISS (municípios **e DF**) |
| Alvo ancorado | média 2012-2021 %PIB **− IS − IPI residual** (art. 353) | média 2024-2026 (arts. 361-365) | média 2024-2026 |
| §1º art. 350 | + Simples | + Simples + FECP (ADCT 82 §1º) | + Simples + FECP-ISS (ADCT 82 §2º) |
| Fonte de R | XLSX RFB 1994-2025 + IPEADATA | SICONFI RREO (v1 route) | SICONFI DCA municipal + RREO-DF |
| Cashback (art. 118) | 100% piso + 20% demais | 20% uniforme | 20% uniforme |
| Regionalização | nacional | 27 UFs | nacional + 27 (agregados) |

**Compras governamentais (arts. 472-473) — módulo comum às TRÊS esferas:**
nas aquisições do ente, as alíquotas dos demais zeram e a alíquota do
comprador = SOMA das três, pós-redutor (art. 473 §1º). Logo G sai da base
ordinária de todas as esferas e vira termo próprio:

    R_s = τ_s·D_s + σ·G_s^aq,   com σ = (τ_U + τ_E + τ_M) − redutor
    D_s = B^ord·(1−π) − CB_s;   B^ord = C_POF + ISFLSF + FBCF_NC  (sem G)

Sistema LINEAR 3×3 nas τ — resolvido em forma fechada. G_s^aq = naturezas de
compra (3.3.90.30/36/39) APENAS — folha está fora do campo (art. 4º; mesmo
fundamento da flag F). O fechamento SNA da base nacional (invariante) usa
G-SNA separado do G-473 (papéis distintos, declarados). Redutor art. 370:
central = iso-carga (carga atual sobre compras públicas estimada via TRU:
impostos sobre produtos × mix de absorção do governo); sensibilidade: sem
redutor e redutor total. A realocação federativa (carga embutida hoje pertence
a Estados/União; amanhã ao comprador) é reportada — achado federativo per se.

### 2.2 Hiato de conformidade e ψ (F1 — resolvido)

Central: corredor **da NT SERT (convenção Hungria)** [10%; 15%], ponto 12,5% =
hiato de neutralidade **implícito** no FMI WP/2025/266 — rótulos exatos.
Corredor ÚNICO para as três esferas com fundamento estrutural: pelo art. 15 a
alíquota da operação é a soma sobre base única; conformidade é propriedade DA
OPERAÇÃO, não da esfera (evasões legadas ISS≠ICMS vivem nos numeradores, que
são receita realizada). ψ (split payment) fora do central; cenários {0; 0,3; 1}
com banda Polônia/Itália/Tchéquia reportada à parte; toda banda comunicada
declara o que propaga (corrige E1/E2 do v1). Reverse Method sobre C-eff ICMS
mantido como cota superior estadual diagnóstica.

### 2.3 Receitas de referência (numeradores)

- **União:** séries PIS+Cofins+IPI+IOF 2012-2021 e 2024-2025. Rota primária:
  XLSX "Arrecadação das receitas federais 1994-2025" (gov.br/receitafederal;
  testado HTTP 200, hash congelado). Fallback: IPEADATA OData4, SERCODIGOs
  pinados SRF12_COFINS12/SRF12_PIS12/SRF12_IPI12/SRF12_IOF12 (mensais,
  anualizar por soma; Cofins 2021 = 286.499,3 R$ mi — bate com RFB).
  **IOF-seguros:** não há decomposição aberta máquina-legível → razão
  IOF-seguros/IOF-total de quadro publicado (página citada) aplicada ao total
  aberto; registrado como ponto OD/ADM da esfera federal (C3).
  **Tema 69 dentro da âncora — RESOLVIDO (2026-07-10):** a convenção líquida
  por tributo existe ABERTA (RTN/STN, Tabela 2.2, conceito caixa líquido de
  restituições) e é o CENTRAL (5,1270% PIB); bruta-RFB (5,1143%) =
  sensibilidade em aferir_nacional.csv (coluna ancora_federal); Δ medido
  +0,0127 p.p. PIB (líquida > bruta — parcelamentos REFIS/PERT no caixa;
  sinal empírico, reportado). Nota: a âncora
  2012-2021 repõe carga HISTÓRICA por decisão legal — τ_CBS não é comparável
  1:1 com exercícios ancorados em receita corrente (SERT/FMI); dito no texto.
  **Alvo CBS** = âncora×PIB(base) − IS_estimado − IPI_residual (art. 353 §1º;
  IS por proxy iso-carga de dado aberto: IPI corrente em fumo/bebidas/
  automóveis, XLSX RFB — cota inferior do campo do art. 409 + Anexo XVII,
  17,60 R$ bi na janela; IS=0 vira sensibilidade, coluna is_cenario; a
  projeção oficial segue ADM — o "0,13% PIB do FMI" é cashback, não IS).
- **Estados:** rota v1 (RREO Anexo III rubrica ICMS; triangulação RREO×DCA;
  janela 2024-2025 deflacionada, 2026 indisponível declarado) **+ FECP**
  (ADCT 82 §1º — contas SICONFI de fundo de combate à pobreza, mapeadas e
  documentadas) **+ fundos art. 350, II, 'b'**: valorados pela fórmula do
  §2º, II (média arrecadada 2021-2023 × variação do ICMS da UF), excluídas
  contribuições migradas ao ADCT 136 (§2º, I); metodologia oficial dos fundos
  é do CGIBS homologada pelo TCU (§2º, III) = marcador OD/ADM. Simples-ICMS:
  já dentro da rubrica SICONFI (verificar conta e documentar).
- **Municípios:** DCA municipal via API SICONFI (testada: ~1 req/s, 11.140
  chamadas ≈ 3,1 h, ~0,5 GB; concorrência ≤4 com backoff; medida real do
  design review). Numerador = conta **1.1.1.4.51.1.0 apenas** — já consolida
  principal, multas e dívida ativa (art. 350 §1º, III; verificado AO CENTAVO
  contra MSC dez/2024 SP: 33.458,0+463,7+1.655,6+258,9 = 35.836,3 R$ mi).
  Convenção de coluna: Receitas Brutas Realizadas − Outras Deduções (líquida
  de restituições; Deduções-FUNDEB não se aplicam ao ISS) — invariante testa.
  **+ ISS do DF somado a R_M** (art. 350, III: "Municípios e do Distrito
  Federal"; fonte RREO-DF, 2024 = R$ 3,47 bi; DF no vetor estadual só com
  ICMS; referência do DF = soma, art. 349, II, 'c'). Fernando de Noronha:
  ISS nas contas de PE (ADCT art. 15, CF); alíquota municipal do IBS em
  Noronha exercida por PE (LC 214 art. 14 §1º). FECP-ISS (ADCT 82 §2º, até
  0,5 p.p.): mapear contas; se imaterial, declarar. Omissos: imputação
  conservadora (população × mediana do estrato da UF) com sensibilidade
  zero-imputação (⚑ F2). Validação externa: STN Boletim + IPEA CC60
  (ISS ~R$ 107 bi 2022). De-para de ementário 2021↔2022 SÓ para a análise
  histórica (Lorenz/transição), fora do caminho crítico do numerador.

### 2.4 Base de destino (denominadores)

Herda a construção v1 (TRU 2021 nível 68 escalada ao biênio; POF 2017-18 com
V9011; expurgos v3.4; ISFLSF pop; FBCF_NC via VTI/PIA; combustíveis
ex-monofásicos ANP×ad rem) com generalizações:
1. **B^ord sem G** (movido ao módulo art. 473, §2.1). Invariante I12 fecha a
   soma: B^ord + G-SNA ≈ âncora TRU (com dedução declarada).
2. **Simples (⚑ F7):** os numeradores INCLUEM receita do Simples (art. 350
   §1º, I), mas optantes não recolherão τ_s pleno. Central = Σ declarada como
   **cota inferior na dimensão Simples**, com banda +2,43 p.p. (IMB-GO) /
   +3,4 p.p. (CNI) citada na Tabela-manchete; sensibilidade paramétrica com
   cunha θ = participação dos optantes no consumo final (calibrada de
   estatística aberta RFB do Simples, se localizável; senão só a banda).
3. Municípios agregados: dispersão intra-UF NÃO identificável (POF para em
   UF) — declarado como fronteira (C3); ⚑ F3 (τ_M por município) descartado.

### 2.5 Saídas canônicas

1. τ_CBS (ponto + corredor); 2. τ_E nacional + vetor 27; 3. τ_M nacional +
vetor 27; 4. Σ vs gatilho de revisão de 26,5% (art. 475 §§9-13 — GATILHO de
PLP, não teto; objeto = referências estimadas de 2033) e vs comparadores;
5. painel federativo (hiato por UF; piso art. 371; Lorenz ISS com
contrafactual de destino; realocação do módulo art. 473).

**Tabela-manchete com colunas obrigatórias:** valor | ano-base | desenho legal
simulado (PEC 45 × LC 214/227) | conceito de receita reposta | natureza
(estimado × assumido × ilustrativo). Rótulos: CCiF = "decomposição ilustrativa
(shares 2015)"; FMI 28% = "alíquota assumida (resolve hiato implícito 12,5%)";
TD 2530 = "estimativa PEC 45, ano-base 2016"; SERT = "estimado, LC 214,
pós-cashback". Sem isso a validação externa vira falsa concordância.

### 2.6 Leitura do vetor municipal (obrigatória no texto)

τ_M^uf = alíquota uniforme hipotética que reporia o ISS agregado dos
municípios da UF sobre a base de destino da UF; equivalente monotônico do
hiato h_uf = R_ISS,uf − τ_M^nac·D_uf. τ_M^uf > τ_M^nac ⟺ share da UF no ISS
(ORIGEM, LC 116 art. 3º) excede share no consumo (DESTINO) ⟺ conjunto
municipal da UF perdedor líquido bruto da municipalização, antes das
retenções 109/110 e da cota-parte art. 128 (80% pop/10% educ/5% amb/5% igual).

### 2.7 Incerteza

Corredor de conformidade = banda principal determinística. Bootstrap POF (PSU,
B=500, seed 42; Rao-Wu sobre pesos finais — hedge na METODOLOGIA §18) → IC de
π^p e f_low; MC conjunto descartado (a decomposição por fonte já comunica as
larguras); ψ como cenário discreto à parte; larguras decompostas por fonte
na comunicação. [Alinhado à entrega na revisão 2026-07-10.] Rev. 3 (E2):
terceira fonte comunicada à parte — erro de CLASSIFICAÇÃO da matriz legal
(dupla codificação vendorada; envelopes determinísticos na grade + bootstrap
decomposto amostragem × classificação × conjunto, mesma B=500; cota
declarada: só os 470 itens amostrados são perturbados).

### 2.8 Invariantes (gate estrito)

Herda do v1: aritmética 1e-6; fechamento TRU; domínios; validade legal da
matriz (0 itens sem dispositivo); hash reprodutível; triangulação RREO×DCA
≤1%; ordenação de cenários. Novos: I10 reconciliação DECOMPOSTA por esfera
(âncora federal vs 4,47% PIB SERT; subnacional vs 7,76% — janelas distintas
declaradas, não soma única); I12 fechamento G; I13 ISS agregado SICONFI×STN
≤2%; I14 match ao centavo DCA×MSC em municípios-sonda. **Sanity-gate único:**
Σ ∈ [24; 30]. Distância ao gatilho 26,5% é RESULTADO REPORTADO, não invariante.
(O sanity-gate implementado desde a primeira execução é Σ ∈ [20; 36] — o
[24; 30] acima era intervalo de plano, pré-execução.) Rev. 3: I4 renomeado
"consistência" (RREO×DCA é intra-declarante — A1); novos I16 (cobertura
econômica municipal ≥ 99%), I17 (grade da revisão completa: 22 rótulos de
cenário obrigatórios em `aferir_nacional.csv`) e I18 (σ coerente com o
perímetro de G). Saída verbatim na METODOLOGIA §14.

## 3. Dados

| Insumo | Rota | Status |
|---|---|---|
| DCA municipal 2024-2025 (5.570) | fetcher API SICONFI, ≤4 conc. | novo; ~3,1 h; fallback FINBRA-agregado se não fechar até 25/07 |
| RREO estadual 2024-2025 | fetcher próprio (`fetch.siconfi_rreo`) | internalizado; hash registrado |
| RFB federal 1994-2025 | XLSX gov.br (primária) + IPEADATA (fallback) | novo; testado 200 |
| G federal | DCA/RREO União id_ente=1 **com paginação** (5.000/hasMore) | novo |
| POF microdados, TRU 68, SIDRA, ANP/CONFAZ | fetchers próprios (`fetch.pof/tru/sidra_ipca/anp`; CONFAZ = tabela curada em data/inputs) | internalizados; derivados reconstruídos no v2 |
| Matriz POF×IBS v5 | **commitada** em `v2/data/inputs/` c/ proveniência (κ=0,637/0,924) + exceção no .gitignore | insumo declarado |

Replicabilidade: ZERO symlink/caminho $HOME; clone limpo + `make fetch && make
all` reproduz hashes (critério de aceite); insumos derivados-indispensáveis
commitados com nota de proveniência.

## 4. Código v2

```
v2/src/aferir/
  config.py provenance.py           # prontos
  fetch/{siconfi_municipal,siconfi_estadual,siconfi_uniao,rfb_federal,ibge,anp}.py
  inputs/{pof,tru,siconfi,ipca_pib,matriz}.py
  base.py revenue.py gaps.py cashback.py govpurchases.py rates.py
  uncertainty.py invariants.py tables.py figures.py manuscript.py
tests/  (≥100 asserts; golden numbers POF: aluguel 606,15; famílias 69.017.704;
         DCA×MSC ao centavo; âncoras vs valores publicados)
```

Padrões mantidos: determinismo byte-idêntico; zero número digitado no
manuscrito; proveniência Num; MANIFEST gerado do grafo. O gerador DOCX é o
ÚNICO entregável (sem fork manual).

## 5. Artigo (≤20 pp corpo; 3 contribuições anunciadas)

1. Introdução (2,5) — inclui §5.1 diferenciação:
   > "Alcântara e Silva (2025) estima, com dados FINBRA e projeções até 2032,
   > o impacto da transição ICMS/ISS→IBS sobre a arrecadação municipal,
   > tomando a alíquota do IBS como parâmetro dado […]. Este artigo ocupa o
   > elo anterior dessa cadeia: calcula, sob dados exclusivamente abertos e
   > replicando a arquitetura legal do cálculo oficial (arts. 349-369), as
   > três alíquotas de referência que aquele estudo toma como dadas —
   > inclusive o split estadual×municipal inédito — e quantifica, ente a
   > ente, a tensão federativa que a referência única terá de absorver."
2. Arquitetura legal e literatura (3) · 3. Metodologia (4,5) · 4. Resultados
(5) · 5. Discussão federativa (3) · 6. Conclusão (1,5). Anexos fora do limite:
matriz legal; receitas por ente; sensibilidades; crosswalk TCU completo;
reprodutibilidade (espelho ANÔNIMO, sem URL pessoal).

## 6. Forks abertos

| ⚑ | Fork | Default | Alternativa |
|---|---|---|---|
| F1 | central sem ψ | resolvido (corredor SERT) | flag ψ=0,30 |
| F2 | omissos municipais | imputar + sensibilidade | zero-imputação |
| F4 | DCA 2025 parcial | usar 2024+2025 medindo completude | só 2024 |
| F7 | Simples | resolvido na rev. 3: cunha MEDIDA ω = 0,1037 (`aferir.simples`, porte IBGE × TRU, cota inferior); central segue cota inferior declarada | cenários na grade: `com_cunha_simples` (+3,60 p.p.) e `com_cunha_simples_dois_lados` (numeradores líquidos, espelho do Regulamento art. 600) |
| F8 | redutor art. 370 | iso-carga via TRU | sem redutor / redutor total |
| F9 | pseudônimo | NOVO (não reusar BANDEIRANTE-FISCAL: vincula v2→v1→autor, ativa 9.9) | manter |
| F10 | submissão | v2 único (estratégia, não regra: item 4.4 PERMITE >1 artigo/autor) | v1+v2 com pseudônimos distintos |

## 7. Cronograma com gates (38 dias)

- **20/07**: dados congelados com hash (fallback municipal aciona 25/07)
- **03/08**: pipeline + invariantes verdes
- **08/08**: manuscrito gerado ≤20 pp
- **08-12/08**: banca simulada + correções
- **13/08**: espelho anônimo + varredura de metadados (docx core/app.xml E
  PNGs tEXt/EXIF; Word regrava metadados a cada save — incidente v1)
- **14/08**: submissão (3 dias de folga; nunca depender do item 4.18)

## 8. Definition of Done

- `make fetch && make all && make manuscript && pytest` verdes em clone limpo;
  invariantes PASS; Σ ∈ [24;30] explicada comparador a comparador.
- DOCX ≤20 pp corpo, Resumo/Abstract ≤150 palavras, Arial 12/1,5, margens
  3/2 cm, figuras ≥300 DPI, refs ABNT lista única, anônimo (metadados docx +
  PNGs varridos), espelho anônimo publicado e citado no Anexo D.
- Banca simulada (critérios 9.15) sem achado alto CONFIRMED aberto.

## 9. Títulos candidatos (⚑ F6)

- **T1 (default):** As Três Alíquotas da Federação: calibração ex-ante das
  alíquotas de referência da CBS e do IBS e o equilíbrio interfederativo sob
  dados abertos
- T2: Federalismo fiscal sob alíquota única: as três alíquotas de referência
  da reforma tributária do consumo e o equilíbrio interfederativo com dados
  abertos
- T3: Equilíbrio interfederativo na reforma tributária do consumo:
  decomposição federativa das alíquotas de referência da CBS e do IBS
  estadual e municipal sob restrição de dados abertos

## 10. Revisão A/E/L (rev. 3, 2026-07-12) — decisões de desenho

A revisão profunda (pareceres A1-A9, E1-E10, L1-L7; plano e critérios de
aceite em `super_documento_revisao.md`) foi implementada sob quatro decisões
de desenho, todas voltadas a preservar o contrato "mesmos insumos ⇒ mesmos
bytes":

### 10.1 Alavancas no orquestrador, não forks de código

Cada correção que muda o cálculo virou **parâmetro nomeado** de
`pipeline.monta_insumos`/`pipeline.executa`, com default = CENTRAL do
artigo: `g_perimetro`/`natureza36` (A5), `sifim` (E7.1), `fbcf_imob`
(E7.2), `escala_base` (E4), `cashback_criterio`/`take_up` (E6),
`matriz` (E2, envelopes), `janela` (A6), `gamma_uf` (E5), `omega_cunha` e
`deduz_simples_alvos` (A7/E1), `is_estimado` (A4) e `lam` como
float-ou-dict (E3, λ por classe). Consequências: (i) o central é UMA
chamada sem argumentos — auditável no próprio docstring, que documenta
alavanca a alavanca; (ii) toda alternativa é executável pelo mesmo caminho
de código (nenhum branch morto); (iii) módulos de medição (`classificacao`,
`sifim_fbcf`, `is_ampliado`, `simples`, `robustez`) só PRODUZEM insumos e
diagnósticos — o flip do central é decisão exclusiva do orquestrador.

### 10.2 Grade de sensibilidades como contrato

Princípio da rev. 3: **toda convenção qualitativa do texto ganha magnitude
medida pelo próprio pipeline**, como linha rotulada de
`aferir_nacional.csv` (22 rótulos de cenário; I17 bloqueia a grade
incompleta). A rotulagem tem regra escrita (`metadata/qa_rotulos_cenarios.csv`
— "rito" só para o art. 353; hierarquia de apresentação) e o quadro de
direções de viés (T5, `tables.py::t5_quadro_vies`) é GERADO da grade —
nunca escrito à mão, mesmo padrão do MANIFEST.

### 10.3 Ordem do Makefile e convergência dos re-baselináveis

`make motor` executa os medidores ANTES do pipeline (`classificacao` →
`sifim_fbcf` → `is_ampliado` → `simples`) porque eles produzem insumos que
o pipeline consome (envelopes de matriz, `ajuste_sifim.csv`/
`ajuste_fbcf_imobiliaria.csv`, IS ampliado, ω); depois `pipeline`,
`uncertainty --classificacao` (decomposição E2), `trava` → `perfis_trava`
(P1 valida a identidade bit a bit com a trava uniforme), `robustez
--vetores` (γ_uf pondera pela `base_uf.csv` recém-gravada), `cashback`,
`distribuicao`, `tables` e `invariants` (gate bloqueante). As COLUNAS DE
EFEITO em p.p. dos medidores são aproximações de 1ª ordem contra a grade
CORRENTE — declaradas **re-baselináveis** nos docstrings: após qualquer
mudança de central, uma reexecução de `make all` converge os artefatos
(na segunda passada, mesmos insumos ⇒ arquivos byte-idênticos, critério de
aceite inalterado).

### 10.4 `metadata/` como camada de QA da revisão

Linha de base congelada ANTES da primeira correção (Onda 0:
`baseline_revisao.json`, run pinado por sha256 dos manifestos) e diff
automatizado ao final (`diff_baseline.md`, com atribuição do movimento da
manchete por correção); regressões intencionais protegidas linha a linha
(`qa_regressoes_parecer_l7.csv` + teste bloqueante); verificação legal
(`legal_map.csv` contra os HTMLs pinados do Planalto), diligências de
fontes com desfecho datado (`diligencias_fontes.csv`), crosswalk com a
metodologia TCU/RFB (`crosswalk_metodologia.csv`) e checagem
citações×referências (`qa_citacoes_referencias.csv`). Nada em `metadata/`
entra no cálculo — é evidência de auditoria, separada de `data/`.
