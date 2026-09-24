# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""metering.py — what the firewall's judge costs, per judgement.

The firewall package reports a verdict, its time and its explanation, but not tokens. So the demo
hands the firewall a judge streamer of its own: the same OpenAI streaming call the library makes,
with `include_usage`, recording each call's tokens and time.

A record is matched to its Decision by the payload it judged (the judge's user prompt is the payload
fenced), not by order, so two judgements that finish out of order cannot swap their numbers.
"""
import re
import threading
import time

# USD per 1M tokens (input, output), OpenAI list prices, standard tier, as used by the benchmarks
# (benchmark/models/run_benchmark.py, benchmark/firewall/run_firewall_benchmark.py; read 2026-09).
PRICES = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
}

# The library's own judge settings (humanbound_firewall/llm/openai.py): a reasoning model's hidden
# reasoning counts against max_completion_tokens, so it gets headroom on top of the visible budget.
_REASONING_TOKEN_HEADROOM = 8192
_TIMEOUT_S = 90
# Reasoning families reject a non-default temperature.
_REASONING_MODEL = re.compile(r"^(gpt-5|o\d)")


def price(model, in_tokens, out_tokens):
    """USD for one call at list price, or None when the model has no price here."""
    p = PRICES.get(model)
    if p is None:
        return None
    return in_tokens * p[0] / 1e6 + out_tokens * p[1] / 1e6


class MeteredStreamer:
    """A firewall judge streamer (the `ping` interface) that records every call it makes."""

    def __init__(self, model, client=None, api_key=None):
        self.model = model
        self._client = client
        self._api_key = api_key
        self._lock = threading.Lock()
        self.records = []

    def _openai(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def ping(self, system_p, user_p, max_tokens=1024, temperature=0.0):
        t0 = time.perf_counter()
        usage = None
        try:
            stream = self._openai().chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_p}, {"role": "user", "content": user_p}],
                stream=True, stream_options={"include_usage": True}, timeout=_TIMEOUT_S,
                max_completion_tokens=max_tokens + _REASONING_TOKEN_HEADROOM,
                **({} if _REASONING_MODEL.match(self.model) else {"temperature": temperature}))
            for chunk in stream:
                usage = getattr(chunk, "usage", None) or usage
                yield chunk
        finally:  # also when the judge stops reading early: the call still happened
            in_t = int(getattr(usage, "prompt_tokens", 0) or 0)
            out_t = int(getattr(usage, "completion_tokens", 0) or 0)
            with self._lock:
                self.records.append({"user_p": user_p, "in_tokens": in_t, "out_tokens": out_t,
                                     "judge_ms": int((time.perf_counter() - t0) * 1000),
                                     "cost_usd": price(self.model, in_t, out_t)})

    def take(self, payload):
        """Remove and sum the records of the judge calls on this payload (a retry is a second
        call on the same payload). None if there are none (the judge was never called)."""
        if not payload:
            return None
        with self._lock:
            mine = [r for r in self.records if payload in r["user_p"]]
            self.records = [r for r in self.records if payload not in r["user_p"]]
        if not mine:
            return None
        costs = [r["cost_usd"] for r in mine]
        return {"calls": len(mine),
                "in_tokens": sum(r["in_tokens"] for r in mine),
                "out_tokens": sum(r["out_tokens"] for r in mine),
                "judge_ms": sum(r["judge_ms"] for r in mine),
                "cost_usd": None if None in costs else sum(costs)}
