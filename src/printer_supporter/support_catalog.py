"""근거가 확인된 '우선 안내 모델' 목록.

'우선 안내'는 이 앱에서 실물 출력 테스트 완료를 뜻하지 않습니다.
실제 기기 속성이 확인되지 않은 경우에도 등록/설치 제약은 그대로 유지합니다.
목록에 없는 프린터도 기존의 범용 IPP/CUPS 탐색 경로를 이용할 수 있습니다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .identification import PrinterIdentity


PWG_CERTIFIED_LIST = "https://www.pwg.org/printers/"
DEBIAN_BRLASER_PACKAGE = "https://packages.debian.org/bookworm/printer-driver-brlaser"
SAMSUNG_M2030W_SUPPORT = "https://www.samsung.com/sec/support/model/SL-M2030W/"


@dataclass(frozen=True)
class FocusPrinter:
    manufacturer: str
    model: str
    pathway: str  # driverless | distro-package | vendor-manual
    evidence: str
    source_url: str
    guidance: str

    @property
    def full_name(self) -> str:
        return f"{self.manufacturer} {self.model}"


# 정확한 모델명만 명시합니다. 유사 접미사(예: M2030 / M2030W), 지역별 변형,
# 'Series' 누락 등은 동일 모델로 임의 판단하지 않습니다.
FOCUS_PRINTERS: tuple[FocusPrinter, ...] = (
    FocusPrinter(
        "Samsung", "SL-M2030W", "vendor-manual",
        "제조사 공식 Linux 드라이버 다운로드 안내",
        SAMSUNG_M2030W_SUPPORT,
        "x86_64에서는 삼성 공식 ZIP을 SHA-256으로 검증해 승인 후 다운로드·설치할 수 있습니다. "
        "ARM은 지원되지 않으며 제조사 설치 스크립트는 실행하지 않습니다.",
    ),
    FocusPrinter(
        "Brother", "HL-L2340D series", "distro-package",
        "Debian brlaser 패키지의 지원 보고 모델",
        DEBIAN_BRLASER_PACKAGE,
        "정확한 IPP 모델 응답이 확인되면 printer-driver-brlaser 설치 가능성을 확인합니다. "
        "Socket/mDNS 이름만으로는 자동 설치하지 않습니다.",
    ),
    FocusPrinter(
        "Brother", "DCP-L2540DW", "distro-package",
        "Debian brlaser 패키지의 지원 보고 모델",
        DEBIAN_BRLASER_PACKAGE,
        "정확한 IPP 모델 응답이 확인되면 printer-driver-brlaser 설치 가능성을 확인합니다. "
        "Socket/mDNS 이름만으로는 자동 설치하지 않습니다.",
    ),
    FocusPrinter(
        "Brother", "MFC-L2710DW", "distro-package",
        "Debian brlaser 패키지의 지원 보고 모델",
        DEBIAN_BRLASER_PACKAGE,
        "정확한 IPP 모델 응답이 확인되면 printer-driver-brlaser 설치 가능성을 확인합니다. "
        "Socket/mDNS 이름만으로는 자동 설치하지 않습니다.",
    ),
    FocusPrinter(
        "HP", "LaserJet Pro M404dw", "driverless",
        "PWG IPP Everywhere 인증 모델 목록 등재",
        PWG_CERTIFIED_LIST,
        "IPP/IPPS 연결을 먼저 확인하세요. 앱에서는 장치의 실제 IPP 속성을 조회한 후 "
        "드라이버리스 사용 가능성을 표시합니다.",
    ),
    FocusPrinter(
        "Canon", "imageCLASS MF662Cdw", "driverless",
        "PWG IPP Everywhere 인증 모델 목록 등재",
        PWG_CERTIFIED_LIST,
        "IPP/IPPS 연결을 먼저 확인하세요. 앱에서는 장치의 실제 IPP 속성을 조회한 후 "
        "드라이버리스 사용 가능성을 표시합니다.",
    ),
    FocusPrinter(
        "Epson", "EM-C7100", "driverless",
        "PWG IPP Everywhere 인증 모델 목록 등재",
        PWG_CERTIFIED_LIST,
        "IPP/IPPS 연결을 먼저 확인하세요. 앱에서는 장치의 실제 IPP 속성을 조회한 후 "
        "드라이버리스 사용 가능성을 표시합니다.",
    ),
)


@dataclass(frozen=True)
class FocusAssessment:
    profile: FocusPrinter | None
    device_verified: bool
    title: str
    detail: str


def _normalized(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def assess_printer(identity: PrinterIdentity) -> FocusAssessment:
    """모델명 정확 일치만 우선 안내. 미등록 모델은 범용 처리."""
    if not identity.manufacturer or not identity.model:
        return FocusAssessment(
            None, False, "일반 호환성 확인",
            "모델이 확인되지 않았습니다. 기존 IPP/CUPS 탐색과 수동 PPD 선택을 이용할 수 있습니다.",
        )
    verified = identity.source == "IPP 장치 응답"
    # 조회된 제조사와 모델을 각각 비교하므로 타사 제품의 같은 모델명도 제외됩니다.
    for entry in FOCUS_PRINTERS:
        if (_normalized(entry.manufacturer) == _normalized(identity.manufacturer)
                and _normalized(entry.model) == _normalized(identity.model)
                and _normalized(entry.full_name) == _normalized(identity.name)):
            if verified:
                return FocusAssessment(
                    entry, True, f"우선 안내 모델: {entry.full_name}",
                    f"{entry.evidence}. {entry.guidance} "
                    "실제 Chromebook 인쇄 성공 여부는 아직 검증되지 않았습니다.",
                )
            if identity.source == "사용자 확인(명시적 선택)":
                return FocusAssessment(
                    entry, False, f"직접 확인한 모델: {entry.full_name}",
                    f"사용자가 선택한 모델이며 IPP 장치 응답으로 검증된 정보는 아닙니다. "
                    f"{entry.guidance}",
                )
            return FocusAssessment(
                entry, False, f"우선 목록과 이름 일치: {entry.full_name}",
                f"{entry.evidence}. 검색 이름만 일치하므로 실제 모델은 미검증입니다. "
                "자동 설치 또는 드라이버리스 선택을 확정하지 않습니다. "
                + entry.guidance,
            )
    return FocusAssessment(
        None, verified, "일반 호환성 확인",
        "우선 안내 목록에 없는 프린터입니다. 기존 IPP 기능 조회·설치된 CUPS 드라이버 "
        "매칭·공식 제조사 지원 페이지 안내를 그대로 이용할 수 있습니다.",
    )
