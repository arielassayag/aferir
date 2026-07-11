# Diff contra a linha de base da revisão (Onda 0)

Baseline: `20d6e32` (congelada em 2026-07-12). Estado corrente: working tree sobre `4a1f063`.

## Manchete central (construção B, γ=12,5%, ψ=0, iso-carga)

| componente | baseline | corrente | Δ (p.p.) |
|---|---:|---:|---:|
| tau_CBS_pp | 12.7847 | 13.5308 | +0.7461 |
| tau_E_pp | 15.5244 | 16.1510 | +0.6266 |
| tau_M_pp | 2.7478 | 2.8511 | +0.1033 |
| soma_pp | 31.0568 | 32.5329 | +1.4761 |

### Atribuição do movimento da soma (medida pela grade)

| correção | Δ soma (p.p.) |
|---|---:|
| E7.1 SIFIM imputado excluído da âncora | +1.8318 |
| E7.2 redutores imobiliários do art. 261 | +0.1182 |
| A5 perímetro de G + A2/A3 vigências de combustíveis + interações (resíduo) | -0.4739 |
| **total** | **+1.4761** |

## Construção A (âncoras)

| variante | baseline | corrente | Δ |
|---|---:|---:|---:|
| ancora_legal_2012_2021 | 28.0420 | 28.0476 | +0.0056 |
| meta_pldo_4_47 | 26.6282 | 26.6338 | +0.0056 |

## Trava-conforme (γ central)

- λ*: 0.5368 → 0.7101 (o novo central, maior, exige encolhimento maior dos favorecimentos para fechar em 26,5%).
- Custo dos benefícios suprimidos: R$ 193.6 bi → R$ 241.0 bi/ano.

## Métricas-chave

| chave | baseline | corrente |
|---|---:|---:|
| mediana_tau_E_uf | 16.2885 | 16.8964 |
| mediana_tau_M_uf | 1.6773 | 1.7119 |
| n_uf_acima_ref_E | 15.0000 | 16.0000 |
| cobertura_dca_2024 | 99.2500 | 99.2500 |
| g_municipal_janela | 346.9047 | 385.0582 |
| is_estimado_bi | 17.6001 | 17.6001 |
| pi_p_nacional | 0.2505 | 0.2505 |

As regressões protegidas do parecer (L7) e suas justificativas linha a linha estão em `metadata/qa_regressoes_parecer_l7.csv` (teste bloqueante `tests/test_regressoes_l7.py`).
