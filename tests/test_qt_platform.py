"""실제 프린터나 Qt 화면 없이 Crostini X11 실행 경로를 검증."""

from subprocess import CompletedProcess

import pytest

from printer_supporter.qt_platform import (
    QtPlatformError, configure_qt_platform, is_crostini, missing_xcb_libraries,
)


def test_detect_crostini_from_markers_without_changing_other_platforms():
    assert is_crostini(env={}, platform="linux", markers=(False, True))
    assert is_crostini(env={"SOMMELIER_VERSION": "1"}, platform="linux", markers=(False,))
    assert not is_crostini(env={"SOMMELIER_VERSION": "1"}, platform="win32", markers=(True,))


def test_crostini_auto_selects_xcb_before_qt(tmp_path):
    plugin = tmp_path / "libqxcb.so"
    plugin.touch()
    env = {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"}
    assert configure_qt_platform(env=env, platform="linux", crostini=True, plugin=plugin, missing=()) == "xcb"
    assert env["QT_QPA_PLATFORM"] == "xcb"


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_other_platforms_keep_native_qt_default(platform, tmp_path):
    env = {"DISPLAY": ":0"}
    assert configure_qt_platform(env=env, platform=platform, crostini=False) == "system-default"
    assert "QT_QPA_PLATFORM" not in env


@pytest.mark.parametrize("explicit", ["wayland", "offscreen", "xcb"])
def test_explicit_qt_platform_is_preserved(explicit):
    env = {"QT_QPA_PLATFORM": explicit}
    assert configure_qt_platform(env=env, platform="linux", crostini=True) == explicit
    assert env["QT_QPA_PLATFORM"] == explicit


def test_without_display_does_not_fallback_to_wayland():
    env = {"WAYLAND_DISPLAY": "wayland-0"}
    with pytest.raises(QtPlatformError, match="DISPLAY"):
        configure_qt_platform(env=env, platform="linux", crostini=True)
    assert "QT_QPA_PLATFORM" not in env


def test_missing_xcb_plugin_is_actionable(monkeypatch):
    monkeypatch.setattr("printer_supporter.qt_platform._xcb_plugin", lambda: None)
    with pytest.raises(QtPlatformError, match="플러그인"):
        configure_qt_platform(env={"DISPLAY": ":0"}, platform="linux", crostini=True,
                              plugin=None, missing=())


def test_missing_xcb_dependencies_report_package(tmp_path):
    plugin = tmp_path / "libqxcb.so"
    plugin.touch()
    env = {"DISPLAY": ":0"}
    with pytest.raises(QtPlatformError, match="libxcb-cursor0"):
        configure_qt_platform(env=env, platform="linux", crostini=True,
                              plugin=plugin, missing=("libxcb-cursor.so.0",))
    assert "QT_QPA_PLATFORM" not in env


def test_ldd_missing_dependency_parsing(tmp_path):
    plugin = tmp_path / "libqxcb.so"
    plugin.touch()
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return CompletedProcess(command, 0,
                                "    libxcb-cursor.so.0 => not found\n"
                                "    libX11.so.6 => /lib/libX11.so.6\n", "")

    assert missing_xcb_libraries(plugin, runner=runner) == ("libxcb-cursor.so.0",)
    assert calls == [["ldd", str(plugin)]]
