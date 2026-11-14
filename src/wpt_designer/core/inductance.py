"""
Inductance and mutual inductance calculations using elliptic integrals,
Neumann's formula, and method of images for ferrite screens.
"""

from typing import List, Tuple, Optional
import numpy as np
from scipy.special import ellipk, ellipe

from .constants import (
    MU_0,
    FERRITE_REFLECT,
    IMAGE_MIN_WEIGHT,
)
from .winding import Winding


def image_ops(
    d: float,
    H1: float,
    H2: float,
    rho: Optional[float] = None,
    w_min: float = IMAGE_MIN_WEIGHT
) -> List[Tuple[float, float, float]]:
    """
    Операции отражения в двух параллельных ферритовых плоскостях z = -H1 и z = d + H2
    (средняя плоскость Tx в z=0, Rx в z=d). Возвращает список (sign, shift, weight):
    изображение источника в точке z находится в z_img = sign*z + shift.
    Первая запись (1, 0, 1.0) — сам источник. Нечётное число отражений:
    sign=-1, shift=-2*H1+2nS, вес rho^|2n-1|; чётное: sign=+1, shift=2nS, вес rho^|2n|,
    где S = d + H1 + H2. Токи изображений сонаправлены (mu_r >> 1).
    """
    rho = FERRITE_REFLECT if rho is None else rho
    rho = float(np.clip(rho, 0.0, 0.999))
    S = d + H1 + H2
    out = [(1.0, 0.0, 1.0)]
    if rho <= 0.0:
        return out
    n_max = int(min(60, np.ceil(np.log(w_min) / (2.0 * np.log(rho))) + 1))
    for n in range(-n_max, n_max + 1):
        if n != 0:
            w = rho ** abs(2 * n)
            if w >= w_min:
                out.append((1.0, 2.0 * n * S, w))
        w = rho ** abs(2 * n - 1)
        if w >= w_min:
            out.append((-1.0, -2.0 * H1 + 2.0 * n * S, w))
    return out


def winding_sources(w_tx: Winding, w_rx: Winding, d: float, which: str = 'tx') -> List[Tuple[np.ndarray, float]]:
    """
    Источники поля: список (z_массив_витков, вес) для витков и всех их изображений.
    w_tx — передатчик (нижняя катушка), w_rx — приемник (верхняя катушка).
    Rx — зеркальное отражение относительно плоскости z = d:
    z_Rx = d - w_rx.z (слой, ближайший к ферриту Rx, остаётся ближайшим к ферриту).
    """
    if which == 'tx':
        z = w_tx.z
    elif which == 'rx':
        z = d - w_rx.z
    else:
        raise ValueError(f"Неизвестный селектор катушки: {which}")
    return [(sign * z + shift, wt) for sign, shift, wt in image_ops(d, w_tx.H_m, w_rx.H_m)]


def _M_matrix(dz: np.ndarray, r1_arr: np.ndarray, r2_arr: np.ndarray) -> np.ndarray:
    """Матрица взаимных индуктивностей витков (формула Максвелла); dz — скаляр или матрица."""
    R1 = np.asarray(r1_arr, dtype=float)[:, None]
    R2 = np.asarray(r2_arr, dtype=float)[None, :]
    d = np.maximum(np.abs(dz), 1e-5)
    m = np.clip(4.0 * R1 * R2 / ((R1 + R2)**2 + d**2), 1e-12, 1.0 - 1e-12)
    k_e = np.sqrt(m)
    return MU_0 * np.sqrt(R1 * R2) * ((2.0 / k_e - k_e) * ellipk(m) - (2.0 / k_e) * ellipe(m))


def _M_matrix_batch(dz_3d: np.ndarray, r1_arr: np.ndarray, r2_arr: np.ndarray) -> np.ndarray:
    """Пакетная матрица взаимных индуктивностей для массива изображений dz_3d формы (I, N1, N2)."""
    R1 = np.asarray(r1_arr, dtype=float)[None, :, None]
    R2 = np.asarray(r2_arr, dtype=float)[None, None, :]
    d = np.maximum(np.abs(dz_3d), 1e-5)
    m = np.clip(4.0 * R1 * R2 / ((R1 + R2) ** 2 + d**2), 1e-12, 1.0 - 1e-12)
    k_e = np.sqrt(m)
    return MU_0 * np.sqrt(R1 * R2) * ((2.0 / k_e - k_e) * ellipk(m) - (2.0 / k_e) * ellipe(m))


def _coaxial_M_sum(dz: float, r1_arr: np.ndarray, r2_arr: np.ndarray) -> float:
    return float(np.sum(_M_matrix(dz, r1_arr, r2_arr)))


def _neumann_M_sum(dz_mat: np.ndarray, dx_m: float, r1_arr: np.ndarray, r2_arr: np.ndarray, n_phi: int) -> float:
    """Интеграл Неймана по всем парам витков при боковом смещении dx; dz_mat — матрица (A, B)."""
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    dphi = 2.0 * np.pi / n_phi
    cp, sp = np.cos(phi), np.sin(phi)
    cos_diff = np.cos(phi[:, None] - phi[None, :]) * dphi**2            # (P1, P2)
    r2 = np.asarray(r2_arr, dtype=float)[:, None, None]                 # (B, 1, 1)
    X2 = dx_m + r2 * cp[None, None, :]                                  # (B, 1, P2)
    Y2 = r2 * sp[None, None, :]
    dz_mat = np.broadcast_to(dz_mat, (len(r1_arr), len(r2_arr)))
    total = 0.0
    for i, r1 in enumerate(r1_arr):                                      # по виткам первой обмотки
        X1 = r1 * cp[None, :, None]                                      # (1, P1, 1)
        Y1 = r1 * sp[None, :, None]
        dist = np.sqrt((X1 - X2)**2 + (Y1 - Y2)**2 + dz_mat[i][:, None, None]**2)   # (B, P1, P2)
        total += np.sum(r1 * r2 * cos_diff[None, :, :] / dist)
    return float(total * MU_0 / (4.0 * np.pi))


def calc_inductance(w1: Winding, w2: Winding, d_m: float) -> float:
    """
    Индуктивность обмотки w1 при расположении обмотки w2 на расстоянии d_m:
    - L_air — точная сумма: собственные индуктивности витков (пучок радиуса D_wire/2,
      равномерная плотность тока) плюс взаимные индуктивности всех пар витков
      с их реальными положениями (r, z);
    - плюс вклад изображений витков в двух ферритовых плоскостях.
    """
    if w1.N < 1 or w1.r.size == 0:
        return 0.0
    r, z = w1.r, w1.z
    if w1._l_air_cache is None:
        a = w1.D_wire_m / 2.0
        M = _M_matrix(z[:, None] - z[None, :], r, r)
        np.fill_diagonal(M, 0.0)
        L_self = np.sum(MU_0 * r * (np.log(8.0 * r / a) - 2.0 + 0.25))
        w1._l_air_cache = float(np.sum(M) + L_self)

    L = w1._l_air_cache
    d = max(d_m, 1e-4)
    ops = image_ops(d, w1.H_m, w2.H_m)[1:]                              # [0] — сами витки
    if ops:
        signs = np.array([op[0] for op in ops], dtype=float)[:, None]
        shifts = np.array([op[1] for op in ops], dtype=float)[:, None]
        weights = np.array([op[2] for op in ops], dtype=float)[:, None, None]
        z_img = signs * z[None, :] + shifts
        dz_3d = z[None, :, None] - z_img[:, None, :]
        L += float(np.sum(weights * _M_matrix_batch(dz_3d, r, r)))
    return float(L)


def calc_mutual_inductance_fast(d_mm: float, w1: Winding, w2: Winding, dx_mm: float = 0.0) -> float:
    """
    Взаимная индуктивность M между всеми витками Tx и Rx (с реальными z) с учётом
    ВСЕХ изображений Tx в ферритовых плоскостях (та же схема, что и для L).
    Соосно — эллиптические интегралы; при смещении — интеграл Неймана; обе ветви
    используют один набор изображений, поэтому M непрерывна по dx.
    """
    if w1.r.size == 0 or w2.r.size == 0:
        return 0.0
    d = max(d_mm / 1000.0, 1e-4)
    dx = dx_mm / 1000.0
    z1 = w1.z
    z2 = d - w2.z
    ops = image_ops(d, w1.H_m, w2.H_m)
    if abs(dx_mm) < 1e-4:
        signs = np.array([op[0] for op in ops], dtype=float)[:, None]
        shifts = np.array([op[1] for op in ops], dtype=float)[:, None]
        weights = np.array([op[2] for op in ops], dtype=float)[:, None, None]
        z_img = signs * z1[None, :] + shifts
        dz_3d = z_img[:, :, None] - z2[None, None, :]
        return float(np.sum(weights * _M_matrix_batch(dz_3d, w1.r, w2.r)))

    total = 0.0
    for sign, shift, wt in ops:
        dz = (sign * z1 + shift)[:, None] - z2[None, :]
        dmin = float(np.min(np.abs(dz)))
        n_phi = 96 if dmin < 3e-3 else (48 if dmin < 10e-3 else 24)
        total += wt * _neumann_M_sum(dz, dx, w1.r, w2.r, n_phi)
    return float(total)
