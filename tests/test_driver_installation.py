"""드라이버 공식 출처 및 패키지 승인 설치 테스트 (실제 sudo/apt 미실행)."""
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from printer_supporter.driver_installation import (
    DriverInstallError, DriverInstallService, SAMSUNG_SL_M2030W,
    BROLASER_MODELS, official_support_for, package_for_identity,
)
from printer_supporter.identification import PrinterIdentity


def identity(name, *, source="IPP 장치 응답", manufacturer="Brother", model="HL-L2340D series"):
    return PrinterIdentity(
        name=name, manufacturer=manufacturer, model=model, protocol="IPP",
        source=source, driverless="unknown", recommendation="검증 결과",
    )


def make_service(tmp_path, *, installed=False, candidate=True, apt_result=0):
    os_release = tmp_path / "os-release"
    os_release.write_text('ID=debian\nVERSION_ID="12"\n')
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        if args[:2] == ["dpkg-query", "-W"]:
            if installed or (any(x[0][0] == "sudo" for x in calls) and apt_result == 0):
                return CompletedProcess(args, 0, "install ok installed", "")
            return CompletedProcess(args, 1, "", "not installed")
        if args[:2] == ["apt-cache", "policy"]:
            return CompletedProcess(
                args, 0, "Installed: (none)\n  Candidate: 6-3\n"
                if candidate else "Candidate: (none)\n", "",
            )
        if args[:3] == ["sudo", "-n", "apt-get"]:
            return CompletedProcess(args, apt_result, "", "sudo: a password is required" if apt_result else "")
        raise AssertionError(f"unexpected command: {args}")

    return DriverInstallService(runner=runner, os_release=os_release), calls


def test_samsung_specific_official_linux_download_link_and_no_apt(tmp_path):
    samsung = identity(
        "Samsung SL-M2030W", manufacturer="Samsung", model="SL-M2030W",
    )
    title, url, note = official_support_for(samsung)
    assert "SL-M2030W" in title
    assert url == SAMSUNG_SL_M2030W
    assert "Linux" in note
    service, calls = make_service(tmp_path)
    plan = service.plan(samsung)
    assert plan.support_url == SAMSUNG_SL_M2030W
    assert plan.package is None and not plan.can_install
    assert not calls


@pytest.mark.parametrize("name", [
    "Samsung M203x Series", "Samsung SL-M2030", "Samsung SL-M2030W Extra",
])
def test_samsung_related_but_unverified_names_never_claim_exact_driver(tmp_path, name):
    printer = identity(name, manufacturer="Samsung", model=name)
    service, calls = make_service(tmp_path)
    plan = service.plan(printer)
    assert plan.support_url != SAMSUNG_SL_M2030W
    assert plan.support_url == "https://www.samsung.com/sec/support/"
    assert plan.package is None
    assert not calls


def test_brother_exact_model_offers_debian_package(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path)
    plan = service.plan(printer)
    assert plan.package == "printer-driver-brlaser"
    assert plan.can_install
    assert plan.package_status == "available"
    assert "packages.debian.org" in plan.package_note
    assert [command for command, _ in calls] == [
        ["dpkg-query", "-W", "-f=${Status}", "printer-driver-brlaser"],
        ["apt-cache", "policy", "printer-driver-brlaser"],
    ]


@pytest.mark.parametrize("name", [
    "Brother HL-L2340DW series", "Brother HL-L2340D Series Plus",
    "Brother HL-L2300D", "Brother HL-L2340D",
    "Brother HL-L2340DW", "Brother HL-L2340D series Evil",
])
def test_similar_models_are_not_assumed_supported(tmp_path, name):
    printer = identity(name)
    assert package_for_identity(printer) is None
    service, calls = make_service(tmp_path)
    assert not service.plan(printer).can_install
    assert not calls


@pytest.mark.parametrize("source", [
    "검색된 이름(미검증)", "검색된 이름(추정) / IPP 기능 조회", "확인 불가",
])
def test_unverified_socket_or_mdns_name_does_not_offer_automatic_install(tmp_path, source):
    printer = identity("Brother HL-L2340D series", source=source)
    service, calls = make_service(tmp_path)
    assert service.plan(printer).package is None
    assert not calls


def test_package_already_installed_is_not_reinstalled(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path, installed=True)
    plan = service.plan(printer)
    assert plan.package_status == "installed"
    assert not plan.can_install
    assert len(calls) == 1


def test_unavailable_package_does_not_install(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path, candidate=False)
    plan = service.plan(printer)
    assert plan.package_status == "unavailable"
    assert not plan.can_install
    assert not any(x[0][0] == "sudo" for x in calls)


def test_install_requires_explicit_approval_no_command(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path)
    plan = service.plan(printer)
    prior = len(calls)
    with pytest.raises(DriverInstallError, match="사용자 승인"):
        service.install(printer, plan)
    assert len(calls) == prior


def test_install_uses_fixed_allowlisted_package_and_checks_result(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path)
    plan = service.plan(printer)
    message = service.install(printer, plan, approved=True)
    assert "다시 조회" in message
    sudo = [command for command, _ in calls if command[0] == "sudo"]
    assert sudo == [
        ["sudo", "-n", "apt-get", "install", "-y",
         "--no-install-recommends", "printer-driver-brlaser"]
    ]
    assert not any(x[0][0] in {"lp", "lpadmin", "curl", "wget", "bash"} for x in calls)
    assert calls[-1][0][:2] == ["dpkg-query", "-W"]


def test_install_does_not_retry_privilege_failure(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path, apt_result=1)
    plan = service.plan(printer)
    with pytest.raises(DriverInstallError, match="APT 패키지 설치"):
        service.install(printer, plan, approved=True)
    assert sum(cmd[0] == "sudo" for cmd, _ in calls) == 1


def test_mismatched_plan_cannot_install_for_different_printer(tmp_path):
    verified = identity("Brother HL-L2340D series")
    other = identity("Brother HL-L2360D series")
    service, calls = make_service(tmp_path)
    plan = service.plan(verified)
    original = len(calls)
    with pytest.raises(DriverInstallError, match="유효하지"):
        service.install(other, plan, approved=True)
    assert len(calls) == original


def test_non_debian_system_has_no_installable_plan(tmp_path):
    printer = identity("Brother HL-L2340D series")
    service, calls = make_service(tmp_path)
    service.os_release.write_text("ID=fedora\n")
    plan = service.plan(printer)
    assert not plan.can_install
    assert "Debian/Ubuntu" in plan.package_note
    assert not calls


def test_unknown_vendor_never_has_unverified_source_link():
    printer = identity("Random Inkjet 901", manufacturer=None, model="Inkjet 901")
    assert official_support_for(printer)[1] is None
    assert package_for_identity(printer) is None


def test_declared_brother_supported_models_all_allowlist_match():
    for model in BROLASER_MODELS:
        printer = identity("Brother " + model)
        assert package_for_identity(printer) == "printer-driver-brlaser"
