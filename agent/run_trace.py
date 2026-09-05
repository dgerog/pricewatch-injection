# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
"""trace.py (v0.1) — render the agent's full message flow for debugging.

Given the message list from a run, produce a readable trace: the system + human prompts, every
tool CALL (name + args), every tool RESULT (the exact page/DB bytes the model saw, incl. the
injected competitor page), each assistant turn, and — for reasoning models (gpt-5/o-series run
via the Responses API with summary:auto) — the reasoning SUMMARY explaining WHY it chose its tools.
gpt-4o has no reasoning trace; for it the "why" is the pre-tool content + the tool args.
"""


def _reasoning_summary(m):
    """Pull a readable reasoning summary out of an AI message, if the model returned one."""
    ak = getattr(m, "additional_kwargs", None) or {}
    r = ak.get("reasoning")
    if isinstance(r, dict):  # Responses API shape: {"summary": [{"text": ...}, ...]}
        return "\n".join(s.get("text", "") for s in (r.get("summary") or []) if isinstance(s, dict))
    if isinstance(r, str):
        return r
    if ak.get("reasoning_content"):
        return str(ak["reasoning_content"])
    return ""


def _strip_encrypted(content):
    """Drop the opaque encrypted reasoning ciphertext that reasoning models (gpt-5 / o-series via
    the Responses API) return as `encrypted_content` on their content blocks. It is not readable
    evidence — the human-readable reasoning is captured separately as the reasoning summary — and
    leaving it in produces huge base64 blobs that also trip secret scanners. All readable text is
    kept; only the ciphertext field is removed."""
    if isinstance(content, list):
        return [{k: v for k, v in b.items() if k != "encrypted_content"} if isinstance(b, dict) else b
                for b in content]
    return content


def render_messages(messages) -> str:
    """Full ordered trace of one run."""
    out = []
    for idx, m in enumerate(messages):
        mtype = getattr(m, "type", m.__class__.__name__)
        content = _strip_encrypted(getattr(m, "content", ""))
        content = content if isinstance(content, str) else str(content)
        header = f"[{idx}] {mtype.upper()}"
        if mtype == "tool":
            header += f"  (tool={getattr(m, 'name', '?')})"
        out.append(header)
        if content.strip():
            out.append("  content:")
            out.extend("    " + ln for ln in content.splitlines())
        if mtype == "ai":
            summary = _reasoning_summary(m)
            if summary.strip():
                out.append("  reasoning summary:")
                out.extend("    " + ln for ln in summary.splitlines())
            rmeta = getattr(m, "response_metadata", None) or {}
            if rmeta.get("finish_reason"):
                out.append(f"  finish_reason: {rmeta['finish_reason']}")
            if (getattr(m, "additional_kwargs", None) or {}).get("refusal"):
                out.append(f"  refusal: {m.additional_kwargs['refusal']}")
        for tc in (getattr(m, "tool_calls", None) or []):
            out.append(f"  -> TOOL CALL {tc.get('name')}  args={tc.get('args')}")
        out.append("")
    return "\n".join(out)


def fetch_url_calls(messages):
    """URLs the model passed to fetch_url — the exfiltration channel."""
    return [tc.get("args", {}).get("url")
            for m in messages for tc in (getattr(m, "tool_calls", None) or [])
            if tc.get("name") == "fetch_url"]
