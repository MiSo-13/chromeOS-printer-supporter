"""삼성 x86_64 공식 다운로드 승인과 PPD 연결 UI 검증 (실제 다운로드/등록 없음)."""
import os
import subprocess
import sys
import textwrap


def test_samsung_vendor_consent_sets_ppd_but_does_not_register():
    script = textwrap.dedent("""
        import time
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import identity_from_attributes
        from printer_supporter.driver_recommendation import recommend_drivers
        from printer_supporter.driver_installation import DriverInstallPlan
        from printer_supporter.samsung_uld import (
            SamsungInstallResult, SAMSUNG_ULD_URL, SAMSUNG_ULD_SHA256,
        )
        import printer_supporter.setup_ui as setup_module

        app = QApplication([])
        calls = []
        class FakeAdvisor:
            def advise(self, device, identity):
                return recommend_drivers(device, identity, ())
        class FakeInstaller:
            def plan(self, identity):
                return DriverInstallPlan(
                    identity.manufacturer, identity.name,
                    "Samsung 공식 다운로드", "https://www.samsung.com/sec/support/",
                    "공식 Linux 파일",
                    "samsung-uld-m2030w", "available", "SHA 확인",
                    SAMSUNG_ULD_URL, "Samsung 공식 ULD", "samsung-uld",
                    SAMSUNG_ULD_URL, SAMSUNG_ULD_SHA256,
                )
            def install(self, identity, plan, *, approved=False):
                calls.append((identity.name, approved))
                assert approved
                return SamsungInstallResult(
                    "삼성 공식 PPD 및 인쇄 필터 설치 완료",
                    "/tmp/Samsung_M203x_Series.ppd",
                )
        def identify(device):
            return identity_from_attributes(device, {
                "printer-make-and-model": ("Samsung M203x Series",),
            })

        widget = setup_module.PrinterSetupWidget(
            identifier=identify, advisor=FakeAdvisor(), installer=FakeInstaller(),
        )
        widget.show()
        app.processEvents()
        widget._select_device(DiscoveredPrinter(
            "Samsung M203x Series", "ipp://192.168.1.55/ipp/print", "ipp",
        ))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            app.processEvents()
            if widget.install_button.isEnabled():
                break
            time.sleep(0.01)
        assert widget.install_plan is not None
        assert widget.install_plan.source_kind == "samsung-uld"
        assert widget.install_button.isEnabled()
        assert "삼성" in widget.resolution_status.text()
        confirmations = []
        def deny(*args, **kwargs):
            confirmations.append(kwargs)
            return False
        setup_module.confirm_action = deny
        widget.install_driver()
        assert not calls
        assert SAMSUNG_ULD_URL in confirmations[0]["details"]
        assert SAMSUNG_ULD_SHA256 in confirmations[0]["details"]
        assert "libcupsimage2" in confirmations[0]["details"]
        assert "install.sh" in confirmations[0]["details"]

        setup_module.confirm_action = lambda *args, **kwargs: True
        QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        widget.install_driver()
        widget.pool.waitForDone(5000)
        for _ in range(40):
            app.processEvents()
            if widget.ppd_path.text():
                break
        assert calls == [("Samsung M203x Series", True)]
        assert widget.driver.currentData() == "ppd"
        assert widget.ppd_path.text() == "/tmp/Samsung_M203x_Series.ppd"
        assert not widget._install_busy
        assert not widget.install_button.isEnabled()
        widget.pool.waitForDone(5000)
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
