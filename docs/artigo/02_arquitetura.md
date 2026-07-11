# 2 A ARQUITETURA LEGAL COMO ALGORITMO E A LITERATURA

## 2.1 O rito das alíquotas de referência

A LC 214/2025, com as alterações da LC 227/2026, define as alíquotas de
referência como solução de um problema de reposição de receita, com
precisão suficiente para tratar o cálculo como algoritmo.
Três elementos estruturam esse problema. O ponto de partida é a receita de
referência de cada esfera (art. 350): para a União, a arrecadação de
PIS/Pasep, Cofins, IPI e IOF-Seguros; para os Estados, o ICMS bruto
acrescido das contribuições a fundos estaduais condicionantes de benefício
(art. 350, II, "b"); para os Municípios, exclusivamente o
ISS dos Municípios e do Distrito Federal (art. 350,
III). Em todas as esferas incluem-se o Simples Nacional e os adicionais do
art. 82 do ADCT (§1º). Seguem-se as âncoras temporais: a CBS compara a razão receita/PIB dos
anos-base com a média de 2012 a 2021 da receita de referência da União
(art. 353); para Estados e Municípios, a LC 227/2026 reescreveu os arts.
361-365 e ancorou a razão na média de 2024 a 2026. Por fim, a
governança segue calendário anual no exercício anterior ao da vigência:
propostas do Executivo, para a CBS, e do Comitê
Gestor, para o IBS, até 31 de julho; cálculo do TCU até 15 de setembro; e
resolução do Senado até 31 de outubro. Merece nota a cláusula supletiva do
art. 349, §2º: ultrapassado o dia 22 de dezembro, valem provisoriamente as
alíquotas calculadas pelo TCU, sem deliberação política, até sobrevir a
resolução do Senado.

Dois dispositivos acoplam as três alíquotas. As compras
governamentais (arts. 472-473) zeram as alíquotas dos demais entes e
atribuem ao ente comprador uma alíquota equivalente à soma das três, após
redutor uniforme; a receita de cada esfera depende, portanto, das alíquotas
das outras duas. Já o art. 475, §§9º-13, institui a avaliação quinquenal: se
a soma das alíquotas de referência estimadas para 2033 superar 26,5%, o
Executivo fica obrigado a propor lei complementar que reduza benefícios. É
um gatilho sobre o agregado das três esferas, o que torna estruturalmente
incompleta qualquer avaliação restrita a uma só.

O art. 352, §3º, faculta expressamente que as estimativas usem "dados
públicos de agregados macroeconômicos" (inciso II) em alternativa aos dados
administrativos de arrecadação (inciso I). A faculdade é metodológica e
dirige-se ao calculador oficial, não institui canal de participação. A
Receita Federal optou pelo inciso I (TCU/RFB, 2026); este artigo percorre o
inciso II, hipótese metodológica que a própria lei admite e que, por
assentar exclusivamente em dados públicos, é a única das duas replicável
fora da administração tributária.

## 2.2 Literatura

A viabilidade de um IVA subnacional de destino, negada pela prescrição
clássica (Musgrave, 1959;
Ter-Minassian, 1997), foi estabelecida pela linha aberta em Bird e Gendron
(1998) e consolidada pela experiência canadense (Bird; Smart, 2014). As
soluções mecânicas para o comércio interestadual têm matriz brasileira: o
"IVA do barquinho" de Varsano (1995) originou o CVAT (McLure, 2000),
comparado ao VIVAT de Keen e Smith (2000) em Bird e Gendron (2000). O
desenho da EC 132, com destino pleno, câmara de compensação centralizada e
alíquota municipal própria, é mais
descentralizado que o GST indiano, de alíquotas decididas
em conselho, e mais integrado que o regime canadense (Arnold et al., 2025).
Na tradição do federalismo fiscal de segunda geração, a autonomia de
alíquota na margem preserva incentivos e responsabilização (Oates, 2005;
Weingast, 2009). A economia política brasileira, por sua vez, ensina que
reformas dessa magnitude fracassaram por vetos federativos (Junqueira,
2015), o que eleva o custo político de erros de calibração das referências.

Sobre o nível das alíquotas, todas as estimativas publicadas são nacionais
ou, no máximo, por esfera. A Nota Técnica da Secretaria Extraordinária da
Reforma Tributária de agosto de 2023 traz a única
decomposição oficial entre CBS e IBS (8,53 e 16,92 pontos no cenário
factível; SERT/MF, 2023); a de julho de 2024 estima 26,47% no total, já
descontada a devolução personalizada, sem decomposição (SERT/MF, 2024);
Orair e Gobetti
(2019) chegam a 26,9% (10,2; 14,7; 2,0), sob a PEC 45 e ano-base 2016; o
CCiF (2019)
traz partilha ilustrativa (9,2; 13,8; 2,0 sobre 25%); o FMI adota 28% como
dada e resolve o hiato de conformidade
implícito (Cebreiro Gómez et al., 2025). As demais estimativas
institucionais e de mercado são reportadas, com
desenho legal e ano-base, na Tabela C.1 (CNI, 2023; IMB-GO, 2023; Gobetti;
Orair; Monteiro, 2023;
Siqueira; Nogueira; Luna, 2024). Há, além delas, exercícios de natureza
distinta, que tomam a alíquota como dada e simulam impacto ou repartição:
a CNM publica simulações municipais e nota técnica sobre os coeficientes
de distribuição do IBS (CNM, 2024; CNM, 2025); a IFI
resenha as estimativas e os canais fiscais da reforma (IFI,
2024); e o material público do Comsefaz é institucional e administrativo
(Comsefaz, 2025), sem simulação
de alíquota por UF que se possa auditar. O que nenhum desses trabalhos faz,
até onde foi possível verificar, é estimar a própria alíquota de referência
e a sua repartição entre as parcelas estadual e municipal sob a legislação
vigente, descer ao ente federado e permitir replicação. O próprio manual
oficial da CBS se
declara inaplicável ao IBS, "não abrangendo temas correlatos, como o IBS"
(TCU/RFB, 2026, p. 3). O precedente internacional mais próximo do exercício
por ente, as alíquotas de neutralidade estimadas por Estado na Índia antes
do GST (Rao; Chakraborty, 2013), usou dados administrativos e não deixou
código público. É esse o espaço que a rotina AFERIR ocupa.

A escolha metodológica decorre do objeto: a alíquota de
referência é um parâmetro jurídico definido por uma identidade de reposição,
da mesma natureza contábil do cálculo oficial que o TCU executará, e não um
efeito causal a identificar; o valor do exercício está na replicabilidade e
na decomposição federativa. Modelos comportamentais respondem ao que a
reforma causa; este artigo responde que número o rito do art. 349 produzirá
e sobre quem esse número aperta, pergunta que os entes precisam responder
antes de 2029. As respostas comportamentais entram, na escala relevante,
pelo corredor de conformidade e pelos cenários de split payment da seção
3.3.
