"""Office 미리보기의 Qt 비동기 표시·페이지 이동·리소스 정리를 검증합니다."""
import os
import subprocess
import sys
import textwrap


def test_office_preview_window_async_retry_and_cleanup(tmp_path):
    script = textwrap.dedent("""
        import sys
        import time
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import fitz
        from PyQt6.QtWidgets import QApplication

        import printer_supporter.main as main_module
        from printer_supporter.office_preview import ConvertedOfficePreview

        class FakeService:
            def printers(self):
                return []

        class FakeDependencies:
            installed_lo = False
            def installed(self, dependency):
                return self.installed_lo
            def missing(self, *, required_only=False):
                return []

        temp_root = Path(sys.argv[1])
        office = temp_root / "보고서.docx"
        office.write_bytes(b"original office")
        another = temp_root / "다른 문서.pdf"
        with fitz.open() as pdf:
            pdf.new_page()
            pdf.save(another)

        converted_paths = []
        def fake_convert(source):
            holder = TemporaryDirectory(prefix="test-office-preview-")
            pdf_file = Path(holder.name) / (source.stem + ".pdf")
            with fitz.open() as pdf:
                pdf.new_page()
                pdf.new_page()
                pdf.save(pdf_file)
            converted_paths.append(pdf_file)
            return ConvertedOfficePreview(pdf_file, 2, holder)

        main_module.convert_office_preview = fake_convert
        app = QApplication([])
        dependencies = FakeDependencies()
        window = main_module.MainWindow(
            service=FakeService(), dependency_manager=dependencies
        )
        window.timer.stop()
        window.show()
        app.processEvents()

        # LibreOffice가 없는 경우 사용자에게 설치 안내를 제공하며 인쇄하지 않습니다.
        window._set_document(office)
        assert "LibreOffice" in window.preview_view.placeholder.text()
        assert window.preview_retry_button.isVisible()
        assert window._office_preview is None

        dependencies.installed_lo = True
        window.preview_retry_button.click()
        deadline = time.monotonic() + 8
        while window._office_preview is None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert window._office_preview is not None, window.preview_view.placeholder.text()
        assert window.preview_count == 2
        assert window.page_indicator.text() == "1 / 2"
        assert window.preview_view.stack.currentWidget() is window.preview_view.scroll
        assert window.next_page.isEnabled()
        window.next_page.click()
        assert window.page_indicator.text() == "2 / 2"
        assert window.prev_page.isEnabled()
        assert not window.next_page.isEnabled()
        first_preview_pdf = converted_paths[0]
        assert first_preview_pdf.exists()

        # 파일이 바뀌면 임시 PDF를 지우고 새 파일을 표시합니다.
        old_generation = window._preview_generation
        window._set_document(another)
        assert not first_preview_pdf.exists()
        assert window._office_preview is None
        assert window._preview_pdf_path == another
        assert window.page_indicator.text() == "1 / 1"

        # 늦게 끝난 이전 변환 결과는 표시하지 않고 즉시 정리합니다.
        stale = fake_convert(office)
        stale_path = stale.pdf_path
        window._office_preview_ready((old_generation, office, stale))
        assert not stale_path.exists()
        assert window._preview_pdf_path == another

        window._set_document(office)
        deadline = time.monotonic() + 8
        while window._office_preview is None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert window._office_preview is not None
        current_path = window._office_preview.pdf_path
        assert current_path.exists()
        window.close()
        assert not current_path.exists()
        assert office.read_bytes() == b"original office"
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen",
             "PRINTHUB_CONFIG_DIR": str(tmp_path / "settings")},
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
