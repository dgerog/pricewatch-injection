# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""The report shows the two rates, the per-family breakdown and the pages that went wrong."""
import report

RESULTS = {
    "meta": {"date": "2026-09-24", "firewall": "0.3.0", "judge": "gpt-4.1-mini", "runs": 3,
             "pages": {"attack": 72, "adaptive": 15, "benign": 26, "door": 3}, "task": "Reprice?"},
    "summary": {"attack_success_rate": 0.0115, "attack_evaluations": 261, "adaptive_success_rate": 0.0,
                "false_positive_rate": 0.0344, "benign_evaluations": 87, "uncertain": 2,
                "by_family": {"exfil_direct": {"success_rate": 0.0, "evaluations": 12}},
                "attacks_through": [("obf-03", 3)], "benign_withheld": [("benign-07", 3)]},
}


def test_the_report_leads_with_the_two_rates():
    md = report.render(RESULTS)
    assert "**Attack success rate**" in md and "**1.1%**" in md and "261" in md
    assert "**False-positive rate**" in md and "**3.4%**" in md and "87" in md


def test_the_report_says_it_is_ai_assisted_and_computed_from_the_results():
    md = report.render(RESULTS)
    assert "AI-assisted report" in md and "results.json" in md


def test_the_report_names_what_went_wrong_and_how_to_reproduce():
    md = report.render(RESULTS)
    assert "| exfil_direct | 0.0% | 12 |" in md
    assert "`obf-03`: 3" in md and "`benign-07`: 3" in md
    assert "--report-only" in md and "0.3.0" in md


def test_false_positives_that_are_all_door_openers_are_explained():
    results = {**RESULTS, "summary": {**RESULTS["summary"], "benign_withheld": [("door-01", 3)]},
               "evaluations": [{"id": "door-01", "category": "door"}]}
    assert "All of them are door-opener pages" in report.render(results)
    assert "All of them are door-opener pages" not in report.render(RESULTS)  # benign-07 is not one
