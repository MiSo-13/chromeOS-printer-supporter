"""선별 안내 모델의 근거/안전한 범용 fallback/문서 일관성 검사."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from printer_supporter.identification import PrinterIdentity
from printer_supporter.support_catalog import (
    FOCUS_PRINTERS, FocusPrinter, assess_printer,
)


def identity(
    manufacturer: str | None, model: str | None,
    source: str = "IPP 장치 응답", name: str | None = None,
):
    return PrinterIdentity(
        name=name or f"{manufacturer or ''} {model or ''}".strip(),
        manufacturer=manufacturer, model=model, protocol="IPP",
        source=source, driverless="unknown", recommendation="조회 완료",
    )


def test_priority_catalog_has_five_manufacturers_seven_unique_models():
    assert len(FOCUS_PRINTERS) == 7
    assert {p.manufacturer for p in FOCUS_PRINTERS} == {
        "Samsung", "Brother", "HP", "Canon", "Epson",
    }
    assert len({p.full_name.casefold() for p in FOCUS_PRINTERS}) == 7
    assert {p.pathway for p in FOCUS_PRINTERS} == {
        "driverless", "distro-package", "vendor-manual",
    }


@pytest.mark.parametrize("entry", FOCUS_PRINTERS, ids=lambda p: p.full_name)
def test_catalog_exact_models_have_evidence_and_no_print_guarantee(entry: FocusPrinter):
    result = assess_printer(identity(entry.manufacturer, entry.model))
    assert result.profile == entry
    assert result.device_verified
    assert "우선 안내 모델" in result.title
    assert "검증되지 않았습니다" in result.detail
    assert entry.evidence in result.detail
    parsed = urlsplit(entry.source_url)
    assert parsed.scheme == "https"
    assert parsed.hostname in {
        "www.samsung.com", "packages.debian.org", "www.pwg.org",
    }


@pytest.mark.parametrize("entry", FOCUS_PRINTERS, ids=lambda p: p.full_name)
def test_name_from_mdns_is_only_hint_not_verified(entry):
    result = assess_printer(identity(
        entry.manufacturer, entry.model, source="검색된 이름(미검증)"
    ))
    assert result.profile == entry
    assert not result.device_verified
    assert "이름 일치" in result.title
    assert "미검증" in result.detail


@pytest.mark.parametrize("manufacturer,model", [
    ("Samsung", "SL-M2030"),
    ("Samsung", "SL-M2030W Plus"),
    ("Samsung", "M203x Series"),
    ("Brother", "HL-L2340DW series"),
    ("HP", "LaserJet Pro M404dn"),
    ("Canon", "imageCLASS MF662Cdw II"),
    ("Epson", "EM-C7100BAM"),
    ("Kyocera", "TASKalfa 2553ci"),
    ("Generic", "IPP Printer"),
])
def test_other_models_use_unchanged_generic_policy(manufacturer, model):
    result = assess_printer(identity(manufacturer, model))
    assert result.profile is None
    assert result.title == "일반 호환성 확인"
    assert "기존 IPP" in result.detail


def test_missing_model_never_claims_focus_profile():
    result = assess_printer(identity(None, None, source="확인 불가"))
    assert result.profile is None
    assert "모델이 확인되지 않았습니다" in result.detail


def test_other_manufacturer_cannot_match_focus_model():
    result = assess_printer(identity("HP", "SL-M2030W", name="HP SL-M2030W"))
    assert result.profile is None


def test_case_insensitive_only_no_suffix_guessing():
    result = assess_printer(identity("hp", "laserjet pro m404DW"))
    assert result.profile is not None
    assert result.profile.manufacturer == "HP"
    assert assess_printer(
        identity("HP", "LaserJet Pro M404dw 2")
    ).profile is None


def test_readme_explains_generic_compatibility_and_links_to_catalog():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "특정 제조사 전용 앱이 아닙니다" in readme
    assert "IPP Everywhere" in readme
    assert "CUPS 드라이버" in readme
    assert "PPD" in readme
    assert "목록에 없는 프린터도" in readme
    assert "docs/SUPPORTED_PRINTERS.md" in readme


def test_priority_models_are_documented_separately_with_verification_status():
    root = Path(__file__).resolve().parents[1]
    docs = (root / "docs" / "SUPPORTED_PRINTERS.md").read_text(encoding="utf-8")
    for entry in FOCUS_PRINTERS:
        assert entry.model in docs
        assert entry.source_url in docs
    assert "일반 호환성 확인" in docs
    assert "우선 안내 모델" in docs
    assert "실기기 검증 완료" in docs
    assert "현재 공개할 실기기 검증 기록은 없습니다" in docs
    assert "목록에 없는 프린터도" in docs


def test_epson_has_verified_official_support_landing_page():
    from printer_supporter.driver_installation import official_support_for

    title, url, note = official_support_for(identity("Epson", "EM-C7100"))
    assert "Epson" in title
    assert url == "https://www.epson.co.kr/sl/s"
    assert "보증하지 않습니다" in note
