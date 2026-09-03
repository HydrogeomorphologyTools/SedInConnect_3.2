# -*- coding: utf-8 -*-
"""
SedInConnect QGIS Plugin entry point.
Includes automatic dependency verification and auto-installer for any missing Python packages.
"""

import sys
import subprocess


def ensure_dependencies():
    """Check required packages (numba, numpy, scipy, matplotlib) and prompt auto-install if missing."""
    missing = []
    for pkg in ["numba", "numpy", "scipy", "matplotlib"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        from PyQt5.QtWidgets import QMessageBox
        res = QMessageBox.question(
            None,
            "SedInConnect — Dependency Setup",
            "SedInConnect requires the following scientific Python package(s) for native high-performance calculations in QGIS:\n\n"
            + "\n".join([f"  • {p}" for p in missing])
            + "\n\nWould you like QGIS to automatically download and install them now?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
                QMessageBox.information(
                    None,
                    "SedInConnect",
                    f"Successfully installed {', '.join(missing)}!\nPlease enable the plugin in QGIS Plugin Manager."
                )
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "Installation Error",
                    f"Failed to install dependencies automatically:\n{e}\n\nPlease run in terminal:\n{sys.executable} -m pip install {' '.join(missing)}"
                )


def classFactory(iface):
    """Load SedInConnectPlugin class from file plugin."""
    ensure_dependencies()
    from .plugin import SedInConnectPlugin
    return SedInConnectPlugin(iface)
