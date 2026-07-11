"""Sistema de design das figuras AFERIR — manuscrito e divulgação.

Paleta e especificações de marca herdadas do método design-system-agnostic
de visualização de dados (seis verificações: forma → cor → validação →
marcas → rótulos → revisão visual). Paleta categórica validada (CVD ΔE ≥ 12,
contraste ≥ 3:1 no papel claro) — ver `references/palette.md` do skill.

Tipografia: Helvetica Neue (família do sistema macOS), quatro pesos extraídos
da coleção `.ttc` do SO como TTFs autônomos em `assets/fonts/` — o próprio
matplotlib não lê múltiplas faces de uma `.ttc`; extrair resolve isso sem
depender de nenhuma fonte de terceiros. Fallback: DejaVu Sans (embutida no
matplotlib) se os arquivos não existirem (ambiente não-macOS).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm

ASSETS_FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"

_FACES = {
    "regular": "HelveticaNeue-Regular.ttf",
    "medium": "HelveticaNeue-Medium.ttf",
    "bold": "HelveticaNeue-Bold.ttf",
    "light": "HelveticaNeue-Light.ttf",
}
FAMILY = "Helvetica Neue"
_FALLBACK_FAMILY = "DejaVu Sans"

_registered = False


def _register_fonts() -> str:
    """Registra os quatro pesos no matplotlib; retorna a família a usar."""
    global _registered
    if _registered:
        return FAMILY
    faltando = [f for f in _FACES.values() if not (ASSETS_FONTS / f).exists()]
    if faltando:
        return _FALLBACK_FAMILY
    for arq in _FACES.values():
        fm.fontManager.addfont(str(ASSETS_FONTS / arq))
    _registered = True
    return FAMILY


ATIVA = _register_fonts()


def fp(weight: str = "regular", size: float | None = None) -> fm.FontProperties:
    """FontProperties no peso pedido; cai para DejaVu Sans fora do macOS."""
    if ATIVA == _FALLBACK_FAMILY:
        peso_map = {"regular": "normal", "medium": "medium", "bold": "bold",
                    "light": "light"}
        return fm.FontProperties(family=_FALLBACK_FAMILY,
                                 weight=peso_map.get(weight, "normal"),
                                 size=size)
    return fm.FontProperties(fname=str(ASSETS_FONTS / _FACES[weight]), size=size)


# ---------------------------------------------------------------- cor
# Tokens de chrome (papel claro — as figuras do manuscrito vivem numa
# página A4 branca do Word; SURFACE_CARD é usado só nas peças de divulgação).
INK = "#0b0b0b"          # texto primário, valores em destaque
INK2 = "#52514e"         # texto secundário (notas, subtítulos)
MUTED = "#898781"        # eixos, ticks, rótulos discretos
GRID = "#e1e0d9"         # linha de grade (hairline)
BASELINE = "#c3c2b7"     # eixo/spine
SURFACE = "#ffffff"      # fundo das figuras do manuscrito (página branca)
SURFACE_CARD = "#fcfcfb"  # fundo das peças de divulgação (claras)
SURFACE_DARK = "#14171c"  # fundo das peças de divulgação (escuras)

# Paleta categórica (ordem fixa, ΔE validado) — papel de cada série no
# corpus AFERIR, não apenas "cor 1, cor 2...":
ESTADUAL = "#2a78d6"       # IBS estadual (fig1 barras, fig2/fig3 séries principais)
MUNICIPAL = "#eb6834"      # IBS municipal
CONSTRUCAO_A = "#4a3aa7"   # construção âncora-consistente (fig4)
AFERIR_B = "#2a78d6"       # identidade "este artigo, construção B" (fig4) = ESTADUAL
POPULACAO = "#1baf7a"      # série de contraste (fig3: Lorenz da população)
LITERATURA = "#898781"     # literatura/notas oficiais (= MUTED)

# Paleta de status (fixa — nunca reciclada para série)
CRITICO = "#d03b3b"        # gatilho de revisão / trava (art. 475, §11)
BOM = "#0ca30c"            # suficiência ≥ piso (distribuição legal)
ALERTA = "#fab219"         # zona de atenção (piso vinculante)

DPI = 400
FIGSIZE = (7.2, 5.4)                      # × 400 dpi = 2880×2160 px
PNG_METADATA = {"Software": "AFERIR (matplotlib/Agg)"}  # fixo: determinismo

RC = {
    "font.family": ATIVA,
    "font.sans-serif": [ATIVA, "DejaVu Sans"],
    "font.size": 10,
    "text.color": INK,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.7,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.frameon": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
}


def br(v: float, nd: int = 2) -> str:
    """Número em convenção PT-BR (vírgula decimal, ponto de milhar)."""
    s = f"{v:,.{nd}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def style_axes(ax, grid: str = "y") -> None:
    """Aplica o chrome padrão: eixos recessivos, grade hairline, ticks mudos."""
    ax.tick_params(colors=MUTED, labelcolor=INK2, length=3.0)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(BASELINE)
    if grid:
        ax.grid(axis=grid, lw=0.6, color=GRID, zorder=0)
    ax.set_axisbelow(True)


def source_note(fig, text: str, y: float = 0.012, x: float = 0.012,
                ha: str = "left") -> None:
    """Linha de fonte, tipografia discreta (rodapé editorial FT/OWID)."""
    fig.text(x, y, text, fontproperties=fp("regular", 7.6), color=MUTED, ha=ha,
             va="bottom")


def savefig(fig, path: Path, dpi: int = DPI) -> Path:
    """Grava a figura no próprio facecolor (branco nas figuras do manuscrito;
    escuro/claro nas peças de divulgação — nunca sobrescrito para branco)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, metadata=PNG_METADATA,
               facecolor=fig.get_facecolor())
    matplotlib.pyplot.close(fig)
    return path
