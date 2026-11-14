"""
Unit tests for simulation orchestration, frequency/distance sweeps,
3D field interpolation/streamline tracing, report formatting, and preset invariants.
"""

import unittest
import numpy as np

from wpt_designer.core import (
    AxisymmetricField2D,
    Field3DInterpolator,
    calc_critical_coupling,
    compute_2d_field_and_psi,
    compute_2d_multi_turn_field,
    compute_distance_sweep,
    compute_distance_table,
    compute_flux_function_Psi,
    compute_frequency_sweep,
    find_peak_phase_currents,
    format_markdown_report,
    run_wpt_simulation,
    solve_ss_frequency_sweep,
    solve_ss_wpt_circuit,
    trace_streamline_3d,
    trace_streamlines_batch_3d,
    winding_resistances,
    winding_sources,
)
from wpt_designer.gui.presets import PRESETS


class TestSimulationAndField3D(unittest.TestCase):
    def _default_sim(self, **overrides):
        params = dict(
            tx_Dout=50.0,
            tx_Din=20.0,
            tx_N=12,
            rx_Dout=50.0,
            rx_Din=20.0,
            rx_N=12,
            d_strand=0.10,
            n_strands=100,
            V_bus=5.0,
            Rds_mOhm=18.0,
            R_load=10.0,
            f0_kHz=120.0,
            f_drive_kHz=120.0,
            dist_mm=10.0,
            auto_track=False,
        )
        params.update(overrides)
        return run_wpt_simulation(**params)

    def test_run_wpt_simulation_valid_and_invalid(self):
        res = self._default_sim()
        self.assertIn("L1", res)
        self.assertIn("circuit", res)
        self.assertGreater(res["circuit"]["P_out"], 0.0)

        with self.assertRaises(ValueError):
            self._default_sim(tx_Dout=15.0, tx_Din=20.0)

        with self.assertRaises(ValueError):
            self._default_sim(dist_mm=0.2)

    def test_distance_sweep_and_table(self):
        res = self._default_sim()
        sweep = compute_distance_sweep(res, auto_track=False, d_max_mm=40.0, num_points=20)
        self.assertEqual(len(sweep["d_mm"]), 20)
        self.assertTrue(np.all(np.isfinite(sweep["eta_pct"])))
        self.assertTrue(np.all(sweep["k"] >= 0.0))

        table = compute_distance_table(res, auto_track=False, d_max_mm=30)
        self.assertGreater(len(table), 5)
        self.assertEqual(
            set(table[0].keys()),
            {"d_mm", "k", "eta_pct", "Pout_W", "Ploss_W", "Vout_V"},
        )

    def test_frequency_sweep_matches_scalar_solver(self):
        res = self._default_sim()
        sweep = compute_frequency_sweep(res, d_mm=10.0, num_points=25)
        f_span = sweep["f_span"]
        pout_sweep = sweep["pout_W"]
        eta_sweep = sweep["eta_pct"]

        d_m = res["dist_mm"] / 1000.0
        for idx in (0, len(f_span) // 2, len(f_span) - 1):
            f_k = float(f_span[idx])
            _, r1, _, r2 = winding_resistances(res["lay_tx"], res["lay_rx"], f_k, d_m)
            sol = solve_ss_wpt_circuit(
                res["V_bus"],
                f_k,
                res["L1"],
                res["C1"],
                r1,
                res["L2"],
                res["C2"],
                r2,
                res["M"],
                res["R_load"],
                res["Rds_mOhm"],
            )
            self.assertAlmostEqual(float(pout_sweep[idx]), sol["P_out"], places=8)
            self.assertAlmostEqual(float(eta_sweep[idx]), sol["eta"] * 100.0, places=8)

        # Direct check for zero-determinant protection
        p0, e0 = solve_ss_frequency_sweep(
            12.0,
            np.array([100.0]),
            10e-6,
            1.0 / ((2.0 * np.pi * 100e3) ** 2 * 10e-6),
            np.array([0.0]),
            10e-6,
            1.0 / ((2.0 * np.pi * 100e3) ** 2 * 10e-6),
            np.array([0.0]),
            0.0,
            0.0,
            0.0,
        )
        self.assertEqual(float(p0[0]), 0.0)
        self.assertEqual(float(e0[0]), 0.0)

    def test_field_3d_interpolator_and_streamlines_standard_and_ev(self):
        for preset_key in ("qi_5w", "ev_3kw"):
            p = PRESETS[preset_key].params
            res = run_wpt_simulation(
                tx_Dout=float(p["tx_Dout"]),
                tx_Din=float(p["tx_Din"]),
                tx_N=int(p["tx_N"]),
                rx_Dout=float(p["rx_Dout"]),
                rx_Din=float(p["rx_Din"]),
                rx_N=int(p["rx_N"]),
                d_strand=float(p["d_strand"]),
                n_strands=int(p["n_strands"]),
                V_bus=float(p["V_bus"]),
                Rds_mOhm=float(p["Rds_mOhm"]),
                R_load=float(p["R_load"]),
                f0_kHz=float(p["f0_kHz"]),
                f_drive_kHz=float(p["f_drive_kHz"]),
                dist_mm=float(p["dist_mm"]),
                auto_track=PRESETS[preset_key].auto_track,
            )
            lay_tx, lay_rx = res["lay_tx"], res["lay_rx"]
            d_m = res["dist_mm"] / 1000.0
            src_tx = winding_sources(lay_tx, lay_rx, d_m, "tx")
            src_rx = winding_sources(lay_tx, lay_rx, d_m, "rx")
            I1_eff, I2_eff = find_peak_phase_currents(
                lay_tx,
                lay_rx,
                d_m,
                src_tx,
                src_rx,
                res["circuit"]["I1_c"],
                res["circuit"]["I2_c"],
            )
            self.assertGreaterEqual(I1_eff, 0.0)

            interp = Field3DInterpolator(
                lay_tx, lay_rx, d_m, 0.0, I1_eff, I2_eff, grid_size=25, src_tx=src_tx, src_rx=src_rx
            )
            r_max_m = max(lay_tx.D_out_mm, lay_rx.D_out_mm) / 2000.0
            seeds = np.array(
                [
                    [0.28 * r_max_m, 0.0, d_m / 2.0],
                    [0.48 * r_max_m, 0.1 * r_max_m, d_m / 2.0],
                ],
                dtype=float,
            )
            ds_m = r_max_m * 0.032
            xy_b = r_max_m * 2.1
            batch_pts = trace_streamlines_batch_3d(
                interp,
                seeds,
                ds=ds_m,
                n_steps=20,
                direction=1,
                xy_bound_m=xy_b,
                z_min_m=-0.05,
                z_max_m=d_m + 0.05,
            )
            for idx, p0 in enumerate(seeds):
                pts = trace_streamline_3d(
                    interp.eval_B,
                    p0,
                    ds=ds_m,
                    n_steps=20,
                    direction=1,
                    xy_bound_m=xy_b,
                    z_min_m=-0.05,
                    z_max_m=d_m + 0.05,
                )
                self.assertGreater(len(pts), 1)
                self.assertTrue(np.all(np.isfinite(pts)))
                self.assertEqual(batch_pts[idx].shape, pts.shape)
                self.assertTrue(np.allclose(batch_pts[idx], pts, atol=1e-10, rtol=1e-10))

            # Verify set_state updates dx_m and currents cleanly
            interp.set_state(0.005, I1_eff * 0.5, I2_eff * 0.5)
            b_shifted = interp.eval_B(0.005, 0.0, d_m / 2.0)
            self.assertTrue(np.all(np.isfinite(b_shifted)))

    def test_2d_field_and_psi_and_axisymmetric_cache(self):
        res = self._default_sim()
        lay_tx, lay_rx = res["lay_tx"], res["lay_rx"]
        d_m = res["dist_mm"] / 1000.0
        src_tx = winding_sources(lay_tx, lay_rx, d_m, "tx")
        src_rx = winding_sources(lay_tx, lay_rx, d_m, "rx")

        x = np.linspace(-0.04, 0.04, 25)
        z = np.linspace(0.002, d_m - 0.002, 15)
        X, Z = np.meshgrid(x, z)

        bx_ref, bz_ref = compute_2d_multi_turn_field(X, Z, lay_tx.r, src_tx, I_turn=1.0)
        psi_ref = compute_flux_function_Psi(X, Z, lay_tx.r, src_tx, I_eff=1.0)
        bx_fast, bz_fast, psi_fast = compute_2d_field_and_psi(X, Z, lay_tx.r, src_tx, I_turn=1.0)

        self.assertLess(float(np.max(np.abs(bx_fast - bx_ref))), 1e-12)
        self.assertLess(float(np.max(np.abs(bz_fast - bz_ref))), 1e-12)
        self.assertLess(float(np.max(np.abs(psi_fast - psi_ref))), 1e-12)

        field2d = AxisymmetricField2D(lay_tx, lay_rx, d_m, rho_max_m=0.06)
        (bx_t, bz_t), (bx_r, bz_r), psi_t, psi_r = field2d.eval_grid(X, Z, dx_m=0.0)
        bx_r_ref, bz_r_ref, psi_r_ref = compute_2d_field_and_psi(X, Z, lay_rx.r, src_rx, I_turn=1.0)

        # Symmetry check at x = 0 (center column)
        center_col = len(x) // 2
        self.assertAlmostEqual(float(np.max(np.abs(bx_t[:, center_col]))), 0.0, places=10)
        self.assertAlmostEqual(float(np.max(np.abs(bx_r[:, center_col]))), 0.0, places=10)

        # Relative agreement in the air gap
        rel_err_bz = np.max(np.abs(bz_t - bz_ref)) / np.max(np.abs(bz_ref))
        rel_err_rx = np.max(np.abs(bz_r - bz_r_ref)) / np.max(np.abs(bz_r_ref))
        rel_err_psi = np.max(np.abs(psi_r - psi_r_ref)) / np.max(np.abs(psi_r_ref))
        self.assertLess(rel_err_bz, 0.02)
        self.assertLess(rel_err_rx, 0.02)
        self.assertLess(rel_err_psi, 0.02)

    def test_critical_coupling_consistency(self):
        kc = calc_critical_coupling(25e-6, 0.15, 25e-6, 4.2, 100.0)
        self.assertGreater(kc, 0.05)
        self.assertLess(kc, 0.99)

    def test_exact_resonance_phase_non_negative(self):
        for preset_key in ("qi_5w", "femm_bench", "implant_1m"):
            preset = PRESETS[preset_key]
            p = preset.params
            res = run_wpt_simulation(
                tx_Dout=float(p["tx_Dout"]),
                tx_Din=float(p["tx_Din"]),
                tx_N=int(p["tx_N"]),
                rx_Dout=float(p["rx_Dout"]),
                rx_Din=float(p["rx_Din"]),
                rx_N=int(p["rx_N"]),
                d_strand=float(p["d_strand"]),
                n_strands=int(p["n_strands"]),
                V_bus=float(p["V_bus"]),
                Rds_mOhm=float(p["Rds_mOhm"]),
                R_load=float(p["R_load"]),
                f0_kHz=float(p["f0_kHz"]),
                f_drive_kHz=float(p["f_drive_kHz"]),
                dist_mm=float(p["dist_mm"]),
                auto_track=preset.auto_track,
            )
            self.assertEqual(res["circuit"]["phase_deg"], 0.0, f"{preset_key} phase should clamp to 0.0")
            self.assertGreaterEqual(res["circuit"]["phase_deg"], 0.0)

    def test_format_markdown_report(self):
        res = self._default_sim()
        report = format_markdown_report(res, version="2.0.0")
        self.assertIn("WPT Coil Designer & Analyzer v2.0.0", report)
        self.assertIn("Инвариант сохранения энергии", report)

    def test_presets_schema_and_ev_description(self):
        for key, preset in PRESETS.items():
            self.assertIsInstance(preset.auto_track, bool, f"{key}: auto_track must be bool")
            for param_key, param_val in preset.params.items():
                self.assertIsInstance(param_val, str, f"{key}.{param_key} must be str")

        self.assertIn("80 мм", PRESETS["ev_3kw"].description)
        self.assertEqual(PRESETS["ev_3kw"].params["dist_mm"], "80.0")


if __name__ == "__main__":
    unittest.main()
