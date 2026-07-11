"""Figuras canônicas do artigo (F1-F4) — PNG 400 dpi, determinísticas.

Executar: PYTHONPATH=src python3 -m aferir.figures
Saídas em data/outputs/figures/ (2880×2160 px = 7,2×5,4 pol × 400 dpi).

Convenções (DESIGN §2.5-2.6, edital PTN e o método de visualização de dados
do projeto — forma → cor → validação → marcas → rótulos → revisão visual):
- rótulos PT-BR, decimal vírgula; SEM título embutido (título e fonte vão na
  legenda do manuscrito, exceto a nota de fonte discreta no rodapé da figura);
- tipografia Helvetica Neue (quatro pesos, ``aferir.style``); paleta
  categórica validada (CVD ΔE ≥ 12; ver ``aferir/style.py`` e o relatório do
  validador nas notas de implementação — cinza-neutro e cores de status são
  exceções documentadas: de-ênfase intencional e rótulo sempre pareado);
- determinismo byte-idêntico: metadados PNG FIXOS (sem timestamp — também
  requisito de anonimato do espelho), sem bbox "tight", sem aleatoriedade;
- todo número exibido é lido dos processados do pipeline — zero número digitado.

F1 fig1_vetores_uf     — vetores indicativos τ_E^UF + τ_M^UF (barras empilhadas)
F2 fig2_origem_destino — share da UF no ISS (origem) × share na base (destino)
F3 fig3_lorenz_iss     — Lorenz do ISS municipal 2024 × Lorenz da população
F4 fig4_comparadores   — dot-plot das estimativas da Tabela 1 vs gatilho 26,5
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as mpe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402  (backend antes do pyplot)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import config, revenue, style  # noqa: E402
from .style import br  # noqa: E402

DPI = style.DPI
FIGSIZE = style.FIGSIZE


def _salva(fig: plt.Figure, nome: str, out_dir: Path | None) -> Path:
    destino = Path(out_dir) if out_dir is not None else config.FIGURES
    return style.savefig(fig, destino / nome)


def _central() -> pd.Series:
    """Linha do cenário central (γ=12,5%, ψ=0, iso-carga) de aferir_nacional."""
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    m = nac[(nac["cenario_gamma"] == "central") & (nac["psi"] == 0.0)
            & (nac["modo_redutor"] == "iso_carga")]
    if len(m) != 1:
        raise ValueError("cenário central ausente ou duplicado em aferir_nacional.csv")
    return m.iloc[0]


def _trava_central() -> pd.Series:
    """Linha trava-conforme (γ=12,5%): Σ = 26,5% exatos (art. 475, §11)."""
    t = pd.read_csv(config.PROCESSED / "trava_conforme.csv")
    m = t[t["cenario_gamma"] == "central"]
    if len(m) != 1:
        raise ValueError("cenário central ausente ou duplicado em trava_conforme.csv")
    return m.iloc[0]


def lorenz(valores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Curva de Lorenz discreta: (x, y) com x = fração acumulada de unidades
    (ordenadas do menor para o maior valor) e y = fração acumulada do total."""
    v = np.sort(np.asarray(valores, dtype=float))
    if v.size == 0 or v.sum() <= 0 or (v < 0).any():
        raise ValueError("Lorenz exige valores não negativos com soma positiva")
    x = np.arange(v.size + 1) / v.size
    y = np.concatenate([[0.0], np.cumsum(v)]) / v.sum()
    return x, y


def gini(valores: np.ndarray) -> float:
    """Gini pela Lorenz discreta: 1 − Σ (y_i + y_{i−1})·(x_i − x_{i−1})."""
    x, y = lorenz(valores)
    return float(1.0 - np.sum((y[1:] + y[:-1]) * np.diff(x)))


# ---------------------------------------------------------------- F1
def fig1_vetores_uf(out_dir: Path | None = None) -> Path:
    """Dois painéis (estadual e municipal): NECESSIDADE indicativa de
    reposição por UF (barras) contra as duas linhas da lei — a referência
    nacional da esfera e o piso de fixação de 2033 (90,5% da referência,
    art. 371 + Anexo XVI). Onde a necessidade fica abaixo do piso, um
    segmento âmbar completa a barra até a alíquota mínima de fixação
    (τ* = max(τ; 0,905·τ_ref), seção 3.1). Linhas nomeadas na margem
    direita (labels fora do campo de dados — zero colisão com barras).
    Escala estadual truncada em 30 p.p. (AM anotado — corte declarado)."""
    vet = pd.read_csv(config.PROCESSED / "aferir_vetor_uf.csv")
    c = _central()
    vet = vet.sort_values("tau_E_uf_pp", ascending=False, kind="mergesort") \
             .reset_index(drop=True)
    x = np.arange(len(vet))
    y_corte = 30.0

    paineis = (
        ("tau_E_uf_pp", style.ESTADUAL, float(c["tau_E_pp"]), "estadual"),
        ("tau_M_uf_pp", style.MUNICIPAL, float(c["tau_M_pp"]), "municipal"),
    )

    with plt.rc_context(style.RC):
        fig, (ax_e, ax_m) = plt.subplots(
            2, 1, figsize=(7.2, 7.4), height_ratios=[1.25, 1.0])
        fig.subplots_adjust(left=0.07, right=0.845, top=0.975, bottom=0.075,
                            hspace=0.32)

        n_vinc: dict[str, int] = {}
        for ax, (col, cor, ref, rotulo) in zip((ax_e, ax_m), paineis):
            piso = 0.905 * ref
            ax.bar(x, vet[col], width=0.70, color=cor, zorder=3)
            # complemento imposto pelo piso: segmento âmbar da necessidade
            # até a alíquota mínima de fixação (só onde o piso vincula)
            vinc = (vet[col] < piso).to_numpy()
            n_vinc[rotulo] = int(vinc.sum())
            # seam branco mais grosso: separa base e complemento por
            # luminância mesmo em reprodução P&B (mitigação de contraste);
            # suprimido quando o complemento é pequeno (< 2% da escala do
            # painel): o edge consumiria o segmento quase inteiro (caso RS,
            # ~0,26 p.p.) e o leitor deixaria de contar a UF como âmbar
            comp = (piso - vet.loc[vinc, col]).to_numpy()
            escala_y = y_corte if col == "tau_E_uf_pp" else 4.6
            lw_seam = np.where(comp < 0.02 * escala_y, 0.0, 1.5)
            ax.bar(x[vinc], comp, bottom=vet.loc[vinc, col], width=0.70,
                   color=style.ALERTA, zorder=5.5, edgecolor=style.SURFACE,
                   linewidth=lw_seam)
            # linhas legais, nomeadas na margem direita (fora do campo)
            ax.axhline(ref, ls=(0, (5, 3)), lw=1.1, color=style.INK2,
                       zorder=5)
            ax.axhline(piso, ls=(0, (1, 1.6)), lw=1.3, color=style.INK,
                       zorder=5)
            eixo_y = ax.get_yaxis_transform()      # x em fração, y em dados
            folga = 0.012 * (y_corte if col == "tau_E_uf_pp" else 4.6)
            ax.text(1.012, ref + folga, f"referência\nnacional = {br(ref)}",
                    transform=eixo_y, ha="left", va="bottom",
                    color=style.INK2, clip_on=False,
                    fontproperties=style.fp("medium", 8.0))
            ax.text(1.012, piso - folga,
                    f"piso 2033 = {br(piso)}\n(90,5% da ref.,\nart. 371)",
                    transform=eixo_y, ha="left", va="top", color=style.INK,
                    clip_on=False, fontproperties=style.fp("medium", 8.0))
            ax.set_xlim(-0.7, len(vet) - 0.3)
            ax.set_xticks(x)
            ax.set_xticklabels(vet["uf"], rotation=0,
                               fontproperties=style.fp("regular", 7.2))
            ax.set_ylabel(f"IBS {rotulo} indicativo (p.p.)",
                          fontproperties=style.fp("regular", 9.5))
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: br(v, 0)))
            style.style_axes(ax, grid="y")

        # painel estadual: corte de escala declarado (AM > 30 p.p.) — marcas
        # de ruptura junto ao corte; o prefixo "AM:" dispensa linha-guia
        acima = vet[vet["tau_E_uf_pp"] > y_corte]
        for _, r in acima.iterrows():
            i = int(vet.index[vet["uf"] == r["uf"]][0])
            for y0 in (28.55, 29.40):          # marca dupla de ruptura na barra
                ax_e.plot([i - 0.5, i + 0.5], [y0 - 0.32, y0 + 0.32],
                          color=style.SURFACE, lw=2.8, zorder=6,
                          solid_capstyle="butt")
            ax_e.text(i + 0.75, y_corte - 0.35,
                      f"{r['uf']}: {br(r['tau_E_uf_pp'], 1)} p.p. "
                      "(escala truncada em 30)",
                      ha="left", va="top", zorder=7,
                      fontproperties=style.fp("bold", 8.6), color=style.INK)
        ax_e.set_ylim(0, y_corte)
        ax_m.set_ylim(0, 4.6)
        ax_m.set_yticks([0, 1, 2, 3, 4])

        # extremos anotados; quando o piso cobre a barra com o segmento
        # âmbar, o rótulo entra em branco DENTRO do segmento da necessidade
        for ax, col, ref_p, pares in (
                (ax_e, "tau_E_uf_pp", paineis[0][2], ("DF",)),
                (ax_m, "tau_M_uf_pp", paineis[1][2], ("SP", "AP"))):
            for uf in pares:
                i = int(vet.index[vet["uf"] == uf][0])
                v = float(vet.loc[i, col])
                dentro = v < 0.905 * ref_p
                ax.annotate(br(v, 1), (i, v),
                            xytext=(0, -4) if dentro else (0, 3),
                            textcoords="offset points", ha="center",
                            va="top" if dentro else "bottom", zorder=7,
                            color=style.SURFACE if dentro else style.INK,
                            fontproperties=style.fp("bold", 7.0))

        # contagens de vinculação — texto direto em área livre de dados
        ax_e.text(0.985, 0.70,
                  f"piso vinculante em {n_vinc['estadual']} de 27 UFs",
                  transform=ax_e.transAxes, ha="right", va="top",
                  color=style.INK, fontproperties=style.fp("bold", 8.6))
        ax_m.text(0.02, 0.965,
                  f"piso vinculante em {n_vinc['municipal']} de 27 agregados",
                  transform=ax_m.transAxes, ha="left", va="top",
                  color=style.INK, fontproperties=style.fp("bold", 8.6))

        legenda = [
            plt.Rectangle((0, 0), 1, 1, fc=style.ALERTA,
                          label="complemento imposto pelo piso (até a "
                                "alíquota mínima de fixação)"),
            plt.Line2D([], [], ls=(0, (1, 1.6)), lw=1.3, color=style.INK,
                       label="piso de fixação em 2033 (art. 371)"),
            plt.Line2D([], [], ls=(0, (5, 3)), lw=1.1, color=style.INK2,
                       label="referência nacional da esfera"),
        ]
        leg = ax_e.legend(handles=legenda, loc="upper right",
                          bbox_to_anchor=(1.0, 0.92), frameon=True,
                          facecolor=style.SURFACE, edgecolor="none",
                          framealpha=1.0, prop=style.fp("regular", 8.2),
                          labelcolor=style.INK2)
        leg.set_zorder(7)
        style.source_note(fig, "Fonte: elaboração própria a partir de SICONFI/"
                          "DCA, RREO, POF 2017-2018 e TRU 2021; piso: LC "
                          "214/2025, art. 371 e Anexo XVI (AFERIR).")
        return _salva(fig, "fig1_vetores_uf.png", out_dir)


# ---------------------------------------------------------------- F2
def fig2_origem_destino(out_dir: Path | None = None) -> Path:
    """Dispersão origem×destino: share da UF no ISS nacional (média da janela,
    convenção do numerador — origem, LC 116 art. 3º) × share na base de destino
    B^ord. Acima da reta de 45°: ganhador líquido bruto da municipalização
    (antes das retenções 109/110 e da cota-parte do art. 128 da LC 227/2026). Escala log-log
    (declarada) para tornar legíveis as UFs pequenas; bolha ∝ população."""
    defl = revenue.deflator_2025()
    r_m = revenue.alvo_municipal_uf(defl)                    # R$ bi, média janela
    share_iss = 100.0 * r_m / r_m.sum()
    b = pd.read_csv(config.PROCESSED / "base_uf.csv").set_index("uf")
    share_base = 100.0 * b["B_ord"] / b["B_ord"].sum()
    pop = pd.read_parquet(config.PROCESSED / "iss_municipio_2024.parquet") \
        .groupby("uf")["populacao"].sum()

    df = pd.DataFrame({"iss": share_iss, "base": share_base,
                       "pop": pop.astype(float)}).sort_index()
    if df.isna().any().any() or len(df) != len(config.UFS):
        raise ValueError("F2: UFs incompletas em ISS/base/população")

    # regra determinística de rotulagem (declarada): desvio relativo
    # |ln(iss/base)| ≥ 0,30 OU desvio absoluto ≥ 1 p.p. OU DF (único ente que
    # acumula as duas alíquotas — art. 349, II, 'c': leitura federativa própria)
    desvio_rel = np.abs(np.log(df["iss"] / df["base"]))
    desvio_abs = (df["iss"] - df["base"]).abs()
    rotular = (desvio_rel >= 0.30) | (desvio_abs >= 1.0) | (df.index == "DF")

    with plt.rc_context(style.RC):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        fig.subplots_adjust(left=0.088, right=0.975, top=0.965, bottom=0.11)

        lim = (0.09, 60.0)
        ax.plot(lim, lim, ls=(0, (5, 3)), lw=1.1, color=style.BASELINE, zorder=2)
        ax.text(0.098, 0.104, "reta de 45°", fontproperties=style.fp("regular", 8),
                color=style.MUTED, rotation=45, ha="left", va="bottom",
                transform_rotates_text=True, rotation_mode="anchor")

        # bolhas desenhadas da maior para a menor (pequenas por cima); cor
        # pré-mesclada com branco em vez de alpha — gridlines e a reta de
        # 45° deixam de vazar através do preenchimento
        tam = 14.0 + 720.0 * df["pop"] / df["pop"].max()     # pontos² ∝ população
        ordem = np.argsort(-tam.to_numpy(), kind="stable")
        cor_bolha = _mistura(style.ESTADUAL, "#ffffff", 0.24)
        ax.scatter(df["iss"].to_numpy()[ordem], df["base"].to_numpy()[ordem],
                   s=tam.to_numpy()[ordem], color=cor_bolha, alpha=1.0,
                   edgecolor=style.SURFACE, linewidth=1.3, zorder=3)

        # deslocamentos manuais (determinísticos) p/ evitar sobreposição de
        # siglas; pares apertados (GO/PE) e o cluster AP/AC recebem
        # linha-guia curta que PARA na borda da bolha (shrinkB ≈ raio)
        ajuste = {"AC": (10, -13, "left", "top"),
                  "AP": (-12, 9, "right", "bottom"),
                  "PI": (7, -2, "left", "center"),
                  "PE": (18, -14, "left", "top"),
                  "GO": (-24, 18, "right", "bottom"),
                  "DF": (9, -9, "left", "top"),
                  "SP": (-22, 14, "right", "bottom")}
        com_guia = {"GO": 8, "PE": 8, "DF": 4, "AC": 3, "AP": 3}  # shrinkB em pontos
        for uf, r in df[rotular].iterrows():
            ganhador = r["base"] > r["iss"]                  # acima da reta
            dx, dy, ha, va = ajuste.get(
                uf, (-4, 4, "right", "bottom") if ganhador
                else (5, -5, "left", "top"))
            guia = (dict(arrowstyle="-", lw=0.7, color=style.MUTED,
                         shrinkA=1, shrinkB=com_guia[uf])
                    if uf in com_guia else None)
            ax.annotate(uf, xy=(r["iss"], r["base"]), zorder=4,
                        fontproperties=style.fp("medium", 8.2), color=style.INK,
                        xytext=(dx, dy), textcoords="offset points", ha=ha,
                        va=va, arrowprops=guia)

        ax.text(0.03, 0.965,
                "acima da reta: participação no destino > participação na\n"
                "origem, isto é, ganhador líquido bruto da municipalização\n"
                "(antes das retenções arts. 109-110 e da cota-parte\nmunicipal: CF, art. 158, IV, \u2018b\u2019; LC 227/2026, art. 128)",
                transform=ax.transAxes, va="top", color=style.INK2,
                fontproperties=style.fp("regular", 8.2))
        ax.text(0.97, 0.045, "área da bolha proporcional à população (2024)",
                transform=ax.transAxes, ha="right", color=style.MUTED,
                fontproperties=style.fp("regular", 7.6))

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ticks = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50]
        for eixo in (ax.xaxis, ax.yaxis):
            eixo.set_major_locator(plt.FixedLocator(ticks))
            eixo.set_major_formatter(
                plt.FuncFormatter(lambda v, _: br(v, 1 if v < 1 else 0)))
            eixo.set_minor_locator(plt.NullLocator())
        ax.set_xlabel("participação da UF no ISS nacional, na origem "
                      "(%, escala log)", fontproperties=style.fp("regular", 9.5))
        ax.set_ylabel("participação da UF na base de destino (%, escala log)",
                      fontproperties=style.fp("regular", 9.5))
        style.style_axes(ax, grid="both")
        style.source_note(fig, "Fonte: elaboração própria a partir de SICONFI/"
                          "DCA, POF 2017-2018 e TRU 2021 (AFERIR).")
        return _salva(fig, "fig2_origem_destino.png", out_dir)


# ---------------------------------------------------------------- F3
def fig3_lorenz_iss(out_dir: Path | None = None) -> Path:
    """Lorenz do ISS municipal 2024 (universo de 5.569 municípios, ex-DF;
    omissos da DCA computados a zero — convenção declarada) contra a Lorenz da
    população municipal (contrafactual aproximado da distribuição de destino).

    Paleta: a série de contraste usa a aqua validada (slot 2), que fica
    abaixo de 3:1 de contraste no papel claro por desenho da paleta — a
    mitigação (regra de alívio do método) é o rótulo textual direto na
    legenda, presente aqui."""
    p = pd.read_parquet(config.PROCESSED / "iss_municipio_2024.parquet")
    p = p[p["cod_ibge"] != config.COD_IBGE_BRASILIA]         # nota DF
    n = len(p)
    iss = p["iss_liquida"].fillna(0.0).to_numpy()
    x_iss, y_iss = lorenz(iss)
    x_pop, y_pop = lorenz(p["populacao"].to_numpy())
    g = gini(iss)

    v = np.sort(iss)
    tops = {k: float(v[-k:].sum() / v.sum()) for k in (1, 10, 100)}

    with plt.rc_context(style.RC):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        fig.subplots_adjust(left=0.09, right=0.975, top=0.965, bottom=0.11)

        l_ig, = ax.plot([0, 1], [0, 1], ls=(0, (5, 3)), lw=1.1,
                        color=style.BASELINE, zorder=2,
                        label="igualdade perfeita")
        # série primária (ISS) POR CIMA no trecho final coincidente; cap
        # reto para a ponta não vazar acima de y = 1
        l_pop, = ax.plot(x_pop, y_pop, ls=(0, (1, 1.4)), lw=2.0,
                         color=style.POPULACAO, zorder=3,
                         label="população municipal\n"
                               "(contrafactual de destino aproximado)")
        l_iss, = ax.plot(x_iss, y_iss, lw=2.2, color=style.ESTADUAL, zorder=5,
                         solid_capstyle="butt", label="ISS municipal 2024")

        # anotações top-k ancoradas com marcador no ponto exato da curva do
        # ISS; posições fora da trajetória da diagonal (caixa mínima)
        anot = {1: (0.90, 0.66), 10: (0.82, 0.50), 100: (0.72, 0.33)}
        for k, xy_texto in anot.items():
            ponto = ((n - k) / n, 1.0 - tops[k])
            ax.plot(*ponto, "o", ms=4.5, color=style.ESTADUAL, zorder=6,
                    markeredgecolor=style.SURFACE, markeredgewidth=0.8)
            ax.annotate(f"top-{k}: {br(100 * tops[k], 1)}% do ISS",
                        xy=ponto, xytext=xy_texto, ha="right", va="center",
                        zorder=6, fontproperties=style.fp("bold", 8.6),
                        color=style.INK,
                        bbox=dict(boxstyle="square,pad=0.10", fc=style.SURFACE,
                                  ec="none"),
                        arrowprops=dict(arrowstyle="-", lw=0.7,
                                        color=style.BASELINE, shrinkB=3))

        ax.text(0.035, 0.97, f"Gini (ISS) = {br(g, 3)}",
                transform=ax.transAxes, va="top", color=style.INK,
                fontproperties=style.fp("bold", 11))
        ax.text(0.035, 0.895,
                f"universo: {br(n, 0)} municípios, sem Brasília\n"
                "(ISS do DF apurado no RREO-DF; a referência do DF\n"
                "soma as duas esferas, art. 349, II, 'c');\n"
                "omissos da DCA computados a zero",
                transform=ax.transAxes, va="top", color=style.INK2,
                fontproperties=style.fp("regular", 8.0))

        # folga mínima nos limites: as curvas em x=1 e y=0 renderizam com
        # espessura plena (sem clipping de meia-linha nas bordas)
        ax.set_xlim(0, 1.004)
        ax.set_ylim(-0.004, 1.004)
        ax.set_xticks(np.arange(0, 1.01, 0.2))
        ax.set_yticks(np.arange(0, 1.01, 0.2))
        fmt = plt.FuncFormatter(lambda v_, _: br(v_, 1))
        ax.xaxis.set_major_formatter(fmt)
        ax.yaxis.set_major_formatter(fmt)
        ax.set_xlabel("fração acumulada de municípios (do menor para o maior)",
                      fontproperties=style.fp("regular", 9.5))
        ax.set_ylabel("fração acumulada do ISS / da população",
                      fontproperties=style.fp("regular", 9.5))
        style.style_axes(ax, grid="both")
        leg = ax.legend(handles=[l_iss, l_pop, l_ig], loc="upper left",
                        bbox_to_anchor=(0.02, 0.70), frameon=True,
                        facecolor=style.SURFACE, edgecolor="none",
                        framealpha=1.0, prop=style.fp("regular", 8.2),
                        labelcolor=style.INK2)
        style.source_note(fig, "Fonte: elaboração própria a partir de SICONFI/"
                          "DCA municipal 2024 (AFERIR).")
        return _salva(fig, "fig3_lorenz_iss.png", out_dir)


# ---------------------------------------------------------------- F4
def fig4_comparadores(out_dir: Path | None = None) -> Path:
    """Dot-plot horizontal das estimativas da Tabela 1 (total em p.p.),
    ordenadas; segmento = corredor quando a fonte o publica (extraído do
    campo `conceito_nota` de t1_manchete.csv); linha vertical = gatilho de
    revisão de 26,5% (LC 214, art. 475, §11 — gatilho de PLP, não teto).
    O ponto trava-conforme (mesma cor do gatilho) assenta exatamente sobre a
    linha: é a alíquota resultante de aplicar o mecanismo do §11."""
    t1 = pd.read_csv(config.OUTPUTS / "t1_manchete.csv")
    t1 = t1.sort_values("total_pp", ascending=True, kind="mergesort") \
           .reset_index(drop=True)

    def categoria(fonte: str) -> str:
        if fonte.startswith("AFERIR, construção B"):
            return "aferir_b"
        if fonte.startswith("AFERIR, trava-conforme"):
            return "trava"
        if fonte.startswith("AFERIR"):
            return "aferir_a"
        return "literatura"

    ROTULOS_AFERIR = {
        "AFERIR, construção B: identidade sobre dados abertos "
        "(cota superior), cenário central":
            "AFERIR: construção B, central (este artigo)",
        "AFERIR, trava-conforme: construção B com o PLP redutor "
        "do art. 475, §11":
            "AFERIR: trava-conforme (art. 475, §11)",
        "AFERIR, construção A, rito (âncora legal do art. 353)":
            "AFERIR: construção A, rito\n(âncora legal do art. 353)",
        "AFERIR, construção A, comparável às oficiais (meta do PLDO)":
            "AFERIR: construção A, comparável\nàs oficiais (meta do PLDO)",
    }
    faltam = [f for f in t1["fonte"]
              if f.startswith("AFERIR") and f not in ROTULOS_AFERIR]
    if faltam:                       # deriva de rótulo falha ruidosamente
        raise ValueError(f"F4: linha AFERIR sem rótulo curto: {faltam}")
    CORES = {"aferir_b": style.AFERIR_B, "aferir_a": style.CONSTRUCAO_A,
             "trava": style.CRITICO, "literatura": style.LITERATURA}
    MARCADORES = {"aferir_b": "o", "aferir_a": "o", "trava": "D",
                  "literatura": "o"}
    corredor_re = r"corredor[^\[]*\[\s*([\d]+[.,]?\d*)\s*;\s*([\d]+[.,]?\d*)\s*\]"

    gatilho = 100.0 * config.TRAVA_SOMA_REFERENCIAS

    with plt.rc_context(style.RC):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        fig.subplots_adjust(left=0.375, right=0.965, top=0.965, bottom=0.105)

        ax.axvline(gatilho, ls=(0, (5, 3)), lw=1.2, color=style.CRITICO, zorder=2)
        ax.text(gatilho, len(t1) - 0.35,
                f"gatilho de revisão: {br(gatilho, 1)} p.p.\n(art. 475, §11)",
                fontproperties=style.fp("medium", 8.2), color=style.CRITICO,
                ha="center", va="top",
                bbox=dict(boxstyle="round,pad=0.3", fc=style.SURFACE, ec="none"))

        for i, r in t1.iterrows():
            cat = categoria(r["fonte"])
            cor = CORES[cat]
            faixa = pd.Series(r["conceito_nota"]).str.extract(corredor_re)
            if faixa.notna().all(axis=None):
                lo, hi = (float(str(s).replace(",", ".")) for s in faixa.iloc[0])
                ax.hlines(i, lo, hi, color=cor, lw=3.6, alpha=0.42, zorder=3,
                          capstyle="round")
                for ponta in (lo, hi):
                    ax.vlines(ponta, i - 0.17, i + 0.17, color=cor, lw=1.3,
                              alpha=0.85, zorder=3)
            ax.plot(r["total_pp"], i, MARCADORES[cat], ms=8.5, color=cor,
                    zorder=5, markeredgecolor=style.SURFACE,
                    markeredgewidth=1.5)
            # caixa branca: abre janela sobre a linha do gatilho nos rótulos
            # próximos de 26,5 (26,47/26,50/26,63)
            ax.annotate(br(float(r["total_pp"]), 2), (r["total_pp"], i),
                        xytext=(0, 7), textcoords="offset points",
                        ha="center", zorder=6, color=style.INK,
                        fontproperties=style.fp("bold" if cat != "literatura"
                                                else "medium", 8.2),
                        bbox=dict(boxstyle="square,pad=0.10", fc=style.SURFACE,
                                  ec="none"))

        rotulos = [ROTULOS_AFERIR.get(f, f) for f in t1["fonte"]]
        ax.set_yticks(range(len(t1)))
        ax.set_yticklabels(rotulos, fontproperties=style.fp("regular", 8.4))
        ax.set_ylim(-0.6, len(t1) - 0.4)
        ax.set_xlim(23.5, 34.5)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: br(v, 0)))
        ax.set_xlabel("soma das alíquotas de referência (p.p.)",
                      fontproperties=style.fp("regular", 9.5))
        style.style_axes(ax, grid="x")

        legenda = [
            plt.Line2D([], [], marker="o", ls="", color=style.AFERIR_B, ms=8,
                       label="AFERIR: construção B (cota superior)"),
            plt.Line2D([], [], marker="o", ls="", color=style.CONSTRUCAO_A, ms=8,
                       label="AFERIR: construção A (âncoras oficiais)"),
            plt.Line2D([], [], marker="D", ls="", color=style.CRITICO, ms=7.5,
                       label="AFERIR: trava-conforme (Σ = 26,5 p.p.)"),
            plt.Line2D([], [], marker="o", ls="", color=style.LITERATURA, ms=8,
                       label="literatura e notas oficiais"),
            plt.Line2D([], [], ls="-", lw=3.6, alpha=0.42, color=style.INK2,
                       label="corredor declarado (na cor da estimativa)"),
        ]
        leg = ax.legend(handles=legenda, loc="lower right", frameon=True,
                        facecolor=style.SURFACE, edgecolor="none",
                        framealpha=1.0, prop=style.fp("regular", 8.2),
                        labelcolor=style.INK2)
        leg.set_zorder(7)
        style.source_note(fig, "Fonte: elaboração própria a partir de SICONFI, "
                          "RREO, POF 2017-2018, TRU 2021, RFB e ANP/CONFAZ; "
                          "comparadores: Tabela C.1 (AFERIR).")
        return _salva(fig, "fig4_comparadores.png", out_dir)


# ---------------------------------------------------------------- F5
def fig5_cenarios(out_dir: Path | None = None) -> Path:
    """Painel de cenários: barras horizontais empilhadas (CBS + IBS estadual
    + IBS municipal) para cada linha da grade de sensibilidades — corredor de
    conformidade γ, split payment ψ, modo do redutor de compras públicas,
    alvo federal — e a linha trava-conforme (art. 475, §11). A linha vertical
    marca o gatilho de 26,5%; o bigode sobre o cenário central é o intervalo
    bootstrap de 90% da POF (Rao-Wu). Todo número vem dos processados."""
    nac = pd.read_csv(config.PROCESSED / "aferir_nacional.csv")
    tv = _trava_central()
    banda = pd.read_csv(config.PROCESSED / "banda_incerteza.csv")
    soma_band = banda[banda["componente"] == "soma_pp"].iloc[0]

    def linha(cen: str, psi: float, modo: str) -> pd.Series:
        m = nac[(nac["cenario_gamma"] == cen) & (nac["psi"] == psi)
                & (nac["modo_redutor"] == modo)]
        if len(m) != 1:
            raise ValueError(f"F5: cenário ({cen}, ψ={psi}, {modo}) "
                             f"casa {len(m)} linhas")
        return m.iloc[0]

    # ("header", txt) | ("row", rótulo, série, extra) — os cabeçalhos vivem
    # na CALHA esquerda (fora do campo de dados), acima do seu grupo
    itens: list[tuple] = []
    itens.append(("header", "Hiato de conformidade γ"))
    itens.append(("row", "γ = 0 (hiato nulo, diagnóstico)",
                  linha("hiato_zero", 0.0, "iso_carga"), None))
    itens.append(("row", "γ = 10% (factível)", linha("factivel", 0.0, "iso_carga"), None))
    itens.append(("row", "γ = 12,5% (central)", linha("central", 0.0, "iso_carga"), "banda"))
    itens.append(("row", "γ = 15% (conservador)", linha("conservador", 0.0, "iso_carga"), None))
    itens.append(("row", "γ = 20% (estresse, além do corredor)",
                  linha("estresse", 0.0, "iso_carga"), None))
    itens.append(("header", "Split payment ψ (γ central)"))
    itens.append(("row", "ψ = 0 (sem split; = central)", linha("central", 0.0, "iso_carga"), None))
    itens.append(("row", "ψ = 0,3 (adoção parcial)", linha("central", 0.3, "iso_carga"), None))
    itens.append(("row", "ψ = 1 (pleno; coincide com γ = 0)", linha("central", 1.0, "iso_carga"), None))
    itens.append(("header", "Redutor de compras públicas (art. 370)"))
    itens.append(("row", "sem redutor (r = 0; σ = Στ)", linha("central", 0.0, "sem_redutor"), None))
    itens.append(("row", "redutor integral (r = 1; σ = 0)", linha("central", 0.0, "redutor_total"), None))
    itens.append(("header", "Alvo federal (art. 353)"))
    itens.append(("row", "IS = 0 (sem dedução do Seletivo)", linha("sens_is_zero", 0.0, "iso_carga"), None))
    itens.append(("row", "âncora federal bruta-RFB", linha("sens_ancora_bruta", 0.0, "iso_carga"), None))
    itens.append(("row", "IS ampliado (minerais, petróleo e gás)",
                  linha("sens_is_ampliado", 0.0, "iso_carga"), None))
    itens.append(("header", "Cunha do Simples (denominador)"))
    itens.append(("row", "consumo dos optantes fora da base (ω)",
                  linha("com_cunha_simples", 0.0, "iso_carga"), None))
    itens.append(("header", "Mecanismo corretivo (art. 475, §11)"))
    itens.append(("row", f"trava-conforme (λ = {br(float(tv['lambda']), 2)})",
                  tv, "trava"))

    gatilho = 100.0 * config.TRAVA_SOMA_REFERENCIAS
    CORES = ((style.CONSTRUCAO_A, "tau_CBS_pp"), (style.ESTADUAL, "tau_E_pp"),
             (style.MUNICIPAL, "tau_M_pp"))
    ALTURA_HEADER, ALTURA_ROW = 1.30, 1.0

    with plt.rc_context(style.RC):
        fig, ax = plt.subplots(figsize=(7.2, 7.5))
        fig.subplots_adjust(left=0.308, right=0.955, top=0.940, bottom=0.110)

        total_altura = sum(ALTURA_HEADER if t[0] == "header" else ALTURA_ROW
                           for t in itens)
        eixo_y = ax.get_yaxis_transform()          # x em fração do eixo
        y = total_altura
        yticks, yticklabels = [], []
        for tipo, *resto in itens:
            if tipo == "header":
                y -= ALTURA_HEADER
                # calha esquerda: título de grupo alinhado ao início dos
                # rótulos, em negrito; fundo branco impede a spine/grade de
                # riscar os títulos que invadem a área de plotagem
                ax.text(-0.415, y + 0.10, resto[0], transform=eixo_y,
                        ha="left", va="bottom", clip_on=False, zorder=6,
                        fontproperties=style.fp("bold", 8.6), color=style.INK,
                        bbox=dict(boxstyle="square,pad=0.12", fc=style.SURFACE,
                                  ec="none"))
                continue
            y -= ALTURA_ROW
            rotulo, r, extra = resto
            if extra == "banda":     # destaque do cenário central: cobre o
                # slot inteiro, do rótulo na calha à borda direita (padrão
                # OWID de linha destacada)
                ax.add_patch(plt.Rectangle(
                    (-0.42, y - 0.5), 1.42, 1.0, transform=eixo_y,
                    facecolor=style.GRID, alpha=0.38, edgecolor="none",
                    clip_on=False, zorder=0.8))
            esq = 0.0
            for cor, colname in CORES:
                v = float(r[colname])
                ax.barh(y, v, left=esq, height=0.56, color=cor, zorder=3,
                        edgecolor=style.SURFACE, linewidth=0.8)
                esq += v
            cor_total = style.CRITICO if extra == "trava" else style.INK
            # IC-90% bootstrap (Rao-Wu) mais estreito que a resolução visual
            # da impressão: reportado NUMERICAMENTE sob o total da linha
            # central, em vez de um bigode ilegível
            if extra == "banda":
                lo, hi = float(soma_band["p5"]), float(soma_band["p95"])
                ax.annotate(br(esq, 2), (esq, y), xytext=(7, 5),
                            textcoords="offset points", va="bottom", zorder=6,
                            fontproperties=style.fp("bold", 8.6),
                            color=cor_total)
                ax.annotate(f"[{br(lo, 1)}; {br(hi, 1)}]", (esq, y),
                            xytext=(7, -4), textcoords="offset points",
                            va="top", zorder=6, color=style.INK2,
                            fontproperties=style.fp("regular", 7.2))
            else:
                ax.annotate(br(esq, 2), (esq, y), xytext=(7, 0),
                            textcoords="offset points", va="center", zorder=6,
                            fontproperties=style.fp("bold", 8.6),
                            color=cor_total)
            yticks.append(y)
            yticklabels.append(rotulo)

        ax.axvline(gatilho, ls=(0, (5, 3)), lw=1.2, color=style.CRITICO,
                   zorder=4)
        ax.text(gatilho, total_altura + 0.15,
                f"gatilho de revisão: {br(gatilho, 1)} (art. 475, §11)",
                fontproperties=style.fp("medium", 8.4), color=style.CRITICO,
                ha="center", va="bottom", zorder=6, clip_on=False)

        ax.set_yticks(yticks)
        ax.set_yticklabels(yticklabels, fontproperties=style.fp("regular", 8.4))
        for rot_tick in ax.get_yticklabels():    # linha de referência: rótulo
            if "(central)" in rot_tick.get_text():        # mais forte, não
                rot_tick.set_fontproperties(style.fp("bold", 8.4))
                rot_tick.set_color(style.INK)             # o mais apagado
        ax.set_ylim(-0.75, total_altura)
        # 37,5: acomoda a maior barra da grade (ω ≈ 36,1) + rótulo; com o
        # antigo 35,0 as barras de estresse e ω eram clipadas e suas
        # anotações (xy fora dos eixos) nem eram desenhadas
        ax.set_xlim(0, 37.5)
        ax.set_xticks([0, 5, 10, 15, 20, 25, 30])
        ax.spines["bottom"].set_bounds(0, 30)      # spine só no domínio marcado
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: br(v, 0)))
        ax.set_xlabel("alíquotas de referência (p.p.)",
                      fontproperties=style.fp("regular", 9.5))
        style.style_axes(ax, grid="x")

        legenda = [
            plt.Rectangle((0, 0), 1, 1, fc=style.CONSTRUCAO_A, label="CBS"),
            plt.Rectangle((0, 0), 1, 1, fc=style.ESTADUAL,
                          label="IBS estadual"),
            plt.Rectangle((0, 0), 1, 1, fc=style.MUNICIPAL,
                          label="IBS municipal"),
        ]
        fig.legend(handles=legenda, loc="upper left",
                   bbox_to_anchor=(0.030, 0.995), ncols=3,
                   prop=style.fp("regular", 8.4), labelcolor=style.INK2,
                   frameon=False, columnspacing=1.6, handlelength=1.4)
        style.source_note(fig, "Fonte: elaboração própria a partir de "
                          "SICONFI, RREO, POF 2017-2018, TRU 2021, RFB e "
                          "ANP/CONFAZ (AFERIR).")
        return _salva(fig, "fig5_cenarios.png", out_dir)


# ---------------------------------------------------------------- F6
def fig6_transicao(out_dir: Path | None = None) -> Path:
    """Transição federativa em dois painéis. Painel A: a trajetória LEGAL da
    distribuição do produto do IBS (ADCT, arts. 131-132; LC 227/2026,
    arts. 109 e 114-117): retenção por coeficientes de receita média
    histórica de 80% (2029-2032) e 90% (2033), decrescente à razão de 1/45
    ao ano de 2034 a 2077, com destino pleno em 2078; anotam-se o
    seguro-receita, a cota-parte e a convivência com o ICMS/ISS em
    extinção (ADCT, art. 128). Painel B: os mecanismos
    em 2033, por UF — componentes do recebido (retenção, destino líquido da
    cota-parte, seguro) em % da receita de referência do ente (E+M agregado,
    distribuicao_2033.csv). Percentuais do painel A: texto literal do ADCT."""
    d = pd.read_csv(config.PROCESSED / "distribuicao_2033.csv")
    agg = d.groupby("uf")[["receita_referencia", "recebido_legal",
                           "componente_retencao", "componente_destino",
                           "componente_cota_parte",
                           "componente_seguro"]].sum()
    # cota-parte líquida por UF ≡ 0 (fluxo interno E→M), exceto arredondamento
    if (agg["componente_cota_parte"].abs() > 1e-9).any():
        raise AssertionError("F6: cota-parte não se anula no agregado E+M da UF")
    ref = agg["receita_referencia"]
    comp = pd.DataFrame({
        "retencao": 100 * agg["componente_retencao"] / ref,
        "destino": 100 * agg["componente_destino"] / ref,
        "seguro": 100 * agg["componente_seguro"] / ref,
    }).sort_values(["retencao"], kind="mergesort")
    comp = comp.assign(total=comp.sum(axis=1)) \
               .sort_values("total", kind="mergesort")

    anos = np.arange(2029, 2081)
    ret = np.where(anos <= 2032, 80.0,
                   np.where(anos == 2033, 90.0,
                            np.clip(90.0 * (1 - (anos - 2033) / 45.0),
                                    0.0, None)))
    ret[anos >= 2078] = 0.0

    with plt.rc_context(style.RC):
        fig, (ax_a, ax_b) = plt.subplots(
            2, 1, figsize=(7.2, 8.2), height_ratios=[1.0, 1.7])
        fig.subplots_adjust(left=0.085, right=0.975, top=0.975, bottom=0.082,
                            hspace=0.34)

        # ---- painel A: trajetória legal 2029-2080
        ax_a.fill_between(anos, 0, ret, step="mid", color=style.MUTED,
                          alpha=0.26, zorder=2)
        ax_a.fill_between(anos, ret, 100, step="mid", color=style.ESTADUAL,
                          alpha=0.18, zorder=2)
        ax_a.step(anos, ret, where="mid", color=style.INK2, lw=1.6, zorder=3)
        # blocos de texto posicionados INTEIRAMENTE dentro das áreas (nenhuma
        # linha cruza a escada; conferido contra ret(t) nos extremos do bloco)
        ax_a.text(2036, 20, "retenção distribuída por coeficientes de\n"
                  "receita média histórica (ADCT, art. 131, §§1º-2º;\n"
                  "LC 227/2026, arts. 109 e 114-115)",
                  ha="left", va="center", color=style.INK,
                  fontproperties=style.fp("medium", 8.2), zorder=4)
        cor_area_destino = _mistura(style.ESTADUAL, "#ffffff", 0.82)
        ax_a.text(2062, 80, "parcela distribuída pelo destino\n"
                  "(ADCT, art. 131, §4º), sujeita à cota-parte\n"
                  "municipal de 25% (CF, art. 158, IV, ‘b’)",
                  ha="left", va="center", color=style.INK,
                  fontproperties=style.fp("medium", 8.2), zorder=4,
                  bbox=dict(boxstyle="square,pad=0.15", fc=cor_area_destino,
                            ec="none"))
        ax_a.annotate("80% (2029-2032):\nconvivência com ICMS/ISS\n"
                      "a 9/10 até 6/10 das alíquotas\n(ADCT, art. 128)",
                      xy=(2031, 80), xytext=(2029.3, 52), ha="left", va="top",
                      fontproperties=style.fp("regular", 7.8),
                      color=style.INK2, zorder=4,
                      arrowprops=dict(arrowstyle="-", lw=0.8,
                                      color=style.INK2))
        ax_a.annotate("90% em 2033 + seguro-receita: 5% da\nparcela não "
                      "retida aos entes com maiores\nperdas relativas "
                      "(ADCT, art. 132)",
                      xy=(2033, 90), xytext=(2040, 99), ha="left", va="top",
                      fontproperties=style.fp("regular", 7.8),
                      color=style.INK2, zorder=4,
                      arrowprops=dict(arrowstyle="-", lw=0.8,
                                      color=style.INK2))
        ax_a.annotate("redução de 1/45 ao ano\n(2034-2077)",
                      xy=(2066, float(ret[anos == 2066][0])),
                      xytext=(2059, 5), ha="left", va="bottom",
                      fontproperties=style.fp("regular", 7.8),
                      color=style.INK2, zorder=4,
                      arrowprops=dict(arrowstyle="-", lw=0.8,
                                      color=style.INK2))
        ax_a.annotate("2078:\ndestino pleno", xy=(2078, 0),
                      xytext=(2072.5, 22), ha="left", va="bottom",
                      fontproperties=style.fp("bold", 7.8), color=style.INK,
                      zorder=4,
                      arrowprops=dict(arrowstyle="-", lw=0.8,
                                      color=style.INK2))
        ax_a.set_xlim(2029, 2080)
        ax_a.set_ylim(0, 100)
        ax_a.set_xticks([2029, 2033, 2040, 2050, 2060, 2070, 2078])
        ax_a.set_ylabel("% do produto do IBS",
                        fontproperties=style.fp("regular", 9.5))
        ax_a.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: br(v, 0)))
        style.style_axes(ax_a, grid="y")

        # ---- painel B: mecanismos em 2033, % da referência do ente (E+M)
        yb = np.arange(len(comp))
        # largura VISUAL mínima do seguro-receita (0,35% da referência),
        # compensada na fronteira com o destino — o comprimento total da
        # barra permanece exato; só a divisa interna desloca ~0,3 p.p.
        # (convenção de exibição; valores verdadeiros na Tabela A.2)
        seg_real = comp["seguro"].to_numpy()
        seg_vis = np.where((seg_real > 0) & (seg_real < 0.35), 0.35, seg_real)
        dest_vis = comp["destino"].to_numpy() - (seg_vis - seg_real)
        series = (("retenção (coeficientes históricos)", style.MUTED,
                   comp["retencao"].to_numpy()),
                  ("destino (líquido da cota-parte)", style.ESTADUAL,
                   dest_vis),
                  ("seguro-receita (art. 132)", style.POPULACAO, seg_vis))
        esq = np.zeros(len(comp))
        for rotulo, cor, v in series:
            ax_b.barh(yb, v, left=esq, height=0.68, color=cor, zorder=3,
                      edgecolor=style.SURFACE, linewidth=0.7, label=rotulo)
            esq += v
        ax_b.axvline(100, ls=(0, (5, 3)), lw=1.1, color=style.INK2, zorder=4)
        # rótulo da linha de 100% na zona livre inferior-direita (as barras
        # de baixo terminam antes de 100)
        ax_b.text(101.2, 1.8, "100% da\nreceita de\nreferência",
                  ha="left", va="center", color=style.INK2,
                  fontproperties=style.fp("medium", 8.0), zorder=5)
        # todas as barras rotuladas (remove a ambiguidade da rotulagem
        # seletiva); entes alcançados pelo seguro-receita em negrito
        seg_pos = comp["seguro"] > 0.005
        for i, (uf, r) in enumerate(comp.iterrows()):
            destaque = bool(seg_pos.loc[uf])
            # caixa branca + halo (withStroke): a linha tracejada de 100%
            # não risca os rótulos dos entes que terminam logo antes dela
            # nem encosta traços nos glifos (respiro além da caixa)
            ax_b.annotate(br(float(r["total"]), 1),
                          (float(r["total"]), i), xytext=(4, 0),
                          textcoords="offset points", va="center",
                          fontproperties=style.fp(
                              "bold" if destaque else "regular", 7.2),
                          color=style.INK if destaque else style.INK2,
                          zorder=6,
                          path_effects=[mpe.withStroke(
                              linewidth=7, foreground=style.SURFACE)],
                          bbox=dict(boxstyle="square,pad=0.10",
                                    fc=style.SURFACE, ec="none"))
        ax_b.set_yticks(yb)
        ax_b.set_yticklabels(comp.index,
                             fontproperties=style.fp("regular", 7.8))
        ax_b.set_ylim(-0.7, len(comp) - 0.1)
        ax_b.set_xlim(0, 114)
        ax_b.set_xticks(range(0, 101, 20))
        ax_b.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: br(v, 0)))
        ax_b.set_xlabel("recebido em 2033, por componente, em % da receita "
                        "de referência do ente (E+M)",
                        fontproperties=style.fp("regular", 9.5))
        style.style_axes(ax_b, grid="x")
        handles, labels = ax_b.get_legend_handles_labels()
        fig.legend(handles, labels, loc="center", ncols=3,
                   bbox_to_anchor=(0.53, 0.585), frameon=False,
                   prop=style.fp("regular", 8.4), labelcolor=style.INK2,
                   columnspacing=1.4, handlelength=1.5)
        style.source_note(fig, "Fonte: elaboração própria a partir de "
                          "SICONFI/DCA 2019-2025, RREO, POF 2017-2018 e TRU "
                          "2021; trajetória: ADCT, arts. 131-132 (AFERIR).")
        return _salva(fig, "fig6_transicao.png", out_dir)


# ---------------------------------------------------------------- F7
def _paths_da_feicao(geom: dict):
    """GeoJSON Polygon/MultiPolygon -> matplotlib Path composto (anéis
    exteriores e interiores no mesmo Path — buracos preservados)."""
    from matplotlib.path import Path as MplPath
    polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
             else geom["coordinates"])
    aneis = [MplPath(np.asarray(anel, dtype=float), closed=True)
             for rings in polys for anel in rings]
    return MplPath.make_compound_path(*aneis)


def _centroide_maior_anel(geom: dict) -> tuple[float, float]:
    """Centroide (shoelace) do maior anel exterior — âncora de anotações."""
    polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
             else geom["coordinates"])
    melhor, area_max = None, -1.0
    for rings in polys:
        v = np.asarray(rings[0], dtype=float)
        x, y = v[:, 0], v[:, 1]
        cruz = x * np.roll(y, -1) - np.roll(x, -1) * y
        a = cruz.sum() / 2.0
        if abs(a) > area_max:
            area_max, melhor = abs(a), (v, cruz, a)
    v, cruz, a = melhor
    cx = ((v[:, 0] + np.roll(v[:, 0], -1)) * cruz).sum() / (6.0 * a)
    cy = ((v[:, 1] + np.roll(v[:, 1], -1)) * cruz).sum() / (6.0 * a)
    return float(cx), float(cy)


def _mistura(hex_cor: str, alvo: str, t: float) -> str:
    """Mistura linear de hex_cor com `alvo` ('#ffffff' clareia, '#000000'
    escurece) na fração t — tintas derivadas da paleta validada."""
    a = np.array([int(hex_cor[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    b = np.array([int(alvo[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
    m = np.rint(a + (b - a) * t).astype(int)
    return "#" + "".join(f"{c:02x}" for c in m)


def fig7_mapa_uf(out_dir: Path | None = None) -> Path:
    """Dois mapas coropléticos do Brasil (malha IBGE, GeoJSON em coordenadas
    geográficas): necessidade indicativa estadual e municipal por UF,
    classificada em relação à referência e ao piso da PRÓPRIA esfera —
    mesma gramática da Figura de vetores (âmbar = piso vinculante; tintas
    da cor da esfera acima do piso). Classes, contagens e extremos vêm dos
    processados; malha: aferir.fetch.ibge.malha_uf (idempotente)."""
    from matplotlib.patches import PathPatch
    from aferir.fetch.ibge import COD_UF_SIGLA, malha_uf

    vet = pd.read_csv(config.PROCESSED / "aferir_vetor_uf.csv").set_index("uf")
    c = _central()
    malha = malha_uf()
    geo = {COD_UF_SIGLA[f["properties"]["codarea"]]: f["geometry"]
           for f in malha["features"]}

    paineis = (
        ("tau_E_uf_pp", float(c["tau_E_pp"]), style.ESTADUAL,
         "IBS estadual", [("AM", "dentro"), ("DF", "fora", (-37.3, -18.6))]),
        ("tau_M_uf_pp", float(c["tau_M_pp"]), style.MUNICIPAL,
         "IBS municipal (agregado por UF)",
         [("SP", "fora", (-44.5, -28.0)), ("AP", "fora", (-46.5, 3.4)),
          ("DF", "fora", (-42.8, -12.6))]),
    )

    with plt.rc_context(style.RC):
        fig, eixos = plt.subplots(1, 2, figsize=(7.2, 5.0))
        fig.subplots_adjust(left=0.015, right=0.985, top=0.925, bottom=0.235,
                            wspace=0.04)

        for ax, (col, ref, cor, titulo, destaques) in zip(eixos, paineis):
            piso = 0.905 * ref
            limites = np.array([piso, ref, 1.5 * ref])
            # tinta da classe 2 por esfera: no painel municipal (laranja, da
            # mesma família quente do âmbar) a mistura é menor para manter a
            # LUMINÂNCIA monotônica acima do âmbar (âmbar = status, mais
            # claro que toda a rampa); no estadual a quebra de matiz
            # (amarelo vs. azul) já sinaliza a classe categórica
            t_claro = 0.62 if cor == style.ESTADUAL else 0.32
            cores = [style.ALERTA, _mistura(cor, "#ffffff", t_claro), cor,
                     _mistura(cor, "#000000", 0.45)]
            classes = {uf: int(np.searchsorted(limites, float(v), "right"))
                       for uf, v in vet[col].items()}
            for uf, geom in geo.items():
                ax.add_patch(PathPatch(_paths_da_feicao(geom),
                                       facecolor=cores[classes[uf]],
                                       edgecolor=style.SURFACE, linewidth=0.7,
                                       zorder=3))
            # extremos anotados (máximo e mínimo do painel)
            for d in destaques:
                uf, modo = d[0], d[1]
                v = float(vet.loc[uf, col])
                cx, cy = _centroide_maior_anel(geo[uf])
                if modo == "dentro":
                    ax.text(cx, cy, f"{uf}: {br(v, 1)}", ha="center",
                            va="center", color=style.SURFACE, zorder=5,
                            fontproperties=style.fp("bold", 9.0))
                else:
                    # arco suave: a guia do DF estadual bordeja o ES (classe
                    # oposta) por cima em vez de tangenciá-lo em linha reta
                    ax.annotate(f"{uf}: {br(v, 1)}", xy=(cx, cy),
                                xytext=d[2], ha="left", va="center",
                                color=style.INK, zorder=5,
                                fontproperties=style.fp("bold", 8.6),
                                arrowprops=dict(arrowstyle="-", lw=0.8,
                                                color=style.INK2,
                                                shrinkA=2, shrinkB=1,
                                                connectionstyle="arc3,rad=0.14"))
            n = np.bincount(list(classes.values()), minlength=4)
            legenda = [
                plt.Rectangle((0, 0), 1, 1, fc=cores[0],
                              label=f"abaixo do piso (< {br(piso, 2)}): "
                                    f"{n[0]} de 27"),
                plt.Rectangle((0, 0), 1, 1, fc=cores[1],
                              label=f"do piso à referência "
                                    f"({br(piso, 2)} a {br(ref, 2)}): {n[1]}"),
                plt.Rectangle((0, 0), 1, 1, fc=cores[2],
                              label=f"da referência a 1,5× "
                                    f"(até {br(1.5 * ref, 2)}): {n[2]}"),
                plt.Rectangle((0, 0), 1, 1, fc=cores[3],
                              label=f"acima de 1,5× a referência: {n[3]}"),
            ]
            ax.legend(handles=legenda, loc="upper left",
                      bbox_to_anchor=(-0.02, -0.015), frameon=False,
                      prop=style.fp("regular", 8.0), labelcolor=style.INK2,
                      handlelength=1.3, handleheight=1.0,
                      borderaxespad=0.0, labelspacing=0.42)
            ax.set_title(titulo, fontproperties=style.fp("bold", 10.5),
                         color=style.INK, pad=8)
            ax.set_aspect("equal")
            ax.autoscale_view()
            ax.axis("off")

        style.source_note(fig, "Fonte: elaboração própria a partir de "
                          "SICONFI/DCA, RREO, POF 2017-2018 e TRU 2021; "
                          "malha: IBGE, API de Malhas v3 (AFERIR).")
        return _salva(fig, "fig7_mapa_uf.png", out_dir)


# ---------------------------------------------------------------- main
FIGURAS = (fig1_vetores_uf, fig2_origem_destino, fig3_lorenz_iss,
           fig4_comparadores, fig5_cenarios, fig6_transicao, fig7_mapa_uf)


def main() -> None:
    for funcao in FIGURAS:
        print("gerada", funcao())


if __name__ == "__main__":
    main()
