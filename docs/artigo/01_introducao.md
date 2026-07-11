# 1 INTRODUÇÃO

A Emenda Constitucional nº 132/2023 promoveu a mais profunda reorganização
federativa da tributação brasileira desde 1965. Cinco tributos serão
substituídos por um IVA dual de destino: o ICMS, o ISS, o PIS/Pasep, a
Cofins e, em larga medida, o IPI darão lugar à Contribuição sobre Bens e
Serviços (CBS), federal, e ao Imposto sobre Bens e Serviços (IBS),
compartilhado por Estados e Municípios. Como observa a OCDE (Arnold et
al., 2025),
diferentemente do Canadá e da Índia, o Brasil atribuiu jurisdição sobre a
tributação do consumo também aos Municípios: a alíquota do IBS incidente
sobre cada operação será a soma das alíquotas do Estado e do
Município de destino (LC 214/2025, art. 15), e cada um dos 5.569 Municípios,
como cada Estado e o Distrito Federal, poderá fixar a sua por lei
própria (art. 14).

O centro de gravidade fiscal dessa arquitetura são as três alíquotas de
referência, uma por esfera. Elas valem como regra supletiva para todo ente que não legislar e servem de
âncora aos pisos da alíquota própria durante a transição (art. 371). Serão
fixadas por resolução do Senado Federal, com base em cálculos do Tribunal de
Contas da União (TCU) sobre propostas do Poder Executivo, para a CBS, e
do Comitê Gestor do IBS (CGIBS), para o IBS (art. 349). Esse rito,
contudo, opera sob dupla lacuna. A primeira é temporal: até julho de 2026, nenhuma
resolução havia sido editada, e a primeira fixação da CBS ocorrerá no
ciclo de 2026; a do IBS, no de 2028, para vigência
em 2029. A segunda é informacional: a metodologia oficial homologada para a
CBS (TCU/RFB, 2026) assenta-se em escriturações fiscais protegidas por
sigilo (ECF, EFD, NF-e), e a metodologia do
Regulamento do IBS (Res. CGIBS nº 6/2026, arts. 598-609) apoia-se em bases
apuradas de documentos fiscais e de escrituração, igualmente
sigilosas. Nenhuma das duas pode ser replicada fora das administrações que
as executam. O ente individual, sobretudo o município pequeno, não acessa as
bases do Comitê Gestor, de que participa por representação; a sociedade
civil não acessa nenhuma delas; e cada esfera é incapaz de verificar o
cálculo da outra, embora o gatilho do art. 475 incida sobre a soma das três
referências. Entre a promulgação da emenda e a primeira resolução do Senado,
os entes subnacionais planejam décadas de receita sobre um parâmetro que
nenhum deles consegue verificar sozinho.

Este artigo ocupa esse vazio: antecipar, com dados
exclusivamente abertos, a ordem de grandeza das três alíquotas de referência
e dos vetores de reposição por ente. Uma questão de pesquisa orienta o
trabalho: até onde os dados abertos permitem replicar o cálculo dos
arts. 349-369, e em que pontos os dados administrativos se tornam
indispensáveis? Para responder a essa pergunta, constrói-se uma rotina
pública, determinística e auditável, batizada AFERIR, que replica a
arquitetura legal do cálculo oficial (LC 214/2025, arts. 349-369 e
472-473, com as alterações da LC 227/2026) usando somente fontes
abertas: o Sistema de Informações Contábeis e Fiscais do Setor Público
Brasileiro (SICONFI/FINBRA), a Pesquisa
de Orçamentos Familiares (POF) 2017-2018, as Tabelas de Recursos e Usos
(TRU), as séries de arrecadação da Receita Federal do Brasil (RFB) e os
dados da ANP e do CONFAZ.

A rotina produz três resultados. O primeiro é a ordem de grandeza das três
alíquotas de referência, incluindo a repartição estadual-municipal do IBS
sob a legislação vigente: as decomposições disponíveis
referem-se a desenhos anteriores
à LC 214, com anos-base de 2015 a 2022, e nenhuma desce ao ente federado; a
seção 2.2 situa e qualifica essa contribuição. O
segundo são os vetores indicativos por ente (27 alíquotas estaduais e 27
agregados municipais), que quantificam a tensão federativa que a referência
única e a transição terão de absorver. O terceiro é a demarcação
empírica, esfera a esfera, da fronteira entre o que os dados abertos
alcançam e o que depende de dados administrativos: a
fronteira é resultado da pesquisa, não limitação dela.

O trabalho dialoga diretamente com Alcântara e Silva (2026), que estima,
com dados FINBRA, o impacto da substituição do ICMS e do ISS sobre a
arrecadação e o investimento municipais, tomando a alíquota do IBS como
dada, e conclui que a equalização importa mais que o nível da alíquota;
este artigo ocupa o
elo anterior dessa cadeia: calcula as alíquotas que aquele estudo adota e
mede, ente a ente, o quanto a equalização terá de trabalhar. Na tipologia do
federalismo fiscal de segunda geração (Oates, 2005; Weingast, 2009), a
contribuição é de responsabilização interfederativa: quando a suficiência de
cada ente passa a depender de um parâmetro único calculado centralmente sob
sigilo, a capacidade de os governos subnacionais anteciparem e contestarem
esse parâmetro torna-se condição material da autonomia que a Constituição
lhes preservou.

O restante organiza-se em cinco seções: a 2 apresenta a
arquitetura legal como algoritmo e a literatura; a 3, a
metodologia; a 4, as três referências, os vetores por ente, o gatilho de
26,5% (art. 475, §11), a trava e a distribuição legal de 2033;
a 5, as implicações federativas; a 6 conclui.
