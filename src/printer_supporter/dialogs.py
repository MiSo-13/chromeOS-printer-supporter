"""명령과 영향 범위를 선택/복사할 수 있는 작업 안내·승인 창."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)


class CopyableDetailsDialog(QDialog):
    """읽기 전용 텍스트로 명령을 보여주고, 복사한 뒤 승인할 수 있습니다."""

    def __init__(
        self, parent, *, title: str, summary: str, details: str,
        confirm_label: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("copyableDetailsDialog")
        self.setMinimumWidth(520)
        self.resize(600, 390)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        heading = QLabel(summary)
        heading.setObjectName("dialogSummary")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.details = QPlainTextEdit()
        self.details.setObjectName("copyableDetails")
        self.details.setReadOnly(True)
        self.details.setPlainText(details)
        self.details.setMinimumHeight(170)
        layout.addWidget(self.details, 1)

        controls = QHBoxLayout()
        self.copy_button = QPushButton("내용 복사")
        self.copy_button.setObjectName("copyDetailsButton")
        self.copy_button.clicked.connect(self.copy_details)
        controls.addWidget(self.copy_button)
        controls.addStretch()

        self.cancel_button = QPushButton("닫기" if confirm_label is None else "취소")
        self.cancel_button.setObjectName("cancelActionButton")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setDefault(True)
        controls.addWidget(self.cancel_button)

        self.approve_button = None
        if confirm_label:
            self.approve_button = QPushButton(confirm_label)
            self.approve_button.setObjectName("approveActionButton")
            self.approve_button.clicked.connect(self.accept)
            controls.addWidget(self.approve_button)
        layout.addLayout(controls)

    def copy_details(self):
        QApplication.clipboard().setText(self.details.toPlainText())


def confirm_action(
    parent, *, title: str, summary: str, details: str, confirm_label: str = "계속",
) -> bool:
    """창을 명시적으로 승인한 경우에만 True. 닫기/취소/Esc는 False."""
    dialog = CopyableDetailsDialog(
        parent, title=title, summary=summary, details=details,
        confirm_label=confirm_label,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_guide(parent, *, title: str, summary: str, details: str) -> None:
    dialog = CopyableDetailsDialog(
        parent, title=title, summary=summary, details=details,
    )
    dialog.exec()
