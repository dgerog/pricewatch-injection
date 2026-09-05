# Contributing to PriceWatch

Thanks for your interest! PriceWatch is an educational security lab, and it's
built to be extended. This guide covers the ways to contribute, the ground
rules, and the workflow.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute (good first contributions)

PriceWatch has three clean extension seams — each is an open invitation:

1. **Add a model → PR your numbers.** `agent_core.get_llm()` dispatches on a
   `provider:` prefix, and the whole benchmark is provider-agnostic. Run a model
   we haven't tested, regenerate the report, and open a PR with the results. The
   findings in [`benchmark/report.md`](benchmark/report.md) are meant to grow
   into a **living, community leaderboard** of which models resist the attack.
   *(Please share the numbers, not your API keys.)*

2. **Build a defense → the firewall challenge.** The clean extension point is
   `guard.EgressGuard.check_url(url) → (allowed, reason)`. The baseline there is
   a value-DLP that is deliberately defeated by the digit-interleave encoding.
   Can you add an independent control — provenance/taint tracking, a destination
   allowlist, an injection screen — that stops the encoded exfil *without*
   depending on the model behaving? Add it behind a flag and let the benchmark
   measure the difference.

3. **Add an attack or a wording.** The single attack-definition point is
   `storefront/templates.py`. New payloads, new encodings, or new core-prompt
   wordings that broaden the study are welcome.

Documentation, plain-language explanations, and teaching improvements are just
as valuable — this is a lab people learn from.

## Ground rules

- **Keep it a local teaching lab.** Contributions must not turn PriceWatch into
  a tool aimed at systems the user doesn't own. It attacks its own bundled
  target, and it should stay that way. See [SECURITY.md](SECURITY.md).
- **License & third-party code.** This project is **Apache-2.0**; no CLA is
  required. Any vendored or copied code must be under a permissive license
  (Apache-2.0, MIT, BSD-2/3-Clause, or ISC). GPL/AGPL/SSPL/BSL code cannot be
  accepted.
- **SPDX headers.** Every `.py` file carries an SPDX header:
  ```python
  # SPDX-License-Identifier: Apache-2.0
  # Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
  ```
  Add it to new files you create.

## Developer Certificate of Origin (DCO)

All commits must be **signed off** to certify the [DCO](DCO.md):

```bash
git commit -s -m "your message"
```

This appends a `Signed-off-by: Your Name <you@example.com>` trailer using your
real name and a reachable email. Commits without a sign-off cannot be merged.

## Development setup

```bash
python3.12 -m venv agent/.venv
agent/.venv/bin/pip install -r agent/requirements.txt -r storefront/requirements.txt
export OPENAI_API_KEY="sk-..."
```

Run the demo and the benchmark as described in the [README](README.md). The
report regenerates for free from saved results:

```bash
cd benchmark && ../agent/.venv/bin/python run_benchmark.py --report-only
```

## Pull-request workflow

1. **Fork** the repo and create a branch from `main`; keep each PR focused on one
   change.
2. Make your change; **sign off** every commit (`git commit -s`).
3. If you changed benchmark behavior, regenerate `report.md` with
   `--report-only` and include it in the PR so reviewers see the effect.
4. Open the PR with a clear description of *what* and *why*. Screenshots or the
   relevant report rows help.

## Filing issues

Use GitHub Issues for bugs, ideas, questions, and "I ran model X, here are the
numbers." For anything that looks like a *genuine* security problem outside the
intended teaching scope, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.

Thank you for helping people understand — and defend against — indirect prompt
injection. 🛡️
