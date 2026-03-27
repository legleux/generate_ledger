---
theme: seriph
canvasWidth: 1400
fonts:
  sans: Inter
  mono: JetBrains Mono
class: text-left
---

# generate_ledger

---

## generate_ledger

**generate_ledger: Reproducible XRPL Test Networks**

_From zero -> running an XRPL network in one command_

**Speaker notes:**

- This is a tool for generating XRPL test environments quickly and reproducibly.
- Not just a ledger file — a full runnable network.

---

## Slide 2 — The Problem

**Setting up XRPL test environments is painful**

- Manual ledger construction
- Hand-written configs
- Validator setup is tedious
- Hard to reproduce exact scenarios
- Scaling test data is slow

**Speaker notes:**

- Testing non-trivial scenarios usually means a pile of scripts.
- Reproducibility becomes a problem almost immediately.

---

## Slide 3 — The Pitch

**What this solves**

- Generate a full XRPL test network
- Deterministic + repeatable
- Configurable scenarios (accounts, AMMs, trustlines)
- One CLI → working environment

**Speaker notes:**

- This compresses setup into a single workflow.
- Think “infrastructure as code” for XRPL testnets.

---

## Slide 4 — What It Produces

**Output artifacts**

- `ledger.json` (genesis state)
- `accounts.json`
- `xrpld.cfg` (per validator)
- `docker-compose.yml`

**Speaker notes:**

- This is the key mental model.
- Not just data — something runnable.

---

## Slide 5 — The Happy Path

**30-second workflow**

```bash
uv sync
uv run gen
cd testnet
docker compose up
```

**Speaker notes:**

- Install → generate → run.
- No hidden steps.

---

## Slide 6 — Live Demo

**Demo: Generate + Run**

```bash
uv run gen --accounts 20 --validators 3 --output-dir ./testnet
cd testnet
docker compose up
```

**Show:**

- Generated files
- Docker containers starting

**Speaker notes:**

- Small network for speed.
- Show artifacts, then bring it up.

---

## Slide 7 — Custom Scenarios

**Not just random data**

- Trustlines
- Issued currencies
- AMM pools
- Gateways
- Amendments
- Fee configs

**Speaker notes:**

- This is where it becomes useful.
- You can shape realistic ledger states.

---

## Slide 8 — Example Scenario

**Example: AMM + Trustlines**

```bash
uv run gen \
  --accounts 100 \
  --validators 5 \
  --trustline USD \
  --amm-pool XRP/USD
```

**Speaker notes:**

- Network with issued asset + liquidity pool.
- Immediately usable for testing.

---

## Slide 9 — Architecture

**How it works**

```text
CLI (gen)
   ↓
Generation logic
   ↓
Artifacts (ledger + configs)
   ↓
Docker / xrpld network
```

**Speaker notes:**

- Three layers: CLI → generator → outputs.
- Straightforward pipeline.

---

## Slide 10 — Scale & Performance

**Scaling up**

- Handles large synthetic ledgers
- CPU: roughly linear scaling
- GPU support (CuPy)
- Bottleneck: JSON serialization

**Speaker notes:**

- Generation is fast.
- Writing massive JSON becomes the limiter.

---

## Slide 11 — Developer Experience

**DX matters**

- Python ≥ 3.13
- `uv` for environment + deps
- Typer-based CLI
- Optional GPU support

**Speaker notes:**

- Simple tooling.
- Easy to extend.

---

## Slide 12 — Why This Is Useful

**Real value**

- Reproducible test environments
- Faster experimentation
- Realistic network simulation
- Eliminates manual setup

**Speaker notes:**

- Focus on behavior, not setup.

---

## Slide 13 — Future / Next Steps

**Where this could go**

- Scenario presets
- Visualization tools
- Incremental ledger mutation
- CI integration

**Speaker notes:**

- Move from static generation → dynamic workflows.

---

## Slide 14 — Closing

**Takeaway**

> generate_ledger makes XRPL network setup fast, reproducible, and configurable.

**Speaker notes:**

- Stop here and take questions.

---

## Backup Slide — If Demo Fails

**What you _would_ have seen**

- Generated files (`ledger.json`, configs, compose file)
- Running validator containers

**Speaker notes:**

- “Imagine that worked perfectly.”
- Move on confidently.

---

## Timing Guide

- Slides 1–5 → ~3 min
- Demo → ~4 min
- Slides 7–12 → ~3–4 min
- Buffer → ~1–2 min
