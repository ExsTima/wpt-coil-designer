"""
Entry point for WPT Coil Designer & Analyzer application.
"""

import logging
import sys
import tkinter as tk

logger = logging.getLogger(__name__)


def configure_dpi_awareness() -> None:
    """Настраивает масштабирование интерфейса с учётом DPI монитора на Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return

    try:
        # Per-Monitor V2 DPI Awareness
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception as exc:
        logger.debug("SetProcessDpiAwarenessContext failed: %s", exc)

    for mode in (2, 1):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(mode)
            return
        except Exception as exc:
            logger.debug("SetProcessDpiAwareness(%s) failed: %s", mode, exc)

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as exc:
        logger.debug("SetProcessDPIAware failed: %s", exc)


def main():
    from wpt_designer.gui.app_window import WPTCalculatorApp

    configure_dpi_awareness()
    root = tk.Tk()
    WPTCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
