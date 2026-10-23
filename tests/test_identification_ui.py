"""프린터 모델 식별 화면을 독립 Qt 프로세스에서 검증합니다.

pytest와 Qt 백그라운드 작업 사이의 객체 수명 충돌을 피합니다.
"""
import os
import subprocess
import sys
import textwrap


def test_printer_identification_ui(tmp_path):
    script = textwrap.dedent("""
        import time
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import identity_from_attributes, unknown_identity
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        def identify(device):
            if device.scheme == "socket":
                return unknown_identity(device)
            return identity_from_attributes(device, {
                "printer-make-and-model": ("Samsung M203x Series",),
                "ipp-versions-supported": ("2.0",),
                "document-format-supported": ("image/pwg-raster",),
            })

        widget = PrinterSetupWidget(identifier=identify)
        widget.show()
        app.processEvents()
        ipp = DiscoveredPrinter("Service Name", "ipp://192.168.6.151/ipp/print", "ipp")
        socket = DiscoveredPrinter("Samsung M203x Series", "socket://192.168.6.147:9100", "socket")

        widget._select_device(ipp)
        deadline = time.monotonic() + 4
        while widget.identity_result is None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.identity_result is not None, "IPP 식별 응답이 도착하지 않았습니다."
        assert widget.identity_result.manufacturer == "Samsung"
        assert "Samsung M203x Series" in widget.identity_summary.text()
        assert "드라이버리스 후보" in widget.identity_evidence.text()
        assert "IPP 장치 응답" in widget.identity_evidence.text()
        assert widget.driver.currentData() == "everywhere"
        assert widget.queue_name.text() == "Service_Name"

        previous_generation = widget.identity_generation
        widget._select_device(socket)
        widget._identity_ready((previous_generation, ipp, identify(ipp)))
        deadline = time.monotonic() + 4
        while widget.identity_result is None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.current_device == socket
        assert widget.driver.currentData() == "ppd"
        assert widget.identity_result is not None
        assert widget.identity_result.driverless == "unknown"
        assert "미확인" in widget.identity_evidence.text()
        assert widget.queue_name.text() == "Samsung_M203x_Series"

        # 수동으로 편집한 CUPS 큐 이름은 다른 프린터를 선택해도 유지됩니다.
        widget.queue_name.setText("Custom_Queue")
        widget._queue_name_edited("Custom_Queue")
        widget._select_device(ipp)
        assert widget.queue_name.text() == "Custom_Queue"

        widget.pool.waitForDone(5000)
        app.processEvents()
        widget.close()
        app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
