# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""Without --yes the study only prints its plan: no key needed, nothing is run."""
import sys

import run_benchmark as bench


def test_without_yes_it_prints_the_plan_and_runs_nothing(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(bench, "_run_full", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    monkeypatch.setattr(bench, "_measure", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    monkeypatch.setattr(sys, "argv", ["run_benchmark.py"])
    monkeypatch.chdir(bench.HERE)
    bench.main()
    out = capsys.readouterr().out
    assert "PLAN (FULL report)" in out and "--yes" in out


def test_the_study_always_measures_the_undefended_agent(monkeypatch):
    """No value-DLP and no firewall, whatever GUARD / FIREWALL say in the environment."""
    import asyncio

    import agent_core

    monkeypatch.setenv("FIREWALL", "on")
    monkeypatch.setenv("GUARD", "on")
    seen = {}

    class Stop(Exception):
        pass

    def capture(**kwargs):
        seen.update(kwargs)
        raise Stop

    monkeypatch.setattr(agent_core, "build_agent", capture)
    try:
        asyncio.run(bench._one(agent_core, None, "system prompt"))
    except Stop:
        pass
    assert seen == {"guard_enabled": False, "firewall_enabled": False}
