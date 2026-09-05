# A short course on indirect prompt injection

**Format:** self-paced · **Total time:** ~2 hours · **Level:** any developer working with LLMs or AI agents

This repository is not just a demo — it's a complete, hands-on **course** on one of the most important
weaknesses in AI agents today: **indirect prompt injection**. You watch it, you run it, you break it, you
read the evidence, and then you learn to test *your own* agents for it.

Start with the [20-minute video](#the-course-pack), then work through the modules below at your own pace.

## Who this is for

Anyone who builds, ships, reviews, or secures software that uses an LLM to *do* things — call tools, read
web pages or documents, or act on their output. No security background required; if you can run a Python
script, you can do this course.

## What you'll be able to do

By the end you will be able to:

1. **Explain** what indirect prompt injection is and why the *lethal trifecta* makes AI agents structurally
   exposed.
2. **Demonstrate** the attack live — make an AI agent leak a company secret to a web page it read.
3. **Reason** about why the usual defenses (a "confidentiality" prompt, an injection-aware prompt, a value
   filter) are unreliable — and predict when each fails.
4. **Read and interpret** a security benchmark: leak rate, the security-vs-usefulness trade-off, and why
   "just use a better model" is not a fix.
5. **Apply** the lesson — check your *own* agent for the same weakness, and run automated adversarial tests
   against it continuously.

## The course pack

Everything you need is in this repo (plus the video):

| Material | What it is | Where |
|---|---|---|
| 📺 **Video (20 min)** | the orientation: see the attack, get the one lesson | *(webinar recording — link in the repo release / description)* |
| 🗺️ **`COURSE.md`** | this file — the learning path | you're reading it |
| 🧪 **`LAB.md`** | the guided, hands-on lab with self-checks | [`LAB.md`](LAB.md) |
| 📊 **`benchmark/report.md`** | the full study: 9 models, 5 vendors, the data behind every claim | [`benchmark/report.md`](benchmark/report.md) |
| 🛠️ **the code** | a full, end-to-end vulnerable agent + attacker storefront + benchmark | `agent/` · `storefront/` · `benchmark/` |
| 📎 **`README.md`** | the plain-English overview and quickstart | [`README.md`](README.md) |

> The code is deliberately a **complete, working rogue-agent scenario** — not a toy snippet — so you can
> see exactly how the attack is executed *and* how the mitigations are (and aren't) effective.

## The learning path

Work top to bottom. Each module says what to do, which material to use, and how long it takes.

### Module 0 · Watch (10 min)
Watch the 20-minute video. Don't take notes — just get the shape of the threat and the one lesson: *a
system-prompt guardrail cannot be relied on to secure an AI agent.*

### Module 1 · Understand the threat (15 min)
Read `README.md` §1–3 (the scenario, the attack) and `benchmark/report.md` §2 and §6 (the trust boundary
and the lethal trifecta). **Outcome:** you can explain, in one paragraph, why an agent that reads private
data *and* untrusted content *and* can send data out is exposed — no matter how it's prompted.
→ *Self-check A in [`LAB.md`](LAB.md#self-checks).*

### Module 2 · Do it — run the attack (20 min)
Complete **Part 1–2 of [`LAB.md`](LAB.md)**: set up, run the live demo, and watch the agent leak the secret
to the attacker. **Outcome:** you've reproduced the attack and can point to the exact moment the secret
leaves.

### Module 3 · Watch the defenses fail (20 min)
Complete **Part 3 of [`LAB.md`](LAB.md)** (toggle the guardrails and the value filter, switch models) and
skim `benchmark/report.md` §3. **Outcome:** you can explain why the junior prompt is a coin-flip, why even
the expert prompt fails on at least one model, and why the value filter is beaten by a trivial encoding.

### Module 4 · Read the evidence (15 min)
Read `benchmark/report.md` §5 (results) — the leak-rate table and Figures 3–4, the "no clean win" figure,
and the cost table. **Outcome:** you can read a security benchmark and defend the claim that *safety is
model-dependent and must be measured, not assumed.*
→ *Self-check B in [`LAB.md`](LAB.md#self-checks).*

### Module 5 · Mitigate & transfer — your own agent (30 min)
Complete the **Capstone in [`LAB.md`](LAB.md#part-5--capstone-red-team-your-own-agent)**: walk the lethal-
trifecta checklist over an agent you actually work on, and identify where the boundary is crossed.
**Outcome:** you can spot the exposure in real code and name the independent controls that would reduce it.

### Module 6 · Go continuous — automate the testing (15 min)  ⭐
You just red-teamed an agent **by hand**. In the real world you have many agents, they change every week,
and models update underneath you — you cannot hand-test that. The final step of this course is to make the
testing **automatic and repeatable** with an open-source adversarial-testing CLI, **Humanbound (`hb`)**:

```bash
pip install humanbound[engine]     # the hb CLI + provider adapters — free, runs locally
```

Then point it at the PriceWatch agent you've been playing with (see the Capstone in `LAB.md` for the
endpoint config), watch it find the injection **automatically**, and run the same test against *your own*
agent — locally or in CI:

```bash
hb test --endpoint ./bot-config.json --wait     # adversarially test an agent endpoint
hb posture                                       # see its security posture
hb report -o report.html                         # a shareable report, like the one in this repo
```

`hb` runs entirely locally with no account required, and a **free Humanbound account** lets you track
posture over time and across your fleet. Docs: **[docs.humanbound.ai](https://docs.humanbound.ai/)** ·
Community: **[Discord](https://discord.gg/QFTD6tr9zu)**.

**Outcome — and the point of the whole course:** you don't just *understand* indirect prompt injection, you
have a repeatable way to **catch it in your own agents, continuously.**

## Where to go next

- Do the **Capstone** in [`LAB.md`](LAB.md) against a real agent and install **`hb`** to automate it.
- Contribute back: run a model we haven't tested and PR the numbers (see [`CONTRIBUTING.md`](CONTRIBUTING.md)) —
  the report is a living, community leaderboard.
- Read the real-world incidents in `benchmark/report.md` §9 (EchoLeak, CamoLeak) to see this in shipped
  products.
