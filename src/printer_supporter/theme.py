"""PrintHub 데스크톱 UI 공통 스타일."""

APP_STYLESHEET = """
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
