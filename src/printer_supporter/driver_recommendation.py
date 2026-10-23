"""설치된 CUPS 드라이버 카탈로그와 IPP 속성 기반의 보수적인 드라이버 추천.

외부 다운로드, 패키지 설치, 프린터 등록 및 인쇄 작업은 수행하지 않습니다.
CUPS에 실제로 등록된 모델 ID만 후보로 제안합니다.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from subprocess import CompletedProcess, TimeoutExpired, run
from typing import Callable

from .discovery import DiscoveredPrinter
from .identification import PrinterIdentity


# lpinfo -m의 첫 항목은 CUPS -m 모델 ID(공백 없음).
# 직접 등록 시에는 별도로 이 목록에 존재하는지 재확인합니다.
_MODEL_ID = re.compile(r"^[A-Za-z0-9][^\s\x00-\x1f]{0,255}$")
_WORD = re.compile(r"[a-z0-9]+")
_ALLOWED_TRAILING = {"spl", "ppd", "foomatic", "driver", "v", "cups", "gutenprint"}


@dataclass(frozen=True)
class InstalledDriver:
    model_id: str
    description: str


@dataclass(frozen=True)
class DriverRecommendation:
    preferred: str | None               # "everywhere" | "model" | None
    preferred_model: str | None
    installed_matches: tuple[InstalledDriver, ...]
    message: str
    catalog_status: str
    verified_model: bool


def safe_model_id(value: str) -> bool:
    return bool(
        _MODEL_ID.fullmatch(value)
        and value.casefold() not in {"everywhere", "raw"}
        and not value.startswith("-")
    )


def parse_installed_drivers(output: str) -> tuple[InstalledDriver, ...]:
    """lpinfo -m 출력의 'ID 설명' 형식을 읽고 동적/범용 모델은 제외."""
    seen = set()
    models = []
    for raw in output.splitlines():
        parts = raw.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        model_id, description = parts
        if not safe_model_id(model_id) or not description.strip():
            continue
        if model_id in seen:
            continue
        seen.add(model_id)
        models.append(InstalledDriver(model_id, description.strip()[:250]))
    return tuple(models)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(text.casefold()))


def _exact_model_match(expected: str, label: str) -> bool:
    """모델명 일치만 허용; M2030과 M2030W를 같은 모델로 추정하지 않음."""
    expected_words = _tokens(expected)
    label_words = _tokens(label)
    if len(expected_words) < 2 or label_words[:len(expected_words)] != expected_words:
        return False
    extra = label_words[len(expected_words):]
    return not extra or all(token in _ALLOWED_TRAILING or token.isdigit() for token in extra)


def matching_installed_drivers(
    identity: PrinterIdentity, installed: tuple[InstalledDriver, ...]
) -> tuple[InstalledDriver, ...]:
    if not identity.manufacturer or not identity.model:
        return ()
    # 모델 이름이 실제 IPP 속성에서 왔는지 여부는 UI 자동 적용 판단에 사용합니다.
    expected = identity.name
    matched = tuple(
        model for model in installed
        if _exact_model_match(expected, model.description)
    )
    return matched[:8]


def recommend_drivers(
    device: DiscoveredPrinter,
    identity: PrinterIdentity,
    installed: tuple[InstalledDriver, ...],
    *,
    catalog_status: str = "설치된 CUPS 드라이버 확인 완료",
) -> DriverRecommendation:
    matches = matching_installed_drivers(identity, installed)
    verified = identity.source == "IPP 장치 응답"
    ipp_possible = device.scheme in {"ipp", "ipps"}

    if ipp_possible and identity.driverless == "reported":
        return DriverRecommendation(
            "everywhere", None, matches,
            "장치가 IPP Everywhere 기능을 보고했습니다. 우선 드라이버리스 연결을 권장합니다. "
            "실제 인쇄 호환성과 인증 여부는 별도로 확인해야 합니다.",
            catalog_status, verified,
        )
    if ipp_possible and identity.driverless == "candidate":
        return DriverRecommendation(
            "everywhere", None, matches,
            "IPP 2.x·PWG Raster로 드라이버리스 연결을 시도할 수 있습니다. "
            "인쇄 성공을 보장하지 않으며 실패 시 설치된 CUPS 모델이나 제조사 드라이버를 확인하세요.",
            catalog_status, verified,
        )
    if verified and len(matches) == 1:
        return DriverRecommendation(
            "model", matches[0].model_id, matches,
            "IPP 장치가 보고한 모델명과 설치된 CUPS 드라이버 설명이 일치합니다. "
            "사용하려면 실제 프린터의 모델과 드라이버 호환성을 확인한 뒤 등록하세요.",
            catalog_status, True,
        )
    if verified and len(matches) > 1:
        return DriverRecommendation(
            None, None, matches,
            "동일한 모델명의 설치된 드라이버가 여러 개 있습니다. "
            "잘못된 드라이버를 자동 선택하지 않으니 목록을 직접 확인하세요.",
            catalog_status, True,
        )
    if matches:
        return DriverRecommendation(
            None, None, matches,
            "설치된 CUPS에서 이름이 일치하는 모델 후보를 찾았습니다. "
            "하지만 모델명은 검색 서비스에서 추정한 값이므로 자동 선택하지 않습니다. "
            "실제 기기 모델과 일치하는지 먼저 확인하세요.",
            catalog_status, False,
        )
    return DriverRecommendation(
        None, None, (),
        "설치된 CUPS에서 정확히 일치하는 드라이버 후보를 확인하지 못했습니다. "
        "IPP 지원 여부를 다시 확인하거나 제조사에서 배포한 호환 PPD를 직접 선택하세요. "
        "이 앱은 임의의 드라이버를 다운로드하지 않습니다.",
        catalog_status, verified,
    )


class DriverAdvisor:
    def __init__(self, runner: Callable[..., CompletedProcess[str]] = run):
        self.runner = runner

    def installed_drivers(self) -> tuple[InstalledDriver, ...]:
        """Crostini CUPS의 로컬 카탈로그만 읽습니다 (네트워크 스캔/설치 없음)."""
        try:
            result = self.runner(
                ["lpinfo", "-m"], capture_output=True, text=True,
                check=False, timeout=20,
            )
        except (OSError, TimeoutExpired) as exc:
            raise RuntimeError("CUPS 드라이버 목록을 읽을 수 없습니다.") from exc
        if result.returncode:
            raise RuntimeError(
                "CUPS 드라이버 목록 접근이 거부되었습니다. lpinfo -m 권한을 확인하세요."
            )
        return parse_installed_drivers(result.stdout)

    def advise(
        self, device: DiscoveredPrinter, identity: PrinterIdentity,
    ) -> DriverRecommendation:
        try:
            installed = self.installed_drivers()
            status = f"설치된 CUPS 드라이버 {len(installed)}개 검사"
        except RuntimeError as exc:
            installed = ()
            status = str(exc)
        return recommend_drivers(device, identity, installed, catalog_status=status)
