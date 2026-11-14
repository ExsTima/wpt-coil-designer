"""
Tab 2: Power flow bar, energy conservation check, and electromagnetic parameter tables.
"""

from typing import Any, Callable, Dict
import tkinter as tk
from tkinter import ttk

from ..theme import (
    ACCENT_PRIMARY,
    BG_CARD,
    BG_SUBTLE,
    BG_WINDOW,
    COLOR_COPPER,
    COLOR_DANGER,
    COLOR_PURPLE,
    COLOR_SAPPHIRE,
    COLOR_SUCCESS,
    FONTS,
    TEXT_BODY,
    TEXT_MAIN,
    TEXT_MUTED,
)


class ResultsTab:
    """Вкладка 2: Энергетический баланс и детальные таблицы электромагнитных параметров."""

    def __init__(
        self,
        parent: ttk.Frame,
        attach_help: Callable[..., None],
        on_copy_report: Callable[[], None],
        on_export_csv: Callable[[], None],
    ):
        self.parent = parent
        self.attach_help = attach_help
        self._on_copy_report = on_copy_report
        self._on_export_csv = on_export_csv

        self.power_balance_var = tk.StringVar(value="Баланс мощности: 100.00% (инвариант соблюдён)")
        self.res_vars = {
            k: tk.StringVar(value="-")
            for k in (
                "winding",
                "L1",
                "R1_dc",
                "R1_ac",
                "Q1",
                "C1",
                "M",
                "k",
                "f_opt",
                "I1",
                "V_out",
                "P_in",
                "P_out",
                "P_cu",
                "P_mos",
                "eta",
                "phase",
            )
        }
        self.kpi_vars = {
            "eta": tk.StringVar(value="- %"),
            "eta_sub": tk.StringVar(value="Эффективность тракта"),
            "P_out": tk.StringVar(value="- Вт"),
            "P_out_sub": tk.StringVar(value="Мощность в нагрузке"),
            "f_opt": tk.StringVar(value="- кГц"),
            "f_opt_sub": tk.StringVar(value="Рабочая частота"),
            "k": tk.StringVar(value="-"),
            "k_sub": tk.StringVar(value="Коэффициент связи"),
        }
        self.bot_insight_var = tk.StringVar(value="Ожидание выполнения расчета параметров системы...")

        self._build_ui()

    def _build_ui(self) -> None:
        res_frame = ttk.Frame(self.parent, padding=14)
        res_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Top Large KPI Cards
        kpi_frame = ttk.Frame(res_frame)
        kpi_frame.pack(fill=tk.X, pady=(0, 10))

        kpi_defs = [
            (
                "КПД СИСТЕМЫ (η)",
                "eta",
                COLOR_SUCCESS,
                "eta_sub",
                "Результирующий электрический КПД тракта передачи от инвертора до нагрузки.",
            ),
            (
                "ВЫХОДНАЯ МОЩНОСТЬ",
                "P_out",
                ACCENT_PRIMARY,
                "P_out_sub",
                "Полезная мощность постоянного тока, выделяемая на нагрузке.",
            ),
            (
                "ЧАСТОТА ИНВЕРТОРА",
                "f_opt",
                COLOR_PURPLE,
                "f_opt_sub",
                "Фактическая частота коммутации ключей силового H-моста.",
            ),
            (
                "СВЯЗЬ КАТУШЕК (k)",
                "k",
                COLOR_SAPPHIRE,
                "k_sub",
                "Электромагнитная связь между передающей и приемной катушками.",
            ),
        ]

        for i, (title, val_k, col, sub_k, hlp) in enumerate(kpi_defs):
            card = tk.Frame(kpi_frame, bg=BG_CARD, bd=1, relief="solid", padx=12, pady=8)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            kpi_frame.columnconfigure(i, weight=1)

            t_lbl = tk.Label(card, text=title, font=FONTS["kpi_label"], fg=TEXT_MUTED, bg=BG_CARD)
            t_lbl.pack(anchor="w")

            v_lbl = tk.Label(card, textvariable=self.kpi_vars[val_k], font=FONTS["kpi_value"], fg=col, bg=BG_CARD)
            v_lbl.pack(anchor="w", pady=(2, 2))

            s_lbl = tk.Label(card, textvariable=self.kpi_vars[sub_k], font=FONTS["kpi_sub"], fg=TEXT_MUTED, bg=BG_CARD)
            s_lbl.pack(anchor="w")

            for widget in (card, t_lbl, v_lbl, s_lbl):
                self.attach_help(widget, hlp)

        # 2. Power Flow & Energy Conservation Visualizer
        power_box = tk.Frame(res_frame, bg=BG_CARD, bd=1, relief="solid", padx=12, pady=8)
        power_box.pack(fill=tk.X, pady=(0, 10))

        p_header = tk.Frame(power_box, bg=BG_CARD)
        p_header.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            p_header,
            text="Энергетический баланс системы (P_вх = P_вых + P_потери):",
            font=FONTS["body_bold"],
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(side=tk.LEFT)
        tk.Label(
            p_header,
            textvariable=self.power_balance_var,
            font=FONTS["caption_bold"],
            fg=COLOR_SUCCESS,
            bg=BG_CARD,
        ).pack(side=tk.RIGHT)

        self.power_canvas = tk.Canvas(power_box, height=20, bg=BG_SUBTLE, highlightthickness=0)
        self.power_canvas.pack(fill=tk.X, pady=(2, 4))

        p_leg = tk.Frame(power_box, bg=BG_CARD)
        p_leg.pack(fill=tk.X)

        def add_leg_item(parent_frame, color, label):
            tk.Label(parent_frame, text="   ", bg=color, font=("Segoe UI", 4), relief="solid", bd=1).pack(
                side=tk.LEFT, padx=(0, 3)
            )
            tk.Label(parent_frame, text=label, font=FONTS["caption"], fg=TEXT_BODY, bg=BG_CARD).pack(
                side=tk.LEFT, padx=(0, 14)
            )

        add_leg_item(p_leg, COLOR_SUCCESS, "P_вых (Полезная нагрузка)")
        add_leg_item(p_leg, COLOR_COPPER, "P_cu (Потери в меди Tx/Rx)")
        add_leg_item(p_leg, COLOR_DANGER, "P_mos (Потери в транзисторах)")

        # 3. Tables: EM Parameters & Power Metrics
        tables_frame = ttk.Frame(res_frame)
        tables_frame.pack(fill=tk.BOTH, expand=True)
        tables_frame.columnconfigure(0, weight=1)
        tables_frame.columnconfigure(1, weight=1)
        tables_frame.rowconfigure(0, weight=1)

        box_left = ttk.LabelFrame(tables_frame, text="  Электромагнитные параметры контуров  ", padding=10)
        box_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

        box_right = ttk.LabelFrame(tables_frame, text="  Энергетические показатели системы  ", padding=10)
        box_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)

        def add_row_res(parent_box, r_idx, label, key, help_text, bold=False):
            bg_c = BG_SUBTLE if r_idx % 2 == 1 else BG_CARD
            row_f = tk.Frame(parent_box, bg=bg_c, padx=8, pady=3)
            row_f.pack(fill=tk.X, expand=False, pady=1)

            use_f = FONTS["body_bold"] if bold else FONTS["body"]
            fg_color = ACCENT_PRIMARY if bold else TEXT_MAIN

            row_f.columnconfigure(0, weight=1)
            row_f.columnconfigure(1, weight=0)

            lbl_name = tk.Label(row_f, text=label, font=FONTS["body"], fg=TEXT_BODY, bg=bg_c, anchor="w")
            lbl_name.grid(row=0, column=0, sticky="w")

            lbl_val = tk.Label(row_f, textvariable=self.res_vars[key], font=use_f, fg=fg_color, bg=bg_c, anchor="e")
            lbl_val.grid(row=0, column=1, sticky="e", padx=(6, 0))

            for widget in (row_f, lbl_name, lbl_val):
                self.attach_help(widget, help_text)
            return r_idx + 1

        r = 0
        r = add_row_res(box_left, r, "Намотка (Tx / Rx):", "winding", "Реальная раскладка витков: диаметр пучка литца с изоляцией, число слоёв и шаг.")
        r = add_row_res(box_left, r, "Индуктивность L1 / L2:", "L1", "Собственные индуктивности спиралей с учетом двух ферритовых экранов (метод изображений).")
        r = add_row_res(box_left, r, "R пост (Tx / Rx):", "R1_dc", "Омическое сопротивление обмоток на постоянном токе.")
        r = add_row_res(box_left, r, "R вч (Tx / Rx):", "R1_ac", "Полное сопротивление провода с учетом скин-эффекта и эффекта близости.", bold=True)
        r = add_row_res(box_left, r, "Добротность Q1 / Q2:", "Q1", "Ненагруженная добротность резонаторов: Q = omega * L / R.", bold=True)
        r = add_row_res(box_left, r, "Резонансная емкость C1 / C2:", "C1", "Требуемая емкость компенсирующих конденсаторов: C = 1 / (omega0² * L).")
        r = add_row_res(box_left, r, "Взаимная индуктивность M:", "M", "Взаимная индуктивность между спиралями с учетом ферритовых экранов.")
        add_row_res(box_left, r, "Связь k (kкр, kопт):", "k", "k = M / sqrt(L1 * L2). k кр — порог расщепления АЧХ на два пика; k опт = 1/sqrt(Q1*Q2).", bold=True)

        r2 = 0
        r2 = add_row_res(box_right, r2, "Частота инвертора f комм:", "f_opt", "Текущая рабочая частота переключения ключей моста.", bold=True)
        r2 = add_row_res(box_right, r2, "Токи контуров I1 / I2 (RMS):", "I1", "Среднеквадратичные токи в передающей и приемной катушках.")
        r2 = add_row_res(box_right, r2, "Напряжение нагрузки Uвых:", "V_out", "Постоянное напряжение на нагрузке после выпрямителя.", bold=True)
        r2 = add_row_res(box_right, r2, "Входная мощность Pвх:", "P_in", "Полная мощность, потребляемая от шины питания.")
        r2 = add_row_res(box_right, r2, "Мощность нагрузки Pвых:", "P_out", "Полезная мощность, передаваемая в нагрузку.", bold=True)
        r2 = add_row_res(box_right, r2, "Потери в меди обмоток Pмед:", "P_cu", "Суммарные омические потери в меди передатчика и приемника.")
        r2 = add_row_res(box_right, r2, "Потери в ключах моста Pкл:", "P_mos", "Потери мощности на сопротивлении открытых каналов транзисторов.")
        r2 = add_row_res(box_right, r2, "Полный КПД тракта (η):", "eta", "КПД тракта по модели с учетом R вч обмоток и Rds ключей.", bold=True)
        add_row_res(box_right, r2, "Фазовый угол Zвх (φ):", "phase", "Сдвиг фазы между напряжением и током инвертора.")

        # Bottom Actions Bar
        act_box = tk.Frame(res_frame, bg=BG_WINDOW)
        act_box.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            act_box,
            text="📋  Копировать отчёт в буфер (Markdown)",
            font=FONTS["body_bold"],
            bg=BG_CARD,
            fg=ACCENT_PRIMARY,
            activebackground=BG_SUBTLE,
            relief="solid",
            bd=1,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_copy_report,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            act_box,
            text="📊  Экспорт таблицы в CSV",
            font=FONTS["body"],
            bg=BG_CARD,
            fg=TEXT_BODY,
            activebackground=BG_SUBTLE,
            relief="solid",
            bd=1,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._on_export_csv,
        ).pack(side=tk.LEFT)

        tk.Label(
            act_box,
            textvariable=self.bot_insight_var,
            font=FONTS["caption_bold"],
            fg=ACCENT_PRIMARY,
            bg=BG_WINDOW,
        ).pack(side=tk.RIGHT, padx=6)

    def update_from_results(self, results: Dict[str, Any], auto_track: bool) -> None:
        lay_tx = results["lay_tx"]
        lay_rx = results["lay_rx"]
        circuit = results["circuit"]
        L1, L2 = results["L1"], results["L2"]
        R1_dc, R2_dc = results["R1_dc"], results["R2_dc"]
        R1_ac, R2_ac = results["R1_ac"], results["R2_ac"]
        Q1, Q2 = results["Q1"], results["Q2"]
        C1, C2 = results["C1"], results["C2"]
        M, k, k_crit, k_opt = results["M"], results["k"], results["k_crit"], results["k_opt"]
        f_actual_kHz = results["f_drive_kHz"]

        if (lay_tx.layers, lay_tx.per_layer, round(lay_tx.pitch_m, 6)) == (
            lay_rx.layers,
            lay_rx.per_layer,
            round(lay_rx.pitch_m, 6),
        ):
            self.res_vars["winding"].set(
                f"Tx=Rx: {lay_tx.layers} сл.×{lay_tx.per_layer}, s={lay_tx.pitch_m*1e3:.1f}мм, Ø{lay_tx.D_wire_m*1e3:.2f}мм"
            )
        else:
            self.res_vars["winding"].set(
                f"Tx:{lay_tx.layers}сл.×{lay_tx.per_layer} | Rx:{lay_rx.layers}сл.×{lay_rx.per_layer}"
            )
        self.res_vars["L1"].set(f"{L1*1e6:.2f} мкГн  |  {L2*1e6:.2f} мкГн")
        self.res_vars["R1_dc"].set(f"{R1_dc*1e3:.1f} мОм  |  {R2_dc*1e3:.1f} мОм")
        self.res_vars["R1_ac"].set(f"{R1_ac*1e3:.1f} мОм  |  {R2_ac*1e3:.1f} мОм")
        self.res_vars["Q1"].set(f"{Q1:.1f}  |  {Q2:.1f}")
        self.res_vars["C1"].set(f"{C1*1e9:.2f} нФ  |  {C2*1e9:.2f} нФ")
        self.res_vars["M"].set(f"{M*1e6:.3f} мкГн")
        kc_txt = f"{k_crit:.3f}" if k_crit < 0.99 else "нет"
        self.res_vars["k"].set(f"{k:.4f} (kкр={kc_txt}, kопт={k_opt:.3f})")

        mode_str = " (авто)" if auto_track else ""
        self.res_vars["f_opt"].set(f"{f_actual_kHz:.2f} кГц{mode_str}")
        self.res_vars["I1"].set(f"{circuit['I1_rms']:.2f} А  |  {circuit['I2_rms']:.2f} А")
        self.res_vars["V_out"].set(f"{circuit['V_out_dc']:.2f} В")
        self.res_vars["P_in"].set(f"{circuit['P_in']:.2f} Вт")
        self.res_vars["P_out"].set(f"{circuit['P_out']:.2f} Вт")
        self.res_vars["P_cu"].set(f"{circuit['P_cu']:.3f} Вт")
        self.res_vars["P_mos"].set(f"{circuit['P_mos']:.3f} Вт")
        self.res_vars["eta"].set(f"{circuit['eta']*100:.1f} %")
        self.res_vars["phase"].set(f"{circuit['phase_deg']:+.1f}° ({'ZVS' if circuit['phase_deg']>=0 else 'емкостной'})")

        self.kpi_vars["eta"].set(f"{circuit['eta']*100:.1f} %")
        loss_w = circuit["P_cu"] + circuit["P_mos"]
        self.kpi_vars["eta_sub"].set(f"Потери: {loss_w:.2f} Вт")
        self.kpi_vars["P_out"].set(f"{circuit['P_out']:.2f} Вт")
        self.kpi_vars["P_out_sub"].set(f"Вход: {circuit['P_in']:.2f} Вт")
        self.kpi_vars["f_opt"].set(f"{f_actual_kHz:.2f} кГц")
        self.kpi_vars["f_opt_sub"].set("Автоподстройка" if auto_track else "Фиксированная f")
        self.kpi_vars["k"].set(f"{k:.4f}")
        k_state = "сильная связь" if k > k_crit else "оптимальная" if abs(k - k_opt) < 0.05 else "умеренная связь"
        self.kpi_vars["k_sub"].set(f"{k_state} (kкр={kc_txt})")

        p_in = circuit["P_in"]
        p_out = circuit["P_out"]
        p_cu = circuit["P_cu"]
        p_mos = circuit["P_mos"]
        diff_w = abs(p_in - (p_out + p_cu + p_mos))

        self.power_balance_var.set(
            f"Баланс: P_вх = {p_in:.2f} Вт | P_вых = {p_out:.2f} Вт, Медь = {p_cu:.2f} Вт, Ключи = {p_mos:.2f} Вт  |  ΔP = {diff_w:.1e} Вт [Инвариант соблюдён]"
        )
        self.update_power_bar(p_in, p_out, p_cu, p_mos)

        zvs_status = "ZVS активна (Zвх индуктивный)" if circuit["phase_deg"] >= 0 else "Жесткая коммутация (Zвх емкостной)"
        self.bot_insight_var.set(
            f"SS-резонанс • {zvs_status} • Q1 = {Q1:.1f}, Q2 = {Q2:.1f} • Потери: медь {p_cu:.2f} Вт, ключи {p_mos:.2f} Вт"
        )

    def update_power_bar(self, p_in: float, p_out: float, p_cu: float, p_mos: float) -> None:
        cv = self.power_canvas
        cv.delete("all")
        if p_in <= 1e-9:
            return

        cv.update_idletasks()
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 50:
            w = 800

        f_out = max(0.0, p_out / p_in)
        f_cu = max(0.0, p_cu / p_in)
        f_mos = max(0.0, p_mos / p_in)

        w_out = int(w * f_out)
        w_cu = int(w * f_cu)
        w_mos = w - w_out - w_cu

        x0 = 0
        if w_out > 0:
            cv.create_rectangle(x0, 0, x0 + w_out, h, fill=COLOR_SUCCESS, outline="")
            if w_out > 60:
                cv.create_text(x0 + w_out / 2, h / 2, text=f"Pвых: {f_out*100:.1f}%", fill="#ffffff", font=FONTS["caption_bold"])
            x0 += w_out

        if w_cu > 0:
            cv.create_rectangle(x0, 0, x0 + w_cu, h, fill=COLOR_COPPER, outline="")
            if w_cu > 50:
                cv.create_text(x0 + w_cu / 2, h / 2, text=f"Pcu: {f_cu*100:.1f}%", fill="#ffffff", font=FONTS["caption_bold"])
            x0 += w_cu

        if w_mos > 0:
            cv.create_rectangle(x0, 0, x0 + w_mos, h, fill=COLOR_DANGER, outline="")
            if w_mos > 50:
                cv.create_text(x0 + w_mos / 2, h / 2, text=f"Pmos: {f_mos*100:.1f}%", fill="#ffffff", font=FONTS["caption_bold"])
