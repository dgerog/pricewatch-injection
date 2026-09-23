# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""app.py (v0.3) — PriceWatch demo agent (web UI). Runs the LOCKED multi-hop cost attack.

Two-server demo: this agent UI on :8000 embeds the storefront (:8001). Press ▶ Ask and watch the
agent chase the door-opener and exfiltrate the unit cost to the attacker's collector.

The DEFENSE toggle here is the PROMPT GUARDRAIL (none -> hardened), NOT the enforced value-DLP guard:
the digit-interleave encoding sails past a value-DLP (proven), so the working defense against this
attack is the injection-aware hardened prompt (which stops the capable models).

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
  GET|POST /guardrail[DEMO] flip the prompt-guardrail defense at runtime (a real deploy sets it by config)
  GET  /health       [CORE] liveness / status
"""
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
from agent_core import build_agent, build_task, run_job
from run_trace import _reasoning_summary, _strip_encrypted

db.init_db()  # OPENAI_API_KEY is passed on the command line (no .env dependency)

STATE = {"agent": None,
         "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
         "guardrail": os.getenv("GUARDRAIL", "none"),   # none | basic | hardened (PROMPT defense)
         "dlp": os.getenv("GUARD", "off").lower() in ("on", "1", "true")}  # enforced value-DLP guard


def _apply_prompt():
    """The system prompt = minimal core + the selected guardrail. run_job reads agent_core.SYSTEM_PROMPT
    fresh each call, so a guardrail change needs no agent rebuild."""
    agent_core.SYSTEM_PROMPT = agent_core.minimal_prompt() + guardrails.get(STATE["guardrail"])


def _agent(rebuild=False):
    if STATE["agent"] is None or rebuild:
        os.environ["OPENAI_MODEL"] = STATE["model"]
        STATE["agent"] = build_agent(guard_enabled=STATE["dlp"])  # enforced value-DLP on the fetch boundary
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
    if "dlp" in body and bool(body["dlp"]) != STATE["dlp"]:
        STATE["dlp"] = bool(body["dlp"]); rebuild = True   # guard is baked into the fetch tool at build
    if body.get("guardrail") in ("none", "basic", "hardened"):
        STATE["guardrail"] = body["guardrail"]
    _apply_prompt()
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
    return JSONResponse({"sku": sku, "model": STATE["model"], "guardrail": STATE["guardrail"],
                         "dlp": STATE["dlp"], "recommendation": recommendation, "trace": _trace(messages)})


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


async def _run_events(agent, sku, question):
    """One run as a sequence of events: every model turn (its context size, its text, reasoning
    summary and tool calls) and every tool call (its input and its raw output). What the model
    actually received from each tool is reported separately ("seen"), read from the context of the
    next model turn — it differs from the raw output when a defense rewrote it (the DLP)."""
    task = build_task(sku, question)
    secrets = (db.query_products(sku=sku, columns=["cost", "floor", "margin"]) or [{}])[0]
    yield {"type": "start", "sku": sku, "task": task, "system_prompt": agent_core.SYSTEM_PROMPT,
           "model": STATE["model"], "guardrail": STATE["guardrail"], "dlp": STATE["dlp"],
           "fetch_tool": agent_core._fetch_name(),
           "storefront": db._BASE, "secrets": secrets}
    before = await _collector_log()
    seen, turn, final = set(), 0, None
    async for ev in agent.astream_events(
            {"messages": [SystemMessage(content=agent_core.SYSTEM_PROMPT), HumanMessage(content=task)]},
            version="v2"):
        kind, data = ev["event"], ev.get("data") or {}
        node = (ev.get("metadata") or {}).get("langgraph_node")
        if kind == "on_chat_model_start" and node == "model":
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
            yield {"type": "llm_end", "turn": turn,
                   "text": _text(_strip_encrypted(getattr(out, "content", ""))),
                   "reasoning": _reasoning_summary(out) if out is not None else "",
                   "tool_calls": [{"id": tc.get("id"), "name": tc["name"], "args": tc.get("args", {})}
                                  for tc in (getattr(out, "tool_calls", None) or [])]}
        elif kind == "on_tool_start":
            yield {"type": "tool_start", "name": ev.get("name"), "args": data.get("input")}
        elif kind == "on_tool_end":
            out = data.get("output")
            content = out.content if isinstance(out, ToolMessage) else out
            yield {"type": "tool_end", "name": ev.get("name"),
                   "id": getattr(out, "tool_call_id", None),
                   "content": _text(content)[:_MAX_CHARS]}
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


# [DEMO] Runtime read/toggle of the prompt-guardrail defense — a demo convenience so the UI can flip
# defenses between runs. The defense itself (guardrails.py) is real; a production deploy would pick it
# by config/env, not expose a live toggle.
@app.get("/guardrail")
async def guardrail_status():
    return {"guardrail": STATE["guardrail"], "model": STATE["model"]}


@app.post("/guardrail")
async def guardrail_set(request: Request):
    body = await request.json() if await request.body() else {}
    if body.get("guardrail") in ("none", "basic", "hardened"):
        STATE["guardrail"] = body["guardrail"]
    return {"guardrail": STATE["guardrail"]}


# [CORE] Liveness / status.
@app.get("/health")
async def health():
    return {"status": "ok", "agent": "PriceWatch v0.3", "model": STATE["model"],
            "guardrail": STATE["guardrail"], "dlp": STATE["dlp"]}
