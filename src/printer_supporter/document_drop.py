"""문서 드롭 이벤트를 미리보기/인쇄 화면으로 전달합니다."""
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame

from .document_input import local_document_from_mime


class DocumentDropArea(QFrame):
    fileDropped = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("documentDropArea")

    def dragEnterEvent(self, event):
        if local_document_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if local_document_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = local_document_from_mime(event.mimeData())
        if path:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda selected=path: self.fileDropped.emit(selected))
        else:
            event.ignore()
