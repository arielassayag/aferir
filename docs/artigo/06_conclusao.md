# 6 CONCLUSÃO

Este artigo construiu e executou uma rotina pública que antecipa as
três alíquotas de referência do novo sistema tributário do consumo,
replicando a arquitetura legal do cálculo
oficial exclusivamente com dados abertos. Os resultados resumem-se em três
planos. No plano nacional, a construção que segue a
âncora federal legal do art. 353 produz CBS de
{{csv:aferir_ancoras.csv:variante_federal=ancora_legal_2012_2021:tau_CBS_pp:.1f}},
IBS estadual de
{{csv:aferir_ancoras.csv:variante_federal=ancora_legal_2012_2021:tau_E_pp:.1f}} e
IBS municipal de
{{csv:aferir_ancoras.csv:variante_federal=ancora_legal_2012_2021:tau_M_pp:.1f}}
pontos percentuais, somando
{{csv:aferir_ancoras.csv:variante_federal=ancora_legal_2012_2021:soma_pp:.1f}};
a variante que substitui essa âncora pela meta federal corrente do PLDO,
comparável às notas técnicas oficiais, produz CBS de
{{csv:aferir_ancoras.csv:variante_federal=meta_pldo_4_47:tau_CBS_pp:.1f}} e
soma de
{{csv:aferir_ancoras.csv:variante_federal=meta_pldo_4_47:soma_pp:.1f}}. Em
ambas, a soma excede o gatilho de revisão de 26,5% antes de qualquer
hipótese adversa de conformidade, como excedem as estimativas oficiais mais
recentes, e a construção de dados abertos fixa a leitura sobre a base
potencial em
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:soma_pp:.1f}}
pontos, cota superior nas dimensões de base e de conformidade e
cota inferior na do Simples (espelhada a dedução oficial do regime nos
dois lados, a leitura sobe ao intervalo que contém a estimativa da
literatura sobre a mesma base POF). A ponte entre as duas construções está
integralmente decomposta, e as direções de viés de cada convenção estão
declaradas no Anexo C. Aplicado o
mecanismo corretivo que o art. 475, §11, prescreve, as três
alíquotas compatíveis com o limite são *CBS de
{{csv:trava_conforme.csv:cenario_gamma=central:tau_CBS_pp:.1f}}, estadual de
{{csv:trava_conforme.csv:cenario_gamma=central:tau_E_pp:.1f}} e municipal de
{{csv:trava_conforme.csv:cenario_gamma=central:tau_M_pp:.1f}}, somando
26,5*, ao preço, aqui quantificado, de suprimir
{{csv:trava_conforme.csv:cenario_gamma=central:lambda:.0%}} dos regimes
favorecidos, ou R$
{{csv:trava_conforme.csv:cenario_gamma=central:custo_beneficios_rs_bi:.0f}}
bilhões anuais no perfil de corte uniforme, convenção declarada entre os
perfis admissíveis do §11 (o perfil que protege
integralmente os essenciais é infactível com esse
instrumento isoladamente; o corte por regressividade fecha a mesma soma com outra
dispersão federativa, seção 4.5). A escolha entre exceções e alíquota, que
costuma ser retórica, torna-se aritmética.

No plano dos entes, os vetores indicativos revelam a dispersão do regime
permanente: na esfera estadual, de
{{csv:aferir_vetor_uf.csv:uf=DF:tau_E_uf_pp:.1f}} no Distrito Federal a
{{csv:aferir_vetor_uf.csv:uf=AM:tau_E_uf_pp:.1f}} no Amazonas; na
municipal, de {{csv:aferir_vetor_uf.csv:uf=AP:tau_M_uf_pp:.1f}} no Amapá a
{{csv:aferir_vetor_uf.csv:uf=SP:tau_M_uf_pp:.1f}} nos municípios
paulistas. A distribuição legal de 2033 comprime essa dispersão a uma
suficiência mediana de
{{csv:metricas_dist.csv:chave=suf_mediana:valor:.1f}}%, sem nenhum Estado
abaixo do patamar do piso e com um resíduo municipal localizado, que restará
à equalização federal. Um único município segue concentrando mais de um
quarto do ISS municipal; e o piso de fixação do art. 371, e não a própria necessidade
de receita, será a restrição vinculante de longo prazo para
{{csv:metricas_piso.csv:chave=n_piso_vinc_E:valor:.0f}} unidades
estaduais e
{{csv:metricas_piso.csv:chave=n_piso_vinc_M:valor:.0f}} dos 27 agregados
municipais, fazendo da referência fixada pelo Senado o verdadeiro
parâmetro de carga da maior parte dos conjuntos municipais.

Para as administrações subnacionais, a rotina oferece o que, até onde foi
possível verificar, não existia:
um instrumento verificável de planejamento e de contestação técnica das
propostas que o Comitê Gestor e o Executivo levarão ao TCU e ao Senado. Para
a política de transparência, a fronteira demarcada esfera a esfera
converte uma limitação em agenda: publicados os poucos agregados que
faltam, o cálculo mais consequente do federalismo fiscal brasileiro deixa
de ser ato de fé. Os dados abertos, como se demonstrou, fixam a ordem de grandeza e o
mapa das tensões federativas. Não substituem o Senado, o TCU nem o Comitê
Gestor; permitem que a federação os observe trabalhando.
