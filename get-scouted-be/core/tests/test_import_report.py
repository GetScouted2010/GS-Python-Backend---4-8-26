"""Tests for core.import_utils.ImportReport (the shared import-report accumulator).

Every Phase 1 import command (Plans 04-09) reuses this class, so its shape --
field_issues grouped by (field, issue) with count/rate/sample_ids, plus
rows_created/updated/flagged and the JSON+Markdown write() output -- is locked
down here first.
"""

from core.import_utils import ImportReport


def test_report_shape(tmp_path):
    report = ImportReport(source_file="Players.csv", source_row_count=100)

    # A few field issues, some repeated to prove grouping-by-(field, issue).
    report.add_field_issue("Foot", "invalid_value:'0'", sample_id=1)
    report.add_field_issue("Foot", "invalid_value:'0'", sample_id=2)
    report.add_field_issue("Foot", "invalid_value:'unknown'", sample_id=3)
    report.add_field_issue("Market_value", "missing_or_zero", sample_id=4)

    report.set_counts(created=95, updated=0, flagged=4)

    report.add_section(
        "club_derivation",
        {
            "distinct_clubs": 5,
            "clubs_with_ambiguous_league": 1,
            "clubs_with_playing_style_coverage": 2,
            "playing_style_coverage_rate": 0.4,
        },
    )

    data = report.to_dict()

    # Top-level keys.
    for key in (
        "run_at",
        "source_file",
        "source_row_count",
        "rows_created",
        "rows_updated",
        "rows_flagged",
        "field_issues",
        "club_derivation",
    ):
        assert key in data

    assert data["source_file"] == "Players.csv"
    assert data["source_row_count"] == 100
    assert data["rows_created"] == 95
    assert data["rows_updated"] == 0
    assert data["rows_flagged"] == 4
    assert data["club_derivation"]["distinct_clubs"] == 5

    # field_issues are grouped by (field, issue), not one entry per row.
    assert len(data["field_issues"]) == 3
    by_key = {(e["field"], e["issue"]): e for e in data["field_issues"]}
    foot_zero = by_key[("Foot", "invalid_value:'0'")]
    assert foot_zero["count"] == 2
    assert foot_zero["rate"] == 0.02
    assert set(foot_zero["sample_ids"]) == {1, 2}
    assert len(foot_zero["sample_ids"]) <= 10

    market_value = by_key[("Market_value", "missing_or_zero")]
    assert market_value["count"] == 1
    assert market_value["sample_ids"] == [4]

    # write() produces both a .json and a .md file.
    json_path, md_path = report.write(tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.suffix == ".json"
    assert md_path.suffix == ".md"

    written = json_path.read_text()
    assert '"field_issues"' in written
    assert '"club_derivation"' in written


def test_field_issue_sample_ids_capped_at_ten():
    report = ImportReport(source_file="Players.csv", source_row_count=50)
    for i in range(15):
        report.add_field_issue("Contract_expires", "missing", sample_id=i)

    data = report.to_dict()
    entry = data["field_issues"][0]
    assert entry["count"] == 15
    assert len(entry["sample_ids"]) == 10


def test_rate_guards_divide_by_zero():
    report = ImportReport(source_file="Empty.csv", source_row_count=0)
    report.add_field_issue("Foot", "missing", sample_id=1)
    data = report.to_dict()
    assert data["field_issues"][0]["rate"] == 0.0
