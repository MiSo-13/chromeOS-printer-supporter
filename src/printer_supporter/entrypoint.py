"""PyInstaller 릴리즈 실행 진입점."""
from __future__ import annotations

import sys

from printer_supporter import __version__


def smoke_test() -> int:
    """패키징된 Qt UI만 점검합니다. CUPS 명령·설치·출력은 호출하지 않습니다."""
    from PyQt6.QtWidgets import QApplication
    from printer_supporter.main import MainWindow
    from printer_supporter.qt_platform import _xcb_plugin

    if getattr(sys, "frozen", False) and _xcb_plugin() is None:
        raise RuntimeError("Crostini X11(xcb) 플랫폼 플러그인이 번들에 없습니다.")
    app = QApplication([])
    original_refresh = MainWindow.refresh_all
    original_check = MainWindow.check_dependencies
    try:
        MainWindow.refresh_all = lambda self: None
        MainWindow.check_dependencies = lambda self, **kwargs: None
        window = MainWindow()
        window.timer.stop()
        window.show()
        app.processEvents()
        assert window.menuBar().actions(), "상단 메뉴 초기화 실패"
        assert window.navigation, "기본 화면 초기화 실패"
        window.close()
        app.processEvents()
    finally:
        MainWindow.refresh_all = original_refresh
        MainWindow.check_dependencies = original_check
    return 0


def run() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--version":
        print(__version__)
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--smoke-test":
        return smoke_test()

    from printer_supporter.main import main

    main()
    return 0


if __name__ == "__main__":
    sys.exit(run())
