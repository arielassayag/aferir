"""Núcleo: sistema tri-esfera de alíquotas de referência.

Espelho do desenho legal (LC 214, arts. 349-369 + 472-473):

    Alvo_s = τ_s · D_s + σ · G_s        s ∈ {U, E, M}
    σ = (1 − r) · (τ_U + τ_E + τ_M)     (compras governamentais, art. 473 §1º:
                                         alíquota dos demais entes zerada e a
                                         do comprador = soma das alíquotas
                                         REDUZIDA DE MODO UNIFORME, na
                                         proporção do redutor r — art. 472,
                                         forma legal MULTIPLICATIVA)

com D_s = N·(1−γ_eff) − cb_base_s, onde N é a base ordinária líquida do hiato
de política, γ_eff = γ·(1−ψ) e cb_base_s o redutor de cashback da esfera
(art. 118). O sistema é LINEAR nas três alíquotas.

Modos do redutor (art. 370, ⚑ F8) — parametrizações de σ = (1−r)·Στ:
- "iso_carga": σ é conhecido (art. 370, §§1º-4º: equivalência com a carga
  atual sobre compras públicas, estimada via TRU como proxy de média por
  produto — cota inferior do conceito operação-específico) — o sistema
  DESACOPLA: τ_s = (Alvo_s − σ·G_s)/D_s;
- "sem_redutor": r = 0 ⇒ σ = Στ — sistema 3×3 completo;
- "redutor_total": r = 1 ⇒ σ = 0 — compras públicas não geram receita.

Os três modos cobrem o contínuo r ∈ [0; 1]; o comportamento numérico de
cada modo é idêntico ao da forma subtrativa avaliada no ponto correspondente.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EsferaInput:
    alvo: float        # receita de referência a repor (R$ bi biênio)
    D: float           # base ordinária líquida (já com cashback deduzido)
    G: float           # compras governamentais da esfera (art. 473)


@dataclass(frozen=True)
class SolucaoTriEsfera:
    tau_U: float
    tau_E: float
    tau_M: float
    sigma: float       # alíquota efetiva sobre compras governamentais
    modo: str

    @property
    def soma(self) -> float:
        return self.tau_U + self.tau_E + self.tau_M


def resolve_tri_esfera(
    uniao: EsferaInput,
    estadual: EsferaInput,
    municipal: EsferaInput,
    modo: str = "iso_carga",
    sigma_iso: float | None = None,
) -> SolucaoTriEsfera:
    """Resolve o sistema nacional das três alíquotas de referência."""
    esferas = (uniao, estadual, municipal)
    for e in esferas:
        if e.D <= 0:
            raise ValueError("base líquida não positiva")

    if modo == "iso_carga":
        if sigma_iso is None or sigma_iso < 0:
            raise ValueError("iso_carga exige sigma_iso >= 0")
        taus = [(e.alvo - sigma_iso * e.G) / e.D for e in esferas]
        sigma = sigma_iso
    elif modo == "redutor_total":
        taus = [e.alvo / e.D for e in esferas]
        sigma = 0.0
    elif modo == "sem_redutor":
        # A[i][j] = D_i·1{i=j} + G_i ; b_i = Alvo_i
        A = np.array([[e.D * (i == j) + e.G for j in range(3)]
                      for i, e in enumerate(esferas)])
        b = np.array([e.alvo for e in esferas])
        taus = list(np.linalg.solve(A, b))
        sigma = sum(taus)
    else:
        raise ValueError(f"modo desconhecido: {modo}")

    sol = SolucaoTriEsfera(*map(float, taus), sigma=float(sigma), modo=modo)
    for nome, t in (("tau_U", sol.tau_U), ("tau_E", sol.tau_E), ("tau_M", sol.tau_M)):
        if not 0 < t < 0.60:
            raise ValueError(f"{nome}={t:.4f} fora do domínio de sanidade (0, 0,60)")
    return sol


def vetor_indicativo(
    alvo_j: float,
    D_j: float,
    G_j: float,
    tau_outros: float,
    modo: str = "iso_carga",
    sigma_iso: float | None = None,
    redutor: float = 0.0,
) -> float:
    """Alíquota indicativa de UMA esfera no ente j, com as demais esferas na
    referência nacional (leitura obrigatória: DESIGN §2.6 — alíquota uniforme
    hipotética que reporia a receita da esfera no ente j sobre a base de
    destino do ente j; NÃO é alíquota que o ente fixaria).

    tau_outros = soma das alíquotas nacionais das outras duas esferas.
    redutor = r do art. 472 (forma legal multiplicativa: σ_j = (1−r)·(τ_j +
    tau_outros)); no modo central o redutor entra via sigma_iso.
    """
    if D_j <= 0:
        raise ValueError("D_j não positivo")
    if modo == "iso_carga":
        if sigma_iso is None:
            raise ValueError("iso_carga exige sigma_iso")
        return (alvo_j - sigma_iso * G_j) / D_j
    if modo == "redutor_total":
        return alvo_j / D_j
    if modo == "sem_redutor":
        # σ_j = (1−r)·(τ_j + tau_outros)  ⇒  linear em τ_j
        fator = 1.0 - redutor
        return (alvo_j - fator * tau_outros * G_j) / (D_j + fator * G_j)
    raise ValueError(f"modo desconhecido: {modo}")
