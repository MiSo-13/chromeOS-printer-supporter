"""필수 의존성 설치도 복사 가능한 승인창을 거치는지 확인."""
import os
import subprocess
import sys
import textwrap


def test_dependency_installation_only_after_copyable_confirmation():
    script = textwrap.dedent("""
        from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
        import printer_supporter.main as main_module
        from printer_supporter.dependencies import LIBREOFFICE

        app = QApplication([])
        main = main_module.MainWindow.__new__(main_module.MainWindow)
        QMainWindow.__init__(main)
        main.status = QLabel(main)
        main._dependency_install_busy = False
        calls = []

        class FakeDeps:
            def installation_command(self, items):
                assert items == [LIBREOFFICE]
                return ["sudo", "-n", "apt-get", "install", "-y", "libreoffice"]
            def install(self, items, *, approved=False):
                calls.append(("install", approved))
                return "설치 완료"

        main.dependency_manager = FakeDeps()
        main._background = lambda operation, done, failed=None: calls.append(
            ("pending", operation, done, failed)
        )
        main.show_error = lambda message: calls.append(("error", message))

        details = []
        main_module.confirm_action = lambda *args, **kwargs: details.append(kwargs) or False
        main._offer_install([LIBREOFFICE])
        assert not calls
        assert not main._dependency_install_busy
        assert "sudo -n apt-get install -y libreoffice" in details[0]["details"]
        assert "Crostini" in details[0]["details"]

        main_module.confirm_action = lambda *args, **kwargs: details.append(kwargs) or True
        main._offer_install([LIBREOFFICE])
        assert main._dependency_install_busy
        assert len(calls) == 1 and calls[0][0] == "pending"
        main._offer_install([LIBREOFFICE])
        assert len(calls) == 1  # 승인 중이어도 중복 시작 없음
        operation = calls[0][1]
        assert operation() == "설치 완료"
        assert calls[-1] == ("install", True)

        main._installation_failed("sudo 권한 없음")
        assert not main._dependency_install_busy
        assert calls[-1] == ("error", "패키지 설치 실패: sudo 권한 없음")
        main.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
