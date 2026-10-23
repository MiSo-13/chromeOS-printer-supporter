"""ChromeOS .deb 구성과 파일 앱 런처 메타데이터 검사."""
from __future__ import annotations

import configparser
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "chromeos-printer-supporter"


def test_linux_desktop_file_and_icon():
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    desktop = ROOT / "packaging" / f"{PACKAGE}.desktop"
    parser.read(desktop, encoding="utf-8")
    app = parser["Desktop Entry"]
    assert app["Type"] == "Application"
    assert app["Exec"] == f"/usr/bin/{PACKAGE}"
    assert app["TryExec"] == f"/usr/bin/{PACKAGE}"
    assert app["Icon"] == PACKAGE
    assert app["Terminal"] == "false"
    assert app["Name[ko]"]
    assert "Office;" in app["Categories"]

    launcher = (ROOT / "packaging" / PACKAGE).read_text(encoding="utf-8")
    assert launcher.startswith("#!/bin/sh")
    assert "exec /opt/chromeos-printer-supporter/chromeos-printer-supporter" in launcher
    assert '"$@"' in launcher

    icon = ET.parse(ROOT / "packaging" / f"{PACKAGE}.svg")
    assert icon.getroot().attrib["viewBox"] == "0 0 128 128"


@pytest.mark.skipif(
    shutil.which("dpkg-deb") is None or platform.machine() not in ("x86_64", "aarch64"),
    reason="Debian 패키징 도구가 설치된 Linux에서 실행",
)
def test_build_deb_from_mocked_bundle_and_verify_contents(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    executable = bundle / PACKAGE
    executable.write_text("#!/bin/sh\necho mocked release bundle\n", encoding="utf-8")
    executable.chmod(0o755)
    libdir = bundle / "_internal"
    libdir.mkdir()
    (libdir / "file.txt").write_text("bundled runtime", encoding="utf-8")

    output_dir = tmp_path / "artifacts"
    arch = "amd64" if platform.machine() == "x86_64" else "arm64"
    result = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "build_deb.py"),
            "--bundle", str(bundle),
            "--output-dir", str(output_dir),
            "--arch", arch,
        ], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    package = output_dir / f"{PACKAGE}_0.1.0_{arch}.deb"
    assert package.is_file()
    checksum = package.with_suffix(".deb.sha256")
    digest, filename = checksum.read_text().split()
    assert digest == hashlib.sha256(package.read_bytes()).hexdigest()
    assert filename == package.name

    info = subprocess.run(
        ["dpkg-deb", "--field", str(package)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert f"Architecture: {arch}" in info
    assert "Depends: " in info and "cups-client" in info
    assert "Suggests: libreoffice" in info
    assert "Python" not in info  # 별도 Python 설치를 요구하지 않습니다.

    listing = subprocess.run(
        ["dpkg-deb", "--contents", str(package)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert f"/opt/{PACKAGE}/{PACKAGE}" in listing
    assert f"/opt/{PACKAGE}/_internal/file.txt" in listing
    assert f"/usr/bin/{PACKAGE}" in listing
    assert f"/usr/share/applications/{PACKAGE}.desktop" in listing
    assert f"/usr/share/icons/hicolor/scalable/apps/{PACKAGE}.svg" in listing


def test_release_versions_are_consistent():
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    about = (ROOT / "src" / "printer_supporter" / "__init__.py").read_text(
        encoding="utf-8",
    )
    assert f'__version__ = "{project["project"]["version"]}"' in about


def test_settings_are_saved_in_user_config_not_working_directory(tmp_path, monkeypatch):
    from printer_supporter.settings import SettingsStore, settings_path

    monkeypatch.delenv("PRINTHUB_CONFIG_DIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)
    assert settings_path() == (
        tmp_path / "config" / PACKAGE / "settings.json"
    )
    store = SettingsStore()
    store.set_theme("dark")
    assert SettingsStore().data["theme"] == "dark"
    assert not (tmp_path / "data").exists()


def test_legacy_test_config_env_still_supported(tmp_path, monkeypatch):
    from printer_supporter.settings import settings_path

    monkeypatch.setenv("PRINTHUB_CONFIG_DIR", str(tmp_path / "existing-config"))
    assert settings_path() == tmp_path / "existing-config" / "settings.json"
