"""APT 드라이버 설치 후 CUPS 모델 존재 여부와 추가 준비 사항을 확인합니다.

드라이버 파일 설치와 실제 인쇄 성공은 별개입니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .driver_recommendation import matching_installed_drivers, parse_installed_drivers
from .identification import PrinterIdentity


@dataclass(frozen=True)
class CupsDriverCheck:
    status: str                # matched | multiple | missing | unavailable
    details: str
    model_id: str | None = None


# foo2zjs 제작사 설치 문서에 별도 펌웨어 전송이 필요한 모델로 명시됨.
# https://sources.debian.org/src/foo2zjs/20200505dfsg0-1/INSTALL/
_HP_FIRMWARE_MODELS = frozenset({
    "LASERJET 1000", "LASERJET 1005", "LASERJET 1018", "LASERJET 1020",
})


def firmware_notice(identity: PrinterIdentity, package: str | None) -> str | None:
    if (
        package == "printer-driver-foo2zjs"
        and identity.manufacturer == "HP"
        and " ".join((identity.model or "").upper().split()) in _HP_FIRMWARE_MODELS
    ):
        return (
            "이 HP LaserJet 모델은 전원을 켤 때 프린터 펌웨어를 별도로 전송해야 할 수 있습니다. "
            "Crostini에서는 USB 장치 접근이 제한될 수 있으며, 드라이버 패키지 설치만으로 "
            "출력 준비가 끝나지 않습니다. 이 앱은 펌웨어를 자동 전송하지 않습니다."
        )
    return None


def verify_cups_model(identity: PrinterIdentity, lpinfo_output: str) -> CupsDriverCheck:
    installed = parse_installed_drivers(lpinfo_output)
    matches = matching_installed_drivers(identity, installed)
    if len(matches) == 1:
        return CupsDriverCheck(
            "matched",
            "설치 후 CUPS 목록에서 모델명이 일치하는 드라이버 1개를 확인했습니다. "
            "실제 출력 성공 여부는 별도로 확인해야 합니다.",
            matches[0].model_id,
        )
    if len(matches) > 1:
        return CupsDriverCheck(
            "multiple",
            f"설치 후 CUPS에서 모델명 일치 후보 {len(matches)}개를 찾았습니다. "
            "사용자가 정확한 드라이버를 선택해야 합니다.",
        )
    return CupsDriverCheck(
        "missing",
        "패키지는 설치됐지만 CUPS 목록에서 모델명에 정확히 일치하는 드라이버를 "
        "확인하지 못했습니다. 드라이버/모델을 확인한 뒤 등록해 주세요.",
    )
