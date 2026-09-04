# -*- coding: utf-8 -*-

"""GUI 入口。"""

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName('图片自动归类')
    window = MainWindow()
    window.show()
    return app.exec()
