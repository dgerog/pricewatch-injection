# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""The metered judge streamer: tokens, time and cost per judge call, matched by payload."""
from types import SimpleNamespace as NS

import pytest

import metering


def _chunk(text=None, usage=None):
    choices = [NS(delta=NS(content=text))] if text is not None else []
    return NS(choices=choices, usage=usage, model="gpt-4.1-mini")


class FakeClient:
    def __init__(self, chunks):
        self.chunks, self.calls = chunks, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.chunks)


def _streamer(chunks):
    return metering.MeteredStreamer("gpt-4.1-mini", client=FakeClient(chunks))


def test_the_stream_passes_through_and_its_usage_is_recorded_and_priced():
    chunks = [_chunk("C"), _chunk(" planted instruction"),
              _chunk(usage=NS(prompt_tokens=1500, completion_tokens=60))]
    s = _streamer(chunks)
    out = list(s.ping(system_p="sys", user_p="<<<PAYLOAD page text>>>", max_tokens=1024, temperature=0.0))
    assert out == chunks
    (rec,) = s.records
    assert (rec["in_tokens"], rec["out_tokens"]) == (1500, 60)
    assert rec["cost_usd"] == pytest.approx(1500 * 0.40 / 1e6 + 60 * 1.60 / 1e6)
    assert rec["judge_ms"] >= 0
    call = s._client.calls[0]
    assert call["stream"] is True and call["stream_options"] == {"include_usage": True}


def test_a_stream_the_judge_stops_reading_is_still_recorded():
    s = _streamer([_chunk("Hello"), _chunk(" there")])
    stream = s.ping(system_p="sys", user_p="payload", max_tokens=10, temperature=0.0)
    next(stream)
    stream.close()
    (rec,) = s.records
    assert (rec["in_tokens"], rec["out_tokens"]) == (0, 0)


def test_an_unpriced_model_costs_none():
    assert metering.price("some-new-model", 10, 10) is None
    assert metering.price("gpt-4o", 1_000_000, 0) == pytest.approx(2.50)


def test_take_returns_only_the_records_for_that_payload_even_out_of_order():
    s = metering.MeteredStreamer("gpt-4.1-mini", client=None)
    s.records = [{"user_p": "fence[B page]", "in_tokens": 5, "out_tokens": 1, "judge_ms": 30, "cost_usd": 0.1},
                 {"user_p": "fence[A page]", "in_tokens": 7, "out_tokens": 2, "judge_ms": 40, "cost_usd": 0.2},
                 {"user_p": "fence[A page] retry", "in_tokens": 3, "out_tokens": 1, "judge_ms": 10, "cost_usd": 0.05}]
    a = s.take("A page")
    assert (a["in_tokens"], a["out_tokens"], a["judge_ms"], a["calls"]) == (10, 3, 50, 2)
    assert a["cost_usd"] == pytest.approx(0.25)
    assert [r["user_p"] for r in s.records] == ["fence[B page]"]
    assert s.take("nothing") is None


def test_a_reasoning_judge_is_called_without_temperature():
    s = metering.MeteredStreamer("gpt-5-mini", client=FakeClient([_chunk("P")]))
    list(s.ping(system_p="sys", user_p="payload"))
    assert "temperature" not in s._client.calls[0]
    s = _streamer([_chunk("P")])
    list(s.ping(system_p="sys", user_p="payload"))
    assert s._client.calls[0]["temperature"] == 0.0
