---
titulo: "Exemplo integral do contrato do renderizador AFERIR (aferir.manuscript)"
pseudonimo: "AFERIDOR"
tema: "Tema 3 — Federalismo Fiscal e Equilíbrio Interfederativo"
palavras_chave: "exemplo; renderizador; determinismo; dados abertos"
keywords: "example; renderer; determinism; open data"
jel: "H71; H77; H20"
---

# RESUMO

Amostra que exercita toda a sintaxe do gerador: números lidos de CSV como a
soma central de
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:soma_pp:.2f}}
pontos percentuais (CBS
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:tau_CBS_pp:.1f}};
IBS estadual
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:tau_E_pp:.1f}};
IBS municipal
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:tau_M_pp:.1f}}),
ênfase em **negrito** e *itálico*, matemática inline $\tau_E + \tau_M$ e
código `make manuscript`. Nenhum número é digitado no texto.

# ABSTRACT

Sample exercising the full renderer contract: CSV-resolved figures such as
the central sum of
{{csv:aferir_nacional.csv:cenario_gamma=central&psi=0&modo_redutor=iso_carga:soma_pp:.2f}}
percentage points, **bold** and *italic* emphasis, inline math
$\tau_U + \tau_E$ and `code spans`. No number is typed by hand.
