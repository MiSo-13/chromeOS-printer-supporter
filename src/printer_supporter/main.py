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
from .setup_ui import PrinterSetupWidget
from .dependencies import CUPS, LIBREOFFICE, DependencyManager


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
    def __init__(self, service: CupsService | None = None, dependency_manager: DependencyManager | None = None):
        super().__init__()
        self.service = service or CupsService()
        self.dependency_manager = dependency_manager or DependencyManager()
        self.pool = QThreadPool.globalInstance()
        self.selected_file: Path | None = None
        self.current_jobs: list[PrintJob] = []
        self.completed_jobs: list[PrintJob] = []
        self.queue_generation = 0
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
        check_packages = QPushButton("패키지 점검")
        check_packages.clicked.connect(lambda: self.check_dependencies(required_only=False))
        selection.addWidget(check_packages)
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
        queue_tabs = QTabWidget()
        queue_layout.addWidget(queue_tabs)
        active_page = QWidget()
        active_layout = QVBoxLayout(active_page)
        active_layout.addWidget(QLabel("대기 또는 처리 중인 CUPS 작업 (작업별 상세 진행률은 제공되지 않습니다)"))
        self.job_list = QListWidget()
        self.job_list.currentItemChanged.connect(self._update_queue_actions)
        active_layout.addWidget(self.job_list)
        actions = QHBoxLayout()
        self.hold_button = QPushButton("내 작업 보류")
        self.hold_button.clicked.connect(lambda: self.change_selected_job("hold"))
        actions.addWidget(self.hold_button)
        self.resume_button = QPushButton("내 작업 재개")
        self.resume_button.clicked.connect(lambda: self.change_selected_job("resume"))
        actions.addWidget(self.resume_button)
        self.cancel_button = QPushButton("내 작업 취소")
        self.cancel_button.clicked.connect(self.cancel_selected)
        actions.addWidget(self.cancel_button)
        active_layout.addLayout(actions)
        queue_tabs.addTab(active_page, "진행 중인 작업")
        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_layout.addWidget(QLabel("CUPS 처리 종료 이력 (종이 출력 성공을 의미하지 않음)"))
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        queue_tabs.addTab(history_page, "처리 종료 이력")
        self.queue_info = QLabel("목록 갱신 중…")
        queue_layout.addWidget(self.queue_info)
        queue_layout.addWidget(QLabel("이 Linux CUPS 큐의 작업만 표시하며, 다른 PC에서 직접 보낸 작업은 보이지 않을 수 있습니다."))
        tabs.addTab(queue_page, "인쇄 대기열")
        self._update_queue_actions()

        state_page = QWidget()
        state_layout = QVBoxLayout(state_page)
        self.state_text = QTextEdit()
        self.state_text.setReadOnly(True)
        state_layout.addWidget(self.state_text)
        state_layout.addWidget(QLabel("장치 오류는 연결 방식에 따라 일부만 보고될 수 있습니다."))
        tabs.addTab(state_page, "상태 및 오류")

        tabs.addTab(PrinterSetupWidget(on_registered=self.refresh_all), "프린터 추가")

        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start()
        self.refresh_all()
        QTimer.singleShot(100, lambda: self.check_dependencies(required_only=True))

    def _background(self, operation, completed):
        task = Task(operation)
        task.signals.finished.connect(completed)
        task.signals.failed.connect(self.show_error)
        self.pool.start(task)

    def check_dependencies(self, *, required_only: bool = False):
        missing = self.dependency_manager.missing(required_only=required_only)
        if not missing:
            if not required_only:
                QMessageBox.information(self, "의존성 점검", "필요한 패키지가 모두 설치되어 있습니다.")
            return
        self._offer_install(missing)

    def _offer_install(self, missing):
        names = ", ".join(dep.name for dep in missing)
        command = " ".join(self.dependency_manager.installation_command(missing))
        description = "\n".join(f"• {dep.name}: {dep.description}" for dep in missing)
        answer = QMessageBox.question(
            self,
            "필요한 패키지 설치",
            f"설치되지 않은 패키지:\n{description}\n\n"
            f"실행 명령:\n{command}\n\n"
            "Linux 컨테이너에만 설치됩니다. sudo 권한과 네트워크가 필요합니다.\n"
            "설치를 진행할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText(f"설치 보류: {names}")
            return
        self.status.setText(f"설치 중: {names} (잠시 기다려 주세요)")
        self._background(
            lambda: self.dependency_manager.install(missing, approved=True),
            self._installation_finished,
        )

    def _installation_finished(self, message: str):
        QMessageBox.information(self, "패키지 설치 완료", message)
        self.status.setText(message)
        self.refresh_all()

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
        self.queue_generation += 1
        generation = self.queue_generation
        if not printer:
            self.current_jobs = []
            self.completed_jobs = []
            self.job_list.clear()
            self.history_list.clear()
            self.queue_info.setText("선택한 프린터가 없습니다.")
            self._update_queue_actions()
            return
        self._background(
            lambda: (printer, generation, self.service.jobs(printer)),
            self._populate_jobs,
        )
        self._background(
            lambda: (printer, generation, self.service.completed_jobs(printer)),
            self._populate_history,
        )
        self._background(
            lambda: (printer, generation, self.service.printer_reasons(printer)),
            self._populate_reasons,
        )

    def _valid_queue_result(self, printer: str, generation: int) -> bool:
        return printer == self.printer_box.currentText() and generation == self.queue_generation

    def _populate_reasons(self, result):
        printer, generation, reason = result
        if self._valid_queue_result(printer, generation):
            self.state_text.setPlainText(reason)

    def _populate_jobs(self, result):
        printer, generation, jobs = result
        if not self._valid_queue_result(printer, generation):
            return
        self.current_jobs = jobs
        selected = self.job_list.currentItem()
        selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
        self.job_list.clear()
        for job in jobs:
            owned = "내 작업" if job.owner == getpass.getuser() else "다른 사용자"
            item = QListWidgetItem(
                f"대기/처리 중  |  {job.job_id}  |  {owned} ({job.owner})  |  "
                f"{job.size} bytes  |  {job.submitted}"
            )
            item.setData(Qt.ItemDataRole.UserRole, job.job_id)
            self.job_list.addItem(item)
            if job.job_id == selected_id:
                self.job_list.setCurrentItem(item)
        self._update_queue_actions()
        self.queue_info.setText(f"진행 중인 작업 {len(jobs)}건 · 5초마다 자동 갱신")

    def _populate_history(self, result):
        printer, generation, jobs = result
        if not self._valid_queue_result(printer, generation):
            return
        self.completed_jobs = jobs
        self.history_list.clear()
        for job in jobs[:100]:
            self.history_list.addItem(
                f"CUPS 처리 종료  |  {job.job_id}  |  {job.owner}  |  "
                f"{job.size} bytes  |  {job.submitted}"
            )

    def _selected_own_job(self) -> PrintJob | None:
        item = self.job_list.currentItem()
        if item is None:
            return None
        identifier = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (job for job in self.current_jobs
             if job.job_id == identifier and job.owner == getpass.getuser()),
            None,
        )

    def _update_queue_actions(self, *_):
        enabled = self._selected_own_job() is not None
        self.hold_button.setEnabled(enabled)
        self.resume_button.setEnabled(enabled)
        self.cancel_button.setEnabled(enabled)

    def change_selected_job(self, action: str):
        job = self._selected_own_job()
        if job is None:
            return
        if action not in {"hold", "resume"}:
            return
        verb = "보류" if action == "hold" else "재개"
        answer = QMessageBox.question(
            self, f"인쇄 작업 {verb}", f"{job.job_id} 작업을 {verb}할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        operation = self.service.hold if action == "hold" else self.service.resume
        self._background(
            lambda: operation(job, getpass.getuser()),
            lambda _: self.refresh_jobs(),
        )

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
        if self.selected_file.suffix.lower() in {
            ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods",
            ".ppt", ".pptx", ".odp",
        } and not self.dependency_manager.installed(LIBREOFFICE):
            self._offer_install([LIBREOFFICE])
            return
        if not self.dependency_manager.installed(CUPS):
            self._offer_install([CUPS])
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
        job = self._selected_own_job()
        if job is None:
            return
        answer = QMessageBox.question(
            self, "인쇄 작업 취소", f"{job.job_id} 작업을 취소할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._background(
                lambda: self.service.cancel(job, getpass.getuser()),
                lambda _: self.refresh_jobs(),
            )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
