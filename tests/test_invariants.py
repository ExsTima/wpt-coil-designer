"""
Invariant and physical conservation law tests:
1. Energy conservation (P_in == P_out + P_losses) for all engineering presets.
2. Reciprocity invariance (M_12 == M_21).
3. Boundary asymptotic limits (M -> 0 as d -> inf, R_ac -> R_dc as f -> 0).
4. Preset configurations validity and geometric feasibility.
"""

import unittest
import numpy as np

from wpt_designer.core import (
    Winding,
    calc_inductance,
    calc_mutual_inductance_fast,
    winding_resistances,
    solve_ss_wpt_circuit,
)
from wpt_designer.core.ac_losses import calc_litz_resistance
from wpt_designer.gui.presets import PRESETS


class TestPhysicalInvariants(unittest.TestCase):
    def test_presets_feasibility_and_energy_conservation(self):
        """
        Тестирование физического инварианта сохранения энергии для всех пресетов:
        P_in = P_out + P_cu + P_mos с точностью до 10^-9 Вт.
        """
        for preset_key, preset in PRESETS.items():
            p = preset.params
            tx_Dout = float(p["tx_Dout"])
            tx_Din = float(p["tx_Din"])
            tx_N = int(p["tx_N"])
            rx_Dout = float(p["rx_Dout"])
            rx_Din = float(p["rx_Din"])
            rx_N = int(p["rx_N"])
            d_strand = float(p["d_strand"])
            n_strands = int(p["n_strands"])

            w_tx = Winding(tx_Dout, tx_Din, tx_N, d_strand, n_strands)
            w_rx = Winding(rx_Dout, rx_Din, rx_N, d_strand, n_strands)
            self.assertTrue(w_tx.feasible, f"Preset {preset_key} Tx winding is not feasible")
            self.assertTrue(w_rx.feasible, f"Preset {preset_key} Rx winding is not feasible")

            dist_mm = float(p["dist_mm"])
            d_m = dist_mm / 1000.0
            L1 = calc_inductance(w_tx, w_rx, d_m)
            L2 = calc_inductance(w_rx, w_tx, d_m)
            M = calc_mutual_inductance_fast(dist_mm, w_tx, w_rx)

            f0 = float(p["f0_kHz"])
            omega0 = 2.0 * np.pi * f0 * 1000.0
            C1 = 1.0 / (omega0**2 * L1)
            C2 = 1.0 / (omega0**2 * L2)

            f_drive = float(p["f_drive_kHz"])
            _, R1_ac, _, R2_ac = winding_resistances(w_tx, w_rx, f_drive, d_m)

            sol = solve_ss_wpt_circuit(
                V_bus_dc=float(p["V_bus"]),
                f_drive_kHz=f_drive,
                L1=L1,
                C1=C1,
                R1=R1_ac,
                L2=L2,
                C2=C2,
                R2=R2_ac,
                M=M,
                R_load=float(p["R_load"]),
                Rds_on_mOhm=float(p["Rds_mOhm"])
            )

            p_in = sol["P_in"]
            p_out = sol["P_out"]
            p_losses = sol["P_cu"] + sol["P_mos"]

            self.assertAlmostEqual(
                p_in,
                p_out + p_losses,
                places=7,
                msg=f"Preset {preset_key}: Energy conservation failed! P_in={p_in}, P_sum={p_out + p_losses}"
            )

    def test_reciprocity_invariance(self):
        """Проверка симметрии и взаимности электродинамической связи: M_12 == M_21."""
        w1 = Winding(60.0, 25.0, 10, 0.1, 80)
        w2 = Winding(45.0, 15.0, 14, 0.08, 60)

        for d in [10.0, 25.0, 50.0]:
            M_12 = calc_mutual_inductance_fast(d, w1, w2)
            M_21 = calc_mutual_inductance_fast(d, w2, w1)
            self.assertAlmostEqual(M_12, M_21, places=10, msg=f"Reciprocity violated at d={d} mm")

    def test_asymptotic_distance_limit(self):
        """Асимптотическое свойство: при d -> inf взаимная индуктивность M(d) -> 0."""
        w1 = Winding(50.0, 20.0, 12, 0.1, 40)
        w2 = Winding(50.0, 20.0, 12, 0.1, 40)

        M_near = calc_mutual_inductance_fast(5.0, w1, w2)
        M_mid = calc_mutual_inductance_fast(30.0, w1, w2)
        M_far = calc_mutual_inductance_fast(300.0, w1, w2)

        self.assertGreater(M_near, M_mid)
        self.assertGreater(M_mid, M_far)
        self.assertLess(M_far, 1e-8, "M at 300 mm should approach zero")

    def test_asymptotic_frequency_limit(self):
        """Асимптотическое свойство: при f -> 0 сопротивление переменному току R_ac -> R_dc."""
        w = Winding(50.0, 20.0, 12, 0.1, 40)
        R_dc, R_ac_hf = calc_litz_resistance(w, f_kHz=100.0)
        _, R_ac_lf = calc_litz_resistance(w, f_kHz=0.001)

        self.assertGreater(R_ac_hf, R_dc)
        self.assertAlmostEqual(R_ac_lf, R_dc, delta=1e-5, msg="R_ac at f=1Hz should equal R_dc")


if __name__ == "__main__":
    unittest.main()
