"""
GUI automated verification tests for WPTCalculatorApp.
Verifies:
1. Widget tree builds and theme styles apply cleanly without Tk exceptions.
2. Initial calculation populates all KPI and telemetry variables.
3. Switching between engineering presets updates entries and recalculates.
4. Power flow bar and energy conservation invariants execute properly.
5. Interactive 2D Gaussmeter probe lookup returns valid numerical values.
"""

import unittest
import tkinter as tk

from wpt_designer.gui.app_window import WPTCalculatorApp
from wpt_designer.gui.presets import PRESETS


class TestWPTCalculatorApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()  # Offscreen
            cls.app = WPTCalculatorApp(cls.root)
        except Exception as e:
            raise unittest.SkipTest(f"Tkinter display not available: {e}") from e

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'app') and hasattr(cls, 'root'):
            try:
                cls.root.update_idletasks()
                cls.app.on_close()
            except Exception:
                pass

    def test_gui_initialization_and_results(self):
        """Проверка успешной инициализации GUI и выполнения начального расчета."""
        self.assertIsNotNone(self.app.results)
        self.assertIn("L1", self.app.results)
        self.assertIn("circuit", self.app.results)

        # Check telemetry and KPI variables
        self.assertTrue(self.app.telemetry_zvs_var.get().startswith("🟢 ZVS"))
        self.assertTrue("⚡ Решатель:" in self.app.telemetry_bench_var.get())
        self.assertTrue("Инвариант соблюдён" in self.app.power_balance_var.get())

        # Check live express KPI on Tab 1
        self.assertTrue(len(self.app.live_kpi['eta'].get()) > 0)
        self.assertTrue(len(self.app.live_kpi['pout'].get()) > 0)

    def test_preset_switching(self):
        """Проверка переключения инженерных пресетов через GUI."""
        for preset_key, preset in PRESETS.items():
            self.app.load_preset_by_key(preset_key)
            self.assertEqual(self.app.preset_var.get(), preset.name)
            self.assertIsNotNone(self.app.results)
            # Energy balance check in GUI
            c = self.app.results['circuit']
            p_in = c['P_in']
            p_sum = c['P_out'] + c['P_cu'] + c['P_mos']
            self.assertAlmostEqual(p_in, p_sum, places=6)

    def test_tab_rendering(self):
        """Проверка ленивой отрисовки всех вкладок графиков."""
        for tab_idx in range(2, 6):
            self.app.notebook.select(tab_idx)
            self.app._render_tab_if_dirty(tab_idx)
            self.assertFalse(self.app._dirty_tabs.get(tab_idx, True))

    def test_interactive_gaussmeter_probe(self):
        """Проверка работы 2D сплайна для интерактивного зонда поля."""
        # Ensure tab 4 (2D field) is rendered
        self.app.notebook.select(4)
        self.app.plot_field_2d()
        self.assertIsNotNone(self.app._spline_B_2d)

        # Probe at center of gap (x=0, z=d/2)
        d_mid = self.app.results['dist_mm'] / 2.0
        b_val = float(self.app._spline_B_2d(0.0, d_mid)[0, 0])
        self.assertGreater(b_val, 0.0)
        self.assertLess(b_val, 150.0)


if __name__ == "__main__":
    unittest.main()
