# 5 DISCUSSÃO FEDERATIVA

## 5.1 O que a referência única não repõe

A alíquota de referência é uma só por esfera; as necessidades de
reposição, como a seção 4 mostrou, variam por um fator superior a quatro. A
diferença não desaparece: é administrada por três mecanismos cuja
carga o artigo dimensiona. O primeiro é a própria transição de
receita: as retenções dos arts. 109-110 da LC 227/2026 diferem a passagem
ao destino até 2077, e a seção 4.4 mostrou
quanto isso rende, com a suficiência mediana por ente em
{{csv:metricas_dist.csv:chave=suf_mediana:valor:.1f}}% e a tensão do
contrafactual encolhida em uma ordem de grandeza; o custo é simétrico,
pois o ajuste ao destino, conteúdo econômico da reforma,
fica adiado na mesma proporção. Soma-se a nova cota-parte:
25% do IBS estadual distribuído aos municípios por critérios que abandonam o
valor adicionado (80% população, 10% indicadores de educação, 5% critério
ambiental, 5% igualitário; art. 128 da LC
227/2026), redistribuindo
dentro de cada Estado o que a municipalização redistribui entre Estados.
Completa o conjunto a equalização federal, formada pelos Fundos de Participação dos
Estados e dos Municípios (FPE e FPM) e pelo valor de referência dos arts.
477-478, calculado e publicado pelo TCU (Res.-TCU 388/2026, alterada pela
Res.-TCU 389/2026).
Alcântara e Silva (2026) já apontava a suficiência desses instrumentos como
a variável decisiva; os vetores aqui estimados a quantificam pela raiz. A Figura 7 resume os dois planos: no tempo, a
saída gradual dos coeficientes históricos rumo ao destino pleno de 2078;
no corte de 2033, a contribuição de cada mecanismo por
ente, com o seguro-receita atuando onde o contrafactual aperta
(AM, RR, MT, TO, RO e MS).

[[FIG:fig6_transicao.png|A transição federativa da receita. Painel superior: trajetória legal da distribuição do produto do IBS entre coeficientes de receita média histórica e destino (redução escalonada das alíquotas de ICMS e ISS: ADCT, art. 128; retenções e destino: ADCT, arts. 131-132, e LC 227/2026, arts. 109 e 114-117; cota-parte municipal: LC 227/2026, art. 128). Painel inferior: os mecanismos em 2033, por UF, componentes do recebido em proporção da receita de referência do ente (esferas estadual e municipal agregadas; rótulos em negrito nos entes alcançados pelo seguro-receita). Fonte: elaboração própria a partir de SICONFI/DCA 2019-2025, RREO, POF 2017-2018 e TRU 2021.]]

## 5.2 Autonomia sob piso: o achado contraintuitivo

O piso do art. 371 à alíquota própria, descrito na seção 3.1, comporta
duas precisões. A primeira: o piso disciplina a
fixação de alíquota, não a suficiência. Como a regra supletiva legal é a
própria referência (art. 14, §3º), nenhum ente o descumpre por inércia, e,
sob a distribuição legal, todos os Estados recebem ao
menos {{csv:metricas_dist.csv:chave=suf_min_E:valor:.1f}}% da própria
receita de referência (seção 4.4). A segunda diz
respeito ao longo prazo (seção 4.2): confrontando o piso de 2033 com os
vetores indicativos do contrafactual sem retenções,
{{csv:metricas_piso.csv:chave=n_piso_vinc_E:valor:.0f}} unidades (AP, DF, PR,
RN, RS e SE) têm necessidade de reposição estadual inferior ao piso, e
no plano municipal o chão vincula
{{csv:metricas_piso.csv:chave=n_piso_vinc_M:valor:.0f}} dos 27 agregados.
Para esses entes, a restrição vinculante não é o teto político da carga,
mas o chão legal que protege o condomínio federativo contra
a subtributação oportunista (seção 3.1), pois, sob o princípio do destino,
a receita de um ente é função da alíquota que os demais suportam
politicamente. É a tradução operacional do dilema entre
autonomia e objetivos comuns que dá nome ao Tema: a federação protegeu a
arrecadação agregada ao custo de obrigar parte dos entes a cobrar mais do
que precisariam no regime permanente, e devolver a diferença é decisão de
cada legislativo, não da referência.

## 5.3 Compras governamentais: a realocação silenciosa

O módulo dos arts. 472-473 tem uma consequência federativa pouco notada.
Hoje, o ICMS embutido nas compras de um município pertence ao Estado, e o
PIS/Cofins, à União. Desde 2027, a parcela da CBS sobre a
aquisição pública pertence ao ente comprador; de 2029 em diante, também a
do IBS, completando-se o quadro em 2033, com a extinção do ICMS e do
ISS. Com aquisições municipais da ordem de R$
{{csv:metricas.csv:chave=g_municipal_janela:valor:.0f}} bilhões
anuais, cerca do dobro das estaduais, a regra transfere silenciosamente
base das esferas maiores para a municipal, e explica por que o componente
municipal da referência
({{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:tau_M_pp:.1f}})
é menor do que a razão entre ISS e consumo sugeriria. A estimativa do
redutor do art. 370, infralegal mas vinculada à regra de equivalência dos
§§1º-4º, modula essa realocação e merece o mesmo escrutínio público que as
alíquotas.

## 5.4 A fronteira entre dados abertos e administrativos como agenda

Cada esfera tem sua fronteira, e o artigo a demarca com evidência. Na
federal, a projeção do Imposto Seletivo e a decomposição do IOF por
modalidade não existem em dado aberto: o PLDO de 2027 remete à lei futura,
e a série da RFB traz o IOF em linha única; esgotadas as bases abertas
(diligência registrada no espelho), a decomposição por modalidade permanece
fronteira administrativa e vale a razão constante, com sensibilidade de um
quarto para cada lado. Na estadual, a metodologia dos
fundos do art. 350, §2º, III, é do CGIBS, sob homologação do TCU; a
publicação consolidada do boletim CONFAZ para 2024-2025 segue pendente, e o
confronto externo do Anexo B recorre à extração com pendências do catálogo de
dados abertos, cuja abertura por produto, que reconciliaria as deduções de
combustíveis, termina em 2023. Na
municipal, a parametrização de alíquotas do padrão nacional da Nota Fiscal
de Serviços eletrônica (NFS-e) exige
certificado
digital, e a dispersão das bases de consumo dentro de cada UF é
inobservável, porque a POF para na UF. A fronteira é, além disso, dinâmica:
a NT SERT de agosto de 2024, aberta no momento da coleta, passou a exigir
login gov.br, e a cópia íntegra obtida enquanto aberta está arquivada, com
hash, no manifesto; já o relatório da SPA/MF sobre apostas de quota fixa
(SPA/MF, 2025) exigia autenticação gov.br quando a diligência de coleta o
alcançou, de modo que nenhuma cópia aberta pôde ser arquivada. A receita
bruta de jogos segue, portanto, como lacuna declarada: sua exclusão do
cenário do Imposto Seletivo ampliado é justificada porque a própria LC 214
não fixa alíquota ou teto que ancore um piso análogo ao dos bens minerais. Nada
disso impede a ordem de
grandeza, como as seções 4.1 a 4.3 demonstram, mas define com precisão o que
o Comitê Gestor e o TCU precisariam publicar para que a sociedade replique o
cálculo que definirá a carga tributária do consumo por meio século:
agregados por esfera das bases declaradas, projeção do IS e arrecadação
efetiva por ente em formato aberto; a esse rol soma-se, como pedido
específico de transparência, a abertura em arquivo direto e estável dos
quadros de ICMS e ISS do Simples Nacional de 2024-2025, hoje atrás de
aplicação dinâmica. O art. 352, §3º, II, já admite, como
faculdade metodológica do calculador, a estimativa sobre dados públicos;
falta a política de transparência que publique esses agregados e a torne
verificável por terceiros. E, porque o gatilho do art. 475 incide sobre a
soma das três referências, a transparência é recíproca por natureza:
nenhuma esfera consegue, sozinha, conferir o agregado que a obriga.

Em termos operacionais, o uso da rotina é imediato: uma secretaria de
fazenda ou uma prefeitura executa `make fetch` e `make all` e
obtém a sua linha da Tabela A.1 (alíquota indicativa própria, mínima de
fixação sob o piso do art. 371 e teste de vinculação por esfera); se
dispuser da
própria arrecadação administrativa, substitui por ela o numerador aberto,
o único insumo que só o próprio ente pode melhorar, e confronta a
proposta que o
CGIBS e o Executivo levarão ao TCU, fundamentando tecnicamente a fixação da
alíquota própria (art. 14) e a sua manifestação no rito do art. 349.
