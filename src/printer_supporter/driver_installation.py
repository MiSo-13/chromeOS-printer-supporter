"""공식 제조사 지원 페이지와 명시적 승인 기반 배포판 드라이버 설치.

제조사 제공 다운로드 바이너리/스크립트는 절대로 앱에서 실행하지 않습니다.
Linux 배포판 저장소의 사전에 허용된 패키지만 설치할 수 있습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import Callable
import re

from .identification import PrinterIdentity

# 다음 링크는 제조사 공식 사이트 및 배포판 문서에서 개별 확인한 정적 주소입니다.
# 감지된 프린터 이름을 URL에 삽입하거나 임의의 다운로드 주소를 열지 않습니다.
OFFICIAL_SUPPORT = {
    "Samsung": ("Samsung 고객지원", "https://www.samsung.com/sec/support/"),
    "Brother": ("Brother 지원 및 다운로드", "https://www.brother-korea.com/ko-kr/support"),
    "HP": ("HP 프린터 드라이버 지원", "https://support.hp.com/us-en/drivers/printers"),
    "Canon": ("Canon 글로벌 지원", "https://global.canon/en/support/"),
}

SAMSUNG_SL_M2030W = "https://www.samsung.com/sec/support/model/SL-M2030W/"
BROTHER_BRLASER_DOCS = "https://packages.debian.org/bookworm/printer-driver-brlaser"

# Debian 패키지 메타데이터에 호환이 명시된 모델만 나열합니다.
# 'Series'는 모델 식별 정규화 과정에서 임의로 생략하지 않습니다.
BROLASER_MODELS = frozenset({
    "DCP-1510", "DCP-1602", "DCP-7030", "DCP-7040", "DCP-7055",
    "DCP-7055W", "DCP-7060D", "DCP-7065DN", "DCP-7080",
    "DCP-L2500D", "DCP-L2540DW", "DCP-L2710DW",
    "HL-1110 SERIES", "HL-1200 SERIES", "HL-L2300D SERIES",
    "HL-L2320D SERIES", "HL-L2340D SERIES", "HL-L2360D SERIES",
    "MFC-1910W", "MFC-7240", "MFC-7360N", "MFC-7365DN",
    "MFC-7840W", "MFC-L2710DW",
})
# 호환이 명확한 모델 하나의 배포판 패키지부터 지원하고, 임의의
# 패키지 이름이나 서드파티 저장소를 모델에서 유추하지 않습니다.
ALLOWLIST = {"printer-driver-brlaser": "Brother"}


@dataclass(frozen=True)
class DriverInstallPlan:
    manufacturer: str | None
    model_name: str
    support_title: str | None
    support_url: str | None
    support_note: str
    package: str | None
    package_status: str       # available, installed, unavailable, unknown, not_applicable
    package_note: str

    @property
    def can_install(self) -> bool:
        return self.package is not None and self.package_status == "available"


class DriverInstallError(RuntimeError):
    """승인/호환성/설치 오류."""


def _normalized_name(name: str) -> str:
    return " ".join(name.upper().strip().replace("_", "-").split())


def package_for_identity(identity: PrinterIdentity) -> str | None:
    """실제 IPP 응답에서 확인된 Brother 지원 모델만 배포판 설치 대상으로 지정."""
    if identity.source != "IPP 장치 응답" or identity.manufacturer != "Brother":
        return None
    reported = _normalized_name(identity.name)
    if not reported.startswith("BROTHER "):
        return None
    model = reported[len("BROTHER "):]
    if model in BROLASER_MODELS:
        return "printer-driver-brlaser"
    return None


def official_support_for(identity: PrinterIdentity) -> tuple[str | None, str | None, str]:
    if identity.manufacturer == "Samsung" and _normalized_name(identity.name) in {
        "SAMSUNG SL-M2030W", "SAMSUNG SL M2030W",
    }:
        return (
            "Samsung SL-M2030W 공식 다운로드",
            SAMSUNG_SL_M2030W,
            "이 모델의 공식 지원 페이지에 Linux 드라이버가 게시되어 있습니다. "
            "운영체제·아키텍처·라이선스를 확인한 뒤 수동으로 받으세요. "
            "앱은 다운로드한 압축파일·스크립트를 자동 실행하지 않습니다.",
        )
    support = OFFICIAL_SUPPORT.get(identity.manufacturer or "")
    if support is None:
        return None, None, (
            "확인된 제조사 지원 페이지가 없습니다. 프린터의 정확한 모델을 확인하고 "
            "제조사의 공식 웹사이트에서 직접 검색하세요."
        )
    name, url = support
    return name, url, (
        "제조사 공식 지원 입구입니다. 표시된 모델이 실제 기기와 같고 "
        "Linux용 파일이 제공되는지 직접 확인하세요. "
        "이 링크는 특정 모델의 드라이버 호환성을 보증하지 않습니다."
    )


def _installed_status(output: str) -> bool:
    return "install ok installed" in output.lower()


def _candidate_available(output: str) -> bool:
    match = re.search(r"^\s*Candidate:\s*(\S+)\s*$", output, re.MULTILINE)
    return bool(match and match.group(1).lower() not in {"(none)", "none"})


class DriverInstallService:
    def __init__(
        self,
        runner: Callable[..., CompletedProcess[str]] = run,
        *,
        os_release: str | Path = "/etc/os-release",
    ):
        self.runner = runner
        self.os_release = Path(os_release)

    def _run(self, args: list[str], timeout: int = 20) -> CompletedProcess[str]:
        try:
            return self.runner(
                args, capture_output=True, text=True, check=False, timeout=timeout,
            )
        except (OSError, TimeoutExpired) as exc:
            raise DriverInstallError("패키지 관리자 실행 또는 조회가 실패했습니다.") from exc

    def _verify_linux_distribution(self) -> None:
        try:
            content = self.os_release.read_text(encoding="utf-8")
        except OSError as exc:
            raise DriverInstallError("운영체제 정보를 확인할 수 없습니다.") from exc
        pairs = {}
        for line in content.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                pairs[key] = value.strip().strip('"').strip("'")
        family = (pairs.get("ID", "") + " " + pairs.get("ID_LIKE", "")).split()
        if not {"debian", "ubuntu"}.intersection(family):
            raise DriverInstallError("Debian/Ubuntu 계열 Linux 컨테이너에서만 설치할 수 있습니다.")

    def plan(self, identity: PrinterIdentity) -> DriverInstallPlan:
        title, url, note = official_support_for(identity)
        package = package_for_identity(identity)
        if package is None:
            return DriverInstallPlan(
                identity.manufacturer, identity.name, title, url, note,
                None, "not_applicable",
                "정확한 모델과 배포판 지원 근거가 없어 자동 설치할 패키지를 지정하지 않았습니다. "
                "공식 지원 페이지 또는 기존 PPD 선택을 이용하세요.",
            )
        try:
            self._verify_linux_distribution()
            query = self._run(
                ["dpkg-query", "-W", "-f=${Status}", package], timeout=8,
            )
            if query.returncode == 0 and _installed_status(query.stdout):
                status = "installed"
                text = "배포판 패키지가 이미 설치되어 있습니다. CUPS 모델 목록을 다시 조회해 주세요."
            else:
                policy = self._run(["apt-cache", "policy", package], timeout=8)
                if policy.returncode == 0 and _candidate_available(policy.stdout):
                    status = "available"
                    text = (
                        "설정된 Debian/Ubuntu APT 저장소에서 설치 가능한 "
                        "printer-driver-brlaser 패키지를 확인했습니다. "
                        "패키지의 모델 지원 문서: " + BROTHER_BRLASER_DOCS
                    )
                else:
                    status = "unavailable"
                    text = "현재 설정된 APT 저장소에서 설치 후보를 찾을 수 없습니다."
        except DriverInstallError as exc:
            status = "unknown"
            text = str(exc)
        return DriverInstallPlan(
            identity.manufacturer, identity.name, title, url, note,
            package, status, text,
        )

    def install(
        self, identity: PrinterIdentity, plan: DriverInstallPlan,
        *, approved: bool = False,
    ) -> str:
        if not approved:
            raise DriverInstallError("사용자 승인 없이 드라이버를 설치할 수 없습니다.")
        package = package_for_identity(identity)
        if (
            not package or package not in ALLOWLIST
            or ALLOWLIST[package] != identity.manufacturer
            or plan.package != package or plan.model_name != identity.name
            or plan.manufacturer != identity.manufacturer
            or not plan.can_install
        ):
            raise DriverInstallError("승인한 프린터 모델 또는 설치 계획이 유효하지 않습니다.")
        self._verify_linux_distribution()
        # 화면에서 확인한 계획이 오래됐거나 패키지 출처가 바뀌었다면 설치 중단.
        refreshed = self.plan(identity)
        if refreshed.package != package or refreshed.package_status != "available":
            raise DriverInstallError("패키지 설치 가능 상태가 변경되었습니다. 다시 조회해 주세요.")
        args = [
            "sudo", "-n", "apt-get", "install", "-y",
            "--no-install-recommends", package,
        ]
        result = self._run(args, timeout=600)
        if result.returncode:
            detail = (result.stderr or result.stdout or "원인을 알 수 없습니다.").strip()[-900:]
            raise DriverInstallError("APT 패키지 설치에 실패했습니다: " + detail)
        query = self._run(
            ["dpkg-query", "-W", "-f=${Status}", package], timeout=8,
        )
        if query.returncode or not _installed_status(query.stdout):
            raise DriverInstallError("설치 명령은 끝났지만 패키지 설치 완료를 확인하지 못했습니다.")
        return (
            f"{package} 설치를 확인했습니다. CUPS 모델 목록을 다시 조회한 다음 "
            "프린터와 모델이 일치하는지 확인하고 등록하세요."
        )
