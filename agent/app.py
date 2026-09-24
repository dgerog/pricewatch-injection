# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""app.py (v0.3) — PriceWatch demo agent (web UI). Runs the LOCKED multi-hop cost attack.

Two-server demo: this agent UI on :8000 embeds the storefront (:8001). Press ▶ Ask and watch the
agent chase the door-opener and exfiltrate the unit cost to the attacker's collector.

No defence is switched on or off here. The agent runs unprotected, and on the SAME run the two
defences judge every edge's exact payload: the value-DLP checks each outbound URL, and the Humanbound
firewall (in log mode: it judges, it never enforces) judges each tool result before the model reads
it. So the walkthrough shows, on one model trajectory, what went through and what each defence would
have stopped, with the firewall's explanation, latency and cost. Separate runs per defence would
compare the defences on different inputs, since the model reasons differently each time.
The prompt guardrail is the exception: it changes what the model reads, so it is chosen when the
server starts (GUARDRAIL=none|basic|hardened) and holds for every run.

The REAL agent is agent_core.py + tools.py + guard.py. THIS file is only the HTTP shell around it,
and each endpoint below is tagged [CORE] (part of the agent's own surface — what you would ship in a
real deployment) or [DEMO] (added purely to drive the webinar walkthrough UI). If you want to play
with or extend the attack, work in agent_core/tools/guard: every [DEMO] endpoint here can be deleted
without changing the agent or the attack.

Endpoints:
  GET  /             [DEMO] serve the walkthrough web page (static/index.html)
  POST /run          [CORE] invoke the agent for one SKU -> recommendation (+ a debug trace)
  POST /run/stream   [DEMO] the SAME run re-emitted as server-sent events (one per model turn / tool
                            call) so the UI can build the graph step by step — no new agent behaviour
  GET  /health       [CORE] liveness / status
"""
import asyncio
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import db
import agent_core
import guardrails
import metering
from agent_core import build_agent, build_task, run_job
from run_trace import _reasoning_summary, _strip_encrypted

db.init_db()  # OPENAI_API_KEY is passed on the command line (no .env dependency)

STATE = {"agent": None,
         "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
         "guardrail": "none",        # the prompt guardrail, read from GUARDRAIL when the agent is built
         "firewall_mw": None,        # the firewall's LangChain adapter, in log mode
         "meter": None,              # its metered judge: tokens, time and cost per judgement
         "firewall_status": "not built"}  # "on", or "unavailable (<why>)"


def _judge_model():
    return os.getenv("FIREWALL_JUDGE_MODEL", "gpt-4.1-mini")


def _guardrail_level():
    """GUARDRAIL=none|basic|hardened, as set when the server started; anything else is none."""
    level = (os.getenv("GUARDRAIL") or "none").lower()
    return level if level in guardrails.LEVELS else "none"


def _apply_prompt():
    """The system prompt = minimal core + the prompt guardrail chosen at start-up (GUARDRAIL=none|basic|
    hardened, default none). Unlike the DLP and the firewall, a guardrail changes what the model reads,
    so it cannot be judged beside the run: it is a setting of the server, the same for every run.
    run_job reads SYSTEM_PROMPT fresh."""
    STATE["guardrail"] = _guardrail_level()
    agent_core.SYSTEM_PROMPT = agent_core.minimal_prompt() + guardrails.get(STATE["guardrail"])


def _whatif_firewall():
    """The firewall in log mode on a metered judge: it judges every tool result exactly as an
    enforcing firewall would, and passes it on. Returns (middleware, meter, status). Without the
    package or a judge key the run still happens, and the status says why there is no firewall."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, None, "unavailable (no OPENAI_API_KEY for the judge)"
    try:
        meter = metering.MeteredStreamer(_judge_model(), api_key=api_key)
        return agent_core.build_firewall_middleware(mode="log", streamer=meter), meter, "on"
    except Exception as e:  # ImportError when humanbound-firewall is not installed
        return None, None, f"unavailable ({e})"


def _agent(rebuild=False):
    if STATE["agent"] is None or rebuild:
        os.environ["OPENAI_MODEL"] = STATE["model"]
        _apply_prompt()
        # The middleware is kept so a run can subscribe to its decisions (see _run_events).
        STATE["firewall_mw"], STATE["meter"], STATE["firewall_status"] = _whatif_firewall()
        # Nothing enforces: the fetch tool is unguarded (the value-DLP is checked beside it, in
        # _run_events), and the env's GUARD / FIREWALL cannot switch enforcement back on.
        STATE["agent"] = build_agent(guard_enabled=False, firewall_enabled=False,
                                     firewall_middleware=STATE["firewall_mw"])
    return STATE["agent"]


app = FastAPI(title="PriceWatch v0.3 Demo Agent")
_static = Path(__file__).parent / "static"
_static.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


def _text(content):
    """Reasoning models (gpt-5 / o-series via the Responses API) return message content as a LIST of
    blocks, not a string. Flatten to plain text so the UI always gets a string recommendation."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text") or b.get("content") or "")
            else:
                parts.append(str(b))
        return " ".join(p for p in parts if p)
    return str(content)


def _trace(messages):
    steps, id_to_name = [], {}
    for m in messages:
        for tc in (getattr(m, "tool_calls", None) or []):
            if tc.get("id"):
                id_to_name[tc["id"]] = tc["name"]
            steps.append({"type": "tool_call", "name": tc["name"], "args": tc.get("args", {})})
        if isinstance(m, ToolMessage):
            steps.append({"type": "tool_result",
                          "name": id_to_name.get(getattr(m, "tool_call_id", ""), ""),
                          "content": str(m.content)})
    return steps


# [DEMO] Serves the walkthrough web page; the /static mount above serves it and the client/brand logos.
@app.get("/")
async def root():
    idx = _static / "index.html"
    # no-store so a reload during the demo always serves the latest UI (never a cached page).
    if idx.exists():
        return FileResponse(str(idx), headers={"Cache-Control": "no-store"})
    return JSONResponse({"message": "PriceWatch v0.3 — POST /run"})


# ============================ CORE AGENT ============================
# Shared request plumbing + the agent's real endpoint. In a production deployment this (plus
# agent_core/tools/guard) is essentially all you would ship.
def _configure(body):
    """Apply the settings a run request carries; return (sku, question, rebuild)."""
    rebuild = False
    if body.get("model") and body["model"] != STATE["model"]:
        STATE["model"] = body["model"]; rebuild = True
    return body.get("sku") or "SKU-4471", (body.get("question") or "").strip(), rebuild


# [CORE] The agent's real endpoint: run the agent on one SKU and return its recommendation. The `trace`
# it also returns is a debug convenience (the full tool-call list); the recommendation is the product.
@app.post("/run")
async def run(request: Request):
    body = await request.json() if await request.body() else {}
    sku, question, rebuild = _configure(body)
    try:
        messages = await run_job(_agent(rebuild=rebuild), sku, question)
        final = messages[-1]
        recommendation = _text(final.content)
    except Exception as e:
        print(f"[PriceWatch v0.3] agent error: {e}")
        return JSONResponse(status_code=500, content={"error": "agent error", "detail": str(e)})
    return JSONResponse({"sku": sku, "model": STATE["model"],
                         "recommendation": recommendation, "trace": _trace(messages)})


# ==================== DEMO / VISUALISATION (everything below) ====================
# None of the following is the agent. It re-plays a SINGLE /run as server-sent events so the UI can
# build the trust-zone graph one turn at a time, and exposes runtime defense toggles. It calls the same
# run_job/agent as /run — it adds visualisation, not behaviour. Delete it and the attack is unchanged.
_MAX_CHARS = 20000  # a tool result is shown whole in the UI; cap it so one huge page can't flood it


async def _collector_log():
    """What the attacker's collector has received so far (None if the storefront is not running)."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            return (await client.get(f"{db._BASE}/collect/log")).json()
    except Exception:
        return None


# ---- what each defence would have done, on the unprotected run's own payloads ----
def would_stop(verdict, cls, fail="closed"):
    """What an ENFORCING firewall does with this verdict: the Guard's block-mode rule. The run is
    judged in log mode, where every decision passes, so the stop is worked out here (a test pins it
    to the Guard's own rule)."""
    value = getattr(verdict, "value", verdict)
    if value == "block" or (value == "review" and fail == "closed"):
        return "reject" if cls == "request" else "withhold"
    return "pass"


def dlp_event(name, url, guard):
    """The value-DLP's check on the exact URL the model sent. Nothing enforces it: the request goes
    out either way, and this says whether the DLP would have stopped it."""
    import time
    t0 = time.perf_counter()
    allowed, reason = guard.check_url(url)
    return {"type": "dlp", "name": name, "url": url, "would": "allow" if allowed else "block",
            "reason": reason, "check_ms": round((time.perf_counter() - t0) * 1000, 3), "cost_usd": 0.0}


def judge_metrics(meter, payload):
    """Tokens, full judge time and cost of the judge call(s) on this payload ({} if none)."""
    m = meter.take(payload) if meter is not None else None
    if not m:
        return {}
    return {k: m[k] for k in ("judge_ms", "in_tokens", "out_tokens", "cost_usd")}


class RunTotals:
    """What the run cost: the agent's own model turns, and each defence's judgements beside it."""

    def __init__(self, agent_model, judge_model):
        self.agent_model, self.judge_model = agent_model, judge_model
        self.a_in = self.a_out = 0
        self.fw = {"n": 0, "verdict_ms": 0, "judge_ms": 0, "in_tokens": 0, "out_tokens": 0, "cost_usd": 0.0}
        self.fw_priced = True
        self.dl = {"n": 0, "check_ms": 0.0, "cost_usd": 0.0}

    def agent_turn(self, usage):
        usage = usage or {}
        self.a_in += int(usage.get("input_tokens") or 0)
        self.a_out += int(usage.get("output_tokens") or 0)

    def firewall(self, ev):
        self.fw["n"] += 1
        for k in ("verdict_ms", "judge_ms", "in_tokens", "out_tokens"):
            self.fw[k] += int(ev.get(k) or 0)
        if ev.get("cost_usd") is None:
            self.fw_priced = False
        else:
            self.fw["cost_usd"] += ev["cost_usd"]

    def dlp(self, ev):
        self.dl["n"] += 1
        self.dl["check_ms"] += ev.get("check_ms") or 0.0

    def event(self):
        return {"type": "metrics",
                "agent": {"model": self.agent_model, "in_tokens": self.a_in, "out_tokens": self.a_out,
                          "cost_usd": metering.price(self.agent_model, self.a_in, self.a_out)},
                "firewall": {**self.fw, "judge": self.judge_model,
                             "cost_usd": self.fw["cost_usd"] if self.fw_priced else None},
                "dlp": {**self.dl, "check_ms": round(self.dl["check_ms"], 3)}}


async def _run_events(agent, sku, question):
    """One run as a sequence of events: every model turn (its context size, its text, reasoning
    summary and tool calls) and every tool call (its input and its raw output). What the model
    actually received from each tool is reported separately ("seen"), read from the context of the
    next model turn — it differs from the raw output when a defense rewrote it (firewall, DLP).

    Nothing is enforced; both defences judge the run's own payloads. The firewall (log mode) judges
    in the background, so its events arrive as verdicts land, each tagged with its tool_call_id.
    Every firewall Decision (which boundary, what it judged, verdict, category, the judge's
    explanation, and what an enforcing firewall `would` do, with time to verdict, full judge time,
    tokens and cost) is a "firewall" event, and every value-DLP check of an outbound URL is a "dlp"
    event with what it `would` do. A "metrics" event before "final" totals the agent's cost and
    each defence's."""
    task = build_task(sku, question)
    secrets = (db.query_products(sku=sku, columns=["cost", "floor", "margin"]) or [{}])[0]
    mw = STATE.get("firewall_mw")
    decisions = []
    if mw is not None:
        mw.firewall.guard.on_decision = decisions.append  # observe-only; cannot change a verdict
    guard = agent_core.EgressGuard(enabled=True)  # judges every outbound URL; the tool is unguarded
    meter = STATE.get("meter")
    fail = mw.firewall.guard.fail if mw is not None else "closed"
    totals = RunTotals(STATE["model"], _judge_model())
    yield {"type": "start", "sku": sku, "task": task, "system_prompt": agent_core.SYSTEM_PROMPT,
           "model": STATE["model"], "guardrail": STATE["guardrail"],
           "fetch_tool": agent_core._fetch_name(),
           "defences": {"dlp": "value match on every outbound URL (judged, not enforced)",
                        "firewall": STATE["firewall_status"],
                        "firewall_judge": _judge_model() if mw is not None else None,
                        "firewall_fail": fail},
           "firewall_boundaries": mw.boundaries if mw is not None else [],
           "storefront": db._BASE, "secrets": secrets}
    before = await _collector_log()
    seen, turn, final, args_by_run = set(), 0, None, {}

    async def firewall_events():
        while decisions:
            d = decisions.pop(0)
            explanation = await asyncio.to_thread(d.wait_explanation, 10) if d.result else d.explanation
            payload = _text(d.result.prompt) if d.result else ""
            fe = {"type": "firewall", "boundary": (d.boundary or {}).get("name"), "cls": d.cls,
                  "tool_call_id": (d.boundary or {}).get("tool_call_id"),
                  "verdict": d.verdict.value, "category": d.category.value,
                  "would": would_stop(d.verdict, d.cls, fail), "tier": d.tier, "mode": d.mode_applied,
                  "verdict_ms": d.elapsed_ms, "judge_ms": None, "in_tokens": None, "out_tokens": None,
                  "cost_usd": None, **judge_metrics(meter, payload),
                  "letter": getattr(d.result, "raw_letter", "") if d.result else "",
                  "explanation": explanation, "input": payload[:_MAX_CHARS],
                  "posture": d.session.posture}
            if d.result is not None:
                totals.firewall(fe)
            yield fe
    async for ev in agent.astream_events(
            {"messages": [SystemMessage(content=agent_core.SYSTEM_PROMPT), HumanMessage(content=task)]},
            version="v2"):
        kind, data = ev["event"], ev.get("data") or {}
        node = (ev.get("metadata") or {}).get("langgraph_node")
        if kind == "on_chat_model_start" and node == "model":
            # The tools node is done: report the firewall's decisions before the model's next turn.
            # (A tool's own end event fires before the middleware around it has finished judging.)
            async for fe in firewall_events():
                yield fe
            context = (data.get("input") or {}).get("messages") or [[]]
            context = context[0] if context and isinstance(context[0], list) else context
            for m in context:
                if isinstance(m, ToolMessage) and m.tool_call_id not in seen:
                    seen.add(m.tool_call_id)
                    yield {"type": "seen", "id": m.tool_call_id,
                           "content": _text(m.content)[:_MAX_CHARS]}
            turn += 1
            yield {"type": "llm_start", "turn": turn, "context": len(context)}
        elif kind == "on_chat_model_end" and node == "model":
            final = out = data.get("output")
            totals.agent_turn(getattr(out, "usage_metadata", None))
            yield {"type": "llm_end", "turn": turn,
                   "text": _text(_strip_encrypted(getattr(out, "content", ""))),
                   "reasoning": _reasoning_summary(out) if out is not None else "",
                   "tool_calls": [{"id": tc.get("id"), "name": tc["name"], "args": tc.get("args", {})}
                                  for tc in (getattr(out, "tool_calls", None) or [])]}
        elif kind == "on_tool_start":
            args_by_run[ev.get("run_id")] = data.get("input")
            yield {"type": "tool_start", "name": ev.get("name"), "args": data.get("input")}
        elif kind == "on_tool_end":
            out = data.get("output")
            content = out.content if isinstance(out, ToolMessage) else out
            text = _text(content)
            args = args_by_run.pop(ev.get("run_id"), None) or {}
            dl = None
            if ev.get("name") == agent_core._fetch_name() and isinstance(args, dict) and args.get("url"):
                dl = dlp_event(ev.get("name"), args["url"], guard)
                dl["tool_call_id"] = getattr(out, "tool_call_id", None)
                totals.dlp(dl)
            yield {"type": "tool_end", "name": ev.get("name"),
                   "id": getattr(out, "tool_call_id", None),
                   "content": text[:_MAX_CHARS]}
            if dl is not None:  # after the tool's card, so the page can attach it there
                yield dl
            async for fe in firewall_events():
                yield fe
    if mw is not None:
        # Log mode judges off the agent's path, so verdicts can still be landing after the run.
        # Wait for them (a verdict takes ~1 s) so the flow and the totals have every one.
        await asyncio.to_thread(mw.flush, 30)
    async for fe in firewall_events():
        yield fe
    if mw is not None:
        mw.firewall.guard.on_decision = None
    yield totals.event()
    yield {"type": "final",
           "recommendation": _text(_strip_encrypted(getattr(final, "content", ""))) if final else ""}
    after = await _collector_log()
    yield {"type": "collector", "available": after is not None,
           "entries": (after or [])[len(before or []):]}


# [DEMO] The same run as /run, streamed as SSE for the step-by-step graph. Visualisation only.
@app.post("/run/stream")
async def run_stream(request: Request):
    """The run, streamed as server-sent events so the UI can show each step as it happens."""
    body = await request.json() if await request.body() else {}
    sku, question, rebuild = _configure(body)

    async def sse():
        try:
            async for event in _run_events(_agent(rebuild=rebuild), sku, question):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            print(f"[PriceWatch v0.3] agent error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# [CORE] Liveness / status.
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "PriceWatch v0.3", "model": STATE["model"],
            "defences": {"prompt_guardrail": STATE["guardrail"] if STATE["agent"] else _guardrail_level(),
                         "dlp": "judged on every outbound URL (not enforced)",
                         "firewall": STATE["firewall_status"], "firewall_judge": _judge_model()}}
