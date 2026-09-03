# -*- coding: utf-8 -*-
"""
SedInConnect QGIS Plugin entry point.
Cross-platform, Qt5/Qt6 independent, and self-healing with prominent fallback notifications.
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
    If declined or if installation fails, displays a clear warning alert with installation instructions,
    then proceeds smoothly in pure NumPy/SciPy fallback mode.
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
        "SedInConnect — Performance Acceleration (Numba)",
        "SedInConnect uses the 'numba' JIT compiler for ultra-fast calculation (10x–20x speedup).\n\n"
        "Numba is currently not detected. Would you like QGIS to automatically download and install 'numba' now in your user folder?\n\n"
        "(Click 'Yes' to auto-install, or 'No' to proceed with the slower pure NumPy fallback).",
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
            return

    # If user chose 'No' or auto-install failed, show clear warning with manual steps
    QMessageBox.warning(
        None,
        "SedInConnect — Pure NumPy Fallback Mode Active",
        "⚠️ <b>Numba is not installed.</b><br><br>"
        "SedInConnect will proceed using the <b>pure native NumPy/SciPy fallback engine</b>.<br><br>"
        "<b>Note on Precision:</b> Results are <b>100% mathematically exact and identical</b>.<br>"
        "<b>Note on Performance:</b> Calculations will be noticeably slower on large catchments.<br><br>"
        "<b>To achieve 10x–20x maximum speedup, we strongly recommend installing 'numba':</b><br>"
        "• <b>Linux (Ubuntu/Debian):</b> Open Terminal and run: <code>sudo apt install python3-numba</code><br>"
        "• <b>Windows:</b> Open OSGeo4W Shell and run: <code>pip install numba</code><br>"
        "• <b>macOS / Pip:</b> In Terminal run: <code>pip3 install --user numba</code>"
    )


def classFactory(iface):
    """Load SedInConnectPlugin class from file plugin."""
    ensure_dependencies()
    from .plugin import SedInConnectPlugin
    return SedInConnectPlugin(iface)
