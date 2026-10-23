"""ChromeOS Printer Supporter 데스크톱 UI 공통 스타일."""

APP_STYLESHEET = """
QWidget#documentPreview, QScrollArea#previewScroll { background: #edf1f5; border: none; border-radius: 6px; }
QLabel#previewPlaceholder { background: #edf1f5; color: #56677a; padding: 16px; border-radius: 6px; }
QLabel#previewImage { background: #ffffff; }
QPlainTextEdit#previewText { background: #ffffff; color: #25313c; border: 1px solid #dce2e8; border-radius: 6px; padding: 12px; }

QLabel#focusSupportSummary { background: #e8f0fa; color: #174c85; border: 1px solid #bfcee1; border-radius: 5px; padding: 9px 11px; font-weight: 700; }
QLabel#focusSupportDetail { color: #394c60; padding: 4px 2px; }
QTabWidget#queueTabs::pane { background: #ffffff; border: 1px solid #bfcbd9; border-top: 2px solid #8da9c9; border-radius: 6px; }
QTabBar#queueTabBar::tab { background: #e3e9f1; color: #3a4f67; border: 1px solid #b8c7d7; border-bottom: 3px solid #afc0d0; border-radius: 7px 7px 0 0; margin-right: 8px; min-width: 136px; padding: 12px 18px; font-weight: 500; }
QTabBar#queueTabBar::tab:selected { background: #d9e9ff; color: #124f91; border-color: #7da9d9; border-bottom: 3px solid #1673d1; font-weight: 700; }
QTabBar#queueTabBar::tab:hover:!selected { background: #f0f5fb; color: #174c85; border-color: #7da9d9; }
QTabBar#queueTabBar::tab:focus { border-color: #1673d1; }

QLabel#dropHint { color: #556477; font-size: 12px; padding: 6px 2px; }

QLabel#diagnosisSummary { font-size: 15px; font-weight: 600; padding: 12px; background: #e8f0f9; border-radius: 7px; }
QLabel#diagnosisSummary[severity="warning"] { color: #854b13; background: #fff0d9; }

QLabel#appTitle { font-size: 15px; font-weight: 600; color: #35465a; padding: 2px 0; }
QLabel#appCredit { color: #718092; font-size: 11px; padding: 2px 4px; }
QGroupBox { padding-top: 18px; }
QComboBox, QSpinBox, QLineEdit { min-height: 24px; }
QPushButton { min-height: 24px; }
QListWidget::item { padding: 6px 8px; }

QLabel#sidebarCaption { color: #556477; font-size: 12px; }
QComboBox#themeSelector { min-width: 80px; }
QComboBox QAbstractItemView { background: #ffffff; color: #25313c; selection-background-color: #d4e2f4; selection-color: #174c85; }
QPushButton:pressed { background: #dbe8f6; color: #174c85; }
QPushButton#primaryButton:hover { background: #174c85; color: #ffffff; }

QLabel#previewCanvas { background: #f0f2f5; color: #64717e; border-radius: 6px; }
QPushButton#primaryButton { background: #225e9e; color: white; border: none; font-weight: 600; padding: 10px 22px; }

QMainWindow, QWidget { background: #f5f6f8; color: #25313c; font-size: 13px; }
QMainWindow { background: #f5f6f8; }
QLabel { background: transparent; }
QFrame#sidebar { background: #e9edf2; border-right: 1px solid #d8dfe7; border-radius: 8px; }
QFrame#settingsPanel { background: #ffffff; border: 1px solid #dce2e8; border-radius: 9px; padding: 12px; }
QPushButton#navButton { text-align: left; border: none; background: transparent; color: #425163; padding: 13px 15px; border-radius: 6px; font-weight: 500; }
QPushButton#navButton:hover { background: #dfe6ef; }
QPushButton#navButton:checked { background: #d4e2f4; color: #174c85; font-weight: 700; }
QPushButton { background: white; border: 1px solid #cbd4df; border-radius: 6px; padding: 8px 12px; }
QPushButton:hover { border-color: #467cb8; }
QPushButton:disabled { color: #a0a8b1; background: #f0f2f4; }
QComboBox, QSpinBox, QLineEdit { background: #fff; border: 1px solid #cbd4df; border-radius: 5px; padding: 7px; min-height: 20px; }
QComboBox:focus, QLineEdit:focus { border-color: #316da8; }
QListWidget, QTextEdit { background: #fff; border: 1px solid #dce2e8; border-radius: 7px; }
QTabWidget::pane { border: 1px solid #dce2e8; background: #fff; border-radius: 7px; }
QTabBar::tab { background: #e9edf2; padding: 10px 15px; }
QTabBar::tab:selected { background: #fff; font-weight: 600; }
QGroupBox { background: #fff; border: 1px solid #dce2e8; border-radius: 8px; margin-top: 12px; padding: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
"""

DARK_STYLESHEET = """
QWidget#documentPreview, QScrollArea#previewScroll { background: #303843; border: none; border-radius: 6px; }
QLabel#previewPlaceholder { background: #303843; color: #c0cad5; padding: 16px; border-radius: 6px; }
QLabel#previewImage { background: #ffffff; }
QPlainTextEdit#previewText { background: #242b34; color: #e1e6ed; border: 1px solid #3b4551; border-radius: 6px; padding: 12px; }

QLabel#focusSupportSummary { background: #263d57; color: #c4e2ff; border: 1px solid #426789; border-radius: 5px; padding: 9px 11px; font-weight: 700; }
QLabel#focusSupportDetail { color: #d2dde9; padding: 4px 2px; }
QTabWidget#queueTabs::pane { background: #242b34; border: 1px solid #4c596b; border-top: 2px solid #65819e; border-radius: 6px; }
QTabBar#queueTabBar::tab { background: #313b48; color: #d1ddeb; border: 1px solid #586879; border-bottom: 3px solid #536477; border-radius: 7px 7px 0 0; margin-right: 8px; min-width: 136px; padding: 12px 18px; font-weight: 500; }
QTabBar#queueTabBar::tab:selected { background: #244e79; color: #ffffff; border-color: #6ea0d3; border-bottom: 3px solid #8cc9ff; font-weight: 700; }
QTabBar#queueTabBar::tab:hover:!selected { background: #405367; color: #ffffff; border-color: #86b5e3; }
QTabBar#queueTabBar::tab:focus { border-color: #9cd4ff; }

QLabel#dropHint { color: #b8c4d1; font-size: 12px; padding: 6px 2px; }

QLabel#diagnosisSummary { font-size: 15px; font-weight: 600; padding: 12px; color: #dbeafe; background: #263d57; border-radius: 7px; }
QLabel#diagnosisSummary[severity="warning"] { color: #ffe2ae; background: #503d25; }

QLabel#appTitle { font-size: 15px; font-weight: 600; color: #dce5ef; padding: 2px 0; }
QLabel#appCredit { color: #a6b3c2; font-size: 11px; padding: 2px 4px; }
QGroupBox { padding-top: 18px; }
QComboBox, QSpinBox, QLineEdit { min-height: 24px; }
QPushButton { min-height: 24px; }
QListWidget::item { padding: 6px 8px; }

QLabel#sidebarCaption { color: #b8c4d1; font-size: 12px; }
QComboBox#themeSelector { min-width: 80px; }
QComboBox QAbstractItemView { background: #242b34; color: #f1f5f9; selection-background-color: #365778; selection-color: #ffffff; }
QPushButton:pressed { background: #365778; color: #ffffff; }
QPushButton#primaryButton:hover { background: #4893d3; color: #ffffff; }

QLabel#previewCanvas { background: #303843; color: #c0cad5; border-radius: 6px; }
QPushButton#primaryButton { background: #357bbd; color: white; border: none; font-weight: 600; padding: 10px 22px; }

QMainWindow, QWidget { background: #181c22; color: #e1e6ed; font-size: 13px; }
QMainWindow { background: #181c22; }
QLabel { background: transparent; }
QFrame#sidebar { background: #242b34; border-right: 1px solid #3b4551; border-radius: 8px; }
QFrame#settingsPanel { background: #242b34; border: 1px solid #3b4551; border-radius: 9px; padding: 12px; }
QPushButton#navButton { text-align: left; border: none; background: transparent; color: #d3dce7; padding: 13px 15px; border-radius: 6px; font-weight: 500; }
QPushButton#navButton:hover { background: #333f4e; color: #ffffff; }
QPushButton#navButton:checked { background: #263d57; color: #b8d9ff; font-weight: 700; }
QPushButton { background: #303a46; color: #f1f5f9; border: 1px solid #4b5868; border-radius: 6px; padding: 8px 12px; }
QPushButton:hover { background: #3b4a5b; color: #ffffff; border-color: #8bbcf2; }
QPushButton:disabled { color: #a4afbd; background: #29313b; border-color: #3c4652; }
QComboBox, QSpinBox, QLineEdit { color: #f1f5f9; background: #242b34; border: 1px solid #4b5868; border-radius: 5px; padding: 7px; min-height: 20px; }
QComboBox:focus, QLineEdit:focus { border-color: #8bbcf2; }
QListWidget, QTextEdit { background: #242b34; border: 1px solid #3b4551; border-radius: 7px; }
QTabWidget::pane { border: 1px solid #3b4551; background: #242b34; border-radius: 7px; }
QTabBar::tab { background: #242b34; padding: 10px 15px; }
QTabBar::tab:selected { background: #242b34; font-weight: 600; }
QGroupBox { background: #242b34; border: 1px solid #3b4551; border-radius: 8px; margin-top: 12px; padding: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
"""

def stylesheet_for(theme: str) -> str:
    return DARK_STYLESHEET if theme == "dark" else APP_STYLESHEET
