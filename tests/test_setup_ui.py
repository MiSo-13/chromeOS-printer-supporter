"""lpinfo 접근 거부가 앱 시작/수동 등록을 방해하지 않는지 검증."""

from subprocess import CompletedProcess

import pytest

try:
    from PyQt6.QtWidgets import QApplication
    from printer_supporter.setup_ui import PrinterSetupWidget
except ImportError as exc:
    pytest.skip(f"GUI 시스템 라이브러리 없음: {exc}", allow_module_level=True)

from printer_supporter.discovery import DiscoveryService


def test_setup_does_not_search_automatically(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    calls = []

    def forbidden(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 1, "", "lpinfo: Forbidden")

    widget = PrinterSetupWidget(service=DiscoveryService(runner=forbidden))
    assert calls == []
    assert widget.scan_button.isEnabled()

    widget._search_failed("lpinfo: Forbidden")
    assert widget.scan_button.isEnabled()
    assert "IP 주소 직접 입력" in widget.status.text()

    widget.ip_input.setText("192.168.6.147")
    widget.protocol.setCurrentIndex(widget.protocol.findData("socket"))
    widget.apply_manual()
    assert widget.uri.text() == "socket://192.168.6.147:9100"
    widget.close()
