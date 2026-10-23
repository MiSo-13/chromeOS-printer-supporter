"""CUPS 프린터 상태를 사용자 친화적인 진단으로 변환합니다."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PrinterDiagnosis:
    severity: str
    summary: str
    advice: str


REASONS = (
    ("media-empty", "용지가 없습니다", "용지를 채우고 프린터 상태를 다시 확인하세요."),
    ("media-jam", "용지 걸림", "프린터에서 걸린 용지를 제거하세요."),
    ("marker-supply-empty", "토너 또는 잉크가 없습니다", "소모품을 교체한 뒤 다시 확인하세요."),
    ("marker-supply-low", "토너 또는 잉크가 부족합니다", "소모품 교체를 준비하세요."),
    ("door-open", "프린터 덮개가 열려 있습니다", "덮개를 닫으세요."),
    ("offline", "프린터가 오프라인 상태입니다", "전원과 네트워크 연결을 확인하세요."),
    ("paused", "인쇄 대기열이 일시 중지되었습니다", "CUPS 대기열 상태와 오류를 확인하세요."),
)


def diagnose_printer(state: str, enabled: bool, detail: str) -> PrinterDiagnosis:
    """장치가 제공하는 상태만 해석합니다. 소모품 수치를 추정하지 않습니다."""
    lowered = detail.lower()
    tokens = set(re.findall(r"[a-z]+(?:-[a-z]+)+", lowered))
    for code, summary, advice in REASONS:
        if code in tokens:
            return PrinterDiagnosis("warning", summary, advice)
    if not enabled or state == "중지됨":
        return PrinterDiagnosis("warning", "인쇄 대기열이 중지되었습니다", "CUPS에서 프린터 사용 여부와 오류 로그를 확인하세요.")
    if "unable to connect" in lowered or "not connected" in lowered:
        return PrinterDiagnosis("warning", "프린터 연결을 확인할 수 없습니다", "프린터 전원, IP 주소 및 네트워크를 확인하세요.")
    if state == "인쇄 중":
        return PrinterDiagnosis("info", "인쇄 작업을 처리 중입니다", "작업이 완료될 때까지 기다리세요.")
    return PrinterDiagnosis("ok", "CUPS 대기열이 준비되었습니다", "실제 장치 연결과 소모품 상태는 프린터가 정보를 제공하는 경우에만 확인할 수 있습니다.")
