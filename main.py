"""
Launcher for WPT Coil Designer & Analyzer.
"""

import sys
import os

# Redirect standard file descriptors only in pythonw mode (when stdout/stderr are None)
if sys.platform == "win32" and (sys.stdout is None or sys.stderr is None):
    try:
        null_fd = os.open(os.devnull, os.O_RDWR)
        try:
            for fd in (1, 2):
                try:
                    os.dup2(null_fd, fd)
                except OSError:
                    pass
        finally:
            os.close(null_fd)
    except OSError:
        pass

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Add src to sys.path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from wpt_designer.main import main

if __name__ == "__main__":
    main()
