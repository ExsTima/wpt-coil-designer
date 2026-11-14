"""
Winding geometry and conductor layout for planar spiral coils.
"""

from typing import Dict, Optional, Tuple
import numpy as np

from .constants import (
    FERRITE_CLEARANCE_M,
    LITZ_PACKING,
    LITZ_SERVING_M,
    TURN_GAP_M,
    COIL_CLEARANCE_M,
)


class Winding:
    """
    Реальная раскладка витков плоской спиральной обмотки из литцендрата.
    Внешний диаметр пучка D_wire = d_жилы*sqrt(n/заполнение) + 2*изоляция.
    Если витки не помещаются в один слой в зоне (D_out - D_in)/2 с учётом D_wire,
    обмотка автоматически становится многослойной (слои выровнены по оси, равномерно
    распределённые витки). Для каждого витка хранятся радиус r и осевое смещение z
    от средней плоскости обмотки; H — расстояние от средней плоскости до феррита.
    """
    def __init__(
        self,
        D_out_mm: float,
        D_in_mm: float,
        N: int,
        d_strand_mm: float,
        n_strands: int
    ):
        self.D_out_mm = float(D_out_mm)
        self.D_in_mm = float(D_in_mm)
        self.N = int(N)
        self.d_strand_mm = float(d_strand_mm)
        self.n_strands = int(n_strands)

        d_s = self.d_strand_mm / 1000.0
        if self.n_strands <= 1:
            D_wire = d_s * 1.05
        else:
            D_wire = d_s * np.sqrt(self.n_strands / LITZ_PACKING) + 2.0 * LITZ_SERVING_M
        self.D_wire_m = float(D_wire)

        r_in = self.D_in_mm / 2000.0
        r_out = self.D_out_mm / 2000.0
        width = r_out - r_in
        self.width_m = width
        self.feasible = bool(self.N >= 1 and width >= D_wire - 1e-9)

        pitch_min = D_wire + TURN_GAP_M
        per_max = max(1, int(np.floor(width / pitch_min + 1e-9))) if width > 0 else 1
        if self.N <= per_max:
            layers, per_layer = 1, max(self.N, 1)
        else:
            layers = int(np.ceil(self.N / per_max))
            per_layer = int(np.ceil(self.N / layers))
        self.layers = layers
        self.per_layer = per_layer
        self.pitch_m = width / per_layer if per_layer > 0 else 0.0

        radii, zs = [], []
        left = self.N
        for j in range(layers):
            n_j = min(per_layer, left)
            left -= n_j
            z_j = (j - (layers - 1) / 2.0) * D_wire
            for k in range(n_j):
                radii.append(r_in + (k + 0.5) * self.pitch_m)
                zs.append(z_j)
        self.r = np.array(radii, dtype=float)
        self.z = np.array(zs, dtype=float)
        self.thickness_m = layers * D_wire
        self.H_m = FERRITE_CLEARANCE_M + self.thickness_m / 2.0
        self.length_m = float(np.sum(2.0 * np.pi * self.r))
        self._prox_cache: Dict[Tuple[float, float, float], float] = {}
        self._l_air_cache: Optional[float] = None
        self._prox_self_cache: Optional[Tuple[np.ndarray, np.ndarray]] = None

    def same_geometry(self, other: "Winding") -> bool:
        """Проверяет геометрическую идентичность двух обмоток для переиспользования симметрии."""
        return (
            self.D_out_mm == other.D_out_mm
            and self.D_in_mm == other.D_in_mm
            and self.N == other.N
            and self.d_strand_mm == other.d_strand_mm
            and self.n_strands == other.n_strands
        )

    def summary(self) -> str:
        return (f"{self.layers} сл. x {self.per_layer}, шаг {self.pitch_m*1e3:.2f} мм, "
                f"пучок Ø{self.D_wire_m*1e3:.2f} мм")


def min_coil_gap_m(w1: Winding, w2: Winding) -> float:
    """Минимальный осевой зазор d между средними плоскостями обмоток (без перекрытия)."""
    return (w1.thickness_m + w2.thickness_m) / 2.0 + COIL_CLEARANCE_M
