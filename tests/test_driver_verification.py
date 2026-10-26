"""APT 설치 후 CUPS 모델 확인과 일부 HP 모델의 펌웨어 주의 사항."""
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from printer_supporter.driver_installation import AptInstallResult, DriverInstallService
from printer_supporter.driver_verification import firmware_notice, verify_cups_model
from printer_supporter.driver_workflow import resolve_driver
from printer_supporter.identification import PrinterIdentity


def printer(vendor="HP", model="LaserJet 1020"):
    return PrinterIdentity(
        name=f"{vendor} {model}", manufacturer=vendor, model=model,
        protocol="IPP", source="IPP 장치 응답",
        driverless="unknown", recommendation="확인 완료",
    )


def test_cups_check_requires_exact_model():
    identity = printer("Samsung", "ML-1660")
    result = verify_cups_model(
        identity,
        "drv-one Samsung ML-1660\n"
        "drv-other Samsung ML-1660W\n"
        "drv-third HP LaserJet 1020\n",
    )
    assert result.status == "matched"
    assert result.model_id == "drv-one"
    assert "출력 성공" in result.details


def test_cups_check_ambiguous_or_missing():
    identity = printer("Samsung", "ML-1660")
    multiple = verify_cups_model(identity, "a.ppd Samsung ML-1660\nb.ppd Samsung ML-1660\n")
    assert multiple.status == "multiple"
    assert multiple.model_id is None
    assert "선택" in multiple.details
    missing = verify_cups_model(identity, "other.ppd Samsung ML-1660W\n")
    assert missing.status == "missing"
    assert missing.model_id is None
    assert "등록" in missing.details


@pytest.mark.parametrize("model", ["LaserJet 1000", "LaserJet 1005", "LaserJet 1018", "LaserJet 1020"])
def test_only_documented_foo2zjs_hp_models_have_firmware_notice(model):
    assert "펌웨어" in firmware_notice(printer(model=model), "printer-driver-foo2zjs")
    assert firmware_notice(printer(model=model), "printer-driver-splix") is None


def test_other_model_firmware_is_not_assumed():
    assert firmware_notice(printer(model="LaserJet 1022"), "printer-driver-foo2zjs") is None
    assert firmware_notice(printer("Minolta", "magicolor 2300 DL"), "printer-driver-foo2zjs") is None


@pytest.mark.parametrize("catalog_result,expected", [
    (CompletedProcess(["lpinfo", "-m"], 0, "hp.ppd HP LaserJet 1020\n", ""), "matched"),
    (CompletedProcess(["lpinfo", "-m"], 0, "other.ppd HP LaserJet 1018\n", ""), "missing"),
    (CompletedProcess(["lpinfo", "-m"], 1, "", "not authorized"), "unavailable"),
    (TimeoutExpired(["lpinfo", "-m"], 25), "unavailable"),
])
def test_apt_install_checks_local_cups_without_printing(tmp_path, catalog_result, expected):
    os_release = tmp_path / "os-release"
    os_release.write_text("ID=debian\n")
    calls = []
    installed = False

    def runner(args, **kwargs):
        nonlocal installed
        calls.append(args)
        if args[:2] == ["dpkg-query", "-W"]:
            return CompletedProcess(
                args, 0 if installed else 1,
                "install ok installed" if installed else "", "",
            )
        if args[:2] == ["apt-cache", "policy"]:
            return CompletedProcess(args, 0, "Candidate: 1.0\n", "")
        if args[:3] == ["sudo", "-n", "apt-get"]:
            installed = True
            return CompletedProcess(args, 0, "", "")
        if args == ["lpinfo", "-m"]:
            if isinstance(catalog_result, BaseException):
                raise catalog_result
            return catalog_result
        raise AssertionError(args)

    service = DriverInstallService(runner=runner, os_release=os_release)
    identity = printer()
    plan = service.plan(identity)
    assert plan.can_install and "펌웨어" in plan.additional_notice
    assert "펌웨어" in resolve_driver(None, plan).details
    result = service.install(identity, plan, approved=True)
    assert isinstance(result, AptInstallResult)
    assert result.cups_status == expected
    assert "설치는 완료됐습니다" in result.message
    assert "펌웨어" in result.message
    assert calls[-1] == ["lpinfo", "-m"]
    assert not any(cmd[0] in {"lpadmin", "lp", "curl", "wget"} for cmd in calls)


def test_installed_apt_package_still_warns_about_firmware(tmp_path):
    os_release = tmp_path / "os-release"
    os_release.write_text("ID=debian\n")

    def runner(args, **kwargs):
        if args[:2] == ["dpkg-query", "-W"]:
            return CompletedProcess(args, 0, "install ok installed", "")
        raise AssertionError(args)

    plan = DriverInstallService(runner=runner, os_release=os_release).plan(printer())
    assert plan.package_status == "installed"
    assert "펌웨어" in resolve_driver(None, plan).details
