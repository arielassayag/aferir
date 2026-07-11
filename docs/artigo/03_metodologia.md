# 3 METODOLOGIA

## 3.1 Identidade central e sistema tri-esfera

Para cada esfera $s \in \{U, E, M\}$, a alíquota de referência indicativa
resolve a reposição da receita de referência sobre a base potencial de
destino, líquida dos hiatos e da devolução personalizada, acrescida do
módulo de compras governamentais:

$$R_s = \tau_s \cdot D_s + \sigma \cdot G_s$$

onde $D_s = N \cdot (1-\gamma) - CB_s$ é a base ordinária líquida; $N$ é a
base potencial já descontado o hiato de política; $\gamma$ é o hiato de
conformidade; $CB_s$ é a dedução de cashback da esfera; $G_s$ são as
aquisições governamentais da esfera; e
$\sigma = (1-r) \cdot (\tau_U + \tau_E + \tau_M)$ é a alíquota efetiva sobre
compras públicas após o redutor $r$ do art. 370, uniforme e
proporcional às três alíquotas (art. 472). Como o art. 473, §1º, zera as
alíquotas dos demais entes e atribui ao comprador a soma das três, o sistema
é linear e simultâneo nas três alíquotas, com solução em forma fechada. No
cenário central, o redutor segue o regime de carga equivalente do art.
370, §§1º-4º: as compras públicas pagam, no novo
sistema, o que pagam hoje, carga medida na TRU 2021 pela média do
tributo embutido em cada produto, ponderada pela cesta de compras do
governo (folha fora do
campo). Sob esse regime, $\sigma$ =
{{csv:tru_gov_carga.csv:cenario=carga_embutida_gov_central_pct:carga_embutida_estimada_pct:.1f}}%;
é cota inferior
do conceito por operação, cuja apuração exata exigiria dado
administrativo (cenários sem redutor e com redutor integral na
Figura 6 e no Anexo C).

Nas leituras por ente, o vetor indicativo $\tau_s^j$ resolve a mesma
equação para o ente $j$, mantidas as demais esferas na referência nacional:
mede a necessidade de reposição no regime
permanente e não é, nem poderia ser, a alíquota que o ente fixará.
Durante a transição, o art. 371 e o Anexo XVI da LC 214 impõem piso à
alíquota própria, de 81% da referência entre 2029 e 2032 e de 90,5% em
2033, desenhado, como declara o caput, para proteger as retenções do
condomínio federativo da transição (ADCT, arts. 131-132) contra a
subtributação. A alíquota mínima de fixação em 2033 é, portanto, a
censura inferior do indicativo no piso da esfera,
$\tau_s^{j*} = \max\{\tau_s^j; 0{,}905 \cdot \tau_s\}$: onde a necessidade
fica abaixo do piso, o ente cobra o piso e arrecada acima da
necessidade, com devolução a critério do legislativo
local. As duas leituras são reportadas lado a lado na
seção 4.2 e na Tabela A.1; o piso escala com a referência que o Senado
fixar, e sob a trava-conforme da seção 3.4 o chão desce na mesma
proporção.

## 3.2 Receitas de referência (numeradores)

Salvo indicação em contrário, os valores em reais deste artigo ("R$ bilhões do biênio")
são médias anuais da janela 2024-2025 a preços de 2024, a mesma convenção
dos alvos.

**União (art. 353).** A âncora legal é a média de 2012 a 2021 da razão
entre receita de referência e PIB. Duas séries públicas a medem: a central
é a Tabela 2.2 do Resultado do Tesouro Nacional (RTN/STN), em conceito
caixa e líquida das restituições, convenção compatível com o Tema 69
do STF, e alcança
{{csv:ancora_uniao.csv:metrica=media_pct_pib_2012_2021_liquida_rtn:valor:.1f}}%
do PIB; a alternativa, a planilha bruta da RFB (1994-2025), sem a mesma
dedução de restituições nem a mesma alocação dos parcelamentos, dá
{{csv:ancora_uniao.csv:metrica=media_pct_pib_2012_2021:valor:.1f}}%,
diferença de
{{csv:ancora_uniao.csv:metrica=delta_liquida_menos_bruta_pct_pib:valor:.3f}}
ponto do PIB, com sinal empírico (Anexo C), e entra como sensibilidade. O
alvo da CBS deduz, conforme o art. 353,
§1º, o que seguirá arrecadado fora dela: o Imposto
Seletivo (IS) e o IPI residual. Sem projeção oficial aberta do IS, pois o
Projeto de Lei de Diretrizes Orçamentárias (PLDO) de 2027 aguarda a lei de
alíquotas, o central usa a arrecadação
corrente de IPI nos produtos do
campo do novo imposto (fumo, bebidas e veículos, conforme o art. 409 e o
Anexo XVII da LC 214), R$
{{csv:metricas.csv:chave=is_estimado_bi:valor:.1f}} bilhões na
janela: aproximação em cota inferior do IS, logo CBS em cota superior
nessa dimensão, com a projeção oficial na fronteira
administrativa federal (cenários com IS zero e ampliado na grade). O IPI
residual é abatido porque a reforma não o extingue: desde 2027 as
alíquotas estão zeradas,
exceto para os produtos que concorrem com a industrialização incentivada na
Zona Franca de Manaus (ZFM), que o conservam como proteção
do polo (ADCT, art. 126, III); o abatimento, de R$
2,6 bilhões anuais, é o efeito líquido publicado pela Nota Técnica da
SERT/MF de julho de 2024, cujas parcelas brutas não são publicadas em
separado (outra fronteira administrativa). Por fim, a parcela de PIS/Cofins
sobre combustíveis monofásicos é deduzida simetricamente à exclusão dos
combustíveis da base, mês a mês e sobre o alvo corrente da CBS (âncora
histórica intacta), por volumes ANP às alíquotas ad rem vigentes
(produtos, vigências, blends e exceções no Anexo B).

**Estados (art. 350, II).** Usa-se a rubrica de ICMS do Relatório Resumido
da Execução Orçamentária (RREO, Anexo 03) na janela 2024-2025, os dois
exercícios já observáveis da âncora legal de 2024 a 2026 (arts. 361-365),
deflacionada a preços de 2024; a rubrica é bruta, anterior ao FUNDEB e à
cota-parte, já contém o adicional destinado ao Fundo Estadual de Combate à
Pobreza (FECP) e tem identidade verificada contra as
Declarações de Contas Anuais (DCA) em 54
de 54 pares UF-ano, com desvio zero. Deduz-se a receita ad rem de
combustíveis mês a mês, pelos volumes da ANP à alíquota vigente no mês
(vigências dos Convênios do CONFAZ no Anexo
B); o etanol hidratado é monofásico (art. 172, VI) e sai simetricamente da
base e do alvo: como os convênios ad rem ainda não o alcançam, sua dedução
usa volumes ANP, preço ao consumidor ANP e alíquota ad valorem vigente por
UF, com tabela de vigências de ato citado linha a linha no espelho e
detalhe operacional no Anexo B. Somam-se os fundos do art.
350, II, "b", cujo total oficial da NT SERT é alocado a MT, MS e GO e
corrigido pela variação do ICMS, na forma do §2º, II.

**Municípios (art. 350, III).** Usa-se a conta 1.1.1.4.51.1.0 (ISSQN) das
DCA dos 5.569 municípios, via API do SICONFI, para
2024 e 2025. A conta consolida principal, multas e dívida
ativa, o que atende o §1º; a DCA é a peça primária e a Matriz de Saldos
Contábeis (MSC), ao centavo, a de validação. A cobertura econômica é de
{{csv:metricas.csv:chave=cobertura_econ_2024:valor:.2f}}% do ISS em 2024 e
{{csv:metricas.csv:chave=cobertura_econ_2025:valor:.2f}}% em 2025
(declarantes, imputação pela mediana per capita do estrato da UF e delta
da janela só-2024 no Anexo B). O
ISS do
Distrito Federal (art. 350, III, parte final) soma-se pela rubrica própria
do RREO distrital.

## 3.3 Base de destino (denominador)

A base potencial é única, pois a legislação material do IBS e da CBS é a
mesma: consumo das famílias, consumo das instituições sem
fins lucrativos a serviço das famílias (ISFLSF) e formação bruta de
capital fixo (FBCF) não corporativa, ancorados na TRU 2021 nível 68, última
edição detalhada, e escalados ao biênio pelas variações nominais das Contas
Nacionais Trimestrais (fatores e aproximações no Anexo B). Do consumo
excluem-se, no próprio nível da TRU, o aluguel imputado (produto 68002, fora
do campo de incidência, art. 4º), os serviços domésticos (97001), os
combustíveis monofásicos (gasoálcool 19912, etanol e biocombustíveis 19921,
em que o hidratado deixa a base, e demais derivados do refino 19916) e o
serviço financeiro
imputado (SIFIM) alocado às famílias, sem operação onerosa e também fora
do campo; tarifas e prêmios explícitos
permanecem (break-even do ISS financeiro no Anexo C). A
FBCF residencial nova recebe o redutor
de 50% do art. 261; as convenções alternativas, o SIFIM imputado mantido
na base e a FBCF sem o redutor, entram como sensibilidades, com
efeitos de
{{csv:ajuste_sifim.csv:componente=efeito_pp_soma:valor_rs_bi_2021:.1f}} e
{{csv:ajuste_fbcf_imobiliaria.csv:componente=reducao_aliquota_art261:efeito_pp_aprox:.1f}}
ponto na soma. A distribuição por UF usa os
microdados da POF 2017-2018, reconstruídos ao centavo contra os totais do
IBGE. As compras governamentais saem da base ordinária das três
esferas (art. 473). O perímetro central, ampliado a partir da DCA
consolidada, é fronteira declarada mais ampla que o alcance literal dos
arts. 472-473 e vem acompanhado do corredor mínimo/máximo, da chave da
natureza 36 e de $\sigma$
recalibrado para capital (elementos e medição no Anexo C); o corredor
desloca a referência municipal em
{{csv:metricas.csv:chave=amplitude_g_municipal_pp:valor:.1f}} ponto e a
soma em {{csv:metricas.csv:chave=amplitude_g_soma_pp:valor:.1f}}.

O hiato de política aplica a matriz item a item POF×LC 214:
13.474 itens classificados nos seis níveis legais de tributação,
com dispositivo citado e dupla codificação cega (κ = 0,66 na amostra
combinada; desenho no Anexo A), média
nacional de
{{csv:metricas.csv:chave=pi_p_nacional:valor:.1%}} da despesa em campo.
O hiato de conformidade usa o corredor da NT SERT, de 10%
a 15%, com a trajetória húngara pós-digitalização (European
Commission, 2025) como referência de ordem de grandeza para um IVA com
documento fiscal eletrônico universal e crédito amplo (benchmark, não
equivalência institucional) e ponto central em 12,5%, o hiato de
neutralidade implícito no FMI (Cebreiro Gómez et al., 2025). O corredor é único para as três
esferas: pela conjugação dos arts. 14-15 com a incidência de IBS e CBS
sobre a mesma operação e a mesma base (arts. 4º e 12), uma operação
evadida subtrai as três parcelas identicamente; a conformidade é
propriedade
da operação, não da esfera, e as diferenças históricas de evasão entre ICMS
e ISS vivem nos numeradores. Dois conceitos de
evasão, aliás, não se confundem: a evasão do sistema atual já está nos
numeradores, arrecadação efetivamente realizada, enquanto $\gamma$ responde
à pergunta prospectiva da literatura de mensuração de
cima para baixo (Hutton, 2017; Barra; Prokof'yeva, 2025), a fração da base
potencial que o novo tributo deixará de converter em receita. Encolher
também a base pela evasão legada contaria a mesma evasão duas vezes; o
corredor aplica-se, por isso, apenas ao denominador, como hipótese
sobre a conformidade do sistema novo. A forma multiplicativa dos hiatos,
$\gamma$ sobre a base já líquida do hiato de política, é a consistente
com o RA-GAP; a alternativa aditiva elevaria a soma, e a grade não a
adota por ser mais penalizadora. O split payment, recolhimento na
própria liquidação financeira da operação, é o mecanismo da lei
que promete comprimir esse hiato; sem medida
empírica de eficácia, entra como cenário explícito, com $\psi \in \{0; 0{,}3; 1\}$
como fração do hiato eliminada, jamais no cenário central.

O cashback (art. 118) entra em forma fechada como dedução de base,
assimétrico por esfera: a CBS devolve 100% nos itens do piso (energia, água
e esgoto, gás e telecomunicações, dentro da base ad valorem) e 20% no
restante; o IBS devolve 20% uniformes. A elegibilidade central usa os três
primeiros decis da POF, o primeiro terço do Cenário L da NT SERT, com QA
de custo contra o implícito oficial e defesa no Anexo C; o critério legal
estrito de meio salário mínimo per capita e o take-up de 80% são
sensibilidades, e o take-up de 100% é convenção do desenho legal de
inclusão automática (art. 113, §1º).

Já o Simples Nacional exige tratamento nos dois lados. Nos numeradores, a
inclusão exigida pelo art. 350, §1º,
é demonstrada: as naturezas consolidadas já contêm o ICMS e o
ISS dos optantes (LC 123/2006, arts. 13 e 22), como a varredura por
exaustão do Ementário prova, em ordem compatível com
os quadros públicos do regime (Anexo B). Na base, os optantes continuarão
recolhendo pelo regime favorecido, e o
desenho oficial deduz essa parcela (Res. CGIBS nº
6/2026, art. 600, §4º, II); a proxy aberta ω, construída setorialmente no
Anexo C, mede
{{csv:omega_simples.csv:atividade=TOTAL:contribuicao_omega:.1%}} do consumo
em campo, cota inferior declarada. O cenário com a cunha eleva a
soma de
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:soma_pp:.1f}}
para
{{csv:aferir_nacional.csv:cenario_gamma=com_cunha_simples&psi=0&modo_redutor=iso_carga:soma_pp:.1f}}
pontos (dois lados, com dedução também nos numeradores subnacionais, o ICMS
e o ISS do Simples:
{{csv:aferir_nacional.csv:cenario_gamma=com_cunha_simples_dois_lados&psi=0&modo_redutor=iso_carga:soma_pp:.1f}}).
A âncora federal do art. 353 exigiria a série histórica da parcela federal
do regime, mesma fronteira do §1º, e por isso não é deduzida. O corte exato
segue nos microdados administrativos da RFB, e o central, sem a dedução, é
cota inferior nessa dimensão (baliza da literatura: 2,4 a 3,4 pontos;
IMB-GO, 2023; CNI, 2023).

## 3.4 Trava do art. 475 e distribuição legal de 2033

Dois módulos fecham o desenho. O módulo da trava resolve o §11 do art. 475
como problema inverso: dado o encolhimento uniforme λ dos regimes
favorecidos, com $m_i(\lambda) = m_i + \lambda \cdot (1-m_i)$ nos itens em
campo, itens fora do campo intocados e adendo da ZFM e cashback
recomputados, a bisseção determinística encontra o λ que iguala a soma a
26,5% exatos, produzindo a referência trava-conforme, com alíquotas e
custo anual dos benefícios suprimidos reportados. O módulo da
distribuição reproduz a cadeia de repartição do produto do IBS em 2033
(ADCT, arts. 131-132; LC 227/2026, arts. 109-117 e 128): retenção de 90% por
coeficientes de receita média histórica (janela efetiva de 2019 a 2025,
declarada), parcela de destino, seguro-receita de 5% com teto per capita e
cota-parte municipal; mede-se então a suficiência de cada ente, razão
entre o recebido e a receita de referência, o teste
juridicamente pertinente para o piso do art. 371.

## 3.5 Duas construções e auditabilidade

Os resultados são reportados em duas construções complementares, que usam
os mesmos numeradores (as receitas de referência do art. 350) e diferem
apenas na base sobre a qual a alíquota incide. A
construção B monta a base de baixo para cima, com dados abertos: resolve
o sistema da seção 3.1 sobre a base potencial TRU/POF, líquida de hiatos e
de cashback. É transparente em cada componente e produz a leitura de cota
superior das alíquotas nas dimensões de base e de conformidade, porque a
base potencial das contas nacionais é
maior do que a base que os contribuintes declaram ao fisco;
na dimensão do Simples, pela assimetria da seção 3.3, a mesma leitura é
cota inferior, e o Anexo C consolida as direções de viés de cada
convenção. A construção A obtém a base de cima para baixo, das âncoras
oficiais: se a NT SERT de julho de 2024 calibrou a alíquota de
26,47% para arrecadar a meta de 12,30% do PIB, a base efetiva com que
o governo trabalha é o quociente entre as duas, já líquida de
conformidade, favorecimentos e cashback; aplicar-lhe os mesmos numeradores
produz a leitura comparável às estimativas oficiais e à
literatura, em duas variantes para a parcela federal, a âncora legal de
2012 a 2021 (art. 353) e a meta corrente do PLDO. A distância entre B e A
não é ruído: decompõe-se integralmente em três convenções observáveis (base
potencial contra base declarada; cota inferior do IS; âncora federal
histórica contra projeção corrente) e forma a ponte de comparabilidade da
Figura 1 e da Tabela C.1.

Toda a rotina é determinística, com execuções byte a byte idênticas; cada
número carrega fórmula e fonte; e invariantes bloqueantes, de identidades
contábeis à consistência entre as peças declaratórias do próprio SICONFI
(RREO contra DCA, DCA contra MSC), são
reexecutados a cada geração; o mapa de cada dispositivo legal citado,
com redação e verificação contra o texto consolidado
(`metadata/legal_map.csv`), é um desses invariantes. Como as três peças
são autodeclarações do
mesmo ente ao mesmo sistema, a concordância valida o pipeline e
a coerência interna das declarações, não a exatidão econômica do valor
declarado; validação externa, onde existe fonte independente, é reportada
em separado: para os numeradores estaduais, o confronto com o boletim do
CONFAZ fecha com desvio mediano por UF-ano abaixo de meio por cento
(Anexo B). A correspondência com o cálculo oficial é auditável
em crosswalk passo a passo (`metadata/crosswalk_metodologia.csv`): cada
etapa da metodologia TCU/RFB e do Regulamento do IBS
(Res. CGIBS nº 6/2026, arts. 598-609) recebe status de replicada,
aproximada ou fronteira administrativa, com módulo e teste; e uma
auditoria adversarial do nível, um verificador cético por alavanca do
cálculo, com recomputação contra os artefatos do espelho, acompanha o
repositório (`metadata/auditoria_nivel_2026_07_13.md`). Código, dados e
manifesto de hashes acompanham o artigo em espelho anônimo (Anexo D).
