"""창 크기에 맞는 문서 미리보기, 확대/축소 및 텍스트 표시 위젯."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImageReader, QTextCursor
from PyQt6.QtWidgets import (
    QFrame, QLabel, QPlainTextEdit, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)


class ResizableScrollArea(QScrollArea):
    resized = pyqtSignal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class DocumentPreview(QWidget):
    """원본 픽스맵을 보관하여 창 크기와 배율을 바꿔도 미리보기 유지."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("documentPreview")
        self._original = QPixmap()
        self._zoom = "fit"
        self._fit_update_pending = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.placeholder = QLabel("PDF, 이미지 또는 텍스트 문서를 선택해 주세요.")
        self.placeholder.setObjectName("previewPlaceholder")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.stack.addWidget(self.placeholder)

        self.scroll = ResizableScrollArea()
        self.scroll.setObjectName("previewScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label = QLabel()
        self.image_label.setObjectName("previewImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.image_label)
        self.scroll.resized.connect(self._schedule_fit_refresh)
        self.stack.addWidget(self.scroll)

        self.text_view = QPlainTextEdit()
        self.text_view.setObjectName("previewText")
        self.text_view.setReadOnly(True)
        self.stack.addWidget(self.text_view)

    def clear(self, message: str):
        self._original = QPixmap()
        self.image_label.clear()
        self.text_view.clear()
        self.placeholder.setText(message)
        self.stack.setCurrentWidget(self.placeholder)

    def show_image(self, pixmap: QPixmap):
        if pixmap.isNull():
            self.clear("이미지 미리보기를 만들지 못했습니다.")
            return
        self._original = pixmap
        self.stack.setCurrentWidget(self.scroll)
        self._refresh_image()

    def show_text(self, content: str):
        self._original = QPixmap()
        self.text_view.setPlainText(content)
        self.text_view.moveCursor(QTextCursor.MoveOperation.Start)
        self.stack.setCurrentWidget(self.text_view)

    def set_zoom(self, value: str | float):
        if value != "fit" and value not in (0.75, 1.0, 1.25, 1.5, 2.0):
            raise ValueError("지원하지 않는 미리보기 배율입니다.")
        self._zoom = value
        if not self._original.isNull():
            self._refresh_image()

    def _schedule_fit_refresh(self):
        if self._zoom != "fit" or self._original.isNull() or self._fit_update_pending:
            return
        self._fit_update_pending = True
        QTimer.singleShot(0, self._flush_fit_refresh)

    def _flush_fit_refresh(self):
        self._fit_update_pending = False
        if self._zoom == "fit" and not self._original.isNull():
            self._refresh_image()

    def _refresh_image(self):
        if self._original.isNull():
            return
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self._zoom == "fit"
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self._zoom == "fit"
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        if self._zoom == "fit":
            viewport = self.scroll.viewport().size()
            factor = min(
                1.0,
                max(1, viewport.width() - 16) / self._original.width(),
                max(1, viewport.height() - 16) / self._original.height(),
            )
        else:
            factor = float(self._zoom)
        # 고해상도 원본에 큰 배율을 적용하더라도 화면 이미지가 과도하게
        # 메모리를 사용하지 않도록 한 변의 최대 크기를 제한합니다.
        factor = min(
            factor,
            4096 / self._original.width(),
            4096 / self._original.height(),
        )
        target_width = max(1, round(self._original.width() * factor))
        target_height = max(1, round(self._original.height() * factor))
        scaled = self._original.scaled(
            target_width, target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())


def read_image(path) -> QPixmap:
    """EXIF 방향을 적용하고 과도하게 큰 이미지는 디코딩 전에 축소합니다."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > 2400:
        reader.setScaledSize(
            size.scaled(2400, 2400, Qt.AspectRatioMode.KeepAspectRatio)
        )
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString() or "지원하지 않는 이미지 형식입니다.")
    return QPixmap.fromImage(image)
