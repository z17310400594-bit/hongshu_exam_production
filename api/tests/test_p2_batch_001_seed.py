from datetime import date

from scripts.p2_batch_001_seed import CPTA_2026_EXAM_DATES, LEGACY_BACKUP, dry_run, parse_copy_table


def test_p2_parses_legacy_cert_basic_as_supported_certificate_catalog():
    rows = parse_copy_table(LEGACY_BACKUP, "cert_basic")
    by_code = {row["cert_id"]: row for row in rows}

    assert len(rows) >= 10
    assert by_code["pharmacist_licensed"]["cert_name"] == "执业药师"
    assert by_code["cls1_constructor"]["cert_name"] == "一级建造师"


def test_p2_dry_run_counts_batch_001_scope():
    stats = dry_run()

    assert stats.certificates >= 10
    assert stats.exam_events == 2
    assert stats.knowledge_points >= 8
    assert stats.eligibility_rules >= 7
    assert stats.questions >= 6


def test_p2_uses_official_cpta_2026_exam_dates_for_selected_certs():
    assert CPTA_2026_EXAM_DATES["cls1_constructor"]["exam_start"] == date(2026, 9, 12)
    assert CPTA_2026_EXAM_DATES["cls1_constructor"]["exam_end"] == date(2026, 9, 13)
    assert CPTA_2026_EXAM_DATES["pharmacist_licensed"]["exam_start"] == date(2026, 10, 31)
    assert CPTA_2026_EXAM_DATES["pharmacist_licensed"]["exam_end"] == date(2026, 11, 1)
