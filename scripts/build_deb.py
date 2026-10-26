#!/usr/bin/env python3
"""PyInstaller onedir를 ChromeOS Crostini용 Debian 패키지로 묶습니다."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "chromeos-printer-supporter"
ARCHITECTURES = {"x86_64": "amd64", "aarch64": "arm64"}
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){1,3}$")
DEPENDENCIES = (
    "libc6 (>= 2.35)",
    "cups",
    "cups-client",
    "cups-ipp-utils",
    "libegl1",
    "libgl1",
    "libopengl0",
    "libfontconfig1",
    "libxkbcommon-x11-0",
    "libxcb-cursor0",
    "libxcb-icccm4",
    "libxcb-image0",
    "libxcb-keysyms1",
    "libxcb-render-util0",
    "libxcb-xinerama0",
    "libxcb-xkb1",
)


def version_from_project() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError("배포 버전을 pyproject.toml의 숫자 형태로 지정해 주세요.")
    return version


def architecture_from_host() -> str:
    arch = ARCHITECTURES.get(platform.machine().lower())
    if not arch:
        raise ValueError("이 빌드 환경의 CPU 아키텍처는 지원하지 않습니다.")
    return arch


def create_deb(bundle: Path, output_dir: Path, architecture: str) -> Path:
    host_arch = architecture_from_host()
    if architecture != host_arch:
        raise ValueError(f"빌드 머신({host_arch})과 패키지 아키텍처({architecture})가 다릅니다.")
    bundle = bundle.resolve()
    entry = bundle / PACKAGE
    if not entry.is_file() or not os.access(entry, os.X_OK):
        raise ValueError("PyInstaller onedir 실행 파일을 찾을 수 없습니다.")

    version = version_from_project()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir.resolve() / f"{PACKAGE}_{version}_{architecture}.deb"

    with tempfile.TemporaryDirectory(prefix="chromeos-printer-deb-") as tmp:
        root = Path(tmp) / "package"
        binary_dir = root / "opt" / PACKAGE
        binary_dir.parent.mkdir(parents=True)
        shutil.copytree(bundle, binary_dir, symlinks=True)

        launcher = root / "usr" / "bin" / PACKAGE
        launcher.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "packaging" / PACKAGE, launcher)
        launcher.chmod(0o755)

        desktop = root / "usr" / "share" / "applications" / f"{PACKAGE}.desktop"
        desktop.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "packaging" / f"{PACKAGE}.desktop", desktop)
        desktop.chmod(0o644)

        icon = (
            root / "usr" / "share" / "icons" / "hicolor" / "scalable"
            / "apps" / f"{PACKAGE}.svg"
        )
        icon.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "packaging" / f"{PACKAGE}.svg", icon)
        icon.chmod(0o644)

        control_dir = root / "DEBIAN"
        control_dir.mkdir()
        control = (
            f"Package: {PACKAGE}\n"
            f"Version: {version}\n"
            f"Section: graphics\n"
            f"Priority: optional\n"
            f"Architecture: {architecture}\n"
            f"Maintainer: MiSo-13 <72727535+MiSo-13@users.noreply.github.com>\n"
            f"Homepage: https://github.com/MiSo-13/chromeOS-printer-supporter\n"
            f"Depends: {', '.join(DEPENDENCIES)}\n"
            "Suggests: libreoffice\n"
            "Description: CUPS printer support for ChromeOS Linux (Crostini)\n"
            " Open documents, preview, and manage printers from the Linux app launcher.\n"
        )
        (control_dir / "control").write_text(control, encoding="utf-8")
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(root), str(output)],
            check=True,
        )

    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("dist") / PACKAGE)
    parser.add_argument("--output-dir", type=Path, default=Path("dist") / "deb")
    parser.add_argument("--arch", choices=tuple(ARCHITECTURES.values()))
    args = parser.parse_args()
    try:
        output = create_deb(
            args.bundle, args.output_dir, args.arch or architecture_from_host()
        )
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(output)
    print(output.with_suffix(output.suffix + ".sha256"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
