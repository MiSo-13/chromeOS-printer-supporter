"""설치 실패 시 재확인과 검증된 대체 경로만 제안하는지 확인."""
import pytest

from printer_supporter.driver_recovery import recovery_advice


@pytest.mark.parametrize("issue,text", [
    ("missing", "일치하는 CUPS"),
    ("multiple", "여러 개"),
    ("unavailable", "목록을 읽지"),
    ("no-candidate", "드라이버를 찾지"),
    ("failed", "설치를 완료하지"),
])
def test_recovery_messages_for_different_failures(issue, text):
    guide = recovery_advice(issue, scheme="socket")
    assert text in guide.summary
    assert "다시 확인" in guide.instructions
    assert "PPD 파일" in guide.instructions
    assert "다시 승인" in guide.instructions
    assert not guide.can_try_ipp
    assert not guide.has_cups_choices


@pytest.mark.parametrize("scheme,driverless,expected", [
    ("ipp", "reported", True),
    ("ipps", "candidate", True),
    ("ipp", "unknown", False),
    ("socket", "reported", False),
    ("dnssd", "reported", False),
])
def test_only_ipp_capable_device_can_offer_driverless_fallback(scheme, driverless, expected):
    guide = recovery_advice(
        "missing", scheme=scheme, driverless=driverless, matching_cups_count=0,
    )
    assert guide.can_try_ipp is expected


def test_cups_alternative_only_if_match_is_available():
    without = recovery_advice("missing", matching_cups_count=0)
    with_one = recovery_advice("missing", matching_cups_count=1)
    assert not without.has_cups_choices
    assert with_one.has_cups_choices
    assert "실제 모델과 일치" in with_one.instructions


@pytest.mark.parametrize("error,diagnosis", [
    ("sudo: a password is required", "sudo 권한"),
    ("Temporary failure resolving", "인터넷 연결"),
    ("SHA-256 verification failed", "검증되지 않은"),
    ("unexpected error", "오류 내용"),
])
def test_failure_diagnosis_does_not_try_untrusted_driver(error, diagnosis):
    guide = recovery_advice("failed", error=error, official_support=True)
    assert diagnosis in guide.instructions
    assert "제조사 공식 지원 페이지" in guide.instructions
    assert "다시 승인" in guide.instructions
