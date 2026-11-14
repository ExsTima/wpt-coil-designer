"""
Tab 7: Automated FEA verification with FEMM 4.2 and CSV report export.
"""

import csv
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..theme import ACCENT_HOVER, ACCENT_PRIMARY, BG_CARD, FONTS, TEXT_BODY, TEXT_MUTED

logger = logging.getLogger(__name__)


class FemmTab:
    """Вкладка 7: Кросс-верификация аналитического ядра с FEMM 4.2."""

    def __init__(
        self,
        parent: ttk.Frame,
        root: tk.Tk,
        attach_help: Callable[..., None],
        get_results: Callable[[], Optional[Dict[str, Any]]],
        examples_dir: Path,
        screenshot_path: Path,
    ):
        self.parent = parent
        self.root = root
        self.attach_help = attach_help
        self._get_results = get_results
        self.examples_dir = examples_dir
        self.screenshot_path = screenshot_path

        self._femm_running = False
        self._femm_stop_event = threading.Event()
        self.var_keep_femm_open = tk.BooleanVar(value=True)
        self.femm_report_rows: List[Tuple[str, str, str, str]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.parent, padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        top_bar = ttk.LabelFrame(
            container,
            text="Автоматическая кросс-верификация методом конечных элементов (FEMM 4.2)",
            padding=10,
        )
        top_bar.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            top_bar,
            text=(
                "Модуль передает точные параметры спиралей в FEMM 4.2, строит КЭ-сетку с ферритовыми экранами MnZn (mu_r = 2000)\n"
                "и выполняет раздельные расчеты для L1, L2, M и k без приближений."
            ),
            font=FONTS["body"],
            fg=TEXT_BODY,
            bg=BG_CARD,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(top_bar, bg=BG_CARD)
        btn_row.pack(fill=tk.X)

        self.btn_run_femm = tk.Button(
            btn_row,
            text="🚀  Запустить верификацию в FEMM 4.2",
            font=FONTS["body_bold"],
            bg=ACCENT_PRIMARY,
            fg="#ffffff",
            activebackground=ACCENT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.run_verification,
        )
        self.btn_run_femm.pack(side="left", ipadx=10, ipady=6)
        self.attach_help(self.btn_run_femm, "Запустить сессию FEMM 4.2, построить геометрию и рассчитать L1, L2, M.")

        ttk.Checkbutton(btn_row, text="Оставлять FEMM открытым", variable=self.var_keep_femm_open).pack(
            side="left", padx=(12, 6)
        )

        self.btn_open_screen = ttk.Button(btn_row, text="Открыть снимок", command=self.open_saved_screenshot)
        self.btn_open_screen.pack(side="left", padx=4, ipadx=4, ipady=2)

        self.btn_close_femm = ttk.Button(btn_row, text="Закрыть FEMM", command=self.close_femm_manually)
        self.btn_close_femm.pack(side="left", padx=4, ipadx=4, ipady=2)

        ttk.Button(btn_row, text="Экспорт протокола (CSV)", command=self.save_report).pack(
            side="left", padx=(4, 0), ipadx=4, ipady=2
        )

        table_box = ttk.LabelFrame(
            container,
            text="Сравнительная таблица: Аналитическая модель (Python) vs МКЭ (FEMM 4.2)",
            padding=10,
        )
        table_box.pack(fill=tk.BOTH, expand=True)

        cols = ("param", "analytic", "femm", "error")
        self.femm_tree = ttk.Treeview(table_box, columns=cols, show="headings", height=6)
        self.femm_tree.heading("param", text="Исследуемый параметр")
        self.femm_tree.heading("analytic", text="Аналитическая модель (Python)")
        self.femm_tree.heading("femm", text="МКЭ-моделирование (FEMM 4.2)")
        self.femm_tree.heading("error", text="Относительное расхождение, %")

        self.femm_tree.column("param", width=380, anchor="w")
        self.femm_tree.column("analytic", width=220, anchor="center")
        self.femm_tree.column("femm", width=220, anchor="center")
        self.femm_tree.column("error", width=200, anchor="center")
        self.femm_tree.pack(fill=tk.X, pady=(4, 10))

        self.femm_status_lbl = tk.Label(
            table_box,
            text="Статус: Ожидание запуска FEMM 4.2 (требуются pyfemm и установленный пакет FEMM 4.2).",
            font=FONTS["body"],
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        self.femm_status_lbl.pack(anchor="w", pady=4)

    def populate_initial_table(self, results: Optional[Dict[str, Any]]) -> None:
        for item in self.femm_tree.get_children():
            self.femm_tree.delete(item)
        if not results:
            return
        rows = [
            ("Индуктивность передатчика L1, мкГн", f"{results['L1']*1e6:.2f}", "Ожидание расчета...", "-"),
            ("Индуктивность приемника L2, мкГн", f"{results['L2']*1e6:.2f}", "Ожидание расчета...", "-"),
            (f"Взаимная индуктивность M (d={results['dist_mm']:.0f} мм), мкГн", f"{results['M']*1e6:.3f}", "Ожидание расчета...", "-"),
            ("Коэффициент магнитной связи k", f"{results['k']:.4f}", "Ожидание расчета...", "-"),
            ("Активное ВЧ-сопротивление обмотки R вч (Tx), мОм", f"{results['R1_ac']*1e3:.1f}", "Ожидание расчета...", "-"),
        ]
        for row_vals in rows:
            self.femm_tree.insert("", tk.END, values=row_vals)

    def run_verification(self, results: Optional[Dict[str, Any]] = None) -> None:
        if results is None:
            results = self._get_results()
        if not results:
            messagebox.showwarning("Внимание", "Сначала выполните расчет на Вкладке 1.")
            return

        if self._femm_running:
            messagebox.showinfo("Расчет выполняется", "Верификация в FEMM 4.2 уже запущена в фоновом режиме.")
            return

        from ...verification.femm_runner import is_femm_available, run_femm_simulation

        avail, err_msg = is_femm_available()
        if not avail:
            messagebox.showerror("FEMM 4.2 недоступен", err_msg)
            return

        self._femm_running = True
        self.btn_run_femm.config(state=tk.DISABLED)
        self.femm_status_lbl.config(text="Статус: Построение КЭ-сетки и расчет в FEMM 4.2 (в фоновом потоке)...")

        self._femm_stop_event.set()
        self._femm_stop_event = threading.Event()
        stop_event = self._femm_stop_event
        r_copy = results.copy()

        def worker() -> None:
            try:
                def on_success(femm_res) -> None:
                    self.femm_report_rows = femm_res.report_rows
                    for item in self.femm_tree.get_children():
                        self.femm_tree.delete(item)
                    for row_vals in self.femm_report_rows:
                        self.femm_tree.insert("", tk.END, values=row_vals)

                    status_msg = "Статус: Верификация в FEMM 4.2 успешно завершена."
                    if self.var_keep_femm_open.get():
                        status_msg += " Окно FEMM 4.2 оставлено открытым (снимок сохранен в assets/femm_verification_screenshot.png)."
                    self.femm_status_lbl.config(text=status_msg)
                    self.btn_run_femm.config(state=tk.NORMAL)
                    self._femm_running = False

                run_femm_simulation(
                    r_copy,
                    output_dir=str(self.examples_dir),
                    save_screenshot=True,
                    screenshot_path=str(self.screenshot_path),
                    keep_open=self.var_keep_femm_open.get(),
                    stop_event=stop_event,
                    on_complete=lambda res: self.root.after(0, on_success, res),
                )
            except Exception as exc:
                logger.exception("FEMM verification failed")
                err_text = str(exc)

                def on_error() -> None:
                    self.femm_status_lbl.config(text=f"Статус: Ошибка при обращении к FEMM 4.2 ({err_text}).")
                    messagebox.showerror("Ошибка интеграции с FEMM 4.2", f"Не удалось выполнить расчет в FEMM:\n{err_text}")
                    self.btn_run_femm.config(state=tk.NORMAL)
                    self._femm_running = False

                self.root.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

    def close_femm_manually(self) -> None:
        self.stop_and_close()
        self.femm_status_lbl.config(text="Статус: Окно FEMM 4.2 закрыто.")

    def stop_and_close(self) -> None:
        self._femm_stop_event.set()
        try:
            from ...verification.femm_runner import close_femm

            close_femm()
        except Exception as exc:
            logger.debug("Failed to close FEMM window: %s", exc)

    def open_saved_screenshot(self) -> None:
        if self.screenshot_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self.screenshot_path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(self.screenshot_path)])
                else:
                    subprocess.Popen(["xdg-open", str(self.screenshot_path)])
            except Exception as exc:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл: {exc}")
        else:
            messagebox.showinfo(
                "Снимок не найден",
                "Файл femm_verification_screenshot.png еще не создан. Запустите верификацию в FEMM 4.2.",
            )

    def save_report(self) -> None:
        if not self.femm_report_rows:
            messagebox.showwarning("Внимание", "Сначала запустите верификацию в FEMM 4.2 и дождитесь окончания расчета.")
            return
        fn = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not fn:
            return
        with open(fn, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Параметр", "Аналитическая_модель_Python", "МКЭ_FEMM_4_2", "Погрешность_проц"])
            writer.writerows(self.femm_report_rows)
        messagebox.showinfo("Экспорт", "Протокол сверки сохранен.")
