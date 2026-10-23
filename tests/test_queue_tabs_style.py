"""활성/비활성 탭의 경계·강조를 Qt 오프스크린 렌더링으로 검증합니다."""
import os
import subprocess
import sys
import textwrap

from printer_supporter.theme import stylesheet_for


def test_tab_styles_have_clear_light_and_dark_selection():
    for theme in ("light", "dark"):
        css = stylesheet_for(theme)
        assert "QTabBar#queueTabBar::tab {" in css
        assert "QTabBar#queueTabBar::tab:selected" in css
        assert "QTabBar#queueTabBar::tab:hover:!selected" in css
        assert "margin-right: 8px" in css
        assert "border-bottom: 3px solid" in css


def test_tab_bar_pixel_colors_change_on_selection(tmp_path):
    script = textwrap.dedent("""
        import sys
        from PyQt6.QtWidgets import (
            QApplication, QLabel, QTabWidget, QVBoxLayout, QWidget,
        )
        from printer_supporter.theme import stylesheet_for

        app = QApplication([])
        for theme in ("light", "dark"):
            root = QWidget()
            root.resize(540, 260)
            root.setStyleSheet(stylesheet_for(theme))
            layout = QVBoxLayout(root)
            tabs = QTabWidget()
            tabs.setObjectName("queueTabs")
            bar = tabs.tabBar()
            bar.setObjectName("queueTabBar")
            bar.setDocumentMode(False)
            bar.setExpanding(False)
            tabs.addTab(QLabel("대기 중이거나 인쇄 중인 작업"), "진행 중인 작업")
            tabs.addTab(QLabel("최근 처리된 작업"), "처리 종료 이력")
            layout.addWidget(tabs)
            root.show()
            app.processEvents()

            def sample(index):
                rect = bar.tabRect(index)
                img = bar.grab().toImage()
                x = rect.center().x()
                y = rect.bottom() - 2
                return img.pixelColor(x, y).getRgb()[:3]

            tabs.setCurrentIndex(0)
            app.processEvents()
            first_active = sample(0)
            second_inactive = sample(1)
            assert first_active != second_inactive, (
                theme, first_active, second_inactive
            )
            tabs.setCurrentIndex(1)
            app.processEvents()
            first_inactive = sample(0)
            second_active = sample(1)
            assert second_active != first_inactive
            assert first_active == second_active, (
                theme, first_active, second_active
            )
            assert first_inactive == second_inactive, (
                theme, first_inactive, second_inactive
            )
            root.close()
            app.processEvents()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=20,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_queue_tab_object_names_are_set_in_main_ui():
    from pathlib import Path
    code = (
        Path(__file__).resolve().parents[1]
        / "src" / "printer_supporter" / "ui_pages.py"
    ).read_text(encoding="utf-8")
    assert 'queue_tabs.setObjectName("queueTabs")' in code
    assert 'queue_tabs.tabBar().setObjectName("queueTabBar")' in code
