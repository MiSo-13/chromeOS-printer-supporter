"""인쇄 요청 중복 방지·진행 표시와 테마 설정 위치 검증."""
import os
import subprocess
import sys
import textwrap

from printer_supporter.theme import stylesheet_for


def test_print_buttons_busy_state_and_retry(tmp_path):
    pdf = tmp_path / "example.pdf"
    pdf.write_bytes(b"PDF for mocked CUPS only")
    script = textwrap.dedent("""
        from pathlib import Path
        import sys
        from PyQt6.QtWidgets import (
            QApplication, QComboBox, QLabel, QLineEdit, QMainWindow,
            QMessageBox, QProgressBar, QPushButton, QSpinBox,
        )
        from printer_supporter.main import MainWindow

        app = QApplication([])
        window = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(window)
        window._print_busy = False
        window.selected_file = Path(sys.argv[1])
        window.preview_count = 1
        window.status = QLabel(window)
        window.print_feedback = QLabel(window)
        window.print_button = QPushButton("인쇄", window)
        window.test_page_button = QPushButton("테스트 페이지 인쇄", window)
        window.print_progress = QProgressBar(window)
        window.print_progress.setVisible(False)
        window.printer_box = QComboBox(window)
        window.printer_box.addItem("Test_Queue")
        window.paper = QComboBox(window)
        window.paper.addItem("A4", "A4")
        window.copies = QSpinBox(window)
        window.copies.setValue(2)
        window.page_range = QLineEdit(window)
        window.dependency_manager = type(
            "Deps", (), {"installed": lambda self, *_args: True},
        )()
        calls = []
        class Service:
            def print_file(self, *args, **kwargs):
                calls.append(("document", args, kwargs))
                return "job 123"
            def print_test_page(self, *args, **kwargs):
                calls.append(("test", args, kwargs))
                return "job 124"
        window.service = Service()
        window._selected_print_options = lambda: {}
        pending = []
        window._background = lambda operation, callback: pending.append(
            (operation, callback)
        )
        updates = []
        window.refresh_jobs = lambda: updates.append("refreshed")
        window.show_error = lambda message: updates.append("error: " + message)
        window.print_selected()
        assert window._print_busy
        assert not window.print_button.isEnabled()
        assert not window.test_page_button.isEnabled()
        assert not window.print_progress.isHidden()
        assert "요청 중" in window.print_button.text()
        assert "CUPS" in window.print_feedback.text()
        window.print_selected()
        window.print_test_page()
        assert len(pending) == 1 and not calls
        operation, completed = pending.pop()
        completed(operation())
        assert calls[0][0] == "document"
        assert not window._print_busy
        assert window.print_button.isEnabled()
        assert window.test_page_button.isEnabled()
        assert window.print_button.text() == "인쇄"
        assert "접수 완료" in window.print_feedback.text()
        assert updates == ["refreshed"]

        QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes
        window.print_test_page()
        assert len(pending) == 1
        assert window._print_busy
        window.print_selected()
        window.print_test_page()
        assert len(pending) == 1
        operation, completed = pending.pop()
        completed(operation())
        assert len(calls) == 2 and calls[1][0] == "test"
        assert not window._print_busy
        assert window.test_page_button.isEnabled()
        assert "테스트 페이지 접수 완료" in window.print_feedback.text()

        window._print_busy = True
        window._set_print_busy(False)
        assert not window._print_busy
        window.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(pdf)],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_menu_styles_and_no_sidebar_settings():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main = (root / "src" / "printer_supporter" / "main.py").read_text()
    menus = (root / "src" / "printer_supporter" / "app_menu.py").read_text()
    assert "build_menus(" in main
    assert 'settings_group = QGroupBox("설정")' not in main
    assert 'self.theme_box = QComboBox()' not in main
    assert 'bar.addMenu("파일")' in menus
    assert 'bar.addMenu("설정")' in menus
    for theme in ("light", "dark"):
        styles = stylesheet_for(theme)
        assert "QMenuBar::item:selected" in styles
        assert "QMenu::item:selected" in styles
        assert "QProgressBar#printProgress" in styles
        assert "QLabel#printFeedback" in styles
