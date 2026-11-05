"""CUPS 자동 조회 중복 방지와 화면별 조회량을 Qt 오프스크린으로 검증합니다."""
import os
import subprocess
import sys
import textwrap


def test_refresh_coalescing_page_scope_and_unchanged_widgets(tmp_path):
    script = textwrap.dedent("""
        from unittest.mock import patch
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.main import MainWindow
        from printer_supporter.backend import Printer, PrintJob

        class Service:
            def __init__(self):
                self.calls = {"printers": 0, "jobs": 0, "history": 0, "reasons": 0}
                self.fail_jobs = False
            def printers(self):
                self.calls["printers"] += 1
                return [Printer("Demo", "대기", True, "printer idle")]
            def jobs(self, printer):
                self.calls["jobs"] += 1
                if self.fail_jobs:
                    raise RuntimeError("CUPS unavailable")
                return [PrintJob("Demo-7", "tester", "123", "date", printer)]
            def completed_jobs(self, printer):
                self.calls["history"] += 1
                return []
            def printer_reasons(self, printer):
                self.calls["reasons"] += 1
                return "printer idle"
            def printer_options(self, printer):
                return {}

        app = QApplication([])
        service = Service()
        pending = []
        def enqueue(self, operation, completed, failed=None):
            pending.append((operation, completed, failed))
        with patch.object(MainWindow, "_background", enqueue), \\
             patch.object(MainWindow, "check_dependencies", lambda self, **kw: None):
            window = MainWindow(service=service)
            window.timer.stop()
            window.show()
            app.processEvents()
            assert window.timer.interval() == 10000
            assert len(pending) == 1

            # 이전 프린터 조회가 진행 중이면 추가 요청은 하나만 예약합니다.
            window.refresh_all()
            window.refresh_all()
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["printers"] == 1
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["printers"] == 2
            assert not pending
            # 문서 인쇄 화면의 자동 갱신은 대기열을 조회하지 않습니다.
            assert service.calls["jobs"] == 0
            assert service.calls["history"] == 0
            assert service.calls["reasons"] == 0

            window._switch_page(1)
            assert len(pending) == 1
            window.refresh_jobs()
            window.refresh_jobs()
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["jobs"] == 1
            assert service.calls["history"] == 1
            assert service.calls["reasons"] == 0
            assert len(pending) == 1
            row = window.job_list.item(0)
            row.setData(Qt.ItemDataRole.UserRole.value + 1, "preserved")
            operation, done, _ = pending.pop(0)
            done(operation())
            assert window.job_list.item(0).data(
                Qt.ItemDataRole.UserRole.value + 1
            ) == "preserved"
            assert service.calls["jobs"] == 2
            assert service.calls["history"] == 2
            assert not window._queue_refreshing

            # 프린터 상태 화면에서는 상세 상태만 요청합니다.
            window._switch_page(2)
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["reasons"] == 1
            assert service.calls["jobs"] == 2
            assert service.calls["history"] == 2

            window.hide()
            window._auto_refresh()
            assert not pending
            window.show()
            window._auto_refresh()
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["printers"] == 3
            assert len(pending) == 1
            operation, done, _ = pending.pop(0)
            done(operation())
            assert service.calls["reasons"] == 2
            assert not pending

            # 일부 명령 실패 후에도 대기열 갱신 락이 해제됩니다.
            window._switch_page(1)
            service.fail_jobs = True
            operation, done, _ = pending.pop(0)
            done(operation())
            assert not window._queue_refreshing
            assert "CUPS 조회 오류" in window.status.text()
            service.fail_jobs = False
            window.refresh_jobs()
            operation, done, _ = pending.pop(0)
            done(operation())
            assert not window._queue_refreshing
            window.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
             "PRINTHUB_CONFIG_DIR": str(tmp_path / "config")},
        timeout=35, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
