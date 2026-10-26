"""프린터별 드라이버 확보 순서를 판단하는 순수 함수.

IPP Everywhere → 이미 설치된 CUPS → 검증된 APT 후보 → 제조사 지원 순서.
패키지 설치, 다운로드 또는 프린터 등록은 이 모듈에서 실행하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from .driver_recommendation import DriverRecommendation
from .driver_installation import DriverInstallPlan


@dataclass(frozen=True)
class Resolution:
    route: str  # ipp | installed | apt | apt-installed | vendor | manual
    summary: str
    details: str
    can_install: bool


def resolve_driver(
    recommended: DriverRecommendation | None,
    plan: DriverInstallPlan | None,
) -> Resolution:
    if recommended and recommended.preferred == "everywhere":
        return Resolution(
            "ipp", "IPP Everywhere 사용 가능",
            "프린터가 지원하는 IPP 기능으로 연결합니다. 별도 드라이버 다운로드가 필요하지 않습니다.",
            False,
        )
    if recommended and recommended.preferred == "model":
        return Resolution(
            "installed", "설치된 CUPS 드라이버 찾음",
            "확인된 드라이버를 선택했습니다. 프린터 등록을 진행할 수 있습니다.",
            False,
        )
    if recommended and recommended.installed_matches:
        return Resolution(
            "installed", "설치된 드라이버 후보 확인 필요",
            "모델 이름의 출처가 미확인되었거나 후보가 여러 개입니다. 목록에서 정확한 모델을 선택하세요.",
            False,
        )
    if plan and plan.can_install and plan.source_kind == "samsung-uld":
        return Resolution(
            "vendor-download", "삼성 공식 Linux 드라이버 다운로드 가능",
            f"출처: {plan.download_url}\n"
            f"SHA-256: {plan.download_sha256}\n"
            "x86_64 전용 CUPS 인쇄 필터·PPD를 설치합니다. "
            "제조사 설치 스크립트는 실행하지 않습니다. 승인 후 다운로드가 시작됩니다.",
            True,
        )
    if plan and plan.can_install:
        return Resolution(
            "apt", f"호환 드라이버 후보: {plan.package}",
            f"패키지 출처: Debian/Ubuntu APT\n"
            f"모델 근거: {plan.package_evidence or '배포판 지원 목록'}\n"
            f"참고: {plan.package_source or '-'}\n"
            "설치 전 내용 확인과 승인이 필요합니다. 설치 후 CUPS 모델을 다시 조회합니다."
            + (f"\\n추가 확인: {plan.additional_notice}" if plan.additional_notice else ""),
            True,
        )
    if plan and plan.package and plan.package_status == "installed":
        return Resolution(
            "apt-installed", f"{plan.package} 설치됨",
            "패키지는 이미 설치됐으나 정확히 일치하는 CUPS 모델을 찾지 못했습니다. "
            "장치 모델/드라이버를 다시 확인하세요."
            + (f"\\n추가 확인: {plan.additional_notice}" if plan.additional_notice else ""),
            False,
        )
    if plan and plan.support_url:
        return Resolution(
            "vendor", "제조사 Linux 드라이버 확인 필요",
            "배포판에서 검증된 호환 패키지를 찾지 못했습니다. "
            "제조사 공식 지원 페이지에서 Linux용 파일 및 CPU 아키텍처를 확인하세요. "
            "검증되지 않은 제조사 설치 스크립트는 실행하지 않습니다.",
            False,
        )
    return Resolution(
        "manual", "드라이버 확인 필요",
        "IPP/CUPS에서 검증된 호환 드라이버를 찾지 못했습니다. "
        "제조사 공식 PPD가 있으면 선택할 수 있습니다.",
        False,
    )
