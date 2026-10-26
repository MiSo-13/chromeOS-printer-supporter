"""설치 후 CUPS 확인 결과가 사용자에게 표시되는지 Qt 오프스크린에서 검증."""
import os
import subprocess
import sys
import textwrap


def test_cups_verification_result_dialog_and_refresh():
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.driver_installation import AptInstallResult
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        widget = PrinterSetupWidget()
        device = DiscoveredPrinter(
            "HP LaserJet 1020", "ipp://192.168.1.11/ipp/print", "ipp",
        )
        widget.current_device = device
        widget.identity_generation = 3
        events = []
        widget.identify_current = lambda: events.append("refresh")
        QMessageBox.information = lambda *args: events.append(("info", args[1], args[2]))
        QMessageBox.warning = lambda *args: events.append(("warn", args[1], args[2]))

        warning = AptInstallResult("설치했으나 CUPS 모델 확인 필요", "missing")
        widget._driver_install_finished(3, device, warning)
        assert events == [
            ("warn", "드라이버 추가 확인 필요", warning.message),
            "refresh",
        ]
        assert not widget._install_busy

        events.clear()
        success = AptInstallResult("모델명 일치 확인, 출력 미검증", "matched", "hp.ppd")
        widget._driver_install_finished(3, device, success)
        assert events == [
            ("info", "드라이버 설치 확인", success.message),
            "refresh",
        ]
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
