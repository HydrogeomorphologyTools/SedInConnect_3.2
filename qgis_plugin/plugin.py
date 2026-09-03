# -*- coding: utf-8 -*-
"""
Main QGIS Plugin class for SedInConnect.
Manages toolbar actions, menus, and Processing provider registration.
Cross-platform Qt5/Qt6 compatible.
"""

import os
from qgis.core import QgsApplication

try:
    from qgis.PyQt.QtGui import QIcon
    try:
        from qgis.PyQt.QtWidgets import QAction
    except ImportError:
        from qgis.PyQt.QtGui import QAction
except ImportError:
    try:
        from PyQt5.QtWidgets import QAction
        from PyQt5.QtGui import QIcon
    except ImportError:
        from PyQt6.QtGui import QAction, QIcon

from .sedinconnect_provider import SedInConnectProvider
from .sedinconnect_dialog import SedInConnectDialog


class SedInConnectPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dialog = None

    def initProcessing(self):
        self.provider = SedInConnectProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), 'logo2.png')

        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, "SedInConnect 3.2 — Connectivity Assessment", self.iface.mainWindow())
        self.action.setToolTip("SedInConnect 3.2 — Stand-alone Sediment Connectivity Assessment (MORPHEUS PRIN 2023-2026)")
        self.action.setStatusTip("Calculate Sediment Connectivity Index (IC)")
        self.action.triggered.connect(self.run)

        # Add to standard Plugins Toolbar and Raster Toolbar
        self.iface.addToolBarIcon(self.action)
        self.iface.addRasterToolBarIcon(self.action)

        # Add to Menu items
        self.iface.addPluginToMenu("&SedInConnect", self.action)
        self.iface.addPluginToRasterMenu("&SedInConnect", self.action)

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
        if self.action:
            self.iface.removePluginMenu("&SedInConnect", self.action)
            self.iface.removePluginRasterMenu("&SedInConnect", self.action)
            self.iface.removeRasterToolBarIcon(self.action)
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        if not self.dialog:
            self.dialog = SedInConnectDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
