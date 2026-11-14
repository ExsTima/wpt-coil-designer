"""
Tab 4: Frequency response (AFC / bifurcation) sweep charts.
"""

from typing import Any, Callable, Dict, Optional
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import ttk

from ...core.simulation import compute_frequency_sweep
from ..theme import ACCENT_PRIMARY, BG_MUTED, BG_WINDOW, FONTS, TEXT_MAIN, apply_publication_theme


class FrequencySweepTab:
    """Вкладка 4: Частотный анализ (АЧХ мощности и КПД при расщеплении резонанса)."""

    def __init__(
        self,
        parent: ttk.Frame,
        root: tk.Tk,
        get_results: Callable[[], Optional[Dict[str, Any]]],
        on_mark_clean: Callable[[], None],
    ):
        self.parent = parent
        self.root = root
        self._get_results = get_results
        self._on_mark_clean = on_mark_clean
        self._after_id: Optional[str] = None
        self.fig_freq = None
        self.ax_f_pout = None
        self.ax_f_eta = None
        self.canvas_freq: Optional[FigureCanvasTkAgg] = None
        self._build_ui()

    def _build_ui(self) -> None:
        ctrl = ttk.Frame(self.parent, padding=8)
        ctrl.pack(fill="x")
        tk.Label(ctrl, text="Осевой зазор d:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(
            side="left", padx=(6, 4)
        )

        self.var_freq_d_val = tk.StringVar(value="10 мм")
        self.slider_freq_d = tk.Scale(
            ctrl,
            from_=2,
            to=45,
            orient="horizontal",
            length=220,
            resolution=1,
            showvalue=False,
            font=FONTS["caption"],
            bg=BG_WINDOW,
            fg=TEXT_MAIN,
            activebackground=ACCENT_PRIMARY,
            troughcolor=BG_MUTED,
            bd=0,
            highlightthickness=0,
            command=self._on_slider_change,
        )
        self.slider_freq_d.set(10)
        self.slider_freq_d.pack(side="left", padx=4)

        tk.Label(
            ctrl,
            textvariable=self.var_freq_d_val,
            font=FONTS["mono_bold"],
            fg=ACCENT_PRIMARY,
            bg=BG_WINDOW,
            width=6,
        ).pack(side="left", padx=(2, 10))

        self._plot_host = ttk.Frame(self.parent)
        self._plot_host.pack(fill=tk.BOTH, expand=True)

    def _ensure_canvas(self) -> None:
        if self.canvas_freq is not None:
            return
        self.fig_freq = Figure(figsize=(9, 4.5))
        self.ax_f_pout, self.ax_f_eta = self.fig_freq.subplots(1, 2)
        apply_publication_theme(self.fig_freq)
        self.canvas_freq = FigureCanvasTkAgg(self.fig_freq, master=self._plot_host)
        self.canvas_freq.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _on_slider_change(self, val: str) -> None:
        self.var_freq_d_val.set(f"{int(float(val))} мм")
        if self._get_results() is None:
            return
        self.cancel_pending()
        self._after_id = self.root.after(40, lambda v=float(val): self._render_and_clean(v))

    def _render_and_clean(self, val: float) -> None:
        self._after_id = None
        results = self._get_results()
        if not results:
            return
        self.render(results, d_mm=val)
        self._on_mark_clean()

    def render(self, results: Dict[str, Any], d_mm: Optional[float] = None) -> None:
        if not results:
            return
        self._ensure_canvas()
        if d_mm is None:
            d_mm = float(self.slider_freq_d.get())

        sweep = compute_frequency_sweep(results, d_mm)
        d_eff = sweep["d_mm"]
        kd = sweep["kd"]
        f_opt_d = sweep["f_opt_d"]
        f_span = sweep["f_span"]
        pout_f = sweep["pout_W"]
        eta_f = sweep["eta_pct"]

        self.ax_f_pout.clear()
        self.ax_f_eta.clear()
        apply_publication_theme(self.fig_freq)

        for ax in (self.ax_f_pout, self.ax_f_eta):
            ax.set_xlim(f_span[0], f_span[-1])
        self.ax_f_eta.set_ylim(0, 105)

        self.ax_f_pout.plot(f_span, pout_f, color="#ea580c", lw=2.6, label="$P_{\\mathrm{вых}}(f)$")
        self.ax_f_pout.fill_between(f_span, pout_f, color="#ea580c", alpha=0.15)
        self.ax_f_pout.axvline(results["f0_kHz"], color="#64748b", ls="--", lw=1.6, label=f"$f_0 = {results['f0_kHz']:.0f}$ кГц")
        self.ax_f_pout.axvline(f_opt_d, color="#16a34a", ls=":", lw=2.0, label=f"$f_{{опт}} = {f_opt_d:.1f}$ кГц")
        self.ax_f_pout.set_title(
            f"АЧХ мощности нагрузки ($d = {d_eff:.0f}$ мм, $k = {kd:.3f}$)",
            fontsize=12,
            fontweight="bold",
            color="#0f172a",
            pad=6,
        )
        self.ax_f_pout.set_xlabel("Частота $f$ [кГц]", fontsize=11, fontweight="bold", color="#334155")
        self.ax_f_pout.set_ylabel("Мощность $P_{\\mathrm{вых}}$ [Вт]", fontsize=11, fontweight="bold", color="#1e293b")
        self.ax_f_pout.legend(fontsize=10, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        self.ax_f_eta.plot(f_span, eta_f, color="#0284c7", lw=2.6, label="$\\eta(f)$")
        self.ax_f_eta.fill_between(f_span, eta_f, color="#0284c7", alpha=0.15)
        self.ax_f_eta.axvline(results["f0_kHz"], color="#64748b", ls="--", lw=1.6, label=f"$f_0 = {results['f0_kHz']:.0f}$ кГц")
        self.ax_f_eta.axvline(f_opt_d, color="#16a34a", ls=":", lw=2.0, label=f"$f_{{опт}} = {f_opt_d:.1f}$ кГц")
        self.ax_f_eta.set_title(
            f"АЧХ коэффициента полезного действия $\\eta(f)$ ($d = {d_eff:.0f}$ мм)",
            fontsize=12,
            fontweight="bold",
            color="#0f172a",
            pad=6,
        )
        self.ax_f_eta.set_xlabel("Частота $f$ [кГц]", fontsize=11, fontweight="bold", color="#334155")
        self.ax_f_eta.set_ylabel("КПД $\\eta$ [\\%]", fontsize=11, fontweight="bold", color="#1e293b")
        self.ax_f_eta.legend(fontsize=10, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        self.fig_freq.tight_layout(pad=2.0)
        self.canvas_freq.draw_idle()

    def cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def close(self) -> None:
        self.cancel_pending()
        if self.fig_freq is not None:
            self.fig_freq.clear()
