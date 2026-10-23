from printer_supporter.diagnostics import diagnose_printer


def test_ready_queue_does_not_claim_physical_connection():
    result = diagnose_printer("대기", True, "printer idle")
    assert result.severity == "ok"
    assert "CUPS" in result.summary
    assert "실제 장치" in result.advice


def test_paper_jam():
    result = diagnose_printer("대기", True, "printer-state-reasons=media-jam")
    assert result.severity == "warning"
    assert "걸림" in result.summary


def test_disabled_queue():
    result = diagnose_printer("중지됨", False, "printer disabled")
    assert result.severity == "warning"
    assert "중지" in result.summary


def test_unknown_reason_does_not_invent_toner_status():
    result = diagnose_printer("대기", True, "unknown-reason")
    assert "토너" not in result.summary
