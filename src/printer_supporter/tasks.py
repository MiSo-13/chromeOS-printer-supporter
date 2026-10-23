"""메인 화면과 프린터 추가 화면에서 공유하는 Qt 백그라운드 작업."""
from __future__ import annotations

from collections.abc import Callable
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal


class TaskSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class BackgroundTask(QRunnable):
    """작업 완료/실패 신호를 UI 스레드로 전달합니다."""

    def __init__(self, operation: Callable[[], object]):
        super().__init__()
        self.operation = operation
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.operation()
        except Exception as exc:
            try:
                self.signals.failed.emit(str(exc))
            except RuntimeError:
                # UI가 종료된 뒤 신호 수신 객체가 삭제된 경우입니다.
                pass
        else:
            try:
                self.signals.finished.emit(result)
            except RuntimeError:
                pass
