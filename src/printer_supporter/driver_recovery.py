"""드라이버 설치 실패 후 사용할 수 있는 다음 작업을 제안합니다.

모델이 비슷하다는 이유로 다른 드라이버를 자동 선택하지 않습니다.
재설치·프린터 등록·다운로드는 이 모듈에서 실행하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryAdvice:
    summary: str
    instructions: str
    can_try_ipp: bool
    has_cups_choices: bool


def recovery_advice(
    issue: str,
    *,
    error: str = "",
    scheme: str = "",
    driverless: str = "unknown",
    matching_cups_count: int = 0,
    official_support: bool = False,
) -> RecoveryAdvice:
    """검증된 기능만 대체 경로로 제시하고 위험한 자동 재시도는 하지 않습니다."""
    if issue == "multiple":
        headline = "CUPS 드라이버가 여러 개 발견됐습니다."
        guidance = "기기에 적힌 모델과 일치하는 항목을 직접 골라 주세요."
    elif issue == "missing":
        headline = "설치된 패키지에서 일치하는 CUPS 드라이버를 찾지 못했습니다."
        guidance = "같은 이름의 다른 모델 드라이버를 임의로 설치하지 않습니다."
    elif issue == "unavailable":
        headline = "CUPS 드라이버 목록을 읽지 못했습니다."
        guidance = "CUPS 서비스와 조회 권한을 확인한 뒤 다시 검사해 주세요."
    elif issue == "no-candidate":
        headline = "자동으로 사용할 드라이버를 찾지 못했습니다."
        guidance = "IPP 지원 여부를 확인하거나 제조사에서 제공한 PPD를 선택해 주세요."
    elif issue == "registration-failed":
        headline = "프린터 등록을 완료하지 못했습니다."
        guidance = (
            "먼저 연결 주소와 CUPS 오류를 확인하세요. 드라이버 방식이 맞지 않으면 "
            "확인된 CUPS 드라이버나 제조사 PPD로 바꿔 다시 등록할 수 있습니다."
        )
    else:
        headline = "드라이버 설치를 완료하지 못했습니다."
        lowered = error.casefold()
        if any(term in lowered for term in ("sudo", "password", "permission", "권한")):
            guidance = "sudo 권한을 확인한 뒤 '드라이버 다시 확인'을 눌러 주세요."
        elif any(term in lowered for term in ("resolve", "resolving", "network", "timeout", "connection", "네트워크", "시간 초과")):
            guidance = "Linux의 인터넷 연결을 확인한 뒤 '드라이버 다시 확인'을 눌러 주세요."
        elif any(term in lowered for term in ("sha-256", "해시", "checksum")):
            guidance = "다운로드 파일 검증에 실패했습니다. 검증되지 않은 드라이버는 설치하지 않습니다."
        else:
            guidance = "오류 내용을 확인하고 드라이버를 다시 검사해 주세요."

    can_try_ipp = scheme in {"ipp", "ipps"} and driverless in {"reported", "candidate"}
    choices = matching_cups_count > 0
    options = ["'드라이버 다시 확인'을 누르면 설치 없이 IPP/CUPS/패키지 정보를 새로 조회합니다."]
    if can_try_ipp:
        options.append("IPP 연결도 시도할 수 있습니다. 실제 인쇄 가능 여부는 별도 확인이 필요합니다.")
    if choices:
        options.append("설치된 CUPS 드라이버 목록에서 실제 모델과 일치하는 항목을 선택할 수 있습니다.")
    options.append("호환 PPD 파일을 가지고 있다면 직접 선택할 수 있습니다.")
    if official_support:
        options.append("제조사 공식 지원 페이지에서 Linux용 드라이버도 확인할 수 있습니다.")
    options.append("드라이버 재설치 및 프린터 등록은 각각 다시 승인해야 합니다.")
    return RecoveryAdvice(
        headline, guidance + "\n" + "\n".join(options), can_try_ipp, choices,
    )
