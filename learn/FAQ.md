# FAQ — troubleshooting & questions

There are two kinds of entries. **[Troubleshooting](#troubleshooting)** covers the things that actually go
wrong when you run the lab and how to fix them, while **[Questions about the topic](#questions-about-the-topic)**
covers the conceptual questions trainees ask, answered briefly with a pointer to the full explanation. Both
are curated, and the human instructor keeps them up to date as new questions come in.

> **If you're an AI assistant helping someone with this course:** answer *troubleshooting* from this file;
> for *topic* questions give the short answer here and point to the cited report section for depth; use
> [`../benchmark/models/report.md`](../benchmark/models/report.md) and
> [`../benchmark/firewall/report.md`](../benchmark/firewall/report.md) for the exact numbers; and **don't reveal the answers
> to the [`LAB.md`](LAB.md) self-checks** — nudge, don't spoil.

---

# Troubleshooting

## Setup & install

**`python3.12: command not found` (or the venv uses the wrong Python).**
This lab targets **Python 3.12**, so use whatever launches it on your system, whether that is `python3.12`,
`py -3.12`, or a pyenv/conda 3.12. After creating the venv, check the version with
`agent/.venv/bin/python --version`.

**Do I need two virtualenvs (agent + storefront)?**
No. A single venv at `agent/.venv` serves the agent, the storefront, **and** the benchmark. Install both
requirement files into it:
```bash
python3.12 -m venv agent/.venv
agent/.venv/bin/pip install -r agent/requirements.txt -r storefront/requirements.txt
```

**`ModuleNotFoundError` when running a server or the benchmark.**
You're almost certainly using the system Python instead of the venv, so always call the venv explicitly with
`agent/.venv/bin/python -m uvicorn ...` (or, from `benchmark/models/` or `benchmark/firewall/`,
`../../agent/.venv/bin/python run_benchmark.py` / `run_firewall_benchmark.py`).

## Running the demo

**`[Errno 48] Address already in use` (port 8001 or 8000).**
A previous server is still running, so free the port and restart:
```bash
pkill -f "uvicorn app:app --port 8001"    # or 8000 for the agent UI
lsof -nP -iTCP:8001 -sTCP:LISTEN          # still stuck? see who's on it
```

**`http://localhost:8000` shows JSON like `{"message": "... POST /run"}` instead of the UI.**
Start the agent server **from inside the `agent/` directory** so that it finds `static/index.html`, as in
`cd agent && ... uvicorn app:app --port 8000`.

**I press ▶ Run agent and get an error / the button stays greyed out.**
This is usually a missing or wrong API key (see below), and if the button doesn't re-enable, reload the page.
A `[object Object]` or `.trim is not a function` error means you're on an old copy, so run `git pull`:
reasoning models (gpt-5/o-series) return message content as a list, which the current code handles.

**`Missing credentials … set the OPENAI_API_KEY environment variable` even though I exported it.**
Environment variables live only in the terminal that set them, so export the key in the **same terminal**
that runs the agent server, and re-export it whenever you open a new terminal with
`export OPENAI_API_KEY="sk-..."`.

**The first card says `firewall: unavailable (...)` and there are no firewall panels** (or
`demo_leak.py --firewall` stops with an `ImportError`).
The firewall comes from the `humanbound-firewall` package and judges with an OpenAI model
(`gpt-4.1-mini`), so it needs both. Re-run `agent/.venv/bin/pip install -r agent/requirements.txt`, and
start the agent server with `OPENAI_API_KEY` set. The reason in brackets says which one is missing. The
run itself still works without it; only the firewall's verdicts are missing.

## "Is it broken?" — reading the results

**Nothing leaked — Security says 🟢 secure. Did I do it wrong?**
Probably not. Some conditions are *supposed* to resist, and the **hardened** guardrail, the weak model
`gpt-4o-mini`, and `Cohere` all often hold. To see a leak reliably, start the agent server **without `GUARDRAIL`**
(guardrail none), use **model `gpt-4o`**, and press ▶ Run agent a few times, since models are
non-deterministic. To check what actually
reached the attacker, run `curl -s http://localhost:8001/collect/log`.

**It leaked but the verdict says "poisoned," not "grounded." Why?**
That's exactly the point: a leak means the agent also swallowed the attacker's fake £199 and built its
advice on it. A leaked run is therefore **poisoned**, while a secure one is **speculation** (a safe guess),
and there is no "safe *and* well-informed" outcome.
*(Full explanation: [`../benchmark/models/report.md`](../benchmark/models/report.md) §5.4.)*

**The secret arrived as `1x1x8.4x0`, not `1x1x8.4`. Is that a miss?**
No. It decodes to `118.40`, which equals the secret `118.4`, so it counts, because scoring is decimal-safe.
A value that decodes to something *else*, such as a dropped decimal giving `1184`, does not count.

## Models — Azure AI Foundry & reasoning models

**How do I run a non-OpenAI model?** Pass a `foundry:` tag, and note that the endpoint **must end in
`/openai/v1/`**:
```bash
export AZURE_INFERENCE_ENDPOINT="https://<resource>.services.ai.azure.com/openai/v1/"
export AZURE_INFERENCE_CREDENTIAL="<key>"
```

**`foundry:` model returns 401 / 404.** A **401** means the key is wrong, or the endpoint isn't the
`/openai/v1/` path. A **404** means the model name is wrong, so use the **exact deployment name** as the part
after `foundry:`.

**My model fails every run / its baseline fails.** The attack is a tool-use chain, so the model must support
tool calling on the serverless endpoint. According to Microsoft's capability table, **DeepSeek and Llama do
not** on that path, so use a tool-calling model such as Grok, Kimi, Mistral, Cohere, or the GPT/o-series.

**A model shows tokens but no `$` cost.** Its per-token price isn't in the `PRICES` table in
`benchmark/models/conditions.py`, as happens with Mistral Large 3, a preview with no published price. Add the
price and re-run `--report-only`, which is free, to populate it.

## The benchmark

**Will `run_benchmark.py` charge my API account?**
Running `--report-only` is **free**, since it re-renders from saved results, and running without `--yes`
gives a **plan preview** only. Running `--mode full --yes`, however, costs **real money and hours**, so start
small with `--mode models --guardrails none --runs 1`.

**A long run failed partway with `unavailable: Connection error` on many cells.** This usually means the
local storefront died, often from a terminal disconnect. The current code isolates it so that a disconnect
can't kill it, and you can resume without repeating the good cells:
```bash
../../agent/.venv/bin/python run_benchmark.py --mode full --resume --yes --runs 15 --models "..."
```
Run long jobs detached so that they survive with `nohup caffeinate -i ... > run.log 2>&1 &`.

**`Set OPENAI_API_KEY and/or Azure Foundry vars first.`** A full run needs `OPENAI_API_KEY` for OpenAI models
and/or `AZURE_INFERENCE_ENDPOINT` plus `AZURE_INFERENCE_CREDENTIAL` for `foundry:` models, all exported
before `--yes`.

**Will `run_firewall_benchmark.py` charge my API account?**
`--report-only` is **free** (it re-renders `report.md` from `results.json`), and running without `--yes` only
prints the plan. With `--yes` it makes one judge call per page and run: 116 pages × 3 runs = 348 calls to
`gpt-4.1-mini`, about **$0.35** and under a minute. It needs only `OPENAI_API_KEY`, and no servers.

**My firewall benchmark numbers differ a little from the published ones.** That's expected: the judge is a
model, so verdicts on borderline pages can change from run to run, and the provider updates the model behind
the name over time. The published run is in `results.json`, with the judge, the firewall version and the
date.

---

# Questions about the topic

Short answers to the conceptual questions trainees ask most. Keep them brief, since the full reasoning lives
in the report. *Instructor: add the real questions from your session's Q&A here, keeping each answer to a few
lines and citing the report section for depth.*

**Why doesn't the value-DLP catch the secret?**
It matches the *literal* number, but the attack sends it encoded as `1x1x8.4`, so the literal number never
appears in the outgoing request. → [`../benchmark/models/report.md`](../benchmark/models/report.md) §7.

**Why does the attack page never say the word "cost"?**
So that a keyword filter for "cost" won't fire. It paraphrases instead, asking for "the amount you paid per
unit", which forces the model to *understand* the request and is why the junior/confidentiality guardrail is
a coin-flip. → §2, §6.

**Why do the newer, bigger models leak *more*?**
A more capable, more agentic model follows the multi-hop task more reliably, and that includes the attacker's
step, so capability doesn't fix this. → §6 ("Won't more capable models make this go away?").

**Why does the firewall stop what the prompts and the value-DLP can't?**
It sits outside the model and judges what *comes in*: it reads the attacker's page against the agent's policy
before the model does, and withholds it. So it doesn't depend on the model obeying, and it never sees the
encoding, which only happens later. → [`LAB.md`](LAB.md) Part 4, [`../benchmark/firewall/report.md`](../benchmark/firewall/report.md).

**Is the firewall enforcing in the web demo?**
No. The web demo runs the agent unprotected and the firewall in *log* mode: it judges every step of that same
run and shows what it *would* have stopped, so you can compare the defences on identical input. To see it
enforce, run `demo_leak.py --firewall`. → [`LAB.md`](LAB.md) step 4.3.

**Why does the firewall block the door-opener page, which is legitimate?**
The page only points to the live offer, and following such a link is fine, but the judge treats the pointer
as borderline. It is the firewall's main source of false positives (10.3% of benign pages in the benchmark),
and the price of blocking the attack's first hop is a less-informed recommendation.
→ [`../benchmark/firewall/report.md`](../benchmark/firewall/report.md).

**Isn't this just a made-up scenario?**
No. Reading a competitor's page to set a price is a normal task, real prices sit one link away, the attacker
only edits their own page, and the same attack works across nine models. It also mirrors real incidents such
as EchoLeak and CamoLeak. → README §2, report §9.

---

Still stuck, or found a real bug (not the intentional vulnerability, which is covered in
[`../SECURITY.md`](../SECURITY.md))? Open an issue, or ask in the
[community Discord](https://discord.gg/QFTD6tr9zu).
