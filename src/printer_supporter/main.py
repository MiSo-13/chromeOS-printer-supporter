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

from PyQt6.QtCore import QThreadPool, QTimer, Qt, QEvent
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QTextEdit, QPlainTextEdit,
    QVBoxLayout, QWidget, QLineEdit, QStackedWidget, QFrame,
)

from .backend import CupsService, PrintError, PrintJob, SUPPORTED_EXTENSIONS, OFFICE_EXTENSIONS
from .capabilities import feature_options
from .diagnostics import diagnose_printer
from .document_input import local_document_from_mime, supported_document
from .preview import normalize_page_ranges, pdf_page_count, render_pdf_page, read_text_preview
from .preview_widget import read_image
from .office_preview import ConvertedOfficePreview, convert_office_preview
from .settings import SettingsStore
from .theme import stylesheet_for
from .ui_pages import build_workspace_pages
from .tasks import BackgroundTask as Task, TaskSignals as Signals
from .document_drop import DocumentDropArea
from .app_menu import build_menus
from .dependencies import CUPS, LIBREOFFICE, DependencyManager
from .dialogs import confirm_action


class MainWindow(QMainWindow):
    def __init__(self, service: CupsService | None = None, dependency_manager: DependencyManager | None = None):
        super().__init__()
        self.service = service or CupsService()
        self.dependency_manager = dependency_manager or DependencyManager()
        self.pool = QThreadPool.globalInstance()
        self.selected_file: Path | None = None
        self._dependency_install_busy = False
        self._preview_generation = 0
        self._preview_pdf_path: Path | None = None
        self._office_preview: ConvertedOfficePreview | None = None
        self.current_jobs: list[PrintJob] = []
        self.completed_jobs: list[PrintJob] = []
        self.queue_generation = 0
        self.option_generation = 0
        self.option_printer = ""
        self.option_keys: dict[str, str] = {}
        self._print_busy = False
        QApplication.instance().installEventFilter(self)
        self.setAcceptDrops(True)
        self.setWindowTitle("ChromeOS Printer Supporter")
        self.resize(1120, 800)
        self.setMinimumSize(960, 680)
        self.settings = SettingsStore()
        self.setStyleSheet(stylesheet_for(self.settings.data["theme"]))
        self._theme_actions = build_menus(
            self, theme=self.settings.data["theme"],
            open_file=self.choose_file,
            refresh=self.refresh_all,
            change_theme=self._change_theme,
        )

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 10)
        layout.setSpacing(12)
        self.setCentralWidget(root)

        heading = QLabel("ChromeOS Printer Supporter")
        heading.setObjectName("appTitle")
        layout.addWidget(heading)
        self.status = QLabel("프린터 연결 확인 중…")
        layout.addWidget(self.status)

        selection = QHBoxLayout()
        selection.setSpacing(12)
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
        side_layout.setContentsMargins(10, 14, 10, 12)
        side_layout.setSpacing(8)
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

        build_workspace_pages(self, add_page)
        side_layout.addStretch()
        self._switch_page(0)
        footer = QHBoxLayout()
        footer.addStretch()
        credit = QLabel("made by MiSo")
        credit.setObjectName("appCredit")
        footer.addWidget(credit)
        layout.addLayout(footer)

        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start()
        self.refresh_all()
        QTimer.singleShot(100, lambda: self.check_dependencies(required_only=True))

    @staticmethod
    def _text_input_has_focus() -> bool:
        """실제로 편집 가능한 입력란의 일반 Ctrl+V만 보호합니다."""
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return not focused.isReadOnly()
        if isinstance(focused, QSpinBox):
            return True
        if isinstance(focused, QComboBox):
            return focused.isEditable()
        return False

    def eventFilter(self, watched, event):
        """프린터 선택창을 포함해 앱 어디서나 복사한 문서 파일을 붙여넣습니다."""
        if (event.type() == QEvent.Type.KeyPress and self.isActiveWindow()
                and event.key() == Qt.Key.Key_V
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and isinstance(watched, QWidget)
                and (watched is self or self.isAncestorOf(watched))
                and not self._text_input_has_focus()):
            path = local_document_from_mime(QApplication.clipboard().mimeData())
            if path is not None:
                self._set_document(path)
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        # 이벤트 테스트에서 __init__ 없이 생성한 최소 Qt 창도 안전하게 종료합니다.
        if hasattr(self, "_preview_generation"):
            self._preview_generation += 1
            self._release_office_preview()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if local_document_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if local_document_from_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        path = local_document_from_mime(event.mimeData())
        if path:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda selected=path: self._set_document(selected))
        else:
            super().dropEvent(event)

    def _change_theme(self, theme: str):
        """메뉴에서 선택한 테마를 저장하고 창 전체에 적용합니다."""
        previous = self.settings.data["theme"]
        if theme == previous:
            return
        try:
            self.settings.set_theme(theme)
        except OSError as exc:
            self._theme_actions[previous].setChecked(True)
            self.show_error(f"테마 설정 저장 실패: {exc}")
            return
        self.setStyleSheet(stylesheet_for(theme))

    def _switch_page(self, index: int):
        self.centralWidget().findChild(QStackedWidget).setCurrentIndex(index)
        for position, button in enumerate(self.navigation):
            button.setChecked(position == index)

    def _background(self, operation, completed, failed=None):
        task = Task(operation)
        task.signals.finished.connect(completed)
        task.signals.failed.connect(failed or self.show_error)
        self.pool.start(task)

    def check_dependencies(self, *, required_only: bool = False):
        missing = self.dependency_manager.missing(required_only=required_only)
        if not missing:
            if not required_only:
                QMessageBox.information(self, "의존성 점검", "필요한 패키지가 모두 설치되어 있습니다.")
            return
        self._offer_install(missing)

    def _offer_install(self, missing):
        if self._dependency_install_busy or not missing:
            return
        names = ", ".join(dep.name for dep in missing)
        command = " ".join(self.dependency_manager.installation_command(missing))
        description = "\n".join(
            f"  - {dep.name}: {', '.join(dep.packages)}\n    {dep.description}"
            for dep in missing
        )
        if not confirm_action(
            self, title="패키지 설치 확인",
            summary=f"필요한 패키지 {len(missing)}개를 설치할까요?",
            details=(
                f"설치 대상:\n{description}\n\n"
                f"실행 명령:\n{command}\n\n"
                "설치 위치: Crostini Linux 컨테이너\n"
                "영향: 시스템 패키지 및 의존성이 설치됩니다.\n"
                "sudo 권한과 네트워크 연결이 필요합니다.\n"
                "프린터 등록이나 실제 인쇄는 하지 않습니다."
            ),
            confirm_label="설치",
        ):
            self.status.setText(f"설치 취소: {names}")
            return
        self._dependency_install_busy = True
        self.status.setText(f"패키지 설치 중: {names}")
        try:
            self._background(
                lambda: self.dependency_manager.install(missing, approved=True),
                self._installation_finished,
                self._installation_failed,
            )
        except Exception as exc:
            self._installation_failed(str(exc))

    def _installation_failed(self, message: str):
        self._dependency_install_busy = False
        self.show_error("패키지 설치 실패: " + message)

    def _installation_finished(self, message: str):
        self._dependency_install_busy = False
        QMessageBox.information(self, "패키지 설치 완료", message)
        self.status.setText(message)
        self.refresh_all()
        if (self.selected_file is not None
                and self.selected_file.suffix.lower() in OFFICE_EXTENSIONS
                and self._preview_pdf_path is None):
            self._load_preview()

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
        self.printer_box.blockSignals(False)
        selected = next((p for p in printers if p.name == self.printer_box.currentText()), None)
        self.selected_printer_status = selected
        self._update_diagnosis(selected.reason if selected else "")
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
        self.option_info.setText("인쇄 설정을 불러오는 중…")
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
            "인쇄 설정을 불러왔습니다."
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
            self.state_text.clear()
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

    def _update_diagnosis(self, detail: str):
        printer = getattr(self, "selected_printer_status", None)
        if printer is None:
            self.diagnosis_label.setText("등록된 프린터가 없습니다.")
            self.diagnosis_advice.setText("프린터 추가에서 네트워크 프린터를 검색하거나 IP 주소로 등록하세요.")
            return
        diagnosis = diagnose_printer(printer.state, printer.enabled, detail or printer.reason)
        self.diagnosis_label.setText(f"{printer.name} · {diagnosis.summary}")
        self.diagnosis_advice.setText(diagnosis.advice)
        self.diagnosis_label.setProperty("severity", diagnosis.severity)
        self.diagnosis_label.style().unpolish(self.diagnosis_label)
        self.diagnosis_label.style().polish(self.diagnosis_label)

    def _populate_reasons(self, result):
        printer, generation, reason = result
        if self._valid_queue_result(printer, generation):
            self.state_text.setPlainText(reason)
            self._update_diagnosis(reason)

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
                f"{job.job_id}  ·  {owned} ({job.owner})  ·  "
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
                f"{job.job_id}  ·  {job.owner}  ·  "
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

    def _set_document(self, path: Path):
        path = Path(path).expanduser()
        if not supported_document(path):
            self.show_error("지원하지 않거나 존재하지 않는 문서 파일입니다.")
            return
        self.selected_file = path
        self.file_label.setText(path.name)
        self.file_label.setToolTip(str(path))
        self._load_preview()
        try:
            self.settings.set_last_document_dir(path.parent)
        except OSError as exc:
            self.status.setText(f"문서는 선택했지만 최근 폴더 저장에 실패했습니다: {exc}")

    def choose_file(self):
        extensions = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        stored_dir = self.settings.data.get("last_document_dir", "")
        saved = Path(stored_dir).expanduser() if stored_dir else None
        initial_dir = saved if saved is not None and saved.is_dir() else Path.home()
        name, _ = QFileDialog.getOpenFileName(
            self, "인쇄할 문서 선택", str(initial_dir), f"지원 문서 ({extensions})"
        )
        if name:
            self._set_document(Path(name))

    def _set_preview_navigation(self, has_pdf: bool, *, can_zoom: bool = False):
        self.prev_page.setEnabled(has_pdf and self.preview_index > 0)
        self.next_page.setEnabled(has_pdf and self.preview_index + 1 < self.preview_count)
        self.page_indicator.setText(
            f"{self.preview_index + 1} / {self.preview_count}" if has_pdf else "—"
        )
        self.zoom_box.setEnabled(can_zoom)

    def _change_preview_zoom(self, _index: int):
        self.preview_view.set_zoom(self.zoom_box.currentData())

    def _release_office_preview(self):
        self._preview_pdf_path = None
        if self._office_preview is not None:
            self._office_preview.close()
            self._office_preview = None

    def _load_preview(self):
        self._preview_generation += 1
        self._release_office_preview()
        self.preview_retry_button.setVisible(False)
        self.preview_index = 0
        self.preview_count = 0
        # 새 문서를 열면 이전 파일의 확대 배율을 이어받지 않습니다.
        self.zoom_box.blockSignals(True)
        self.zoom_box.setCurrentIndex(0)
        self.zoom_box.blockSignals(False)
        self.preview_view.set_zoom("fit")
        self.preview_view.clear("미리보기를 불러오는 중…")
        self._set_preview_navigation(False)
        if self.selected_file is None:
            self.preview_view.clear("문서를 선택하면 미리보기가 표시됩니다.")
            return

        suffix = self.selected_file.suffix.lower()
        if suffix == ".pdf":
            try:
                self._preview_pdf_path = self.selected_file
                self.preview_count = pdf_page_count(self.selected_file)
                if self.preview_count == 0:
                    raise ValueError("페이지가 없는 PDF입니다.")
                self._show_preview_page(0)
            except Exception as exc:
                self.preview_count = 0
                self.preview_view.clear(f"PDF 미리보기를 열 수 없습니다: {exc}")
                self._set_preview_navigation(False)
        elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff"}:
            try:
                self.preview_view.show_image(read_image(self.selected_file))
                self._set_preview_navigation(False, can_zoom=True)
            except Exception as exc:
                self.preview_view.clear(f"이미지 미리보기를 열 수 없습니다: {exc}")
        elif suffix == ".txt":
            try:
                self.preview_view.show_text(read_text_preview(self.selected_file))
            except Exception as exc:
                self.preview_view.clear(f"텍스트 미리보기를 열 수 없습니다: {exc}")
        elif suffix in OFFICE_EXTENSIONS:
            if not self.dependency_manager.installed(LIBREOFFICE):
                self.preview_view.clear(
                    "Office 미리보기에는 LibreOffice가 필요합니다. "
                    "환경 점검에서 설치한 뒤 '미리보기 다시 시도'를 누르세요."
                )
                self.preview_retry_button.setVisible(True)
                return
            source = self.selected_file
            generation = self._preview_generation
            self.preview_view.clear("LibreOffice로 미리보기용 PDF를 만드는 중…")
            task = Task(lambda: (generation, source, convert_office_preview(source)))
            task.signals.finished.connect(self._office_preview_ready)
            task.signals.failed.connect(
                lambda error, expected=generation: self._office_preview_failed(expected, error)
            )
            self.pool.start(task)
        else:
            self.preview_view.clear("이 파일 형식의 미리보기를 지원하지 않습니다.")

    def _office_preview_ready(self, result):
        generation, source, converted = result
        if generation != self._preview_generation or source != self.selected_file:
            converted.close()
            return
        self._office_preview = converted
        self._preview_pdf_path = converted.pdf_path
        self.preview_count = converted.page_count
        self._show_preview_page(0)

    def _office_preview_failed(self, generation: int, error: str):
        if generation != self._preview_generation:
            return
        self.preview_count = 0
        self._release_office_preview()
        self.preview_view.clear(f"Office 미리보기 실패: {error}")
        self._set_preview_navigation(False)
        self.preview_retry_button.setVisible(True)

    def _show_preview_page(self, index: int):
        if self._preview_pdf_path is None or not 0 <= index < self.preview_count:
            return
        try:
            image = QPixmap()
            if not image.loadFromData(
                render_pdf_page(self._preview_pdf_path, index, scale=1.6)
            ):
                raise ValueError("PDF 페이지 이미지를 표시할 수 없습니다.")
            self.preview_view.show_image(image)
            self.preview_index = index
            self._set_preview_navigation(True, can_zoom=True)
        except Exception as exc:
            self._release_office_preview()
            self.preview_count = 0
            self.preview_view.clear(f"PDF 미리보기 오류: {exc}")
            self._set_preview_navigation(False)
            self.preview_retry_button.setVisible(True)

    def _set_print_busy(self, busy: bool, message: str = ""):
        """문서 인쇄·테스트 인쇄 중복 요청을 앱 레벨에서도 차단합니다."""
        self._print_busy = busy
        self.print_button.setEnabled(not busy)
        self.test_page_button.setEnabled(not busy)
        self.print_button.setText("인쇄 요청 중…" if busy else "인쇄")
        self.test_page_button.setText("요청 중…" if busy else "테스트 페이지 인쇄")
        self.print_progress.setVisible(busy)
        if message:
            self.print_feedback.setText(message)
            self.status.setText(message)

    def print_test_page(self):
        if self._print_busy:
            return
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
        self._set_print_busy(True, "테스트 페이지를 CUPS에 보내는 중…")

        def operation():
            try:
                return (True, self.service.print_test_page(printer, media=media, options=selected_options))
            except Exception as exc:
                return (False, str(exc))

        try:
            self._background(operation, self._test_page_printed)
        except Exception as exc:
            self._set_print_busy(False, "인쇄 요청 실패")
            self.show_error(str(exc))

    def _test_page_printed(self, result):
        self._set_print_busy(False)
        success, message = result
        if success:
            self.print_feedback.setText("테스트 페이지 접수 완료 · 인쇄 대기열에서 확인하세요.")
            self.status.setText(f"테스트 페이지 접수: {message}")
            self.refresh_jobs()
        else:
            self.print_feedback.setText("테스트 페이지 요청 실패 · 오류를 확인하세요.")
            self.show_error(message)

    def print_selected(self):
        if self._print_busy:
            return
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
        self._set_print_busy(True, "인쇄 작업을 CUPS에 보내는 중…")
        source, printer = self.selected_file, self.printer_box.currentText()
        copies, paper = self.copies.value(), self.paper.currentData()
        selected_options = self._selected_print_options()
        def print_operation():
            try:
                return (True, self.service.print_file(source, printer, copies=copies, media=paper, options=selected_options, page_ranges=ranges))
            except Exception as exc:
                return (False, str(exc))

        try:
            self._background(print_operation, self._printed)
        except Exception as exc:
            self._set_print_busy(False, "인쇄 요청 실패")
            self.show_error(str(exc))

    def _printed(self, result):
        self._set_print_busy(False)
        success, message = result
        if success:
            self.print_feedback.setText("인쇄 작업 접수 완료 · 인쇄 대기열에서 확인하세요.")
            self.status.setText(f"작업 접수: {message}")
            self.refresh_jobs()
        else:
            self.print_feedback.setText("인쇄 요청 실패 · 오류를 확인하세요.")
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
