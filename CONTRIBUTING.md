# Contributing to PriceWatch

Thanks for your interest. PriceWatch is an educational security lab that was
built to be extended, and this guide walks through the ways you can contribute,
the ground rules that apply, and the workflow we follow.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute (good first contributions)

PriceWatch has three clean extension seams, and each one is an open invitation:

1. **Add a model → PR your numbers.** `agent_core.get_llm()` dispatches on a
   `provider:` prefix, so the whole benchmark is provider-agnostic. Run a model
   we haven't tested yet, regenerate the report, and open a PR with the results.
   The findings in [`benchmark/report.md`](benchmark/report.md) are meant to
   grow into a living, community leaderboard of which models resist the attack,
   so please share the numbers rather than your API keys.

2. **Build a defense → the firewall challenge.** The clean extension point is
   `guard.EgressGuard.check_url(url) → (allowed, reason)`. The baseline there is
   a value-DLP that the digit-interleave encoding is designed to defeat, and the
   challenge is to add an independent control that stops the encoded exfil
   without depending on the model behaving. That might be provenance or taint
   tracking, a destination allowlist, or an injection screen. Add it behind a
   flag so that the benchmark can measure the difference.

3. **Add an attack or a wording.** The single attack-definition point is
   `storefront/templates.py`, and new payloads, new encodings, or new
   core-prompt wordings that broaden the study are all welcome.

Documentation, plain-language explanations, and teaching improvements are just
as valuable, because this is a lab that people learn from.

## Ground rules

- **Keep it a local teaching lab.** Contributions must not turn PriceWatch into
  a tool aimed at systems the user doesn't own. It attacks its own bundled
  target, and it should stay that way. See [SECURITY.md](SECURITY.md).
- **License & third-party code.** This project is Apache-2.0 and no CLA is
  required. Any vendored or copied code must be under a permissive license, which
  means Apache-2.0, MIT, BSD-2/3-Clause, or ISC; code under GPL, AGPL, SSPL, or
  BSL cannot be accepted.
- **SPDX headers.** Every `.py` file carries an SPDX header:
  ```python
  # SPDX-License-Identifier: Apache-2.0
  # Copyright 2026 AI and Me Single-Member Private Company (Humanbound)
  ```
  Add it to new files you create.

## Developer Certificate of Origin (DCO)

All commits must be signed off to certify the [DCO](DCO.md):

```bash
git commit -s -m "your message"
```

This appends a `Signed-off-by: Your Name <you@example.com>` trailer using your
real name and a reachable email, and commits without a sign-off cannot be
merged.

## Development setup

```bash
python3.12 -m venv agent/.venv
agent/.venv/bin/pip install -r agent/requirements.txt -r storefront/requirements.txt
export OPENAI_API_KEY="sk-..."
```

Run the demo and the benchmark as described in the [README](README.md). The
report regenerates for free from the saved results:

```bash
cd benchmark && ../agent/.venv/bin/python run_benchmark.py --report-only
```

## Pull-request workflow

1. Fork the repo and create a branch from `main`, keeping each PR focused on one
   change.
2. Make your change, and sign off every commit (`git commit -s`).
3. If you changed benchmark behavior, regenerate `report.md` with
   `--report-only` and include it in the PR so that reviewers can see the effect.
4. Open the PR with a clear description of what you changed and why. Screenshots
   or the relevant report rows are a helpful addition.

## Filing issues

Use GitHub Issues for bugs, ideas, questions, and reports of the form "I ran
model X, and here are the numbers." For anything that looks like a genuine
security problem outside the intended teaching scope, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.

Thank you for helping people understand and defend against indirect prompt
injection. 🛡️
