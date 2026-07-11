"""Hiatos: política (matriz POF×LC 214) e conformidade (corredor oficial).

π^p (policy gap) vem da matriz legal item a item vendorada em
`data/inputs/matriz_pof_ibs_v5.csv` (13.474 itens; m_i ∈ {0; 0,30; 0,40;
0,60; 0,70; 1,00}; flag F = fora do campo, arts. 4º/6º LC 214 — itens F saem
da base e os pesos são renormalizados).

Conformidade (γ): corredor da NT SERT/MF jul/2024 (convenção Hungria)
[10%; 15%], ponto central 12,5% = hiato de neutralidade implícito no FMI
WP/2025/266. Corredor ÚNICO para as três esferas: pela LC 214, art. 15, a
alíquota da operação é a soma das parcelas sobre base única — conformidade é
propriedade da operação, não da esfera (DESIGN §2.2).
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config
from .provenance import MANIFEST, Label, Num

MATRIZ_PATH = config.V2_ROOT / "data" / "inputs" / "matriz_pof_ibs_v5.csv"

# ------------------------------------------------- classes de regime (E3)
# Partição DERIVADA DA PRÓPRIA MATRIZ: nível m_i × conteúdo textual de
# tratamento_ibs_v3 (regex determinísticos sobre o texto em MAIÚSCULAS).
# O nível m=0,40 (redução de 60%, arts. 126-137 e Anexos da LC 214) é o único
# heterogêneo e é subdividido em saúde / educação / alimentos / demais, na
# ORDEM DE PRECEDÊNCIA abaixo (primeiro regex que casa decide).
_RE_SAUDE_60 = (r"SAÚDE|SAUDE|MEDICAMENT|ANVISA|MÉDIC|ODONTOLÓG|HOSPITALAR|"
                r"LABORATORIA|MENSTRUAL|DISPOSITIVOS_IV")
_RE_EDUCACAO_60 = r"EDUCAÇ|EDUCAC|ENSINO"
_RE_ALIMENTOS_60 = (r"ALIMENT|ANEXO VII\b|ANEXO IX\b|IOGURTE|ÓLEOS VEGETAIS|"
                    r"PAO_FORMA|AMIDO_MILHO|MASSAS_COZIDAS")

# Classes com favorecimento (1−m_i > 0) alcançadas pelo PLP do art. 475, §11.
# NÃO inclui 'padrao' (m=1, sem favorecimento), 'fora_campo' (arts. 4º/6º,
# fora do alcance do §11) nem a pseudo-classe 'zfm' (adendo de política do AM,
# tratada no orquestrador — pipeline._d_esfera).
CLASSES_FAVORECIDAS = (
    "cesta_aliquota_zero",       # m=0,00 — alíquota zero/imunidade
    "saude_60",                  # m=0,40 — saúde e medicamentos
    "educacao_60",               # m=0,40 — serviços de educação
    "alimentos_60",              # m=0,40 — alimentos (Anexos VII/IX)
    "demais_60",                 # m=0,40 — higiene/limpeza, funerária etc.
    "reducao_40_especificos",    # m=0,60 — regimes específicos (bares, hotelaria...)
    "reducao_30",                # m=0,70 — profissões regulamentadas
    "reducao_70_imoveis",        # m=0,30 — locação de bens imóveis
)


def classifica_regime() -> pd.DataFrame:
    """Classe de regime favorecido por item da matriz legal VENDORADA.

    Partição determinística dos 13.474 itens por (m_i × tratamento_ibs_v3):
    flag F → 'fora_campo'; m=1 → 'padrao'; m=0 → 'cesta_aliquota_zero';
    m=0,30 → 'reducao_70_imoveis'; m=0,60 → 'reducao_40_especificos';
    m=0,70 → 'reducao_30'; m=0,40 → saúde/educação/alimentos/demais_60 por
    regex sobre tratamento_ibs_v3 (precedência: saúde > educação > alimentos).
    Usada pelo corte por classe da trava (perfis_trava.py) e pelo parâmetro
    lam: dict de policy_gap_por_uf. Retorna [codigo_pof, m_i, flag, classe].
    """
    bruto = pd.read_csv(MATRIZ_PATH, dtype={"codigo_pof": str})
    bruto = bruto.rename(columns={"m_i_v3": "m_i", "flag_v3": "flag"})
    if bruto["codigo_pof"].duplicated().any():
        raise ValueError("matriz legal com codigo_pof duplicado")
    trat = bruto["tratamento_ibs_v3"].fillna("").str.upper()
    m, flag = bruto["m_i"], bruto["flag"]
    condicoes = [
        flag.eq("F"),
        m.eq(1.0),
        m.eq(0.0),
        m.eq(0.30),
        m.eq(0.60),
        m.eq(0.70),
        m.eq(0.40) & trat.str.contains(_RE_SAUDE_60, regex=True),
        m.eq(0.40) & trat.str.contains(_RE_EDUCACAO_60, regex=True),
        m.eq(0.40) & trat.str.contains(_RE_ALIMENTOS_60, regex=True),
        m.eq(0.40),
    ]
    rotulos = ["fora_campo", "padrao", "cesta_aliquota_zero",
               "reducao_70_imoveis", "reducao_40_especificos", "reducao_30",
               "saude_60", "educacao_60", "alimentos_60", "demais_60"]
    classe = np.select(condicoes, rotulos, default="")
    if (classe == "").any():
        orfaos = bruto.loc[classe == "", "codigo_pof"].tolist()[:5]
        raise ValueError(f"itens sem classe de regime (m_i fora dos níveis?): {orfaos}")
    out = bruto[["codigo_pof", "m_i", "flag"]].copy()
    out["classe"] = classe
    return out


@lru_cache(maxsize=1)
def _classe_por_codigo() -> pd.Series:
    """Cache codigo_pof → classe (Series imutável por convenção; só .map)."""
    c = classifica_regime()
    return c.set_index("codigo_pof")["classe"]


def carrega_matriz() -> pd.DataFrame:
    """Matriz legal: codigo_pof -> (m_i, flag F, dispositivo)."""
    m = pd.read_csv(MATRIZ_PATH, dtype={"codigo_pof": str})
    m = m.rename(columns={"m_i_v3": "m_i", "flag_v3": "flag"})
    cols = ["codigo_pof", "m_i", "flag", "art_lc_214_v3"]
    m = m[cols].copy()
    if m["codigo_pof"].duplicated().any():
        raise ValueError("matriz legal com codigo_pof duplicado")
    if not m["m_i"].dropna().isin([0.0, 0.30, 0.40, 0.60, 0.70, 1.0]).all():
        raise ValueError("m_i fora dos seis níveis canônicos")
    return m


def policy_gap_por_uf(despesa_item_uf: pd.DataFrame,
                      lam: float | Mapping[str, float] = 0.0,
                      matriz: pd.DataFrame | None = None) -> pd.DataFrame:
    """π^p por UF sobre a despesa DENTRO do campo (flag F excluída, pesos
    renormalizados).

    lam = fração de encolhimento dos regimes favorecidos (trava do art. 475,
    §11, LC 214 — módulos trava.py e perfis_trava.py):
      float — encolhimento UNIFORME: m_i(λ) = m_i + λ·(1−m_i) nos itens EM
        CAMPO; flag F (fora do campo, arts. 4º/6º) intocada. λ=0 reproduz a
        matriz legal vigente; λ=1 suprime todos os favorecimentos.
        Identidade implicada (testada): π^p(λ) = (1−λ)·π^p(0), UF a UF.
      dict[classe → λ_c] — encolhimento POR CLASSE de regime (E3): cada item
        recebe o λ da sua classe (classifica_regime, sempre derivada da
        matriz VENDORADA); classe ausente do dict ⇒ λ_c = 0. Com todas as
        classes favorecidas no MESMO λ, reproduz o caminho float bit a bit.

    matriz = matriz legal ALTERNATIVA [codigo_pof, m_i, flag] (contrafactuais
    de classificação — aferir.classificacao, E2); None = matriz vendorada.
    A proveniência de pi_p_nacional só é registrada com a matriz central.

    despesa_item_uf: [codigo_pof, uf, despesa_anual_rs]
    Retorna: [uf, pi_p, share_fora_campo, despesa_em_campo]
    """
    if isinstance(lam, Mapping):
        for c, v in lam.items():
            if not 0.0 <= float(v) <= 1.0:
                raise ValueError(f"λ da classe '{c}' fora de [0; 1]")
    elif not 0.0 <= lam <= 1.0:
        raise ValueError("λ fora de [0; 1]")
    if matriz is None:
        m = carrega_matriz()
    else:
        m = matriz[["codigo_pof", "m_i", "flag"]].copy()
        if m["codigo_pof"].duplicated().any():
            raise ValueError("matriz alternativa com codigo_pof duplicado")
    df = despesa_item_uf.merge(m, on="codigo_pof", how="left", validate="m:1")
    if isinstance(lam, Mapping):
        # λ por item via classe de regime (item sem classe/matriz ⇒ λ=0)
        classes = df["codigo_pof"].map(_classe_por_codigo())
        lam_i = classes.map(
            lambda c: float(lam.get(c, 0.0)) if isinstance(c, str) else 0.0)
        df["m_i"] = df["m_i"] + lam_i * (1.0 - df["m_i"])   # m_i(λ_classe)
    else:
        df["m_i"] = df["m_i"] + lam * (1.0 - df["m_i"])   # m_i(λ); NaN preservado
    sem_ref = df["m_i"].isna() & (df["flag"] != "F")
    perda = df.loc[sem_ref, "despesa_anual_rs"].sum() / df["despesa_anual_rs"].sum()
    if perda > 0.01:
        raise ValueError(f"{perda:.2%} da despesa sem correspondência na matriz (>1%)")

    linhas = []
    for uf, g in df.groupby("uf"):
        total = g["despesa_anual_rs"].sum()
        fora = g.loc[g["flag"] == "F", "despesa_anual_rs"].sum()
        em_campo = g[g["flag"] != "F"].dropna(subset=["m_i"])
        base = em_campo["despesa_anual_rs"].sum()
        pi_p = float((em_campo["despesa_anual_rs"] * (1 - em_campo["m_i"])).sum() / base)
        linhas.append(
            {"uf": uf, "pi_p": pi_p, "share_fora_campo": fora / total,
             "despesa_em_campo": base}
        )
    out = pd.DataFrame(linhas).sort_values("uf").reset_index(drop=True)
    nacional = (
        (df[df["flag"] != "F"].dropna(subset=["m_i"])
         .eval("despesa_anual_rs * (1 - m_i)").sum())
        / df[df["flag"] != "F"].dropna(subset=["m_i"])["despesa_anual_rs"].sum()
    )
    if not isinstance(lam, Mapping) and lam == 0.0 and matriz is None:
        # proveniência só da matriz vigente (λ uniforme nulo)
        MANIFEST.registra(
            "pi_p_nacional",
            Num(float(nacional), "Σ w_i(1−m_i) / Σ w_i, i∉F", str(MATRIZ_PATH.name),
                Label.DERIVADO, "fração"),
        )
    return out


def pi_combinado(pi_p: float, gamma: float, psi: float = 0.0,
                 zfm: float = 0.0) -> float:
    """Hiato total: 1 − (1−π^p−zfm)·(1−γ·(1−ψ)).

    γ = hiato de conformidade (corredor SERT [0,10; 0,15]; central 0,125);
    ψ = mitigação por split payment (CENÁRIO, fora do central — DESIGN F1);
    zfm = adendo de política da ZFM (só AM, aditivo a π^p como no v1).
    """
    if not 0 <= gamma <= 0.5 or not 0 <= psi <= 1:
        raise ValueError("γ ou ψ fora do domínio")
    return 1 - (1 - pi_p - zfm) * (1 - gamma * (1 - psi))
