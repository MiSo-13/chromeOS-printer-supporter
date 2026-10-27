"""문서 인쇄·대기열·프린터 상태·프린터 추가 화면 구성.

CUPS 작업 및 백그라운드 처리 로직은 MainWindow에 둡니다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QProgressBar, QPushButton, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .document_drop import DocumentDropArea
from .preview_widget import DocumentPreview
from .setup_ui import PrinterSetupWidget


def build_workspace_pages(self, add_page):
    print_page = QWidget()
    print_layout = QHBoxLayout(print_page)
    print_layout.setSpacing(20)
    print_layout.setContentsMargins(4, 6, 4, 6)
    document_panel = DocumentDropArea()
    document_panel.fileDropped.connect(self._set_document)
    document_layout = QVBoxLayout(document_panel)
    document_layout.setSpacing(12)
    settings_panel = QFrame()
    settings_panel.setObjectName("settingsPanel")
    settings_panel.setFixedWidth(330)
    settings_layout = QVBoxLayout(settings_panel)
    settings_layout.setContentsMargins(16, 22, 16, 18)
    settings_layout.setSpacing(16)
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
    drop_hint = QLabel("파일을 이 영역에 끌어놓거나 Ctrl+V로 파일/경로 붙여넣기")
    drop_hint.setObjectName("dropHint")
    drop_hint.setWordWrap(True)
    document_layout.addWidget(drop_hint)
    preview_group = QGroupBox("문서 미리보기")
    preview_layout = QVBoxLayout(preview_group)
    preview_layout.setSpacing(12)
    self.preview_view = DocumentPreview()
    self.preview_view.setMinimumHeight(280)
    preview_layout.addWidget(self.preview_view, 1)

    navigation = QHBoxLayout()
    navigation.setSpacing(8)
    self.prev_page = QPushButton("이전")
    self.prev_page.clicked.connect(lambda: self._show_preview_page(self.preview_index - 1))
    self.next_page = QPushButton("다음")
    self.next_page.clicked.connect(lambda: self._show_preview_page(self.preview_index + 1))
    self.page_indicator = QLabel("—")
    self.page_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.page_indicator.setMinimumWidth(52)
    navigation.addWidget(self.prev_page)
    navigation.addWidget(self.page_indicator)
    navigation.addWidget(self.next_page)
    navigation.addStretch()
    self.zoom_box = QComboBox()
    self.zoom_box.setAccessibleName("미리보기 확대/축소")
    self.zoom_box.addItem("화면 맞춤", "fit")
    for label, value in (("75%", 0.75), ("100%", 1.0), ("125%", 1.25),
                         ("150%", 1.5), ("200%", 2.0)):
        self.zoom_box.addItem(label, value)
    self.zoom_box.currentIndexChanged.connect(self._change_preview_zoom)
    navigation.addWidget(self.zoom_box)
    preview_layout.addLayout(navigation)
    self.preview_note = QLabel("미리보기와 실제 출력은 프린터 설정에 따라 다를 수 있습니다.")
    self.preview_note.setObjectName("previewNote")
    self.preview_note.setWordWrap(True)
    preview_layout.addWidget(self.preview_note)
    self.preview_retry_button = QPushButton("미리보기 다시 시도")
    self.preview_retry_button.setVisible(False)
    self.preview_retry_button.clicked.connect(self._load_preview)
    preview_layout.addWidget(self.preview_retry_button)
    document_layout.addWidget(preview_group, 1)
    self.preview_index = 0
    self.preview_count = 0
    self._set_preview_navigation(False)
    range_row = QHBoxLayout()
    range_row.setSpacing(12)
    range_row.addWidget(QLabel("페이지"))
    self.page_range = QLineEdit()
    self.page_range.setPlaceholderText("전체 페이지 (예: 1-3, 5)")
    range_row.addWidget(self.page_range, 1)
    settings_layout.addLayout(range_row)
    options = QHBoxLayout()
    options.setSpacing(12)
    options.addWidget(QLabel("인쇄 매수"))
    self.copies = QSpinBox()
    self.copies.setRange(1, 99)
    options.addWidget(self.copies)
    options.addStretch()
    settings_layout.addLayout(options)

    # 지원하지 않거나 알려지지 않은 옵션은 프린터 기본값을 사용합니다.
    from PyQt6.QtWidgets import QFormLayout
    option_form = QFormLayout()
    option_form.setHorizontalSpacing(16)
    option_form.setVerticalSpacing(12)
    # CUPS 표준 작업 옵션: lpoptions -l에 나타나지 않아도 사용할 수 있습니다.
    self.orientation = QComboBox()
    self.orientation.setAccessibleName("인쇄 방향")
    self.orientation.addItem("자동 (문서 방향)", None)
    self.orientation.addItem("세로", "3")
    self.orientation.addItem("가로", "4")
    self.orientation.currentIndexChanged.connect(self._change_preview_orientation)
    option_form.addRow("방향", self.orientation)
    # 문서 크기 정보가 있는 경우 CUPS가 현재 용지에 맞춰 크기를 조정합니다.
    self.fit_to_page = QComboBox()
    self.fit_to_page.setAccessibleName("인쇄 크기 맞춤")
    self.fit_to_page.addItem("원본 크기 (기본값)", None)
    self.fit_to_page.addItem("용지에 맞추기", "true")
    option_form.addRow("크기 맞춤", self.fit_to_page)
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
    print_actions.setSpacing(12)
    self.print_button = QPushButton("인쇄")
    self.print_button.setObjectName("primaryButton")
    self.print_button.clicked.connect(self.print_selected)
    print_actions.addWidget(self.print_button)
    self.test_page_button = QPushButton("테스트 페이지 인쇄")
    self.test_page_button.clicked.connect(self.print_test_page)
    print_actions.addWidget(self.test_page_button)
    settings_layout.addLayout(print_actions)
    self.print_progress = QProgressBar()
    self.print_progress.setObjectName("printProgress")
    self.print_progress.setRange(0, 0)
    self.print_progress.setTextVisible(False)
    self.print_progress.setVisible(False)
    settings_layout.addWidget(self.print_progress)
    self.print_feedback = QLabel("문서와 프린터를 선택한 뒤 인쇄해 주세요.")
    self.print_feedback.setObjectName("printFeedback")
    self.print_feedback.setWordWrap(True)
    settings_layout.addWidget(self.print_feedback)

    settings_layout.addStretch()
    add_page(print_page, "문서 인쇄")

    queue_page = QWidget()
    queue_layout = QVBoxLayout(queue_page)
    queue_tabs = QTabWidget()
    queue_tabs.setObjectName("queueTabs")
    queue_tabs.tabBar().setObjectName("queueTabBar")
    queue_tabs.tabBar().setDocumentMode(False)
    queue_tabs.tabBar().setExpanding(False)
    queue_tabs.setAccessibleName("인쇄 대기열 작업 종류")
    queue_layout.addWidget(queue_tabs)
    active_page = QWidget()
    active_layout = QVBoxLayout(active_page)
    active_layout.addWidget(QLabel("대기 중이거나 인쇄 중인 작업"))
    self.job_list = QListWidget()
    self.job_list.currentItemChanged.connect(self._update_queue_actions)
    active_layout.addWidget(self.job_list)
    actions = QHBoxLayout()
    actions.setSpacing(12)
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
    self.diagnosis_label = QLabel("프린터를 선택하면 상태를 확인합니다.")
    self.diagnosis_label.setObjectName("diagnosisSummary")
    self.diagnosis_label.setWordWrap(True)
    state_layout.addWidget(self.diagnosis_label)
    self.diagnosis_advice = QLabel("")
    self.diagnosis_advice.setWordWrap(True)
    state_layout.addWidget(self.diagnosis_advice)
    state_layout.addWidget(QLabel("CUPS 상세 정보"))
    self.state_text = QTextEdit()
    self.state_text.setReadOnly(True)
    state_layout.addWidget(self.state_text)
    
    add_page(state_page, "프린터 상태")

    add_page(PrinterSetupWidget(on_registered=self.refresh_all), "프린터 추가")
