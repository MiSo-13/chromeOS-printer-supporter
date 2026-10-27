"""인쇄 방향 선택을 CUPS 표준 작업 옵션으로 전달하는 UI 테스트."""
import os
import subprocess
import sys
import textwrap


def test_orientation_selector_is_available_without_driver_options():
    script = textwrap.dedent("""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.main import MainWindow

        app = QApplication([])
        original_refresh = MainWindow.refresh_all
        original_check = MainWindow.check_dependencies
        try:
            # 실제 프린터나 CUPS 서비스 없이 UI 설정만 검증합니다.
            MainWindow.refresh_all = lambda self: None
            MainWindow.check_dependencies = lambda self, **kwargs: None
            window = MainWindow()
            window.timer.stop()

            assert window.orientation.isEnabled()
            assert window.orientation.currentText() == "자동 (문서 방향)"
            assert window._selected_print_options() == {}
            assert "실제 출력" in window.preview_note.text()

            # 인쇄 방향을 바꾸면 기존 이미지가 즉시 회전합니다.
            source = QPixmap(100, 140)
            source.fill(Qt.GlobalColor.white)
            window.preview_view.show_image(source)
            assert window.preview_view.image_label.pixmap().height() > 100
            window.orientation.setCurrentIndex(1)
            assert window._selected_print_options() == {
                "orientation-requested": "3",
            }
            window.orientation.setCurrentIndex(2)
            assert window._selected_print_options() == {
                "orientation-requested": "4",
            }
            rotated = window.preview_view.image_label.pixmap()
            assert rotated.width() > rotated.height()
            assert (window.preview_view._original.width(),
                    window.preview_view._original.height()) == (100, 140)

            # 프린터 옵션을 조회할 수 없어도 방향 선택은 유지합니다.
            window.refresh_options("")
            assert window.orientation.isEnabled()
            assert window._selected_print_options() == {
                "orientation-requested": "4",
            }
            window.orientation.setCurrentIndex(0)
            assert window.preview_view.image_label.pixmap().height() > (
                window.preview_view.image_label.pixmap().width()
            )
            window.close()
            app.processEvents()
        finally:
            MainWindow.refresh_all = original_refresh
            MainWindow.check_dependencies = original_check
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
