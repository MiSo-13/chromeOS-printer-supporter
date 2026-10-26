"""검색 실패 도움말과 단일 프린터 자동 선택을 Qt 오프스크린에서 확인."""
import os
import subprocess
import sys
import textwrap


def test_empty_search_and_manual_selection_guidance():
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        widget = PrinterSetupWidget()
        widget.show()
        app.processEvents()
        assert widget.pool.maxThreadCount() == 2
        assert not widget.discovery_help_button.isChecked()
        assert widget.discovery_help.isHidden()
        assert "모델명" in widget.discovery_help_text.text()
        assert "IPv4" in widget.discovery_help_text.text()

        widget._populate([])
        assert widget.discovery_help_button.isChecked()
        assert not widget.discovery_help.isHidden()
        assert "모델과 IP 주소" in widget.status.text()

        widget.discovery_help_button.click()
        assert widget.discovery_help.isHidden()
        widget._search_failed("lpinfo: Forbidden")
        assert not widget.discovery_help.isHidden()
        assert "IP 주소 직접 입력" in widget.status.text()

        selected = []
        widget._select_device = lambda device: selected.append(device)
        widget._scan_busy = True
        widget._auto_select_search_result = True
        widget.ip_input.setText("192.168.1.55")
        widget.apply_manual()
        assert selected[-1].uri == "ipp://192.168.1.55/ipp/print"
        assert not widget._auto_select_search_result

        widget._populate([DiscoveredPrinter(
            "Other", "ipp://192.168.1.70/ipp/print", "ipp",
        )])
        # 검색 진행 중 명시적으로 선택한 프린터를 덮어쓰지 않습니다.
        assert len(selected) == 1

        widget._auto_select_search_result = True
        widget._populate([DiscoveredPrinter(
            "Other", "ipp://192.168.1.70/ipp/print", "ipp",
        )])
        assert len(selected) == 2
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
