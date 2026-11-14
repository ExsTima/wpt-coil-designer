"""
Tab 6: 3D magnetic field streamlines and vector slice visualization.
"""

from typing import Any, Callable, Dict, Optional, Tuple
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import mpl_toolkits.mplot3d  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Line3DCollection
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core import (
    FERRITE_OVERHANG_M,
    Field3DInterpolator,
    calc_inductance,
    calc_mutual_inductance_fast,
    find_peak_phase_currents,
    min_coil_gap_m,
    solve_ss_wpt_circuit,
    trace_streamlines_batch_3d,
    winding_sources,
)
from ..theme import ACCENT_PRIMARY, BG_MUTED, BG_WINDOW, FONTS, TEXT_MAIN


def _winding_key(w) -> Tuple[float, float, int, float, int]:
    return (w.D_out_mm, w.D_in_mm, w.N, w.d_strand_mm, w.n_strands)


class Field3DTab:
    """Вкладка 6: 3D-визуализация катушек, ферритовых экранов и силовых трубок поля."""

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
        self.fig_3d = None
        self.ax_3d = None
        self.canvas_3d: Optional[FigureCanvasTkAgg] = None
        self._interp_cache: Dict[Tuple[Any, ...], Field3DInterpolator] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        ctrl = ttk.Frame(self.parent, padding=(8, 4))
        ctrl.pack(fill="x")

        row1 = ttk.Frame(ctrl)
        row1.pack(fill="x", pady=(0, 3))

        tk.Label(row1, text="Зазор z:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(2, 2))
        self.var_3d_d_val = tk.StringVar(value="12 мм")
        self.slider_3d_d = tk.Scale(
            row1,
            from_=4,
            to=35,
            orient="horizontal",
            length=75,
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
        self.slider_3d_d.set(12)
        self.slider_3d_d.pack(side="left", padx=2)
        tk.Label(
            row1, textvariable=self.var_3d_d_val, font=FONTS["mono_bold"], fg=ACCENT_PRIMARY, bg=BG_WINDOW, width=5
        ).pack(side="left", padx=(1, 8))

        tk.Label(row1, text="Смещение Δx:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(4, 2))
        self.var_3d_dx_val = tk.StringVar(value="0 мм")
        self.slider_3d_dx = tk.Scale(
            row1,
            from_=-20,
            to=20,
            orient="horizontal",
            length=75,
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
        self.slider_3d_dx.set(0)
        self.slider_3d_dx.pack(side="left", padx=2)
        tk.Label(
            row1, textvariable=self.var_3d_dx_val, font=FONTS["mono_bold"], fg=ACCENT_PRIMARY, bg=BG_WINDOW, width=5
        ).pack(side="left", padx=(1, 8))

        tk.Label(row1, text="Зум:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(4, 2))
        self.var_3d_zm_val = tk.StringVar(value="1.2x")
        self.slider_3d_zoom = tk.Scale(
            row1,
            from_=0.5,
            to=2.5,
            orient="horizontal",
            length=65,
            resolution=0.1,
            showvalue=False,
            font=FONTS["caption"],
            bg=BG_WINDOW,
            fg=TEXT_MAIN,
            activebackground=ACCENT_PRIMARY,
            troughcolor=BG_MUTED,
            bd=0,
            highlightthickness=0,
            command=self._on_zoom_slider_change,
        )
        self.slider_3d_zoom.set(1.2)
        self.slider_3d_zoom.pack(side="left", padx=2)
        tk.Label(
            row1, textvariable=self.var_3d_zm_val, font=FONTS["mono_bold"], fg=ACCENT_PRIMARY, bg=BG_WINDOW, width=5
        ).pack(side="left", padx=(1, 12))

        tk.Label(row1, text="Ракурс:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(4, 2))
        ttk.Button(row1, text="Изометрия", width=10, command=lambda: self.set_view(24, -45, 1.2)).pack(side="left", padx=2)
        ttk.Button(row1, text="Вид X-Z", width=8, command=lambda: self.set_view(0, -90, 1.25)).pack(side="left", padx=2)
        ttk.Button(row1, text="Вид X-Y", width=8, command=lambda: self.set_view(90, -90, 1.25)).pack(side="left", padx=2)

        row2 = ttk.Frame(ctrl)
        row2.pack(fill="x", pady=(2, 0))

        tk.Label(row2, text="Режим 3D:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_WINDOW).pack(side="left", padx=(2, 4))
        self.coord_3d_var = tk.StringVar(value="3D силовые линии (Streamlines)")
        cmb_coord = ttk.Combobox(
            row2,
            textvariable=self.coord_3d_var,
            values=["3D силовые линии (Streamlines)", "Векторное поле (Срез Y=0)", "Комбинированный вид"],
            state="readonly",
            width=30,
            font=FONTS["body"],
        )
        cmb_coord.pack(side="left", padx=2)
        cmb_coord.bind("<<ComboboxSelected>>", lambda _e: self._render_current())

        ttk.Button(row2, text="Сохранить 3D-снимок (PNG)", command=self.save_snapshot).pack(side="right", padx=2)

        self._plot_host = ttk.Frame(self.parent)
        self._plot_host.pack(fill=tk.BOTH, expand=True)

    def _ensure_canvas(self) -> None:
        if self.canvas_3d is not None:
            return
        self.fig_3d = Figure(figsize=(9.5, 7.2))
        self.fig_3d.patch.set_facecolor("#ffffff")
        self.ax_3d = self.fig_3d.add_subplot(111, projection="3d")
        self.fig_3d.subplots_adjust(left=0.02, right=0.98, bottom=0.05, top=0.88)

        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, master=self._plot_host)
        self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas_3d.mpl_connect("scroll_event", self.on_scroll)

    def _on_d_slider_change(self, val: str) -> None:
        self.var_3d_d_val.set(f"{int(float(val))} мм")
        if self._get_results() is None:
            return
        self.cancel_pending()
        self._after_id = self.root.after(80, self._render_and_clean)

    def _on_dx_slider_change(self, val: str) -> None:
        self.var_3d_dx_val.set(f"{int(float(val))} мм")
        if self._get_results() is None:
            return
        self.cancel_pending()
        self._after_id = self.root.after(80, self._render_and_clean)

    def _on_zoom_slider_change(self, val: str) -> None:
        self.var_3d_zm_val.set(f"{float(val):.1f}x")
        if self._get_results() is not None and self.ax_3d is not None:
            self.apply_zoom()

    def _render_and_clean(self) -> None:
        self._after_id = None
        results = self._get_results()
        if not results:
            return
        self.render(results)
        self._on_mark_clean()

    def _render_current(self) -> None:
        results = self._get_results()
        if results:
            self.render(results)

    def set_view(self, elev: float, azim: float, zoom_val: Optional[float] = None) -> None:
        if self.ax_3d is None:
            return
        self.ax_3d.view_init(elev=elev, azim=azim)
        if zoom_val is not None:
            self.slider_3d_zoom.set(zoom_val)
        self.apply_zoom()

    def on_scroll(self, event) -> None:
        if self.ax_3d is None:
            return
        curr = float(self.slider_3d_zoom.get())
        if event.button == "up":
            new_z = min(2.5, curr + 0.15)
        elif event.button == "down":
            new_z = max(0.5, curr - 0.15)
        else:
            return
        self.slider_3d_zoom.set(round(new_z, 2))
        self.apply_zoom()

    def apply_zoom(self) -> None:
        results = self._get_results()
        if not results or self.ax_3d is None:
            return
        zoom = float(self.slider_3d_zoom.get())
        r_max = max(results["tx_Dout"], results["rx_Dout"]) / 2.0
        dist_mm = float(self.slider_3d_d.get())
        dx_mm = float(self.slider_3d_dx.get())
        span = (r_max * 1.25 + abs(dx_mm) * 0.5) / zoom
        z_mid = dist_mm / 2.0
        z_half = (max(dist_mm + 10.0, 20.0) / 2.0) / zoom

        self.ax_3d.set_xlim([-span, span])
        self.ax_3d.set_ylim([-span, span])
        self.ax_3d.set_zlim([z_mid - z_half, z_mid + z_half])
        try:
            self.ax_3d.set_box_aspect((1.0, 1.0, 0.72))
        except Exception:
            pass
        self.canvas_3d.draw_idle()

    def render(self, results: Dict[str, Any]) -> None:
        if not results:
            return
        self._ensure_canvas()
        elev = getattr(self.ax_3d, "elev", 20)
        azim = getattr(self.ax_3d, "azim", -55)
        self.ax_3d.clear()

        lay_tx, lay_rx = results["lay_tx"], results["lay_rx"]
        d_min_mm = float(np.ceil(min_coil_gap_m(lay_tx, lay_rx) * 1e4) / 10.0)
        dist_mm = max(float(self.slider_3d_d.get()), d_min_mm)
        dx_mm = float(self.slider_3d_dx.get())
        d_m = dist_mm * 1e-3
        dx_m = dx_mm * 1e-3

        R_tx_out, N_tx = results["tx_Dout"] / 2.0, results["tx_N"]
        R_rx_out = results["rx_Dout"] / 2.0
        H1_mm = lay_tx.H_m * 1000.0
        H2_mm = lay_rx.H_m * 1000.0
        ov_mm = FERRITE_OVERHANG_M * 1000.0

        phi_c = np.linspace(0.0, 2.0 * np.pi, 90)
        cos_p, sin_p = np.cos(phi_c), np.sin(phi_c)
        tx_segs = [
            np.column_stack((rc * cos_p, rc * sin_p, np.full_like(phi_c, zc)))
            for rc, zc in zip(lay_tx.r * 1000.0, lay_tx.z * 1000.0, strict=True)
        ]
        if tx_segs:
            self.ax_3d.add_collection3d(Line3DCollection(tx_segs, colors="#d97706", linewidths=2.2), autolim=False)
        self.ax_3d.plot([], [], [], color="#d97706", lw=2.2, label=f"Обмотка Tx ({lay_tx.layers} сл., N={N_tx})")

        rx_segs = [
            np.column_stack((dx_mm + rc * cos_p, rc * sin_p, np.full_like(phi_c, dist_mm - zc)))
            for rc, zc in zip(lay_rx.r * 1000.0, lay_rx.z * 1000.0, strict=True)
        ]
        if rx_segs:
            self.ax_3d.add_collection3d(Line3DCollection(rx_segs, colors="#0284c7", linewidths=2.2), autolim=False)
        self.ax_3d.plot([], [], [], color="#0284c7", lw=2.2, label=f"Обмотка Rx (z={dist_mm:.1f} мм, Δx={dx_mm:.0f} мм)")

        # Ferrite disks with distinct meshes for Tx and Rx radii
        r_fer_tx = R_tx_out + ov_mm
        r_fer_rx = R_rx_out + ov_mm
        r_p_tx, p_p_tx = np.meshgrid(np.linspace(0, r_fer_tx, 12), np.linspace(0, 2 * np.pi, 24))
        xf_tx, yf_tx = r_p_tx * np.cos(p_p_tx), r_p_tx * np.sin(p_p_tx)
        r_p_rx, p_p_rx = np.meshgrid(np.linspace(0, r_fer_rx, 12), np.linspace(0, 2 * np.pi, 24))
        xf_rx, yf_rx = r_p_rx * np.cos(p_p_rx), r_p_rx * np.sin(p_p_rx)

        self.ax_3d.plot_surface(xf_tx, yf_tx, np.full_like(xf_tx, -H1_mm - 1.8), color="#334155", alpha=0.30, shade=True)
        self.ax_3d.plot_surface(
            dx_mm + xf_rx, yf_rx, np.full_like(xf_rx, dist_mm + H2_mm + 1.8), color="#334155", alpha=0.30, shade=True
        )

        phi_f = np.linspace(0, 2.0 * np.pi, 80)
        self.ax_3d.plot(
            r_fer_tx * np.cos(phi_f),
            r_fer_tx * np.sin(phi_f),
            np.full_like(phi_f, -H1_mm - 1.8),
            color="#1e293b",
            ls="--",
            lw=1.2,
            label="Феррит MnZn",
        )
        self.ax_3d.plot(
            dx_mm + r_fer_rx * np.cos(phi_f),
            r_fer_rx * np.sin(phi_f),
            np.full_like(phi_f, dist_mm + H2_mm + 1.8),
            color="#1e293b",
            ls="--",
            lw=1.2,
        )

        L1_d = calc_inductance(lay_tx, lay_rx, d_m)
        L2_d = L1_d if lay_tx.same_geometry(lay_rx) else calc_inductance(lay_rx, lay_tx, d_m)
        M_3d = calc_mutual_inductance_fast(dist_mm, lay_tx, lay_rx, dx_mm)
        sol_3d = solve_ss_wpt_circuit(
            results["V_bus"],
            results["f_drive_kHz"],
            L1_d,
            results["C1"],
            results["R1_ac"],
            L2_d,
            results["C2"],
            results["R2_ac"],
            M_3d,
            results["R_load"],
            results["Rds_mOhm"],
        )
        I1c, I2c = sol_3d["I1_c"], sol_3d["I2_c"]

        src_tx = winding_sources(lay_tx, lay_rx, d_m, "tx")
        src_rx = winding_sources(lay_tx, lay_rx, d_m, "rx")
        I1_eff, I2_eff = find_peak_phase_currents(lay_tx, lay_rx, d_m, src_tx, src_rx, I1c, I2c)

        cache_key = (_winding_key(lay_tx), _winding_key(lay_rx), round(dist_mm, 3))
        interp = self._interp_cache.get(cache_key)
        if interp is None:
            if len(self._interp_cache) >= 12:
                self._interp_cache.clear()
            interp = Field3DInterpolator(
                lay_tx, lay_rx, d_m, dx_m, I1_eff, I2_eff, grid_size=45, src_tx=src_tx, src_rx=src_rx
            )
            self._interp_cache[cache_key] = interp
        else:
            interp.set_state(dx_m, I1_eff, I2_eff)

        mode = self.coord_3d_var.get()
        show_lines = "Линии" in mode or "силовые" in mode or "Streamlines" in mode or "Комбинированный" in mode
        show_quiver = "Векторное" in mode or "Срез" in mode or "Комбинированный" in mode

        r_max_mm = max(R_tx_out, R_rx_out)
        r_max_m = r_max_mm * 1e-3

        if show_lines:
            z_seed = d_m / 2.0
            radii_seed = [frac * r_max_m for frac in (0.12, 0.28, 0.48, 0.72, 0.96)]
            ds_m = r_max_m * 0.032
            xy_bound_m = r_max_m * 2.1 + abs(dx_m)
            z_bound_lo = -max(0.013, lay_tx.H_m + 0.010)
            z_bound_hi = d_m + max(0.017, lay_rx.H_m + 0.012)
            palette = ["#0284c7", "#2563eb", "#7c3aed", "#c026d3", "#ea580c"]

            phis = np.linspace(0, 2 * np.pi, 8, endpoint=False)
            seeds = []
            line_colors = []
            for idx_r, r_s in enumerate(radii_seed):
                line_col = palette[idx_r % len(palette)]
                for phi_s in phis:
                    seeds.append([r_s * np.cos(phi_s) + 0.5 * dx_m, r_s * np.sin(phi_s), z_seed])
                    line_colors.append(line_col)

            seeds_arr = np.asarray(seeds, dtype=float)
            fwds = trace_streamlines_batch_3d(
                interp, seeds_arr, ds=ds_m, n_steps=90, direction=1, xy_bound_m=xy_bound_m, z_min_m=z_bound_lo, z_max_m=z_bound_hi
            )
            bwds = trace_streamlines_batch_3d(
                interp, seeds_arr, ds=ds_m, n_steps=90, direction=-1, xy_bound_m=xy_bound_m, z_min_m=z_bound_lo, z_max_m=z_bound_hi
            )

            stream_segs = []
            ax_x, ax_y, ax_z, au, av, aw, arrow_cols = [], [], [], [], [], [], []
            for fwd, bwd, col in zip(fwds, bwds, line_colors, strict=True):
                full_mm = np.vstack([bwd[::-1], fwd[1:]]) * 1000.0
                stream_segs.append(full_mm)
                mid_i = len(bwd) - 1
                if 0 <= mid_i < len(full_mm) - 2:
                    p_mid = full_mm[mid_i]
                    d_vec = full_mm[mid_i + 2] - p_mid
                    ax_x.append(p_mid[0])
                    ax_y.append(p_mid[1])
                    ax_z.append(p_mid[2])
                    au.append(d_vec[0])
                    av.append(d_vec[1])
                    aw.append(d_vec[2])
                    arrow_cols.append(col)

            if stream_segs:
                self.ax_3d.add_collection3d(
                    Line3DCollection(stream_segs, colors=line_colors, linewidths=1.4, alpha=0.82),
                    autolim=False,
                )
            if ax_x:
                self.ax_3d.quiver(
                    ax_x,
                    ax_y,
                    ax_z,
                    au,
                    av,
                    aw,
                    length=max(2.8, r_max_mm * 0.112),
                    normalize=True,
                    color=arrow_cols,
                    arrow_length_ratio=0.5,
                    lw=1.4,
                )

        if show_quiver:
            x_pts = np.linspace(-1.4 * r_max_mm, 1.4 * r_max_mm + dx_mm, 15) * 1e-3
            z_pts = np.linspace(-H1_mm - 2.0, dist_mm + H2_mm + 4.0, 11) * 1e-3
            Xq, Zq = np.meshgrid(x_pts, z_pts)
            Yq = np.zeros_like(Xq)

            b_arr = interp.eval_B_batch(Xq.ravel(), Yq.ravel(), Zq.ravel())
            U = b_arr[:, 0].reshape(Xq.shape)
            V = b_arr[:, 1].reshape(Xq.shape)
            W = b_arr[:, 2].reshape(Xq.shape)
            B_mag = np.sqrt(U**2 + V**2 + W**2) + 1e-12
            q_scale = max(3.6, r_max_mm * 0.144)

            self.ax_3d.quiver(
                Xq * 1000.0,
                Yq * 1000.0,
                Zq * 1000.0,
                (U / B_mag) * q_scale,
                (V / B_mag) * q_scale,
                (W / B_mag) * q_scale,
                length=1.0,
                normalize=False,
                color="#1e293b",
                alpha=0.88,
                arrow_length_ratio=0.35,
                lw=1.2,
            )

        self.ax_3d.set_xlabel("Координата $x$ [мм]", fontsize=10.5, fontweight="bold", labelpad=7)
        self.ax_3d.set_ylabel("Координата $y$ [мм]", fontsize=10.5, fontweight="bold", labelpad=7)
        self.ax_3d.set_zlabel("Высота $z$ [мм]", fontsize=10.5, fontweight="bold", labelpad=7)
        self.ax_3d.tick_params(labelsize=9.5)
        self.ax_3d.set_title(
            f"3D-модель вихревого поля $\\mathbf{{B}}$  [$d = {dist_mm:.1f}$ мм,  $\\Delta x = {dx_mm:.1f}$ мм]\nСиловые трубки магнитного потока $\\Psi$",
            fontsize=11,
            fontweight="bold",
            color="#0f172a",
            pad=4,
        )
        self.ax_3d.legend(loc="upper right", fontsize=9.5)
        self.ax_3d.view_init(elev=elev, azim=azim)
        self.apply_zoom()

    def save_snapshot(self) -> None:
        if self.fig_3d is None or self._get_results() is None:
            return
        fn = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")])
        if fn:
            self.fig_3d.savefig(fn, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Экспорт", "3D-снимок модели сохранен.")

    def cancel_pending(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def close(self) -> None:
        self.cancel_pending()
        if self.fig_3d is not None:
            self.fig_3d.clear()
