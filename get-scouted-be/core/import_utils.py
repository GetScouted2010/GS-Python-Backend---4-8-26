"""Shared ETL infrastructure for Phase 1 import commands.

Provides:
- A chunked, explicit-dtype CSV reader (`read_csv_chunks` / `read_csv_full`) so no
  import command ever lets pandas silently infer column types (the exact
  int->float upcasting / locale-dependent date-parsing failure mode flagged in
  01-RESEARCH.md's "Don't Hand-Roll" table).
- `resolve_dataset_path`, a single place that maps a dataset filename (including
  the "Compatability Scores/CS_CB_25.csv"-style subpaths) to a real path under
  `settings.DATASET_DIR`.
- `ImportReport`, a structured accumulator for import-run bookkeeping (created/
  updated/flagged row counts, per-(field, issue) grouped counts with a capped
  id sample, and free-form named sections like `club_derivation`) that writes
  both a machine-readable JSON artifact and a human-readable Markdown summary.
  This is the shared object every Phase 1 import command (Plans 04-09) reuses.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from django.conf import settings

DEFAULT_NA_VALUES = ("", "N/A", "NA")
DEFAULT_REPORT_DIR = "core/import_reports"


def resolve_dataset_path(filename: str) -> Path:
    """Resolve a dataset-relative filename (or subpath) against DATASET_DIR.

    Handles subpaths like "Compatability Scores/CS_CB_25.csv" transparently --
    `Path.__truediv__` splits on "/" the same way regardless of nesting depth.
    """
    return Path(settings.DATASET_DIR) / filename


def read_csv_chunks(path, dtypes, chunksize: int = 2000, na_values=DEFAULT_NA_VALUES):
    """Yield DataFrame chunks from `path`, always with an explicit `dtype=` dict.

    Never let pandas infer dtypes for an import path -- explicit dtypes are what
    prevent, e.g., a nullable integer column silently upcasting to float on the
    first NaN it encounters.
    """
    if not dtypes:
        raise ValueError("read_csv_chunks requires an explicit non-empty dtype mapping")
    return pd.read_csv(
        path,
        dtype=dtypes,
        na_values=list(na_values),
        keep_default_na=True,
        chunksize=chunksize,
    )


def read_csv_full(path, dtypes, na_values=DEFAULT_NA_VALUES) -> pd.DataFrame:
    """Read the entire CSV as one DataFrame (for small aggregation passes).

    Same explicit-dtype requirement as `read_csv_chunks` -- used where the whole
    file must be seen at once (e.g. Club/League mode-derivation over Players.csv).
    """
    if not dtypes:
        raise ValueError("read_csv_full requires an explicit non-empty dtype mapping")
    return pd.read_csv(
        path,
        dtype=dtypes,
        na_values=list(na_values),
        keep_default_na=True,
    )


class ImportReport:
    """Accumulates structured results of a single import command run.

    Field issues are grouped by (field, issue) -- NOT one entry per offending
    row -- because several real issues here affect thousands of rows (e.g.
    Contract_expires missing on 7,518/41,708 Players.csv rows) and per-row
    logging would make the report unreadable rather than more useful.
    """

    def __init__(self, source_file: str, source_row_count: int = 0):
        self.source_file = source_file
        self.source_row_count = source_row_count
        self.rows_created = 0
        self.rows_updated = 0
        self.rows_flagged = 0
        self._field_issues: dict[tuple[str, str], Counter] = defaultdict(Counter)
        self._field_issue_samples: dict[tuple[str, str], list] = defaultdict(list)
        self._sections: dict[str, Any] = {}
        self.run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def add_field_issue(self, field: str, issue: str, sample_id=None) -> None:
        """Record one occurrence of `issue` on `field`.

        Increments a (field, issue) counter and appends `sample_id` to that
        pair's sample list, capped at 10 ids -- enough to spot-check without
        spamming the report.
        """
        key = (field, issue)
        self._field_issues[key]["count"] += 1
        if sample_id is not None and len(self._field_issue_samples[key]) < 10:
            self._field_issue_samples[key].append(sample_id)

    def set_counts(self, created: int = 0, updated: int = 0, flagged: int = 0) -> None:
        self.rows_created = created
        self.rows_updated = updated
        self.rows_flagged = flagged

    def add_section(self, name: str, data: dict) -> None:
        """Attach a free-form named section (e.g. `club_derivation`,
        `unresolved_club_names`) to the report."""
        self._sections[name] = data

    def _rate(self, count: int) -> float:
        if not self.source_row_count:
            return 0.0
        return round(count / self.source_row_count, 4)

    def to_dict(self) -> dict:
        field_issues = []
        for (field, issue), counter in self._field_issues.items():
            count = counter["count"]
            field_issues.append(
                {
                    "field": field,
                    "issue": issue,
                    "count": count,
                    "rate": self._rate(count),
                    "sample_ids": list(self._field_issue_samples[(field, issue)]),
                }
            )
        result = {
            "run_at": self.run_at,
            "source_file": self.source_file,
            "source_row_count": self.source_row_count,
            "rows_created": self.rows_created,
            "rows_updated": self.rows_updated,
            "rows_flagged": self.rows_flagged,
            "field_issues": field_issues,
        }
        result.update(self._sections)
        return result

    def _to_markdown(self, data: dict) -> str:
        lines = [
            f"# Import Report: {data['source_file']}",
            "",
            f"- Run at: {data['run_at']}",
            f"- Source row count: {data['source_row_count']}",
            f"- Rows created: {data['rows_created']}",
            f"- Rows updated: {data['rows_updated']}",
            f"- Rows flagged: {data['rows_flagged']}",
            "",
            "## Field Issues",
            "",
        ]
        if data["field_issues"]:
            lines.append("| Field | Issue | Count | Rate | Sample IDs |")
            lines.append("|---|---|---|---|---|")
            for entry in data["field_issues"]:
                samples = ", ".join(str(s) for s in entry["sample_ids"])
                lines.append(
                    f"| {entry['field']} | {entry['issue']} | {entry['count']} | "
                    f"{entry['rate']} | {samples} |"
                )
        else:
            lines.append("None.")

        extra_keys = [
            k
            for k in data
            if k
            not in (
                "run_at",
                "source_file",
                "source_row_count",
                "rows_created",
                "rows_updated",
                "rows_flagged",
                "field_issues",
            )
        ]
        for key in extra_keys:
            lines.append("")
            lines.append(f"## {key}")
            lines.append("")
            lines.append(f"```json\n{json.dumps(data[key], indent=2, default=str)}\n```")

        return "\n".join(lines) + "\n"

    def write(self, dir_path=None) -> tuple[Path, Path]:
        """Write both a JSON artifact and a Markdown summary, returning their paths.

        Creates `dir_path` (default `core/import_reports/`) if it doesn't exist.
        """
        out_dir = Path(dir_path) if dir_path is not None else Path(DEFAULT_REPORT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        entity = Path(self.source_file).stem
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_name = f"{entity}_{timestamp}"

        data = self.to_dict()

        json_path = out_dir / f"{base_name}.json"
        json_path.write_text(json.dumps(data, indent=2, default=str))

        md_path = out_dir / f"{base_name}.md"
        md_path.write_text(self._to_markdown(data))

        return json_path, md_path
