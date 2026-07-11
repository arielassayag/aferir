# ANEXO A. MATRIZ LEGAL POF×LC 214 E VETORES POR ENTE

Nota de precisão: os anexos reportam saídas do pipeline com duas casas
decimais (ou mais, quando o artefato o exigir); no corpo do artigo, a
precisão editorial é de uma casa decimal, compatível com a incerteza
decomposta na seção 4.5.

A matriz classifica cada um dos 13.474 itens de despesa da POF 2017-2018 em
um dos seis níveis de tributação da LC 214/2025, com $m \in \{0; 0{,}30; 0{,}40; 0{,}60; 0{,}70; 1{,}00\}$, ou como fora do campo de
incidência (flag F, arts. 4º e 6º), sempre com o dispositivo legal citado
item a item. A classificação passou por auditoria exaustiva em nove
domínios e por dupla codificação cega em duas amostras complementares:
uma amostra estratificada de 470 itens, recodificada por um segundo
avaliador cego ao gabarito (κ de Cohen de 0,637 nos níveis e de 0,924 na
flag F; 10,8% da despesa da base do hiato de política), e uma amostra
dirigida pelo peso, que recodificou todo item da metade superior da
despesa dessa base (κ de 0,90 nos níveis). A amostra combinada, de 516
itens, cobre 53% da despesa da base, com κ de 0,66 nos níveis e de 0,80
na flag F; a despesa dos itens efetivamente divergentes equivale a 10,7%
dessa base, com exposição item a item, com
dispositivo e despesa, no arquivo `classificacao_divergencias.csv`. A
incerteza resultante propaga-se por duas vias: envelopes determinísticos,
que fixam todas as divergências no menor ou no maior nível de tributação
(cenários de classificação na grade da Tabela C.2, artefato
`envelope_classificacao.csv`), e bootstrap conjunto, que, em cada réplica
Rao-Wu da POF, sorteia a classificação de cada item divergente entre os
dois codificadores com probabilidade 1/2, regra de desempate declarada
(artefato `qa_bootstrap_classificacao.json`). A incerteza dos itens não
amostrados não é capturada por nenhuma das vias, mas fica delimitada à
cauda de itens de baixo peso individual, cerca de 47% da despesa da base,
cada item abaixo de 0,4% dela (seção 4.5). A matriz completa, com dispositivo e
justificativa por item,
acompanha o espelho de replicação (Anexo D), no arquivo
`data/inputs/matriz_pof_ibs_v5.csv`.

[[TAB:t2_vetores_uf.csv|Vetores por UF: necessidade indicativa, alíquota mínima de fixação sob o piso de 2033 e teste de vinculação do piso (art. 371)
|colunas=uf,tau_E_uf_pp,tau_M_uf_pp,tau_E_exequivel_pp,tau_M_exequivel_pp,piso_vinculante_E,piso_vinculante_M
|rotulos=uf:UF;tau_E_uf_pp:τ estadual indicativo (p.p.);tau_M_uf_pp:τ municipal indicativo (p.p.);tau_E_exequivel_pp:τ estadual mínimo de fixação (p.p.);tau_M_exequivel_pp:τ municipal mínimo de fixação (p.p.);piso_vinculante_E:Piso vincula (E)?;piso_vinculante_M:Piso vincula (M)?
|fmt=pt
|fonte=elaboração própria a partir de SICONFI/DCA, RREO, POF 2017-2018 e TRU 2021; piso de 90,5% sobre a referência central da construção B (LC 214/2025, art. 371 e Anexo XVI). Os vetores são a necessidade contrafactual do regime permanente, não previsão de alíquota nem de perda. O Distrito Federal acumula as competências estadual e municipal (art. 14, IV) e aparece nas duas esferas.]]

[[TAB:t4_distribuicao.csv|Distribuição legal do produto do IBS em 2033 e suficiência por ente (agregados por UF)
|colunas=uf,esfera,receita_referencia,recebido_legal,suficiencia_pct
|rotulos=uf:UF;esfera:Esfera;receita_referencia:Receita de referência (R$ bi);recebido_legal:Recebido pela distribuição legal (R$ bi);suficiencia_pct:Suficiência (%)
|fmt=pt
|fonte=elaboração própria a partir de SICONFI/DCA 2019-2025, RREO e base de destino (ADCT, arts. 131-132; LC 227/2026, arts. 109-117 e 128).]]

# ANEXO B. RECEITAS DE REFERÊNCIA POR ESFERA

Os numeradores correspondem à média da janela 2024-2025, em bilhões de reais
de 2024, com os valores de 2025 deflacionados pelo IPCA. As âncoras de 2021
são escaladas ao biênio por séries nominais próprias das Contas Nacionais
Trimestrais (SIDRA 1846): o consumo das famílias, pelo fator
{{csv:metricas.csv:chave=escala_bienio:valor:.4f}}, aplicado também às
ISFLSF; e a formação de capital, pelo fator
{{csv:metricas.csv:chave=escala_bienio_fbcf:valor:.4f}}. A composição por
esfera é a seguinte. União: PIS/Pasep, Cofins, IPI e IOF-Seguros por razão
declarada, com alvo ancorado na média de 2012 a 2021 (art. 353, convenção
líquida do RTN) e dedução do IS estimado por carga equivalente, do IPI
residual e da parcela de combustíveis. Estados: ICMS bruto do RREO, que já
contém o FECP, com identidade verificada contra a DCA em 54 de 54 pares
UF-ano, menos a receita ad rem estimada por ANP e CONFAZ, mais os fundos do
art. 350, II, "b". Municípios: conta 1.1.1.4.51.1.0 dos 5.569 municípios,
mais o ISS do Distrito Federal. Os arquivos `r_uniao.csv`,
`r_uniao_liquida.csv`, `r_estadual.csv` e `r_municipal_uf.csv` do espelho
trazem cada componente com fórmula e fonte por linha.

As duas deduções de combustíveis operam mês a mês, com tabelas de
vigências no espelho. Na federal, os volumes mensais da ANP são valorados
pelas alíquotas ad rem do Decreto 5.059/2004 e atos alteradores vigentes
em cada mês, aplicadas às frações fósseis das misturas vigentes no mês
(E27/E30 e B14/B15, Resoluções CNPE nº 8/2023 e nº 9/2025); o GLP
doméstico em recipientes de até 13 kg entra à alíquota zero, e o QAV não é
deduzido, por simetria com a sua permanência na base
(`deducao_federal_combustiveis_mes.csv`). Na estadual, a tabela de
vigências é construída dos Convênios ICMS 199/2022 (diesel/biodiesel e
GLP/GLGN) e 15/2023 (gasolina e etanol anidro), dos reajustes dos
Convênios 126/2024 e 127/2024, com efeitos em fevereiro de 2025, e das
orientações do CONFAZ de fevereiro e março de 2025; a mistura comercial
integral entra no ICMS, contra a fração fóssil na dedução federal
(`deducao_icms_adrem_uf_mes.csv`). O etanol hidratado, monofásico (LC
214, art. 172, VI) e ainda fora dos convênios ad rem, é deduzido à parte,
mês a mês: volumes ANP vezes o preço médio de revenda ao consumidor
(ANP-SLP) vezes a carga ad valorem de ICMS vigente na UF, com tabela de
vigências de ato citado linha a linha
(`icms_etanol_hidratado_vigencias.csv`): 17 UFs têm ato específico para o
etanol hidratado (alíquota própria, base reduzida ou carga por crédito outorgado) e 10
permanecem na alíquota modal declarada; as trocas dentro da janela, em
MG, MA, RN e PI, são datadas por ato, com o detalhe mensal em
`deducao_icms_etanol_uf_mes.csv` e o agregado por UF em
`deducao_icms_etanol_uf.csv`.

A inclusão do Simples Nacional nos numeradores é demonstrada por exaustão
no Ementário da Receita Orçamentária (edições 2024 e 2025): o documento
único do regime inclui o ICMS e o ISS e seu produto é repassado ao ente
titular (LC 123/2006, arts. 13 e 22); a varredura mostra que todas as
naturezas de receita que citam o Simples são contribuições federais, sem
natureza própria para ICMS-Simples ou ISS-Simples, de modo que as
naturezas consolidadas usadas nos numeradores já contêm essas parcelas,
com reconciliação por exercício contra os quadros públicos do regime em
`qa_simples_numeradores.csv`
({{csv:qa_simples_numeradores.csv:item=icms_simples_vs_numerador&ano=2024:share_pct:.0f}}%
do ICMS e
{{csv:qa_simples_numeradores.csv:item=iss_simples_vs_numerador&ano=2024:share_pct:.0f}}%
do ISS em 2024).

Sobre o universo municipal: o endpoint de entes do SICONFI traz 5.570
entes municipais porque inclui Brasília; o painel da DCA usa os 5.569
municípios, e Brasília entra à parte, pela rubrica própria de ISS do RREO
distrital (linha própria, universo de um ente); as contagens de cobertura
somam os dois universos. A cobertura municipal
é separada por exercício em `coverage_siconfi.csv`: em 2024,
{{csv:coverage_siconfi.csv:ano=2024:n_declarantes:,.0f}} declarantes da
peça primária (DCA) e {{csv:coverage_siconfi.csv:ano=2024:n_imputados:.0f}}
imputados; em 2025,
{{csv:coverage_siconfi.csv:ano=2025:n_declarantes:,.0f}} e
{{csv:coverage_siconfi.csv:ano=2025:n_imputados:.0f}}; a MSC e o RREO
distrital são as peças de validação, e há sensibilidade sem imputação.
Restringir a janela ao exercício de 2024, o único já ratificado, mantém a
soma das referências praticamente inalterada, de
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:soma_pp:.2f}}
para
{{csv:aferir_nacional.csv:cenario_gamma=sens_janela_2024&psi=0&modo_redutor=iso_carga:soma_pp:.2f}}
pontos (Tabela C.2).

Consistência interna e validação externa são reportadas em separado. Os
invariantes RREO×DCA×MSC validam o pipeline e a coerência das
autodeclarações do próprio ente ao SICONFI, não a exatidão econômica do
valor declarado (seção 3.5). A validação externa tem o seguinte estado.
Para o ICMS, o confronto com o Boletim de Arrecadação dos Tributos
Estaduais do CONFAZ foi executado sobre o arquivo do conjunto de dados
abertos oficial (dados.gov.br, extração de 23/06/2026, vintage "com
pendências" declarada no cabeçalho; obtido pela interface do catálogo,
com a rota de coleta manual documentada no espelho): o desvio mediano por
UF-ano é de
{{csv:qa_confaz_vs_rreo.csv:uf=BR&ano=2024&estatistica=mediana_ano:desvio_pct:.2f}}%
em 2024 e
{{csv:qa_confaz_vs_rreo.csv:uf=BR&ano=2025&estatistica=mediana_ano:desvio_pct:.2f}}%
em 2025, e cai a
{{csv:qa_confaz_vs_rreo.csv:uf=BR&ano=2024&estatistica=mediana_ano:desvio_pos_ponte_pct:.2f}}%
e
{{csv:qa_confaz_vs_rreo.csv:uf=BR&ano=2025&estatistica=mediana_ano:desvio_pos_ponte_pct:.2f}}%
após duas pontes conceituais documentadas: a dívida ativa, que o boletim
reporta em separado e o RREO consolida, e o FECP, de tratamento
heterogêneo por UF no boletim (o Rio de Janeiro fecha de
{{csv:qa_confaz_vs_rreo.csv:uf=RJ&ano=2024:desvio_pct:.1f}}% para
{{csv:qa_confaz_vs_rreo.csv:uf=RJ&ano=2024:desvio_pos_ponte_pct:.2f}}%
quando o adicional é deduzido do RREO). As pendências de carga da própria
vintage (meses incompletos em SC) são declaradas caso a caso em
`qa_confaz_vs_rreo.csv`. A abertura por produto do boletim, que
reconciliaria as deduções de combustíveis, termina em 2023 e segue
fronteira de dados abertos: a ponte pela CNAE do recolhedor foi avaliada
e é indefensável, porque a CNAE não identifica o produto. Para o ISS, o
agregado nacional é confrontado com a
publicação Carga Tributária no Brasil (CTB/RFB) como teste de agregação do
pipeline, com origem comum declarada: a própria CTB apura o ISS a partir
das declarações ao SICONFI, o que a torna teste de coerência, e não fonte
independente.

# ANEXO C. COMPARADORES, CENÁRIOS E SENSIBILIDADES

[[TAB:t1_manchete.csv|Alíquotas de referência estimadas e comparadores externos
|colunas=fonte,total_pp,cbs_pp,ibs_estadual_pp,ibs_municipal_pp,ano_base_dados,desenho_legal,natureza
|rotulos=fonte:Fonte;total_pp:Total (p.p.);cbs_pp:CBS (p.p.);ibs_estadual_pp:IBS estadual (p.p.);ibs_municipal_pp:IBS municipal (p.p.);ano_base_dados:Ano-base;desenho_legal:Desenho legal;natureza:Natureza
|fmt=pt
|fonte=elaboração própria a partir de SICONFI, RREO, POF 2017-2018, TRU 2021, RFB e ANP/CONFAZ; comparadores conforme a coluna Fonte; conceito e corredor de cada comparador no arquivo t1_manchete.csv do espelho (Anexo D). Cada componente é arredondado de forma independente a partir do valor pleno, de modo que a soma dos componentes exibidos pode diferir do total exibido em um centésimo (artefato de arredondamento, não de cômputo).]]

As quatro linhas AFERIR da tabela diferem apenas nas hipóteses seguintes,
detalhadas na seção 3.

- **Construção B, cenário central (identidade sobre dados abertos).** Base
  potencial de destino TRU 2021/POF (consumo das famílias, ISFLSF e FBCF
  não corporativa com o redutor imobiliário do art. 261; SIFIM imputado
  excluído); conformidade de 12,5% no corredor [10%; 15%]; sem split
  payment; redutor de compras públicas por carga equivalente; G no
  perímetro central da seção 3.3; cashback do
  art. 118 em forma fechada (decis 1-3, take-up 100%); IS por aproximação
  de carga do IPI (cota
  inferior do IS, logo CBS em cota superior); âncora federal líquida-RTN de
  2012 a 2021; sem cunha do Simples na base. Leitura de cota superior nas
  dimensões de base e de conformidade e de cota inferior na dimensão do
  Simples.
- **Trava-conforme (construção B com o PLP redutor do art. 475, §11).**
  Hipóteses idênticas às da construção B central, mais o mecanismo
  corretivo da própria lei: regimes favorecidos encolhidos uniformemente em
  λ = {{csv:trava_conforme.csv:cenario_gamma=central:lambda:.3f}} até a
  soma de 26,5% exatos, ao custo anual de R$
  {{csv:trava_conforme.csv:cenario_gamma=central:custo_beneficios_rs_bi:.0f}}
  bilhões em benefícios suprimidos.
- **Construção A, comparável às oficiais (meta federal do PLDO).** Os mesmos
  numeradores do art. 350 aplicados à base efetiva implícita nas âncoras
  oficiais (meta de 12,30% do PIB dividida por 26,47%, NT SERT de julho de
  2024, base já líquida de conformidade, favorecimentos e cashback), com a
  parcela federal na projeção corrente do PLDO. Leitura comparável à
  literatura.
- **Construção A, rito do art. 353 (âncora federal legal de 2012 a
  2021).** Idêntica à variante da meta do PLDO, com a parcela federal
  reposta pela média histórica que
  o art. 353 determina, a qual embute a carga do IPI e o regime anterior ao
  Tema 69.

[[TAB:t3_cenarios.csv|Grade de cenários: conformidade (corredor, estresse e hiato nulo), split payment, redutor e perímetro de compras governamentais, cunha do Simples, cashback, SIFIM e FBCF, base/PIB, classificação, IS ampliado e janela
|colunas=cenario_gamma,psi,modo_redutor,tau_CBS_pp,tau_E_pp,tau_M_pp,soma_pp
|rotulos=cenario_gamma:Cenário;psi:ψ (split payment);modo_redutor:Modo do redutor;tau_CBS_pp:CBS (p.p.);tau_E_pp:IBS estadual (p.p.);tau_M_pp:IBS municipal (p.p.);soma_pp:Soma (p.p.)
|fmt=pt
|fonte=elaboração própria a partir de SICONFI, RREO, POF 2017-2018, TRU 2021, RFB, ANP/CONFAZ, IBGE (PAC/PIA/PAS, PNAD Contínua e Contas Nacionais Trimestrais) e ANM.]]

O perfil de corte da trava (seções 3.4 e 4.5) é parametrizado por classe
de regime (cesta a alíquota zero, reduções de 60%, de 40% e de 30% e
demais regimes), com bisseção determinística fechando a soma em 26,5% e
benefícios valorados às alíquotas trava-conformes (a valoração às
alíquotas centrais consta do artefato `resultados_perfis_trava.csv`). P1
aplica λ uniforme a todas as classes; P2 protege integralmente a cesta e
os regimes essenciais e concentra o corte nas demais classes, ficando
infactível mesmo com a supressão integral delas (soma de
{{csv:resultados_perfis_trava.csv:perfil=P2_protege_essenciais&gamma=0.125:soma_pp:.1f}}
pontos no γ central); P3 ordena as classes pela incidência nos decis de
renda e corta das mais pró-ricas às mais pró-pobres, fechando em 26,5 com
composição nacional quase idêntica à de P1 e maior dispersão dos vetores
por ente (coeficiente de variação estadual de
{{csv:resultados_perfis_trava.csv:perfil=P1_uniforme&gamma=0.125:cv_vetor_E:.0%}}
para
{{csv:resultados_perfis_trava.csv:perfil=P3_regressividade&gamma=0.125:cv_vetor_E:.0%}}).
A conformidade heterogênea por UF da seção 4.5 é parametrizada por β em
{0,5; 1} sobre a informalidade local, com média nacional preservada em
12,5%: os máximos de deslocamento do vetor estadual são de
{{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=0.5&esfera=E:max_abs_delta_pp:.1f}}
(β = 0,5) e
{{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=1&esfera=E:max_abs_delta_pp:.1f}}
pontos (β = 1), e as contagens não se alteram
({{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=1&esfera=E:n_uf_acima_ref:.0f}}
contra
{{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=1&esfera=E:n_uf_acima_ref_central:.0f}}
UFs acima da referência estadual;
{{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=1&esfera=E:n_piso_vinculante:.0f}}
contra
{{csv:sens_vetores_gamma_uf.csv:uf=RESUMO&beta=1&esfera=E:n_piso_vinculante_central:.0f}}
vinculadas ao piso), artefato `sens_vetores_gamma_uf.csv`.

O quadro seguinte (Tabela C.3) consolida a direção de viés de cada convenção do
desenho: o lado da identidade que ela afeta, o sinal sobre a alíquota, a
magnitude medida na grade e o status. O sinal reportado é o efeito da
omissão da correção correspondente, medido contra o cenário central.

[[TAB:t5_quadro_vies.csv|Direções de viés das convenções
|colunas=convencao,afeta,sinal_na_aliquota,magnitude,status
|rotulos=convencao:Convenção;afeta:Afeta;sinal_na_aliquota:Sinal na alíquota;magnitude:Magnitude;status:Status
|fonte=elaboração própria; magnitudes medidas contra o cenário central na grade de cenários (aferir_nacional.csv do espelho).]]

A prosa que segue detalha as convenções do quadro. O IS entra por
aproximação de carga equivalente da arrecadação corrente de IPI em fumo,
bebidas e veículos, cota inferior do campo do art. 409 (empurra a CBS para
cima; os cenários com IS igual a zero e com IS ampliado aos componentes
quantificáveis constam da grade; apostas e embarcações/aeronaves permanecem
não quantificadas por dado aberto). A âncora federal
segue a convenção líquida do RTN, relativa ao Tema 69, com a série bruta da
RFB como sensibilidade (diferença medida de
{{csv:ancora_uniao.csv:metrica=delta_liquida_menos_bruta_pct_pib:valor:.3f}}
ponto do PIB; o sinal é empírico porque as restituições puxam a série
líquida para baixo, enquanto o regime de caixa e a alocação por tributo
dos parcelamentos a puxam para cima em anos de programas especiais).
Etanol e biodiesel ficam fora da dedução
federal de combustíveis (CBS para cima). O consumo fora do campo residual
permanece na base (alíquotas para baixo). A cunha do Simples é medida pela
proxy aberta ω da seção 3.3, construída por atividade como a participação
das empresas de menor porte na receita (PAC, PIA e PAS 2023) multiplicada
pela propensão da atividade a vender às famílias na TRU, e entra como
cenário na grade (de um e de dois
lados); o central permanece sem a dedução e é cota inferior nessa dimensão
(a literatura baliza o efeito entre 2,4 e 3,4 pontos), e a própria ω é
cota inferior, porque a cunha do varejo sobre bens não é separável do
preço ao consumidor e a cobertura setorial com porte aberto alcança cerca
de três quartos do consumo em campo (`omega_simples.csv`). A razão do
IOF-Seguros é constante
(o peso do componente na âncora federal é de cerca de 0,05 ponto do PIB;
variações de um quarto para cima ou para baixo na razão deslocam a âncora
em pouco mais de 0,01 ponto; diligência registrada, seção 5.4). As ISFLSF são
escaladas ao biênio pelo consumo das
famílias, por não existir série própria na frequência trimestral
(aproximação declarada, de segunda ordem). A elegibilidade do cashback usa
os três primeiros decis da POF com participação do piso igual à média, o que
subestima a devolução do piso (CBS para baixo, segunda ordem); a escolha
dos decis é defendida por comparabilidade com o primeiro terço do Cenário
L da NT SERT, e o QA de custo (`qa_cashback_custo.csv`) mostra desvio de
{{csv:qa_cashback_custo.csv:variante=decis3_takeup_100:desvio_pct_vs_oficial:+.0f}}%
do custo oficial implícito, contra
{{csv:qa_cashback_custo.csv:variante=legal_takeup_100:desvio_pct_vs_oficial:.0f}}%
do critério legal estrito (art. 113); o critério legal e o take-up de 80%
são cenários da grade, e o take-up de 100% do central é convenção do
desenho legal de inclusão automática do destinatário (art. 113, §1º). O SIFIM imputado às famílias está
excluído do central, por não constituir operação onerosa (art. 4º); as
tarifas e os prêmios explícitos permanecem na base ao padrão da alíquota
uniforme nacional (Res. CGIBS nº 6/2026, art. 600, §4º), e o ISS financeiro
permanece no numerador municipal. O break-even desse desvio declarado é de
{{csv:ajuste_sifim.csv:componente=break_even_iss_financeiro_share:valor_rs_bi_2021:.1%}}
do alvo municipal (cerca de R$
{{csv:ajuste_sifim.csv:componente=break_even_iss_financeiro_rs_bi_ano:valor_rs_bi_2021:.1f}}
bilhões anuais): somente se o ISS financeiro exceder essa fração a
convenção superestima a referência municipal; a quantificação do numerador
financeiro é fronteira administrativa (a DCA reporta o ISSQN em conta
única). O resíduo imputado excluído fica no intervalo de R$
{{csv:ajuste_sifim.csv:componente=sifim_imputado_familias_2021:valor_rs_bi_2021:.0f}}
a R$
{{csv:ajuste_sifim.csv:componente=sensibilidade_escala_ipca_sifim_2021:valor_rs_bi_2021:.0f}}
bilhões de 2021 (cota superior com escala só-IPCA), com o central no polo
conservador; a validação externa por dado aberto do BCB, o SIFIM das
famílias pelo lado dos empréstimos (séries SGS: saldo médio do crédito às
pessoas físicas vezes a diferença entre a taxa do estoque, ICC-PF, e a
Selic), dá cerca de R$
{{csv:ajuste_sifim.csv:componente=fisim_pf_bcb_2021:valor_rs_bi_2021:.0f}}
bilhões em 2021, acima do resíduo, com teto
mecânico na própria célula da TRU (R$
{{csv:ajuste_sifim.csv:componente=consumo_familias_64801_tru2021:valor_rs_bi_2021:.0f}}
bilhões). A convenção alternativa, com o SIFIM imputado na base, é
cenário da grade. O
perímetro central das aquisições governamentais reúne os elementos de
despesa 3.3.90.30, 32, 33, 36, 37, 39 e 40 da DCA do ente consolidado; o
mínimo restringe ao trio 3.3.90.30/36/39 e o máximo acrescenta o capital
(4.4.90.51/52), com $\sigma$ recalibrado para a cesta de obras e equipamentos; a
natureza 36 (pessoa física) é chave dentro/fora do campo; a União entra
pela DCA paginada, os Estados pelas respectivas DCA e os Municípios por
amostra de capitais e dos 200 maiores. O sinal do viés depende
do perímetro, para cima no mínimo e para baixo no máximo, como o quadro
registra. O G municipal vem de extrapolação pós-estratificada, com corredor
S1-S3 propagado, em que S1 é a extrapolação por escala populacional, S2 é a
cota inferior, restrita à amostra observada, e S3 é a própria amostra apurada no
estágio das despesas liquidadas. O corredor do modo do redutor (Figura 6)
é assimétrico por construção: o extremo sem redutor não é cota inferior
crível, porque omite o custo adicional que as próprias compras públicas
teriam à alíquota cheia, fora do alvo; a sensibilidade da soma é de cerca
de 0,17 ponto por ponto de $\sigma$ e, sendo o $\sigma$ de carga equivalente medido sem
a cascata a montante, cota inferior, o viés residual do módulo é
conservador (auditoria de nível, `metadata/auditoria_nivel_2026_07_13.md`).

# ANEXO D. REPRODUTIBILIDADE

A replicação exige três comandos sobre o espelho anônimo: `make fetch` baixa
todos os insumos das fontes públicas (API SICONFI, XLSX da RFB, SIDRA e
malhas do IBGE, microdados da POF no FTP do IBGE e vendas da ANP; nenhum
exige credencial); `make all` executa o pipeline determinístico, dos insumos
às alíquotas, passando pelos invariantes bloqueantes; e
`make manuscript` gera as figuras e este documento, byte a byte idênticos
entre execuções. O manifesto `MANIFEST_RUN.json` registra o SHA-256 de cada
arquivo e a cadeia de fórmula e fonte de cada número. Endereço do espelho
anônimo: `https://anonymous.4open.science/r/aferir-E5DC/` (código, dados e
documentação navegáveis, com download integral do repositório). Nenhum dado
utilizado exige credencial privada; os pontos em que dados administrativos
seriam indispensáveis estão demarcados na seção 5.4.
