"""CUPS 네트워크 프린터 검색과 등록 UI."""

from __future__ import annotations

import re

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .discovery import (
    DiscoveredPrinter, DiscoveryService, PrinterRegistrationError,
    Registration, manual_printer,
)


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
    def __init__(self, *, service: DiscoveryService | None = None, on_registered=None):
        super().__init__()
        self.service = service or DiscoveryService()
        self.on_registered = on_registered
        self.pool = QThreadPool.globalInstance()
        self.current_device: DiscoveredPrinter | None = None
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("검색된 프린터 (CUPS / mDNS)"))
        scan_row = QHBoxLayout()
        self.scan_button = QPushButton("네트워크 프린터 검색")
        self.scan_button.clicked.connect(self.search)
        scan_row.addWidget(self.scan_button)
        scan_row.addStretch()
        layout.addLayout(scan_row)

        self.devices = QListWidget()
        self.devices.currentItemChanged.connect(self._select_discovered)
        layout.addWidget(self.devices)

        form = QFormLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("예: 192.168.6.147")
        form.addRow("IP 직접 입력", self.ip_input)
        self.protocol = QComboBox()
        self.protocol.addItem("IPP Everywhere (631)", "ipp")
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
        self.driver = QComboBox()
        self.driver.addItem("IPP Everywhere (드라이버리스)", "everywhere")
        self.driver.addItem("설치된 제조사 PPD 파일", "ppd")
        self.driver.currentIndexChanged.connect(self._driver_changed)
        form.addRow("드라이버", self.driver)
        self.ppd_path = QLineEdit()
        self.ppd_path.setPlaceholderText("삼성 ULD 등 설치된 PPD 파일 경로")
        ppd_row = QHBoxLayout()
        ppd_row.addWidget(self.ppd_path)
        ppd_button = QPushButton("찾아보기")
        ppd_button.clicked.connect(self.choose_ppd)
        ppd_row.addWidget(ppd_button)
        form.addRow("PPD 파일", ppd_row)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.probe_button = QPushButton("연결 확인")
        self.probe_button.clicked.connect(self.probe)
        actions.addWidget(self.probe_button)
        self.register_button = QPushButton("이 프린터 등록")
        self.register_button.clicked.connect(self.register)
        actions.addWidget(self.register_button)
        layout.addLayout(actions)
        self.status = QLabel("프린터를 검색하거나 IP 주소를 입력해 주세요.")
        layout.addWidget(self.status)
        layout.addWidget(QLabel(
            "프린터 자체의 설정은 바꾸지 않습니다. 기존 CUPS 큐도 덮어쓰지 않습니다."
        ))
        self._driver_changed()
        self.search()

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

    def search(self):
        self.scan_button.setEnabled(False)
        self.status.setText("CUPS에서 네트워크 프린터를 검색 중입니다…")
        self._background(self.service.discover, self._populate)

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

    def _select_device(self, device: DiscoveredPrinter):
        self.current_device = device
        self.uri.setText(device.uri)
        if not self.queue_name.text().strip():
            slug = re.sub(r"[^A-Za-z0-9_.-]", "_", device.name)
            slug = "Printer_" + slug if not slug or not slug[0].isalpha() else slug
            self.queue_name.setText(slug[:64])
        index = self.driver.findData("ppd" if device.scheme == "socket" else "everywhere")
        self.driver.setCurrentIndex(index)
        self.status.setText("연결 방식과 드라이버를 확인한 뒤 등록해 주세요.")

    def apply_manual(self):
        try:
            device = manual_printer(self.ip_input.text(), protocol=self.protocol.currentData())
        except PrinterRegistrationError as exc:
            self._error(str(exc))
            return
        self._select_device(device)

    def _driver_changed(self):
        enabled = self.driver.currentData() == "ppd"
        self.ppd_path.setEnabled(enabled)

    def choose_ppd(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "제조사 PPD 선택", "", "CUPS PPD (*.ppd)"
        )
        if path:
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
        )
        driver_name = "IPP Everywhere" if registration.driver == "everywhere" else "PPD"
        summary = (
            f"프린터: {registration.name}\n"
            f"연결: {registration.uri}\n"
            f"드라이버: {driver_name}\n\n"
            "내 Crostini CUPS에 새 프린터 큐를 등록할까요?\n"
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
