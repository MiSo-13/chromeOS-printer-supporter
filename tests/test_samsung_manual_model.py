"""IPP를 제공하지 않는 Samsung Socket 프린터의 직접 모델 확인 회귀 테스트."""
import os
import subprocess
import sys
import textwrap


def test_socket_printer_needs_explicit_model_confirmation_before_download():
    script = textwrap.dedent("""
        import time
        from PyQt6.QtWidgets import QApplication, QInputDialog
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import unknown_identity
        from printer_supporter.driver_recommendation import recommend_drivers
        from printer_supporter.driver_installation import DriverInstallPlan
        from printer_supporter.samsung_uld import SAMSUNG_ULD_URL, SAMSUNG_ULD_SHA256
        import printer_supporter.setup_ui as sm

        app = QApplication([])
        class FakeAdvisor:
            def advise(self, device, identity):
                return recommend_drivers(device, identity, ())
        class FakeInstaller:
            def plan(self, identity):
                confirmed = identity.source == "사용자 확인(명시적 선택)"
                return DriverInstallPlan(
                    identity.manufacturer, identity.name,
                    "Samsung Linux", "https://www.samsung.com/sec/support/",
                    "공식",
                    "samsung-uld-m2030w" if confirmed else None,
                    "available" if confirmed else "not_applicable", "확인",
                    SAMSUNG_ULD_URL if confirmed else None, "Samsung",
                    "samsung-uld" if confirmed else "apt",
                    SAMSUNG_ULD_URL if confirmed else None,
                    SAMSUNG_ULD_SHA256 if confirmed else None,
                )
        widget = sm.PrinterSetupWidget(
            identifier=lambda d: unknown_identity(d),
            advisor=FakeAdvisor(), installer=FakeInstaller(),
        )
        widget.show()
        app.processEvents()
        widget._select_device(DiscoveredPrinter(
            "Samsung M203x Series", "socket://192.168.1.50:9100", "socket",
        ))
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            app.processEvents()
            if widget.identity_result:
                break
            time.sleep(0.01)
        assert widget.identity_result is not None
        assert widget.confirm_model_button.isEnabled()
        assert not widget.install_button.isEnabled()
        calls = []
        QInputDialog.getItem = lambda *a, **kw: ("Samsung SL-M2030W", True)
        sm.confirm_action = lambda *a, **kw: calls.append(kw) or False
        widget.confirm_model_button.click()
        assert widget.identity_result.source != "사용자 확인(명시적 선택)"
        assert len(calls) == 1
        sm.confirm_action = lambda *a, **kw: calls.append(kw) or True
        widget.confirm_model_button.click()
        app.processEvents()
        assert widget.identity_result.source == "사용자 확인(명시적 선택)"
        assert widget.identity_result.name == "Samsung SL-M2030W"
        assert widget.install_plan.source_kind == "samsung-uld"
        assert widget.install_button.isEnabled()
        assert not widget.confirm_model_button.isEnabled()
        assert len(calls) == 2
        widget.pool.waitForDone(4000)
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
