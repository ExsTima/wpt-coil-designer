"""
Main GUI application window coordinator for WPT Coil Designer and Analyzer v2.0.
Manages the multi-tab Tkinter interface, shared telemetry status bar,
lazy tab rendering, simulation orchestration, and file exports.
"""

import csv
import logging
import sys
from pathlib import Path
import time
from typing import Any, Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..core.simulation import (
    compute_distance_table,
    format_markdown_report,
    run_wpt_simulation,
)
from ..main import configure_dpi_awareness
from .presets import PRESET_NAMES
from .tabs import (
    DistanceSweepTab,
    FemmTab,
    Field2DTab,
    Field3DTab,
    FrequencySweepTab,
    InputTab,
    ResultsTab,
)
from .theme import (
    BG_CARD,
    BG_WINDOW,
    COLOR_DANGER,
    COLOR_DANGER_BG,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    FONTS,
    TEXT_BODY,
    TEXT_MUTED,
    configure_matplotlib_defaults,
    configure_ttk_theme,
)
from .tooltip import ToolTip

logger = logging.getLogger(__name__)

configure_matplotlib_defaults()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SCREENSHOT_PATH = ASSETS_DIR / "femm_verification_screenshot.png"


class WPTCalculatorApp:
    """Главное окно приложения WPT Coil Designer & Analyzer."""

    def __init__(self, root: tk.Tk):
        configure_dpi_awareness()

        self.root = root
        self.root.title(
            f"WPT Coil Designer & Analyzer v{__version__} — Научно-инженерный комплекс проектирования БПЭ"
        )

        # Responsive adaptive sizing: 84% width, 86% height
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        init_w = max(1120, min(int(screen_w * 0.84), 2200))
        init_h = max(700, min(int(screen_h * 0.86), 1300))
        pos_x = max(0, (screen_w - init_w) // 2)
        pos_y = max(0, (screen_h - init_h) // 2)
        self.root.geometry(f"{init_w}x{init_h}+{pos_x}+{pos_y}")
        self.root.minsize(1020, 620)

        self._load_app_icons()

        self.results: Optional[Dict[str, Any]] = None
        self._dirty_tabs: Dict[int, bool] = {2: True, 3: True, 4: True, 5: True, 6: True}

        self.status_var = tk.StringVar(
            value="Готов к работе. Наведите курсор на параметр для просмотра физического описания."
        )
        self.telemetry_zvs_var = tk.StringVar(value="🟢 ZVS активна (индуктивный режим)")
        self.telemetry_bench_var = tk.StringVar(value="⚡ Решатель: 0.0 мс")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_widgets()
        self.calculate()

    def _load_app_icons(self) -> None:
        icon_ico = ASSETS_DIR / "icon.ico"
        icon_png = ASSETS_DIR / "icon.png"
        if sys.platform == "win32" and icon_ico.exists():
            try:
                self.root.iconbitmap(str(icon_ico))
            except Exception as exc:
                logger.debug("Failed to load icon.ico: %s", exc)
        if icon_png.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon_png))
                self.root.iconphoto(True, self._icon_img)
            except Exception as exc:
                logger.debug("Failed to load icon.png: %s", exc)

    @property
    def _spline_B_2d(self):
        return self.field_2d_tab.spline_B_2d

    def on_close(self) -> None:
        for tab in (self.frequency_tab, self.field_2d_tab, self.field_3d_tab):
            tab.cancel_pending()
        self.femm_tab.stop_and_close()
        for tab in (self.distance_tab, self.frequency_tab, self.field_2d_tab, self.field_3d_tab):
            tab.close()
        self.root.destroy()

    def attach_help(self, widget: tk.Widget, text: str, title: Optional[str] = None) -> None:
        ToolTip(widget, text, self.status_var, title=title)

    def create_widgets(self) -> None:
        self.root.configure(bg=BG_WINDOW)
        configure_ttk_theme(ttk.Style())

        # Three-Segment Telemetry Status Bar
        status_container = tk.Frame(self.root, bg=BG_CARD, bd=1, relief="solid", highlightthickness=0)
        status_container.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))

        tk.Label(
            status_container,
            textvariable=self.status_var,
            font=FONTS["body"],
            fg=TEXT_BODY,
            bg=BG_CARD,
            anchor="w",
            padx=10,
            pady=4,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_zvs_badge = tk.Label(
            status_container,
            textvariable=self.telemetry_zvs_var,
            font=FONTS["body_bold"],
            fg=COLOR_SUCCESS,
            bg=COLOR_SUCCESS_BG,
            padx=12,
            pady=3,
            relief="solid",
            bd=1,
            highlightbackground=COLOR_SUCCESS,
            highlightthickness=0,
        )
        self.lbl_zvs_badge.pack(side=tk.LEFT, padx=6, pady=2)
        self.attach_help(
            self.lbl_zvs_badge,
            "Текущий режим коммутации инвертора. Режим ZVS (Zero Voltage Switching) гарантирует безопасное переключение ключей при нуле напряжения.",
        )

        lbl_bench = tk.Label(
            status_container,
            textvariable=self.telemetry_bench_var,
            font=FONTS["mono_bold"],
            fg=TEXT_MUTED,
            bg=BG_CARD,
            padx=10,
            pady=4,
        )
        lbl_bench.pack(side=tk.RIGHT)
        self.attach_help(lbl_bench, "Время решения аналитической электродинамической модели контуров WPT.")

        # Main Tabbed Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 2))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        self.tab_input = ttk.Frame(self.notebook)
        self.tab_calc = ttk.Frame(self.notebook)
        self.tab_graphs = ttk.Frame(self.notebook)
        self.tab_freq = ttk.Frame(self.notebook)
        self.tab_field_2d = ttk.Frame(self.notebook)
        self.tab_field_3d = ttk.Frame(self.notebook)
        self.tab_femm = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_input, text="1. Параметры & Экспресс-анализ")
        self.notebook.add(self.tab_calc, text="2. Энергетический баланс")
        self.notebook.add(self.tab_graphs, text="3. Зависимости от зазора")
        self.notebook.add(self.tab_freq, text="4. Частотный анализ (АЧХ)")
        self.notebook.add(self.tab_field_2d, text="5. Магнитное поле 2D")
        self.notebook.add(self.tab_field_3d, text="6. Магнитное поле 3D")
        self.notebook.add(self.tab_femm, text="7. МКЭ-верификация (FEMM)")

        self.input_tab = InputTab(
            self.tab_input, self.root, self.attach_help, self.status_var, on_calculate=self.calculate
        )
        self.results_tab = ResultsTab(
            self.tab_calc, self.attach_help, on_copy_report=self.copy_report_to_clipboard, on_export_csv=self.save_table
        )
        self.distance_tab = DistanceSweepTab(self.tab_graphs, self.attach_help, on_export_csv=self.save_table)
        self.frequency_tab = FrequencySweepTab(
            self.tab_freq, self.root, get_results=lambda: self.results, on_mark_clean=lambda: self._dirty_tabs.__setitem__(3, False)
        )
        self.field_2d_tab = Field2DTab(
            self.tab_field_2d, self.root, self.status_var, get_results=lambda: self.results, on_mark_clean=lambda: self._dirty_tabs.__setitem__(4, False)
        )
        self.field_3d_tab = Field3DTab(
            self.tab_field_3d, self.root, get_results=lambda: self.results, on_mark_clean=lambda: self._dirty_tabs.__setitem__(5, False)
        )
        self.femm_tab = FemmTab(
            self.tab_femm, self.root, self.attach_help, get_results=lambda: self.results, examples_dir=EXAMPLES_DIR, screenshot_path=SCREENSHOT_PATH
        )

        # Compatibility references to tab StringVars/dicts
        self.preset_var = self.input_tab.preset_var
        self.live_kpi = self.input_tab.live_kpi
        self.vars = self.input_tab.vars
        self.entry_widgets = self.input_tab.entry_widgets
        self.var_sym = self.input_tab.var_sym
        self.var_auto_track = self.input_tab.var_auto_track
        self.power_balance_var = self.results_tab.power_balance_var
        self.res_vars = self.results_tab.res_vars
        self.kpi_vars = self.results_tab.kpi_vars
        self.bot_insight_var = self.results_tab.bot_insight_var

    def apply_selected_preset(self, event=None) -> None:
        self.input_tab.apply_selected_preset(event)

    def load_preset_by_key(self, preset_key: str) -> None:
        self.input_tab.load_preset_by_key(preset_key)

    def toggle_symmetry(self) -> None:
        self.input_tab.toggle_symmetry()

    def sync_coils(self) -> None:
        self.input_tab.sync_coils()

    def _on_notebook_tab_changed(self, _event=None) -> None:
        if not self.results:
            return
        try:
            curr_idx = self.notebook.index(self.notebook.select())
            self._render_tab_if_dirty(curr_idx)
        except tk.TclError:
            pass

    def _render_tab_if_dirty(self, tab_idx: int) -> None:
        if not self.results or not self._dirty_tabs.get(tab_idx, False):
            return
        if tab_idx == 2:
            self.update_graphs()
        elif tab_idx == 3:
            self.update_freq_sweep(float(self.frequency_tab.slider_freq_d.get()))
        elif tab_idx == 4:
            self.plot_field_2d()
        elif tab_idx == 5:
            self.plot_field_3d()
        elif tab_idx == 6:
            self.femm_tab.populate_initial_table(self.results)
        self._dirty_tabs[tab_idx] = False

    def calculate(self) -> None:
        t_start = time.perf_counter()
        try:
            params, err_msg = self.input_tab.read_inputs()
            if params is None:
                if err_msg:
                    self.status_var.set(err_msg)
                return

            try:
                results = run_wpt_simulation(**params)
            except ValueError as exc:
                self.status_var.set(f"Ошибка: {exc}")
                return

            self.results = results
            self.input_tab.update_from_results(results)
            self.results_tab.update_from_results(results, auto_track=bool(self.var_auto_track.get()))

            t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            self.telemetry_bench_var.set(f"⚡ Решатель: {t_elapsed_ms:.1f} мс")

            phase_deg = results["circuit"]["phase_deg"]
            if phase_deg >= 0:
                self.telemetry_zvs_var.set(f"🟢 ZVS активна (φ = +{phase_deg:.1f}°)")
                self.lbl_zvs_badge.configure(bg=COLOR_SUCCESS_BG, fg=COLOR_SUCCESS)
            else:
                self.telemetry_zvs_var.set(f"🔴 Жесткая коммутация (φ = {phase_deg:.1f}°)")
                self.lbl_zvs_badge.configure(bg=COLOR_DANGER_BG, fg=COLOR_DANGER)

            for tab_id in (2, 3, 4, 5, 6):
                self._dirty_tabs[tab_id] = True

            try:
                curr_idx = self.notebook.index(self.notebook.select())
                self._render_tab_if_dirty(curr_idx)
            except tk.TclError:
                pass

        except Exception as exc:
            logger.exception("Calculation error")
            self.status_var.set(f"Ошибка при расчете: {exc}")

    def update_graphs(self) -> None:
        if self.results:
            self.distance_tab.render(self.results, auto_track=bool(self.var_auto_track.get()))

    def update_freq_sweep(self, d_mm: float) -> None:
        if self.results:
            self.frequency_tab.render(self.results, d_mm=d_mm)

    def plot_field_2d(self) -> None:
        if self.results:
            self.field_2d_tab.render(self.results)

    def plot_field_3d(self) -> None:
        if self.results:
            self.field_3d_tab.render(self.results)

    def copy_report_to_clipboard(self) -> None:
        if not self.results:
            return
        report = format_markdown_report(self.results, version=__version__)
        self.root.clipboard_clear()
        self.root.clipboard_append(report)
        self.status_var.set("Отчёт успешно скопирован в буфер обмена в формате Markdown!")

    def save_table(self) -> None:
        if not self.results:
            return
        fn = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not fn:
            return
        rows = compute_distance_table(self.results, auto_track=bool(self.var_auto_track.get()))
        fieldnames = ["d_mm", "k", "eta_pct", "Pout_W", "Ploss_W", "Vout_V"]
        with open(fn, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        messagebox.showinfo("Экспорт", "Таблица данных сохранена.")


__all__ = ["WPTCalculatorApp", "PRESET_NAMES"]
