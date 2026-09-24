# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""The report re-renders from the saved results exactly as published (no API calls)."""
import json
import re
from pathlib import Path

import report

HERE = Path(__file__).resolve().parent.parent
STAMP = re.compile(r"Generated|code version")  # when and from which commit it was rendered


def _without_stamp(text):
    return [line for line in text.splitlines() if not STAMP.search(line)]


def test_the_report_re_renders_from_full_results_as_published(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "REPORT_PATH", str(tmp_path / "report.md"))
    d = json.loads((HERE / "full_results.json").read_text())
    security = {tuple(k.split("|")): v for k, v in d["security"].items()}
    report._render_full_report(d["baseline"], security, d["models"], d["runs"])
    rendered = (tmp_path / "report.md").read_text()
    assert _without_stamp(rendered) == _without_stamp((HERE / "report.md").read_text())
