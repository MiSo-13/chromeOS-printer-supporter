"""등록 실행 중 다른 화면의 오류가 중복 등록을 유발하지 않는지 검사."""
import os
import subprocess
import sys
import textwrap


def test_unrelated_errors_do_not_unlock_pending_registration():
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from printer_supporter.setup_ui import PrinterSetupWidget
        from printer_supporter.discovery import DiscoveredPrinter

        app = QApplication([])
        widget = PrinterSetupWidget()
        widget.show()
        app.processEvents()
        device = DiscoveredPrinter(
            "Generic Printer", "ipp://192.168.1.100/ipp/print", "ipp",
        )
        # 비동기 식별 작업이 시작되지 않도록 상태만 설정합니다.
        widget.current_device = device
        widget.register_button.setEnabled(False)
        widget.scan_button.setEnabled(False)
        widget._register_busy = True
        widget._scan_busy = True
        alerts = []
        QMessageBox.warning = lambda *args, **kwargs: alerts.append(args[2])
        widget._error("연결 상태 확인 오류")
        assert widget._register_busy
        assert widget._scan_busy
        assert not widget.register_button.isEnabled()
        assert not widget.scan_button.isEnabled()
        assert alerts == ["연결 상태 확인 오류"]

        widget._registration_failed("권한 없음")
        assert not widget._register_busy
        assert widget._scan_busy
        assert widget.register_button.isEnabled()
        assert not widget.scan_button.isEnabled()
        widget._search_failed("검색 실패")
        assert not widget._scan_busy
        assert widget.scan_button.isEnabled()
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
