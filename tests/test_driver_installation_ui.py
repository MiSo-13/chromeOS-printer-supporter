"""드라이버 설치 안내 화면과 명시적 승인 절차를 실제 Qt 이벤트로 검증."""
import os
import subprocess
import sys
import textwrap


def test_official_support_and_apt_install_consent_ui(tmp_path):
    script = textwrap.dedent("""
        import time
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import identity_from_attributes
        from printer_supporter.driver_recommendation import DriverAdvisor, recommend_drivers
        from printer_supporter.driver_installation import (
            DriverInstallPlan, official_support_for,
        )
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        calls = []
        class FakeAdvisor:
            def advise(self, device, identity):
                return recommend_drivers(device, identity, ())

        class FakeInstaller:
            def plan(self, identity):
                title, url, note = official_support_for(identity)
                if identity.manufacturer == "Brother":
                    return DriverInstallPlan(
                        identity.manufacturer, identity.name, title, url, note,
                        "printer-driver-brlaser", "available",
                        "설치 가능한 APT 패키지 확인 완료",
                    )
                return DriverInstallPlan(
                    identity.manufacturer, identity.name, title, url, note,
                    None, "not_applicable", "자동 설치 후보가 없습니다.",
                )

            def install(self, identity, plan, *, approved=False):
                calls.append((identity.name, plan.package, approved))
                assert approved is True
                return "확인된 배포판 패키지 설치 완료"

        def identify(device):
            if "Samsung" in device.name:
                return identity_from_attributes(device, {
                    "printer-make-and-model": ("Samsung SL-M2030W",),
                })
            return identity_from_attributes(device, {
                "printer-make-and-model": ("Brother HL-L2340D series",),
            })

        widget = PrinterSetupWidget(
            identifier=identify, advisor=FakeAdvisor(), installer=FakeInstaller(),
        )
        widget.show()
        app.processEvents()

        def drain():
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                widget.pool.waitForDone(500)
                app.processEvents()
                if widget.install_plan is not None:
                    break
                time.sleep(0.01)
            assert widget.install_plan is not None

        samsung = DiscoveredPrinter(
            "Samsung SL-M2030W", "ipp://192.168.6.200/ipp/print", "ipp"
        )
        brother = DiscoveredPrinter(
            "Brother HL-L2340D series", "ipp://192.168.6.201/ipp/print", "ipp"
        )
        widget._select_device(samsung)
        drain()
        assert "SL-M2030W" in widget.official_support_label.text()
        assert widget.official_support_button.isEnabled()
        assert not widget.install_button.isEnabled()
        assert widget.install_plan.package is None

        widget._select_device(brother)
        drain()
        assert widget.install_plan.package == "printer-driver-brlaser"
        assert widget.install_button.isEnabled()
        assert widget.official_support_button.isEnabled()

        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.No
        widget.install_driver()
        assert not calls
        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        widget.install_driver()
        widget.pool.waitForDone(5000)
        for _ in range(20):
            app.processEvents()
        assert calls == [("Brother HL-L2340D series", "printer-driver-brlaser", True)]
        # 설치 뒤 모델 정보를 다시 조회하여 CUPS 목록/패키지 상태도 새로고침.
        widget.pool.waitForDone(5000)
        for _ in range(20):
            app.processEvents()
        assert widget.identity_result is not None

        widget.pool.waitForDone(5000)
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=35, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
