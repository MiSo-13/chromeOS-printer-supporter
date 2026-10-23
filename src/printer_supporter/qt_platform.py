"""Crostini에서는 Qt import 전에 X11/xcb 플랫폼을 선택합니다."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import MutableMapping

CROSTINI_MARKERS = (Path("/mnt/chromeos"), Path("/opt/google/cros-containers"), Path("/dev/.cros_milestone"))
LIBRARY_PACKAGES = {
    "libxcb-cursor.so.0": "libxcb-cursor0",
    "libxcb-icccm.so.4": "libxcb-icccm4",
    "libxcb-image.so.0": "libxcb-image0",
    "libxcb-keysyms.so.1": "libxcb-keysyms1",
    "libxcb-render-util.so.0": "libxcb-render-util0",
    "libxcb-xinerama.so.0": "libxcb-xinerama0",
    "libxcb-xkb.so.1": "libxcb-xkb1",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libxcb.so.1": "libxcb1",
    "libX11-xcb.so.1": "libx11-xcb1",
    "libEGL.so.1": "libegl1",
}
MISSING_LIBRARY = re.compile(r"^\s*(\S+)\s+=>\s+not found\s*$")


class QtPlatformError(RuntimeError):
    """그래픽 환경을 초기화하기 전에 보여줄 실행 환경 오류."""


def is_crostini(*, env: MutableMapping[str, str] | None = None, platform: str | None = None,
                markers: tuple[bool, ...] | None = None) -> bool:
    target = os.environ if env is None else env
    system = sys.platform if platform is None else platform
    if not system.startswith("linux"):
        return False
    if target.get("SOMMELIER_VERSION") or target.get("CROS_USER_ID_HASH"):
        return True
    return any(markers) if markers is not None else any(path.exists() for path in CROSTINI_MARKERS)


def _xcb_plugin() -> Path | None:
    try:
        spec = importlib.util.find_spec("PyQt6")
    except (ImportError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    plugin = Path(spec.origin).resolve().parent / "Qt6" / "plugins" / "platforms" / "libqxcb.so"
    return plugin if plugin.is_file() else None


def missing_xcb_libraries(plugin: Path, *, runner=subprocess.run) -> tuple[str, ...]:
    try:
        result = runner(["ldd", str(plugin)], capture_output=True, text=True, check=False, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        raise QtPlatformError(f"X11 라이브러리 검사(ldd)에 실패했습니다: {exc}") from exc
    if result.returncode != 0:
        raise QtPlatformError(f"X11 라이브러리 검사에 실패했습니다: {(result.stderr or result.stdout).strip()}")
    missing = []
    for line in result.stdout.splitlines():
        match = MISSING_LIBRARY.match(line)
        if match:
            missing.append(match.group(1))
    return tuple(sorted(set(missing)))


def configure_qt_platform(
    *, env: MutableMapping[str, str] | None = None, platform: str | None = None,
    crostini: bool | None = None, plugin: Path | None = None,
    missing: tuple[str, ...] | None = None,
) -> str:
    """명시적 Qt 설정을 존중하며, Crostini인 경우에만 XCB를 기본값으로 선택."""
    target = os.environ if env is None else env
    system = sys.platform if platform is None else platform
    if target.get("QT_QPA_PLATFORM"):
        return target["QT_QPA_PLATFORM"]
    if not system.startswith("linux"):
        return "system-default"
    detected = is_crostini(env=target, platform=system) if crostini is None else crostini
    if not detected:
        return "system-default"
    if not target.get("DISPLAY"):
        raise QtPlatformError("Crostini X11 DISPLAY가 없습니다. XWayland/Sommelier 연결을 확인하세요.")

    target_plugin = _xcb_plugin() if plugin is None else plugin
    if target_plugin is None or not target_plugin.is_file():
        raise QtPlatformError("PyQt6 X11(xcb) 플러그인을 찾지 못했습니다. PyQt6 설치를 확인하세요.")

    absent = missing_xcb_libraries(target_plugin) if missing is None else missing
    if absent:
        packages = sorted({LIBRARY_PACKAGES[name] for name in absent if name in LIBRARY_PACKAGES})
        install = (
            "sudo apt update && sudo apt install -y " + " ".join(packages)
            if packages else "누락된 라이브러리를 제공하는 Debian 패키지를 확인해 주세요."
        )
        raise QtPlatformError(
            "Crostini X11(xcb) 라이브러리가 누락되었습니다: "
            + ", ".join(absent)
            + "\n설치 방법: " + install
        )

    target["QT_QPA_PLATFORM"] = "xcb"
    return "xcb"
