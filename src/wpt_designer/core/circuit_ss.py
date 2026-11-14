"""
SS-resonance circuit solver (First Harmonic Approximation), bifurcation analysis,
optimal frequency tracking, and power/efficiency calculations.
"""

from typing import Dict, Any, Tuple
import numpy as np
from scipy.signal import find_peaks


def calc_coupling(M: float, L1: float, L2: float) -> float:
    """Коэффициент магнитной связи k = M / sqrt(L1 * L2)."""
    if L1 <= 0 or L2 <= 0:
        return 0.0
    k = M / np.sqrt(L1 * L2)
    return float(np.clip(k, 0.0, 0.999))


def _count_peaks(P: np.ndarray) -> int:
    return int(np.sum((P[1:-1] > P[:-2]) & (P[1:-1] >= P[2:])))


def calc_critical_coupling(L1: float, R1_tot: float, L2: float, R2_tot: float, f0_kHz: float) -> float:
    """
    Критический коэффициент связи бифуркации: наименьшее k, при котором АЧХ
    выходного тока SS-системы становится двугорбой (определяется численно для
    той же схемы замещения, что и решатель; пригодно при любых Q1, Q2).
    Возвращает 1.0, если расщепления нет при любом k < 1.
    """
    omega0 = 2.0 * np.pi * f0_kHz * 1000.0
    if L1 <= 0 or L2 <= 0 or omega0 <= 0:
        return 0.0
    C1 = 1.0 / (omega0**2 * L1)
    C2 = 1.0 / (omega0**2 * L2)
    # логарифмическая сетка: верхний пик при k -> 1 уходит далеко от f0 (f0/sqrt(1-k))
    w = omega0 * np.exp(np.linspace(np.log(0.3), np.log(12.0), 2001))
    Z1 = R1_tot + 1j * (w * L1 - 1.0 / (w * C1))
    Z2 = R2_tot + 1j * (w * L2 - 1.0 / (w * C2))
    Z1_Z2 = Z1 * Z2
    re_z1z2 = np.real(Z1_Z2)
    im_z1z2_sq = np.imag(Z1_Z2) ** 2
    w2_L1L2 = (w ** 2) * (L1 * L2)

    def n_peaks(k_val: float) -> int:
        k2_term = (k_val ** 2) * w2_L1L2
        return _count_peaks(w2_L1L2 / ((re_z1z2 + k2_term) ** 2 + im_z1z2_sq))

    k_max = 0.99
    if n_peaks(k_max) < 2:
        return 1.0
    lo, hi = 1e-4, k_max
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        if n_peaks(mid) >= 2:
            hi = mid
        else:
            lo = mid
    return float(hi)


def calc_optimal_coupling(L1: float, R1_tot: float, L2: float, R2_tot: float, f0_kHz: float) -> float:
    """Связь, при которой P_вых на резонансе максимальна: k_опт = 1 / sqrt(Q1 * Q2)."""
    omega0 = 2.0 * np.pi * f0_kHz * 1000.0
    if L1 <= 0 or L2 <= 0 or omega0 <= 0:
        return 0.0
    return float(np.sqrt(R1_tot * R2_tot) / (omega0 * np.sqrt(L1 * L2)))


def find_optimal_tracking_freq(
    f0_kHz: float,
    L1: float,
    C1: float,
    R1: float,
    L2: float,
    C2: float,
    R2: float,
    M: float,
    R_load: float,
    Rds_on_mOhm: float
) -> float:
    """
    Частота максимума мощности в нагрузке (тока Rx) на верхней ветви резонанса (f >= f0, ZVS-режим).
    Если коэффициент связи k <= k_крит (расщепления резонанса нет), система должна работать
    строго на номинальной резонансной частоте f0_kHz. Это предотвращает ложный уход частоты
    в паразитный последовательный резонанс ненагруженного первичного контура (X1 -> 0),
    который приводил к аномальному току I1 до 60 А и потерям до 250 Вт при 5 В.
    """
    if L1 <= 0 or L2 <= 0 or M <= 0 or C1 <= 0 or C2 <= 0 or f0_kHz <= 0:
        return float(f0_kHz)

    Rds = Rds_on_mOhm / 1000.0
    R_eq = (8.0 / (np.pi**2)) * R_load
    R1_tot = R1 + 2.0 * Rds
    R2_tot = R2 + 2.0 * Rds + R_eq

    k = M / np.sqrt(L1 * L2)
    k_crit = calc_critical_coupling(L1, R1_tot, L2, R2_tot, f0_kHz)

    # При k <= k_crit бифуркации нет — остаемся строго на f0
    if k <= k_crit:
        return float(f0_kHz)

    # При сильной связи (k > k_crit) ищем верхний пик бифуркации (f > f0, ZVS-ветвь)
    ratio = max(1.65, 1.35 / np.sqrt(max(1.0 - k, 0.02)))
    f_max_kHz = f0_kHz * ratio
    n_points = int(max(350, round(350 * (ratio / 1.65))))
    f_grid_kHz = np.linspace(f0_kHz, f_max_kHz, n_points)
    w = 2.0 * np.pi * f_grid_kHz * 1000.0

    Z1 = R1_tot + 1j * (w * L1 - 1.0 / (w * C1))
    Z2 = R2_tot + 1j * (w * L2 - 1.0 / (w * C2))
    ZM = 1j * w * M
    I2_sq = np.abs(ZM / (Z1 * Z2 - (ZM**2)))**2

    # Ищем истинные внутренние локальные максимумы
    peaks, _ = find_peaks(I2_sq)
    if len(peaks) > 0:
        best_peak = peaks[np.argmax(I2_sq[peaks])]
        return float(f_grid_kHz[best_peak])

    return float(f0_kHz)


def solve_ss_wpt_circuit(
    V_bus_dc: float,
    f_drive_kHz: float,
    L1: float,
    C1: float,
    R1: float,
    L2: float,
    C2: float,
    R2: float,
    M: float,
    R_load: float,
    Rds_on_mOhm: float
) -> Dict[str, Any]:
    """
    Решение связанных контуров методом первой гармоники (FHA).
    Положительные направления I1 и I2 — одинаковый обход витков (оба тока создают
    поле одного знака). Из закона Фарадея: Z1*I1 + jwM*I2 = V1, jwM*I1 + Z2*I2 = 0,
    откуда I2 = -jwM*I1/Z2 (на резонансе I2 отстаёт от I1 на 90°).
    """
    if f_drive_kHz <= 0 or L1 <= 0 or L2 <= 0 or C1 <= 0 or C2 <= 0:
        raise ValueError("Частота (f_drive_kHz), индуктивности (L1, L2) и емкости (C1, C2) должны быть строго больше 0.")

    f = f_drive_kHz * 1000.0
    omega = 2.0 * np.pi * f
    Rds = Rds_on_mOhm / 1000.0

    V1_rms = (2.0 * np.sqrt(2.0) / np.pi) * V_bus_dc
    R_eq = (8.0 / (np.pi**2)) * R_load

    R1_tot = R1 + 2.0 * Rds
    R2_tot = R2 + 2.0 * Rds

    X1 = omega * L1 - 1.0 / (omega * C1)
    X2 = omega * L2 - 1.0 / (omega * C2)

    Z1 = R1_tot + 1j * X1
    Z2 = (R2_tot + R_eq) + 1j * X2
    ZM = 1j * omega * M

    det = Z1 * Z2 - (ZM**2)
    if abs(det) < 1e-18:
        raise ZeroDivisionError("Определитель матрицы импедансов цепи близок к нулю (|det| < 1e-18).")
    I1 = (V1_rms * Z2) / det
    I2 = -(V1_rms * ZM) / det

    I1_abs = abs(I1)
    I2_abs = abs(I2)

    # Входная активная мощность первой гармоники от инвертора:
    P_in = float(np.real(V1_rms * np.conj(I1)))

    # Выходные параметры выпрямителя с емкостным фильтром (метод первой гармоники FHA):
    I_out_dc = (2.0 * np.sqrt(2.0) / np.pi) * I2_abs
    V_out_dc = I_out_dc * R_load
    P_out    = (I2_abs**2) * R_eq

    P_cu_tx  = (I1_abs**2) * R1
    P_cu_rx  = (I2_abs**2) * R2
    P_mos_tx = (I1_abs**2) * (2.0 * Rds)
    P_mos_rx = (I2_abs**2) * (2.0 * Rds)

    eta = (P_out / P_in) if P_in > 1e-12 else 0.0

    Z_in = V1_rms / I1 if I1_abs > 1e-9 else 1e9
    phase_deg = float(np.degrees(np.angle(Z_in)))
    if abs(phase_deg) < 1e-9:
        phase_deg = 0.0
    phi_i2_i1_rad = float(np.angle(I2 / I1)) if (I1_abs > 1e-9 and I2_abs > 1e-12) else 0.0

    return {
        'I1_rms': float(I1_abs),
        'I2_rms': float(I2_abs),
        'I1_c': complex(I1),
        'I2_c': complex(I2),
        'phi_i2_i1_rad': phi_i2_i1_rad,
        'V_out_dc': float(V_out_dc),
        'P_in': P_in,
        'P_out': float(P_out),
        'P_cu': float(P_cu_tx + P_cu_rx),
        'P_mos': float(P_mos_tx + P_mos_rx),
        'eta': float(eta),
        'phase_deg': phase_deg
    }


def solve_ss_frequency_sweep(
    V_bus_dc: float,
    f_grid_kHz: np.ndarray,
    L1: float,
    C1: float,
    R1_arr: np.ndarray,
    L2: float,
    C2: float,
    R2_arr: np.ndarray,
    M: float,
    R_load: float,
    Rds_on_mOhm: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Векторизованный расчёт АЧХ SS-цепи по сетке частот f_grid_kHz.
    Возвращает кортеж массивов (pout_W, eta_pct) с защитой от нулевого определителя.
    """
    if L1 <= 0 or L2 <= 0 or C1 <= 0 or C2 <= 0:
        raise ValueError("Индуктивности (L1, L2) и емкости (C1, C2) должны быть строго больше 0.")
    f_arr = np.asarray(f_grid_kHz, dtype=float)
    if np.any(f_arr <= 0):
        raise ValueError("Все частоты в сетке f_grid_kHz должны быть строго больше 0.")

    R1 = np.asarray(R1_arr, dtype=float)
    R2 = np.asarray(R2_arr, dtype=float)
    omega = 2.0 * np.pi * f_arr * 1000.0
    Rds = Rds_on_mOhm / 1000.0

    V1_rms = (2.0 * np.sqrt(2.0) / np.pi) * V_bus_dc
    R_eq = (8.0 / (np.pi**2)) * R_load

    R1_tot = R1 + 2.0 * Rds
    R2_tot = R2 + 2.0 * Rds

    X1 = omega * L1 - 1.0 / (omega * C1)
    X2 = omega * L2 - 1.0 / (omega * C2)

    Z1 = R1_tot + 1j * X1
    Z2 = (R2_tot + R_eq) + 1j * X2
    ZM = 1j * omega * M

    det = Z1 * Z2 - (ZM**2)
    valid = np.abs(det) >= 1e-18
    safe_det = np.where(valid, det, 1.0 + 0.0j)

    I1 = np.where(valid, (V1_rms * Z2) / safe_det, 0.0 + 0.0j)
    I2 = np.where(valid, -(V1_rms * ZM) / safe_det, 0.0 + 0.0j)

    I2_abs = np.abs(I2)
    P_in = np.real(V1_rms * np.conj(I1))
    pout_W = (I2_abs**2) * R_eq
    eta_pct = np.where(valid & (P_in > 1e-12), (pout_W / np.where(P_in > 1e-12, P_in, 1.0)) * 100.0, 0.0)
    return pout_W, eta_pct
