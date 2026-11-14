"""
Physical constants and default engineering parameters for planar WPT coils,
ferrite shields, and litz wire.
"""

import numpy as np

# Фундаментальные физические константы
MU_0: float = 4.0 * np.pi * 1e-7          # Магнитная постоянная вакуума, Гн/м
RHO_CU: float = 1.68e-8                  # Удельное сопротивление меди при 20°C, Ом*м

# Параметры ферритовых экранов (метод зеркальных отображений)
FERRITE_CLEARANCE_M: float = 0.15e-3     # Зазор от наружной поверхности обмотки до феррита, м
FERRITE_OVERHANG_M: float = 2.0e-3       # Выступ феррита за внешний диаметр катушки, м
FERRITE_REFLECT: float = 0.60            # Калибровочный коэффициент отражения плоского феррита (по FEMM 4.2)
FERRITE_LEAK: float = 0.18               # Ослабление поля за ферритом (для визуализации)
IMAGE_MIN_WEIGHT: float = 5e-3           # Порог отсечения слабых изображений

# Параметры литцендрата и геометрии намотки
LITZ_PACKING: float = 0.6                # Коэффициент заполнения пучка медью (жилы + изоляция + воздух)
LITZ_SERVING_M: float = 0.05e-3          # Толщина внешней обмотки пучка (шёлк/полиэфир) на сторону, м
TURN_GAP_M: float = 0.05e-3              # Технологический зазор между соседними витками, м
COIL_CLEARANCE_M: float = 0.2e-3         # Минимальный зазор между обмотками Tx и Rx, м
