"""기본 메뉴바: 파일 작업과 화면 설정."""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import QMainWindow


def build_menus(
    window: QMainWindow,
    *,
    theme: str,
    open_file: Callable[[], None],
    refresh: Callable[[], None],
    change_theme: Callable[[str], None],
):
    bar = window.menuBar()
    # Crostini를 포함해 앱 창 위쪽에 항상 메뉴를 표시합니다.
    bar.setNativeMenuBar(False)

    file_menu = bar.addMenu("파일")
    file_menu.setObjectName("fileMenu")
    open_action = file_menu.addAction("문서 열기…")
    open_action.setShortcut("Ctrl+O")
    open_action.triggered.connect(open_file)
    refresh_action = file_menu.addAction("새로고침")
    refresh_action.setShortcut("Ctrl+R")
    refresh_action.triggered.connect(refresh)
    file_menu.addSeparator()
    quit_action = file_menu.addAction("종료")
    quit_action.setShortcut("Ctrl+Q")
    quit_action.triggered.connect(window.close)

    settings_menu = bar.addMenu("설정")
    settings_menu.setObjectName("settingsMenu")
    theme_menu = settings_menu.addMenu("화면 테마")
    theme_menu.setObjectName("themeMenu")
    theme_group = QActionGroup(window)
    theme_group.setExclusive(True)
    theme_actions = {}
    for value, label in (("light", "라이트"), ("dark", "다크")):
        action = theme_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(value == theme)
        action.triggered.connect(
            lambda checked=False, selected=value: change_theme(selected)
        )
        theme_group.addAction(action)
        theme_actions[value] = action
    return theme_actions
