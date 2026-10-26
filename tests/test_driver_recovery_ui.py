"""설치 문제 해결 패널이 사용자 동작으로만 대체 경로를 고르는지 테스트."""
import os
import subprocess
import sys
import textwrap


def test_install_failure_recovery_actions_do_not_install_or_register(tmp_path):
    script = textwrap.dedent("""
        from pathlib import Path
        from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import PrinterIdentity
        from printer_supporter.driver_recommendation import DriverRecommendation, InstalledDriver
        from printer_supporter.driver_installation import DriverInstallPlan, AptInstallResult
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        widget = PrinterSetupWidget()
        widget.current_device = DiscoveredPrinter(
            "Samsung ML-1660", "ipp://192.168.1.12/ipp/print", "ipp",
        )
        widget.identity_generation = 4
        widget.identity_result = PrinterIdentity(
            "Samsung ML-1660", "Samsung", "ML-1660", "IPP",
            "IPP 장치 응답", "reported", "조회 완료",
        )
        widget.install_plan = DriverInstallPlan(
            "Samsung", "Samsung ML-1660", "Samsung 지원",
            "https://www.samsung.com/sec/support/", "지원",
            "printer-driver-splix", "available", "APT 가능",
        )
        widget.driver_recommendation = DriverRecommendation(
            None, None, (), "", "", True,
        )
        actions = []
        QMessageBox.warning = lambda *args: actions.append(("warn", args[1]))
        widget._driver_install_failed(4, widget.current_device, "sudo: a password is required")
        assert widget._recovery_issue == "failed"
        assert not widget.recovery_panel.isHidden()
        assert "sudo 권한" in widget.recovery_details.text()
        assert widget.recovery_recheck_button.isEnabled()
        assert widget.recovery_ipp_button.isEnabled()
        assert not widget.recovery_cups_button.isEnabled()
        assert not widget.install_button.isEnabled()

        widget.identify_current = lambda: actions.append(("refresh",))
        widget.recovery_recheck_button.click()
        assert actions[-1] == ("refresh",)
        assert widget._recovery_issue == "failed"
        assert not widget.install_button.isEnabled()

        widget.recovery_ipp_button.click()
        assert widget.driver.currentData() == "everywhere"
        assert widget._driver_user_edited
        assert widget._recovery_issue is None

        widget._show_recovery("missing")
        widget.driver_recommendation = DriverRecommendation(
            None, None, (InstalledDriver("ml1660.ppd", "Samsung ML-1660"),),
            "", "", True,
        )
        widget._update_recovery()
        assert widget.recovery_cups_button.isEnabled()
        widget.recovery_cups_button.click()
        assert widget.driver.currentData() == "model"
        assert widget._recovery_issue == "missing"
        widget.model_choice.addItem("Samsung ML-1660", "ml1660.ppd")
        widget.model_choice.setCurrentIndex(widget.model_choice.findData("ml1660.ppd"))
        widget.model_choice.activated.emit(widget.model_choice.currentIndex())
        assert widget._recovery_issue is None
        assert widget.model_choice.currentData() == "ml1660.ppd"

        widget._show_recovery("missing")
        ppd = Path("REPLACE_PPD")
        ppd.write_text('*PPD-Adobe: "4.3"\\n')
        QFileDialog.getOpenFileName = lambda *a, **kw: (str(ppd), "CUPS PPD")
        widget.recovery_ppd_button.click()
        assert widget.driver.currentData() == "ppd"
        assert widget.ppd_path.text() == str(ppd)
        assert widget._recovery_issue is None
        assert all(kind in {"warn", "refresh"} for kind, *_ in actions)

        # 프린터 등록에 실패한 경우에도 임의로 드라이버를 바꾸지 않습니다.
        widget._registration_failed("CUPS: unable to copy PPD file")
        assert widget._recovery_issue == "registration-failed"
        assert not widget.recovery_panel.isHidden()
        assert widget.driver.currentData() == "ppd"
        widget.driver_recommendation = DriverRecommendation(
            "everywhere", None, (), "", "", True,
        )
        widget._refresh_driver_resolution()
        # 등록 실패는 자동 추천 재조회만으로 해결됐다고 취급하지 않습니다.
        assert widget._recovery_issue == "registration-failed"
        widget.close()
    """).replace("REPLACE_PPD", str(tmp_path / "sample.ppd"))
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_socket_or_unverified_ipp_never_auto_selects_ipp_fallback():
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.discovery import DiscoveredPrinter
        from printer_supporter.identification import PrinterIdentity
        from printer_supporter.setup_ui import PrinterSetupWidget

        app = QApplication([])
        widget = PrinterSetupWidget()
        widget.current_device = DiscoveredPrinter(
            "Unknown Printer", "socket://192.168.1.15:9100", "socket",
        )
        widget.identity_result = PrinterIdentity(
            "Unknown Printer", None, None, "SOCKET",
            "검색된 이름(미검증)", "unknown", "조회 불가",
        )
        widget._show_recovery("missing")
        assert not widget.recovery_ipp_button.isEnabled()
        original = widget.driver.currentData()
        widget.try_recovery_ipp()
        assert widget.driver.currentData() == original
        assert widget._recovery_issue == "missing"
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
