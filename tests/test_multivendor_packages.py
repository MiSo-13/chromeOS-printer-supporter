"""검증된 모델별 Debian 드라이버 탐색, 승인, 안전한 fallback."""
from subprocess import CompletedProcess
import pytest

from printer_supporter.driver_installation import (
    DriverInstallError, DriverInstallService, package_for_identity,
)
from printer_supporter.driver_package_catalog import (
    BROTHER_BR_LASER, SPLIX_MODELS, FOO2ZJS_MODELS,
    GUTENPRINT_MODELS, distro_package_for,
)
from printer_supporter.identification import PrinterIdentity, identity_from_attributes
from printer_supporter.discovery import DiscoveredPrinter


def device(vendor, model, *, source="IPP 장치 응답", name=None):
    return PrinterIdentity(
        name=name or f"{vendor} {model}", manufacturer=vendor,
        model=model, protocol="IPP", source=source,
        driverless="unknown", recommendation="조회됨",
    )


@pytest.mark.parametrize("vendor,model,package", [
    ("Brother", "HL-L2340D series", "printer-driver-brlaser"),
    ("Brother", "DCP-L2540DW", "printer-driver-brlaser"),
    ("Samsung", "ML-1660", "printer-driver-splix"),
    ("Samsung", "M2020 Series", "printer-driver-splix"),
    ("Xerox", "Phaser 3020", "printer-driver-splix"),
    ("Dell", "1100", "printer-driver-splix"),
    ("Lexmark", "X215 MFP", "printer-driver-splix"),
    ("HP", "LaserJet 1020", "printer-driver-foo2zjs"),
    ("Minolta", "magicolor 2300 DL", "printer-driver-foo2zjs"),
    ("Epson", "Stylus Photo R200", "printer-driver-gutenprint"),
    ("Canon", "PIXMA iP4000", "printer-driver-gutenprint"),
])
def test_multiple_vendors_have_specific_repository_packages(vendor, model, package):
    result = distro_package_for(device(vendor, model))
    assert result is not None and result.package == package
    assert result.source_url.startswith("https://")
    assert result.evidence
    assert package_for_identity(device(vendor, model)) == package


@pytest.mark.parametrize("vendor,model", [
    ("Samsung", "SL-M2030W"),  # 제조사 Linux 파일 제공, SpliX 지원 증거 없음
    ("Samsung", "SL-M2030"),  # 유사 제품 추정 금지
    ("Samsung", "ML-1660W"),
    ("Brother", "HL-L2340DW series"),
    ("Epson", "Stylus Photo R2000 Plus"),
    ("Canon", "PIXMA iP4200"),  # Gutenprint experimental
    ("HP", "LaserJet 1021"),
    ("Unknown", "Foo Printer"),
])
def test_unverified_models_not_automatically_assigned(vendor, model):
    assert distro_package_for(device(vendor, model)) is None


def test_requires_ipp_verified_model_and_coherent_make_model():
    base = device("HP", "LaserJet 1020")
    assert distro_package_for(device("HP", "LaserJet 1020", source="검색된 이름(미검증)")) is None
    assert distro_package_for(device("HP", "LaserJet 1020", name="Brother LaserJet 1020")) is None
    assert distro_package_for(device("Samsung", "ML-1660X")) is None
    assert base.name == "HP LaserJet 1020"


def test_broader_than_seven_focus_models():
    models = sum(len(v) for v in SPLIX_MODELS.values())
    models += sum(len(v) for v in FOO2ZJS_MODELS.values())
    models += sum(len(v) for v in GUTENPRINT_MODELS.values())
    models += len(BROTHER_BR_LASER)
    assert models > 100
    assert len(set(SPLIX_MODELS) | set(FOO2ZJS_MODELS)
               | set(GUTENPRINT_MODELS) | {"Brother"}) >= 8


def test_multi_vendor_driver_installation_requires_approval_and_uses_apt(tmp_path):
    path = tmp_path / "os-release"
    path.write_text("ID=debian\nVERSION_ID=12\n")
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
            return CompletedProcess(args, 0, "  Candidate: 5.3\n", "")
        if args[:3] == ["sudo", "-n", "apt-get"]:
            installed = True
            return CompletedProcess(args, 0, "done", "")
        if args == ["lpinfo", "-m"]:
            return CompletedProcess(args, 0, "epson.ppd Epson Stylus Photo R200\n", "")
        raise AssertionError(args)

    installer = DriverInstallService(runner=runner, os_release=path)
    printer = device("Epson", "Stylus Photo R200")
    plan = installer.plan(printer)
    assert plan.package == "printer-driver-gutenprint"
    assert plan.package_source and "gimp-print" in plan.package_source
    assert plan.can_install
    prior = len(calls)
    with pytest.raises(DriverInstallError, match="사용자 승인"):
        installer.install(printer, plan, approved=False)
    assert len(calls) == prior
    installer.install(printer, plan, approved=True)
    assert [x for x in calls if x[0] == "sudo"] == [[
        "sudo", "-n", "apt-get", "install", "-y",
        "--no-install-recommends", "printer-driver-gutenprint",
    ]]
    assert not any(args[0] in {"wget", "curl", "bash", "lpadmin"} for args in calls)


@pytest.mark.parametrize("manufacturer", ["Samsung", "Xerox", "Dell", "Lexmark"])
def test_splix_models_are_brand_scoped(manufacturer):
    one = next(iter(SPLIX_MODELS[manufacturer]))
    assert distro_package_for(device(manufacturer, one)) is not None
    assert distro_package_for(device("HP", one)) is None


def test_legacy_brother_models_remain_supported():
    assert len(BROTHER_BR_LASER) >= 20
    for model in BROTHER_BR_LASER:
        assert package_for_identity(device("Brother", model)) == "printer-driver-brlaser"


@pytest.mark.parametrize("reported_name,vendor,expected_package", [
    ("Dell 1100", "Dell", "printer-driver-splix"),
    ("Minolta magicolor 2300 DL", "Minolta", "printer-driver-foo2zjs"),
    ("Konica Minolta magicolor 2300 DL", "Konica Minolta", "printer-driver-foo2zjs"),
])
def test_ipp_identification_to_driver_lookup(reported_name, vendor, expected_package):
    """실제 IPP 파싱 → 브랜드 인식 → 패키지 후보까지 검증."""
    printer = DiscoveredPrinter(reported_name, "ipp://192.168.1.5/ipp/print", "ipp")
    identity = identity_from_attributes(printer, {
        "printer-make-and-model": (reported_name,),
    })
    assert identity.source == "IPP 장치 응답"
    assert identity.manufacturer == vendor
    assert package_for_identity(identity) == expected_package


def test_konica_minolta_install_allowlist_accepts_verified_model(tmp_path):
    path = tmp_path / "os-release"
    path.write_text("ID=debian\\nVERSION_ID=12\\n".replace("\\n", "\n"))
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
            return CompletedProcess(args, 0, "  Candidate: 5.3\n", "")
        if args[:3] == ["sudo", "-n", "apt-get"]:
            installed = True
            return CompletedProcess(args, 0, "done", "")
        if args == ["lpinfo", "-m"]:
            return CompletedProcess(args, 0, "minolta.ppd Konica Minolta magicolor 2300 DL\n", "")
        raise AssertionError(args)

    installer = DriverInstallService(runner=runner, os_release=path)
    identity = device("Konica Minolta", "magicolor 2300 DL")
    plan = installer.plan(identity)
    assert plan.can_install and plan.package == "printer-driver-foo2zjs"
    with pytest.raises(DriverInstallError, match="사용자 승인"):
        installer.install(identity, plan, approved=False)
    installer.install(identity, plan, approved=True)
    assert [args[-1] for args in calls if args[:3] == ["sudo", "-n", "apt-get"]] == [
        "printer-driver-foo2zjs"
    ]
