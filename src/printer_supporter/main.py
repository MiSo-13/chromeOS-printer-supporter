"""프린터·대기열·오류를 한눈에 볼 수 있는 PyQt6 앱."""

from __future__ import annotations

from pathlib import Path
import getpass
import sys

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .backend import CupsService, PrintError, PrintJob, SUPPORTED_EXTENSIONS


class Signals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class Task(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = Signals()

    def run(self):
        try:
            self.signals.finished.emit(self.operation())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, service: CupsService | None = None):
        super().__init__()
        self.service = service or CupsService()
        self.pool = QThreadPool.globalInstance()
        self.selected_file: Path | None = None
        self.current_jobs: list[PrintJob] = []
        self.setWindowTitle("PrintHub · ChromeOS 프린터 관리자")
        self.resize(820, 680)

        root = QWidget()
        layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        heading = QLabel("PrintHub")
        heading.setStyleSheet("font-size: 26px; font-weight: 700")
        layout.addWidget(heading)
        self.status = QLabel("CUPS 연결 확인 중…")
        layout.addWidget(self.status)

        selection = QHBoxLayout()
        selection.addWidget(QLabel("프린터"))
        self.printer_box = QComboBox()
        self.printer_box.currentTextChanged.connect(self.refresh_jobs)
        selection.addWidget(self.printer_box, 1)
        refresh = QPushButton("새로고침")
        refresh.clicked.connect(self.refresh_all)
        selection.addWidget(refresh)
        layout.addLayout(selection)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        print_page = QWidget()
        print_layout = QVBoxLayout(print_page)
        file_row = QHBoxLayout()
        self.file_label = QLabel("선택한 문서 없음")
        file_row.addWidget(self.file_label, 1)
        choose = QPushButton("문서 선택")
        choose.clicked.connect(self.choose_file)
        file_row.addWidget(choose)
        print_layout.addLayout(file_row)
        print_layout.addWidget(QLabel("PDF, Word, Excel, PowerPoint, 텍스트 및 이미지 지원"))
        options = QHBoxLayout()
        options.addWidget(QLabel("인쇄 매수"))
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        options.addWidget(self.copies)
        options.addWidget(QLabel("용지"))
        self.paper = QComboBox()
        self.paper.addItems(["A4", "Letter"])
        options.addWidget(self.paper)
        options.addStretch()
        print_layout.addLayout(options)
        self.print_button = QPushButton("인쇄하기")
        self.print_button.clicked.connect(self.print_selected)
        print_layout.addWidget(self.print_button)
        print_layout.addStretch()
        tabs.addTab(print_page, "문서 인쇄")

        queue_page = QWidget()
        queue_layout = QVBoxLayout(queue_page)
        self.job_list = QListWidget()
        queue_layout.addWidget(self.job_list)
        self.cancel_button = QPushButton("선택한 내 작업 취소")
        self.cancel_button.clicked.connect(self.cancel_selected)
        queue_layout.addWidget(self.cancel_button)
        queue_layout.addWidget(QLabel("이 앱이 연결한 CUPS의 작업만 표시합니다. 다른 PC의 작업은 보이지 않을 수 있습니다."))
        tabs.addTab(queue_page, "인쇄 대기열")

        state_page = QWidget()
        state_layout = QVBoxLayout(state_page)
        self.state_text = QTextEdit()
        self.state_text.setReadOnly(True)
        state_layout.addWidget(self.state_text)
        state_layout.addWidget(QLabel("장치 오류는 연결 방식에 따라 일부만 보고될 수 있습니다."))
        tabs.addTab(state_page, "상태 및 오류")

        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start()
        self.refresh_all()

    def _background(self, operation, completed):
        task = Task(operation)
        task.signals.finished.connect(completed)
        task.signals.failed.connect(self.show_error)
        self.pool.start(task)

    def show_error(self, message: str):
        self.status.setText(f"오류: {message}")
        self.state_text.setPlainText(message)

    def refresh_all(self):
        self._background(self.service.printers, self._populate_printers)

    def _populate_printers(self, printers):
        previous = self.printer_box.currentText()
        self.printer_box.blockSignals(True)
        self.printer_box.clear()
        self.printer_box.addItems([p.name for p in printers])
        if previous in [p.name for p in printers]:
            self.printer_box.setCurrentText(previous)
        elif "Samsung_SL_M2030W" in [p.name for p in printers]:
            self.printer_box.setCurrentText("Samsung_SL_M2030W")
        self.printer_box.blockSignals(False)
        selected = next((p for p in printers if p.name == self.printer_box.currentText()), None)
        self.status.setText(f"{selected.name}: {selected.state}" if selected else "등록된 CUPS 프린터 없음")
        self.refresh_jobs()

    def refresh_jobs(self, *_):
        printer = self.printer_box.currentText()
        if printer:
            self._background(lambda: self.service.jobs(printer), self._populate_jobs)
            self._background(lambda: self.service.printer_reasons(printer), self.state_text.setPlainText)
        else:
            self.job_list.clear()

    def _populate_jobs(self, jobs: list[PrintJob]):
        self.current_jobs = jobs
        self.job_list.clear()
        for job in jobs:
            item = QListWidgetItem(f"{job.job_id}  |  {job.owner}  |  {job.size} bytes  |  {job.submitted}")
            item.setData(Qt.ItemDataRole.UserRole, job.job_id)
            self.job_list.addItem(item)

    def choose_file(self):
        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        name, _ = QFileDialog.getOpenFileName(self, "인쇄할 문서 선택", str(Path.home()), f"지원 문서 ({extensions})")
        if name:
            self.selected_file = Path(name)
            self.file_label.setText(self.selected_file.name)

    def print_selected(self):
        if not self.selected_file or not self.printer_box.currentText():
            self.show_error("프린터와 파일을 선택해 주세요.")
            return
        self.print_button.setEnabled(False)
        source, printer = self.selected_file, self.printer_box.currentText()
        copies, paper = self.copies.value(), self.paper.currentText()
        def print_operation():
            try:
                return (True, self.service.print_file(source, printer, copies=copies, media=paper))
            except Exception as exc:
                return (False, str(exc))

        self._background(print_operation, self._printed)

    def _printed(self, result):
        self.print_button.setEnabled(True)
        success, message = result
        if success:
            self.status.setText(f"작업 접수: {message}")
            self.refresh_jobs()
        else:
            self.show_error(message)

    def cancel_selected(self):
        item = self.job_list.currentItem()
        if not item:
            return
        job = next((j for j in self.current_jobs if j.job_id == item.data(Qt.ItemDataRole.UserRole)), None)
        if not job:
            return
        if job.owner != getpass.getuser():
            self.show_error("다른 사용자의 작업은 취소할 수 없습니다.")
            return
        answer = QMessageBox.question(self, "인쇄 작업 취소", f"{job.job_id} 작업을 취소할까요?")
        if answer == QMessageBox.StandardButton.Yes:
            self._background(lambda: self.service.cancel(job, getpass.getuser()), lambda _: self.refresh_jobs())


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
