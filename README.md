# AFERIR — Alíquotas Federativas de Referência sob Insumos Replicáveis

Rotina **pública, auditável e replicável** que antecipa, com dados
exclusivamente abertos, a ordem de grandeza das **três alíquotas de
referência** criadas pela EC 132/2023 — CBS (União), IBS estadual e IBS
municipal — replicando a arquitetura legal do cálculo oficial
(LC 214/2025 e LC 227/2026, arts. 349-369 e 472-473), que o rito
Senado/TCU/CGIBS produzirá sob sigilo fiscal.

Este repositório é o **espelho de replicação** do artigo *"As Três Alíquotas
da Federação: calibração ex-ante das alíquotas de referência da CBS e do IBS
e o equilíbrio interfederativo sob dados abertos"* (pseudônimo **AFERIDOR**;
31º Prêmio Tesouro Nacional 2026, Tema 3 — Federalismo Fiscal e Equilíbrio
Interfederativo). O repositório é mantido sob pseudônimo para preservar a
avaliação cega do certame.

## Replicação em três comandos

Ponto de partida: **(a)** durante a avaliação cega, baixe o repositório
inteiro pela vista anônima (botão de download, arquivo zip) e extraia;
**(b)** fora do cegamento, `git clone` deste repositório. As duas vias
carregam exatamente os mesmos arquivos. Em seguida:

```bash
pip install -e ".[dev]" -c requirements.lock   # Python >= 3.12 (lock = ambiente da verificação byte a byte)
make fetch        # completa os dados brutos (rede SÓ para a POF, ~210 MB; nenhuma credencial)
make all          # pipeline determinístico: brutos -> processados -> alíquotas -> gate de invariantes
make manuscript   # gera figuras e o manuscrito DOCX (zero número digitado no texto)
```

TODOS os insumos brutos, exceto um, **acompanham o repositório com vintage
congelada** e sha256 nos `_meta.json`/`SHA256SUMS`: os pequenos (SICONFI,
RFB, STN, SIDRA — inclusive porte empresarial e informalidade —, TRU, ANP
vendas/produção/preços, ANM, textos legais compilados do Planalto e do
CONFAZ, malha) como arquivos diretos, e as
**DCAs estaduais** (189 arquivos, 2019-2025) e a **subamostra municipal de
DCAs** (14.192 arquivos, 2019-2023) como snapshots arquivísticos em
`data/raw/siconfi_estadual/snapshot/` e
`data/raw/siconfi_municipal_dca/snapshot/` — o fetcher remonta, verifica o
sha256 pinado e extrai **sem rede**.
A única baixa de rede do `make fetch` são os microdados da POF 2017-2018
(FTP público do IBGE, ~210 MB comprimidos), verificados byte a byte contra
os hashes pinados em `data/raw/pof/_meta.json`.

Por que snapshot, e não refetch da API? Instabilidade **medida** da fonte
viva: entre a coleta (maio/2026) e a verificação (julho/2026), 1 par pinado
foi retirado da API do SICONFI e 12 de 13.377 reconferidos voltaram
retificados na origem. O snapshot congela a vintage usada pelo artigo; a
rota de API permanece implementada como re-derivação documentada
(`aferir.fetch.siconfi_municipal_dca`), com falha ruidosa para pares
retificados.

Complementares: `make test` (suíte pytest, offline) e `make verify`
(= `all` + `test`). O repositório versiona os derivados determinísticos em
`data/processed/`, de modo que `make all` também serve de **verificação**: a
reexecução deve reproduzir os mesmos arquivos. Aferição na publicação do
espelho (2026-07-12), em clone limpo deste repositório com ambiente virtual
novo (`requirements.lock`) e `make fetch` real: os 38 arquivos então
versionados de `data/processed/`, as 7 figuras, as 4 tabelas e o próprio
`MANUSCRIPT.docx` reproduzidos **byte a byte**, com o gate de invariantes
integral e a suíte de testes verde. A revisão A1-A9/E1-E10/L1-L7 (ver
`docs/CHANGELOG.md` e `metadata/diff_baseline.md`) ampliou `data/processed/`
para 65 artefatos e a suíte para 269 testes verdes, sob o mesmo critério de
aceite. Hashes sha256 de todos os insumos brutos ficam em
`data/processed/_seed_manifest.json`
e nos `_meta.json` de cada domínio de `data/raw/`. Critério de aceite:
mesmos insumos ⇒ mesmos outputs (semente única `SEED = 42` para as rotinas
estocásticas de incerteza; nenhum `datetime` fora dos fetchers).

### Fontes de dados (todas abertas, sem credencial)

| Insumo | Fonte pública | Fetcher |
|---|---|---|
| Arrecadação federal 1994-2025 (XLSX) | RFB, gov.br (dados abertos) | `aferir.fetch.rfb_federal` |
| Resultado do Tesouro Nacional (série histórica) | STN, Tesouro Transparente | `aferir.fetch.rfb_federal` |
| IPCA (número-índice, SIDRA 1737) | IBGE, API SIDRA | `aferir.fetch.sidra_ipca` |
| PIB e CNT (SIDRA 1846: PIB, consumo, FBCF; série 2015-2025 p/ base/PIB) + malha das UFs | IBGE, API SIDRA / API Malhas v3 | `aferir.fetch.ibge` |
| TRU 2021 nível 68 (zip XLS) | IBGE, Contas Nacionais (FTP) | `aferir.fetch.tru` |
| POF 2017-2018 (microdados fixed-width) | IBGE, FTP oficial | `aferir.fetch.pof` |
| Vendas de derivados por UF (m³) | ANP, dados abertos | `aferir.fetch.anp` |
| Textos legais compilados (LC 214, LC 227, EC 132, CF/ADCT) | Planalto (HTML integral, sha pinado) | `aferir.fetch.planalto` |
| Porte empresarial 2023 (PAC 1399, PIA 1839, PAS ×7) — ω do Simples | IBGE, API SIDRA | `aferir.fetch.ibge_porte` |
| Informalidade por UF 2024T1-2025T4 (PNADC, SIDRA 8529) — γ heterogêneo | IBGE, API SIDRA | `aferir.fetch.ibge_informalidade` |
| DCA União (Anexo I-D) | SICONFI/Tesouro, API pública | `aferir.fetch.siconfi_uniao` |
| DCA estaduais 2019-2025 (27 UFs) | SICONFI, API pública | `aferir.fetch.siconfi_estadual` |
| RREO Anexo 03 (ICMS 2024-2025; ISS-DF) | SICONFI, API pública | `aferir.fetch.siconfi_rreo` |
| DCA municipal: ISS universo 2024-2025 | SICONFI, API pública | `aferir.fetch.siconfi_municipal` |
| DCA municipal: amostra G (capitais+top-200) | SICONFI, API pública | `aferir.fetch.siconfi_municipal_g` |
| DCA municipal: subamostra fixada 2019-2023 | snapshot arquivístico VERSIONADO (partes em `data/raw/siconfi_municipal_dca/snapshot/`, sha256 pinado; release e API SICONFI como rotas alternativas) | `aferir.fetch.siconfi_municipal_dca` |

Brutos pinados **sem fetcher próprio** (baixados uma vez, com sidecar
`_meta.json` registrando URL, data e sha256): Anuário Mineral Brasileiro da
ANM e produção/preços de referência da ANP (`data/raw/anm/`,
`data/raw/anp_producao/` — cenário IS ampliado), arrecadação do Simples
Nacional da RFB (`data/raw/rfb/sn_arrecadacao_ate_jan26.xlsx`), informe
CadÚnico do MDS (`data/raw/mds/`) e os atos do CONFAZ, decretos federais,
Ementário STN e resoluções TCU/CGIBS em `data/raw/normas/`.

Insumos **curados** (não-fetcháveis por natureza) são versionados em
`data/inputs/` com dispositivo legal ou proveniência linha a linha: matriz
POF×LC 214 (`matriz_pof_ibs_v5.csv`, 13.474 itens com artigo citado),
tabelas de **vigências** das alíquotas ad rem — ICMS/CONFAZ
(`icms_adrem_vigencias.csv`, 6 convênios com período e URL) e PIS/Cofins
(`pis_cofins_combustiveis_vigencias.csv`, Decreto 5.059/2004 e alteradores)
—, dupla codificação da matriz legal (`dupla_codificacao_2026_07.csv`,
amostra de 470 itens, κ_m = 0,637), comparadores externos
(`comparadores.csv`), composição pinada da subamostra municipal
(`amostra_dca_municipal.csv`, 14.192 pares município×ano) e convenções
declaradas (`fbcf_v1_uf.csv`, `is_ipi_residual.csv`).

## Princípios (critérios de verificação obrigatórios)

1. **Publicidade** — fontes e código acessíveis sem credencial privada.
2. **Auditabilidade** — cada número rastreável a fonte + transformação:
   todo CSV processado carrega colunas `formula` e `fonte`; todo agregado
   central vira um `Num` (valor, fórmula, fonte, rótulo
   OFICIAL/DADO/DERIVADO/CONVENCAO) no `MANIFEST_RUN.json`, gerado do
   próprio grafo de execução — nunca escrito à mão.
3. **Replicabilidade** — determinismo; zero caminho absoluto de máquina;
   zero `datetime`/`random` fora dos fetchers e da semente 42.
4. **Fronteira dados abertos × administrativos (OD/ADM)** — onde o dado
   aberto basta e onde o dado administrativo é indispensável é **resultado**
   do artigo, demarcado esfera a esfera (ver
   [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md)).

## Estrutura do repositório

```
.
├── Makefile                  # contrato de replicação (fetch / dados / all / manuscript / test / verify)
├── pyproject.toml            # pacote `aferir` (Python >= 3.12)
├── docs/
│   ├── DESIGN.md             # decisões de arquitetura (pós-parecer adversarial)
│   ├── METODOLOGIA.md        # peça de auditabilidade completa, passo a passo
│   ├── CHANGELOG.md          # história do projeto com hashes de commit
│   └── artigo/               # fontes Markdown do manuscrito ({{csv:...}} = zero número digitado)
├── src/aferir/
│   ├── config.py             # ÚNICO lugar de caminhos, janelas legais e constantes (com fonte)
│   ├── provenance.py         # Num/Label/Manifest — proveniência como estrutura de dados
│   ├── fetch/                # rede: RFB, STN, IBGE (SIDRA/TRU/POF/malhas/porte/informalidade),
│   │                         #   ANP, SICONFI, Planalto (textos legais)
│   ├── inputs/               # brutos -> processados: pof (+ subcomando `legal`), tru, uniao,
│   │                         #   siconfi_estadual, ipca_pib, combustiveis, gov_aquisicoes, seed
│   ├── base.py               # B^ord por UF (TRU 2021 escalada; shares POF; alavancas sifim/fbcf_imob)
│   ├── gaps.py               # hiato de política π^p (matriz legal) e combinado (γ, ψ, ZFM)
│   ├── classificacao.py      # E2 — dupla codificação κ e envelopes de classificação POF×LC 214
│   ├── sifim_fbcf.py         # E7 — SIFIM imputado (âncora de consumo) e redutores do art. 261
│   ├── is_ampliado.py        # A4 — folga da cota inferior do IS (minerais ANM; petróleo/gás ANP)
│   ├── simples.py            # A7/E1 — cunha ω do Simples (porte IBGE × TRU) + QA dos numeradores
│   ├── cashback.py           # art. 118 — redutor de base assimétrico por esfera (take-up E6)
│   ├── govpurchases.py       # arts. 472-473 — G por esfera; perímetros A5; redutor art. 370
│   ├── revenue.py            # receitas de referência e alvos por esfera (art. 350; vigências A2/A3)
│   ├── rates.py              # sistema linear tri-esfera e vetores indicativos
│   ├── pipeline.py           # orquestrador (grade de 22 cenários; MANIFEST; metricas.csv)
│   ├── uncertainty.py        # banda amostral POF + decomposição E2 (bootstrap Rao-Wu, B=500, seed 42)
│   ├── trava.py              # art. 475 §§10-11 como problema inverso (λ*)
│   ├── perfis_trava.py       # E3 — perfis alternativos de corte da trava (P1/P2/P3)
│   ├── robustez.py           # E4/E5 — base/PIB da década; γ heterogêneo por UF (PNADC)
│   ├── distribuicao.py       # distribuição legal do produto do IBS em 2033
│   ├── tables.py             # tabelas canônicas T1-T5 (data/outputs/; T5 = quadro de vieses)
│   ├── figures.py            # 7 figuras do manuscrito (PNG 300 dpi determinísticos)
│   ├── manuscript.py         # gerador DOCX (renderizador puro de docs/artigo/)
│   └── invariants.py         # gate estrito de invariantes (exit 1 bloqueia)
├── metadata/                 # QA da revisão: legal_map, diligências de fontes, crosswalk TCU,
│                             #   rótulos de cenário, citações×referências, regressões L7,
│                             #   baseline_revisao.json + diff_baseline.md
├── tools/                    # utilitários locais (extração de fontes tipográficas)
├── data/
│   ├── inputs/               # insumos vendorados COM proveniência (matriz legal, vigências, dupla codificação)
│   ├── raw/                  # brutos pinados (pequenos); os 2 volumosos fora do git (hashes nos _meta.json)
│   ├── processed/            # derivados determinísticos VERSIONADOS + MANIFEST_RUN.json
│   └── outputs/              # MANUSCRIPT.docx, t1-t5.csv, figures/
└── tests/                    # suíte pytest (golden numbers, determinismo byte a byte, contratos)
```

## Resultados centrais (dados 2024-2025)

O pipeline reporta **duas construções** — a diferença entre elas é achado
metodológico, não ruído (ponte completa na seção 3 do artigo e em
[`docs/METODOLOGIA.md`](docs/METODOLOGIA.md)):

| Construção / cenário | τ_CBS | τ_E | τ_M | Σ (p.p.) |
|---|---:|---:|---:|---:|
| **B — central** (γ = 12,5%, ψ = 0, redutor iso-carga) | 13,53 | 16,15 | 2,85 | **32,53** |
| B — corredor de conformidade (γ = 10% … 15%; estresse 20%) | | | | 31,89 … 33,77 |
| **A — âncora federal legal 2012-2021 (líquida-RTN)** | 10,67 | 14,75 | 2,62 | **28,04** |
| **A — meta federal PLDO (4,47% PIB)** | 9,26 | 14,75 | 2,62 | **26,63** |
| **Trava-conforme** (art. 475 §11 como problema inverso) | | | | **26,50** |

O central da construção B incorpora as duas rodadas de revisão por parecer
(A1-A9/E1-E10/L1-L7 e R1-R8): SIFIM imputado fora da âncora de consumo,
redutores imobiliários do art. 261, perímetro ampliado de compras
governamentais, deduções ad rem mensais de combustíveis e, na segunda
rodada, a dedução simétrica do ICMS ad valorem do etanol hidratado do alvo
estadual (LC 214, art. 172, VI: o EHC é monofásico e sai da base e do alvo;
achado da auditoria adversarial de nível, `metadata/auditoria_nivel_2026_07_13.md`)
e a imputação municipal somada ao alvo. Atribuição completa em
`metadata/diff_baseline.md`; a construção A não muda. A grade de
`data/processed/aferir_nacional.csv` tem 22+ cenários (envelopes de
classificação, base/PIB mín/máx da década, cashback pelo critério legal de
½ SM com take-up 80%, janela só-2024, IS ampliado, cunha do Simples em um e
em dois lados, perímetros de G, γ de estresse); as direções de viés de cada
convenção estão em `data/outputs/t5_quadro_vies.csv`.

O nível da soma foi submetido a uma **auditoria adversarial** (seis
verificadores céticos, um por alavanca, com refutação cruzada): cinco
alavancas confirmadas adequadas com validação externa por dado aberto (o
resíduo do SIFIM imputado é coberto pelo FISIM-PF calculado das séries do
Banco Central; as âncoras de consumo batem em precisão de máquina com o bruto
do IBGE e a API viva do SIDRA), e um único achado material corrigido (o
etanol hidratado acima). A validação externa CONFAZ×RREO (`qa_confaz_vs_rreo.csv`,
boletim de arrecadação do dados.gov.br) fecha com desvio mediano de 0,46% em
2024 e 0,36% em 2025 após pontes documentadas de dívida ativa e FECP.

A trava-conforme responde: quais são as três referências compatíveis com o
gatilho de 26,5% se o PLP corretivo que a própria lei prescreve encolher os
regimes favorecidos uniformemente? Resposta: λ = 0,710 (suprimir 71,0% dos
favorecimentos, R$ 241 bi/ano valorados às alíquotas trava-conformes; a
elasticidade de λ à soma, cerca de 12 pontos de corte por ponto, é o número
de política relevante, em `metricas_trava.csv`).
Perfis alternativos de corte em
`data/processed/resultados_perfis_trava.csv`: P2 (protege
cesta/saúde/educação) é INFACTÍVEL só com o §11; P3 (por regressividade do
benefício) fecha em 26,5% com custo próximo do uniforme. Vetores
indicativos por UF, piso de fixação do art. 371 (90,5% da referência) e
distribuição legal de 2033 (suficiência mediana 97,9%) em `data/outputs/` e
no artigo.

## Verificação

```bash
make verify
# -> gate de invariantes: todas as checagens [PASS]; suíte pytest verde
```

O gate cobre, entre outros: triangulação RREO×DCA ao ponto percentual,
cobertura municipal ≥ 90% (e cobertura ECONÔMICA ≥ 99% por exercício — I16),
janelas completas nas três esferas, sonda ao centavo (ISS da capital
paulista DCA×MSC; ISS-DF via RREO), ordenação do corredor γ e
monotonicidade em ψ, as sensibilidades federais declaradas, a completude da
grade de 22 cenários da revisão (I17) e a coerência do σ por perímetro de
compras governamentais (I18). Incerteza amostral da POF (bootstrap de
conglomerados Rao-Wu) em `data/processed/banda_incerteza.csv`, decomposta
em amostragem × classificação × conjunto (B = 500) em
`data/processed/banda_incerteza_decomposta.csv` e
`qa_bootstrap_classificacao.json`: a incerteza dominante é a de convenção
(corredor γ), não a amostral nem a de classificação.

## Tipografia das figuras

As figuras usam Helvetica Neue, que é fonte proprietária e **não é
redistribuída** neste repositório. Em macOS, `make fontes` extrai os quatro
pesos da coleção do sistema para `assets/fonts/` (requer `fonttools`); sem
eles, `aferir.style` usa DejaVu Sans como fallback declarado — os números e
o texto do manuscrito não mudam; apenas a tipografia das figuras.

## Documentação

| Documento | Conteúdo |
|---|---|
| [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md) | peça de auditoria: nomenclatura, sistema 3×3, receitas por dispositivo e conta, convenções com direção do viés, invariantes, fronteira OD/ADM, limitações |
| [`docs/DESIGN.md`](docs/DESIGN.md) | decisões de arquitetura e forks |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | história com hashes de commit |
| `metadata/` | QA da revisão A/E/L: mapa dispositivo→norma verificado nos HTMLs do Planalto (`legal_map.csv`), diligências de fontes com data e desfecho (`diligencias_fontes.csv`), crosswalk módulo a módulo com a metodologia TCU/RFB (`crosswalk_metodologia.csv`), regras de rotulagem dos cenários (`qa_rotulos_cenarios.csv`), checagem citações×referências (`qa_citacoes_referencias.csv`), regressões protegidas com justificativa (`qa_regressoes_parecer_l7.csv`, teste bloqueante) e a linha de base congelada do diff (`baseline_revisao.json` + `diff_baseline.md`) |

## Licença e citação

Código sob licença MIT (ver `LICENSE`). Os dados brutos pertencem às fontes
públicas citadas; os derivados em `data/` carregam proveniência linha a
linha. Para citar, use `CITATION.cff` (autoria sob pseudônimo AFERIDOR até o
fim da avaliação cega do certame).
