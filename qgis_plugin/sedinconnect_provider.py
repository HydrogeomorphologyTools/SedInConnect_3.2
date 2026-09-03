# -*- coding: utf-8 -*-
"""
QGIS Processing Provider for SedInConnect.
"""

import os
from qgis.core import QgsProcessingProvider
from PyQt5.QtGui import QIcon
from .sedinconnect_algorithm import SedInConnectAlgorithm


class SedInConnectProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def loadAlgorithms(self):
        self.addAlgorithm(SedInConnectAlgorithm())

    def id(self):
        return 'sedinconnect'

    def name(self):
        return 'SedInConnect'

    def longName(self):
        return 'SedInConnect Sediment Connectivity'

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()
