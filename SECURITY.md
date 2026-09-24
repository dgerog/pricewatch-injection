# Security Policy

## ⚠️ Read this first: the vulnerability is intentional

PriceWatch is a deliberately-vulnerable teaching lab, and its prompt-injection weakness is the whole point of the project rather than a bug. In the intended scenario, a hidden instruction on a competitor web page causes the agent to leak a company secret. Please do not file a security report about the agent leaking that secret, about the value-DLP being bypassed by the digit encoding, about the missing egress firewall, or about any other part of the documented attack, because all of these behaviors are by design and are described in [`benchmark/models/report.md`](benchmark/models/report.md).

You should also run PriceWatch only against the bundled local target, on a machine that you control, and never point it at systems or accounts you do not own.

## What we *do* want reported privately

If you find something that falls outside this intended teaching scope, please report it privately rather than through public issues. Examples include a way the harness could harm the host it runs on, such as writing outside its own directory or achieving arbitrary code execution beyond the intended agent tools; credentials, keys, or private data that were accidentally committed to the repository; a supply-chain or dependency issue in the tooling itself; and anything else that could cause real-world harm if a learner ran the lab as documented.

## How to report

Please do not open a public GitHub issue for any of the above. Instead, you can either email `security@humanbound.ai`, or use GitHub Security Advisories by clicking the "Report a vulnerability" button on the repository's Security tab.

In your report, please include the affected commit or version, a clear description of the issue and its impact, and steps to reproduce it or a proof of concept.

## Our commitment

We will acknowledge your report within 72 hours and aim to complete initial triage within 7 days, after which we will coordinate a fix and disclosure as promptly as is practical. Third-party dependency vulnerabilities should also be reported upstream to the respective projects.
