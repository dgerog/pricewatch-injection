# A short course on indirect prompt injection

**Format:** self-paced · **Total time:** ~2 hours · **Level:** any developer working with LLMs or AI agents

This repository is more than a demo. It is a complete, hands-on **course** on one of the most important
weaknesses in AI agents today, **indirect prompt injection**. Over the course you will watch the attack, run
it, break it, read the evidence behind it, and finally learn to test *your own* agents for the same weakness.

Start with the [20-minute video](#the-course-pack), and then work through the modules below at your own pace.

## Who this is for

This course is for anyone who builds, ships, reviews, or secures software that uses an LLM to *do* things,
whether that means calling tools, reading web pages or documents, or acting on their output. No security
background is required, and if you can run a Python script, you can do this course.

## What you'll be able to do

By the end you will be able to:

1. **Explain** what indirect prompt injection is and why the *lethal trifecta* makes AI agents structurally
   exposed.
2. **Demonstrate** the attack live by making an AI agent leak a company secret to a web page it read.
3. **Reason** about why the usual defenses, such as a "confidentiality" prompt, an injection-aware prompt, or
   a value filter, are unreliable, and predict when each one fails.
4. **Read and interpret** a security benchmark, including the leak rate, the security-versus-usefulness
   trade-off, and why "just use a better model" is not a fix.
5. **Apply** the lesson by checking your *own* agent for the same weakness and running automated adversarial
   tests against it continuously.

## The course pack

Everything you need is in this repo (plus the video):

| Material | What it is | Where |
|---|---|---|
| 📺 **Video (20 min)** | the orientation: see the attack, get the one lesson | *(webinar recording — link in the repo release / description)* |
| 🗺️ **`COURSE.md`** | this file — the learning path | you're reading it |
| 🧪 **`LAB.md`** | the guided, hands-on lab with self-checks | [`LAB.md`](LAB.md) |
| 📊 **`benchmark/report.md`** | the full study: 9 models, 5 vendors, the data behind every claim | [`benchmark/report.md`](../benchmark/report.md) |
| 🛠️ **the code** | a full, end-to-end vulnerable agent + attacker storefront + benchmark | `agent/` · `storefront/` · `benchmark/` |
| 📎 **`README.md`** | the plain-English overview and quickstart | [`README.md`](../README.md) |

> The code is deliberately a **complete, working rogue-agent scenario** rather than a toy snippet, so that
> you can see exactly how the attack is executed and how the mitigations are, and aren't, effective.

## The learning path

Work through the modules top to bottom. Each one tells you what to do, which material to use, and how long
it takes.

### Module 0 · Watch (10 min)
Watch the 20-minute video. There is no need to take notes; simply get the shape of the threat and the one
lesson that follows from it: *a system-prompt guardrail cannot be relied on to secure an AI agent.*

### Module 1 · Understand the threat (15 min)
Read `README.md` §1–3 for the scenario and the attack, then read `benchmark/report.md` §2 and §6 for the
trust boundary and the lethal trifecta. **Outcome:** you can explain, in one paragraph, why an agent that
reads private data, reads untrusted content, and can send data out is exposed no matter how it is prompted.
→ *Self-check A in [`LAB.md`](LAB.md#self-checks).*

### Module 2 · Do it — run the attack (20 min)
Complete **Part 1–2 of [`LAB.md`](LAB.md)**, where you set up the project, run the live demo, and watch the
agent leak the secret to the attacker. **Outcome:** you have reproduced the attack and can point to the
exact moment the secret leaves.

### Module 3 · Watch the defenses fail (20 min)
Complete **Part 3 of [`LAB.md`](LAB.md)**, in which you toggle the guardrails and the value filter and switch
models, and then skim `benchmark/report.md` §3. **Outcome:** you can explain why the junior prompt is a
coin-flip, why even the expert prompt fails on at least one model, and why the value filter is beaten by a
trivial encoding.

### Module 4 · Read the evidence (15 min)
Read `benchmark/report.md` §5, the results, which cover the leak-rate table and Figures 3–4, the "no clean
win" figure, and the cost table. **Outcome:** you can read a security benchmark and defend the claim that
*safety is model-dependent and must be measured, not assumed.*
→ *Self-check B in [`LAB.md`](LAB.md#self-checks).*

### Module 5 · Mitigate & transfer — your own agent (30 min)
Complete the **Capstone in [`LAB.md`](LAB.md#part-5--capstone-red-team-your-own-agent)**, where you walk the
lethal-trifecta checklist over an agent you actually work on and identify where the boundary is crossed.
**Outcome:** you can spot the exposure in real code and name the independent controls that would reduce it.

### Module 6 · Go continuous — automate the testing (15 min)  ⭐
You have just red-teamed an agent **by hand**. In the real world you have many agents, they change every
week, and the models update underneath you, so hand-testing cannot keep up. The final step of this course is
to make the testing **automatic and repeatable** with an open-source adversarial-testing CLI, **Humanbound
(`hb`)**:

```bash
pip install humanbound[engine]     # the hb CLI + provider adapters — free, runs locally
```

Then point it at the PriceWatch agent you have been playing with, using the endpoint config described in the
Capstone in `LAB.md`, watch it find the injection **automatically**, and run the same test against *your own*
agent, either locally or in CI:

```bash
hb test --endpoint ./bot-config.json --wait     # adversarially test an agent endpoint
hb posture                                       # see its security posture
hb report -o report.html                         # a shareable report, like the one in this repo
```

`hb` runs entirely locally with no account required, and a **free Humanbound account** lets you track
posture over time and across your fleet. The docs are at
**[docs.humanbound.ai](https://docs.humanbound.ai/)**, and the community is on
**[Discord](https://discord.gg/QFTD6tr9zu)**.

**Outcome, and the point of the whole course:** you do not just *understand* indirect prompt injection, you
also have a repeatable way to **catch it in your own agents, continuously.**

## Where to go next

- Do the **Capstone** in [`LAB.md`](LAB.md) against a real agent, and install **`hb`** to automate it.
- Contribute back by running a model we haven't tested and sending a PR with the numbers (see
  [`CONTRIBUTING.md`](../CONTRIBUTING.md)), since the report is a living, community leaderboard.
- Read the real-world incidents in `benchmark/report.md` §9, EchoLeak and CamoLeak, to see this weakness in
  shipped products.
