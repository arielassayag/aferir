"""Testes do núcleo puro (sem IO): sistema tri-esfera, cashback, hiatos."""
import math

import pytest

from aferir.cashback import BaseElegivel, base_elegivel, cb_base
from aferir.gaps import pi_combinado
from aferir.rates import EsferaInput, resolve_tri_esfera, vetor_indicativo


def _esferas():
    # ordens de grandeza realistas (R$ bi biênio, preços 2024)
    return (
        EsferaInput(alvo=560.0, D=5600.0, G=60.0),    # União
        EsferaInput(alvo=700.0, D=5600.0, G=250.0),   # Estados
        EsferaInput(alvo=140.0, D=5600.0, G=280.0),   # Municípios
    )


def test_iso_carga_desacopla():
    u, e, m = _esferas()
    sol = resolve_tri_esfera(u, e, m, modo="iso_carga", sigma_iso=0.12)
    assert math.isclose(sol.tau_U, (560 - 0.12 * 60) / 5600, rel_tol=1e-12)
    assert math.isclose(sol.tau_M, (140 - 0.12 * 280) / 5600, rel_tol=1e-12)
    assert sol.sigma == 0.12


def test_sem_redutor_fecha_receita():
    u, e, m = _esferas()
    sol = resolve_tri_esfera(u, e, m, modo="sem_redutor")
    sigma = sol.soma
    for esf, tau in zip((u, e, m), (sol.tau_U, sol.tau_E, sol.tau_M)):
        receita = tau * esf.D + sigma * esf.G
        assert math.isclose(receita, esf.alvo, rel_tol=1e-10)
    # art. 473 vale mais para municípios (G alto, alvo baixo): τ_M cai vs iso
    iso = resolve_tri_esfera(u, e, m, modo="iso_carga", sigma_iso=0.12)
    assert sol.tau_M < iso.tau_M


def test_redutor_total_equivale_g_zero():
    u, e, m = _esferas()
    sol = resolve_tri_esfera(u, e, m, modo="redutor_total")
    assert math.isclose(sol.tau_E, 700 / 5600, rel_tol=1e-12)
    assert sol.sigma == 0.0


def test_vetor_indicativo_consistente_com_nacional():
    u, e, m = _esferas()
    sol = resolve_tri_esfera(u, e, m, modo="sem_redutor")
    # aplicando a fórmula do vetor ao agregado nacional recupera τ_E nacional
    tau_e = vetor_indicativo(
        e.alvo, e.D, e.G, tau_outros=sol.tau_U + sol.tau_M,
        modo="sem_redutor", redutor=0.0,
    )
    assert math.isclose(tau_e, sol.tau_E, rel_tol=1e-10)


def test_dominio_sanidade():
    with pytest.raises(ValueError):
        resolve_tri_esfera(
            EsferaInput(5000.0, 5600.0, 0.0),
            EsferaInput(700.0, 5600.0, 0.0),
            EsferaInput(140.0, 5600.0, 0.0),
            modo="redutor_total",
        )


def test_cashback_assimetrico_por_esfera():
    el = base_elegivel(b_c_liquida=4000.0, f_low=0.10, share_piso=0.15)
    cb_cbs = cb_base("uniao", el)
    cb_ibs = cb_base("estadual", el)
    assert cb_cbs > cb_ibs                       # 100% no piso vs 20% uniforme
    assert math.isclose(cb_ibs, 0.20 * 400.0, rel_tol=1e-12)
    assert math.isclose(cb_cbs, 1.00 * 60.0 + 0.20 * 340.0, rel_tol=1e-12)
    assert cb_base("municipal", el) == cb_ibs    # IBS uniforme nas duas esferas


def test_pi_combinado():
    assert math.isclose(pi_combinado(0.20, 0.125), 1 - 0.80 * 0.875, rel_tol=1e-12)
    # ψ=1 elimina o hiato de conformidade; zfm é aditivo ao de política
    assert math.isclose(pi_combinado(0.20, 0.125, psi=1.0), 0.20, rel_tol=1e-12)
    assert pi_combinado(0.20, 0.125, zfm=0.13) > pi_combinado(0.20, 0.125)
    with pytest.raises(ValueError):
        pi_combinado(0.2, 0.9)
