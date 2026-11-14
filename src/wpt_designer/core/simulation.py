"""
High-level simulation orchestration, parameter sweeps, and report formatting.
Completely independent of GUI toolkits (Tkinter/Matplotlib).
"""

import time
from typing import Any, Dict, List, Tuple

import numpy as np

from .ac_losses import calc_Q, winding_resistances
from .circuit_ss import (
    calc_coupling,
    calc_critical_coupling,
    calc_optimal_coupling,
    find_optimal_tracking_freq,
    solve_ss_frequency_sweep,
    solve_ss_wpt_circuit,
)
from .inductance import calc_inductance, calc_mutual_inductance_fast
from .winding import Winding, min_coil_gap_m


def _d_min_mm(lay_tx: Winding, lay_rx: Winding) -> float:
    return float(np.ceil(min_coil_gap_m(lay_tx, lay_rx) * 1e4) / 10.0)


def _solve_at_gap(
    results: Dict[str, Any],
    d_mm: float,
    auto_track: bool,
) -> Tuple[float, Dict[str, Any]]:
    """Рассчитывает связь k и решение цепи SS на заданном осевом зазоре d_mm."""
    lay_tx = results["lay_tx"]
    lay_rx = results["lay_rx"]
    d_m = d_mm / 1000.0
    L1_d = calc_inductance(lay_tx, lay_rx, d_m)
    L2_d = L1_d if lay_tx.same_geometry(lay_rx) else calc_inductance(lay_rx, lay_tx, d_m)
    Md = calc_mutual_inductance_fast(d_mm, lay_tx, lay_rx)
    kd = calc_coupling(Md, L1_d, L2_d)

    if auto_track:
        _, R1_0, _, R2_0 = winding_resistances(lay_tx, lay_rx, results["f0_kHz"], d_m)
        f_use = find_optimal_tracking_freq(
            results["f0_kHz"],
            L1_d,
            results["C1"],
            R1_0,
            L2_d,
            results["C2"],
            R2_0,
            Md,
            results["R_load"],
            results["Rds_mOhm"],
        )
    else:
        f_use = results["f_drive_kHz"]

    _, R1_u, _, R2_u = winding_resistances(lay_tx, lay_rx, f_use, d_m)
    sol = solve_ss_wpt_circuit(
        results["V_bus"],
        f_use,
        L1_d,
        results["C1"],
        R1_u,
        L2_d,
        results["C2"],
        R2_u,
        Md,
        results["R_load"],
        results["Rds_mOhm"],
    )
    return kd, sol


def run_wpt_simulation(
    tx_Dout: float,
    tx_Din: float,
    tx_N: int,
    rx_Dout: float,
    rx_Din: float,
    rx_N: int,
    d_strand: float,
    n_strands: int,
    V_bus: float,
    Rds_mOhm: float,
    R_load: float,
    f0_kHz: float,
    f_drive_kHz: float,
    dist_mm: float,
    auto_track: bool = False,
) -> Dict[str, Any]:
    """
    Выполняет полный расчёт геометрии катушек, индуктивностей, ВЧ-сопротивлений
    и параметров SS-резонансной цепи. Выбрасывает ValueError при некорректной геометрии.
    """
    if tx_Dout <= tx_Din or rx_Dout <= rx_Din:
        raise ValueError("Внешний диаметр D_нар должен строго превышать внутренний D_вн!")
    if tx_N < 1 or rx_N < 1 or d_strand <= 0 or n_strands < 1:
        raise ValueError("Число витков, число жил и диаметр жилы должны быть > 0!")
    if f0_kHz <= 0 or f_drive_kHz <= 0 or R_load <= 0 or dist_mm <= 0:
        raise ValueError("Частоты, нагрузка и зазор должны быть строго больше 0!")

    lay_tx = Winding(tx_Dout, tx_Din, tx_N, d_strand, n_strands)
    lay_rx = Winding(rx_Dout, rx_Din, rx_N, d_strand, n_strands)
    for name, lay in (("Tx", lay_tx), ("Rx", lay_rx)):
        if not lay.feasible:
            raise ValueError(
                f"{name} пучок литца Ø{lay.D_wire_m*1e3:.2f} мм шире зоны намотки "
                f"(D_внеш − D_внутр)/2 = {lay.width_m*1e3:.2f} мм."
            )

    d_min_mm = min_coil_gap_m(lay_tx, lay_rx) * 1e3
    if dist_mm < d_min_mm:
        raise ValueError(
            f"Зазор d={dist_mm:.1f} мм меньше суммарной толщины обмоток ({d_min_mm:.1f} мм)!"
        )

    d_m = dist_mm / 1000.0
    L1 = calc_inductance(lay_tx, lay_rx, d_m)
    L2 = L1 if lay_tx.same_geometry(lay_rx) else calc_inductance(lay_rx, lay_tx, d_m)

    omega0 = 2.0 * np.pi * f0_kHz * 1000.0
    C1 = 1.0 / ((omega0**2) * L1)
    C2 = 1.0 / ((omega0**2) * L2)

    _, R1_f0, _, R2_f0 = winding_resistances(lay_tx, lay_rx, f0_kHz, d_m)
    Q1 = calc_Q(L1, R1_f0, f0_kHz)
    Q2 = calc_Q(L2, R2_f0, f0_kHz)

    M = calc_mutual_inductance_fast(dist_mm, lay_tx, lay_rx)
    k = calc_coupling(M, L1, L2)

    Rds = Rds_mOhm / 1000.0
    R_eq = (8.0 / (np.pi**2)) * R_load
    k_crit = calc_critical_coupling(L1, R1_f0 + 2.0 * Rds, L2, R2_f0 + 2.0 * Rds + R_eq, f0_kHz)
    k_opt = calc_optimal_coupling(L1, R1_f0 + 2.0 * Rds, L2, R2_f0 + 2.0 * Rds + R_eq, f0_kHz)

    if auto_track:
        f_actual_kHz = find_optimal_tracking_freq(
            f0_kHz, L1, C1, R1_f0, L2, C2, R2_f0, M, R_load, Rds_mOhm
        )
    else:
        f_actual_kHz = float(f_drive_kHz)

    R1_dc, R1_ac, R2_dc, R2_ac = winding_resistances(lay_tx, lay_rx, f_actual_kHz, d_m)
    circuit = solve_ss_wpt_circuit(
        V_bus, f_actual_kHz, L1, C1, R1_ac, L2, C2, R2_ac, M, R_load, Rds_mOhm
    )

    return {
        "tx_Dout": float(tx_Dout),
        "tx_Din": float(tx_Din),
        "tx_N": int(tx_N),
        "rx_Dout": float(rx_Dout),
        "rx_Din": float(rx_Din),
        "rx_N": int(rx_N),
        "lay_tx": lay_tx,
        "lay_rx": lay_rx,
        "d_strand": float(d_strand),
        "n_strands": int(n_strands),
        "V_bus": float(V_bus),
        "Rds_mOhm": float(Rds_mOhm),
        "R_load": float(R_load),
        "f0_kHz": float(f0_kHz),
        "f_drive_kHz": float(f_actual_kHz),
        "dist_mm": float(dist_mm),
        "L1": L1,
        "L2": L2,
        "C1": C1,
        "C2": C2,
        "R1_dc": R1_dc,
        "R1_ac": R1_ac,
        "R2_dc": R2_dc,
        "R2_ac": R2_ac,
        "Q1": Q1,
        "Q2": Q2,
        "M": M,
        "k": k,
        "k_crit": k_crit,
        "k_opt": k_opt,
        "circuit": circuit,
    }


def compute_distance_sweep(
    results: Dict[str, Any],
    auto_track: bool,
    d_max_mm: float = 60.0,
    num_points: int = 45,
) -> Dict[str, np.ndarray]:
    """Строит массивы зависимостей k, КПД, мощности, потерь и U_вых от зазора d."""
    d_start = max(2.0, _d_min_mm(results["lay_tx"], results["lay_rx"]))
    d_end = max(float(d_max_mm), float(results["dist_mm"]) + 10.0)
    d_range = np.linspace(d_start, d_end, num_points)

    k_list, eta_list, pout_list, ploss_list, vout_list = [], [], [], [], []
    for d in d_range:
        kd, sol = _solve_at_gap(results, float(d), auto_track)
        k_list.append(kd)
        eta_list.append(sol["eta"] * 100.0)
        pout_list.append(sol["P_out"])
        ploss_list.append(sol["P_cu"] + sol["P_mos"])
        vout_list.append(sol["V_out_dc"])

    return {
        "d_mm": d_range,
        "k": np.asarray(k_list, dtype=float),
        "eta_pct": np.asarray(eta_list, dtype=float),
        "pout_W": np.asarray(pout_list, dtype=float),
        "ploss_W": np.asarray(ploss_list, dtype=float),
        "vout_V": np.asarray(vout_list, dtype=float),
    }


def compute_distance_table(
    results: Dict[str, Any],
    auto_track: bool,
    d_max_mm: int = 60,
) -> List[Dict[str, Any]]:
    """Формирует табличные строки (шаг 1 мм) для экспорта характеристик в CSV."""
    d_start = int(np.ceil(_d_min_mm(results["lay_tx"], results["lay_rx"])))
    d_end = max(int(d_max_mm), int(np.ceil(results["dist_mm"])) + 10)
    rows: List[Dict[str, Any]] = []
    for d in range(d_start, d_end + 1):
        kd, sol = _solve_at_gap(results, float(d), auto_track)
        rows.append(
            {
                "d_mm": d,
                "k": round(kd, 4),
                "eta_pct": round(sol["eta"] * 100.0, 2),
                "Pout_W": round(sol["P_out"], 2),
                "Ploss_W": round(sol["P_cu"] + sol["P_mos"], 2),
                "Vout_V": round(sol["V_out_dc"], 2),
            }
        )
    return rows


def compute_frequency_sweep(
    results: Dict[str, Any],
    d_mm: float,
    num_points: int = 150,
) -> Dict[str, Any]:
    """Рассчитывает АЧХ мощности и КПД при фиксированном зазоре d_mm."""
    lay_tx = results["lay_tx"]
    lay_rx = results["lay_rx"]
    d_eff = max(float(d_mm), _d_min_mm(lay_tx, lay_rx))
    d_m = d_eff / 1000.0

    L1_d = calc_inductance(lay_tx, lay_rx, d_m)
    L2_d = L1_d if lay_tx.same_geometry(lay_rx) else calc_inductance(lay_rx, lay_tx, d_m)
    Md = calc_mutual_inductance_fast(d_eff, lay_tx, lay_rx)
    kd = calc_coupling(Md, L1_d, L2_d)

    _, R1_0, _, R2_0 = winding_resistances(lay_tx, lay_rx, results["f0_kHz"], d_m)
    f_opt_d = find_optimal_tracking_freq(
        results["f0_kHz"],
        L1_d,
        results["C1"],
        R1_0,
        L2_d,
        results["C2"],
        R2_0,
        Md,
        results["R_load"],
        results["Rds_mOhm"],
    )

    f_span = np.linspace(results["f0_kHz"] * 0.70, results["f0_kHz"] * 1.45, num_points)
    R1_arr = np.empty_like(f_span)
    R2_arr = np.empty_like(f_span)
    for i, f_k in enumerate(f_span):
        _, R1_arr[i], _, R2_arr[i] = winding_resistances(lay_tx, lay_rx, float(f_k), d_m)

    pout_W, eta_pct = solve_ss_frequency_sweep(
        results["V_bus"],
        f_span,
        L1_d,
        results["C1"],
        R1_arr,
        L2_d,
        results["C2"],
        R2_arr,
        Md,
        results["R_load"],
        results["Rds_mOhm"],
    )
    return {
        "d_mm": d_eff,
        "kd": kd,
        "f_opt_d": f_opt_d,
        "f_span": f_span,
        "pout_W": pout_W,
        "eta_pct": eta_pct,
    }


def format_markdown_report(results: Dict[str, Any], version: str = "2.0.0") -> str:
    """Формирует структурированный текстовый отчёт расчёта в формате Markdown."""
    c = results["circuit"]
    diff = abs(c["P_in"] - (c["P_out"] + c["P_cu"] + c["P_mos"]))
    zvs_tag = (
        "ZVS индуктивный (мягкая коммутация)"
        if c["phase_deg"] >= 0
        else "Жесткая коммутация (емкостной ток)"
    )

    return f"""# Отчёт WPT Coil Designer & Analyzer v{version}
**Дата расчёта**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Режим коммутации**: {zvs_tag}

## 1. Геометрия контуров и обмоток
- Передатчик Tx: D_нар = {results['tx_Dout']} мм, D_вн = {results['tx_Din']} мм, витков N1 = {results['tx_N']}
- Приемник Rx: D_нар = {results['rx_Dout']} мм, D_вн = {results['rx_Din']} мм, витков N2 = {results['rx_N']}
- Литцендрат: {results['n_strands']} жил × Ø{results['d_strand']} мм
- Осевое расстояние между катушками d: {results['dist_mm']} мм

## 2. Электромагнитные параметры
- Индуктивность Tx L1: {results['L1']*1e6:.2f} мкГн
- Индуктивность Rx L2: {results['L2']*1e6:.2f} мкГн
- Взаимная индуктивность M: {results['M']*1e6:.3f} мкГн
- Коэффициент связи k: {results['k']:.4f} (k_кр = {results['k_crit']:.3f}, k_опт = {results['k_opt']:.3f})
- Резонансная емкость C1 / C2: {results['C1']*1e9:.2f} нФ / {results['C2']*1e9:.2f} нФ
- Добротность контуров Q1 / Q2: {results['Q1']:.1f} / {results['Q2']:.1f}
- Активное сопротивление R_ac (Tx / Rx): {results['R1_ac']*1e3:.1f} мОм / {results['R2_ac']*1e3:.1f} мОм

## 3. Энергетический баланс (First Harmonic Approximation)
- Напряжение питания шины: {results['V_bus']} В | Нагрузка: {results['R_load']} Ом
- Рабочая частота инвертора: {results['f_drive_kHz']:.2f} кГц
- Ток первичного контура I1 (RMS): {c['I1_rms']:.2f} А
- Ток вторичного контура I2 (RMS): {c['I2_rms']:.2f} А
- Постоянное напряжение на нагрузке U_вых: {c['V_out_dc']:.2f} В
- Входная потребляемая мощность P_вх: {c['P_in']:.2f} Вт
- Полезная выходная мощность P_вых: {c['P_out']:.2f} Вт
- Суммарные потери в меди обмоток P_cu: {c['P_cu']:.3f} Вт
- Потери в ключах MOSFET P_mos: {c['P_mos']:.3f} Вт
- Результирующий КПД тракта: {c['eta']*100:.1f} %
- Фазовый угол входного импеданса: {c['phase_deg']:+.1f}°
- Инвариант сохранения энергии: P_вх - (P_вых + P_пот) = {diff:.2e} Вт
"""
