"""실제 인쇄 없이 오프스크린 Qt에서 미리보기 표시·크기 조정을 검증합니다."""
import os
import subprocess
import sys
import textwrap


def test_preview_viewer_fit_zoom_image_and_text(tmp_path):
    image_path = tmp_path / "example.png"
    script = textwrap.dedent("""
        import sys
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QImage, QPixmap
        from PyQt6.QtWidgets import QApplication
        from printer_supporter.preview_widget import DocumentPreview, read_image

        app = QApplication([])
        view = DocumentPreview()
        view.resize(640, 480)
        view.show()
        app.processEvents()

        pdf_page = QPixmap(1000, 1400)
        pdf_page.fill(Qt.GlobalColor.white)
        view.show_image(pdf_page)
        app.processEvents()
        app.processEvents()
        assert view.stack.currentWidget() is view.scroll
        fitted = view.image_label.pixmap()
        assert not fitted.isNull()
        assert fitted.width() <= view.scroll.viewport().width()
        assert fitted.height() <= view.scroll.viewport().height()

        view.set_zoom(1.5)
        assert view.image_label.pixmap().width() == 1500
        assert view.image_label.pixmap().height() == 2100

        view.set_zoom("fit")
        view.resize(360, 300)
        app.processEvents()
        app.processEvents()
        smaller = view.image_label.pixmap()
        assert smaller.width() < fitted.width()
        assert smaller.width() <= view.scroll.viewport().width()
        assert smaller.height() <= view.scroll.viewport().height()

        image = QImage(120, 80, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.blue)
        assert image.save(sys.argv[1])
        loaded = read_image(sys.argv[1])
        assert loaded.width() == 120
        assert loaded.height() == 80
        view.show_image(loaded)
        assert view.stack.currentWidget() is view.scroll

        view.show_text("텍스트 미리보기")
        assert view.stack.currentWidget() is view.text_view
        assert view.text_view.toPlainText() == "텍스트 미리보기"
        view.clear("선택 없음")
        assert view.stack.currentWidget() is view.placeholder
        assert view.image_label.pixmap() is None or view.image_label.pixmap().isNull()
        assert view.placeholder.text() == "선택 없음"
        view.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(image_path)],
        text=True,
        capture_output=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\\n" + result.stderr
