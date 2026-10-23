"""프린터 추가 단계 표시·첫 검색 안내·등록 승인 프로세스 테스트."""
import os
import subprocess
import sys
import textwrap


def test_setup_steps_search_notice_and_registration_consent():
    script = textwrap.dedent("""
        from subprocess import CompletedProcess
        from PyQt6.QtWidgets import QApplication, QGroupBox, QScrollArea, QMessageBox
        import printer_supporter.setup_ui as sm
        from printer_supporter.discovery import DiscoveredPrinter

        app = QApplication([])
        calls = []
        class FakeService:
            def discover(self):
                calls.append("scan")
                return []
            def register(self, registration, *, approved=False):
                calls.append(("register", registration.name, approved))
                assert approved
                return "프린터 등록 완료"

        widget = sm.PrinterSetupWidget(service=FakeService())
        widget.show()
        app.processEvents()

        titles = [g.title() for g in widget.findChildren(QGroupBox)]
        assert "1. 프린터 찾기" in titles
        assert "2. 모델 확인" in titles
        assert "3. 드라이버 선택" in titles
        assert "4. 프린터 등록" in titles
        assert widget.findChild(QScrollArea) is not None
        assert widget.details_toggle.text() == "상세 정보 보기"
        assert widget.identity_advice.isHidden()
        widget.details_toggle.click()
        assert widget.details_toggle.text() == "상세 정보 접기"
        assert not widget.identity_advice.isHidden()
        widget.details_toggle.click()
        assert widget.identity_advice.isHidden()

        guidance = []
        sm.show_guide = lambda *args, **kwargs: guidance.append(kwargs)
        widget.help_button.click()
        assert "4단계" in guidance[0]["summary"]
        assert "lpadmin" not in guidance[0]["details"] or "등록" in guidance[0]["details"]

        approvals = []
        sm.confirm_action = lambda *args, **kwargs: approvals.append(kwargs) or False
        widget.search()
        assert calls == [] and not widget._search_info_seen
        assert "lpinfo -v" in approvals[0]["details"]
        assert "다운로드" in approvals[0]["details"]
        sm.confirm_action = lambda *args, **kwargs: approvals.append(kwargs) or True
        widget.search()
        widget.pool.waitForDone(4000)
        app.processEvents()
        assert calls == ["scan"] and widget._search_info_seen
        assert widget.scan_button.isEnabled()

        widget.search()
        widget.pool.waitForDone(4000)
        app.processEvents()
        assert calls == ["scan", "scan"]
        assert len(approvals) == 2  # 첫 검색 안내는 한 번만

        # 새 CUPS 큐 등록은 별도로 명시적 동의가 필요합니다.
        widget.current_device = DiscoveredPrinter(
            "Test Printer", "ipp://192.168.1.10/ipp/print", "ipp"
        )
        widget.queue_name.setText("Test_Printer")
        widget.driver.setCurrentIndex(widget.driver.findData("everywhere"))
        widget._background = lambda op, done: calls.append(("pending", op, done))
        sm.confirm_action = lambda *args, **kwargs: approvals.append(kwargs) or False
        widget.register()
        assert not any(isinstance(c, tuple) for c in calls)
        assert "sudo -n lpadmin" in approvals[-1]["details"]
        assert "-p Test_Printer" in approvals[-1]["details"]
        sm.confirm_action = lambda *args, **kwargs: approvals.append(kwargs) or True
        widget.register()
        widget.register()
        pending = [c for c in calls if isinstance(c, tuple) and c[0] == "pending"]
        assert len(pending) == 1
        assert not widget.register_button.isEnabled()
        QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
        _, operation, done = pending[0]
        done(operation())
        assert ("register", "Test_Printer", True) in calls
        assert not widget._register_busy
        assert widget.register_button.isEnabled()
        widget.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=25, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
