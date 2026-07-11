"""SIFIM e FBCF imobiliária — quantificação dos dois desvios de base (E7).

O manuscrito declara hoje (Anexo C) que serviços financeiros ficam "ao
padrão, sem dedução em nenhuma das pontas" e que os redutores imobiliários
da LC 214 não estão aplicados. O superdocumento (E7) exige QUANTIFICAR os
dois canais, porque chamá-los de segunda ordem sem cálculo é incompatível
com a comparação do resultado ao gatilho em décimos de ponto.

E7.1 — SIFIM (serviços de intermediação financeira indiretamente medidos):
  a TRU 2021 nível 68 aloca o SIFIM DENTRO do produto 64801 ("Intermediação
  financeira, seguros e previdência complementar") — não existe linha nem
  coluna explícita de SIFIM/ajuste nas planilhas 68_tab1/tab2 (verificado;
  alocação setorial é a convenção do SCN referência 2010). O consumo das
  famílias do 64801 mistura, portanto, serviço imputado SEM operação
  onerosa (fora do campo do IBS/CBS — LC 214, art. 4º: o fato gerador é
  operação ONEROSA) com tarifas, juros e prêmios explícitos (operações
  onerosas, regime específico dos arts. 181-183). O split é estimado por
  resíduo: explícito medido na POF (escalado ao nível TRU-2021 por fator
  interno declarado) e imputado = produto − explícito (cota, CONVENCAO).

E7.2 — FBCF imobiliária: a FBCF não-corporativa entra hoje em B^ord com
  m=1,00 (convenção legal art. 200, §4º). A parcela RESIDENCIAL NOVA,
  porém, segue o regime de bens imóveis da LC 214: alíquota reduzida em
  50% (art. 261, caput), redutor social de R$ 100.000 por imóvel novo
  residencial e R$ 30.000 por lote (art. 259) e redutor de ajuste
  (arts. 257-258). A parcela residencial é identificada por composição:
  share de Edificações (41801) na FBCF da própria TRU × share residencial
  das obras novas de edifícios na PAIC 2021 (SIDRA, agregado 1740).

Artefatos: data/processed/ajuste_sifim.csv e ajuste_fbcf_imobiliaria.csv.
As alavancas correspondentes em base.base_ordinaria_uf (sifim=,
fbcf_imob=) leem estes CSVs; o flip do central é decisão do orquestrador.

Efeitos em p.p.: aproximação de 1ª ordem Δτ_s ≈ τ_s·(D_s/D_s'−1), com
D_s recomputado por espelho do pipeline (mesmo padrão de
cashback.qa_custo_cashback — pipeline.py é do orquestrador, não importar)
sobre os valores CENTRAIS vigentes de base_uf.csv/aferir_nacional.csv.
Os processados estão em regeneração: os p.p. são declaradamente
RE-BASELINÁVEIS (ordem de grandeza; recalcular no fechamento).

Uso: PYTHONPATH=src python3 -m aferir.sifim_fbcf
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd

from . import config
from .cashback import ZFM_AM_ESPELHO, base_elegivel, cb_base
from .gaps import pi_combinado
from .provenance import MANIFEST, Label, Num, sha256_file

# ------------------------------------------------------------------ caminhos
RAW_SIDRA_FBCF = config.RAW / "sidra_fbcf"
PAIC_JSON = RAW_SIDRA_FBCF / "paic_1740_2021_v1246_c358.json"
PAIC_URL = ("https://servicodados.ibge.gov.br/api/v3/agregados/1740/periodos/"
            "2021/variaveis/1246?localidades=N1[all]&classificacao=358[all]")
LC214_HTML = config.RAW / "normas" / "planalto" / "lcp214.htm"
CSV_SIFIM = config.PROCESSED / "ajuste_sifim.csv"
CSV_FBCF = config.PROCESSED / "ajuste_fbcf_imobiliaria.csv"

# ------------------------------------------------- produto financeiro na TRU
# Único produto com 'financeir/segur/previdênc' e consumo das famílias > 0 na
# TRU 2021 nível 68 (verificação exaustiva: 80001 vigilância/segurança e
# 84002 previdência SOCIAL têm consumo_familias 539 e 0 R$ mi — não são
# serviços financeiros de mercado).
TRU_PRODUTO_FINANCEIRO = "64801"

# ------------------------------------- categorias PAIC (classificação 358)
# Obras NOVAS de edifícios (PRODLIST-Construção, grupo CNAE 4120) — ids da
# própria API (metadados do agregado 1740). Reformas/manutenção (4120.9030/
# 9040) EXCLUÍDAS (não são FBCF nova; o redutor social do art. 259 só alcança
# imóvel NOVO); incorporação 4110 EXCLUÍDA (valor de incorporação sobre
# imóveis construídos por OUTRAS empresas — dupla contagem com 4120 e sem
# split residencial/não-residencial).
PAIC_CAT_RESIDENCIAIS = {
    "8315": "4120.2040 Edifícios residenciais",
    "8318": "4120.9020 Montagem de edifícios residenciais pré-fabricados",
}
PAIC_CAT_NAO_RESIDENCIAIS = {
    "8312": "4120.2010 Edifícios comerciais",
    "8313": "4120.2020 Edifícios industriais",
    "8314": "4120.2030 Edifícios não-residenciais n.e.",
    "8316": "4120.2050 Estações e terminais",
    "8317": "4120.9010 Montagem de edifícios não-residenciais pré-fabricados",
}

_UA = {"User-Agent": "Mozilla/5.0 (aferir; rotina publica de dados abertos)"}


# ==================================================================== fetch
def _grava_meta(destino: Path, url: str, *, status_http: int | None,
                origem: str, descricao: str) -> None:
    """Sidecar `<arquivo>._meta.json` (padrão dos fetchers do pacote)."""
    from datetime import datetime, timezone
    meta = {
        "url": url,
        "sha256": sha256_file(destino),
        "bytes": destino.stat().st_size,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status_http": status_http,
        "origem": origem,
        "descricao": descricao,
    }
    meta_path = destino.with_name(destino.name + "._meta.json")
    tmp = meta_path.with_name(meta_path.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, meta_path)


def fetch_paic_1740(*, force: bool = False) -> Path:
    """Baixa (seed-first, atômico) a PAIC 2021 — agregado 1740, var. 1246
    (valor das incorporações, obras e/ou serviços, R$ mil), classificação
    358 (classes CNAE × produtos PRODLIST-Construção), Brasil."""
    RAW_SIDRA_FBCF.mkdir(parents=True, exist_ok=True)
    meta_path = PAIC_JSON.with_name(PAIC_JSON.name + "._meta.json")
    if PAIC_JSON.exists() and not force:
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("sha256") == sha256_file(PAIC_JSON):
                return PAIC_JSON
        _grava_meta(PAIC_JSON, PAIC_URL, status_http=None,
                    origem="cache_local", descricao=_PAIC_DESCRICAO)
        return PAIC_JSON

    import requests
    resp = requests.get(PAIC_URL, headers=_UA, timeout=120)
    resp.raise_for_status()
    payload = resp.json()
    if not payload or payload[0].get("id") != "1246":
        raise ValueError("PAIC 1740: payload inesperado (variável != 1246)")
    tmp = PAIC_JSON.with_name(PAIC_JSON.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, PAIC_JSON)
    _grava_meta(PAIC_JSON, PAIC_URL, status_http=resp.status_code,
                origem="download", descricao=_PAIC_DESCRICAO)
    return PAIC_JSON


_PAIC_DESCRICAO = ("SIDRA/PAIC agregado 1740 (2021): valor das incorporações, "
                   "obras e/ou serviços das empresas de construção com 30+ "
                   "PO, var 1246, classificação 358 (classes CNAE x produtos "
                   "PRODLIST-Construção), Brasil")


# ============================================================ PAIC → share
def paic_valores_2021() -> dict[str, float]:
    """Valores 2021 por categoria da classificação 358 (R$ bi correntes)."""
    payload = json.loads(PAIC_JSON.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for r in payload[0]["resultados"]:
        (cid, _nome), = r["classificacoes"][0]["categoria"].items()
        v = r["series"][0]["serie"].get("2021")
        if v not in (None, "-", "..", "...", "X"):
            out[cid] = float(v) / 1e6          # R$ mil -> R$ bi
    return out


def share_residencial_paic() -> Num:
    """Share residencial das obras NOVAS de edifícios (PAIC 2021, Brasil).

    Cobertura declarada: empresas de construção com 30+ pessoas ocupadas —
    a produção informal/autoconstrução (relevante no residencial) está fora
    da PAIC, logo o share é COTA INFERIOR para o mix da FBCF não-corporativa
    (viés declarado PARA BAIXO no ajuste)."""
    v = paic_valores_2021()
    faltam = [c for c in (*PAIC_CAT_RESIDENCIAIS, *PAIC_CAT_NAO_RESIDENCIAIS)
              if c not in v]
    if faltam:
        raise ValueError(f"PAIC 1740/2021 sem categorias {faltam}")
    res = sum(v[c] for c in PAIC_CAT_RESIDENCIAIS)
    nao_res = sum(v[c] for c in PAIC_CAT_NAO_RESIDENCIAIS)
    share = res / (res + nao_res)
    return Num(
        share,
        "Σ(4120.2040 + 4120.9020) ÷ Σ(obras novas de edifícios: 4120.2010/"
        "2020/2030/2040/2050 + 4120.9010/9020) — reformas (4120.9030/9040) e "
        "incorporação (4110) excluídas",
        f"PAIC 2021, SIDRA agregado 1740, var. 1246, classif. 358 ({PAIC_URL})",
        Label.DERIVADO, "fração",
    )


# ===================================================== LC 214 — regime imob.
def lc214_regime_imobiliario() -> dict[str, Num]:
    """Parâmetros do regime de bens imóveis LIDOS do texto compilado da
    LC 214 (data/raw/normas/planalto/lcp214.htm) — nenhum número de memória.

    Retorna: reducao_aliquota_pct (art. 261, caput), reducao_locacao_pct
    (art. 261, parágrafo único), redutor_social_novo_rs e
    redutor_social_lote_rs (art. 259, caput)."""
    if not LC214_HTML.exists():
        raise FileNotFoundError(
            f"{LC214_HTML} ausente — rodar aferir.fetch.planalto antes")
    raw = LC214_HTML.read_bytes().decode("cp1252", errors="replace")
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = re.sub(r"\s+", " ", txt)
    fonte = f"LC 214/2025, texto compilado Planalto ({LC214_HTML.name})"

    i261 = txt.find("Art. 261.")
    if i261 < 0:
        raise ValueError("LC 214: art. 261 não localizado no HTML")
    art261 = txt[i261:txt.find("Art. 262.")]
    caput = art261.split("Parágrafo único", 1)[0]
    m = re.search(r"reduzidas em (\d+)% \(", caput)
    if not m:
        raise ValueError("LC 214, art. 261, caput: percentual não localizado")
    red_cap = float(m.group(1))
    m = re.search(r"reduzidas em (\d+)% \(", art261[len(caput):])
    if not m:
        raise ValueError("LC 214, art. 261, p.ú.: percentual não localizado")
    red_loc = float(m.group(1))

    i259 = txt.find("Art. 259.")
    if i259 < 0:
        raise ValueError("LC 214: art. 259 não localizado no HTML")
    art259 = txt[i259:txt.find("Art. 260.")]
    m = re.search(r"redutor social no valor de R\$ ?([\d.]+),00"
                  r".{0,80}?por bem im[oó]vel residencial novo", art259)
    if not m:
        raise ValueError("LC 214, art. 259: redutor de imóvel novo não localizado")
    social_novo = float(m.group(1).replace(".", ""))
    m = re.search(r"R\$ ?([\d.]+),00 \(trinta mil reais\) por lote", art259)
    if not m:
        raise ValueError("LC 214, art. 259: redutor de lote não localizado")
    social_lote = float(m.group(1).replace(".", ""))

    return {
        "reducao_aliquota_pct": Num(red_cap, "texto literal do caput",
                                    f"{fonte}, art. 261, caput",
                                    Label.OFICIAL, "%"),
        "reducao_locacao_pct": Num(red_loc, "texto literal do parágrafo único",
                                   f"{fonte}, art. 261, parágrafo único",
                                   Label.OFICIAL, "%"),
        "redutor_social_novo_rs": Num(social_novo, "texto literal do caput",
                                      f"{fonte}, art. 259, caput",
                                      Label.OFICIAL, "R$/imóvel novo"),
        "redutor_social_lote_rs": Num(social_lote, "texto literal do caput",
                                      f"{fonte}, art. 259, caput",
                                      Label.OFICIAL, "R$/lote"),
    }


# ========================================================= POF — explícito
def componentes_pof_financeiros() -> pd.DataFrame:
    """Despesa POF anual (R$ de 15/01/2018) dos itens financeiros EXPLÍCITOS,
    por componente, com a lista de códigos usada.

    Identificação pela PRÓPRIA matriz legal vendorada (matriz_pof_ibs_v5.csv):
      tarifas_bancarias  — flag A no grupo POF 'Serviços bancários';
      juros_credito      — art_lc_214_v3 cita art. 182, I (operações de
                           crédito; a POF registra o FLUXO de juros — no SCN
                           só a margem SIFIM é consumo: viés declarado);
      seguros            — art_lc_214_v3 cita art. 182, XI (a POF registra
                           prêmios BRUTOS; no SCN o serviço é prêmios −
                           indenizações: viés declarado, sinal oposto);
      previdencia_capitalizacao — flag F (fora do campo, art. 6º), mas o
                           serviço correspondente integra o produto 64801 e
                           permanece na âncora (resíduo declarado de base.py).
    Planos de saúde NÃO entram: produto TRU próprio (86921, Saúde privada).
    """
    m = pd.read_csv(config.INPUTS / "matriz_pof_ibs_v5.csv",
                    dtype={"codigo_pof": str})
    d = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    d["codigo_pof"] = d["codigo_pof"].astype(str)
    gasto = d.groupby("codigo_pof")["despesa_anual_rs"].sum()

    art = m["art_lc_214_v3"].fillna("")
    grupo = m["grupo_pof"].fillna("")
    comp = {
        "tarifas_bancarias": set(
            m.loc[(grupo == "Serviços bancários") & (m["flag_v3"] == "A"),
                  "codigo_pof"]),
        "juros_credito": set(m.loc[art.str.contains("182, I,", regex=False),
                                   "codigo_pof"]),
        "seguros": set(m.loc[art.str.contains("182, XI", regex=False),
                             "codigo_pof"]),
        "previdencia_capitalizacao": {
            "4800601", "4800602", "4800603",      # previdência privada (F)
            "4803301", "4803302",                 # título de capitalização (F)
            "4803501",                            # consórcio de dinheiro (F)
        },
    }
    linhas = []
    for nome, cods in comp.items():
        cods_s = sorted(cods)
        linhas.append({
            "componente": nome,
            "despesa_pof_2018_rs_bi": float(
                gasto.reindex(cods_s).fillna(0.0).sum()) / 1e9,
            "codigos_pof": " ".join(cods_s),
        })
    return pd.DataFrame(linhas)


def escala_pof_para_tru() -> Num:
    """Fator interno POF-2018 → nível TRU-2021 (CONVENCAO declarada).

    escala = C_fam TRU 2021 (Σ 128 produtos) ÷ despesa POF total (Σ itens ×
    UFs, preços de 15/01/2018). Corrige SIMULTANEAMENTE o nível de preços
    2018→2021 e a cobertura média POF vs. SCN. Limite declarado: a correção
    é MÉDIA — itens financeiros podem sub-reportar mais que a média (resíduo
    vira cota SUPERIOR do imputado); sensibilidade com escala só-IPCA
    (sem correção de cobertura) reportada no CSV."""
    tru = pd.read_parquet(config.PROCESSED / "tru_2021_usos.parquet")
    d = pd.read_parquet(config.PROCESSED / "pof_despesa_item_uf.parquet")
    c_fam = float(tru["consumo_familias"].sum()) / 1e3          # R$ bi
    pof = float(d["despesa_anual_rs"].sum()) / 1e9              # R$ bi
    return Num(c_fam / pof,
               "C_fam_TRU2021_total ÷ Σ despesa_anual_rs POF (preços 15/01/2018)",
               "tru_2021_usos.parquet + pof_despesa_item_uf.parquet",
               Label.CONVENCAO, "razão")


def escala_ipca_2018_2021() -> Num:
    """Fator só-preços: IPCA médio de 2021 ÷ IPCA de janeiro/2018 (preços da
    POF são de 15/01/2018). Sensibilidade da escala (sem cobertura)."""
    i = pd.read_parquet(config.RAW / "sidra" / "ipca_1737.parquet")
    v = i.set_index("D3N")["V"].astype(float)
    meses_2021 = [f"{m} 2021" for m in
                  ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
                   "julho", "agosto", "setembro", "outubro", "novembro",
                   "dezembro")]
    fator = float(v.loc[meses_2021].mean() / v.loc["janeiro 2018"])
    return Num(fator, "média(IPCA número-índice 2021) ÷ IPCA janeiro/2018",
               "IBGE SIDRA 1737 (ipca_1737.parquet)", Label.DERIVADO, "razão")


# ============================== validação externa BCB/SGS — FISIM-PF 2021
def fisim_pf_bcb_2021() -> Num:
    """FISIM das famílias pelo lado dos EMPRÉSTIMOS, 2021 — âncora externa
    por dados abertos BCB/SGS (auditoria de nível de 13/07/2026,
    metadata/auditoria_nivel_2026_07_13.md, §SIFIM), reproduzida EXATAMENTE:

        média jan-dez/2021 do saldo da carteira de crédito PF (SGS 20541,
        R$ mi ÷ 1e3 → R$ bi) × (média 2021 do ICC-PF, taxa do ESTOQUE,
        SGS 25353 − média 2021 da Selic anualizada, SGS 4189) ÷ 100.

    Cota SUPERIOR do SIFIM-famílias (inclui habitacional — CI de aluguéis no
    SNA 2008 —, crédito de PF-produtora e a cunha taxa de referência
    IBGE>Selic): valida que o resíduo interno não é exagerado. Determinística
    sobre o snapshot versionado (rota local: sem rede se o CSV existe)."""
    from .fetch.bcb_sgs import (BCB_SGS_CSV, SGS_ICC_PF, SGS_SALDO_PF,
                                SGS_SELIC, fetch_bcb_sgs_fisim_pf)
    df = pd.read_csv(fetch_bcb_sgs_fisim_pf())
    medias: dict[int, float] = {}
    for codigo in (SGS_SALDO_PF, SGS_ICC_PF, SGS_SELIC):
        v = df.loc[df["codigo"] == codigo, "valor"].astype(float)
        if len(v) != 12:
            raise ValueError(f"SGS {codigo}: {len(v)} observações no snapshot "
                             f"{BCB_SGS_CSV.name} (esperadas 12 de 2021)")
        medias[codigo] = float(v.mean())
    saldo_bi = medias[SGS_SALDO_PF] / 1e3
    valor = saldo_bi * (medias[SGS_ICC_PF] - medias[SGS_SELIC]) / 100.0
    return Num(
        valor,
        f"média_2021(SGS {SGS_SALDO_PF} saldo crédito PF, R$ mi)÷1e3 "
        f"[{saldo_bi:.1f} R$ bi] × (média_2021(SGS {SGS_ICC_PF} ICC-PF "
        f"taxa do estoque, % a.a.) [{medias[SGS_ICC_PF]:.4f}] − "
        f"média_2021(SGS {SGS_SELIC} Selic anualizada, % a.a.) "
        f"[{medias[SGS_SELIC]:.4f}])÷100",
        "API BCB/SGS (https://api.bcb.gov.br/dados/serie/bcdata.sgs."
        "{20541,25353,4189}/dados, dados abertos, sem credencial); snapshot "
        f"versionado {BCB_SGS_CSV.name} (data/inputs)",
        Label.DERIVADO, "R$ bi 2021",
    )


# ================================================= espelho D_s (1ª ordem)
def _d_esferas_espelho(shrink_bc: float = 0.0,
                       shrink_fbcf: float = 0.0) -> dict[str, float]:
    """D_s por esfera (R$ bi, média do biênio) reproduzindo pipeline._d_esfera
    SEM importá-lo (mesmo padrão de cashback.qa_custo_cashback), no central
    γ=0,125, ψ=0, λ=0, zfm_AM=0,13: para cada UF de base_uf.csv,
    D = (B_C·(1−s_bc) + B_ISFLSF)·(1−π) + B_FBCF_NC·(1−s_f)·(1−γ) − cb_base,
    com o cashback recomputado sobre a base encolhida."""
    b = pd.read_csv(config.PROCESSED / "base_uf.csv")
    gamma = config.GAP_CONFORMIDADE["central"]
    out = {s: 0.0 for s in config.ESFERAS}
    for _, r in b.iterrows():
        zfm = ZFM_AM_ESPELHO if r["uf"] == "AM" else 0.0
        pi = pi_combinado(r["pi_p"], gamma, 0.0, zfm)
        bc = r["B_C"] * (1.0 - shrink_bc)
        n = ((bc + r["B_ISFLSF"]) * (1 - pi)
             + r["B_FBCF_NC"] * (1.0 - shrink_fbcf) * (1 - gamma))
        el = base_elegivel(bc * (1 - pi), r["f_low"], r["share_piso"])
        for s in config.ESFERAS:
            out[s] += n - cb_base(s, el)
    return out


def _tau_central() -> dict[str, float]:
    """Alíquotas centrais vigentes (γ=0,125, ψ=0, iso_carga) em p.p."""
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    c = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
            & (nac.modo_redutor == "iso_carga")].iloc[0]
    return {"uniao": float(c.tau_CBS_pp), "estadual": float(c.tau_E_pp),
            "municipal": float(c.tau_M_pp)}


def efeitos_pp(shrink_bc: float = 0.0,
               shrink_fbcf: float = 0.0) -> dict[str, float]:
    """Δτ_s de 1ª ordem (p.p.): Δτ_s ≈ τ_s·(D_s/D_s'−1) — alvos, g-fatores e
    σ iso-carga FIXOS (o efeito endógeno completo é papel do pipeline)."""
    d0 = _d_esferas_espelho()
    d1 = _d_esferas_espelho(shrink_bc=shrink_bc, shrink_fbcf=shrink_fbcf)
    tau = _tau_central()
    return {s: tau[s] * (d0[s] / d1[s] - 1.0) for s in config.ESFERAS}


def efeitos_pp_grade(rotulo_sens: str) -> dict[str, float]:
    """Δτ_s ENDÓGENO da grade (p.p.): τ_s do central corrente MENOS τ_s da
    linha de sensibilidade `rotulo_sens` de aferir_nacional.csv (a alavanca
    de base.py está no CENTRAL; a linha sens_* reverte a convenção)."""
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    cen = nac[(nac.cenario_gamma == "central") & (nac.psi == 0.0)
              & (nac.modo_redutor == "iso_carga")]
    rev = nac[nac.cenario_gamma == rotulo_sens]
    if len(cen) != 1 or len(rev) != 1:
        raise ValueError(f"grade sem central único ou sem linha {rotulo_sens!r}"
                         " — rode aferir.pipeline antes")
    c, r = cen.iloc[0], rev.iloc[0]
    return {"uniao": float(c.tau_CBS_pp - r.tau_CBS_pp),
            "estadual": float(c.tau_E_pp - r.tau_E_pp),
            "municipal": float(c.tau_M_pp - r.tau_M_pp)}


def _escalas_bienio() -> tuple[float, float]:
    """(escala_bienio, escala_bienio_fbcf) do MANIFEST_RUN.json vigente
    (gravado pelo pipeline; declarado re-baselinável)."""
    man = json.loads((config.PROCESSED / "MANIFEST_RUN.json")
                     .read_text(encoding="utf-8"))
    return (float(man["nums"]["escala_bienio"]["valor"]),
            float(man["nums"]["escala_bienio_fbcf"]["valor"]))


# ================================================================ E7.1 CSV
_RE_BASELINE = ("valores centrais VIGENTES de base_uf.csv/aferir_nacional.csv/"
                "MANIFEST_RUN.json — processados em regeneração; efeito "
                "declarado RE-BASELINÁVEL (1ª ordem)")


def split_sifim(grava: bool = True) -> pd.DataFrame:
    """ajuste_sifim.csv — split explícito × imputado do produto 64801 e
    efeito da exclusão do imputado nas alíquotas (1ª ordem).

    Fronteira declarada (lado do NUMERADOR): o ISS de serviços financeiros
    não é mensurável com dado aberto — o SICONFI/DCA reporta o ISSQN como
    conta única (1.1.1.4.51.1.0), sem desagregação por atividade/item da
    LC 116, e não existe fonte aberta nacional alternativa. Reporta-se o
    break-even: a participação do ISS financeiro no alvo municipal que
    neutralizaria o efeito-base do tratamento por alíquota própria."""
    tru = pd.read_parquet(config.PROCESSED / "tru_2021_usos.parquet")
    fin = tru[tru["produto_cod"].astype(str) == TRU_PRODUTO_FINANCEIRO]
    if len(fin) != 1:
        raise ValueError(f"produto {TRU_PRODUTO_FINANCEIRO} ausente da TRU")
    c_fin = float(fin["consumo_familias"].iloc[0]) / 1e3        # R$ bi 2021
    desc_fin = str(fin["produto_desc"].iloc[0])

    comp = componentes_pof_financeiros()
    esc = escala_pof_para_tru()
    esc_ipca = escala_ipca_2018_2021()
    pof_total_2018 = float(comp["despesa_pof_2018_rs_bi"].sum())
    explicito = pof_total_2018 * esc.valor
    sifim = c_fin - explicito
    explicito_ipca = pof_total_2018 * esc_ipca.valor
    sifim_ipca = c_fin - explicito_ipca

    pib = pd.read_csv(config.PROCESSED / "pib_nominal.csv")
    pib_2021 = float(pib.loc[pib["ano"] == 2021, "pib_rs_mi"].iloc[0]) / 1e3

    esc_bienio, _ = _escalas_bienio()
    man = json.loads((config.PROCESSED / "MANIFEST_RUN.json")
                     .read_text(encoding="utf-8"))
    bc_nac = float(man["nums"]["B_C_nacional"]["valor"])

    fonte_tru = ("TRU 2021 nível 68, tab2/demanda, produto 64801 "
                 f"({desc_fin}); tru_2021_usos.parquet")
    fonte_pof = ("pof_despesa_item_uf.parquet × matriz_pof_ibs_v5.csv "
                 "(códigos na fórmula)")

    linhas: list[dict] = []

    def add(componente, valor, unidade, metodo, formula, fonte):
        linhas.append({"componente": componente, "valor_rs_bi_2021": valor,
                       "unidade": unidade, "metodo": metodo,
                       "formula": formula, "fonte": fonte})

    add("consumo_familias_64801_tru2021", c_fin, "R$ bi 2021", "DADO",
        "consumo_familias do produto 64801 ÷ 1e3 (inclui SIFIM alocado: sem "
        "linha explícita de SIFIM/ajuste nas 68_tab1/tab2 — SCN ref. 2010 "
        "aloca o SIFIM aos setores usuários)", fonte_tru)
    for _, r in comp.iterrows():
        add(f"pof_{r['componente']}_2018", r["despesa_pof_2018_rs_bi"],
            "R$ bi de 15/01/2018", "DADO",
            f"Σ despesa_anual_rs dos códigos: {r['codigos_pof']}", fonte_pof)
    add("escala_pof_tru", esc.valor, esc.unidade, "CONVENCAO",
        esc.formula + " — corrige preços 2018→2021 E cobertura média "
        "POF/SCN; correção é média (viés item-específico declarado)",
        esc.fonte)
    add("explicito_escalado_2021", explicito, "R$ bi 2021", "DERIVADO",
        "Σ componentes POF × escala_pof_tru", fonte_pof)
    add("sifim_imputado_familias_2021", sifim, "R$ bi 2021", "CONVENCAO",
        "resíduo (cota): consumo_familias_64801 − explicito_escalado. "
        f"= {sifim / c_fin:.1%} do produto; {sifim / pib_2021:.1%} do PIB "
        "2021 (pib_nominal.csv). Vieses declarados e de sinais opostos: "
        "juros POF = fluxo total (só a margem é consumo no SCN → resíduo "
        "subestimado); prêmios POF brutos > serviço SCN de seguros e "
        "sub-relato financeiro na POF (→ resíduo superestimado). Serviço "
        "imputado NÃO é operação onerosa: fora do campo (LC 214, art. 4º)",
        fonte_tru + " − " + fonte_pof)
    add("sensibilidade_escala_ipca_sifim_2021", sifim_ipca, "R$ bi 2021",
        "DERIVADO",
        f"resíduo com escala só-IPCA ({esc_ipca.valor:.6f} = "
        f"{esc_ipca.formula}) — sem correção de cobertura POF (cota superior)",
        esc_ipca.fonte)

    # ------------- efeitos da exclusão do imputado — ENDÓGENOS da grade
    # (a alavanca sifim='excluido' está no CENTRAL; sens_sifim_incluido
    # reverte — a diferença é o efeito exato, com cashback e redutor
    # endógenos; o espelho de 1ª ordem deixou de ser necessário aqui)
    sifim_bienio = sifim * esc_bienio
    shrink = sifim_bienio / bc_nac
    eff = efeitos_pp_grade("sens_sifim_incluido")
    add("sifim_imputado_bienio", sifim_bienio, "R$ bi biênio (R$ 2024)",
        "DERIVADO", f"sifim_imputado_2021 × escala_bienio ({esc_bienio:.6f}, "
        "MANIFEST_RUN.json)", "SIDRA 1846 via pipeline")
    for s, rot in (("uniao", "CBS"), ("estadual", "estadual"),
                   ("municipal", "municipal")):
        add(f"efeito_pp_{s}", eff[s], "p.p.", "DERIVADO",
            f"Δτ_{rot} = τ_central (SIFIM excluído, alavanca de base.py) − "
            "τ(sens_sifim_incluido) — efeito ENDÓGENO da grade "
            f"(encolhimento da âncora: {shrink:.4%})",
            "aferir_nacional.csv (central × sens_sifim_incluido)")
    add("efeito_pp_soma", sum(eff.values()), "p.p.", "DERIVADO",
        "Σ efeitos nas três esferas", _RE_BASELINE)

    # ---------------- alíquota própria (produto inteiro) e break-even ISS
    # O imputado já está FORA do central: o desvio remanescente do
    # tratamento por alíquota própria (arts. 181-183) é a parcela EXPLÍCITA
    # — espelho de 1ª ordem sobre o central vigente (base_uf.csv excluído).
    d0 = _d_esferas_espelho()
    explicito_bienio = explicito * esc_bienio
    bc_nac_exc = float(man["nums"]["B_C_nacional[sifim=excluido]"]["valor"])
    d2 = _d_esferas_espelho(shrink_bc=explicito_bienio / bc_nac_exc)
    eff_expl = {s: _tau_central()[s] * (d0[s] / d2[s] - 1.0)
                for s in config.ESFERAS}
    eff_full = {s: eff[s] + eff_expl[s] for s in config.ESFERAS}
    be_share = (d0["municipal"] - d2["municipal"]) / d0["municipal"]
    rm = pd.read_csv(config.PROCESSED / "r_municipal_uf.csv")
    iss_medio = float((rm["iss_liquida"] + rm["iss_imputado"]).sum()) / 1e9 \
        / rm["ano"].nunique()
    add("efeito_pp_municipal_produto_inteiro", eff_full["municipal"], "p.p.",
        "DERIVADO",
        "lado-base do tratamento por alíquota própria (arts. 181-183): "
        "exclusão do produto 64801 INTEIRO da âncora B_C = imputado "
        "(efeito endógeno da grade) + parcela explícita (espelho de 1ª "
        "ordem sobre o central vigente, já sem o imputado)", _RE_BASELINE)
    add("break_even_iss_financeiro_share", be_share, "fração do alvo municipal",
        "DERIVADO",
        "ΔD_M/D_M da exclusão da parcela EXPLÍCITA remanescente (o imputado "
        "já está fora do central): se ISS financeiro/ISS total exceder esta "
        "fração, o desvio 'ao padrão' SUPERESTIMA τ_M; abaixo, subestima",
        _RE_BASELINE)
    add("break_even_iss_financeiro_rs_bi_ano", be_share * iss_medio,
        "R$ bi/ano (nominal médio 2024-25)", "DERIVADO",
        "break_even_share × ISS médio da janela (r_municipal_uf.csv; ordem "
        "de grandeza, sem deflação)", "SICONFI DCA via r_municipal_uf.csv")
    add("iss_financeiro_numerador", float("nan"), "R$ bi/ano", "FRONTEIRA",
        "NÃO mensurável com dado aberto: SICONFI/DCA reporta ISSQN como "
        "conta única (1.1.1.4.51.1.0), sem corte por atividade/item LC 116; "
        "inexiste fonte aberta nacional alternativa — fronteira OD/ADM "
        "declarada; quantificação limita-se ao lado da base",
        "SICONFI DCA Anexo I-C (ementário)")

    # -------- validação externa (dados abertos BCB/SGS): FISIM-PF ≥ resíduo
    fisim = fisim_pf_bcb_2021()
    add("fisim_pf_bcb_2021", fisim.valor, fisim.unidade, "VALIDACAO",
        fisim.formula + " — cota SUPERIOR externa do SIFIM-famílias (inclui "
        "habitacional, PF-produtora e cunha IBGE>Selic): deve exceder o "
        "resíduo interno (sifim_imputado_familias_2021), com teto mecânico "
        "na célula TRU 64801 (consumo_familias_64801_tru2021)", fisim.fonte)

    df = pd.DataFrame(linhas)
    for k, n in (("sifim_imputado_familias_2021",
                  Num(sifim, "consumo_familias_64801 − Σ POF explícito × "
                      "escala_pof_tru", fonte_tru, Label.CONVENCAO,
                      "R$ bi 2021")),
                 ("sifim_escala_pof_tru", esc),
                 ("sifim_fisim_pf_bcb_2021", fisim),
                 ("sifim_share_residual",
                  Num(sifim / c_fin, "imputado ÷ produto 64801", fonte_tru,
                      Label.DERIVADO, "fração"))):
        MANIFEST.registra(k, n)
    if grava:
        _grava_csv(df, CSV_SIFIM)
    return df


# ================================================================ E7.2 CSV
def ajuste_fbcf_imobiliaria(grava: bool = True) -> pd.DataFrame:
    """ajuste_fbcf_imobiliaria.csv — parcela residencial nova da FBCF
    não-corporativa e redutores do regime imobiliário da LC 214 (artigo a
    artigo), com efeito de 1ª ordem em p.p."""
    fetch_paic_1740()
    lei = lc214_regime_imobiliario()
    tru = pd.read_parquet(config.PROCESSED / "tru_2021_usos.parquet")
    fbcf_tru = float(tru["fbcf"].sum()) / 1e3                  # R$ bi 2021
    edif = float(tru.loc[tru["produto_cod"].astype(str) == "41801",
                         "fbcf"].iloc[0]) / 1e3
    sh_edif = edif / fbcf_tru

    v1 = pd.read_csv(config.FBCF_V1_CSV)
    share_nc = float(v1["B_FBCF_Rbi"].sum()) / (fbcf_tru * 1.406037)
    fbcf_nc_2021 = fbcf_tru * share_nc

    sh_res = share_residencial_paic()
    parcela_res = fbcf_nc_2021 * sh_edif * sh_res.valor
    m_efetivo = 1.0 - lei["reducao_aliquota_pct"].valor / 100.0
    delta = parcela_res * (1.0 - m_efetivo)

    _, esc_fbcf = _escalas_bienio()
    b = pd.read_csv(config.PROCESSED / "base_uf.csv")
    fbcf_nc_bienio = float(b["B_FBCF_NC"].sum())
    shrink = delta * esc_fbcf / fbcf_nc_bienio
    eff = efeitos_pp_grade("sens_fbcf_sem_redutores")

    fonte_261 = lei["reducao_aliquota_pct"].fonte
    fonte_259 = lei["redutor_social_novo_rs"].fonte

    linhas: list[dict] = []

    def add(componente, parcela, redutor, m_ef, delta_v, efeito, formula, fonte):
        linhas.append({"componente": componente,
                       "parcela_residencial_rs_bi": parcela,
                       "redutor_aplicado": redutor, "m_efetivo": m_ef,
                       "delta_base_rs_bi": delta_v,
                       "efeito_pp_aprox": efeito,
                       "formula": formula, "fonte": fonte})

    add("fbcf_nc_2021", fbcf_nc_2021, "nenhum", 1.0, 0.0, float("nan"),
        f"FBCF_TRU2021 ({fbcf_tru:.3f}) × share_fbcf_nc ({share_nc:.6f} = "
        "Σ B_FBCF_v1 ÷ (FBCF_TRU × 1,406037), convenção v1 VTI/PIA)",
        "TRU 2021 tab2 + data/inputs/fbcf_v1_uf.csv")
    add("parcela_residencial_nova_2021", parcela_res, "nenhum (identificação)",
        1.0, 0.0, float("nan"),
        f"fbcf_nc_2021 × share Edificações na FBCF TRU ({sh_edif:.6f} = "
        f"41801 ÷ FBCF total) × share residencial PAIC ({sh_res.valor:.6f}: "
        f"{sh_res.formula}). Convenções declaradas: composição da FBCF "
        "TOTAL como proxy do mix não-corporativo e PAIC 30+ PO sem "
        "informalidade — ambas COTAS INFERIORES da parcela residencial",
        "TRU 2021 (composição por produto) + " + sh_res.fonte)
    add("reducao_aliquota_art261", parcela_res,
        f"alíquotas reduzidas em {lei['reducao_aliquota_pct'].valor:.0f}% "
        "(operações com bens imóveis, incl. alienação — art. 252, I — e "
        "serviços de construção civil — art. 252, V)",
        m_efetivo, delta, eff["uniao"] + eff["estadual"] + eff["municipal"],
        f"delta = parcela_residencial × (1 − {m_efetivo:.2f}); efeito_pp = "
        "Δτ_U+Δτ_E+Δτ_M de 1ª ordem (linhas efeito_pp_*); ALAVANCA "
        "fbcf_imob='redutores' de base.py aplica ESTE delta", fonte_261)
    for s, rot in (("uniao", "CBS"), ("estadual", "estadual"),
                   ("municipal", "municipal")):
        add(f"efeito_pp_{s}", float("nan"), "art. 261, caput", m_efetivo,
            float("nan"), eff[s],
            f"Δτ_{rot} = τ_central (redutores, alavanca de base.py) − "
            "τ(sens_fbcf_sem_redutores) — efeito ENDÓGENO da grade "
            f"(encolhimento de B_FBCF_NC: {shrink:.4%})",
            "aferir_nacional.csv (central × sens_fbcf_sem_redutores)")
    add("redutor_social_art259_imovel_novo", float("nan"),
        f"dedução de R$ {lei['redutor_social_novo_rs'].valor:,.0f} da base "
        "por imóvel residencial novo (até o limite da base, após o redutor "
        "de ajuste)".replace(",", "."),
        float("nan"), float("nan"), float("nan"),
        "FRONTEIRA: quantificação exige contagem/valor médio de unidades "
        "novas alienadas — inexiste em dado aberto oficial (PAIC não conta "
        "unidades; BCB cobre só imóveis financiados, sem separar novos). "
        "Cota: redução adicional = min(100000/valor_unidade, 1) sobre a "
        "fatia alienada; no limite legal, delta adicional ∈ [0; "
        f"{parcela_res * m_efetivo:.2f}] R$ bi 2021 — sinal DECLARADO: "
        "efeito adicional para CIMA nas alíquotas", fonte_259)
    add("redutor_social_art259_lote", float("nan"),
        f"dedução de R$ {lei['redutor_social_lote_rs'].valor:,.0f} da base "
        "por lote residencial".replace(",", "."),
        float("nan"), float("nan"), float("nan"),
        "mesma fronteira da linha anterior (contagem de lotes)", fonte_259)
    add("redutor_ajuste_arts257_258", float("nan"),
        "redutor de ajuste (valor do terreno/aquisição) deduzido da base de "
        "alienação por contribuinte regular", 1.0, 0.0, 0.0,
        "delta 0 DECLARADO: a FBCF da TRU mede o valor da CONSTRUÇÃO (o "
        "terreno não é produção) — a base usada já aproxima a base legal "
        "líquida do redutor de ajuste; convergência declarada, não calculada",
        "LC 214/2025, arts. 257-258, texto compilado Planalto (lcp214.htm)")
    add("uso_proprio_autoconstrucao", float("nan"),
        "serviços de construção civil com alíquota reduzida em "
        f"{lei['reducao_aliquota_pct'].valor:.0f}% (arts. 252, V, c/c 261); "
        "materiais adquiridos diretamente ao PADRÃO (m=1)",
        float("nan"), float("nan"), float("nan"),
        "viés DECLARADO da alavanca: aplicar m=0,50 a toda a parcela "
        "residencial superestima a redução na fatia autoconstruída "
        "(materiais ao padrão); sem split aberto serviços×materiais da "
        "autoconstrução — fronteira declarada",
        "LC 214/2025, arts. 252, V, e 261, texto compilado Planalto")

    df = pd.DataFrame(linhas)
    MANIFEST.registra("fbcf_imob_parcela_residencial_2021",
                      Num(parcela_res, "FBCF_NC × share_edif_TRU × "
                          "share_res_PAIC", "TRU 2021 + PAIC 1740",
                          Label.DERIVADO, "R$ bi 2021"))
    MANIFEST.registra("fbcf_imob_delta_art261_2021",
                      Num(delta, "parcela_residencial × (1 − m_efetivo)",
                          fonte_261, Label.DERIVADO, "R$ bi 2021"))
    if grava:
        _grava_csv(df, CSV_FBCF)
    return df


# ============================================================ IO + leitura
def _grava_csv(df: pd.DataFrame, path: Path) -> None:
    """Escrita atômica e determinística (tmp + os.replace)."""
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def carrega_ajuste_sifim() -> float:
    """SIFIM imputado às famílias (R$ bi 2021) lido de ajuste_sifim.csv —
    consumido pela alavanca sifim='excluido' de base.base_ordinaria_uf."""
    df = pd.read_csv(CSV_SIFIM)
    v = df.loc[df["componente"] == "sifim_imputado_familias_2021",
               "valor_rs_bi_2021"]
    if len(v) != 1:
        raise ValueError("ajuste_sifim.csv sem linha sifim_imputado_familias_2021")
    return float(v.iloc[0])


def carrega_ajuste_fbcf() -> float:
    """Delta de base do art. 261 (R$ bi 2021) lido de
    ajuste_fbcf_imobiliaria.csv — alavanca fbcf_imob='redutores'."""
    df = pd.read_csv(CSV_FBCF)
    v = df.loc[df["componente"] == "reducao_aliquota_art261",
               "delta_base_rs_bi"]
    if len(v) != 1:
        raise ValueError("ajuste_fbcf_imobiliaria.csv sem linha "
                         "reducao_aliquota_art261")
    return float(v.iloc[0])


if __name__ == "__main__":
    s = split_sifim(grava=True)
    f = ajuste_fbcf_imobiliaria(grava=True)
    print(s[["componente", "valor_rs_bi_2021", "unidade"]].to_string(index=False))
    print()
    print(f[["componente", "parcela_residencial_rs_bi", "m_efetivo",
             "delta_base_rs_bi", "efeito_pp_aprox"]].to_string(index=False))
