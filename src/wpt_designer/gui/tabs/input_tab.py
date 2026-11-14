"""
Tab 1: System parameters, engineering presets, and live express KPI preview.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk

from ..presets import PRESETS, PRESET_NAMES
from ..theme import (
    ACCENT_HOVER,
    ACCENT_PRIMARY,
    BG_CARD,
    BG_MUTED,
    BG_SUBTLE,
    BG_WINDOW,
    COLOR_COPPER,
    COLOR_DANGER,
    COLOR_DANGER_BG,
    COLOR_PURPLE,
    COLOR_SAPPHIRE,
    COLOR_SUCCESS,
    FONTS,
    TEXT_BODY,
    TEXT_MAIN,
    TEXT_MUTED,
)


class InputTab:
    """Вкладка 1: Параметры системы, выбор инженерных пресетов и экспресс-KPI."""

    def __init__(
        self,
        parent: ttk.Frame,
        root: tk.Tk,
        attach_help: Callable[..., None],
        status_var: tk.StringVar,
        on_calculate: Callable[[], None],
    ):
        self.parent = parent
        self.root = root
        self.attach_help = attach_help
        self.status_var = status_var
        self._on_calculate = on_calculate

        self.preset_var = tk.StringVar(value=PRESET_NAMES[0])
        self.vars: Dict[str, tk.StringVar] = {}
        self.entry_widgets: Dict[str, tk.Entry] = {}
        self.rx_entries: List[tk.Entry] = []

        self._build_ui()

    def _build_ui(self) -> None:
        canvas = tk.Canvas(self.parent, bg=BG_WINDOW, highlightthickness=0)
        v_scroll = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas, padding=10)

        container.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=v_scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Top Preset Bar
        preset_bar = tk.Frame(container, bg=BG_CARD, bd=1, relief="solid", padx=12, pady=8)
        preset_bar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            preset_bar,
            text="Инженерный пресет:",
            font=FONTS["body_bold"],
            fg=TEXT_MAIN,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(0, 8))

        cmb_preset = ttk.Combobox(
            preset_bar,
            textvariable=self.preset_var,
            values=PRESET_NAMES,
            state="readonly",
            width=42,
            font=FONTS["body"],
        )
        cmb_preset.pack(side=tk.LEFT, padx=(0, 8))
        cmb_preset.bind("<<ComboboxSelected>>", self.apply_selected_preset)

        tk.Button(
            preset_bar,
            text="Применить пресет",
            font=FONTS["body_bold"],
            bg=BG_SUBTLE,
            fg=ACCENT_PRIMARY,
            activebackground=BG_MUTED,
            relief="solid",
            bd=1,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.apply_selected_preset,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            preset_bar,
            text="Сбросить к Qi 5W",
            font=FONTS["body"],
            bg=BG_CARD,
            fg=TEXT_MUTED,
            relief="solid",
            bd=1,
            padx=8,
            pady=3,
            cursor="hand2",
            command=lambda: self.load_preset_by_key("qi_5w"),
        ).pack(side=tk.LEFT)

        self.preset_desc_lbl = tk.Label(
            preset_bar,
            text=PRESETS["qi_5w"].description,
            font=FONTS["caption"],
            fg=TEXT_MUTED,
            bg=BG_CARD,
            anchor="w",
        )
        self.preset_desc_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(12, 0))

        # Three-Column Layout: Geometry | Circuit & Drive | Express KPI Preview
        cols_frame = ttk.Frame(container)
        cols_frame.pack(fill=tk.BOTH, expand=True)
        cols_frame.columnconfigure(0, weight=4)
        cols_frame.columnconfigure(1, weight=4)
        cols_frame.columnconfigure(2, weight=3)

        left_col = ttk.LabelFrame(cols_frame, text="1. Геометрия спиральных катушек и провода", padding=10)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

        mid_col = ttk.LabelFrame(cols_frame, text="2. Силовая цепь, инвертор и частота", padding=10)
        mid_col.grid(row=0, column=1, sticky="nsew", padx=6, pady=0)

        right_col = ttk.LabelFrame(cols_frame, text="3. Экспресс-результаты (Live KPI)", padding=10)
        right_col.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=0)

        def add_entry(frame, r, text, key, default, unit, help_text, is_rx=False):
            lbl = tk.Label(frame, text=text, font=FONTS["body"], fg=TEXT_BODY, bg=BG_CARD, anchor="w")
            lbl.grid(row=r, column=0, sticky="w", pady=3)

            v = tk.StringVar(value=default)
            self.vars[key] = v

            entry_box = tk.Frame(frame, bg=BG_CARD)
            entry_box.grid(row=r, column=1, sticky="w", padx=(4, 2), pady=3)

            ent = tk.Entry(
                entry_box,
                textvariable=v,
                width=8,
                font=FONTS["mono_bold"],
                fg=TEXT_MAIN,
                bg=BG_CARD,
                relief="solid",
                bd=1,
                highlightthickness=0,
            )
            ent.pack(side=tk.LEFT)
            self.entry_widgets[key] = ent

            u_lbl = tk.Label(
                entry_box,
                text=unit,
                font=FONTS["caption_bold"],
                fg=TEXT_MUTED,
                bg=BG_CARD,
                width=5,
                anchor="w",
            )
            u_lbl.pack(side=tk.LEFT, padx=(3, 0))

            self.attach_help(lbl, help_text)
            self.attach_help(ent, help_text)
            self.attach_help(u_lbl, help_text)

            if is_rx:
                self.rx_entries.append(ent)
            return r + 1

        # Left Column: Geometry
        r = 0
        self.var_sym = tk.BooleanVar(value=True)
        chk_sym = ttk.Checkbutton(
            left_col,
            text="Симметричная система (катушки Tx и Rx идентичны)",
            variable=self.var_sym,
            command=self.toggle_symmetry,
        )
        chk_sym.grid(row=r, column=0, columnspan=2, sticky="w", pady=(0, 6))
        r += 1
        self.attach_help(chk_sym, "При включении параметры приемника Rx автоматически повторяют размеры передатчика Tx.")

        tk.Label(left_col, text="Передающий контур (Tx):", font=FONTS["body_bold"], fg=COLOR_COPPER, bg=BG_CARD).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        r += 1
        r = add_entry(left_col, r, "Внешний диаметр D нар:", "tx_Dout", "50.0", "мм", "Наружный диаметр плоской спиральной катушки передатчика.")
        r = add_entry(left_col, r, "Внутренний диаметр D вн:", "tx_Din", "20.0", "мм", "Диаметр свободного окна в центре спирали передатчика.")
        r = add_entry(left_col, r, "Число витков спирали N1:", "tx_N", "12", "вит.", "Количество витков плоской спирали Tx.")

        ttk.Separator(left_col, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=6)
        r += 1
        tk.Label(left_col, text="Приемный контур (Rx):", font=FONTS["body_bold"], fg=COLOR_SAPPHIRE, bg=BG_CARD).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        r += 1
        r = add_entry(left_col, r, "Внешний диаметр D нар:", "rx_Dout", "50.0", "мм", "Наружный диаметр спиральной катушки приемника.", is_rx=True)
        r = add_entry(left_col, r, "Внутренний диаметр D вн:", "rx_Din", "20.0", "мм", "Внутренний диаметр окна приемной катушки.", is_rx=True)
        r = add_entry(left_col, r, "Число витков спирали N2:", "rx_N", "12", "вит.", "Количество витков спирали приемника Rx.", is_rx=True)

        ttk.Separator(left_col, orient="horizontal").grid(row=r, column=0, columnspan=2, sticky="ew", pady=6)
        r += 1
        tk.Label(left_col, text="Провод обмотки (литцендрат):", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_CARD).grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        r += 1
        r = add_entry(left_col, r, "Диаметр единичной жилы d ж:", "d_strand", "0.10", "мм", "Диаметр одной медной микрожилы в составе литцендрата.")
        add_entry(left_col, r, "Количество жил в пучке n ж:", "n_strands", "100", "жил", "Число параллельных изолированных жил в проводе.")

        for key_tx in ("tx_Dout", "tx_Din", "tx_N"):
            self.vars[key_tx].trace_add("write", lambda *_args: self.sync_coils())

        self.toggle_symmetry()

        # Middle Column: Circuit & Drive
        r2 = 0
        tk.Label(mid_col, text="Инвертор (H-мост) и нагрузка:", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_CARD).grid(
            row=r2, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        r2 += 1
        r2 = add_entry(mid_col, r2, "Напряжение питания шины U пит:", "V_bus", "5.0", "В", "Постоянное напряжение питания входного H-моста.")
        r2 = add_entry(mid_col, r2, "Сопротивление ключа Rds:", "Rds_mOhm", "18.0", "мОм", "Сопротивление открытого канала одного MOSFET-транзистора.")
        r2 = add_entry(mid_col, r2, "Сопротивление нагрузки R нагр:", "R_load", "10.0", "Ом", "Активное сопротивление нагрузки на выходе выпрямителя.")

        ttk.Separator(mid_col, orient="horizontal").grid(row=r2, column=0, columnspan=2, sticky="ew", pady=6)
        r2 += 1
        tk.Label(mid_col, text="Частотный режим и зазор d:", font=FONTS["body_bold"], fg=COLOR_PURPLE, bg=BG_CARD).grid(
            row=r2, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        r2 += 1
        r2 = add_entry(mid_col, r2, "Резонансная частота f0:", "f0_kHz", "120.0", "кГц", "Частота, под которую настраиваются компенсирующие емкости C1 и C2.")
        r2 = add_entry(mid_col, r2, "Рабочая частота инвертора f раб:", "f_drive_kHz", "120.0", "кГц", "Фактическая частота переключения транзисторов силового моста.")
        r2 = add_entry(mid_col, r2, "Осевое расстояние d:", "dist_mm", "10.0", "мм", "Воздушный зазор по вертикальной оси Z между спиралями.")

        self.var_auto_track = tk.BooleanVar(value=False)
        chk_track = ttk.Checkbutton(
            mid_col,
            text="Автоподстройка частоты при k > k кр (ZVS)",
            variable=self.var_auto_track,
        )
        chk_track.grid(row=r2, column=0, columnspan=2, sticky="w", pady=(4, 8))
        r2 += 1
        self.attach_help(chk_track, "Перестраивает частоту генератора на верхний пик расщепленного резонанса при сильной связи (k > k кр).")

        btn_calc = tk.Button(
            mid_col,
            text="⚡  ВЫПОЛНИТЬ РАСЧЕТ СИСТЕМЫ",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_PRIMARY,
            fg="#ffffff",
            activebackground=ACCENT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._on_calculate,
        )
        btn_calc.grid(row=r2, column=0, columnspan=2, pady=10, sticky="ew", ipady=8)
        self.attach_help(btn_calc, "Запустить расчет индуктивностей, цепей и обновить все графики (Горячая клавиша: Enter).")
        self.root.bind("<Return>", lambda _e: self._on_calculate())

        # Right Column: Live Express KPI Cards
        self.live_kpi = {
            "eta": tk.StringVar(value="- %"),
            "pout": tk.StringVar(value="- Вт"),
            "k": tk.StringVar(value="-"),
            "f": tk.StringVar(value="- кГц"),
            "L1": tk.StringVar(value="-"),
            "L2": tk.StringVar(value="-"),
            "M": tk.StringVar(value="-"),
            "C1": tk.StringVar(value="-"),
            "Q1": tk.StringVar(value="-"),
            "zvs": tk.StringVar(value="-"),
        }

        kpi_grid = tk.Frame(right_col, bg=BG_CARD)
        kpi_grid.pack(fill=tk.X, pady=(0, 8))
        kpi_grid.columnconfigure(0, weight=1)
        kpi_grid.columnconfigure(1, weight=1)

        def make_mini_kpi(parent_frame, r_idx, c_idx, title, var, color):
            box = tk.Frame(parent_frame, bg=BG_SUBTLE, bd=1, relief="solid", padx=8, pady=6)
            box.grid(row=r_idx, column=c_idx, sticky="nsew", padx=3, pady=3)
            tk.Label(box, text=title, font=FONTS["caption_bold"], fg=TEXT_MUTED, bg=BG_SUBTLE).pack(anchor="w")
            tk.Label(box, textvariable=var, font=FONTS["kpi_value"], fg=color, bg=BG_SUBTLE).pack(anchor="w", pady=(1, 0))

        make_mini_kpi(kpi_grid, 0, 0, "КПД СИСТЕМЫ (η)", self.live_kpi["eta"], COLOR_SUCCESS)
        make_mini_kpi(kpi_grid, 0, 1, "ВЫХОДНАЯ МОЩНОСТЬ", self.live_kpi["pout"], ACCENT_PRIMARY)
        make_mini_kpi(kpi_grid, 1, 0, "СВЯЗЬ КАТУШЕК (k)", self.live_kpi["k"], COLOR_SAPPHIRE)
        make_mini_kpi(kpi_grid, 1, 1, "ЧАСТОТА ИНВЕРТОРА", self.live_kpi["f"], COLOR_PURPLE)

        summary_box = tk.Frame(right_col, bg=BG_CARD, bd=1, relief="solid", padx=8, pady=8)
        summary_box.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tk.Label(summary_box, text="Сводка электродинамики (Tx / Rx):", font=FONTS["body_bold"], fg=TEXT_MAIN, bg=BG_CARD).pack(
            anchor="w", pady=(0, 4)
        )

        def add_mini_row(parent_frame, title, var_k):
            rf = tk.Frame(parent_frame, bg=BG_CARD)
            rf.pack(fill=tk.X, pady=1)
            tk.Label(rf, text=title, font=FONTS["caption"], fg=TEXT_BODY, bg=BG_CARD).pack(side=tk.LEFT)
            tk.Label(rf, textvariable=self.live_kpi[var_k], font=FONTS["mono_bold"], fg=TEXT_MAIN, bg=BG_CARD).pack(side=tk.RIGHT)

        add_mini_row(summary_box, "Индуктивности L1 / L2:", "L1")
        add_mini_row(summary_box, "Взаимная индуктивность M:", "M")
        add_mini_row(summary_box, "Емкости резонанса C1 / C2:", "C1")
        add_mini_row(summary_box, "Добротности контуров Q1 / Q2:", "Q1")
        add_mini_row(summary_box, "Режим коммутации ZVS:", "zvs")

        tk.Label(
            summary_box,
            text="💡 Параметры пересчитываются мгновенно.\nДля глубокого анализа перейдите на Вкладку 2.",
            font=FONTS["caption"],
            fg=TEXT_MUTED,
            bg=BG_CARD,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(8, 0))

    def apply_selected_preset(self, _event=None) -> None:
        name = self.preset_var.get()
        for k, p in PRESETS.items():
            if p.name == name:
                self.load_preset_by_key(k)
                break

    def load_preset_by_key(self, preset_key: str) -> None:
        if preset_key not in PRESETS:
            return
        preset = PRESETS[preset_key]
        self.preset_var.set(preset.name)
        self.preset_desc_lbl.configure(text=preset.description)
        self.var_auto_track.set(preset.auto_track)

        for k, v in preset.params.items():
            if k in self.vars:
                self.vars[k].set(v)

        self._on_calculate()
        self.status_var.set(f"Применен инженерный пресет: {preset.name}")

    def toggle_symmetry(self) -> None:
        is_sym = self.var_sym.get()
        state = "disabled" if is_sym else "normal"
        for ent in self.rx_entries:
            ent.configure(state=state)
        if is_sym:
            self.sync_coils()

    def sync_coils(self) -> None:
        if self.var_sym.get():
            self.vars["rx_Dout"].set(self.vars["tx_Dout"].get())
            self.vars["rx_Din"].set(self.vars["tx_Din"].get())
            self.vars["rx_N"].set(self.vars["tx_N"].get())

    def get_f(self, key: str, default: float) -> float:
        try:
            val = float(self.vars[key].get().replace(",", "."))
            self.set_field_state(key, valid=True)
            return val
        except ValueError:
            self.set_field_state(key, valid=False)
            return default

    def get_i(self, key: str, default: int) -> int:
        try:
            val = int(float(self.vars[key].get().replace(",", ".")))
            self.set_field_state(key, valid=True)
            return val
        except ValueError:
            self.set_field_state(key, valid=False)
            return default

    def set_field_state(self, key: str, valid: bool) -> None:
        ent = self.entry_widgets.get(key)
        if ent is not None:
            if valid:
                ent.configure(bg=BG_CARD, fg=TEXT_MAIN)
            else:
                ent.configure(bg=COLOR_DANGER_BG, fg=COLOR_DANGER)

    def read_inputs(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Считывает и выполняет первичную валидацию полей формы."""
        self.sync_coils()
        tx_Dout = self.get_f("tx_Dout", 50.0)
        tx_Din = self.get_f("tx_Din", 20.0)
        tx_N = self.get_i("tx_N", 12)

        rx_Dout = self.get_f("rx_Dout", 50.0)
        rx_Din = self.get_f("rx_Din", 20.0)
        rx_N = self.get_i("rx_N", 12)

        d_strand = self.get_f("d_strand", 0.10)
        n_strands = self.get_i("n_strands", 100)

        V_bus = self.get_f("V_bus", 5.0)
        Rds_mOhm = self.get_f("Rds_mOhm", 18.0)
        R_load = max(self.get_f("R_load", 10.0), 0.1)

        f0_kHz = max(self.get_f("f0_kHz", 120.0), 1.0)
        f_drive_kHz = max(self.get_f("f_drive_kHz", 120.0), 1.0)
        dist_mm = max(self.get_f("dist_mm", 10.0), 0.5)

        if tx_Dout <= tx_Din or rx_Dout <= rx_Din:
            self.set_field_state("tx_Dout", False)
            self.set_field_state("tx_Din", False)
            return None, "Ошибка геометрии: Внешний диаметр D_нар должен строго превышать внутренний D_вн!"
        if tx_N < 1 or rx_N < 1 or d_strand <= 0 or n_strands < 1:
            return None, "Ошибка параметров: Число витков, число жил и диаметр жилы должны быть > 0!"

        return {
            "tx_Dout": tx_Dout,
            "tx_Din": tx_Din,
            "tx_N": tx_N,
            "rx_Dout": rx_Dout,
            "rx_Din": rx_Din,
            "rx_N": rx_N,
            "d_strand": d_strand,
            "n_strands": n_strands,
            "V_bus": V_bus,
            "Rds_mOhm": Rds_mOhm,
            "R_load": R_load,
            "f0_kHz": f0_kHz,
            "f_drive_kHz": f_drive_kHz,
            "dist_mm": dist_mm,
            "auto_track": bool(self.var_auto_track.get()),
        }, None

    def update_from_results(self, results: Dict[str, Any]) -> None:
        if self.var_auto_track.get():
            self.vars["f_drive_kHz"].set(f"{results['f_drive_kHz']:.2f}")

        circuit = results["circuit"]
        self.live_kpi["eta"].set(f"{circuit['eta']*100:.1f} %")
        self.live_kpi["pout"].set(f"{circuit['P_out']:.2f} Вт")
        self.live_kpi["k"].set(f"{results['k']:.4f}")
        self.live_kpi["f"].set(f"{results['f_drive_kHz']:.1f} кГц")
        self.live_kpi["L1"].set(f"{results['L1']*1e6:.1f} / {results['L2']*1e6:.1f} мкГн")
        self.live_kpi["M"].set(f"{results['M']*1e6:.2f} мкГн")
        self.live_kpi["C1"].set(f"{results['C1']*1e9:.1f} / {results['C2']*1e9:.1f} нФ")
        self.live_kpi["Q1"].set(f"{results['Q1']:.1f} / {results['Q2']:.1f}")
        zvs_str = "ZVS активна" if circuit["phase_deg"] >= 0 else "Жесткая коммутация"
        self.live_kpi["zvs"].set(f"{zvs_str} ({circuit['phase_deg']:+.1f}°)")
