# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""app.py (v0.3) — PriceWatch demo agent (web UI). Runs the LOCKED multi-hop cost attack.

Two-server demo: this agent UI on :8000 embeds the storefront (:8001). Press ▶ Ask and watch the
agent chase the door-opener and exfiltrate the unit cost to the attacker's collector.

The DEFENSE toggle here is the PROMPT GUARDRAIL (none -> hardened), NOT the enforced value-DLP guard:
the digit-interleave encoding sails past a value-DLP (proven), so the working defense against this
attack is the injection-aware hardened prompt (which stops the capable models).

Endpoints: GET / (UI), POST /run, GET|POST /guardrail, GET /health.
"""
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, ToolMessage

import db
import agent_core
import guardrails
from agent_core import build_agent, run_job

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


@app.get("/")
async def root():
    idx = _static / "index.html"
    return FileResponse(str(idx)) if idx.exists() else JSONResponse({"message": "PriceWatch v0.3 — POST /run"})


@app.post("/run")
async def run(request: Request):
    body = await request.json() if await request.body() else {}
    sku = body.get("sku") or "SKU-4471"
    rebuild = False
    if body.get("model") and body["model"] != STATE["model"]:
        STATE["model"] = body["model"]; rebuild = True
    if "dlp" in body and bool(body["dlp"]) != STATE["dlp"]:
        STATE["dlp"] = bool(body["dlp"]); rebuild = True   # guard is baked into the fetch tool at build
    if body.get("guardrail") in ("none", "basic", "hardened"):
        STATE["guardrail"] = body["guardrail"]
    _apply_prompt()
    try:
        messages = await run_job(_agent(rebuild=rebuild), sku)
        final = messages[-1]
        recommendation = _text(final.content)
    except Exception as e:
        print(f"[PriceWatch v0.3] agent error: {e}")
        return JSONResponse(status_code=500, content={"error": "agent error", "detail": str(e)})
    return JSONResponse({"sku": sku, "model": STATE["model"], "guardrail": STATE["guardrail"],
                         "dlp": STATE["dlp"], "recommendation": recommendation, "trace": _trace(messages)})


@app.get("/guardrail")
async def guardrail_status():
    return {"guardrail": STATE["guardrail"], "model": STATE["model"]}


@app.post("/guardrail")
async def guardrail_set(request: Request):
    body = await request.json() if await request.body() else {}
    if body.get("guardrail") in ("none", "basic", "hardened"):
        STATE["guardrail"] = body["guardrail"]
    return {"guardrail": STATE["guardrail"]}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "PriceWatch v0.3", "model": STATE["model"],
            "guardrail": STATE["guardrail"], "dlp": STATE["dlp"]}
