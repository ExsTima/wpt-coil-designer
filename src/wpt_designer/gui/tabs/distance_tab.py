"""
Tab 3: Distance sweep charts (efficiency, coupling, output power, and losses vs gap d).
"""

from typing import Any, Callable, Dict, Optional
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import filedialog, messagebox, ttk

from ...core.simulation import compute_distance_sweep
from ..theme import apply_publication_theme


class DistanceSweepTab:
    """Вкладка 3: Зависимости характеристик WPT от осевого зазора d."""

    def __init__(
        self,
        parent: ttk.Frame,
        attach_help: Callable[..., None],
        on_export_csv: Callable[[], None],
    ):
        self.parent = parent
        self.attach_help = attach_help
        self._on_export_csv = on_export_csv
        self.fig = None
        self.axes = None
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._plot_host = ttk.Frame(self.parent)
        self._plot_host.pack(fill="both", expand=True)

        ctrl = ttk.Frame(self.parent, padding=8)
        ctrl.pack(fill="x")
        btn_box = ttk.Frame(ctrl)
        btn_box.pack(anchor="center")

        b_save_g = ttk.Button(
            btn_box,
            text="Экспорт графиков (PNG / PDF 300 DPI)",
            command=self.save_graphs,
        )
        b_save_g.pack(side="left", padx=10, ipadx=6, ipady=3)
        self.attach_help(b_save_g, "Сохранить четверку графиков в файл публикационного разрешения.")

        b_save_t = ttk.Button(
            btn_box,
            text="Экспорт таблицы данных (CSV)",
            command=self._on_export_csv,
        )
        b_save_t.pack(side="left", padx=10, ipadx=6, ipady=3)

    def _ensure_canvas(self) -> None:
        if self.canvas is not None:
            return
        self.fig = Figure(figsize=(8.5, 5.8))
        self.axes = self.fig.subplots(2, 2)
        apply_publication_theme(self.fig)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self._plot_host)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def render(self, results: Dict[str, Any], auto_track: bool) -> None:
        if not results:
            return
        self._ensure_canvas()
        for ax in self.axes.flat:
            ax.clear()
        apply_publication_theme(self.fig)

        sweep = compute_distance_sweep(results, auto_track=auto_track)
        d_range = sweep["d_mm"]
        eta_list = sweep["eta_pct"]
        k_list = sweep["k"]
        pout_list = sweep["pout_W"]
        ploss_list = sweep["ploss_W"]

        curr_d = results["dist_mm"]
        curr_eta = results["circuit"]["eta"] * 100.0
        curr_k = results["k"]
        curr_pout = results["circuit"]["P_out"]
        curr_ploss = results["circuit"]["P_cu"] + results["circuit"]["P_mos"]

        for ax in self.axes.flat:
            ax.set_xlabel("$d$ [мм]", fontsize=11, fontweight="bold", color="#334155")
            ax.set_xlim(d_range[0], d_range[-1])

        # 1. КПД
        self.axes[0, 0].plot(d_range, eta_list, color="#0284c7", lw=2.6)
        self.axes[0, 0].fill_between(d_range, eta_list, color="#0284c7", alpha=0.15)
        self.axes[0, 0].axvline(curr_d, color="#ef4444", ls="--", lw=1.6, alpha=0.9, label=f"$d = {curr_d:.1f}$ мм")
        self.axes[0, 0].plot(curr_d, curr_eta, "o", color="#0284c7", ms=6, label=f"$\\eta = {curr_eta:.1f}\\%$")
        self.axes[0, 0].set_ylabel("КПД $\\eta$ [\\%]", fontsize=11, fontweight="bold", color="#1e293b")
        self.axes[0, 0].set_title("Зависимость КПД от зазора $\\eta(d)$", fontsize=12, fontweight="bold", color="#0f172a", pad=6)
        self.axes[0, 0].legend(fontsize=9.5, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        # 2. Связь k
        self.axes[0, 1].plot(d_range, k_list, color="#16a34a", lw=2.6, label="$k(d)$")
        self.axes[0, 1].fill_between(d_range, k_list, color="#16a34a", alpha=0.15)
        self.axes[0, 1].axhline(results["k_crit"], color="#64748b", ls=":", lw=1.8, label=f"$k_{{кр}} = {results['k_crit']:.3f}$")
        self.axes[0, 1].axvline(curr_d, color="#ef4444", ls="--", lw=1.6, alpha=0.9)
        self.axes[0, 1].plot(curr_d, curr_k, "o", color="#16a34a", ms=6, label=f"$k = {curr_k:.3f}$")
        self.axes[0, 1].set_ylabel("Связь $k$", fontsize=11, fontweight="bold", color="#1e293b")
        self.axes[0, 1].set_title("Коэффициент магнитной связи $k(d)$", fontsize=12, fontweight="bold", color="#0f172a", pad=6)
        self.axes[0, 1].legend(fontsize=9.5, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        # 3. Мощность
        self.axes[1, 0].plot(d_range, pout_list, color="#ea580c", lw=2.6)
        self.axes[1, 0].fill_between(d_range, pout_list, color="#ea580c", alpha=0.15)
        self.axes[1, 0].axvline(curr_d, color="#ef4444", ls="--", lw=1.6, alpha=0.9, label=f"$d = {curr_d:.1f}$ мм")
        self.axes[1, 0].plot(curr_d, curr_pout, "o", color="#ea580c", ms=6, label=f"$P_{{вых}} = {curr_pout:.2f}$ Вт")
        self.axes[1, 0].set_ylabel("Мощность $P_{\\mathrm{вых}}$ [Вт]", fontsize=11, fontweight="bold", color="#1e293b")
        self.axes[1, 0].set_title("Полезная мощность нагрузки $P_{\\mathrm{вых}}(d)$", fontsize=12, fontweight="bold", color="#0f172a", pad=6)
        self.axes[1, 0].legend(fontsize=9.5, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        # 4. Потери
        self.axes[1, 1].plot(d_range, ploss_list, color="#dc2626", lw=2.6)
        self.axes[1, 1].fill_between(d_range, ploss_list, color="#dc2626", alpha=0.15)
        self.axes[1, 1].axvline(curr_d, color="#ef4444", ls="--", lw=1.6, alpha=0.9, label=f"$d = {curr_d:.1f}$ мм")
        self.axes[1, 1].plot(curr_d, curr_ploss, "o", color="#dc2626", ms=6, label=f"$P_{{пот}} = {curr_ploss:.2f}$ Вт")
        self.axes[1, 1].set_ylabel("Мощность потерь $P_{\\mathrm{пот}}$ [Вт]", fontsize=11, fontweight="bold", color="#1e293b")
        self.axes[1, 1].set_title("Суммарные потери в системе $P_{\\mathrm{пот}}(d)$", fontsize=12, fontweight="bold", color="#0f172a", pad=6)
        self.axes[1, 1].legend(fontsize=9.5, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right")

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw_idle()

    def save_graphs(self) -> None:
        if self.fig is None:
            return
        fn = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")])
        if fn:
            self.fig.savefig(fn, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Экспорт", "Графики успешно сохранены в файл высокого разрешения (300 DPI).")

    def close(self) -> None:
        if self.fig is not None:
            self.fig.clear()
