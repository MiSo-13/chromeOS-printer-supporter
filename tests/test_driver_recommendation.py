"""설치된 CUPS 모델 기반 드라이버 추천의 안전성 테스트."""
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from printer_supporter.discovery import DiscoveredPrinter
from printer_supporter.driver_recommendation import (
    DriverAdvisor, InstalledDriver, parse_installed_drivers,
    matching_installed_drivers, recommend_drivers, safe_model_id,
)
from printer_supporter.identification import PrinterIdentity


def make_identity(
    name="Samsung M203x Series", *, source="IPP 장치 응답",
    driverless="unknown", manufacturer="Samsung", model="M203x Series",
):
    return PrinterIdentity(
        name=name, manufacturer=manufacturer, model=model,
        protocol="IPP", source=source,
        driverless=driverless, recommendation="조회 완료",
    )


def device(scheme="ipp"):
    return DiscoveredPrinter(
        "Samsung M203x Series",
        f"{scheme}://192.168.6.147/ipp/print",
        scheme,
    )


def test_parse_lpinfo_models_excludes_raw_everywhere_and_invalid():
    output = (
        "everywhere IPP Everywhere\n"
        "raw Raw Queue\n"
        "drv:///sample.drv/laserjet.ppd HP LaserJet Series PCL 4/5\n"
        "foomatic:Samsung-M203x_Series.ppd Samsung M203x Series (SPL)\n"
        "foomatic:Samsung-M203x_Series.ppd Samsung M203x Series (SPL)\n"
        "-unsafe Samsung M203x Series\n"
        "garbled\n"
    )
    result = parse_installed_drivers(output)
    assert len(result) == 2
    assert result[1].model_id == "foomatic:Samsung-M203x_Series.ppd"
    assert all(item.model_id not in {"raw", "everywhere"} for item in result)


@pytest.mark.parametrize("value", [
    "", "everywhere", "raw", "-m", "some model", "good\n--bad",
    "x" * 257,
])
def test_reject_invalid_model_ids(value):
    assert not safe_model_id(value)


def test_local_model_exact_match_and_near_model_rejection():
    installed = (
        InstalledDriver("drv:///a.ppd", "Samsung M203x Series (SPL)"),
        InstalledDriver("drv:///b.ppd", "Samsung M2030"),
        InstalledDriver("drv:///c.ppd", "Samsung M2030W"),
        InstalledDriver("drv:///d.ppd", "Samsung M203x Series Plus"),
        InstalledDriver("drv:///e.ppd", "HP M203x Series"),
    )
    assert matching_installed_drivers(make_identity(), installed) == (installed[0],)
    assert matching_installed_drivers(
        make_identity(name="Samsung M2030", model="M2030"), installed,
    ) == (installed[1],)
    assert matching_installed_drivers(
        make_identity(name="Samsung M2030W", model="M2030W"), installed,
    ) == (installed[2],)


def test_driverless_ipp_preferred_without_unverified_certification():
    for status in ("reported", "candidate"):
        advice = recommend_drivers(
            device(), make_identity(driverless=status), (),
        )
        assert advice.preferred == "everywhere"
        assert advice.preferred_model is None
        assert "인쇄" in advice.message
        assert "확인" in advice.catalog_status or "완료" in advice.catalog_status


def test_verified_exactly_one_installed_model_is_recommended():
    installed = (InstalledDriver("drv:///samsung/m203x.ppd", "Samsung M203x Series"),)
    advice = recommend_drivers(device(), make_identity(), installed)
    assert advice.preferred == "model"
    assert advice.preferred_model == installed[0].model_id
    assert advice.verified_model


def test_multiple_matching_drivers_are_not_automatically_selected():
    installed = (
        InstalledDriver("drv:///a.ppd", "Samsung M203x Series"),
        InstalledDriver("drv:///b.ppd", "Samsung M203x Series (SPL)"),
    )
    advice = recommend_drivers(device(), make_identity(), installed)
    assert advice.preferred is None and advice.preferred_model is None
    assert len(advice.installed_matches) == 2
    assert "여러 개" in advice.message


def test_discovered_service_name_is_not_verified_even_with_exact_match():
    installed = (InstalledDriver("drv:///a.ppd", "Samsung M203x Series"),)
    advice = recommend_drivers(
        device("socket"),
        make_identity(source="검색된 이름(미검증)"), installed,
    )
    assert advice.preferred is None
    assert advice.installed_matches == installed
    assert not advice.verified_model
    assert "자동 선택하지 않습니다" in advice.message


def test_unknown_model_never_matches_generic_installed_drivers():
    installed = (InstalledDriver("drv:///samsung.ppd", "Samsung M203x Series"),)
    advice = recommend_drivers(
        device(), make_identity(name="모델 미확인", manufacturer=None, model=None),
        installed,
    )
    assert advice.preferred is None
    assert not advice.installed_matches


def test_unknown_brand_ipp_name_offers_exact_cups_choice_without_auto_selection():
    installed = (
        InstalledDriver("drv:///acme.ppd", "Acme Laser 42"),
        InstalledDriver("drv:///near.ppd", "Acme Laser 420"),
    )
    unknown = make_identity(
        name="Acme Laser 42", manufacturer=None, model=None,
    )
    advice = recommend_drivers(device(), unknown, installed)
    assert advice.installed_matches == (installed[0],)
    assert advice.preferred is None and advice.preferred_model is None
    assert "직접 선택" in advice.message

    unverified = make_identity(
        name="Acme Laser 42", manufacturer=None, model=None,
        source="검색된 이름(미검증)",
    )
    assert not recommend_drivers(device(), unverified, installed).installed_matches


def test_catalog_reads_only_lpinfo_m():
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return CompletedProcess(
            command, 0, "drv:///samsung.ppd Samsung M203x Series\n", "",
        )

    advisor = DriverAdvisor(runner=runner)
    result = advisor.advise(device(), make_identity())
    assert result.preferred == "model"
    assert len(calls) == 1
    assert calls[0][0] == ["lpinfo", "-m"]
    assert calls[0][1]["timeout"] == 20
    assert calls[0][1]["check"] is False


@pytest.mark.parametrize("outcome", ["missing", "timeout", "forbidden"])
def test_catalog_failure_keeps_safe_advice(outcome):
    def runner(command, **kwargs):
        if outcome == "missing":
            raise FileNotFoundError("lpinfo")
        if outcome == "timeout":
            raise TimeoutExpired(command, 20)
        return CompletedProcess(command, 1, "", "lpinfo: Forbidden")

    advice = DriverAdvisor(runner=runner).advise(
        device("socket"), make_identity(source="검색된 이름(미검증)")
    )
    assert advice.preferred is None
    assert advice.installed_matches == ()
    assert "CUPS" in advice.catalog_status
    assert "PPD" in advice.message
