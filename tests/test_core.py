"""
Unit tests for the WPT computational physics and circuit core.
Compatible with standard library unittest and pytest.
"""

import unittest
import numpy as np

from wpt_designer.core import (
    Winding,
    min_coil_gap_m,
    calc_inductance,
    calc_mutual_inductance_fast,
    calc_litz_resistance,
    winding_resistances,
    calc_coupling,
    calc_critical_coupling,
    find_optimal_tracking_freq,
    solve_ss_wpt_circuit,
)
from wpt_designer.core.ac_losses import skin_factor


class TestWPTCore(unittest.TestCase):
    def test_winding_creation(self):
        w = Winding(D_out_mm=50.0, D_in_mm=20.0, N=12, d_strand_mm=0.1, n_strands=40)
        self.assertTrue(w.feasible)
        self.assertGreaterEqual(w.layers, 1)
        self.assertEqual(len(w.r), 12)
        self.assertEqual(len(w.z), 12)
        self.assertGreater(w.length_m, 0.5)

    def test_min_coil_gap(self):
        w1 = Winding(50.0, 20.0, 12, 0.1, 40)
        w2 = Winding(50.0, 20.0, 12, 0.1, 40)
        gap = min_coil_gap_m(w1, w2)
        self.assertGreater(gap, 0.0)
        self.assertLess(gap, 0.01)

    def test_inductance_calculation(self):
        w1 = Winding(50.0, 20.0, 12, 0.1, 40)
        w2 = Winding(50.0, 20.0, 12, 0.1, 40)
        d_m = 0.015

        L1 = calc_inductance(w1, w2, d_m)
        L2 = calc_inductance(w2, w1, d_m)
        M = calc_mutual_inductance_fast(15.0, w1, w2)
        k = calc_coupling(M, L1, L2)

        self.assertTrue(1e-6 < L1 < 100e-6, f"L1={L1} out of expected range")
        self.assertTrue(1e-6 < L2 < 100e-6, f"L2={L2} out of expected range")
        self.assertTrue(0.0 < M < L1, f"M={M} out of expected range")
        self.assertTrue(0.0 < k < 1.0, f"k={k} out of expected range")

    def test_litz_resistance(self):
        w = Winding(50.0, 20.0, 12, 0.1, 40)
        R_dc, R_ac = calc_litz_resistance(w, f_kHz=100.0, K_prox=0.0)

        self.assertGreater(R_dc, 0.0)
        self.assertGreaterEqual(R_ac, R_dc)

    def test_ss_circuit_solver(self):
        w1 = Winding(50.0, 20.0, 12, 0.1, 40)
        w2 = Winding(50.0, 20.0, 12, 0.1, 40)
        d_m = 0.015
        L1 = calc_inductance(w1, w2, d_m)
        L2 = calc_inductance(w2, w1, d_m)
        M = calc_mutual_inductance_fast(15.0, w1, w2)
        R1_dc, R1_ac, R2_dc, R2_ac = winding_resistances(w1, w2, 100.0, d_m)

        f0_kHz = 100.0
        omega0 = 2.0 * np.pi * f0_kHz * 1000.0
        C1 = 1.0 / (omega0**2 * L1)
        C2 = 1.0 / (omega0**2 * L2)

        sol = solve_ss_wpt_circuit(
            V_bus_dc=12.0,
            f_drive_kHz=100.0,
            L1=L1,
            C1=C1,
            R1=R1_ac,
            L2=L2,
            C2=C2,
            R2=R2_ac,
            M=M,
            R_load=10.0,
            Rds_on_mOhm=25.0
        )

        self.assertGreater(sol['I1_rms'], 0.0)
        self.assertGreater(sol['I2_rms'], 0.0)
        self.assertGreater(sol['P_out'], 0.0)
        self.assertTrue(0.0 < sol['eta'] < 1.0, f"eta={sol['eta']} out of expected range")

    def test_energy_conservation(self):
        """Проверка строгого баланса активных мощностей: P_in == P_out + P_cu + P_mos."""
        L1, L2 = 25e-6, 25e-6
        f0_kHz = 100.0
        omega0 = 2.0 * np.pi * f0_kHz * 1000.0
        C1 = 1.0 / (omega0**2 * L1)
        C2 = 1.0 / (omega0**2 * L2)

        for f_drive in [80.0, 100.0, 150.0]:
            sol = solve_ss_wpt_circuit(
                V_bus_dc=12.0,
                f_drive_kHz=f_drive,
                L1=L1,
                C1=C1,
                R1=0.2,
                L2=L2,
                C2=C2,
                R2=0.25,
                M=0.5 * np.sqrt(L1 * L2),
                R_load=8.0,
                Rds_on_mOhm=30.0
            )
            p_in = sol['P_in']
            p_sum = sol['P_out'] + sol['P_cu'] + sol['P_mos']
            self.assertAlmostEqual(p_in, p_sum, places=9)

    def test_skin_factor_continuity(self):
        """Проверка непрерывности skin_factor(xi) на границах формул (xi = 0.05 и x = 50.0)."""
        # Граница 1: xi = 0.05
        sf_low = skin_factor(0.05 - 1e-7)
        sf_high = skin_factor(0.05 + 1e-7)
        self.assertAlmostEqual(sf_low, sf_high, places=5)

        # Граница 2: x = 50.0 -> xi = 50 / sqrt(2)
        xi_crit = 50.0 / np.sqrt(2.0)
        sf_below = skin_factor(xi_crit - 1e-5)
        sf_above = skin_factor(xi_crit + 1e-5)
        self.assertAlmostEqual(sf_below, sf_above, delta=0.01)

    def test_bifurcation_and_zvs(self):
        """Проверка трекера: при k <= k_crit -> f0; при k > k_crit (k=0.7) -> f > f0 и phase_deg > 0."""
        L1, L2 = 25e-6, 25e-6
        f0_kHz = 100.0
        omega0 = 2.0 * np.pi * f0_kHz * 1000.0
        C1 = 1.0 / (omega0**2 * L1)
        C2 = 1.0 / (omega0**2 * L2)
        R1, R2 = 0.1, 0.1
        R_load = 5.0
        Rds = 25.0

        R1_tot = R1 + 2.0 * Rds / 1000.0
        R2_tot = R2 + 2.0 * Rds / 1000.0 + (8.0 / (np.pi**2)) * R_load
        k_crit = calc_critical_coupling(L1, R1_tot, L2, R2_tot, f0_kHz)

        # Слабая связь (k < k_crit)
        M_weak = (k_crit * 0.5) * np.sqrt(L1 * L2)
        f_weak = find_optimal_tracking_freq(f0_kHz, L1, C1, R1, L2, C2, R2, M_weak, R_load, Rds)
        self.assertEqual(f_weak, f0_kHz)

        # Сильная связь (k = 0.7 > k_crit)
        M_strong = 0.7 * np.sqrt(L1 * L2)
        f_strong = find_optimal_tracking_freq(f0_kHz, L1, C1, R1, L2, C2, R2, M_strong, R_load, Rds)
        self.assertGreater(f_strong, f0_kHz)

        sol = solve_ss_wpt_circuit(12.0, f_strong, L1, C1, R1, L2, C2, R2, M_strong, R_load, Rds)
        self.assertGreater(sol['phase_deg'], 0.0)

    def test_edge_cases_and_validation(self):
        """Проверка валидации входных данных и отсутствия необработанных исключений."""
        # Некорректные параметры цепи
        with self.assertRaises(ValueError):
            solve_ss_wpt_circuit(12.0, 0.0, 1e-6, 1e-9, 0.1, 1e-6, 1e-9, 0.1, 0.1e-6, 10.0, 25.0)

        with self.assertRaises(ValueError):
            solve_ss_wpt_circuit(12.0, 100.0, -1e-6, 1e-9, 0.1, 1e-6, 1e-9, 0.1, 0.1e-6, 10.0, 25.0)

        with self.assertRaises(ValueError):
            solve_ss_wpt_circuit(12.0, 100.0, 1e-6, 0.0, 0.1, 1e-6, 1e-9, 0.1, 0.1e-6, 10.0, 25.0)

        # Сингулярная матрица (det == 0)
        with self.assertRaises(ZeroDivisionError):
            omega = 2.0 * np.pi * 100e3
            L = 10e-6
            C = 1.0 / (omega**2 * L)
            # R1=0, R2=0, Rds=0, R_load=0, M=0 -> Z1=0, Z2=0, ZM=0 => det=0
            solve_ss_wpt_circuit(12.0, 100.0, L, C, 0.0, L, C, 0.0, 0.0, 0.0, 0.0)

        # Некорректное число витков в Winding
        w_invalid = Winding(50.0, 20.0, 0, 0.1, 40)
        self.assertFalse(w_invalid.feasible)
        self.assertEqual(len(w_invalid.r), 0)
        self.assertEqual(w_invalid.length_m, 0.0)

        r_dc, r_ac = calc_litz_resistance(w_invalid, 100.0)
        self.assertEqual(r_dc, 0.0)
        self.assertEqual(r_ac, 0.0)


if __name__ == '__main__':
    unittest.main()
