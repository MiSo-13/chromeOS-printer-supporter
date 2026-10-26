"""Samsung SL-M2030W ULD 고정 해시·승인 설치·PPD·필터 안전성."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from subprocess import CompletedProcess
import tarfile
import zipfile

import pytest

from printer_supporter.identification import PrinterIdentity
from printer_supporter import samsung_uld as uld
from printer_supporter.driver_installation import (
    DriverInstallService, DriverInstallError,
)


def identity(*, source="IPP 장치 응답", model="SL-M2030W"):
    return PrinterIdentity(
        name="Samsung " + model, manufacturer="Samsung",
        model=model, protocol="IPP", source=source,
        driverless="unknown", recommendation="조회 완료",
    )


def make_vendor_zip(monkeypatch, ppd=None, filter_data=None):
    filter_data = filter_data or (
        b"\x7fELF\x02\x01" + b"0" * 12 + b"\x3e\x00" + b"binary data"
    )
    ppd = ppd or (
        b'*PPD-Adobe: "4.3"\n'
        b'*ModelName: "Samsung M203x Series"\n'
        b'*cupsFilter:  "application/vnd.cups-raster 0 rastertospl"\n'
    )
    monkeypatch.setattr(uld, "FILTER_SHA256", sha256(filter_data).hexdigest())
    monkeypatch.setattr(uld, "PPD_SHA256", sha256(ppd).hexdigest())
    tarbuf = BytesIO()
    with tarfile.open(fileobj=tarbuf, mode="w:gz") as tar:
        for name, value in ((uld.SOURCE_FILTER, filter_data), (uld.SOURCE_PPD, ppd)):
            info = tarfile.TarInfo(name)
            info.size = len(value)
            tar.addfile(info, BytesIO(value))
        # 파일 목록의 다른 스크립트/바이너리는 절대 설치하지 않습니다.
        info = tarfile.TarInfo("uld/install.sh")
        info.size = len(b"#!/bin/sh\necho unsafe\n")
        tar.addfile(info, BytesIO(b"#!/bin/sh\necho unsafe\n"))
    zipped = BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr(uld.INNER_ARCHIVE, tarbuf.getvalue())
    raw = zipped.getvalue()
    monkeypatch.setattr(uld, "SAMSUNG_ULD_SHA256", sha256(raw).hexdigest())
    return raw, filter_data, ppd


def test_exact_identity_and_architecture(monkeypatch):
    assert uld.supports_samsung_uld(identity())
    assert not uld.supports_samsung_uld(identity(source="검색된 이름(미검증)"))
    assert uld.supports_samsung_uld(identity(source="사용자 확인(명시적 선택)"))
    assert not uld.supports_samsung_uld(identity(model="SL-M2030"))
    monkeypatch.setattr(uld.platform, "machine", lambda: "x86_64")
    assert uld.vendor_architecture_ok()
    monkeypatch.setattr(uld.platform, "machine", lambda: "aarch64")
    assert not uld.vendor_architecture_ok()


def test_archive_extracts_only_pinned_ppd_and_filter(monkeypatch):
    raw, original_filter, ppd = make_vendor_zip(monkeypatch)
    extracted_filter, rewritten = uld.extract_verified_files(raw)
    assert extracted_filter == original_filter
    assert uld.FILTER_NAME.encode() in rewritten
    assert b' 0 rastertospl"' not in rewritten
    assert b"Samsung M203x Series" in rewritten


def test_wrong_sha_and_archive_format_rejected(monkeypatch):
    raw, _, _ = make_vendor_zip(monkeypatch)
    with pytest.raises(uld.VendorDriverError, match="SHA-256"):
        uld.extract_verified_files(raw + b"attack")
    monkeypatch.setattr(uld, "SAMSUNG_ULD_SHA256", sha256(b"not zip").hexdigest())
    with pytest.raises(uld.VendorDriverError, match="압축파일"):
        uld.extract_verified_files(b"not zip")


def test_install_needs_approval_and_does_not_download_without_it(monkeypatch, tmp_path):
    monkeypatch.setattr(uld.platform, "machine", lambda: "x86_64")
    called = []
    with pytest.raises(uld.VendorDriverError, match="승인"):
        uld.install_samsung_uld(
            identity(), approved=False,
            downloader=lambda: called.append("download"),
        )
    assert not called
    monkeypatch.setattr(uld.platform, "machine", lambda: "aarch64")
    with pytest.raises(uld.VendorDriverError, match="x86_64"):
        uld.install_samsung_uld(
            identity(), approved=True, downloader=lambda: called.append("download"),
        )
    assert not called


def test_samsung_vendor_installer_command_source_and_idempotence(monkeypatch, tmp_path):
    monkeypatch.setattr(uld.platform, "machine", lambda: "x86_64")
    raw, filter_data, _ = make_vendor_zip(monkeypatch)
    target = tmp_path / "cups" / uld.FILTER_NAME
    target.parent.mkdir()
    data_dir = tmp_path / "config"
    commands = []
    def run_command(args, **kwargs):
        commands.append(args)
        if args[:4] == ["sudo", "-n", "install", "-m"]:
            Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())
        return CompletedProcess(args, 0, "", "")
    result = uld.install_samsung_uld(
        identity(), approved=True, runner=run_command,
        downloader=lambda: raw, filter_target=target, data_dir=data_dir,
    )
    assert target.read_bytes() == filter_data
    assert "Samsung_M203x_Series.ppd" in result.ppd_path
    assert uld.FILTER_NAME.encode() in Path(result.ppd_path).read_bytes()
    assert commands[0] == [
        "sudo", "-n", "apt-get", "install", "-y", "--no-install-recommends", "libcupsimage2",
    ]
    assert commands[1][:4] == ["sudo", "-n", "install", "-m"]
    assert not any("install.sh" in " ".join(x) for x in commands)
    assert not any("bash" in " ".join(x) for x in commands)
    uld.install_samsung_uld(
        identity(), approved=True, runner=run_command,
        downloader=lambda: raw, filter_target=target, data_dir=data_dir,
    )
    assert len([c for c in commands if c[:3] == ["sudo", "-n", "install"]]) == 1


def test_untrusted_existing_filter_or_ppd_not_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(uld.platform, "machine", lambda: "x86_64")
    raw, filter_data, _ = make_vendor_zip(monkeypatch)
    dest = tmp_path / "filter"
    dest.write_bytes(b"not a verified filter")
    with pytest.raises(uld.VendorDriverError, match="덮어쓰지"):
        uld.install_samsung_uld(
            identity(), approved=True, downloader=lambda: raw,
            filter_target=dest, data_dir=tmp_path / "drivers",
            runner=lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sudo called")),
        )


def test_vendor_plan_and_action_do_not_override_apt_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(uld.platform, "machine", lambda: "x86_64")
    from printer_supporter import driver_installation as module
    monkeypatch.setattr(module, "SAMSUNG_ULD_SHA256", uld.SAMSUNG_ULD_SHA256)
    calls = []
    installer = DriverInstallService(
        runner=lambda *a, **k: (_ for _ in ()).throw(AssertionError("apt lookup")),
        vendor_installer=lambda identified, approved: (
            calls.append((identified.name, approved))
            or uld.SamsungInstallResult("done", "/tmp/M203x.ppd")
        ),
    )
    plan = installer.plan(identity())
    assert plan.source_kind == "samsung-uld" and plan.can_install
    assert plan.download_url == uld.SAMSUNG_ULD_URL
    with pytest.raises(DriverInstallError, match="사용자 승인"):
        installer.install(identity(), plan)
    assert not calls
    done = installer.install(identity(), plan, approved=True)
    assert isinstance(done, uld.SamsungInstallResult)
    assert calls == [("Samsung SL-M2030W", True)]
    monkeypatch.setattr(uld.platform, "machine", lambda: "aarch64")
    blocked = installer.plan(identity())
    assert not blocked.can_install
    with pytest.raises(DriverInstallError, match="유효하지"):
        installer.install(identity(), blocked, approved=True)
