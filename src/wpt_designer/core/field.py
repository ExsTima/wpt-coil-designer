"""
2D and 3D magnetic field calculation, flux stream function Psi, and phasor peak instant.
"""

from typing import Callable, List, Optional, Tuple
import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.special import ellipk, ellipe

from .constants import (
    MU_0,
    FERRITE_LEAK,
)
from .inductance import winding_sources
from .winding import Winding


def ferrite_shield_mask(Z_m: np.ndarray, d_m: float, H1: float, H2: float) -> np.ndarray:
    """Ослабление поля за ферритовыми экранами (z < -H1 и z > d + H2), качественная визуализация."""
    return np.where((Z_m < -H1) | (Z_m > d_m + H2), FERRITE_LEAK, 1.0)


def compute_2d_multi_turn_field(
    X: np.ndarray,
    Z: np.ndarray,
    radii_m: np.ndarray,
    sources: List[Tuple[np.ndarray, float]],
    I_turn: float = 1.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Поле B(x, z) в плоскости y=0 от витков и их ферритовых изображений.
    sources — список (z_массив_по_виткам, вес) из winding_sources(). Возвращает (Bx, Bz)
    для тока I_turn (по умолчанию 1 А).
    """
    Rho = np.maximum(np.abs(X)[None, :, :], 1e-6)
    R_c = np.asarray(radii_m)[:, None, None]
    Bx = np.zeros_like(X, dtype=float)
    Bz = np.zeros_like(X, dtype=float)

    for z_src, w in sources:
        Zeta = Z[None, :, :] - np.asarray(z_src, dtype=float)[:, None, None]
        alpha = np.maximum(R_c**2 + Rho**2 + Zeta**2 - 2.0 * R_c * Rho, 1e-12)
        beta = R_c**2 + Rho**2 + Zeta**2 + 2.0 * R_c * Rho
        m = np.clip(1.0 - alpha / beta, 0.0, 0.999999)
        K = ellipk(m)
        E = ellipe(m)
        C = (MU_0 * I_turn) / (2.0 * np.pi * np.sqrt(beta))
        Bz_all = C * (E * ((R_c**2 - Rho**2 - Zeta**2) / alpha) + K)
        Brho_all = C * (Zeta / Rho) * (E * ((R_c**2 + Rho**2 + Zeta**2) / alpha) - K)
        Bz += w * np.sum(Bz_all, axis=0)
        Bx += w * np.sum(Brho_all, axis=0) * np.sign(X)
    return Bx, Bz


def compute_flux_function_Psi(
    X_m: np.ndarray,
    Z_m: np.ndarray,
    radii_m: np.ndarray,
    sources: List[Tuple[np.ndarray, float]],
    I_eff: float
) -> np.ndarray:
    """
    Функция магнитного потока Psi(r, z) = r * A_phi(r, z) от витков и ферритовых изображений.
    Линии уровня Psi = const строго совпадают с силовыми линиями магнитного поля B,
    гарантируя их математическую непрерывность и замкнутость (div B = 0) без обрывов.
    """
    r = np.maximum(np.abs(X_m), 1e-6)
    Psi = np.zeros_like(X_m, dtype=float)
    R_c = np.asarray(radii_m)[:, None, None]
    for z_src, w in sources:
        Zeta = Z_m[None, :, :] - np.asarray(z_src, dtype=float)[:, None, None]
        denom = (R_c + r[None, :, :])**2 + Zeta**2
        m = np.clip(4.0 * R_c * r[None, :, :] / denom, 0.0, 0.999999)
        k_val = np.sqrt(m)
        K = ellipk(m)
        E = ellipe(m)
        term = np.where(k_val < 1e-7, 0.0, (1.0 - 0.5 * m) * K - E)
        C = (MU_0 * I_eff) / (np.pi * np.maximum(k_val, 1e-7))
        psi_loop = C * np.sqrt(R_c * r[None, :, :]) * term
        Psi += w * np.sum(psi_loop, axis=0)
    return Psi


def compute_2d_field_and_psi(
    X: np.ndarray,
    Z: np.ndarray,
    radii_m: np.ndarray,
    sources: List[Tuple[np.ndarray, float]],
    I_turn: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Совмещённый однопроходный расчёт (Bx, Bz, Psi) в плоскости y=0 на ток I_turn.
    Вычисляет эллиптические интегралы K(m), E(m) один раз на каждое изображение.
    """
    Rho = np.maximum(np.abs(X)[None, :, :], 1e-6)
    R_c = np.asarray(radii_m)[:, None, None]
    sgn_x = np.sign(X)
    Bx = np.zeros_like(X, dtype=float)
    Bz = np.zeros_like(X, dtype=float)
    Psi = np.zeros_like(X, dtype=float)

    for z_src, w in sources:
        Zeta = Z[None, :, :] - np.asarray(z_src, dtype=float)[:, None, None]
        alpha = np.maximum(R_c**2 + Rho**2 + Zeta**2 - 2.0 * R_c * Rho, 1e-12)
        beta = (R_c + Rho) ** 2 + Zeta**2
        m = np.clip(4.0 * R_c * Rho / beta, 0.0, 0.999999)
        K = ellipk(m)
        E = ellipe(m)

        C_b = (MU_0 * I_turn) / (2.0 * np.pi * np.sqrt(beta))
        Bz_all = C_b * (E * ((R_c**2 - Rho**2 - Zeta**2) / alpha) + K)
        Brho_all = C_b * (Zeta / Rho) * (E * ((R_c**2 + Rho**2 + Zeta**2) / alpha) - K)
        Bz += w * np.sum(Bz_all, axis=0)
        Bx += w * np.sum(Brho_all, axis=0) * sgn_x

        k_val = np.sqrt(m)
        term = np.where(k_val < 1e-7, 0.0, (1.0 - 0.5 * m) * K - E)
        C_psi = (MU_0 * I_turn) / (np.pi * np.maximum(k_val, 1e-7))
        psi_loop = C_psi * np.sqrt(R_c * Rho) * term
        Psi += w * np.sum(psi_loop, axis=0)

    return Bx, Bz, Psi


def compute_3d_multi_turn_field(
    X: np.ndarray,
    Y: np.ndarray,
    Z: np.ndarray,
    radii_m: np.ndarray,
    sources: List[Tuple[np.ndarray, float]],
    I_turn: float = 1.0,
    num_segments: int = 36
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Поле B(x, y, z) по закону Био-Савара-Лапласа от витков и их изображений."""
    phi = np.linspace(0, 2.0 * np.pi, num_segments, endpoint=False)
    dphi = 2.0 * np.pi / num_segments

    R_grid, Phi_grid = np.meshgrid(radii_m, phi, indexing='ij')
    shp = (1,) * np.ndim(X) + (-1,)
    xs = (R_grid * np.cos(Phi_grid)).ravel().reshape(shp)
    ys = (R_grid * np.sin(Phi_grid)).ravel().reshape(shp)
    dl_x = (-R_grid * np.sin(Phi_grid) * dphi).ravel().reshape(shp)
    dl_y = (R_grid * np.cos(Phi_grid) * dphi).ravel().reshape(shp)

    rx = X[..., None] - xs
    ry = Y[..., None] - ys
    const = (MU_0 * I_turn) / (4.0 * np.pi)

    Bx = np.zeros_like(X, dtype=float)
    By = np.zeros_like(X, dtype=float)
    Bz = np.zeros_like(X, dtype=float)
    for z_src, w in sources:
        z_seg = np.repeat(np.asarray(z_src, dtype=float), num_segments).reshape(shp)
        rz = Z[..., None] - z_seg
        r_mag = np.maximum(np.sqrt(rx**2 + ry**2 + rz**2), 1e-4)
        r_cube = r_mag**3
        Bx += w * const * np.sum((dl_y * rz) / r_cube, axis=-1)
        By += w * const * np.sum((-dl_x * rz) / r_cube, axis=-1)
        Bz += w * const * np.sum((dl_x * ry - dl_y * rx) / r_cube, axis=-1)
    return Bx, By, Bz


def phasor_field_magnitude(
    b_tx: List[np.ndarray],
    b_rx: List[np.ndarray],
    I1c: complex,
    I2c: complex
) -> np.ndarray:
    """Амплитуда (RMS-фазор) |B| от обоих контуров с учётом комплексных токов."""
    return np.sqrt(sum(np.abs(I1c * a + I2c * b)**2 for a, b in zip(b_tx, b_rx, strict=True)))


def field_at_peak_instant(
    b_tx: List[np.ndarray],
    b_rx: List[np.ndarray],
    I1c: complex,
    I2c: complex,
    n_t: int = 24
) -> List[np.ndarray]:
    """
    Компоненты мгновенного поля в тот момент периода, когда среднее |B| максимально.
    Так вклад Rx виден и на резонансе, где I2 сдвинут на 90° относительно I1.
    """
    best, best_val = None, -1.0
    for th in np.linspace(0.0, np.pi, n_t, endpoint=False):
        e = np.exp(1j * th)
        comps = [np.real((I1c * a + I2c * b) * e) for a, b in zip(b_tx, b_rx, strict=True)]
        val = float(np.mean(np.sqrt(sum(c**2 for c in comps))))
        if val > best_val:
            best, best_val = comps, val
    return best


def find_peak_phase_currents(
    lay_tx: Winding,
    lay_rx: Winding,
    d_m: float,
    src_tx: List[Tuple[np.ndarray, float]],
    src_rx: List[Tuple[np.ndarray, float]],
    I1c: complex,
    I2c: complex,
    n_t: int = 24,
) -> Tuple[float, float]:
    """
    Находит эффективные мгновенные токи (I1_eff, I2_eff) в момент периода,
    когда напряжённость поля в центре зазора максимальна (с гарантией I1_eff >= 0).
    """
    r_probe = max(1e-4, min(0.005, 0.25 * min(lay_tx.D_in_mm, lay_rx.D_in_mm) / 1000.0))
    rp = np.array([[r_probe]])
    zp = np.array([[d_m / 2.0]])
    bx_t0, bz_t0 = compute_2d_multi_turn_field(rp, zp, lay_tx.r, src_tx)
    bx_r0, bz_r0 = compute_2d_multi_turn_field(rp, zp, lay_rx.r, src_rx)

    th_opt, best_val = 0.0, -1.0
    for th in np.linspace(0.0, np.pi, n_t, endpoint=False):
        e = np.exp(1j * th)
        i1_r = np.real(I1c * e)
        i2_r = np.real(I2c * e)
        v_val = (
            (i1_r * bx_t0[0, 0] + i2_r * bx_r0[0, 0]) ** 2
            + (i1_r * bz_t0[0, 0] + i2_r * bz_r0[0, 0]) ** 2
        )
        if v_val > best_val:
            best_val = float(v_val)
            th_opt = float(th)

    e_opt = np.exp(1j * th_opt)
    I1_eff = float(np.real(I1c * e_opt))
    I2_eff = float(np.real(I2c * e_opt))
    if I1_eff < 0:
        I1_eff, I2_eff = -I1_eff, -I2_eff
    return I1_eff, I2_eff


class AxisymmetricField2D:
    """
    Предвычисленный осесимметричный 2D-интерполятор единичных токов (1 А) для пары катушек.
    Позволяет быстро пересчитывать (Bx, Bz, Psi) при смещении Rx Δx и смене токов
    без повторного вычисления эллиптических интегралов.
    """

    def __init__(
        self,
        lay_tx: Winding,
        lay_rx: Winding,
        d_m: float,
        rho_max_m: float,
        n_rho: int = 96,
        n_z: int = 110,
    ):
        self.d_m = float(d_m)
        self.rho_max_m = float(rho_max_m)
        z_half = self.d_m / 2.0 + max(0.025, lay_tx.H_m + 0.015, lay_rx.H_m + 0.015)
        self.z_min_m = self.d_m / 2.0 - z_half
        self.z_max_m = self.d_m / 2.0 + z_half

        rho_grid = np.linspace(0.0, self.rho_max_m, n_rho)
        z_grid = np.linspace(self.z_min_m, self.z_max_m, n_z)
        RHO, Z = np.meshgrid(rho_grid, z_grid, indexing="ij")

        src_tx = winding_sources(lay_tx, lay_rx, self.d_m, "tx")
        br_tx, bz_tx, psi_tx = compute_2d_field_and_psi(RHO, Z, lay_tx.r, src_tx, I_turn=1.0)

        if lay_tx.same_geometry(lay_rx):
            br_rx = -br_tx[:, ::-1]
            bz_rx = bz_tx[:, ::-1]
            psi_rx = psi_tx[:, ::-1]
        else:
            src_rx = winding_sources(lay_tx, lay_rx, self.d_m, "rx")
            br_rx, bz_rx, psi_rx = compute_2d_field_and_psi(RHO, Z, lay_rx.r, src_rx, I_turn=1.0)

        self._tx_br = RectBivariateSpline(rho_grid, z_grid, br_tx)
        self._tx_bz = RectBivariateSpline(rho_grid, z_grid, bz_tx)
        self._tx_psi = RectBivariateSpline(rho_grid, z_grid, psi_tx)
        self._rx_br = RectBivariateSpline(rho_grid, z_grid, br_rx)
        self._rx_bz = RectBivariateSpline(rho_grid, z_grid, bz_rx)
        self._rx_psi = RectBivariateSpline(rho_grid, z_grid, psi_rx)

    def eval_grid(
        self,
        X: np.ndarray,
        Z: np.ndarray,
        dx_m: float,
    ) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray], np.ndarray, np.ndarray]:
        """Возвращает ((Bx_tx, Bz_tx), (Bx_rx, Bz_rx), Psi_tx_unit, Psi_rx_unit) на сетке (X, Z)."""
        x_flat = X.ravel()
        z_flat = np.clip(Z.ravel(), self.z_min_m, self.z_max_m)

        rho_tx = np.clip(np.abs(x_flat), 0.0, self.rho_max_m)
        sgn_tx = np.sign(x_flat)
        bx_tx = (self._tx_br.ev(rho_tx, z_flat) * sgn_tx).reshape(X.shape)
        bz_tx = self._tx_bz.ev(rho_tx, z_flat).reshape(X.shape)
        psi_tx = self._tx_psi.ev(rho_tx, z_flat).reshape(X.shape)

        x_rx = x_flat - dx_m
        rho_rx = np.clip(np.abs(x_rx), 0.0, self.rho_max_m)
        sgn_rx = np.sign(x_rx)
        bx_rx = (self._rx_br.ev(rho_rx, z_flat) * sgn_rx).reshape(X.shape)
        bz_rx = self._rx_bz.ev(rho_rx, z_flat).reshape(X.shape)
        psi_rx = self._rx_psi.ev(rho_rx, z_flat).reshape(X.shape)

        return (bx_tx, bz_tx), (bx_rx, bz_rx), psi_tx, psi_rx


class Field3DInterpolator:
    """
    Быстрая 3D-интерполяция осесимметричных компонент поля Tx и Rx с учётом
    бокового смещения dx_m и мгновенных токов на базе сплайнов единичного тока.
    """

    def __init__(
        self,
        lay_tx: Winding,
        lay_rx: Winding,
        d_m: float,
        dx_m: float,
        I1_eff: float,
        I2_eff: float,
        grid_size: int = 45,
        src_tx: Optional[List[Tuple[np.ndarray, float]]] = None,
        src_rx: Optional[List[Tuple[np.ndarray, float]]] = None,
    ):
        self.d_m = float(d_m)
        self.dx_m = float(dx_m)
        self.I1_eff = float(I1_eff)
        self.I2_eff = float(I2_eff)

        r_max_coil = max(lay_tx.D_out_mm, lay_rx.D_out_mm) / 2000.0
        self.rho_max_m = max(0.075, r_max_coil * 3.0)
        z_half = self.d_m / 2.0 + max(0.025, lay_tx.H_m + 0.018, lay_rx.H_m + 0.018)
        self.z_min_m = self.d_m / 2.0 - z_half
        self.z_max_m = self.d_m / 2.0 + z_half

        if src_tx is None:
            src_tx = winding_sources(lay_tx, lay_rx, self.d_m, "tx")

        rho_grid = np.linspace(0.0005, self.rho_max_m, grid_size)
        z_grid = np.linspace(self.z_min_m, self.z_max_m, grid_size)
        RHO, Z = np.meshgrid(rho_grid, z_grid, indexing="ij")

        shield = ferrite_shield_mask(Z, self.d_m, lay_tx.H_m, lay_rx.H_m)
        br_tx, bz_tx = compute_2d_multi_turn_field(RHO, Z, lay_tx.r, src_tx)
        br_tx_s = br_tx * shield
        bz_tx_s = bz_tx * shield

        if lay_tx.same_geometry(lay_rx):
            br_rx_s = -br_tx_s[:, ::-1]
            bz_rx_s = bz_tx_s[:, ::-1]
        else:
            if src_rx is None:
                src_rx = winding_sources(lay_tx, lay_rx, self.d_m, "rx")
            br_rx, bz_rx = compute_2d_multi_turn_field(RHO, Z, lay_rx.r, src_rx)
            br_rx_s = br_rx * shield
            bz_rx_s = bz_rx * shield

        self._spline_tx_br = RectBivariateSpline(rho_grid, z_grid, br_tx_s)
        self._spline_tx_bz = RectBivariateSpline(rho_grid, z_grid, bz_tx_s)
        self._spline_rx_br = RectBivariateSpline(rho_grid, z_grid, br_rx_s)
        self._spline_rx_bz = RectBivariateSpline(rho_grid, z_grid, bz_rx_s)

    def set_state(self, dx_m: float, I1_eff: float, I2_eff: float) -> None:
        """Обновляет сдвиг Δx и масштабирующие токи без пересчёта сплайнов единичного поля."""
        self.dx_m = float(dx_m)
        self.I1_eff = float(I1_eff)
        self.I2_eff = float(I2_eff)

    def eval_B(self, x: float, y: float, z: float) -> np.ndarray:
        """Возвращает вектор B = [Bx, By, Bz] (Тл) в точке (x, y, z) в метрах."""
        rho_hi = self.rho_max_m * 0.96
        z_lo = self.z_min_m * 0.9
        z_hi = self.z_max_m * 0.95

        r1 = float(np.sqrt(x**2 + y**2))
        r1_c = float(np.clip(r1, 0.0006, rho_hi))
        z_c = float(np.clip(z, z_lo, z_hi))
        br1 = self.I1_eff * float(self._spline_tx_br.ev(r1_c, z_c))
        bz1 = self.I1_eff * float(self._spline_tx_bz.ev(r1_c, z_c))
        bx1 = br1 * (x / (r1 + 1e-9))
        by1 = br1 * (y / (r1 + 1e-9))

        r2 = float(np.sqrt((x - self.dx_m) ** 2 + y**2))
        r2_c = float(np.clip(r2, 0.0006, rho_hi))
        br2 = self.I2_eff * float(self._spline_rx_br.ev(r2_c, z_c))
        bz2 = self.I2_eff * float(self._spline_rx_bz.ev(r2_c, z_c))
        bx2 = br2 * ((x - self.dx_m) / (r2 + 1e-9))
        by2 = br2 * (y / (r2 + 1e-9))
        return np.array([bx1 + bx2, by1 + by2, bz1 + bz2], dtype=float)

    def eval_B_batch(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Векторизованный расчёт векторов B формы (N, 3) для массивов координат."""
        rho_hi = self.rho_max_m * 0.96
        z_lo = self.z_min_m * 0.9
        z_hi = self.z_max_m * 0.95

        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)
        z_c = np.clip(np.asarray(z, dtype=float), z_lo, z_hi)

        r1 = np.sqrt(x_arr**2 + y_arr**2)
        r1_c = np.clip(r1, 0.0006, rho_hi)
        br1 = self.I1_eff * self._spline_tx_br.ev(r1_c, z_c)
        bz1 = self.I1_eff * self._spline_tx_bz.ev(r1_c, z_c)
        inv_r1 = 1.0 / (r1 + 1e-9)
        bx1 = br1 * x_arr * inv_r1
        by1 = br1 * y_arr * inv_r1

        dx_x = x_arr - self.dx_m
        r2 = np.sqrt(dx_x**2 + y_arr**2)
        r2_c = np.clip(r2, 0.0006, rho_hi)
        br2 = self.I2_eff * self._spline_rx_br.ev(r2_c, z_c)
        bz2 = self.I2_eff * self._spline_rx_bz.ev(r2_c, z_c)
        inv_r2 = 1.0 / (r2 + 1e-9)
        bx2 = br2 * dx_x * inv_r2
        by2 = br2 * y_arr * inv_r2

        return np.column_stack((bx1 + bx2, by1 + by2, bz1 + bz2))

    def __call__(self, x: float, y: float, z: float) -> np.ndarray:
        return self.eval_B(x, y, z)


def trace_streamlines_batch_3d(
    field_interp: Field3DInterpolator,
    seeds_arr: np.ndarray,
    ds: float = 0.0008,
    n_steps: int = 90,
    direction: int = 1,
    xy_bound_m: float = 0.052,
    z_min_m: float = -0.013,
    z_max_m: float = 0.030,
) -> List[np.ndarray]:
    """Векторизованно интегрирует пакет 3D силовых линий методом RK4."""
    seeds = np.asarray(seeds_arr, dtype=float)
    n_lines = len(seeds)
    if n_lines == 0:
        return []

    traj = np.empty((n_steps + 1, n_lines, 3), dtype=float)
    traj[0] = seeds
    lengths = np.ones(n_lines, dtype=int)
    active = np.ones(n_lines, dtype=bool)

    def _rk_stage(pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        vec = field_interp.eval_B_batch(pts[:, 0], pts[:, 1], pts[:, 2])
        nrm = np.linalg.norm(vec, axis=1)
        ok = nrm >= 1e-12
        safe_nrm = np.where(ok, nrm, 1.0)[:, None]
        return (direction * vec) / safe_nrm, ok

    for step in range(n_steps):
        idx = np.flatnonzero(active)
        if idx.size == 0:
            break
        curr = traj[step, idx]

        k1, ok1 = _rk_stage(curr)
        k2, ok2 = _rk_stage(curr + 0.5 * ds * k1)
        k3, ok3 = _rk_stage(curr + 0.5 * ds * k2)
        k4, ok4 = _rk_stage(curr + ds * k3)

        ok = ok1 & ok2 & ok3 & ok4
        if not np.all(ok):
            active[idx[~ok]] = False
        idx_ok = idx[ok]
        if idx_ok.size == 0:
            continue

        nxt = curr[ok] + (ds / 6.0) * (k1[ok] + 2.0 * k2[ok] + 2.0 * k3[ok] + k4[ok])
        traj[step + 1, idx_ok] = nxt
        lengths[idx_ok] += 1

        oob = (
            (np.abs(nxt[:, 0]) > xy_bound_m)
            | (np.abs(nxt[:, 1]) > xy_bound_m)
            | (nxt[:, 2] < z_min_m)
            | (nxt[:, 2] > z_max_m)
        )
        if np.any(oob):
            active[idx_ok[oob]] = False

    return [traj[: lengths[i], i].copy() for i in range(n_lines)]


def trace_streamline_3d(
    field_eval: Callable[[float, float, float], np.ndarray],
    p0: np.ndarray,
    ds: float = 0.0008,
    n_steps: int = 90,
    direction: int = 1,
    xy_bound_m: float = 0.052,
    z_min_m: float = -0.013,
    z_max_m: float = 0.030,
) -> np.ndarray:
    """Интегрирует 3D силовую линию магнитного поля методом Рунге-Кутты 4-го порядка (RK4)."""
    pts = [np.asarray(p0, dtype=float).copy()]
    curr = pts[0].copy()
    for _ in range(n_steps):
        v1 = field_eval(curr[0], curr[1], curr[2])
        norm1 = float(np.linalg.norm(v1))
        if norm1 < 1e-12:
            break
        k1 = direction * v1 / norm1

        p2 = curr + 0.5 * ds * k1
        v2 = field_eval(p2[0], p2[1], p2[2])
        norm2 = float(np.linalg.norm(v2))
        if norm2 < 1e-12:
            break
        k2 = direction * v2 / norm2

        p3 = curr + 0.5 * ds * k2
        v3 = field_eval(p3[0], p3[1], p3[2])
        norm3 = float(np.linalg.norm(v3))
        if norm3 < 1e-12:
            break
        k3 = direction * v3 / norm3

        p4 = curr + ds * k3
        v4 = field_eval(p4[0], p4[1], p4[2])
        norm4 = float(np.linalg.norm(v4))
        if norm4 < 1e-12:
            break
        k4 = direction * v4 / norm4

        curr = curr + (ds / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        pts.append(curr.copy())
        if (
            abs(curr[0]) > xy_bound_m
            or abs(curr[1]) > xy_bound_m
            or curr[2] < z_min_m
            or curr[2] > z_max_m
        ):
            break
    return np.array(pts, dtype=float)
