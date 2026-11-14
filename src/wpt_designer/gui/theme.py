"""
UI Design System & Theme Configuration for WPT Coil Designer.
Defines a neutral Tailwind Slate color palette, typography hierarchy,
4px/8px spacing conventions, crisp 1px borders (#e2e8f0 / #cbd5e1),
and publication-grade Matplotlib plot styling.
"""

import tkinter as tk
from tkinter import ttk
import matplotlib as mpl
from matplotlib.figure import Figure

# ==============================================================================
# 1. COLOR TOKENS (Tailwind Slate / Zinc Palette)
# ==============================================================================

# Backgrounds & Surfaces
BG_WINDOW = "#f8fafc"       # Slate-50: Main window and outer panels
BG_CARD = "#ffffff"         # Pure white: Content cards and containers
BG_SUBTLE = "#f1f5f9"       # Slate-100: Secondary containers, table stripes
BG_MUTED = "#e2e8f0"        # Slate-200: Inactive tabs, divider lines
BG_HOVER = "#e0e7ff"        # Soft blue-tint hover for list rows

# Borders
BORDER_COLOR = "#e2e8f0"    # Subtle 1px card boundary
BORDER_STRONG = "#cbd5e1"   # Focused/active control border
BORDER_FOCUS = "#3b82f6"    # Active field focus glow

# Typography Colors
TEXT_MAIN = "#0f172a"       # Slate-900: High-contrast primary text (> 12:1)
TEXT_BODY = "#334155"       # Slate-700: Normal labels and body text
TEXT_MUTED = "#64748b"      # Slate-500: Hints, subheadings, units
TEXT_LIGHT = "#94a3b8"      # Slate-400: Disabled or placeholder text
TEXT_WHITE = "#ffffff"      # Pure white on dark accents

# Functional Accents
ACCENT_PRIMARY = "#2563eb"  # Blue-600: Primary actions & active tabs
ACCENT_HOVER = "#1d4ed8"    # Blue-700: Hover state for primary buttons
ACCENT_ACTIVE = "#1e40af"   # Blue-800: Pressed state
ACCENT_LIGHT = "#eff6ff"    # Blue-50: Badge and alert background

# Semantic Telemetry Colors
COLOR_SUCCESS = "#16a34a"   # Green-600: ZVS inductive mode, convergence OK
COLOR_SUCCESS_BG = "#f0fdf4"# Green-50: Success badge background
COLOR_WARNING = "#d97706"   # Amber-600: Critical coupling, near limits
COLOR_WARNING_BG = "#fffbeb"# Amber-50: Warning badge background
COLOR_DANGER = "#dc2626"    # Red-600: Hard switching, invalid parameters
COLOR_DANGER_BG = "#fef2f2" # Red-50: Error badge & invalid entry background
COLOR_COPPER = "#b45309"    # Amber-700: Coil winding copper accent
COLOR_SAPPHIRE = "#0284c7"  # Sky-600: Receiver / secondary coil accent
COLOR_PURPLE = "#7c3aed"    # Violet-600: Frequency / tracking accent

# ==============================================================================
# 2. TYPOGRAPHY HIERARCHY
# ==============================================================================

FONT_FAMILY_SANS = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

FONTS = {
    "title": (FONT_FAMILY_SANS, 13, "bold"),
    "subtitle": (FONT_FAMILY_SANS, 11, "bold"),
    "section": (FONT_FAMILY_SANS, 10, "bold"),
    "body": (FONT_FAMILY_SANS, 9),
    "body_bold": (FONT_FAMILY_SANS, 9, "bold"),
    "caption": (FONT_FAMILY_SANS, 8),
    "caption_bold": (FONT_FAMILY_SANS, 8, "bold"),
    "kpi_value": (FONT_FAMILY_SANS, 17, "bold"),
    "kpi_label": (FONT_FAMILY_SANS, 8, "bold"),
    "kpi_sub": (FONT_FAMILY_SANS, 8),
    "mono": (FONT_FAMILY_MONO, 9),
    "mono_bold": (FONT_FAMILY_MONO, 9, "bold"),
    "tab": (FONT_FAMILY_SANS, 9, "bold"),
}

# ==============================================================================
# 3. TTK STYLING CONFIGURATION
# ==============================================================================

def configure_ttk_theme(style: ttk.Style) -> None:
    """Configures the modern Tailwind Slate/Zinc theme on the ttk.Style instance."""
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Global base defaults
    style.configure(".", background=BG_WINDOW, font=FONTS["body"], foreground=TEXT_MAIN)
    style.configure("TFrame", background=BG_WINDOW)
    style.configure("Card.TFrame", background=BG_CARD)
    style.configure("Subtle.TFrame", background=BG_SUBTLE)

    # Notebook & Tabs
    style.configure(
        "TNotebook",
        background=BG_WINDOW,
        borderwidth=0,
        tabmargins=[4, 4, 4, 0]
    )
    style.configure(
        "TNotebook.Tab",
        background=BG_MUTED,
        foreground=TEXT_BODY,
        padding=[12, 6],
        font=FONTS["tab"],
        borderwidth=0
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG_CARD), ("!selected", BG_MUTED), ("active", "#cbd5e1")],
        foreground=[("selected", ACCENT_PRIMARY), ("!selected", TEXT_BODY)],
        focuscolor=[("selected", BG_CARD), ("!selected", BG_MUTED)]
    )

    # LabelFrames (Cards)
    style.configure(
        "TLabelframe",
        background=BG_CARD,
        relief="solid",
        borderwidth=1,
        bordercolor=BORDER_COLOR
    )
    style.configure(
        "TLabelframe.Label",
        background=BG_CARD,
        foreground=TEXT_MAIN,
        font=FONTS["section"]
    )
    style.configure(
        "HeaderCard.TLabelframe",
        background=BG_CARD,
        relief="solid",
        borderwidth=1,
        bordercolor=BORDER_COLOR
    )
    style.configure(
        "HeaderCard.TLabelframe.Label",
        background=BG_CARD,
        foreground=ACCENT_PRIMARY,
        font=FONTS["subtitle"]
    )

    # Labels
    style.configure("TLabel", background=BG_WINDOW, foreground=TEXT_MAIN, font=FONTS["body"])
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_BODY, font=FONTS["body"])
    style.configure("CardBold.TLabel", background=BG_CARD, foreground=TEXT_MAIN, font=FONTS["body_bold"])
    style.configure("Muted.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=FONTS["caption"])
    style.configure("Unit.TLabel", background=BG_CARD, foreground=TEXT_MUTED, font=FONTS["caption_bold"])
    style.configure("PanelBold.TLabel", background=BG_WINDOW, foreground=TEXT_MAIN, font=FONTS["body_bold"])

    # Status Bar
    style.configure(
        "Status.TLabel",
        background=BG_CARD,
        foreground=TEXT_BODY,
        font=FONTS["body"],
        relief="solid",
        borderwidth=1,
        padding=[8, 4]
    )

    # Entry Fields
    style.configure(
        "TEntry",
        fieldbackground=BG_CARD,
        foreground=TEXT_MAIN,
        insertcolor=TEXT_MAIN,
        padding=[6, 4],
        font=FONTS["body"]
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", BORDER_FOCUS), ("!focus", BORDER_COLOR)],
        lightcolor=[("focus", BORDER_FOCUS), ("!focus", BORDER_COLOR)]
    )

    # Buttons
    style.configure(
        "TButton",
        background=BG_CARD,
        foreground=TEXT_MAIN,
        padding=[10, 5],
        font=FONTS["body_bold"],
        relief="solid",
        borderwidth=1,
        bordercolor=BORDER_COLOR
    )
    style.map(
        "TButton",
        background=[("pressed", BG_MUTED), ("active", BG_SUBTLE)],
        foreground=[("pressed", ACCENT_HOVER), ("active", ACCENT_PRIMARY)],
        bordercolor=[("active", ACCENT_PRIMARY)]
    )

    # Primary Action Button (Cobalt)
    style.configure(
        "Primary.TButton",
        background=ACCENT_PRIMARY,
        foreground=TEXT_WHITE,
        padding=[14, 7],
        font=FONTS["body_bold"],
        relief="flat",
        borderwidth=0
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", ACCENT_ACTIVE), ("active", ACCENT_HOVER)],
        foreground=[("disabled", "#cbd5e1")]
    )

    # Checkbuttons
    style.configure("TCheckbutton", background=BG_CARD, foreground=TEXT_MAIN, font=FONTS["body"])
    style.map("TCheckbutton", background=[("active", BG_CARD)])

    # Comboboxes
    style.configure(
        "TCombobox",
        fieldbackground=BG_CARD,
        background=BG_CARD,
        foreground=TEXT_MAIN,
        padding=[5, 4],
        font=FONTS["body"]
    )

    # Treeview (Data tables)
    style.configure(
        "Treeview",
        background=BG_CARD,
        fieldbackground=BG_CARD,
        foreground=TEXT_MAIN,
        font=FONTS["body"],
        rowheight=26,
        borderwidth=1,
        relief="solid"
    )
    style.configure(
        "Treeview.Heading",
        background=BG_SUBTLE,
        foreground=TEXT_MAIN,
        font=FONTS["body_bold"],
        padding=[6, 4],
        relief="flat"
    )
    style.map(
        "Treeview",
        background=[("selected", BG_HOVER)],
        foreground=[("selected", ACCENT_PRIMARY)]
    )

    # Progressbar
    style.configure(
        "TProgressbar",
        background=ACCENT_PRIMARY,
        troughcolor=BG_MUTED,
        borderwidth=0
    )


# ==============================================================================
# 4. PUBLICATION-GRADE MATPLOTLIB THEME
# ==============================================================================


def configure_matplotlib_defaults() -> None:
    """Sets clean sans-serif publication defaults on matplotlib.rcParams."""
    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial"]
    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["axes.edgecolor"] = "#cbd5e1"
    mpl.rcParams["axes.linewidth"] = 1.0
    mpl.rcParams["font.size"] = 10
    mpl.rcParams["axes.titlesize"] = 11.5
    mpl.rcParams["axes.labelsize"] = 10.5
    mpl.rcParams["xtick.labelsize"] = 9.5
    mpl.rcParams["ytick.labelsize"] = 9.5
    mpl.rcParams["legend.fontsize"] = 9.5


def apply_publication_theme(fig: Figure) -> None:
    """
    Applies clean publication-grade styling to a Matplotlib figure:
    - High contrast, sans-serif Segoe UI typography.
    - Subtle Slate-200 grid lines and clean spines.
    - Synchronized pure white background.
    """
    fig.patch.set_facecolor("#ffffff")
    for ax in fig.axes:
        ax.set_facecolor("#ffffff")
        ax.grid(True, color="#f1f5f9", linestyle="--", linewidth=0.8, alpha=0.9)
        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")
            spine.set_linewidth(1.0)
        ax.tick_params(colors="#334155", labelsize=10)
        ax.xaxis.label.set_color("#1e293b")
        ax.yaxis.label.set_color("#1e293b")
