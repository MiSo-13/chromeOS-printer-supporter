"""승인 기반 Crostini 의존성 검사 및 설치.

앱이 패키지를 조용히 설치하지 않도록 패키지명은 고정하고
사용자 동의 후에만 sudo -n apt-get을 실행합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import Callable
import shutil


@dataclass(frozen=True)
class Dependency:
    key: str
    name: str
    description: str
    packages: tuple[str, ...]
    commands: tuple[str, ...]
    required: bool


CUPS = Dependency(
    "cups", "CUPS 인쇄 서비스",
    "프린터 검색, 인쇄 작업 전송 및 대기열 관리에 필요합니다.",
    ("cups", "cups-client"), ("lp", "lpstat", "cancel"), True,
)
LIBREOFFICE = Dependency(
    "libreoffice", "LibreOffice",
    "Word, Excel, PowerPoint 및 ODF 문서를 PDF로 변환할 때 필요합니다.",
    ("libreoffice",), ("libreoffice",), False,
)
IPP_TOOLS = Dependency(
    "ipp-utils", "IPP 프린터 정보 도구",
    "프린터 제조사·모델·IPP 지원 속성을 읽는 ipptool 명령입니다.",
    ("cups-ipp-utils",), ("ipptool",), False,
)
DEPENDENCIES = (CUPS, LIBREOFFICE, IPP_TOOLS)


class DependencyInstallError(RuntimeError):
    """사용자에게 안내할 수 있는 패키지 설치 오류."""


class DependencyManager:
    def __init__(
        self,
        which: Callable[[str], str | None] = shutil.which,
        runner: Callable[..., CompletedProcess[str]] = run,
        os_release: str | Path = "/etc/os-release",
    ):
        self.which = which
        self.runner = runner
        self.os_release = Path(os_release)

    def installed(self, dependency: Dependency) -> bool:
        return all(self.which(command) for command in dependency.commands)

    def missing(self, *, required_only: bool = False) -> list[Dependency]:
        return [
            dependency for dependency in DEPENDENCIES
            if (not required_only or dependency.required) and not self.installed(dependency)
        ]

    def installation_command(self, dependencies: list[Dependency]) -> list[str]:
        if not dependencies:
            return []
        allowed = {dependency.key: dependency for dependency in DEPENDENCIES}
        if any(allowed.get(dependency.key) is not dependency for dependency in dependencies):
            raise DependencyInstallError("설치가 허용되지 않은 패키지가 포함되어 있습니다.")
        packages = sorted({package for dep in dependencies for package in dep.packages})
        return ["sudo", "-n", "apt-get", "install", "-y", *packages]

    def _verify_platform(self) -> None:
        try:
            text = self.os_release.read_text(encoding="utf-8")
        except OSError as exc:
            raise DependencyInstallError("운영체제를 확인할 수 없습니다.") from exc
        entries = {}
        for line in text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                entries[key] = value.strip('"')
        family = (entries.get("ID", "") + " " + entries.get("ID_LIKE", "")).split()
        if not {"debian", "ubuntu"}.intersection(family):
            raise DependencyInstallError("자동 설치는 Debian/Ubuntu 계열 Crostini에서만 지원합니다.")

    def install(self, dependencies: list[Dependency], *, approved: bool = False) -> str:
        if not approved:
            raise DependencyInstallError("설치 전에 사용자 동의가 필요합니다.")
        self._verify_platform()
        command = self.installation_command(dependencies)
        if not command:
            return "설치할 패키지가 없습니다."
        if not self.which("sudo") or not self.which("apt-get"):
            raise DependencyInstallError("sudo 또는 apt-get을 찾을 수 없습니다.")
        try:
            result = self.runner(
                command, capture_output=True, text=True, check=False, timeout=600,
            )
        except TimeoutExpired as exc:
            raise DependencyInstallError("패키지 설치 시간이 초과되었습니다. 터미널에서 확인해 주세요.") from exc
        except OSError as exc:
            raise DependencyInstallError(f"설치 도구 실행 실패: {exc}") from exc
        if result.returncode:
            reason = (result.stderr or result.stdout or "알 수 없는 오류").strip()[-1200:]
            raise DependencyInstallError(
                "자동 설치에 실패했습니다. Crostini의 sudo 권한이나 패키지 저장소를 확인해 주세요.\n"
                + reason
            )
        remaining = [dep.name for dep in dependencies if not self.installed(dep)]
        if remaining:
            raise DependencyInstallError(
                "설치는 완료됐지만 일부 명령어가 확인되지 않습니다: " + ", ".join(remaining)
            )
        return "필요한 패키지 설치가 완료되었습니다."
