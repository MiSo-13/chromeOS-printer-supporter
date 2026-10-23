"""CUPS 네트워크 프린터 검색과 등록 UI."""

from __future__ import annotations

import re

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .discovery import (
    DiscoveredPrinter, DiscoveryService, PrinterRegistrationError,
    Registration, manual_printer,
)
from .identification import PrinterIdentity, identify_printer, unknown_identity
from .driver_recommendation import DriverAdvisor, DriverRecommendation


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.finished.emit(self.callback())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class PrinterSetupWidget(QWidget):
    def __init__(self, *, service: DiscoveryService | None = None, on_registered=None,
                 identifier=None, advisor: DriverAdvisor | None = None):
        super().__init__()
        self.service = service or DiscoveryService()
        self.on_registered = on_registered
        self.identifier = identifier or identify_printer
        self.advisor = advisor or DriverAdvisor()
        self.pool = QThreadPool.globalInstance()
        self.current_device: DiscoveredPrinter | None = None
        self.identity_result: PrinterIdentity | None = None
        self.driver_recommendation: DriverRecommendation | None = None
        self.identity_generation = 0
        self._driver_user_edited = False
        self._queue_name_user_edited = False

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

        layout.addWidget(QLabel("검색된 프린터 (CUPS / mDNS)"))
        scan_row = QHBoxLayout()
        scan_row.setSpacing(12)
        self.scan_button = QPushButton("네트워크 프린터 검색")
        self.scan_button.clicked.connect(self.search)
        scan_row.addWidget(self.scan_button)
        scan_row.addStretch()
        layout.addLayout(scan_row)

        self.devices = QListWidget()
        self.devices.currentItemChanged.connect(self._select_discovered)
        self.devices.setMinimumHeight(100)
        layout.addWidget(self.devices, 1)

        details = QGroupBox("프린터 모델 자동 식별")
        details_layout = QVBoxLayout(details)
        details_layout.setSpacing(6)
        self.identity_summary = QLabel("프린터 선택 후 제조사·모델을 확인합니다.")
        self.identity_summary.setWordWrap(True)
        details_layout.addWidget(self.identity_summary)
        self.identity_evidence = QLabel("정보 출처: 미확인")
        self.identity_evidence.setWordWrap(True)
        details_layout.addWidget(self.identity_evidence)
        self.identity_advice = QLabel("IPP 속성 확인은 실제 인쇄 없이 조회합니다.")
        self.identity_advice.setWordWrap(True)
        details_layout.addWidget(self.identity_advice)
        self.identify_button = QPushButton("모델 정보 다시 확인")
        self.identify_button.setEnabled(False)
        self.identify_button.clicked.connect(self.identify_current)
        details_layout.addWidget(self.identify_button)
        layout.addWidget(details)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("예: 192.168.6.147")
        form.addRow("IP 직접 입력", self.ip_input)
        self.protocol = QComboBox()
        self.protocol.addItem("IPP (631) · 지원 여부 자동 확인", "ipp")
        self.protocol.addItem("Socket / JetDirect (9100)", "socket")
        form.addRow("연결 방식", self.protocol)
        apply_ip = QPushButton("IP 주소 적용")
        apply_ip.clicked.connect(self.apply_manual)
        form.addRow("", apply_ip)

        self.uri = QLineEdit()
        self.uri.setReadOnly(True)
        form.addRow("연결 URI", self.uri)
        self.queue_name = QLineEdit()
        self.queue_name.setPlaceholderText("예: Samsung_SL_M2030W")
        form.addRow("CUPS 큐 이름", self.queue_name)
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
        form.addRow("자동 추천", self.recommendation_summary)
        self.recommendation_detail = QLabel(
            "드라이버 설치 없이 로컬 CUPS 목록을 검사합니다."
        )
        self.recommendation_detail.setWordWrap(True)
        form.addRow("", self.recommendation_detail)
        self.ppd_path = QLineEdit()
        self.ppd_path.setPlaceholderText("삼성 ULD 등 설치된 PPD 파일 경로")
        ppd_row = QHBoxLayout()
        ppd_row.setSpacing(12)
        ppd_row.addWidget(self.ppd_path)
        ppd_button = QPushButton("찾아보기")
        ppd_button.clicked.connect(self.choose_ppd)
        ppd_row.addWidget(ppd_button)
        form.addRow("PPD 파일", ppd_row)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.probe_button = QPushButton("연결 확인")
        self.probe_button.clicked.connect(self.probe)
        actions.addWidget(self.probe_button)
        self.register_button = QPushButton("이 프린터 등록")
        self.register_button.clicked.connect(self.register)
        actions.addWidget(self.register_button)
        layout.addLayout(actions)
        self.status = QLabel("프린터를 검색하거나 IP 주소를 입력해 주세요.")
        layout.addWidget(self.status)
        note = QLabel("프린터 자체의 설정은 바꾸지 않습니다. 기존 CUPS 큐도 덮어쓰지 않습니다.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self._driver_changed()
        # lpinfo -v는 일부 Crostini CUPS에서 관리자 권한이 필요합니다.
        # 앱 시작 시 자동 실행하지 않고 사용자가 검색 버튼을 누를 때만 실행합니다.

    def _background(self, operation, callback):
        worker = Worker(operation)
        worker.signals.finished.connect(callback)
        worker.signals.failed.connect(self._error)
        self.pool.start(worker)

    def _error(self, message: str):
        self.status.setText("오류: " + message)
        self.scan_button.setEnabled(True)
        self.register_button.setEnabled(True)
        QMessageBox.warning(self, "프린터 설정 오류", message)

    def _search_failed(self, message: str):
        self.scan_button.setEnabled(True)
        if "forbidden" in message.lower() or "not authorized" in message.lower():
            self.status.setText(
                "CUPS가 네트워크 검색(lpinfo)을 거부했습니다. "
                "IP 주소 직접 입력이나 기존 등록 프린터 사용은 가능합니다."
            )
        else:
            self.status.setText(f"네트워크 검색 실패: {message} · IP 직접 입력은 가능합니다.")

    def search(self):
        self.scan_button.setEnabled(False)
        self.status.setText("CUPS에서 네트워크 프린터를 검색 중입니다…")
        worker = Worker(self.service.discover)
        worker.signals.finished.connect(self._populate)
        worker.signals.failed.connect(self._search_failed)
        self.pool.start(worker)

    def _populate(self, devices):
        self.scan_button.setEnabled(True)
        self.devices.clear()
        for device in devices:
            item = QListWidgetItem(f"{device.name}  ·  {device.scheme}")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.devices.addItem(item)
        self.status.setText(f"검색 결과: {len(devices)}개 · 없으면 IP 주소를 직접 입력하세요.")

    def _select_discovered(self, current, previous):
        if current:
            self._select_device(current.data(Qt.ItemDataRole.UserRole))

    def _queue_name_edited(self, _value: str):
        self._queue_name_user_edited = True

    def _select_device(self, device: DiscoveredPrinter):
        self.current_device = device
        self._driver_user_edited = False
        self.driver_recommendation = None
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
        self.model_choice.clear()
        self.model_choice.addItem("드라이버 모델 확인 중", None)
        self._driver_changed()
        self.recommendation_summary.setText("드라이버 목록을 확인할 준비 중…")
        self.recommendation_detail.setText("IPP 속성 조회 후 로컬 CUPS 목록을 비교합니다.")
        self.identify_button.setEnabled(False)
        self.identity_summary.setText("모델 정보를 확인하는 중…")
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
            f"모델: {identity.name} · 제조사: {identity.manufacturer or '미확인'}"
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
        self.recommendation_summary.setText("설치된 드라이버와 비교 중…")
        worker = Worker(lambda: (
            generation, device, self.advisor.advise(device, identity)
        ))
        worker.signals.finished.connect(self._recommendation_ready)
        worker.signals.failed.connect(
            lambda message, expected=generation, selected=device:
                self._recommendation_failed(expected, selected, message)
        )
        self.pool.start(worker)

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
                "추천: IPP Everywhere · " + recommendation.catalog_status
            )
        elif recommendation.preferred == "model":
            self.recommendation_summary.setText(
                "추천: 설치된 CUPS 모델 · " + recommendation.catalog_status
            )
        elif recommendation.installed_matches:
            self.recommendation_summary.setText(
                "확인 필요: 설치된 드라이버의 모델명과 검색명이 일치하지만 미검증입니다."
            )
        else:
            self.recommendation_summary.setText(
                "호환 드라이버 미확인 · " + recommendation.catalog_status
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
        summary = (
            f"프린터: {registration.name}\n"
            f"연결: {registration.uri}\n"
            f"식별 모델: {self.identity_result.name if self.identity_result else '미확인'}\n"
            f"드라이버: {driver_name}\n"
            f"CUPS 모델 ID: {registration.driver_model or '해당 없음'}\n\n"
            + driver_warning
            + "내 Crostini CUPS에 새 프린터 큐를 등록할까요?\n"
            "다른 PC와 프린터 자체의 설정은 변경되지 않습니다."
        )
        answer = QMessageBox.question(
            self, "프린터 등록 확인", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.register_button.setEnabled(False)
        self.status.setText("CUPS 프린터를 등록 중입니다…")
        self._background(
            lambda: self.service.register(registration, approved=True),
            self._registered,
        )

    def _registered(self, result):
        self.register_button.setEnabled(True)
        self.status.setText(result)
        QMessageBox.information(self, "등록 완료", result)
        if self.on_registered:
            self.on_registered()
