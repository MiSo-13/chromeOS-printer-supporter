import json
import pytest
from printer_supporter.settings import SettingsStore
from printer_supporter.theme import APP_STYLESHEET, DARK_STYLESHEET, stylesheet_for


def test_default_and_persisted_theme(tmp_path):
    path = tmp_path / "data" / "settings.json"
    store = SettingsStore(path)
    assert store.data["theme"] == "light"
    store.set_theme("dark")
    assert json.loads(path.read_text(encoding="utf-8"))["theme"] == "dark"
    assert SettingsStore(path).data["theme"] == "dark"


def test_invalid_or_corrupt_settings_fallback(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{bad", encoding="utf-8")
    assert SettingsStore(path).data["theme"] == "light"
    path.write_text('{"theme":"invalid","other":42}', encoding="utf-8")
    store = SettingsStore(path)
    assert store.data["theme"] == "light"
    store.set_theme("dark")
    assert json.loads(path.read_text(encoding="utf-8"))["other"] == 42
    with pytest.raises(ValueError):
        store.set_theme("invalid")


def test_stylesheet_selection():
    assert stylesheet_for("light") == APP_STYLESHEET
    assert stylesheet_for("dark") == DARK_STYLESHEET
    assert APP_STYLESHEET != DARK_STYLESHEET


def test_dark_theme_button_contrast_rules():
    assert "QPushButton { background: #303a46; color: #f1f5f9;" in DARK_STYLESHEET
    assert "QPushButton:hover { background: #3b4a5b; color: #ffffff;" in DARK_STYLESHEET
    assert "QComboBox QAbstractItemView { background: #242b34; color: #f1f5f9;" in DARK_STYLESHEET
    assert "QPushButton#primaryButton { background: #357bbd; color: white;" in DARK_STYLESHEET
