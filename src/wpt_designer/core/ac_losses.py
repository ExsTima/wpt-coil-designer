"""
High-frequency AC resistance, skin effect, and proximity effect calculations
using Kelvin functions (ber, bei) and 2D magnetic field loops.
"""

from typing import Tuple
import numpy as np
from scipy.special import ellipk, ellipe, ber, bei, berp, beip

from .constants import (
    MU_0,
    RHO_CU,
    FERRITE_REFLECT,
)
from .winding import Winding
from .inductance import image_ops


def skin_factor(xi: float) -> float:
    """
    Точный коэффициент R_ac/R_dc круглой жилы от скин-эффекта (функции Кельвина),
    xi = r_жилы / delta. Для xi < 0.05 — разложение, для xi > 35 — асимптотика.
    """
    if xi < 0.05:
        return 1.0 + xi**4 / 48.0
    x = np.sqrt(2.0) * xi
    if x > 50.0:
        return xi / 2.0 + 0.25
    num = ber(x) * beip(x) - bei(x) * berp(x)
    den = berp(x)**2 + beip(x)**2
    return float((x / 2.0) * num / den)


def _loop_field_matrix(rp: np.ndarray, zp: np.ndarray, rj: np.ndarray, zj: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """B_rho, B_z (Тл на 1 А) в точках (rp[i], zp[i]) от витков (rj[j], zj[j]): матрицы (P, S)."""
    Rho = np.maximum(np.asarray(rp, dtype=float)[:, None], 1e-6)
    Rc = np.asarray(rj, dtype=float)[None, :]
    Zeta = np.asarray(zp, dtype=float)[:, None] - np.asarray(zj, dtype=float)[None, :]
    alpha = np.maximum(Rc**2 + Rho**2 + Zeta**2 - 2.0 * Rc * Rho, 1e-12)
    beta = Rc**2 + Rho**2 + Zeta**2 + 2.0 * Rc * Rho
    m = np.clip(1.0 - alpha / beta, 0.0, 0.999999)
    K, E = ellipk(m), ellipe(m)
    C = MU_0 / (2.0 * np.pi * np.sqrt(beta))
    Bz = C * (E * ((Rc**2 - Rho**2 - Zeta**2) / alpha) + K)
    Brho = C * (Zeta / Rho) * (E * ((Rc**2 + Rho**2 + Zeta**2) / alpha) - K)
    return Brho, Bz


def _loop_field_batch(
    rp: np.ndarray,
    zp: np.ndarray,
    rj: np.ndarray,
    zj_2d: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Пакетный расчёт (B_rho, B_z) формы (I, P, S) от изображений zj_2d формы (I, S)."""
    Rho = np.maximum(np.asarray(rp, dtype=float)[None, :, None], 1e-6)
    Rc = np.asarray(rj, dtype=float)[None, None, :]
    Zeta = np.asarray(zp, dtype=float)[None, :, None] - np.asarray(zj_2d, dtype=float)[:, None, :]
    alpha = np.maximum(Rc**2 + Rho**2 + Zeta**2 - 2.0 * Rc * Rho, 1e-12)
    beta = Rc**2 + Rho**2 + Zeta**2 + 2.0 * Rc * Rho
    m = np.clip(1.0 - alpha / beta, 0.0, 0.999999)
    K, E = ellipk(m), ellipe(m)
    C = MU_0 / (2.0 * np.pi * np.sqrt(beta))
    Bz = C * (E * ((Rc**2 - Rho**2 - Zeta**2) / alpha) + K)
    Brho = C * (Zeta / Rho) * (E * ((Rc**2 + Rho**2 + Zeta**2) / alpha) - K)
    return Brho, Bz


def proximity_geometry(w1: Winding, w2: Winding, d_m: float) -> float:
    """
    Геометрический фактор эффекта близости K = sum_i l_i * <B_i^2>  [м * Тл^2 / А^2]:
    поле в центре каждого витка w1 от ВСЕХ ОСТАЛЬНЫХ витков этой же обмотки и от их
    ферритовых изображений (на 1 А RMS) плюс поле собственного пучка (равномерный ток по
    радиусу пучка: <B^2> = mu0^2 / (8 pi^2 a^2)). Поле второй обмотки не учитывается.
    Результат кэшируется в обмотке.
    """
    d_eff = max(float(d_m), 1e-4)
    key = (round(d_eff, 7), FERRITE_REFLECT, round(w2.H_m, 9))
    cache = w1._prox_cache
    if key in cache:
        return cache[key]
    r, z = w1.r, w1.z
    if w1._prox_self_cache is None:
        Br0, Bz0 = _loop_field_matrix(r, z, r, z)
        np.fill_diagonal(Br0, 0.0)
        np.fill_diagonal(Bz0, 0.0)
        w1._prox_self_cache = (Br0.sum(axis=1), Bz0.sum(axis=1))
    Bsum_r = w1._prox_self_cache[0].copy()
    Bsum_z = w1._prox_self_cache[1].copy()

    ops = image_ops(d_eff, w1.H_m, w2.H_m)[1:]
    if ops:
        signs = np.array([op[0] for op in ops], dtype=float)[:, None]
        shifts = np.array([op[1] for op in ops], dtype=float)[:, None]
        weights = np.array([op[2] for op in ops], dtype=float)[:, None]
        zj_2d = signs * z[None, :] + shifts
        Br_img, Bz_img = _loop_field_batch(r, z, r, zj_2d)
        Bsum_r += np.sum(weights * Br_img.sum(axis=2), axis=0)
        Bsum_z += np.sum(weights * Bz_img.sum(axis=2), axis=0)

    a = w1.D_wire_m / 2.0
    B2_int = MU_0**2 / (8.0 * np.pi**2 * a**2)
    turn_lengths = 2.0 * np.pi * r
    K_geo = float(np.sum(turn_lengths * (Bsum_r**2 + Bsum_z**2 + B2_int)))
    cache[key] = K_geo
    return K_geo


def calc_litz_resistance(w: Winding, f_kHz: float, K_prox: float = 0.0) -> Tuple[float, float]:
    """
    Активное сопротивление обмотки из литцендрата (w — объект Winding):
    - R_dc: реальная длина провода (сумма длин всех витков) / суммарное сечение жил;
    - скин-эффект жилы: точное решение (функции Кельвина);
    - эффект близости: потери вихревых токов в жилах в поперечном поле,
      P' = n*pi*w^2*d^4*B_rms^2 / (64*rho) на единицу длины (приближение низких частот,
      d << delta), поле — из proximity_geometry (K_prox). Для xi > 1 вводится сглаживающий
      множитель 1/(1 + 0.1*xi^2).
    """
    r_s = w.d_strand_mm / 2000.0
    f = f_kHz * 1000.0
    if r_s <= 0 or f <= 0 or w.N <= 0 or w.n_strands <= 0:
        return 0.0, 0.0

    total_area = w.n_strands * (np.pi * (r_s**2))
    R_dc = RHO_CU * w.length_m / total_area

    delta = np.sqrt(RHO_CU / (np.pi * f * MU_0))
    xi = r_s / delta
    omega = 2.0 * np.pi * f
    R_prox = (w.n_strands * np.pi * omega**2 * (2.0 * r_s)**4 / (64.0 * RHO_CU)) * K_prox / (1.0 + 0.1 * xi**2)
    R_ac = R_dc * skin_factor(xi) + R_prox
    return float(R_dc), float(R_ac)


def winding_resistances(w1: Winding, w2: Winding, f_kHz: float, d_m: float) -> Tuple[float, float, float, float]:
    """R_dc и R_ac обеих обмоток на частоте f при осевом зазоре d: (R1_dc, R1_ac, R2_dc, R2_ac)."""
    R1_dc, R1_ac = calc_litz_resistance(w1, f_kHz, proximity_geometry(w1, w2, d_m))
    if w1.same_geometry(w2):
        return R1_dc, R1_ac, R1_dc, R1_ac
    R2_dc, R2_ac = calc_litz_resistance(w2, f_kHz, proximity_geometry(w2, w1, d_m))
    return R1_dc, R1_ac, R2_dc, R2_ac


def calc_Q(L: float, R: float, f_kHz: float) -> float:
    """Добротность колебательного контура Q = (2 * pi * f * L) / R."""
    if R <= 0 or L <= 0 or f_kHz <= 0:
        return 0.0
    omega = 2.0 * np.pi * f_kHz * 1000.0
    return float(omega * L / R)
