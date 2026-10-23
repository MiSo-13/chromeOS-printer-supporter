"""복사 가능한 승인 모달의 실제 Qt 클립보드·거절·동의 동작 테스트."""
import os
import subprocess
import sys
import textwrap


def test_copyable_consent_and_guide_dialog():
    script = textwrap.dedent("""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QDialog, QPlainTextEdit
        from printer_supporter.dialogs import CopyableDetailsDialog, confirm_action, show_guide

        app = QApplication([])
        details = "작업: 드라이버 설치\\n명령: sudo -n apt-get install -y printer-driver-brlaser"
        dialog = CopyableDetailsDialog(
            None, title="테스트 확인", summary="실행 예정 작업",
            details=details, confirm_label="설치",
        )
        assert dialog.cancel_button.isDefault()
        assert isinstance(dialog.details, QPlainTextEdit)
        assert dialog.details.isReadOnly()
        assert dialog.approve_button.text() == "설치"
        dialog.copy_button.click()
        assert QApplication.clipboard().text() == details
        dialog.reject()

        actions = []
        def reject():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, CopyableDetailsDialog)
            assert modal.details.toPlainText() == details
            actions.append("cancel")
            modal.cancel_button.click()
        QTimer.singleShot(0, reject)
        assert not confirm_action(
            None, title="사용자 확인", summary="설치할까요?",
            details=details, confirm_label="설치",
        )
        def accept():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, CopyableDetailsDialog)
            modal.copy_button.click()
            assert QApplication.clipboard().text() == details
            actions.append("accept")
            modal.approve_button.click()
        QTimer.singleShot(0, accept)
        assert confirm_action(
            None, title="사용자 확인", summary="설치할까요?",
            details=details, confirm_label="설치",
        )
        def close():
            modal = QApplication.activeModalWidget()
            assert isinstance(modal, CopyableDetailsDialog)
            assert modal.approve_button is None
            actions.append("guide")
            modal.cancel_button.click()
        QTimer.singleShot(0, close)
        show_guide(None, title="프린터 사용 방법", summary="안내", details="1. 검색")
        assert actions == ["cancel", "accept", "guide"]
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
