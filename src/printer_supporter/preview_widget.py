"""창 크기에 맞는 문서 미리보기, 확대/축소 및 텍스트 표시 위젯."""
from __future__ import annotations

from PyQt6.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QImageReader, QTextCursor
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
        self._orientation: str | None = None
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

    def set_orientation(self, orientation: str | None):
        """선택한 용지 방향에 맞춰 화면만 회전하고 원본은 유지합니다."""
        if orientation not in (None, "3", "4"):
            raise ValueError("지원하지 않는 미리보기 방향입니다.")
        if self._orientation == orientation:
            return
        self._orientation = orientation
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
        source_width, source_height = self._original.width(), self._original.height()
        rotate = (
            (self._orientation == "3" and source_width > source_height)
            or (self._orientation == "4" and source_height > source_width)
        )
        display_width, display_height = (
            (source_height, source_width) if rotate
            else (source_width, source_height)
        )
        if self._zoom == "fit":
            viewport = self.scroll.viewport().size()
            factor = min(
                1.0,
                max(1, viewport.width() - 16) / display_width,
                max(1, viewport.height() - 16) / display_height,
            )
        else:
            factor = float(self._zoom)
        # 방향을 바꿀 때 PDF를 다시 렌더링하지 않고 표시 이미지만 생성합니다.
        # 화면 이미지의 최대 크기를 제한하여 메모리 사용량을 관리합니다.
        factor = min(factor, 4096 / display_width, 4096 / display_height)
        target_width = max(1, round(display_width * factor))
        target_height = max(1, round(display_height * factor))
        displayed = QPixmap(target_width, target_height)
        displayed.fill(Qt.GlobalColor.transparent)
        painter = QPainter(displayed)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if rotate:
            painter.translate(target_width, 0)
            painter.rotate(90)
        painter.drawPixmap(
            QRect(
                0, 0,
                target_height if rotate else target_width,
                target_width if rotate else target_height,
            ),
            self._original,
        )
        painter.end()
        self.image_label.setPixmap(displayed)
        self.image_label.resize(displayed.size())


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
