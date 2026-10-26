"""IPP → 설치된 CUPS → Debian/Ubuntu APT → 제조사 지원 안내 순서 검사."""
import pytest

from printer_supporter.driver_recommendation import DriverRecommendation, InstalledDriver
from printer_supporter.driver_installation import DriverInstallPlan
from printer_supporter.driver_workflow import resolve_driver


def plan(*, status="available", package="printer-driver-splix", link="https://example.com"):
    return DriverInstallPlan(
        "Samsung", "Samsung ML-1660", "Samsung 지원", link, "모델 공식 페이지",
        package, status, "APT 후보", "https://openprinting.github.io/splix/", "OpenPrinting",
    )


def recommend(preferred=None, installed=(), model=None):
    return DriverRecommendation(
        preferred, model, tuple(installed), "테스트", "설치된 CUPS 확인", True
    )


def test_ipp_takes_precedence_over_apt_candidate():
    r = resolve_driver(recommend("everywhere"), plan())
    assert r.route == "ipp" and not r.can_install
    assert "다운로드가 필요하지" in r.details


def test_preinstalled_matching_cups_driver_precedes_apt():
    matched = InstalledDriver("drv.ppd", "Samsung ML-1660")
    r = resolve_driver(recommend("model", [matched], "drv.ppd"), plan())
    assert r.route == "installed" and not r.can_install


def test_ambiguous_installed_cups_drivers_do_not_trigger_apt_install():
    r = resolve_driver(recommend(None, [
        InstalledDriver("drv1.ppd", "Samsung ML-1660"),
        InstalledDriver("drv2.ppd", "Samsung ML-1660"),
    ]), plan())
    assert r.route == "installed" and not r.can_install
    assert "선택" in r.details


def test_approved_apt_candidate_contains_evidence():
    r = resolve_driver(recommend(), plan())
    assert r.route == "apt" and r.can_install
    assert "printer-driver-splix" in r.summary
    assert "openprinting.github.io" in r.details
    assert "APT" in r.details


def test_installed_apt_package_without_cups_match_is_not_assumed_compatible():
    r = resolve_driver(recommend(), plan(status="installed"))
    assert r.route == "apt-installed" and not r.can_install
    assert "정확히" in r.details


def test_vendor_fallback_for_samsung_sl_m2030w_has_no_install_action():
    p = plan(status="not_applicable", package=None,
             link="https://www.samsung.com/sec/support/model/SL-M2030W/")
    r = resolve_driver(recommend(), p)
    assert r.route == "vendor"
    assert not r.can_install
    assert "제조사" in r.details


def test_unknown_fallback_does_not_guess_driver():
    r = resolve_driver(recommend(), None)
    assert r.route == "manual" and not r.can_install
