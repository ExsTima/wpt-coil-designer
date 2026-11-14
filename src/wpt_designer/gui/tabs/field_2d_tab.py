"""
Tab 5: 2D magnetic field contour/streamlines and interactive virtual Gaussmeter probe.
"""

from typing import Any, Callable, Dict, Optional, Tuple
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from scipy.interpolate import RectBivariateSpline
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core import (
    FERRITE_OVERHANG_M,
    AxisymmetricField2D,
    calc_coupling,
    calc_inductance,
    calc_mutual_inductance_fast,
    ferrite_shield_mask,
    find_peak_phase_currents,
    min_coil_gap_m,
    phasor_field_magnitude,
    solve_ss_wpt_circuit,
    winding_sources,
)
from ..theme import ACCENT_PRIMARY, BG_MUTED, BG_WINDOW, FONTS, TEXT_MAIN, apply_publication_theme


def _winding_key(w) -> Tuple[float, float, int, float, int]:
    return (w.D_out_mm, w.D_in_mm, w.N, w.d_strand_mm, w.n_strands)


class Field2DTab:
    """Вкладка 5: 2D-карта магнитного поля |B(x, z)|, линии потока Psi и зонд-тесламетр."""

    def __init__(
        self,
        parent: ttk.Frame,
        root: tk.Tk,
        status_var: tk.StringVar,
        get_results: Callable[[], Optional[Dict[str, Any]]],
        on_mark_clean: Callable[[], None],
    ):
        self.parent = parent
        self.root = root
        self.status_var = status_var
        self._get_results = get_results
        self._on_mark_clean = on_mark_clean

        self._after_id: Optional[str] = None
        self.fig_2d = None
        self.ax_2d = None
        self.canvas_2d: Optional[FigureCanvasTkAgg] = None
        self.cbar_2d = None
        self.spline_B_2d: Optional[RectBivariateSpline] = None
        self._field_2d_cache: Dict[Tuple[Any, ...], AxisymmetricField2D] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        ctrl = ttk.Frame(self.parent, padding=8)
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Зазор d:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(6, 4))
        self.var_2d_d_val = tk.StringVar(value="10 мм")
        self.slider_2d_d = tk.Scale(
            ctrl,
            from_=2,
            to=40,
            orient="horizontal",
            length=150,
            resolution=1,
            showvalue=False,
            font=FONTS["caption"],
            bg=BG_WINDOW,
            fg=TEXT_MAIN,
            activebackground=ACCENT_PRIMARY,
            troughcolor=BG_MUTED,
            bd=0,
            highlightthickness=0,
            command=self._on_d_slider_change,
        )
        self.slider_2d_d.set(10)
        self.slider_2d_d.pack(side="left", padx=4)
        tk.Label(
            ctrl, textvariable=self.var_2d_d_val, font=FONTS["mono_bold"], fg=ACCENT_PRIMARY, bg=BG_WINDOW, width=5
        ).pack(side="left", padx=(1, 14))

        tk.Label(ctrl, text="Смещение Rx Δx:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(
            side="left", padx=(0, 4)
        )
        self.var_2d_dx_val = tk.StringVar(value="0 мм")
        self.slider_2d_dx = tk.Scale(
            ctrl,
            from_=-25,
            to=25,
            orient="horizontal",
            length=150,
            resolution=1,
            showvalue=False,
            font=FONTS["caption"],
            bg=BG_WINDOW,
            fg=TEXT_MAIN,
            activebackground=ACCENT_PRIMARY,
            troughcolor=BG_MUTED,
            bd=0,
            highlightthickness=0,
            command=self._on_dx_slider_change,
        )
        self.slider_2d_dx.set(0)
        self.slider_2d_dx.pack(side="left", padx=4)
        tk.Label(
            ctrl, textvariable=self.var_2d_dx_val, font=FONTS["mono_bold"], fg=ACCENT_PRIMARY, bg=BG_WINDOW, width=5
        ).pack(side="left", padx=(1, 10))

        ttk.Button(ctrl, text="Сохранить 2D-карту (PNG)", command=self.save_snapshot).pack(side="right", padx=10)

        self._plot_host = ttk.Frame(self.parent)
        self._plot_host.pack(fill=tk.BOTH, expand=True)

    def _ensure_canvas(self) -> None:
        if self.canvas_2d is not None:
            return
        self.fig_2d = Figure(figsize=(7.5, 5))
        self.ax_2d = self.fig_2d.add_subplot(111)
        apply_publication_theme(self.fig_2d)
        self.canvas_2d = FigureCanvasTkAgg(self.fig_2d, master=self._plot_host)
        self.canvas_2d.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas_2d.mpl_connect("motion_notify_event", self.on_mouse_motion)

    def _on_d_slider_change(self, val: str) -> None:
        self.var_2d_d_val.set(f"{int(float(val))} мм")
        if self._get_results() is None:
            return
        self.cancel_pending()
        self._after_id = self.root.after(90, self._render_and_clean)

    def _on_dx_slider_change(self, val: str) -> None:
        self.var_2d_dx_val.set(f"{int(float(val))} мм")
        if self._get_results() is None:
            return
        self.cancel_pending()
        self._after_id = self.root.after(90, self._render_and_clean)

    def _render_and_clean(self) -> None:
        self._after_id = None
        results = self._get_results()
        if not results:
            return
        self.render(results)
        self._on_mark_clean()

    def on_mouse_motion(self, event) -> None:
        """Интерактивный зонд: мгновенно отображает (x, z) и индукцию |B| под курсором мыши."""
        if not event.inaxes or self._get_results() is None or self.spline_B_2d is None:
            return
        x_mm, z_mm = event.xdata, event.ydata
        if x_mm is None or z_mm is None:
            return
        try:
            b_val_mT = float(self.spline_B_2d(x_mm, z_mm)[0, 0])
            b_str = f"{b_val_mT:.2f} мТл" if b_val_mT >= 0.01 else f"{b_val_mT*1000.0:.1f} мкТл"
            self.status_var.set(f"📍 Зонд магнитного поля: x = {x_mm:+.1f} мм,  z = {z_mm:.1f} мм  ⟹  |B| = {b_str}")
        except Exception:
            pass

    def render(self, results: Dict[str, Any]) -> None:
        if not results:
            return
        self._ensure_canvas()
        self.ax_2d.clear()
        apply_publication_theme(self.fig_2d)

        lay_tx, lay_rx = results["lay_tx"], results["lay_rx"]
        d_min_mm = float(np.ceil(min_coil_gap_m(lay_tx, lay_rx) * 1e4) / 10.0)
        d_mm = max(float(self.slider_2d_d.get()), d_min_mm)
        dx_mm = float(self.slider_2d_dx.get())
        d_val_m = d_mm / 1000.0
        dx_val_m = dx_mm / 1000.0
        H1_mm = lay_tx.H_m * 1000.0
        H2_mm = lay_rx.H_m * 1000.0
        ov_mm = FERRITE_OVERHANG_M * 1000.0
        t_fer_mm = 2.0

        max_coil_out_mm = max(lay_tx.D_out_mm, lay_rx.D_out_mm)
        x_ext = max(0.055, 1.35 * max_coil_out_mm / 2000.0)
        x = np.linspace(-x_ext, x_ext, 130)
        z = np.linspace(-max(0.016, lay_tx.H_m + 0.012), d_val_m + max(0.025, lay_rx.H_m + 0.012), 130)
        X, Z = np.meshgrid(x, z)

        L1_d = calc_inductance(lay_tx, lay_rx, d_val_m)
        L2_d = L1_d if lay_tx.same_geometry(lay_rx) else calc_inductance(lay_rx, lay_tx, d_val_m)
        M_curr = calc_mutual_inductance_fast(d_mm, lay_tx, lay_rx, dx_mm)
        k_curr = calc_coupling(M_curr, L1_d, L2_d)
        sol_2d = solve_ss_wpt_circuit(
            results["V_bus"],
            results["f_drive_kHz"],
            L1_d,
            results["C1"],
            results["R1_ac"],
            L2_d,
            results["C2"],
            results["R2_ac"],
            M_curr,
            results["R_load"],
            results["Rds_mOhm"],
        )
        I1c, I2c = sol_2d["I1_c"], sol_2d["I2_c"]

        rho_max_m = x_ext + max(0.030, abs(dx_val_m) + 0.005)
        cache_key = (_winding_key(lay_tx), _winding_key(lay_rx), round(d_mm, 3), round(rho_max_m, 4))
        field_cache = self._field_2d_cache.get(cache_key)
        if field_cache is None:
            if len(self._field_2d_cache) >= 12:
                self._field_2d_cache.clear()
            field_cache = AxisymmetricField2D(lay_tx, lay_rx, d_val_m, rho_max_m=rho_max_m)
            self._field_2d_cache[cache_key] = field_cache

        b_tx, b_rx, psi_tx_unit, psi_rx_unit = field_cache.eval_grid(X, Z, dx_val_m)
        B_mag = phasor_field_magnitude(b_tx, b_rx, I1c, I2c)

        src_tx = winding_sources(lay_tx, lay_rx, d_val_m, "tx")
        src_rx = winding_sources(lay_tx, lay_rx, d_val_m, "rx")
        I1_eff, I2_eff = find_peak_phase_currents(lay_tx, lay_rx, d_val_m, src_tx, src_rx, I1c, I2c)
        Psi_total = I1_eff * psi_tx_unit + I2_eff * psi_rx_unit

        shield_mask = ferrite_shield_mask(Z, d_val_m, lay_tx.H_m, lay_rx.H_m)
        B_mag_mT = np.clip(B_mag * shield_mask * 1000.0, 0.005, 120.0)
        log_B = np.log10(B_mag_mT)

        try:
            self.spline_B_2d = RectBivariateSpline(x * 1000.0, z * 1000.0, B_mag_mT.T)
        except Exception:
            self.spline_B_2d = None

        cf = self.ax_2d.contourf(X * 1000, Z * 1000, log_B, levels=32, cmap="plasma", alpha=0.92)

        psi_max = max(float(Psi_total.max()), 1e-12)
        levels = np.geomspace(psi_max * 0.015, psi_max * 0.94, 24)
        self.ax_2d.contour(X * 1000, Z * 1000, Psi_total, levels=levels, colors="#ffffff", linewidths=0.9, alpha=0.90)

        z_mid_mm = d_mm / 2.0
        arrow_x = (max_coil_out_mm / 2.0) * 1.44
        arrow_dz = max(2.5, d_mm * 0.12)
        arrow_style = dict(arrowstyle="-|>", color="#ffffff", lw=1.8, mutation_scale=14)
        self.ax_2d.annotate("", xy=(0.0, z_mid_mm + arrow_dz), xytext=(0.0, z_mid_mm - arrow_dz), arrowprops=arrow_style, zorder=10)
        self.ax_2d.annotate("", xy=(-arrow_x, z_mid_mm - arrow_dz), xytext=(-arrow_x, z_mid_mm + arrow_dz), arrowprops=arrow_style, zorder=10)
        self.ax_2d.annotate("", xy=(arrow_x, z_mid_mm - arrow_dz), xytext=(arrow_x, z_mid_mm + arrow_dz), arrowprops=arrow_style, zorder=10)

        r_fer_tx = lay_tx.D_out_mm / 2.0 + ov_mm
        r_fer_rx = lay_rx.D_out_mm / 2.0 + ov_mm
        rect_tx = Rectangle(
            (-r_fer_tx, -H1_mm - t_fer_mm),
            2.0 * r_fer_tx,
            t_fer_mm,
            facecolor="#334155",
            edgecolor="#1e293b",
            lw=1.2,
            zorder=6,
            label="Феррит MnZn",
        )
        rect_rx = Rectangle(
            (dx_mm - r_fer_rx, d_mm + H2_mm),
            2.0 * r_fer_rx,
            t_fer_mm,
            facecolor="#334155",
            edgecolor="#1e293b",
            lw=1.2,
            zorder=6,
        )
        self.ax_2d.add_patch(rect_tx)
        self.ax_2d.add_patch(rect_rx)

        self._draw_turns_batch(lay_tx, 0.0, 1.0, "#d97706", "#78350f", offset_z=0.0)
        self._draw_turns_batch(lay_rx, dx_mm, -1.0, "#0284c7", "#0369a1", offset_z=d_mm)

        self.ax_2d.plot([], [], "o", mfc="#d97706", mec="#78350f", ms=8, label=f"Tx ({lay_tx.layers} сл., N={results['tx_N']})")
        self.ax_2d.plot([], [], "o", mfc="#0284c7", mec="#0369a1", ms=8, label=f"Rx (d={d_mm:.0f} мм, Δx={dx_mm:.0f} мм)")

        self.ax_2d.set_aspect("equal", adjustable="box")
        self.ax_2d.set_xlim(-x_ext * 1000, x_ext * 1000)
        self.ax_2d.set_ylim(-H1_mm - t_fer_mm - 4.0, d_mm + H2_mm + t_fer_mm + 4.0)

        self.ax_2d.set_xlabel("Координата $x$ [мм]", fontsize=11, fontweight="bold", color="#1e293b")
        self.ax_2d.set_ylabel("Осевая координата $z$ [мм]", fontsize=11, fontweight="bold", color="#1e293b")
        self.ax_2d.tick_params(colors="#334155", labelsize=10)
        self.ax_2d.set_title(
            f"Индукция $|B(x,z)|$ и силовые линии потока $\\Psi(r,z)$\n[$d = {d_mm:.1f}$ мм,  $k = {k_curr:.3f}$,  $M = {M_curr*1e6:.2f}$ мкГн]",
            fontsize=11.5,
            fontweight="bold",
            color="#0f172a",
            pad=6,
        )
        self.ax_2d.legend(loc="upper right", fontsize=9.5, frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1")

        if self.cbar_2d is None:
            self.cbar_2d = self.fig_2d.colorbar(cf, ax=self.ax_2d, fraction=0.035, pad=0.02)
            self.cbar_2d.set_label("Индукция $|B|$, мТл (log)", fontsize=10, fontweight="bold", color="#1e293b")
            self.cbar_2d.set_ticks([-2, -1, 0, 1, 2])
            self.cbar_2d.set_ticklabels(["0.01", "0.1", "1", "10", "100"])
            self.cbar_2d.ax.tick_params(labelsize=9.5, colors="#334155")
        else:
            self.cbar_2d.update_normal(cf)

        self.fig_2d.subplots_adjust(left=0.12, right=0.86, top=0.89, bottom=0.12)
        self.canvas_2d.draw_idle()

    def _draw_turns_batch(
        self,
        winding,
        dx_mm: float,
        z_sign: float,
        facecolor: str,
        edgecolor: str,
        offset_z: float,
    ) -> None:
        r_wire_mm = 0.5 * winding.D_wire_m * 1000.0
        r_mm = winding.r * 1000.0
        z_mm = offset_z + z_sign * (winding.z * 1000.0)
        patches = []
        dot_x, dot_z = [], []
        cross_x, cross_z = [], []

        for rc, cz in zip(r_mm, z_mm, strict=True):
            cx_neg = dx_mm - rc
            cx_pos = dx_mm + rc
            patches.append(Circle((cx_neg, cz), r_wire_mm))
            patches.append(Circle((cx_pos, cz), r_wire_mm))
            dot_x.append(cx_neg)
            dot_z.append(cz)
            cross_x.append(cx_pos)
            cross_z.append(cz)

        if not patches:
            return
        collection = PatchCollection(patches, facecolor=facecolor, edgecolor=edgecolor, linewidth=0.9, zorder=7)
        self.ax_2d.add_collection(collection)
        self.ax_2d.scatter(dot_x, dot_z, marker=r"$\odot$", s=48, c="#ffffff", edgecolors="none", zorder=8)
        self.ax_2d.scatter(cross_x, cross_z, marker=r"$\otimes$", s=48, c="#ffffff", edgecolors="none", zorder=8)

    def save_snapshot(self) -> None:
        if self.fig_2d is None or self._get_results() is None:
            return
        fn = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")])
        if fn:
            self.fig_2d.savefig(fn, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Экспорт", "2D-карта магнитного поля сохранена.")

    def cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def close(self) -> None:
        self.cancel_pending()
        if self.fig_2d is not None:
            self.fig_2d.clear()
