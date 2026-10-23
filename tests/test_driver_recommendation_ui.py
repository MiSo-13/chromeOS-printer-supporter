"""추천 결과를 UI에 반영하고 수동 설정을 보존하는 Qt 오프스크린 테스트."""
import os
import subprocess
import sys
import textwrap


def test_driver_recommendation_ui_and_user_selection(tmp_path):
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import identity_from_attributes, unknown_identity
        from printer_supporter.driver_recommendation import (
            InstalledDriver, recommend_drivers,
        )
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])

        class FakeAdvisor:
            def advise(self, device, identity):
                return recommend_drivers(device, identity, (
                    InstalledDriver("drv:///samsung/m203x.ppd", "Samsung M203x Series (SPL)"),
                ))

        def identify(device):
            if device.scheme == "socket":
                return unknown_identity(device)
            return identity_from_attributes(device, {
                "printer-make-and-model": ("Samsung M203x Series",),
            })

        widget = PrinterSetupWidget(identifier=identify, advisor=FakeAdvisor())
        widget.show()
        app.processEvents()

        ipp = DiscoveredPrinter(
            "Samsung M203x Series", "ipp://192.168.6.151/ipp/print", "ipp",
        )
        socket = DiscoveredPrinter(
            "Samsung M203x Series", "socket://192.168.6.147:9100", "socket",
        )
        widget._select_device(ipp)
        widget.pool.waitForDone(5000)
        for _ in range(10):
            app.processEvents()
        widget.pool.waitForDone(5000)
        for _ in range(10):
            app.processEvents()
        assert widget.driver_recommendation is not None, "추천 결과가 표시되지 않았습니다."
        assert widget.driver_recommendation.preferred == "model"
        assert widget.driver.currentData() == "model"
        assert widget.model_choice.currentData() == "drv:///samsung/m203x.ppd"
        assert widget.model_choice.isEnabled()
        assert "CUPS 모델" in widget.recommendation_summary.text()

        # 수동 PPD 선택은 자동 추천 결과로 덮어쓰지 않습니다.
        widget.driver.setCurrentIndex(widget.driver.findData("ppd"))
        widget._mark_driver_user_edited(widget.driver.currentIndex())
        widget._recommendation_ready((
            widget.identity_generation, ipp, widget.driver_recommendation,
        ))
        assert widget.driver.currentData() == "ppd"
        assert widget.ppd_path.isEnabled()

        # Socket 서비스명만으로는 모델을 확정하지 않아 자동 선택하지 않습니다.
        widget._select_device(socket)
        widget.pool.waitForDone(5000)
        for _ in range(10):
            app.processEvents()
        widget.pool.waitForDone(5000)
        for _ in range(10):
            app.processEvents()
        assert widget.driver_recommendation is not None
        assert widget.driver_recommendation.preferred is None
        assert widget.driver.currentData() == "ppd"
        assert widget.model_choice.count() == 2

        # 오래된 IPP 추천은 현재 Socket 상태를 덮어쓰지 않아야 합니다.
        previous_driver = widget.driver.currentData()
        old = recommend_drivers(ipp, identify(ipp), (
            InstalledDriver("drv:///samsung/m203x.ppd", "Samsung M203x Series"),
        ))
        widget._recommendation_ready((widget.identity_generation - 1, ipp, old))
        assert widget.driver.currentData() == previous_driver

        widget.pool.waitForDone(5000)
        widget.close()
        app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
