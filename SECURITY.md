# Security Policy

## ⚠️ Read this first: the vulnerability is intentional

PriceWatch is a **deliberately-vulnerable teaching lab**. The prompt-injection
weakness — a hidden instruction on a competitor web page that makes the agent
leak a company secret — **is the point of the project, not a bug**. Please do
**not** file a security report about the agent leaking the secret, the value-DLP
being bypassed by the digit encoding, the missing egress firewall, or any part
of the documented attack. Those behaviors are by design and are described in
[`benchmark/report.md`](benchmark/report.md).

Run PriceWatch **only against the bundled local target**, on a machine you
control. Do not point it at systems or accounts you do not own.

## What we *do* want reported privately

Report privately (not via public issues) if you find something outside the
intended teaching scope, for example:

- a way the harness could harm the host it runs on (e.g. writing outside its
  own directory, arbitrary code execution beyond the intended agent tools);
- credentials, keys, or private data accidentally committed to the repository;
- a supply-chain or dependency issue in the tooling itself;
- anything that could cause real-world harm if a learner ran the lab as
  documented.

## How to report

**Do not open a public GitHub issue for the above.** Instead:

1. **Email** `security@humanbound.ai`, or
2. Use **GitHub Security Advisories** — the *"Report a vulnerability"* button on
   the repository's **Security** tab.

Please include: the affected commit or version, a clear description and impact,
and steps to reproduce (or a proof of concept).

## Our commitment

- We acknowledge reports within **72 hours**.
- We aim to complete initial triage within **7 days**.
- We coordinate a fix and disclosure as promptly as is practical.

Third-party dependency vulnerabilities should also be reported upstream to the
respective projects.
