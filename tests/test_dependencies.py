"""승인 없는 설치 차단과 패키지 탐지 동작 검증."""

from subprocess import CompletedProcess

import pytest

from printer_supporter.dependencies import (
    CUPS, LIBREOFFICE, Dependency, DependencyInstallError, DependencyManager,
)


def manager(tmp_path, binaries=(), runner=None):
    release = tmp_path / "os-release"
    release.write_text('ID=debian\nVERSION_ID="12"\n', encoding="utf-8")
    return DependencyManager(
        which=lambda command: f"/usr/bin/{command}" if command in binaries else None,
        runner=runner or (lambda *args, **kwargs: CompletedProcess(args, 0, "", "")),
        os_release=release,
    )


def test_missing_required_and_optional(tmp_path):
    installed = ("lp", "lpstat", "cancel", "sudo", "apt-get")
    service = manager(tmp_path, binaries=installed)
    assert service.missing(required_only=True) == []
    assert service.missing() == [LIBREOFFICE]


def test_missing_cups(tmp_path):
    service = manager(tmp_path, binaries=("libreoffice",))
    assert service.missing(required_only=True) == [CUPS]


def test_user_consent_is_required(tmp_path):
    calls = []
    service = manager(tmp_path, binaries=("sudo", "apt-get"), runner=lambda *a, **k: calls.append(a))
    with pytest.raises(DependencyInstallError, match="동의"):
        service.install([CUPS])
    assert calls == []


def test_whitelist_blocks_unapproved_packages(tmp_path):
    service = manager(tmp_path)
    unknown = Dependency("custom", "위험", "", ("not-approved",), (), False)
    with pytest.raises(DependencyInstallError, match="허용되지"):
        service.installation_command([unknown])


def test_install_uses_fixed_apt_arguments(tmp_path):
    calls = []
    binaries = {"sudo", "apt-get"}

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        service.which = lambda command: f"/usr/bin/{command}"
        return CompletedProcess(command, 0, "", "")

    service = manager(tmp_path, binaries=binaries, runner=runner)
    # 테스트 중에 명령 목록이 변경되면 설치 후 검사에도 반영되어야 합니다.
    service.which = lambda command: f"/usr/bin/{command}" if command in binaries else None
    assert service.install([CUPS], approved=True).startswith("필요한 패키지")
    assert calls[0][0] == [
        "sudo", "-n", "apt-get", "install", "-y", "cups", "cups-client"
    ]
    assert calls[0][1]["timeout"] == 600
    assert calls[0][1]["check"] is False


def test_install_failure_has_helpful_error(tmp_path):
    def runner(command, **kwargs):
        return CompletedProcess(command, 1, "", "sudo: a password is required")

    service = manager(tmp_path, binaries=("sudo", "apt-get"), runner=runner)
    with pytest.raises(DependencyInstallError, match="sudo 권한"):
        service.install([LIBREOFFICE], approved=True)


def test_unsupported_platform_is_rejected(tmp_path):
    service = manager(tmp_path, binaries=("sudo", "apt-get"))
    service.os_release.write_text("ID=fedora\n", encoding="utf-8")
    with pytest.raises(DependencyInstallError, match="Debian/Ubuntu"):
        service.install([CUPS], approved=True)
