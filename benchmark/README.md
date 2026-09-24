# Benchmarks

Each study lives in its own folder, with its own script, data, and report, so they stay independent.

- **[`models/`](models/)** — the cross-vendor model study: does a prompt guardrail stop the attack, across
  nine models? Start with **[`models/report.md`](models/report.md)**.
- **[`firewall/`](firewall/)** — the firewall benchmark: with the page screened before the agent reads it,
  how often does an attack page still get through (attack success rate), and how often is a benign page
  wrongly withheld (false-positive rate)? Start with **[`firewall/report.md`](firewall/report.md)**.
