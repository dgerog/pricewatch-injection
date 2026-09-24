# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""What each defence would have done, on the payloads of an unprotected run."""
import itertools

import pytest

import app
from guard import EgressGuard

pytest.importorskip("humanbound_firewall")


def test_the_firewall_stop_rule_is_the_guards_own_block_mode_rule():
    """The run is judged in log mode (everything passes); `would` must be what block mode does."""
    from humanbound_firewall.guard import Guard
    from humanbound_firewall.models import CLASSES, Verdict

    for fail, verdict, cls in itertools.product(("open", "closed"), Verdict, CLASSES):
        enforcing = Guard(mode="block", fail=fail)
        assert app.would_stop(verdict, cls, fail) == enforcing._action(verdict, cls), (fail, verdict, cls)


def test_the_dlp_stops_our_cost_sent_verbatim():
    ev = app.dlp_event("fetch_url", "http://127.0.0.1:8001/collect?v=118.4", EgressGuard(enabled=True))
    assert ev["type"] == "dlp" and ev["would"] == "block" and "118.4" in ev["reason"]
    assert ev["check_ms"] >= 0


def test_the_dlp_lets_the_encoded_cost_through():
    ev = app.dlp_event("fetch_url", "http://127.0.0.1:8001/collect?v=1x1x8x.x4x0", EgressGuard(enabled=True))
    assert ev["would"] == "allow"


def test_firewall_metrics_come_from_the_judge_calls_on_that_payload():
    import metering
    meter = metering.MeteredStreamer("gpt-4.1-mini", client=None)
    meter.records = [{"user_p": "<<<fence>>> the attacker page", "in_tokens": 1500, "out_tokens": 60,
                      "judge_ms": 1400, "cost_usd": 0.000696}]
    m = app.judge_metrics(meter, "the attacker page")
    assert (m["in_tokens"], m["out_tokens"], m["judge_ms"], m["cost_usd"]) == (1500, 60, 1400, 0.000696)
    assert app.judge_metrics(meter, "the attacker page") == {}  # taken once
    assert app.judge_metrics(None, "x") == {}


def test_run_totals_add_up_the_agent_and_each_defence():
    t = app.RunTotals(agent_model="gpt-4o", judge_model="gpt-4.1-mini")
    t.agent_turn({"input_tokens": 1000, "output_tokens": 100})
    t.agent_turn({"input_tokens": 2000, "output_tokens": 50})
    t.firewall({"verdict_ms": 600, "judge_ms": 1400, "in_tokens": 1500, "out_tokens": 60, "cost_usd": 0.0007})
    t.firewall({"verdict_ms": 400, "judge_ms": 900, "in_tokens": 1000, "out_tokens": 40, "cost_usd": 0.0005})
    t.dlp({"check_ms": 0.2})
    ev = t.event()
    assert ev["type"] == "metrics"
    assert ev["agent"]["in_tokens"] == 3000 and ev["agent"]["out_tokens"] == 150
    assert ev["agent"]["cost_usd"] == pytest.approx(3000 * 2.5 / 1e6 + 150 * 10 / 1e6)
    assert ev["firewall"]["n"] == 2 and ev["firewall"]["verdict_ms"] == 1000
    assert ev["firewall"]["cost_usd"] == pytest.approx(0.0012)
    assert ev["dlp"] == {"n": 1, "check_ms": 0.2, "cost_usd": 0.0}


def test_an_unpriced_agent_model_reports_tokens_without_a_cost():
    t = app.RunTotals(agent_model="foundry:some-model", judge_model="gpt-4.1-mini")
    t.agent_turn({"input_tokens": 10, "output_tokens": 1})
    assert t.event()["agent"]["cost_usd"] is None
