"""
Engineering Presets for WPT Coil Designer.
Provides calibrated, industry-standard configurations for quick exploration:
- Qi Standard v1.2 (Low-Power 5W Smartphone Charger, 110-205 kHz)
- FEMM 4.2 Benchmark Baseline (Axisymmetric FEA Reference, 100 kHz)
- High-Power EV Prototype (SAE J2954 3.3 kW, 85 kHz)
- High-Frequency GaN System (Industrial 24V / 50W, 500 kHz)
- Miniature Biomedical / Sensor (Implant / IoT 3.3V, 1 MHz)
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class WPTPreset:
    name: str
    description: str
    params: Dict[str, str]
    auto_track: bool = False


PRESETS: Dict[str, WPTPreset] = {
    "qi_5w": WPTPreset(
        name="Qi v1.2 Смартфон (5 Вт, 120 кГц)",
        description="Стандартная плоская передающая катушка Qi A11 / приёмник для мобильных устройств (5 В, нагрузка 10 Ом).",
        params={
            "tx_Dout": "50.0",
            "tx_Din": "20.0",
            "tx_N": "12",
            "rx_Dout": "50.0",
            "rx_Din": "20.0",
            "rx_N": "12",
            "d_strand": "0.10",
            "n_strands": "100",
            "V_bus": "5.0",
            "Rds_mOhm": "18.0",
            "R_load": "10.0",
            "f0_kHz": "120.0",
            "f_drive_kHz": "120.0",
            "dist_mm": "10.0",
        },
        auto_track=False,
    ),
    "femm_bench": WPTPreset(
        name="Эталон верификации FEMM 4.2 (100 кГц)",
        description="Калиброванный лабораторный стенд для сверки аналитических формул с конечно-элементным решателем FEMM 4.2.",
        params={
            "tx_Dout": "50.0",
            "tx_Din": "20.0",
            "tx_N": "12",
            "rx_Dout": "50.0",
            "rx_Din": "20.0",
            "rx_N": "12",
            "d_strand": "0.10",
            "n_strands": "40",
            "V_bus": "12.0",
            "Rds_mOhm": "25.0",
            "R_load": "10.0",
            "f0_kHz": "100.0",
            "f_drive_kHz": "100.0",
            "dist_mm": "15.0",
        },
        auto_track=False,
    ),
    "gan_500k": WPTPreset(
        name="Высокочастотный GaN WPT (24 В, 50 Вт, 500 кГц)",
        description="Компактный планарный преобразователь на GaN-транзисторах с малым сопротивлением Rds=12 мОм и высокой плотностью мощности.",
        params={
            "tx_Dout": "65.0",
            "tx_Din": "25.0",
            "tx_N": "9",
            "rx_Dout": "65.0",
            "rx_Din": "25.0",
            "rx_N": "9",
            "d_strand": "0.071",
            "n_strands": "120",
            "V_bus": "24.0",
            "Rds_mOhm": "12.0",
            "R_load": "12.0",
            "f0_kHz": "500.0",
            "f_drive_kHz": "500.0",
            "dist_mm": "12.0",
        },
        auto_track=True,
    ),
    "ev_3kw": WPTPreset(
        name="Тяговый индуктивный заряд EV (3.3 кВт, 85 кГц)",
        description="Крупногабаритная система заряда электромобиля по стандарту SAE J2954 (WPT1) с воздушным зазором 80 мм и шиной 380 В.",
        params={
            "tx_Dout": "300.0",
            "tx_Din": "120.0",
            "tx_N": "16",
            "rx_Dout": "300.0",
            "rx_Din": "120.0",
            "rx_N": "16",
            "d_strand": "0.10",
            "n_strands": "600",
            "V_bus": "380.0",
            "Rds_mOhm": "30.0",
            "R_load": "45.0",
            "f0_kHz": "85.0",
            "f_drive_kHz": "85.0",
            "dist_mm": "80.0",
        },
        auto_track=True,
    ),
    "implant_1m": WPTPreset(
        name="Миниатюрный сенсор / имплант (3.3 В, 1 МГц)",
        description="Сверхкомпактная телеметрическая катушка для носимой электроники и датчиков с тонким проводом.",
        params={
            "tx_Dout": "25.0",
            "tx_Din": "10.0",
            "tx_N": "8",
            "rx_Dout": "25.0",
            "rx_Din": "10.0",
            "rx_N": "8",
            "d_strand": "0.05",
            "n_strands": "30",
            "V_bus": "3.3",
            "Rds_mOhm": "40.0",
            "R_load": "20.0",
            "f0_kHz": "1000.0",
            "f_drive_kHz": "1000.0",
            "dist_mm": "6.0",
        },
        auto_track=False,
    )
}

PRESET_NAMES = [p.name for p in PRESETS.values()]
PRESET_KEYS = list(PRESETS.keys())
