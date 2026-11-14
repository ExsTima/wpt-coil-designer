"""
FEMM 4.2 Automated FEA Verification Runner.
Executes axisymmetric 2D magnetostatic/eddy-current FEA simulations
and compares results with analytical models.
"""

import logging
import sys
import os
import tempfile
import shutil
import threading
from typing import Dict, Any, List, Tuple, Optional, Callable
from dataclasses import dataclass
import numpy as np

from ..core.constants import FERRITE_OVERHANG_M
from ..core.winding import min_coil_gap_m

logger = logging.getLogger(__name__)


def is_femm_available() -> Tuple[bool, str]:
    """
    Проверяет доступность среды FEMM 4.2:
    - ОС должна быть Windows (ActiveX/COM);
    - установлена библиотека pyfemm.
    Возвращает кортеж (is_available, message).
    """
    if sys.platform != "win32":
        return False, "Интеграция с FEMM 4.2 доступна только на ОС Windows (требуются COM/ActiveX и FEMM 4.2)."
    try:
        import femm  # noqa: F401
        return True, ""
    except ImportError:
        return False, "Модуль pyfemm не установлен. Установите: pip install pyfemm"
    except Exception as e:
        return False, f"Ошибка при обращении к pyfemm: {e}"


def close_femm() -> None:
    """Безопасное закрытие открытого окна/сеанса FEMM 4.2."""
    if sys.platform != "win32":
        return
    try:
        import femm
        femm.closefemm()
    except Exception as exc:
        logger.debug("Ignoring close_femm error: %s", exc)


@dataclass
class VerificationRow:
    parameter: str
    analytical: str
    femm: str
    error_pct: str


@dataclass
class FEMMResult:
    L1_H: float
    L2_H: float
    M_H: float
    k: float
    R1_ac_Ohm: float
    report_rows: List[Tuple[str, str, str, str]]
    screenshot_path: Optional[str] = None
    fem_file_path: Optional[str] = None
    ans_file_path: Optional[str] = None


def run_femm_simulation(
    results: Dict[str, Any],
    output_dir: Optional[str] = None,
    save_screenshot: bool = True,
    screenshot_path: Optional[str] = None,
    keep_open: bool = False,
    stop_event: Optional[threading.Event] = None,
    on_complete: Optional[Callable[[FEMMResult], None]] = None
) -> FEMMResult:
    """
    Запускает конечно-элементное моделирование в FEMM 4.2 через ActiveX COM.
    Сравнивает численные результаты с аналитической моделью (L1, L2, M, k, R1_ac).
    """
    avail, err_msg = is_femm_available()
    if not avail:
        raise RuntimeError(err_msg)

    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception as exc:
        logger.debug("pythoncom.CoInitialize skipped: %s", exc)

    import femm

    femm_opened = False
    try:
        try:
            femm.closefemm()
        except Exception as exc:
            logger.debug("Pre-run femm.closefemm ignored: %s", exc)

        r = results
        f_Hz = r['f_drive_kHz'] * 1000.0
        I_tx = max(r.get('circuit', {}).get('I1_rms', 1.0), 1.0)
        dist_mm = r['dist_mm']
        d_strand = r['d_strand']
        n_strands = r['n_strands']

        lay_tx, lay_rx = r['lay_tx'], r['lay_rx']
        half_tx = lay_tx.D_wire_m * 1000.0 * np.sqrt(np.pi) / 4.0
        half_rx = lay_rx.D_wire_m * 1000.0 * np.sqrt(np.pi) / 4.0

        if dist_mm < min_coil_gap_m(lay_tx, lay_rx) * 1000.0:
            raise ValueError("Зазор между катушками меньше суммарной толщины обмоток — увеличьте d.")

        femm.openfemm()
        femm_opened = True
        femm.newdocument(0)
        femm.mi_probdef(f_Hz, 'millimeters', 'axi', 1e-8, 0, 30)

        femm.mi_addmaterial('Air', 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        femm.mi_addmaterial('Copper_Litz_FEMM', 1, 1, 0, 0, 59.5, 0, 0, 1, 5, 0, 0, n_strands, d_strand)
        femm.mi_addmaterial('Ferrite_MnZn', 2000, 2000, 0, 0, 0, 0, 0, 1, 0, 0, 0)

        femm.mi_addcircprop('Tx_Coil', I_tx, 1)
        femm.mi_addcircprop('Rx_Coil', 0.0, 1)

        def draw_block(r1, z1, r2, z2, mat, circ='', turns=0, msize=0.6):
            femm.mi_drawrectangle(r1, z1, r2, z2)
            rm, zm = (r1 + r2) / 2.0, (z1 + z2) / 2.0
            femm.mi_addblocklabel(rm, zm)
            femm.mi_selectlabel(rm, zm)
            femm.mi_setblockprop(mat, 0, msize, circ, 0, 0, turns)
            femm.mi_clearselected()

        for rc, zc in zip(lay_tx.r * 1000.0, lay_tx.z * 1000.0, strict=True):
            draw_block(rc - half_tx, zc - half_tx, rc + half_tx, zc + half_tx, 'Copper_Litz_FEMM', 'Tx_Coil', 1, msize=0.35)
        for rc, zc in zip(lay_rx.r * 1000.0, lay_rx.z * 1000.0, strict=True):
            zr = dist_mm - zc
            draw_block(rc - half_rx, zr - half_rx, rc + half_rx, zr + half_rx, 'Copper_Litz_FEMM', 'Rx_Coil', 1, msize=0.35)

        H1_f = lay_tx.H_m * 1000.0
        H2_f = lay_rx.H_m * 1000.0
        r_fer_tx = r['tx_Dout'] / 2.0 + FERRITE_OVERHANG_M * 1000.0
        r_fer_rx = r['rx_Dout'] / 2.0 + FERRITE_OVERHANG_M * 1000.0
        draw_block(0.0, -H1_f - 2.0, r_fer_tx, -H1_f, 'Ferrite_MnZn', msize=0.7)
        draw_block(0.0, dist_mm + H2_f, r_fer_rx, dist_mm + H2_f + 2.0, 'Ferrite_MnZn', msize=0.7)

        r_domain = max(r_fer_tx, r_fer_rx) * 2.4 + dist_mm
        z_center = dist_mm / 2.0
        r_air_lbl = max(r_fer_tx, r_fer_rx) + 4.0
        femm.mi_addblocklabel(r_air_lbl, z_center)
        femm.mi_selectlabel(r_air_lbl, z_center)
        femm.mi_setblockprop('Air', 1, 0, '', 0, 0, 0)
        femm.mi_clearselected()

        femm.mi_makeABC(7, r_domain, 0.0, z_center, 0)

        temp_fem = os.path.join(tempfile.gettempdir(), "wpt_auto_verification.fem")
        femm.mi_saveas(temp_fem)
        femm.mi_analyze()
        femm.mi_loadsolution()

        tx_props = femm.mo_getcircuitproperties('Tx_Coil')
        rx_props = femm.mo_getcircuitproperties('Rx_Coil')

        L1_femm = abs(tx_props[2]) / I_tx
        M_femm  = abs(rx_props[2]) / I_tx
        R1_femm = float(np.real(tx_props[1] / tx_props[0])) if abs(tx_props[0]) > 1e-9 else r['R1_ac']

        femm.mo_close()

        # Честный расчет L2 вторым прогоном (ток в Rx, Tx обесточен)
        femm.mi_modifycircprop('Tx_Coil', 1, 0.0)
        femm.mi_modifycircprop('Rx_Coil', 1, I_tx)
        femm.mi_analyze()
        femm.mi_loadsolution()

        rx_props_self = femm.mo_getcircuitproperties('Rx_Coil')
        L2_femm = abs(rx_props_self[2]) / I_tx
        k_femm  = M_femm / np.sqrt(L1_femm * L2_femm) if (L1_femm * L2_femm) > 0 else 0.0

        try:
            femm.mo_showdensityplot(1, 0, 0.0015, 0.0, 'bmag')
            femm.mo_zoom(-2, -15, r_domain * 0.65, dist_mm + 20)
            femm.main_restore()
        except Exception as exc:
            logger.warning("FEMM post-processing display error: %s", exc)

        target_screenshot = None
        if save_screenshot:
            temp_bmp = os.path.join(tempfile.gettempdir(), "femm_verification_plot.bmp")
            if screenshot_path:
                target_screenshot = screenshot_path
            else:
                dest_dir = output_dir or os.getcwd()
                target_screenshot = os.path.join(dest_dir, "femm_verification_screenshot.png")
            try:
                femm.mo_savebitmap(temp_bmp)
                if os.path.exists(temp_bmp):
                    from PIL import Image
                    with Image.open(temp_bmp) as im:
                        im.save(target_screenshot)
            except Exception as exc:
                logger.warning("Failed to save FEMM screenshot: %s", exc)
                target_screenshot = None

        saved_fem = None
        saved_ans = None
        if output_dir:
            try:
                saved_fem = os.path.join(output_dir, "wpt_auto_verification.fem")
                shutil.copyfile(temp_fem, saved_fem)
                ans_f = temp_fem.replace(".fem", ".ans")
                if os.path.exists(ans_f):
                    saved_ans = os.path.join(output_dir, "wpt_auto_verification.ans")
                    shutil.copyfile(ans_f, saved_ans)
            except Exception as exc:
                logger.warning("Failed to save FEMM artifacts to %s: %s", output_dir, exc)

        def err_pct(v_py, v_fe):
            return abs(v_py - v_fe) / max(abs(v_fe), 1e-12) * 100.0

        report_rows = [
            ("Индуктивность передатчика L1, мкГн", f"{r['L1']*1e6:.2f}", f"{L1_femm*1e6:.2f}", f"{err_pct(r['L1'], L1_femm):.2f} %"),
            ("Индуктивность приемника L2, мкГн", f"{r['L2']*1e6:.2f}", f"{L2_femm*1e6:.2f}", f"{err_pct(r['L2'], L2_femm):.2f} %"),
            (f"Взаимная индуктивность M (d={dist_mm:.0f} мм), мкГн", f"{r['M']*1e6:.3f}", f"{M_femm*1e6:.3f}", f"{err_pct(r['M'], M_femm):.2f} %"),
            ("Коэффициент магнитной связи k", f"{r['k']:.4f}", f"{k_femm:.4f}", f"{err_pct(r['k'], k_femm):.2f} %"),
            ("Активное ВЧ-сопротивление обмотки R вч (Tx), мОм", f"{r['R1_ac']*1e3:.1f}", f"{R1_femm*1e3:.1f}", f"{err_pct(r['R1_ac'], R1_femm):.2f} %")
        ]

        result = FEMMResult(
            L1_H=L1_femm,
            L2_H=L2_femm,
            M_H=M_femm,
            k=k_femm,
            R1_ac_Ohm=R1_femm,
            report_rows=report_rows,
            screenshot_path=target_screenshot,
            fem_file_path=saved_fem,
            ans_file_path=saved_ans
        )

        if on_complete is not None:
            on_complete(result)

        if keep_open and stop_event is not None:
            stop_event.wait()

        return result

    finally:
        if femm_opened:
            try:
                femm.closefemm()
            except Exception as exc:
                logger.debug("Cleanup femm.closefemm error: %s", exc)
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception as exc:
            logger.debug("Cleanup pythoncom.CoUninitialize skipped: %s", exc)
