"""Cenário sens_is_ampliado — folga da cota inferior do Imposto Seletivo (A4).

O central usa o proxy iso-carga do IS (arrecadação corrente de IPI em fumo,
bebidas e veículos — aferir.revenue.is_estimado_bi), declarado COTA INFERIOR
porque o campo legal do IS é mais amplo. Este módulo QUANTIFICA a folga
mensurável dessa cota com dados abertos, componente a componente do campo
legal, e documenta as lacunas onde a quantificação aberta é impossível.

Campo legal (LC 214/2025, art. 409, § 1º — texto em
data/raw/normas/planalto/lcp214.htm): "consideram-se prejudiciais à saúde ou
ao meio ambiente os bens classificados nos códigos da NCM/SH e o carvão
mineral, e os serviços listados no Anexo XVII, referentes a: I - veículos;
II - embarcações e aeronaves; III - produtos fumígenos; IV - bebidas
alcoólicas; V - bebidas açucaradas; VI - bens minerais; VII - concursos de
prognósticos e fantasy sport." O Anexo XVII delimita "Bens minerais" a
NCM 2601 (minérios de ferro), 2709.00.10 (petróleo bruto), 2711.11.00 (gás
natural liquefeito) e 2711.21.00 (gás natural gasoso); o carvão mineral entra
por menção expressa do próprio § 1º.

Única alíquota que a PRÓPRIA LC fixa (teto): art. 422, § 2º, red. LC 227/2026:
"As alíquotas do Imposto Seletivo respeitarão o percentual máximo de 0,25%
(vinte e cinco centésimos por cento), nas operações com bens minerais
extraídos." Todas as demais alíquotas aguardam lei ordinária (arts. 419, 421
e 422, caput) — logo só o componente extração (ferro, carvão, petróleo, gás)
tem base × alíquota com fundamento citável; o cenário o avalia NO TETO.

Componentes quantificados (média da janela 2024-2025, R$ bi de 2024):
  * minerais (ferro e carvão): base = "Valor Venda (R$)" do Anuário Mineral
    Brasileiro (ANM, dados abertos), tabelas Producao_Bruta + Producao_
    Beneficiada, por substância × ano-base. Proxy declarado do valor de
    referência da extração (art. 414, III, "b" e § 2º); NÃO usa CFEM ÷
    alíquota. Cota inferior da base: autoconsumo e transferências internas
    (verticalização) ficam fora do valor de venda.
  * petróleo e gás natural: produção mensal nacional (ANP) × preço de
    referência do mês (Res. ANP 874/2022 e 875/2022, XLSX por campo
    produtor). CONVENÇÃO declarada: preço = média nacional SIMPLES entre os
    campos do mês — a ponderação por produção de campo é impossível no dado
    aberto baixado (a tabela de preços não traz volumes e o pareamento
    campo→UF não existe no dado); Label.CONVENCAO. Gás: componente é COTA
    SUPERIOR — art. 423 fixa alíquota ZERO para gás destinado a insumo
    industrial e combustível para transporte, parcela não separável aqui.

Lacunas e residuais (documentados no CSV, sem número inventado):
  * bebidas açucaradas: linha I.P.I-BEBIDAS do XLSX RFB é única, sem abertura
    alcoólicas × não alcoólicas (medido na onda anterior); alíquota do IS
    aguarda lei ordinária ⇒ LACUNA.
  * apostas/fantasy sport: base legal = receita própria da entidade (GGR,
    art. 414, V c/c art. 245); EXCLUSÃO JUSTIFICADA em dupla fundamentação:
    (i) a LC 214 não fixa alíquota nem teto do IS para concursos de
    prognósticos (art. 422, caput: lei ordinária futura) — o teto do art.
    422, § 2º, usado nos minerais, alcança SÓ "bens minerais extraídos";
    (ii) a única fonte oficial de GGR agregado identificada (relatório
    SPA/MF do 1º semestre/2025) exigia autenticação gov.br já na diligência
    de coleta (metadata/diligencias_fontes.csv, F13) e nenhuma cópia aberta
    foi arquivada ⇒ LACUNA (piso não calculável sem número inventado).
  * embarcações e aeronaves: alíquotas em lei ordinária (art. 421), sem base
    corrente aberta comparável ⇒ NAO_QUANTIFICADO (permanece no perímetro).
  * LGN e demais substâncias do AMB (água mineral etc.): FORA do campo do IS
    (Anexo XVII não os lista) — registrados para auditoria do perímetro.

Saída: data/processed/sens_is_ampliado.csv (uma linha por componente do campo
legal + totais + efeito de 1ª ordem em τ_CBS nas duas construções, calculado
sobre a grade CORRENTE — re-baseline declarado: outros itens da revisão estão
regenerando os processados; recomputar na integração).
"""
from __future__ import annotations

import functools
import re

import pandas as pd

from aferir import config
from aferir.provenance import MANIFEST, Label, Num

BI = 1e9

# ------------------------------------------------------------------ caminhos
RAW_ANM = config.RAW / "anm"
RAW_ANP_PROD = config.RAW / "anp_producao"
AMB_TABELAS = ("Producao_Bruta.csv", "Producao_Beneficiada.csv")

# ------------------------------------------------------- dispositivos legais
# Transcrições literais de data/raw/normas/planalto/lcp214.htm (grafia do
# Planalto), para que nenhuma alíquota/base entre sem fundamento citável.
ART_409_P1 = (
    'LC 214/2025, art. 409, § 1º: "consideram-se prejudiciais à saúde ou ao '
    "meio ambiente os bens classificados nos códigos da NCM/SH e o carvão "
    "mineral, e os serviços listados no Anexo XVII, referentes a: I - "
    "veículos; II - embarcações e aeronaves; III - produtos fumígenos; IV - "
    "bebidas alcoólicas; V - bebidas açucaradas; VI - bens minerais; VII - "
    'concursos de prognósticos e fantasy sport."')
ART_422_P2 = (
    'LC 214/2025, art. 422, § 2º (red. LC 227/2026): "As alíquotas do '
    "Imposto Seletivo respeitarão o percentual máximo de 0,25% (vinte e "
    "cinco centésimos por cento), nas operações com bens minerais "
    'extraídos."')
ART_414_III_B = (
    "LC 214/2025, art. 414, III, \"b\": base de cálculo é o valor de "
    "referência na extração de bem mineral; § 2º: metodologia do valor de "
    "referência por ato do Executivo, com base em cotações, índices ou "
    "preços vigentes na data do fato gerador; art. 412, V: fato gerador no "
    "momento da extração.")
ART_423 = (
    'LC 214/2025, art. 423: "Caso o gás natural seja destinado à utilização '
    "como insumo em processo industrial e como combustível para fins de "
    "transporte, a alíquota estabelecida na forma do § 2º do art. 422 desta "
    'Lei Complementar deverá ser fixada em zero."')
ANEXO_XVII_MINERAIS = (
    "LC 214/2025, Anexo XVII, \"Bens minerais\": NCM 2601; 2709.00.10; "
    "2711.11.00; 2711.21.00.")

# Teto legal da alíquota do IS sobre bens minerais extraídos — ÚNICA alíquota
# fixada pela própria LC; as demais aguardam lei ordinária (arts. 419/421/422).
ALIQ_IS_MINERAIS_TETO = 0.0025          # 0,25% — art. 422, § 2º (red. LC 227)

# Substâncias do AMB dentro do campo legal (Anexo XVII + art. 409, § 1º).
# Grafias EXATAS da coluna "Substância Mineral" dos CSVs do AMB.
AMB_SUBSTANCIAS_CAMPO = {
    "Ferro": "NCM 2601 — Anexo XVII (minérios de ferro)",
    "Carvão Mineral": "art. 409, § 1º, caput (carvão mineral por menção "
                      "expressa; fora da lista NCM do Anexo XVII)",
}

_MES2NUM = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
            "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

# produto → (csv de produção, escala p/ m³, subdiretório de preços)
_ANP_PRODUTOS = {
    "petroleo": ("producao-petroleo-m3.csv", 1.0, "precos_petroleo"),
    "gas_natural": ("producao-gas-natural-1000m3.csv", 1000.0, "precos_gas"),
}

_FONTE_AMB = (
    "ANM, Anuário Mineral Brasileiro (dados abertos), tabelas Producao_Bruta"
    ".csv e Producao_Beneficiada.csv, https://dadosabertos.anm.gov.br/AMB/ "
    "(cache data/raw/anm/, sha256 nos _meta.json)")
_FONTE_ANP_PROD = (
    "ANP, produção mensal por UF (série 1997-corrente), "
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "arquivos/ppgn-el/ (cache data/raw/anp_producao/)")
_FONTE_ANP_PRECO = (
    "ANP, preços de referência do petróleo (Res. ANP 874/2022) e do gás "
    "natural (Res. ANP 875/2022), XLSX mensais por campo produtor "
    "(cache data/raw/anp_producao/precos_petroleo/ e precos_gas/)")
_FONTE_LC214 = ("LC 214/2025 + LC 227/2026 (textos em data/raw/normas/"
                "planalto/lcp214.htm e lcp227.htm)")
_FONTE_SPA_F13 = (
    "relatório SPA/MF do 1º semestre/2025 (apostas de quota fixa), URL "
    "oficial https://www.gov.br/fazenda/pt-br/composicao/orgaos/"
    "secretaria-de-premios-e-apostas/apresentacoes/"
    "copy_of_apresentacao_spamf_relatoriodo1osemestre_versao1.pdf — o GET "
    "exigia autenticação gov.br na diligência de 2026-07-12 (metadata/"
    "diligencias_fontes.csv, F13); nenhuma cópia aberta foi arquivada")


def _num_br(s: pd.Series) -> pd.Series:
    """Número em convenção brasileira do AMB/ANP: vírgula decimal, sem
    separador de milhar (verificado: nenhuma célula com ponto)."""
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def _deflator_2025() -> float:
    from aferir.inputs.ipca_pib import deflator_para_2024
    return float(deflator_para_2024(2025).valor)


# ------------------------------------------------------------------ minerais
@functools.lru_cache(maxsize=1)
def valor_venda_amb() -> pd.DataFrame:
    """Valor Venda (R$ correntes) por substância do campo × ano da janela.

    Soma as tabelas Producao_Bruta (venda de minério ROM) e Producao_
    Beneficiada (venda do produto beneficiado) do AMB — eventos de venda
    distintos; a dupla contagem possível (ROM vendido a beneficiador terceiro
    que revende) é limitada pelo valor ROM, < 1% do componente ferro.
    """
    frames = []
    for tabela in AMB_TABELAS:
        path = RAW_ANM / tabela
        MANIFEST.registra_arquivo(path)
        df = pd.read_csv(path, encoding="cp1252")
        sel = df[df["Substância Mineral"].isin(AMB_SUBSTANCIAS_CAMPO)
                 & df["Ano base"].isin(config.JANELA_RECEITA)].copy()
        sel["valor_venda_rs"] = _num_br(sel["Valor Venda (R$)"]).fillna(0.0)
        g = (sel.groupby(["Substância Mineral", "Ano base"], as_index=False)
             ["valor_venda_rs"].sum())
        g["tabela"] = tabela
        frames.append(g)
    out = (pd.concat(frames, ignore_index=True)
           .rename(columns={"Substância Mineral": "substancia",
                            "Ano base": "ano"}))
    faltam = [(s, a) for s in AMB_SUBSTANCIAS_CAMPO
              for a in config.JANELA_RECEITA
              if out[(out["substancia"] == s) & (out["ano"] == a)]
              ["valor_venda_rs"].sum() <= 0]
    if faltam:
        raise ValueError(f"AMB sem Valor Venda positivo para {faltam}")
    return out.sort_values(["substancia", "ano", "tabela"]).reset_index(drop=True)


def base_minerais_janela_bi(defl: float) -> dict[str, float]:
    """Base por substância: média da janela deflacionada do Valor Venda
    (bruta + beneficiada), em R$ bi de 2024."""
    vv = valor_venda_amb()
    por_ano = vv.groupby(["substancia", "ano"])["valor_venda_rs"].sum()
    return {s: float((por_ano[(s, 2024)] + por_ano[(s, 2025)] * defl) / 2) / BI
            for s in AMB_SUBSTANCIAS_CAMPO}


# ------------------------------------------------------------ petróleo e gás
@functools.lru_cache(maxsize=None)
def producao_anp_mensal(produto: str) -> pd.DataFrame:
    """Produção nacional mensal (m³) na janela: petróleo ou gás natural.

    Gás publicado em mil m³ (escala ×1000 → m³). Produção TOTAL — parcelas
    reinjetadas/queimadas não são separáveis neste dado (viés para cima,
    coerente com a leitura de cota superior do componente gás)."""
    csv, escala, _ = _ANP_PRODUTOS[produto]
    path = RAW_ANP_PROD / csv
    MANIFEST.registra_arquivo(path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df = df[df["ANO"].isin(config.JANELA_RECEITA)].copy()
    df["mes"] = df["MÊS"].map(_MES2NUM)
    df["volume_m3"] = _num_br(df["PRODUÇÃO"]) * escala
    g = (df.groupby(["ANO", "mes"], as_index=False)["volume_m3"].sum()
         .rename(columns={"ANO": "ano"}))
    if len(g) != 24:
        raise ValueError(f"produção ANP de {produto}: {len(g)} meses ≠ 24")
    return g


@functools.lru_cache(maxsize=None)
def precos_referencia_mensais(produto: str) -> pd.DataFrame:
    """Preço de referência médio do mês (R$/m³): média nacional SIMPLES entre
    os campos produtores do XLSX mensal — CONVENÇÃO declarada (a ponderação
    por produção de campo é impossível no dado aberto: a tabela de preços não
    publica volumes e o pareamento campo→UF não existe no dado)."""
    _, _, subdir = _ANP_PRODUTOS[produto]
    arquivos: dict[tuple[int, int], object] = {}
    for path in sorted((RAW_ANP_PROD / subdir).glob("*.xlsx")):
        m = re.search(r"(\d{4})_.*?(\d{2})\.xlsx$", path.name)
        if m is None:
            raise ValueError(f"nome de XLSX de preço não reconhecido: {path.name}")
        chave = (int(m.group(1)), int(m.group(2)))
        if chave in arquivos:
            raise ValueError(f"preço {produto} {chave}: arquivo duplicado")
        arquivos[chave] = path
    linhas = []
    for ano in config.JANELA_RECEITA:
        for mes in range(1, 13):
            if (ano, mes) not in arquivos:
                raise ValueError(f"preço {produto} {ano}-{mes:02d}: XLSX ausente")
            path = arquivos[(ano, mes)]
            MANIFEST.registra_arquivo(path)
            raw = pd.read_excel(path, header=4)
            cols = [c for c in raw.columns if "Preço de Referência" in str(c)]
            if len(cols) != 1:
                raise ValueError(f"{path.name}: coluna de preço não única")
            p = pd.to_numeric(raw[cols[0]], errors="coerce").dropna()
            if p.empty or (p <= 0).any():
                raise ValueError(f"{path.name}: preços vazios ou não positivos")
            linhas.append({"ano": ano, "mes": mes, "n_campos": int(len(p)),
                           "preco_medio_rs_m3": float(p.mean())})
    return pd.DataFrame(linhas)


def base_petroleo_gas_janela_bi(defl: float) -> dict[str, float]:
    """Base por produto: Σ_mes produção(mês) × preço de referência médio do
    mês, média da janela deflacionada, em R$ bi de 2024."""
    out = {}
    for produto in _ANP_PRODUTOS:
        prod = producao_anp_mensal(produto).set_index(["ano", "mes"])["volume_m3"]
        prc = (precos_referencia_mensais(produto)
               .set_index(["ano", "mes"])["preco_medio_rs_m3"])
        por_ano = {ano: sum(float(prod[(ano, m)]) * float(prc[(ano, m)])
                            for m in range(1, 13))
                   for ano in config.JANELA_RECEITA}
        out[produto] = float((por_ano[2024] + por_ano[2025] * defl) / 2) / BI
    MANIFEST.registra("is_ampliado_preco_medio_convencao", Num(
        1.0, "preço de referência do mês = média nacional SIMPLES entre os "
        "campos do XLSX ANP (ponderação por produção de campo indisponível "
        "no dado aberto; pareamento campo→UF inexiste no dado)",
        _FONTE_ANP_PRECO, Label.CONVENCAO, "adimensional"))
    return out


# ----------------------------------------------------- efeito de 1ª ordem
def _efeitos_tau_cbs_pp(delta_is_bi: float) -> dict[str, float]:
    """Efeito de 1ª ordem de ΔIS sobre τ_CBS nas duas construções, medido na
    grade CORRENTE (re-baseline declarado — processados em regeneração):

    * sistema (aferir_nacional.csv): τ_CBS é linear no alvo ⇒ Δτ = −ΔIS/D_U,
      com D_U implícito EXATO extraído do par central × sens_is_zero
      (mesmos γ/ψ/modo): D_U = IS_proxy / Δτ_observado;
    * âncora legal (aferir_ancoras.csv): τ_s = (R_s − deduções)/B*
      ⇒ Δτ = −ΔIS/B*.
    """
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    central = nac[(nac["cenario_gamma"] == "central") & (nac["psi"] == 0.0)
                  & (nac["modo_redutor"] == "iso_carga")
                  & (nac["is_cenario"] == "proxy_ipi_rfb")
                  & (nac["ancora_federal"] == config.ANCORA_FEDERAL_CENTRAL)]
    zero = nac[nac["is_cenario"] == "zero"]
    if len(central) != 1 or len(zero) != 1:
        raise ValueError("aferir_nacional.csv sem par central × sens_is_zero único")
    from aferir.revenue import is_estimado_bi
    is_proxy = is_estimado_bi(_deflator_2025())
    d_tau = (float(zero["tau_CBS_pp"].iloc[0])
             - float(central["tau_CBS_pp"].iloc[0])) / 100.0
    d_u = is_proxy / d_tau                      # R$ bi — denominador implícito
    anc = pd.read_csv(config.PROCESSED / "aferir_ancoras.csv")
    b_star = float(anc["B_star_bi"].iloc[0])
    return {"D_U_bi": d_u, "B_star_bi": b_star,
            "delta_pp_sistema": -delta_is_bi / d_u * 100.0,
            "delta_pp_ancora": -delta_is_bi / b_star * 100.0,
            "is_proxy_bi": is_proxy}


# ------------------------------------------------------------------- cenário
def sens_is_ampliado() -> pd.DataFrame:
    """Escreve data/processed/sens_is_ampliado.csv e devolve o DataFrame.

    Uma linha por componente do campo legal do IS (art. 409, § 1º — nenhum
    componente desaparece do perímetro), totais e efeito de 1ª ordem em
    τ_CBS. Roda APÓS o pipeline (lê aferir_nacional.csv/aferir_ancoras.csv
    correntes; re-baseline declarado nas linhas de efeito).
    """
    defl = _deflator_2025()
    minerais = base_minerais_janela_bi(defl)
    oleo_gas = base_petroleo_gas_janela_bi(defl)
    periodo = "2024-2025 (média da janela deflacionada, R$ bi 2024)"
    f_teto = (f"{ART_422_P2} Teto legal avaliado como alíquota do cenário; a "
              "alíquota efetiva aguarda lei ordinária (art. 422, caput). "
              f"{ANEXO_XVII_MINERAIS}")

    def comp(nome, desc, base, valor, fundamento, formula, fonte, status,
             aliq=None):
        return {"componente": nome, "base_descricao": desc,
                "base_rs_bi": base, "aliquota": aliq,
                "fundamento_aliquota": fundamento, "valor_rs_bi": valor,
                "periodo": periodo if valor is not None else "",
                "formula": formula, "fonte": fonte, "status": status}

    a = ALIQ_IS_MINERAIS_TETO
    linhas = [
        comp("is_proxy_central",
             "arrecadação corrente de IPI em fumo, bebidas e veículos "
             "(linhas I.P.I-* do XLSX RFB) — proxy iso-carga do central, "
             "cota inferior do IS",
             None, None,   # valor preenchido adiante (revenue.is_estimado_bi)
             "convenção iso-carga (alíquotas do IS aguardam lei ordinária, "
             "arts. 419, 421 e 422 da LC 214); ver revenue.is_estimado_bi",
             "média janela deflacionada de (I.P.I-FUMO + I.P.I-BEBIDAS + "
             "I.P.I-AUTOMÓVEIS)",
             "XLSX RFB 1994-2025; LC 214, art. 409 + Anexo XVII",
             "PROXY_CENTRAL"),
        comp("minerais_ferro",
             "Valor Venda AMB da substância Ferro (bruta + beneficiada) — "
             f"{AMB_SUBSTANCIAS_CAMPO['Ferro']}; proxy do valor de "
             f"referência da extração ({ART_414_III_B}); cota inferior da "
             "base (autoconsumo/transferências internas fora)",
             minerais["Ferro"], minerais["Ferro"] * a, f_teto,
             "valor = [(VV_2024 + VV_2025×0,952229)/2] × 0,25%",
             f"{_FONTE_AMB} | {_FONTE_LC214}", "QUANTIFICADO", a),
        comp("minerais_carvao",
             "Valor Venda AMB da substância Carvão Mineral (bruta + "
             f"beneficiada) — {AMB_SUBSTANCIAS_CAMPO['Carvão Mineral']}; "
             f"proxy do valor de referência da extração ({ART_414_III_B})",
             minerais["Carvão Mineral"], minerais["Carvão Mineral"] * a,
             f"{ART_409_P1} {f_teto}",
             "valor = [(VV_2024 + VV_2025×0,952229)/2] × 0,25%",
             f"{_FONTE_AMB} | {_FONTE_LC214}", "QUANTIFICADO", a),
        comp("petroleo_extracao",
             "produção nacional mensal ANP (m³) × preço de referência médio "
             "do mês (média nacional simples entre campos — CONVENÇÃO; Res. "
             f"ANP 874/2022); proxy do valor de referência ({ART_414_III_B})",
             oleo_gas["petroleo"], oleo_gas["petroleo"] * a, f_teto,
             "valor = [(Σ_mes prod×preço)_2024 + (·)_2025×0,952229]/2 × 0,25%",
             f"{_FONTE_ANP_PROD} | {_FONTE_ANP_PRECO} | {_FONTE_LC214}",
             "QUANTIFICADO", a),
        comp("gas_natural_extracao",
             "produção nacional mensal ANP (mil m³ → m³) × preço de "
             "referência médio do mês (média nacional simples entre campos — "
             "CONVENÇÃO; Res. ANP 875/2022). COTA SUPERIOR do componente: "
             f"{ART_423} — parcela insumo industrial/transporte não separável",
             oleo_gas["gas_natural"], oleo_gas["gas_natural"] * a, f_teto,
             "valor = [(Σ_mes prod×preço)_2024 + (·)_2025×0,952229]/2 × 0,25%",
             f"{_FONTE_ANP_PROD} | {_FONTE_ANP_PRECO} | {_FONTE_LC214}",
             "QUANTIFICADO", a),
        comp("bebidas_acucaradas",
             "NCM 2202.10.00 (Anexo XVII). A linha I.P.I-BEBIDAS do XLSX RFB "
             "é ÚNICA, sem abertura alcoólicas × não alcoólicas (medido "
             "2026-07 na onda A1); a carga corrente de IPI sobre TODAS as "
             "bebidas já integra o proxy central; a folga específica exigiria "
             "alíquota do IS, que aguarda lei ordinária (art. 422, caput e "
             "§ 5º, red. LC 227)",
             None, None,
             "sem alíquota citável: art. 422, caput (lei ordinária futura)",
             "", "XLSX RFB (linha I.P.I-BEBIDAS única); LC 214 Anexo XVII",
             "LACUNA"),
        comp("apostas_prognosticos_fantasy",
             "base legal = receita própria da entidade (GGR: produto da "
             "arrecadação menos premiações pagas e destinações obrigatórias "
             "por lei), LC 214, art. 414, V, c/c art. 245 — não confundir "
             "GGR com volume apostado nem com arrecadação tributária. GGR "
             "agregado de apostas de quota fixa indisponível em rota aberta "
             "sem credencial: a única fonte oficial identificada exigia "
             "login gov.br já na diligência de coleta e nenhuma cópia "
             "aberta foi arquivada",
             None, None,
             "EXCLUSÃO JUSTIFICADA (dupla fundamentação): (i) sem alíquota/"
             "teto legal ancorável — diferentemente dos bens minerais "
             "extraídos, cujo teto de 0,25% o próprio art. 422, § 2º (red. "
             "LC 227) fixa, a LC 214 não fixa alíquota nem teto do IS para "
             "concursos de prognósticos (art. 422, caput: lei ordinária "
             "futura); a destinação regulatória sobre o GGR prevista na "
             "Lei 14.790/2023 é repartição do produto da exploração, não "
             "alíquota do IS, e só seria defensável como proxy de carga "
             "corrente com base GGR aberta; (ii) sem base aberta — fonte "
             "oficial do GGR atrás de login gov.br (diligência F13). Piso "
             "não calculável sem número inventado",
             "", f"LC 214, arts. 245 e 414, V; {_FONTE_SPA_F13}",
             "LACUNA"),
        comp("embarcacoes_aeronaves",
             "NCM 8802 (exceto 8802.60.00) e embarcações com motor da posição "
             "8903 (Anexo XVII); alíquotas em lei ordinária (art. 421); sem "
             "base corrente aberta comparável — parcela residual "
             "explicitamente NÃO quantificada, mantida no perímetro legal",
             None, None,
             "sem alíquota citável: art. 421 (lei ordinária futura)",
             "", f"{_FONTE_LC214}", "NAO_QUANTIFICADO"),
        comp("lgn",
             "líquido de gás natural (produção ANP disponível): NÃO listado "
             "no Anexo XVII (que traz apenas 2711.11.00 — GN liquefeito — e "
             "2711.21.00 — GN gasoso) — excluído do cenário",
             None, None, ANEXO_XVII_MINERAIS, "",
             f"{_FONTE_ANP_PROD} | {_FONTE_LC214}", "FORA_DO_CAMPO"),
        comp("demais_substancias_amb",
             "água mineral e demais substâncias do AMB fora de {Ferro, "
             "Carvão Mineral}: fora do campo do IS (Anexo XVII limita os "
             "bens minerais a 2601, 2709.00.10, 2711.11.00 e 2711.21.00; "
             "carvão entra pelo art. 409, § 1º)",
             None, None, f"{ART_409_P1} {ANEXO_XVII_MINERAIS}", "",
             f"{_FONTE_AMB} | {_FONTE_LC214}", "FORA_DO_CAMPO"),
    ]

    adicional = float(sum(l["valor_rs_bi"] for l in linhas
                          if l["status"] == "QUANTIFICADO"))
    ef = _efeitos_tau_cbs_pp(adicional)
    linhas[0]["valor_rs_bi"] = ef["is_proxy_bi"]
    linhas[0]["periodo"] = periodo
    total = ef["is_proxy_bi"] + adicional

    linhas += [
        comp("total_adicional_quantificado",
             "Σ componentes QUANTIFICADO (ferro + carvão + petróleo + gás) "
             "— folga mensurável da cota inferior no teto do art. 422, § 2º",
             None, adicional, f_teto,
             "Σ valor_rs_bi[status=QUANTIFICADO]",
             "este arquivo (linhas QUANTIFICADO)", "TOTAL"),
        comp("total_is_ampliado",
             "IS ampliado = proxy central + total adicional quantificado",
             None, total,
             "proxy: convenção iso-carga; adicional: teto art. 422, § 2º",
             "is_proxy_central + total_adicional_quantificado",
             "este arquivo", "TOTAL"),
        comp("efeito_tau_cbs_sistema",
             "queda de 1ª ordem de τ_CBS na grade (iso_carga, γ central, "
             f"ψ=0): Δτ_CBS = −ΔIS/D_U = {ef['delta_pp_sistema']:+.6f} p.p. "
             f"(D_U implícito = {ef['D_U_bi']:.3f} R$ bi, extraído do par "
             "central × sens_is_zero da grade CORRENTE — re-baseline "
             "declarado: processados em regeneração na revisão)",
             None, -adicional,
             "aritmética da construção: τ_CBS linear no alvo (art. 353, § 1º)",
             "delta_pp = −total_adicional_quantificado ÷ D_U × 100",
             "aferir_nacional.csv (corrente) + MANIFEST_RUN.json", "EFEITO"),
        comp("efeito_tau_cbs_ancora_legal",
             "queda de 1ª ordem de τ_CBS na construção A (âncoras legais): "
             f"Δτ = −ΔIS/B* = {ef['delta_pp_ancora']:+.6f} p.p. "
             f"(B* = {ef['B_star_bi']:.3f} R$ bi — re-baseline declarado)",
             None, -adicional,
             "aritmética da construção: τ_s = (R_s − deduções)/B*",
             "delta_pp = −total_adicional_quantificado ÷ B* × 100",
             "aferir_ancoras.csv (corrente)", "EFEITO"),
    ]

    df = pd.DataFrame(linhas)
    MANIFEST.registra("is_ampliado_adicional_quantificado", Num(
        adicional, "Σ (base aberta × 0,25%) em ferro, carvão, petróleo e gás "
        "natural — folga mensurável da cota inferior do IS",
        f"{_FONTE_AMB} | {_FONTE_ANP_PROD} | {_FONTE_ANP_PRECO} | teto: "
        "LC 214, art. 422, § 2º (red. LC 227)", Label.DERIVADO, "R$ bi 2024"))
    MANIFEST.registra("is_ampliado_total", Num(
        total, "is_estimado_proxy_ipi + is_ampliado_adicional_quantificado",
        "sens_is_ampliado.csv", Label.DERIVADO, "R$ bi 2024"))
    MANIFEST.registra("is_ampliado_delta_tau_cbs_sistema_pp", Num(
        ef["delta_pp_sistema"], "−ΔIS/D_U×100 (D_U implícito da grade "
        "corrente; re-baseline declarado)",
        "aferir_nacional.csv + sens_is_ampliado.csv", Label.DERIVADO, "p.p."))
    MANIFEST.registra("is_ampliado_delta_tau_cbs_ancora_pp", Num(
        ef["delta_pp_ancora"], "−ΔIS/B*×100 (B* da grade corrente; "
        "re-baseline declarado)",
        "aferir_ancoras.csv + sens_is_ampliado.csv", Label.DERIVADO, "p.p."))
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.PROCESSED / "sens_is_ampliado.csv", index=False)
    return df


if __name__ == "__main__":
    print(sens_is_ampliado().to_string())
