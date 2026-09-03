# -*- coding: utf-8 -*-
"""
SedInConnect QGIS Plugin entry point.
Cross-platform, Qt5/Qt6 independent, self-healing with dynamic OS-tailored help.
"""

import sys
import platform
import subprocess
from pathlib import Path

# Ensure plugin folder is in sys.path
_p_dir = str(Path(__file__).resolve().parent)
if _p_dir not in sys.path:
    sys.path.insert(0, _p_dir)


def get_os_tailored_instructions():
    """Generate precise, copy-pasteable installation instructions tailored to the user's OS."""
    os_name = platform.system()
    if os_name == "Linux":
        pkg_cmd = "sudo apt install python3-numba"
        try:
            if Path("/etc/os-release").exists():
                txt = Path("/etc/os-release").read_text(encoding="utf-8", errors="ignore").lower()
                if "fedora" in txt or "rhel" in txt:
                    pkg_cmd = "sudo dnf install python3-numba"
                elif "arch" in txt or "manjaro" in txt:
                    pkg_cmd = "sudo pacman -S python-numba"
        except Exception:
            pass

        return (
            f"<b>Detected OS: Linux ({platform.machine()})</b><br><br>"
            f"<b>Recommended solution for your system:</b><br>"
            f"Open Terminal and run:<br>"
            f"<code>{pkg_cmd}</code><br><br>"
            f"<i>Alternative (pip in user space):</i><br>"
            f"<code>{sys.executable} -m pip install --user --break-system-packages numba</code>"
        )
    elif os_name == "Darwin":
        return (
            "<b>Detected OS: macOS (Apple Silicon / Intel)</b><br><br>"
            "<b>Recommended solution for your system:</b><br>"
            "Open Terminal and run:<br>"
            "<code>pip3 install --user numba</code><br><br>"
            "<i>Or inside QGIS Python Console:</i><br>"
            "<code>import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', 'numba'])</code>"
        )
    else:
        return (
            "<b>Detected OS: Windows</b><br><br>"
            "<b>Recommended solution for your system:</b><br>"
            "1. In the Windows Start menu, search and open <b>OSGeo4W Shell</b>.<br>"
            "2. Run: <code>pip install numba</code>"
        )


def ensure_dependencies():
    """
    Check if numba JIT compiler is available for maximum speed.
    If missing, prompts user for automatic 1-click installation.
    If declined or if installation fails, displays a clear OS-tailored warning alert,
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

    os_info = get_os_tailored_instructions()
    QMessageBox.warning(
        None,
        "SedInConnect — Pure NumPy Fallback Active",
        "⚠️ <b>Numba JIT is not installed.</b><br><br>"
        "SedInConnect will proceed using the <b>pure native NumPy/SciPy fallback engine</b>.<br><br>"
        "<b>• Numerical Precision:</b> Results are <b>100% mathematically exact and identical</b>.<br>"
        "<b>• Calculation Speed:</b> Noticeably slower on large catchments without JIT.<br><br>"
        f"{os_info}"
    )


def classFactory(iface):
    """Load SedInConnectPlugin class from file plugin."""
    ensure_dependencies()
    from .plugin import SedInConnectPlugin
    return SedInConnectPlugin(iface)
