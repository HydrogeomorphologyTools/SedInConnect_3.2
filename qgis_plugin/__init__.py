# -*- coding: utf-8 -*-
"""
SedInConnect QGIS Plugin entry point.
Cross-platform, Qt5/Qt6 independent, and self-healing with zero-dependency fallback.
"""

import sys
import subprocess
from pathlib import Path

# Ensure plugin folder is in sys.path
_p_dir = str(Path(__file__).resolve().parent)
if _p_dir not in sys.path:
    sys.path.insert(0, _p_dir)


def ensure_dependencies():
    """
    Check if numba JIT compiler is available for maximum speed.
    If missing, prompts user for automatic 1-click installation with PEP 668 / user-space flags.
    If declined or offline, falls back gracefully to pure native NumPy/SciPy without blocking.
    """
    try:
        import numba
        return
    except ImportError:
        pass

    try:
        from qgis.PyQt.QtWidgets import QMessageBox
    except ImportError:
        try:
            from PyQt5.QtWidgets import QMessageBox
        except ImportError:
            from PyQt6.QtWidgets import QMessageBox

    btn_yes = getattr(QMessageBox, "Yes", None) or getattr(getattr(QMessageBox, "StandardButton", None), "Yes", None)
    btn_no = getattr(QMessageBox, "No", None) or getattr(getattr(QMessageBox, "StandardButton", None), "No", None)
    buttons = (btn_yes | btn_no) if (btn_yes is not None and btn_no is not None) else QMessageBox.Ok

    res = QMessageBox.question(
        None,
        "SedInConnect — Optional Speed Acceleration",
        "SedInConnect can use the 'numba' JIT compiler for ultra-fast calculation speed.\n\n"
        "Would you like QGIS to automatically download and install 'numba' in your user directory now?\n\n"
        "(Note: If you click 'No', SedInConnect will still work smoothly using native NumPy/SciPy).",
        buttons
    )

    if res == btn_yes:
        installed = False
        # Try installation strategies (PEP 668 --break-system-packages, --user, standard)
        for cmd in [
            [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "numba"],
            [sys.executable, "-m", "pip", "install", "--user", "numba"],
            [sys.executable, "-m", "pip", "install", "numba"],
        ]:
            try:
                subprocess.check_call(cmd)
                installed = True
                break
            except Exception:
                continue

        if installed:
            QMessageBox.information(
                None,
                "SedInConnect",
                "Successfully installed numba! High-speed JIT acceleration is active.\n"
                "Please enable the plugin in QGIS Plugin Manager."
            )
        else:
            QMessageBox.information(
                None,
                "SedInConnect",
                "Could not install numba automatically.\n\n"
                "SedInConnect will continue running in standard native NumPy mode.\n"
                "(On Linux/Debian systems, you can optionally run: sudo apt install python3-numba)"
            )


def classFactory(iface):
    """Load SedInConnectPlugin class from file plugin."""
    ensure_dependencies()
    from .plugin import SedInConnectPlugin
    return SedInConnectPlugin(iface)
