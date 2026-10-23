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


def test_model_identification_results_display_and_stale_results_are_ignored(monkeypatch):
    import time
    from printer_supporter.discovery import DiscoveredPrinter
    from printer_supporter.identification import (
        PrinterIdentity, identity_from_attributes, unknown_identity,
    )

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    def identify(device):
        if device.scheme == "socket":
            return unknown_identity(device)
        return identity_from_attributes(device, {
            "printer-make-and-model": ("Samsung M203x Series",),
            "ipp-versions-supported": ("2.0",),
            "document-format-supported": ("image/pwg-raster",),
        })

    widget = PrinterSetupWidget(
        service=DiscoveryService(), identifier=identify,
    )
    widget.show()
    ipp = DiscoveredPrinter("Service Name", "ipp://192.168.6.151/ipp/print", "ipp")
    socket = DiscoveredPrinter("Samsung M203x Series", "socket://192.168.6.147:9100", "socket")

    widget._select_device(ipp)
    deadline = time.monotonic() + 3
    while widget.identity_result is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert widget.identity_result is not None
    assert widget.identity_result.manufacturer == "Samsung"
    assert "Samsung M203x Series" in widget.identity_summary.text()
    assert "드라이버리스 후보" in widget.identity_evidence.text()
    assert "IPP 장치 응답" in widget.identity_evidence.text()
    assert widget.driver.currentData() == "everywhere"

    previous_generation = widget.identity_generation
    widget._select_device(socket)
    # 늦게 돌아온 이전 IPP 장치의 결과는 화면에 반영하면 안 됩니다.
    stale = identify(ipp)
    widget._identity_ready((previous_generation, ipp, stale))
    deadline = time.monotonic() + 3
    while widget.identity_result is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert widget.current_device == socket
    assert widget.driver.currentData() == "ppd"
    assert widget.identity_result is not None
    assert widget.identity_result.driverless == "unknown"
    assert "미확인" in widget.identity_evidence.text()
    widget.close()


def test_queue_name_is_updated_until_user_edits(monkeypatch):
    from printer_supporter.discovery import DiscoveredPrinter
    from printer_supporter.identification import unknown_identity
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    widget = PrinterSetupWidget(identifier=unknown_identity)
    first = DiscoveredPrinter("Samsung Printer", "socket://192.168.1.2:9100", "socket")
    second = DiscoveredPrinter("Canon Printer", "socket://192.168.1.3:9100", "socket")
    widget._select_device(first)
    assert widget.queue_name.text() == "Samsung_Printer"
    widget._select_device(second)
    assert widget.queue_name.text() == "Canon_Printer"
    widget.queue_name.setText("Custom_Queue")
    widget._queue_name_edited("Custom_Queue")
    widget._select_device(first)
    assert widget.queue_name.text() == "Custom_Queue"
    widget.close()
