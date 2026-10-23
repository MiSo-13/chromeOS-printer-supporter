"""CUPS 네트워크 프린터 검색과 등록 UI."""

from __future__ import annotations

import re
import shlex

from PyQt6.QtCore import QThreadPool, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .discovery import (
    DiscoveredPrinter, DiscoveryService, PrinterRegistrationError,
    Registration, manual_printer, validate_registration, registration_command,
)
from .identification import PrinterIdentity, identify_printer, unknown_identity
from .dialogs import confirm_action, show_guide
from .support_catalog import assess_printer
from .driver_recommendation import DriverAdvisor, DriverRecommendation
from .driver_installation import (
    DriverInstallPlan, DriverInstallService, official_support_for, package_for_identity,
)


from .tasks import BackgroundTask as Worker, TaskSignals as WorkerSignals


class PrinterSetupWidget(QWidget):
    def __init__(self, *, service: DiscoveryService | None = None, on_registered=None,
                 identifier=None, advisor: DriverAdvisor | None = None,
                 installer: DriverInstallService | None = None):
        super().__init__()
        self.service = service or DiscoveryService()
        self.on_registered = on_registered
        self.identifier = identifier or identify_printer
        self.advisor = advisor or DriverAdvisor()
        self.installer = installer or DriverInstallService()
        self.pool = QThreadPool.globalInstance()
        self.current_device: DiscoveredPrinter | None = None
        self.identity_result: PrinterIdentity | None = None
        self.driver_recommendation: DriverRecommendation | None = None
        self.install_plan: DriverInstallPlan | None = None
        self.identity_generation = 0
        self._install_busy = False
        self._driver_user_edited = False
        self._queue_name_user_edited = False
        self._search_info_seen = False
        self._scan_busy = False
        self._register_busy = False

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)
        scroller.setWidget(content)
        outer_layout.addWidget(scroller)

        intro = QHBoxLayout()
        title = QLabel("프린터 연결하기")
        title.setObjectName("setupTitle")
        intro.addWidget(title)
        intro.addStretch()
        self.help_button = QPushButton("사용 방법")
        self.help_button.setObjectName("setupHelpButton")
        self.help_button.clicked.connect(self.show_help)
        intro.addWidget(self.help_button)
        layout.addLayout(intro)
        steps = QLabel("① 프린터 찾기    ② 모델 확인    ③ 드라이버 선택    ④ 등록")
        steps.setObjectName("setupSteps")
        steps.setWordWrap(True)
        layout.addWidget(steps)

        discovery_group = QGroupBox("1. 프린터 찾기")
        discovery_group.setObjectName("setupStep")
        discovery_layout = QVBoxLayout(discovery_group)
        discovery_layout.addWidget(QLabel("같은 네트워크의 프린터를 찾거나 IP를 입력하세요."))
        scan_row = QHBoxLayout()
        scan_row.setSpacing(12)
        self.scan_button = QPushButton("프린터 검색")
        self.scan_button.clicked.connect(self.search)
        scan_row.addWidget(self.scan_button)
        scan_row.addStretch()
        discovery_layout.addLayout(scan_row)

        self.devices = QListWidget()
        self.devices.currentItemChanged.connect(self._select_discovered)
        self.devices.setMinimumHeight(100)
        discovery_layout.addWidget(self.devices)
        manual_form = QFormLayout()
        manual_form.setSpacing(8)
        discovery_layout.addLayout(manual_form)
        layout.addWidget(discovery_group)

        details = QGroupBox("2. 모델 확인")
        details.setObjectName("setupStep")
        details_layout = QVBoxLayout(details)
        details_layout.setSpacing(6)
        self.identity_summary = QLabel("프린터를 선택하면 모델을 확인합니다.")
        self.identity_summary.setWordWrap(True)
        details_layout.addWidget(self.identity_summary)
        self.identity_evidence = QLabel("정보 출처: 미확인")
        self.identity_evidence.setWordWrap(True)
        details_layout.addWidget(self.identity_evidence)
        self.identity_advice = QLabel("IPP 지원 여부 확인 전")
        self.identity_advice.setWordWrap(True)
        details_layout.addWidget(self.identity_advice)
        self.focus_summary = QLabel("우선 안내 모델 목록과 비교합니다.")
        self.focus_summary.setObjectName("focusSupportSummary")
        self.focus_summary.setWordWrap(True)
        details_layout.addWidget(self.focus_summary)
        self.focus_detail = QLabel(
            "목록에 없더라도 IPP/CUPS 호환성 확인과 수동 드라이버 선택은 계속 사용할 수 있습니다."
        )
        self.focus_detail.setObjectName("focusSupportDetail")
        self.focus_detail.setWordWrap(True)
        details_layout.addWidget(self.focus_detail)
        self.identify_button = QPushButton("다시 확인")
        self.identify_button.setEnabled(False)
        self.identify_button.clicked.connect(self.identify_current)
        details_layout.addWidget(self.identify_button)
        self.details_toggle = QPushButton("상세 정보 보기")
        self.details_toggle.setCheckable(True)
        self.details_toggle.toggled.connect(self._toggle_details)
        details_layout.addWidget(self.details_toggle)
        layout.addWidget(details)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("예: 192.168.6.147")
        manual_form.addRow("IP 주소", self.ip_input)
        self.protocol = QComboBox()
        self.protocol.addItem("IPP (631) · 지원 여부 자동 확인", "ipp")
        self.protocol.addItem("Socket / JetDirect (9100)", "socket")
        manual_form.addRow("연결 방식", self.protocol)
        apply_ip = QPushButton("IP 주소 적용")
        apply_ip.clicked.connect(self.apply_manual)
        manual_form.addRow("", apply_ip)

        self.uri = QLineEdit()
        self.uri.setReadOnly(True)
        details_layout.addWidget(self.uri)
        self.queue_name = QLineEdit()
        self.queue_name.setPlaceholderText("예: Samsung_SL_M2030W")
        register_form = QFormLayout()
        register_form.addRow("프린터 이름", self.queue_name)
        self.queue_name.textEdited.connect(self._queue_name_edited)
        self.driver = QComboBox()
        self.driver.addItem("IPP Everywhere (지원 확인 필요)", "everywhere")
        self.driver.addItem("설치된 CUPS 드라이버 모델", "model")
        self.driver.addItem("설치된 제조사 PPD 파일", "ppd")
        self.driver.currentIndexChanged.connect(self._driver_changed)
        self.driver.activated.connect(self._mark_driver_user_edited)
        form.addRow("드라이버", self.driver)
        self.model_choice = QComboBox()
        self.model_choice.setAccessibleName("설치된 CUPS 모델")
        self.model_choice.addItem("일치하는 모델을 먼저 확인하세요", None)
        self.model_choice.setEnabled(False)
        form.addRow("CUPS 모델", self.model_choice)
        self.recommendation_summary = QLabel("드라이버 추천: 프린터를 선택해 주세요.")
        self.recommendation_summary.setWordWrap(True)
        form.addRow("추천", self.recommendation_summary)
        self.recommendation_detail = QLabel(
            "드라이버 설치 없이 로컬 CUPS 목록을 검사합니다."
        )
        self.recommendation_detail.setWordWrap(True)
        form.addRow("", self.recommendation_detail)
        self.install_panel = QGroupBox("드라이버 확보 및 설치 안내")
        install_layout = QVBoxLayout(self.install_panel)
        self.official_support_label = QLabel("제조사 공식 지원 페이지를 확인합니다.")
        self.official_support_label.setWordWrap(True)
        install_layout.addWidget(self.official_support_label)
        self.official_support_button = QPushButton("제조사 공식 지원 페이지 열기")
        self.official_support_button.setEnabled(False)
        self.official_support_button.clicked.connect(self._open_official_support)
        install_layout.addWidget(self.official_support_button)
        self.install_status_label = QLabel("배포판 패키지 지원 여부를 조회합니다.")
        self.install_status_label.setWordWrap(True)
        install_layout.addWidget(self.install_status_label)
        self.install_button = QPushButton("확인된 배포판 드라이버 설치")
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install_driver)
        install_layout.addWidget(self.install_button)
        install_note = QLabel(
            "제조사 다운로드 파일은 직접 확인해야 하며 자동 실행하지 않습니다. "
            "배포판 패키지는 호환 모델 확인과 별도 승인 후에만 설치합니다."
        )
        install_note.setWordWrap(True)
        install_layout.addWidget(install_note)
        # 설치 안내는 드라이버 선택 아래에 함께 배치합니다.

        self.ppd_path = QLineEdit()
        self.ppd_path.setPlaceholderText("삼성 ULD 등 설치된 PPD 파일 경로")
        ppd_row = QHBoxLayout()
        ppd_row.setSpacing(12)
        ppd_row.addWidget(self.ppd_path)
        ppd_button = QPushButton("찾아보기")
        ppd_button.clicked.connect(self.choose_ppd)
        ppd_row.addWidget(ppd_button)
        form.addRow("PPD 파일", ppd_row)
        driver_group = QGroupBox("3. 드라이버 선택")
        driver_group.setObjectName("setupStep")
        driver_layout = QVBoxLayout(driver_group)
        driver_layout.addLayout(form)
        driver_layout.addWidget(self.install_panel)
        layout.addWidget(driver_group)

        register_group = QGroupBox("4. 프린터 등록")
        register_group.setObjectName("setupStep")
        register_layout = QVBoxLayout(register_group)
        register_layout.addLayout(register_form)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.probe_button = QPushButton("연결 확인")
        self.probe_button.setEnabled(False)
        self.probe_button.clicked.connect(self.probe)
        actions.addWidget(self.probe_button)
        self.register_button = QPushButton("이 프린터 등록")
        self.register_button.setEnabled(False)
        self.register_button.clicked.connect(self.register)
        actions.addWidget(self.register_button)
        register_layout.addLayout(actions)
        self.status = QLabel("먼저 프린터를 검색하세요.")
        self.status.setObjectName("setupStatus")
        self.status.setWordWrap(True)
        register_layout.addWidget(self.status)
        layout.addWidget(register_group)

        self._optional_details = [
            self.identity_evidence, self.identity_advice, self.focus_detail,
            self.recommendation_detail, self.official_support_label, install_note,
        ]
        self._toggle_details(False)
        self._driver_changed()
        # lpinfo -v는 일부 Crostini CUPS에서 관리자 권한이 필요합니다.
        # 앱 시작 시 자동 실행하지 않고 사용자가 검색 버튼을 누를 때만 실행합니다.

    def _toggle_details(self, expanded: bool):
        for label in self._optional_details:
            label.setVisible(expanded)
        self.details_toggle.setText("상세 정보 접기" if expanded else "상세 정보 보기")

    def show_help(self):
        show_guide(
            self, title="프린터 연결 방법",
            summary="4단계로 프린터를 등록할 수 있습니다.",
            details=(
                "1. 프린터 찾기: 검색하거나 IP 주소를 입력합니다.\n"
                "2. 모델 확인: 검색된 프린터를 선택합니다.\n"
                "3. 드라이버 선택: 추천 항목 또는 PPD 파일을 선택합니다.\n"
                "4. 등록: 이름을 확인하고 '이 프린터 등록'을 누릅니다.\n\n"
                "패키지 설치와 프린터 등록은 작업 내용을 확인한 뒤 승인합니다."
            ),
        )

    def _background(self, operation, callback, failed=None):
        worker = Worker(operation)
        worker.signals.finished.connect(callback)
        worker.signals.failed.connect(failed or self._error)
        self.pool.start(worker)

    def _error(self, message: str):
        """일반 오류는 현재 검색·등록 작업 상태를 변경하지 않습니다."""
        self.status.setText("오류: " + message)
        QMessageBox.warning(self, "프린터 설정 오류", message)

    def _registration_failed(self, message: str):
        self._register_busy = False
        self.register_button.setEnabled(self.current_device is not None)
        self._error(message)

    def _search_failed(self, message: str):
        self._scan_busy = False
        self.scan_button.setEnabled(True)
        if "forbidden" in message.lower() or "not authorized" in message.lower():
            self.status.setText(
                "CUPS가 네트워크 검색(lpinfo)을 거부했습니다. "
                "IP 주소 직접 입력이나 기존 등록 프린터 사용은 가능합니다."
            )
        else:
            self.status.setText(f"네트워크 검색 실패: {message} · IP 직접 입력은 가능합니다.")

    def search(self):
        if self._scan_busy:
            return
        if not self._search_info_seen:
            if not confirm_action(
                self, title="프린터 검색",
                summary="같은 네트워크에서 프린터를 찾습니다.",
                details=(
                    "실행 명령: lpinfo -v\n\n"
                    "변경 사항: 없음\n"
                    "Linux(Crostini)의 CUPS 장치 검색 결과를 읽습니다.\n"
                    "프린터 등록, 드라이버 설치, 다운로드, 인쇄는 하지 않습니다.\n"
                    "검색이 안 되면 IP 주소를 직접 입력할 수 있습니다."
                ),
                confirm_label="검색 시작",
            ):
                return
            self._search_info_seen = True
        self._scan_busy = True
        self.scan_button.setEnabled(False)
        self.status.setText("프린터 검색 중…")
        worker = Worker(self.service.discover)
        worker.signals.finished.connect(self._populate)
        worker.signals.failed.connect(self._search_failed)
        self.pool.start(worker)

    def _populate(self, devices):
        self._scan_busy = False
        self.scan_button.setEnabled(True)
        self.devices.clear()
        for device in devices:
            item = QListWidgetItem(f"{device.name}  ·  {device.scheme}")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.devices.addItem(item)
        if len(devices) == 1:
            self.devices.setCurrentRow(0)
        self.status.setText(
            f"{len(devices)}개 발견 · 프린터를 선택하세요." if devices
            else "검색 결과가 없습니다. IP 주소를 입력해 보세요."
        )

    def _select_discovered(self, current, previous):
        if current:
            self._select_device(current.data(Qt.ItemDataRole.UserRole))

    def _queue_name_edited(self, _value: str):
        self._queue_name_user_edited = True

    def _select_device(self, device: DiscoveredPrinter):
        self.current_device = device
        self.probe_button.setEnabled(True)
        self.register_button.setEnabled(not self._register_busy)
        self._driver_user_edited = False
        self.driver_recommendation = None
        self.install_plan = None
        self._reset_install_panel()
        self.model_choice.clear()
        self.model_choice.addItem("드라이버 모델 확인 중", None)
        self.recommendation_summary.setText("드라이버 추천: 모델 분석 대기 중…")
        self.recommendation_detail.setText("설치된 CUPS 드라이버 목록을 조회합니다.")
        self.uri.setText(device.uri)
        if not self._queue_name_user_edited:
            slug = re.sub(r"[^A-Za-z0-9_.-]", "_", device.name)
            slug = "Printer_" + slug if not slug or not slug[0].isalpha() else slug
            self.queue_name.setText(slug[:64])
        index = self.driver.findData("ppd" if device.scheme == "socket" else "everywhere")
        self.driver.setCurrentIndex(index)
        self.status.setText("연결 방식과 드라이버를 확인한 뒤 등록해 주세요.")
        self.identify_current()

    def identify_current(self):
        device = self.current_device
        if device is None:
            return
        self.identity_generation += 1
        generation = self.identity_generation
        self.identity_result = None
        self.driver_recommendation = None
        self.install_plan = None
        self._reset_install_panel()
        self.model_choice.clear()
        self.model_choice.addItem("드라이버 모델 확인 중", None)
        self._driver_changed()
        self.recommendation_summary.setText("드라이버 목록을 확인할 준비 중…")
        self.recommendation_detail.setText("IPP 속성 조회 후 로컬 CUPS 목록을 비교합니다.")
        self.identify_button.setEnabled(False)
        self.identity_summary.setText("모델 정보를 확인하는 중…")
        self.focus_summary.setText("우선 지원 안내 목록 확인 중…")
        self.focus_detail.setText("장치에서 확인된 모델명과 목록을 비교합니다.")
        self.identity_evidence.setText(f"연결 방식: {device.scheme.upper()} / 조회 중")
        self.identity_advice.setText("IPP 프린터만 읽기 전용 속성 조회를 실행합니다.")
        worker = Worker(lambda: (generation, device, self.identifier(device)))
        worker.signals.finished.connect(self._identity_ready)
        worker.signals.failed.connect(
            lambda message, expected=generation, selected=device:
                self._identity_failed(expected, selected, message)
        )
        self.pool.start(worker)

    def _identity_ready(self, result):
        generation, device, identity = result
        if generation != self.identity_generation or self.current_device != device:
            return
        self.identify_button.setEnabled(True)
        self.identity_result = identity
        self.identity_summary.setText(
            f"{identity.name} · {identity.manufacturer or '제조사 미확인'}"
        )
        status = {
            "reported": "IPP Everywhere 기능 보고",
            "candidate": "드라이버리스 후보 (미검증)",
            "unknown": "드라이버리스 지원 미확인",
        }.get(identity.driverless, "지원 미확인")
        version = ", ".join(identity.ipp_versions) or "미확인"
        self.identity_evidence.setText(
            f"출처: {identity.source} · 연결: {identity.protocol} · "
            f"IPP: {version} · {status}"
        )
        self.identity_advice.setText(identity.recommendation)
        self.identity_advice.setToolTip(
            "지원 형식: " + (", ".join(identity.document_formats) or "미확인")
        )
        assessment = assess_printer(identity)
        self.focus_summary.setText(assessment.title)
        self.focus_detail.setText(assessment.detail)
        # 설치 후보가 없는 대부분의 프린터는 공식 URL만 조회하므로
        # 별도 스레드를 만들지 않고 즉시 안내해 창 종료 시 경쟁을 줄입니다.
        if package_for_identity(identity) is None:
            try:
                self._install_plan_ready(
                    (generation, device, self.installer.plan(identity))
                )
            except Exception as exc:
                self._install_plan_failed(generation, device, str(exc))
        else:
            install_worker = Worker(lambda: (
                generation, device, self.installer.plan(identity)
            ))
            install_worker.signals.finished.connect(self._install_plan_ready)
            install_worker.signals.failed.connect(
                lambda message, expected=generation, selected=device:
                    self._install_plan_failed(expected, selected, message)
            )
            self.pool.start(install_worker)
        self.recommendation_summary.setText("드라이버 확인 중…")
        worker = Worker(lambda: (
            generation, device, self.advisor.advise(device, identity)
        ))
        worker.signals.finished.connect(self._recommendation_ready)
        worker.signals.failed.connect(
            lambda message, expected=generation, selected=device:
                self._recommendation_failed(expected, selected, message)
        )
        self.pool.start(worker)

    def _reset_install_panel(self):
        self.official_support_label.setText("프린터 모델의 공식 지원 페이지를 확인합니다.")
        self.official_support_button.setEnabled(False)
        self.official_support_button.setToolTip("")
        self.install_status_label.setText("배포판 패키지 지원 여부를 확인하는 중…")
        self.install_button.setEnabled(False)

    def _install_plan_ready(self, result):
        generation, device, plan = result
        if generation != self.identity_generation or device != self.current_device:
            return
        self.install_plan = plan
        self.official_support_label.setText(
            (plan.support_title + " · " if plan.support_title else "") + plan.support_note
        )
        self.official_support_button.setEnabled(plan.support_url is not None)
        self.official_support_button.setToolTip(plan.support_url or "")
        self.install_status_label.setText(
            f"{plan.package}: {plan.package_status}" if plan.package
            else "자동 설치 후보 없음 · 공식 지원 페이지 확인"
        )
        self.install_status_label.setToolTip(plan.package_note)
        self.install_button.setEnabled(plan.can_install and not self._install_busy)
        self.install_button.setText(
            f"{plan.package} 설치" if plan.package else "확인된 배포판 드라이버 없음"
        )

    def _install_plan_failed(self, generation, device, message):
        if generation != self.identity_generation or device != self.current_device:
            return
        self.install_plan = None
        self.official_support_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.install_status_label.setText("드라이버 설치 경로 확인 실패: " + message[:250])

    def _open_official_support(self):
        plan = self.install_plan
        identity = self.identity_result
        if plan is None or identity is None or not plan.support_url:
            return
        # 열리는 주소를 UI 표시 값이 아닌 공식 주소 허용 목록과 대조합니다.
        _, allowed_url, _ = official_support_for(identity)
        if plan.support_url != allowed_url:
            return
        if not QDesktopServices.openUrl(QUrl(plan.support_url)):
            self.status.setText("브라우저를 열지 못했습니다. URL을 확인해 주세요.")

    def install_driver(self):
        plan = self.install_plan
        identity = self.identity_result
        device = self.current_device
        if (
            self._install_busy or identity is None or device is None
            or plan is None or not plan.can_install
        ):
            return
        command = (
            f"sudo -n apt-get install -y --no-install-recommends {plan.package}"
        )
        if not confirm_action(
            self, title="드라이버 설치 확인",
            summary=f"{plan.package} 패키지를 설치할까요?",
            details=(
                f"프린터 모델: {identity.name}\n"
                f"설치 패키지: {plan.package}\n"
                f"실행 명령: {command}\n\n"
                "설치 위치: Crostini Linux 컨테이너\n"
                "패키지 출처: 현재 설정된 Debian/Ubuntu APT 저장소\n"
                "영향: 패키지 및 의존성이 설치될 수 있습니다.\n"
                "프린터 등록과 실제 인쇄는 하지 않습니다.\n"
                "sudo 권한과 네트워크 연결이 필요합니다."
            ),
            confirm_label="설치",
        ):
            return
        self._install_busy = True
        self.install_button.setEnabled(False)
        self.install_status_label.setText("승인된 배포판 드라이버를 설치 중입니다…")
        generation = self.identity_generation
        worker = Worker(lambda: self.installer.install(identity, plan, approved=True))
        worker.signals.finished.connect(
            lambda message, expected=generation, selected=device:
                self._driver_install_finished(expected, selected, message)
        )
        worker.signals.failed.connect(
            lambda message, expected=generation, selected=device:
                self._driver_install_failed(expected, selected, message)
        )
        self.pool.start(worker)

    def _driver_install_finished(self, generation, device, message):
        self._install_busy = False
        if generation != self.identity_generation or device != self.current_device:
            self.install_button.setEnabled(
                bool(self.install_plan and self.install_plan.can_install)
            )
            return
        self.status.setText(message)
        QMessageBox.information(self, "배포판 드라이버 설치 확인", message)
        self.identify_current()

    def _driver_install_failed(self, generation, device, message):
        self._install_busy = False
        if generation != self.identity_generation or device != self.current_device:
            self.install_button.setEnabled(
                bool(self.install_plan and self.install_plan.can_install)
            )
            return
        self.install_status_label.setText(
            "드라이버 설치 실패: " + message[:400]
        )
        self.install_button.setEnabled(False)
        self.status.setText("설치를 다시 진행하려면 모델 정보를 다시 확인하세요.")
        QMessageBox.warning(self, "드라이버 설치 실패", message)

    def _recommendation_ready(self, result):
        generation, device, recommendation = result
        if generation != self.identity_generation or self.current_device != device:
            return
        self.driver_recommendation = recommendation
        self.model_choice.clear()
        self.model_choice.addItem("설치된 CUPS 모델 선택", None)
        for item in recommendation.installed_matches:
            self.model_choice.addItem(item.description, item.model_id)
        self.recommendation_detail.setText(recommendation.message)
        self.recommendation_detail.setToolTip(recommendation.catalog_status)

        if recommendation.preferred == "everywhere":
            self.recommendation_summary.setText(
                "추천: IPP Everywhere"
            )
        elif recommendation.preferred == "model":
            self.recommendation_summary.setText(
                "추천: 설치된 CUPS 모델"
            )
        elif recommendation.installed_matches:
            self.recommendation_summary.setText(
                "드라이버 후보 있음 · 모델 확인 필요"
            )
        else:
            self.recommendation_summary.setText(
                "드라이버 확인 필요"
            )

        if recommendation.preferred_model:
            index = self.model_choice.findData(recommendation.preferred_model)
            if index >= 0:
                self.model_choice.setCurrentIndex(index)
        if not self._driver_user_edited and recommendation.preferred:
            index = self.driver.findData(recommendation.preferred)
            if index >= 0:
                self.driver.setCurrentIndex(index)
        self._driver_changed()

    def _recommendation_failed(
        self, generation: int, device: DiscoveredPrinter, message: str,
    ):
        if generation != self.identity_generation or self.current_device != device:
            return
        self.driver_recommendation = None
        self.model_choice.clear()
        self.model_choice.addItem("설치된 CUPS 드라이버 조회 실패", None)
        self._driver_changed()
        self.recommendation_summary.setText("드라이버 자동 추천에 실패했습니다.")
        self.recommendation_detail.setText(
            "CUPS 드라이버 목록을 읽지 못했습니다. PPD 파일을 직접 지정할 수 있습니다."
        )

    def _identity_failed(self, generation: int, device: DiscoveredPrinter, message: str):
        if generation == self.identity_generation and self.current_device == device:
            self._identity_ready(
                (generation, device, unknown_identity(device, "모델 조회 오류가 발생했습니다."))
            )

    def apply_manual(self):
        try:
            device = manual_printer(self.ip_input.text(), protocol=self.protocol.currentData())
        except PrinterRegistrationError as exc:
            self._error(str(exc))
            return
        self._select_device(device)

    def _mark_driver_user_edited(self, _index: int):
        self._driver_user_edited = True

    def _driver_changed(self, _index: int = 0):
        selected = self.driver.currentData()
        self.ppd_path.setEnabled(selected == "ppd")
        self.model_choice.setEnabled(
            selected == "model" and self.model_choice.count() > 1
        )

    def choose_ppd(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "제조사 PPD 선택", "", "CUPS PPD (*.ppd)"
        )
        if path:
            self._driver_user_edited = True
            self.ppd_path.setText(path)
            self.driver.setCurrentIndex(self.driver.findData("ppd"))

    def probe(self):
        if not self.current_device:
            self._error("프린터를 먼저 선택해 주세요.")
            return
        self.status.setText("프린터 연결 상태를 확인 중입니다…")
        self._background(
            lambda: self.service.probe(self.current_device),
            self.status.setText,
        )

    def register(self):
        if self._register_busy:
            return
        if not self.current_device:
            self._error("프린터를 먼저 선택해 주세요.")
            return
        registration = Registration(
            self.queue_name.text().strip(),
            self.current_device.uri,
            self.driver.currentData(),
            self.ppd_path.text().strip() or None,
            self.model_choice.currentData() if self.driver.currentData() == "model" else None,
        )
        try:
            validate_registration(registration)
        except PrinterRegistrationError as exc:
            self._error(str(exc))
            return
        driver_name = {
            "everywhere": "IPP Everywhere",
            "ppd": "PPD",
            "model": "설치된 CUPS 모델",
        }.get(registration.driver, "미확인")
        driver_warning = ""
        if registration.driver == "everywhere" and (
            self.identity_result is None or self.identity_result.driverless == "unknown"
        ):
            driver_warning = (
                "주의: IPP Everywhere 지원이 확인되지 않았습니다. "
                "이 등록 방식은 프린터가 지원하는 경우에만 작동합니다.\n\n"
            )
        elif registration.driver == "everywhere" and self.identity_result.driverless == "candidate":
            driver_warning = (
                "안내: IPP 2.x / PWG Raster를 보고했지만 "
                "실제 드라이버리스 인쇄 성공은 검증되지 않았습니다.\n\n"
            )
        details = (
            f"프린터 이름: {registration.name}\n"
            f"연결 URI: {registration.uri}\n"
            f"모델 정보: {self.identity_result.name if self.identity_result else '미확인'}\n"
            f"드라이버: {driver_name}\n"
            f"CUPS 모델 ID: {registration.driver_model or '-'}\n"
            f"PPD 파일: {registration.ppd_path or '-'}\n\n"
            f"{driver_warning}"
            "실행 작업: Crostini CUPS에 새 로컬 프린터 큐 등록\n"
            f"실행 명령: {shlex.join(registration_command(registration))}\n"
            "기존 프린터 큐를 덮어쓰거나 기본 프린터를 변경하지 않습니다.\n"
            "프린터로 실제 문서를 보내지는 않습니다."
        )
        if not confirm_action(
            self, title="프린터 등록 확인",
            summary=f"{registration.name} 프린터를 등록할까요?",
            details=details, confirm_label="등록",
        ):
            return
        self._register_busy = True
        self.register_button.setEnabled(False)
        self.status.setText("CUPS 프린터를 등록 중입니다…")
        try:
            self._background(
                lambda: self.service.register(registration, approved=True),
                self._registered,
                self._registration_failed,
            )
        except Exception as exc:
            self._registration_failed(str(exc))

    def _registered(self, result):
        self._register_busy = False
        self.register_button.setEnabled(True)
        self.status.setText(result)
        QMessageBox.information(self, "등록 완료", result)
        if self.on_registered:
            self.on_registered()
