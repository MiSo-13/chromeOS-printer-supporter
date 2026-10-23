"""프린터 설정 화면에서 우선 목록 표시와 일반 경로를 확인합니다."""
import os
import subprocess
import sys
import textwrap


def test_focus_model_guidance_and_generic_fallback_in_gui():
    script = textwrap.dedent("""
        import time
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import (
            identity_from_attributes, unknown_identity,
        )
        from printer_supporter.driver_recommendation import recommend_drivers
        from printer_supporter.driver_installation import DriverInstallPlan
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])

        class FakeAdvisor:
            def advise(self, device, identity):
                return recommend_drivers(device, identity, ())

        class FakeInstaller:
            def plan(self, identity):
                return DriverInstallPlan(
                    identity.manufacturer, identity.name, None, None, "확인 중",
                    None, "not_applicable", "설치 후보 없음",
                )

        def identifier(device):
            if device.scheme == "socket":
                return unknown_identity(device)
            return identity_from_attributes(device, {
                "printer-make-and-model": (device.name,),
            })

        widget = PrinterSetupWidget(
            identifier=identifier, advisor=FakeAdvisor(),
            installer=FakeInstaller(),
        )
        widget.show()
        app.processEvents()

        def choose(name, scheme="ipp"):
            selected = DiscoveredPrinter(
                name, f"{scheme}://192.168.6.147/ipp/print", scheme,
            )
            widget._select_device(selected)
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                app.processEvents()
                if widget.identity_result is not None and widget.focus_summary.text() != (
                    "우선 지원 안내 목록 확인 중…"
                ):
                    break
                time.sleep(0.01)
            assert widget.identity_result is not None
            return widget.focus_summary.text(), widget.focus_detail.text()

        summary, detail = choose("HP LaserJet Pro M404dw")
        assert "우선 안내 모델" in summary
        assert "IPP Everywhere" in detail
        assert "실제 Chromebook 인쇄 성공" in detail

        summary, detail = choose("Samsung SL-M2030W", "socket")
        assert "목록과 이름 일치" in summary
        assert "미검증" in detail

        summary, detail = choose("Kyocera TASKalfa 2553ci")
        assert summary == "일반 호환성 확인"
        assert "기존 IPP" in detail

        widget.pool.waitForDone(5000)
        app.processEvents()
        widget.close()
        app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=30,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
