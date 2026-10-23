"""실제 Qt 메뉴바 구성 및 테마 설정 유지 검사."""
import os
import subprocess
import sys
import textwrap


def test_native_window_file_settings_menu_and_theme_persistence(tmp_path):
    script = textwrap.dedent("""
        from pathlib import Path
        from unittest.mock import patch

        from PyQt6.QtWidgets import QApplication, QGroupBox

        from printer_supporter.main import MainWindow
        from printer_supporter.theme import stylesheet_for
        from printer_supporter.settings import SettingsStore

        app = QApplication([])

        # UI를 실제 생성하되 CUPS 요청이나 시스템 패키지 점검은 호출하지 않습니다.
        with patch.object(MainWindow, "refresh_all", lambda self: None), \\
             patch.object(MainWindow, "check_dependencies", lambda self, **kw: None):
            window = MainWindow()
            window.timer.stop()
            window.show()
            app.processEvents()

            bar = window.menuBar()
            assert not bar.isNativeMenuBar()
            assert [a.text() for a in bar.actions()] == ["파일", "설정"]
            files = bar.actions()[0].menu()
            settings = bar.actions()[1].menu()
            assert [a.text() for a in files.actions() if not a.isSeparator()] == [
                "문서 열기…", "새로고침", "종료",
            ]
            assert [a.shortcut().toString() for a in files.actions() if not a.isSeparator()] == [
                "Ctrl+O", "Ctrl+R", "Ctrl+Q",
            ]

            theme_menu = settings.actions()[0].menu()
            assert theme_menu.title() == "화면 테마"
            assert [a.text() for a in theme_menu.actions()] == ["라이트", "다크"]
            assert window._theme_actions["light"].isChecked()
            assert not window._theme_actions["dark"].isChecked()
            assert not any(
                group.title() == "설정" for group in window.findChildren(QGroupBox)
            )

            # 설정 메뉴를 클릭하는 실제 Qt 액션과 영속 저장을 검사합니다.
            window._theme_actions["dark"].trigger()
            assert window._theme_actions["dark"].isChecked()
            assert window.settings.data["theme"] == "dark"
            assert window.styleSheet() == stylesheet_for("dark")
            assert SettingsStore().data["theme"] == "dark"

            # 다시 시작해도 저장된 테마가 적용됩니다.
            window.close()
            second = MainWindow()
            second.timer.stop()
            second.show()
            app.processEvents()
            assert second._theme_actions["dark"].isChecked()
            assert second.styleSheet() == stylesheet_for("dark")
            second._theme_actions["light"].trigger()
            assert SettingsStore().data["theme"] == "light"
            second.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "PRINTHUB_CONFIG_DIR": str(tmp_path / "config"),
        },
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_theme_write_error_restores_selected_menu_item(tmp_path):
    script = textwrap.dedent("""
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.main import MainWindow

        app = QApplication([])
        with patch.object(MainWindow, "refresh_all", lambda self: None), \\
             patch.object(MainWindow, "check_dependencies", lambda self, **kw: None):
            window = MainWindow()
            window.timer.stop()
            window.show()
            app.processEvents()
            errors = []
            window.show_error = lambda error: errors.append(error)
            def fail(_theme):
                raise OSError("읽기 전용 경로")
            window.settings.set_theme = fail
            window._theme_actions["dark"].trigger()
            assert errors and "저장 실패" in errors[0]
            assert window._theme_actions["light"].isChecked()
            assert not window._theme_actions["dark"].isChecked()
            assert window.settings.data["theme"] == "light"
            window.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "PRINTHUB_CONFIG_DIR": str(tmp_path / "config"),
        },
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
