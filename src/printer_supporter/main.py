"""프린터·대기열·오류를 한눈에 볼 수 있는 PyQt6 앱."""

from __future__ import annotations

from pathlib import Path
import faulthandler
import getpass
import sys

from .qt_platform import QtPlatformError, configure_qt_platform

# Qt 플랫폼은 반드시 PyQt6 및 QtGui/QtWidgets import 전에 선택합니다.
faulthandler.enable()
try:
    QT_PLATFORM = configure_qt_platform()
except QtPlatformError as exc:
    print(f"QT_PLATFORM_ERROR {exc}", file=sys.stderr)
    raise SystemExit(2) from exc
print(f"QT_PLATFORM_SELECTED platform={QT_PLATFORM}", file=sys.stderr)

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QLineEdit, QGroupBox, QStackedWidget, QFrame,
)

from .backend import CupsService, PrintError, PrintJob, SUPPORTED_EXTENSIONS
from .capabilities import feature_options
from .preview import normalize_page_ranges, pdf_page_count, render_pdf_page
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
        self.option_generation = 0
        self.option_printer = ""
        self.option_keys: dict[str, str] = {}
        self.setWindowTitle("PrintHub · ChromeOS 프린터 관리자")
        self.resize(1000, 760)
        from .theme import APP_STYLESHEET
        self.setStyleSheet(APP_STYLESHEET)

        root = QWidget()
        layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        heading = QLabel("PrintHub")
        heading.setStyleSheet("font-size: 22px; font-weight: 650; color: #182e48; padding: 5px 0;")
        layout.addWidget(heading)
        self.status = QLabel("프린터 연결 확인 중…")
        layout.addWidget(self.status)

        selection = QHBoxLayout()
        selection.addWidget(QLabel("프린터"))
        self.printer_box = QComboBox()
        self.printer_box.currentTextChanged.connect(self.refresh_jobs)
        self.printer_box.currentTextChanged.connect(self.refresh_options)
        selection.addWidget(self.printer_box, 1)
        refresh = QPushButton("새로고침")
        refresh.clicked.connect(self.refresh_all)
        selection.addWidget(refresh)
        check_packages = QPushButton("환경 점검")
        check_packages.clicked.connect(lambda: self.check_dependencies(required_only=False))
        selection.addWidget(check_packages)
        layout.addLayout(selection)

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        layout.addLayout(workspace, 1)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(170)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setSpacing(5)
        tabs = QStackedWidget()
        self.navigation = []
        def add_page(page, title):
            index = tabs.addWidget(page)
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self._switch_page(i))
            side_layout.addWidget(button)
            self.navigation.append(button)
        workspace.addWidget(sidebar)
        workspace.addWidget(tabs, 1)

        print_page = QWidget()
        print_layout = QHBoxLayout(print_page)
        print_layout.setSpacing(16)
        document_panel = QWidget()
        document_layout = QVBoxLayout(document_panel)
        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_panel.setFixedWidth(310)
        settings_layout = QVBoxLayout(settings_panel)
        print_layout.addWidget(document_panel, 1)
        print_layout.addWidget(settings_panel)
        file_row = QHBoxLayout()
        self.file_label = QLabel("선택한 문서 없음")
        file_row.addWidget(self.file_label, 1)
        choose = QPushButton("문서 선택")
        choose.clicked.connect(self.choose_file)
        file_row.addWidget(choose)
        document_layout.addLayout(file_row)
        document_layout.addWidget(QLabel("PDF · Office · 이미지 · 텍스트"))
        preview_group = QGroupBox("문서 미리보기")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel("PDF 파일을 선택하면 미리보기가 표시됩니다.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(370)
        self.preview_label.setStyleSheet("background: #f0f2f5; border-radius: 6px; color: #64717e;")
        preview_layout.addWidget(self.preview_label)
        navigation = QHBoxLayout()
        self.prev_page = QPushButton("이전")
        self.prev_page.clicked.connect(lambda: self._show_preview_page(self.preview_index - 1))
        self.next_page = QPushButton("다음")
        self.next_page.clicked.connect(lambda: self._show_preview_page(self.preview_index + 1))
        self.page_indicator = QLabel("—")
        navigation.addStretch()
        navigation.addWidget(self.prev_page)
        navigation.addWidget(self.page_indicator)
        navigation.addWidget(self.next_page)
        navigation.addStretch()
        preview_layout.addLayout(navigation)
        document_layout.addWidget(preview_group, 1)
        self.preview_index = 0
        self.preview_count = 0
        self.prev_page.setEnabled(False)
        self.next_page.setEnabled(False)
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("페이지"))
        self.page_range = QLineEdit()
        self.page_range.setPlaceholderText("전체 페이지 (예: 1-3, 5)")
        range_row.addWidget(self.page_range, 1)
        settings_layout.addLayout(range_row)
        options = QHBoxLayout()
        options.addWidget(QLabel("인쇄 매수"))
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        options.addWidget(self.copies)
        options.addStretch()
        settings_layout.addLayout(options)

        # 지원하지 않거나 알려지지 않은 옵션은 프린터 기본값을 사용합니다.
        from PyQt6.QtWidgets import QFormLayout
        option_form = QFormLayout()
        self.paper = QComboBox()
        self.color_mode = QComboBox()
        self.duplex_mode = QComboBox()
        self.quality_mode = QComboBox()
        self.resolution_mode = QComboBox()
        self.option_controls = {
            "paper": self.paper,
            "color": self.color_mode,
            "duplex": self.duplex_mode,
            "quality": self.quality_mode,
            "resolution": self.resolution_mode,
        }
        option_labels = {
            "paper": "용지", "color": "흑백 / 컬러", "duplex": "단면 / 양면",
            "quality": "인쇄 품질", "resolution": "해상도",
        }
        for feature, control in self.option_controls.items():
            control.addItem("프린터 기본값", None)
            control.setEnabled(False)
            option_form.addRow(option_labels[feature], control)
        settings_layout.addLayout(option_form)
        self.option_info = QLabel("프린터 옵션을 확인 중입니다…")
        settings_layout.addWidget(self.option_info)
        print_actions = QHBoxLayout()
        self.print_button = QPushButton("인쇄")
        self.print_button.setStyleSheet("background: #225e9e; color: white; border: none; font-weight: 600; padding: 10px 22px;")
        self.print_button.clicked.connect(self.print_selected)
        print_actions.addWidget(self.print_button)
        self.test_page_button = QPushButton("테스트 페이지 인쇄")
        self.test_page_button.clicked.connect(self.print_test_page)
        print_actions.addWidget(self.test_page_button)
        settings_layout.addLayout(print_actions)
        
        settings_layout.addStretch()
        add_page(print_page, "문서 인쇄")

        queue_page = QWidget()
        queue_layout = QVBoxLayout(queue_page)
        queue_tabs = QTabWidget()
        queue_layout.addWidget(queue_tabs)
        active_page = QWidget()
        active_layout = QVBoxLayout(active_page)
        active_layout.addWidget(QLabel("대기 중이거나 인쇄 중인 작업"))
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
        history_layout.addWidget(QLabel("최근 처리된 작업"))
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        queue_tabs.addTab(history_page, "처리 종료 이력")
        self.queue_info = QLabel("목록 갱신 중…")
        queue_layout.addWidget(self.queue_info)
        
        add_page(queue_page, "인쇄 대기열")
        self._update_queue_actions()

        state_page = QWidget()
        state_layout = QVBoxLayout(state_page)
        self.state_text = QTextEdit()
        self.state_text.setReadOnly(True)
        state_layout.addWidget(self.state_text)
        
        add_page(state_page, "프린터 상태")

        add_page(PrinterSetupWidget(on_registered=self.refresh_all), "프린터 추가")
        side_layout.addStretch()
        self._switch_page(0)

        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start()
        self.refresh_all()
        QTimer.singleShot(100, lambda: self.check_dependencies(required_only=True))

    def _switch_page(self, index: int):
        self.centralWidget().findChild(QStackedWidget).setCurrentIndex(index)
        for position, button in enumerate(self.navigation):
            button.setChecked(position == index)

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
        if selected and self.option_printer != selected.name:
            self.refresh_options(selected.name)

    def refresh_options(self, printer: str | None = None):
        printer = printer if isinstance(printer, str) else self.printer_box.currentText()
        self.option_generation += 1
        generation = self.option_generation
        self.option_printer = printer
        self.option_keys = {}
        for control in self.option_controls.values():
            control.clear()
            control.addItem("프린터 기본값", None)
            control.setEnabled(False)
        if not printer:
            self.option_info.setText("프린터를 선택해 주세요.")
            return
        self.option_info.setText(f"{printer} 지원 옵션 조회 중…")
        task = Task(lambda: (printer, generation, self.service.printer_options(printer)))
        task.signals.finished.connect(self._populate_options)
        task.signals.failed.connect(
            lambda message: self._options_failed(printer, generation, message)
        )
        self.pool.start(task)

    def _options_failed(self, printer: str, generation: int, message: str):
        if printer == self.printer_box.currentText() and generation == self.option_generation:
            self.option_info.setText(
                f"지원 옵션을 조회하지 못했습니다: {message} · 프린터 기본값으로 인쇄합니다."
            )

    def _populate_options(self, result):
        printer, generation, options = result
        if printer != self.printer_box.currentText() or generation != self.option_generation:
            return
        supported = feature_options(options)
        self.option_keys = {feature: option.key for feature, option in supported.items()}
        for feature, option in supported.items():
            control = self.option_controls[feature]
            control.clear()
            default_index = 0
            for index, choice in enumerate(option.choices):
                control.addItem(choice.value, choice.value)
                if choice.default:
                    default_index = index
            control.setCurrentIndex(default_index)
            control.setEnabled(len(option.choices) > 1)
        self.option_info.setText(
            f"{printer}: 지원 옵션 {len(supported)}종 감지 · 미지원 항목은 기본값을 사용합니다."
        )

    def _selected_print_options(self) -> dict[str, str]:
        selection = {}
        for feature, key in self.option_keys.items():
            value = self.option_controls[feature].currentData()
            if value is not None:
                selection[key] = value
        return selection

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
        self.queue_info.setText(f"진행 중 {len(jobs)}건")

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
            self._load_preview()

    def _load_preview(self):
        self.preview_index = 0
        self.preview_count = 0
        if self.selected_file and self.selected_file.suffix.lower() == ".pdf":
            try:
                self.preview_count = pdf_page_count(self.selected_file)
                self._show_preview_page(0)
            except Exception as exc:
                self.preview_label.setText(f"미리보기를 열 수 없습니다: {exc}")
        else:
            self.preview_label.setText("미리보기는 PDF 파일에서 사용할 수 있습니다.")
            self.page_indicator.setText("—")
            self.prev_page.setEnabled(False)
            self.next_page.setEnabled(False)

    def _show_preview_page(self, index: int):
        if not self.selected_file or not 0 <= index < self.preview_count:
            return
        from PyQt6.QtGui import QPixmap
        try:
            image = QPixmap()
            image.loadFromData(render_pdf_page(self.selected_file, index))
            self.preview_label.setPixmap(image.scaled(max(400, self.preview_label.width() - 20), 460, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.preview_index = index
            self.page_indicator.setText(f"{index + 1} / {self.preview_count}")
            self.prev_page.setEnabled(index > 0)
            self.next_page.setEnabled(index + 1 < self.preview_count)
        except Exception as exc:
            self.preview_label.setText(f"미리보기 오류: {exc}")

    def print_test_page(self):
        printer = self.printer_box.currentText()
        if not printer:
            self.show_error("테스트할 프린터를 먼저 선택해 주세요.")
            return
        media = self.paper.currentData()
        selected_options = self._selected_print_options()
        answer = QMessageBox.question(
            self,
            "테스트 페이지 인쇄",
            f"'{printer}' 프린터로 {media or '기본 용지'} 테스트 페이지 1장을 출력할까요?\n"
            "회사 공용 프린터에서 실제 종이가 출력될 수 있습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.test_page_button.setEnabled(False)

        def operation():
            try:
                return (True, self.service.print_test_page(printer, media=media, options=selected_options))
            except Exception as exc:
                return (False, str(exc))

        self._background(operation, self._test_page_printed)

    def _test_page_printed(self, result):
        self.test_page_button.setEnabled(True)
        success, message = result
        if success:
            self.status.setText(f"테스트 페이지 접수: {message}")
            self.refresh_jobs()
        else:
            self.show_error(message)

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
        ranges = self.page_range.text().strip() or None
        if ranges:
            try:
                ranges = normalize_page_ranges(ranges, self.preview_count or None)
            except ValueError as exc:
                self.show_error(str(exc))
                return
        self.print_button.setEnabled(False)
        source, printer = self.selected_file, self.printer_box.currentText()
        copies, paper = self.copies.value(), self.paper.currentData()
        selected_options = self._selected_print_options()
        def print_operation():
            try:
                return (True, self.service.print_file(source, printer, copies=copies, media=paper, options=selected_options, page_ranges=ranges))
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
    exit_code = app.exec()
    print(f"APP_EXIT code={exit_code}", file=sys.stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
