"""앱 최초 포커스가 프린터 선택창에 있어도 파일 Ctrl+V가 동작하는지 검증합니다."""

import os
import subprocess
import sys
import textwrap


def test_document_paste_with_printer_selector_focused(tmp_path):
    document = tmp_path / "문서.pdf"
    document.write_bytes(b"sample")

    # CI에 화면 서버가 없어도 Qt 이벤트 전달과 포커스 동작을 검사합니다.
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    script = textwrap.dedent("""
        import sys
        from pathlib import Path
        from PyQt6.QtCore import QMimeData, Qt, QUrl
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit, QMainWindow, QVBoxLayout, QWidget
        from printer_supporter.main import MainWindow

        app = QApplication([])
        window = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(window)
        container = QWidget()
        layout = QVBoxLayout(container)
        printer_box = QComboBox()
        printer_box.addItem("테스트 프린터")
        layout.addWidget(printer_box)
        editor = QLineEdit()
        layout.addWidget(editor)
        window.setCentralWidget(container)
        selected = []
        window._set_document = lambda path: selected.append(path)
        app.installEventFilter(window)

        window.show()
        window.activateWindow()
        printer_box.setFocus()
        app.processEvents()
        assert printer_box.hasFocus(), "프린터 선택창에 포커스가 있어야 합니다."
        assert window.isActiveWindow(), "테스트 창이 활성 상태여야 합니다."

        path = Path(sys.argv[1])
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        app.clipboard().setMimeData(mime)
        QTest.keyClick(printer_box, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        assert selected == [path], f"프린터 포커스 상태에서 붙여넣기 실패: {selected}"

        # 편집 가능한 입력창의 텍스트 Ctrl+V는 기존처럼 동작해야 합니다.
        editor.setFocus()
        app.processEvents()
        app.clipboard().setText("일반 텍스트")
        QTest.keyClick(editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        assert editor.text() == "일반 텍스트"
        assert selected == [path]

        window.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(document)],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
