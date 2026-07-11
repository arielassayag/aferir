# 1 SEÇÃO DE EXEMPLO

Parágrafo normal, justificado, com recuo de primeira linha. Placeholder com
filtro composto:
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:tau_CBS_pp:.2f}}
pontos. Placeholder de vetor por UF:
{{csv:aferir_vetor_uf.csv:uf=AM:tau_E_uf_pp:.2f}} para o Amazonas. Milhar
PT-BR: base implícita de
{{csv:aferir_ancoras.csv:variante_federal=ancora_legal_2012_2021:B_star_bi:,.1f}}
bilhões de reais.

## 1.1 Subseção com matemática

Matemática inline com subscrito e sobrescrito: $\tau_M^j$ e $\pi^p$; grupo
como base: ${CB}_M$; decimal PT-BR em fórmula: $\psi = 0{,}3$. Equação de
exibição numerada:

$$\tau_s = \frac{R_s}{B^{ord} \cdot (1-\pi) - CB_s}$$

### 1.1.1 Nível três de título

- item de lista com **negrito** e $\gamma$;
- segundo item com placeholder
  {{csv:aferir_nacional.csv:cenario_gamma=factivel&psi=0&modo_redutor=iso_carga:soma_pp:.2f}}.

Citação direta com mais de três linhas — recuo de 4 cm, fonte 10,
espaçamento simples (NBR 10520):

> A alíquota incidente sobre cada operação será a soma da alíquota do
> Estado e da alíquota do Município de destino, cabendo a cada ente
> fixá-la por lei específica; na omissão do ente, aplica-se a alíquota
> de referência fixada por resolução do Senado Federal, calculada pelo
> Tribunal de Contas da União nos termos da lei complementar.

[[FIG:fig_exemplo.png|Exemplo de figura embutida a 15,5 cm com legenda e numeração automática ("Figura 1" no corpo; "Figura A.1" por seção nos anexos; prefixo redundante na legenda é removido).|fonte=elaboração própria (linha "Fonte:" em fonte 10, também nas figuras).]]

[[TAB:t1_manchete.csv|Manchete tri-esfera e comparadores (recorte de exemplo)|colunas=fonte,total_pp,cbs_pp,ibs_estadual_pp,ibs_municipal_pp|fmt=pt|rotulos=fonte:Fonte;total_pp:Total (p.p.);cbs_pp:CBS;ibs_estadual_pp:IBS-E;ibs_municipal_pp:IBS-M|fonte=Elaboração própria (t1_manchete.csv; NaN vira travessão).]]

[[TAB:aferir_nacional.csv|Cenários filtrados e formato por coluna|colunas=cenario_gamma,psi,soma_pp|filtro=modo_redutor=iso_carga&psi=0|fmt=psi:.1f;soma_pp:.2f|rotulos=cenario_gamma:Cenário;psi:ψ;soma_pp:Soma (p.p.)]]
