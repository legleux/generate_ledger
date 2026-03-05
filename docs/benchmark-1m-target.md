# Benchmark Target: 1M Accounts with Gateway Trustlines

## Goal

Generate a genesis `ledger.json` with **1,000,000 accounts**, where roughly
half have trustlines to a realistic set of gateways and assets.

## Parameters

| Parameter          | Value                        |
|--------------------|------------------------------|
| Regular accounts   | 1,000,000                    |
| Gateway accounts   | 4                            |
| Assets per gateway | 4                            |
| Total assets       | 16                           |
| Accounts with TLs  | ~500,000 (50% of accounts)   |
| Gateways per acct  | ~2 (half of the 4 gateways)  |
| Assets per acct    | ~8 (2 gateways x 4 assets)   |

### Example Gateways & Assets

| Gateway | Assets                       |
|---------|------------------------------|
| GW0     | USD, EUR, GBP, JPY           |
| GW1     | BTC, ETH, XAU, SGD           |
| GW2     | AUD, CAD, CHF, CNY           |
| GW3     | KRW, BRL, MXN, INR           |

## Ledger Object Count Breakdown

### AccountRoot Objects

| Type             | Count       |
|------------------|-------------|
| Regular accounts | 1,000,000   |
| Gateways         | 4           |
| **Total**        | **1,000,004** |

### RippleState Objects (Trustlines)

Each of the 500,000 trustline-holding accounts connects to ~2 gateways,
subscribing to all 4 assets per gateway = **8 trustlines per account**.

| Calculation                             | Count         |
|-----------------------------------------|---------------|
| 500,000 accounts x 8 trustlines each   | **4,000,000** |

### DirectoryNode Objects

Each account with trustlines needs an **owner directory** (holder side).
Each gateway needs directory pages for all incoming trustlines (issuer side).

**Holder side** (500,000 accounts, 8 entries each):
- DirectoryNode holds up to 32 entries per page
- ceil(8 / 32) = 1 page per holder
- **500,000 DirectoryNode objects**

**Gateway side** (4 gateways, ~1,000,000 trustlines each):
- Each gateway has ~250,000 connecting accounts x 4 assets = 1,000,000 entries
- ceil(1,000,000 / 32) = 31,250 pages per gateway
- 4 gateways x 31,250 = **125,000 DirectoryNode objects**

**Remaining 500,000 accounts** (no trustlines):
- No owner directory needed (OwnerCount = 0, no DirectoryNode created)

| Type                    | Count       |
|-------------------------|-------------|
| Holder directories      | 500,000     |
| Gateway directories     | 125,000     |
| **Total DirectoryNode** | **625,000** |

### Grand Total Ledger Objects

| Object Type    | Count       |
|----------------|-------------|
| AccountRoot    | 1,000,004   |
| RippleState    | 4,000,000   |
| DirectoryNode  | 625,000     |
| Amendments     | 1           |
| FeeSettings    | 1           |
| **Grand Total**| **~5,625,006** |

## Estimated Ledger Size (JSON)

Rough per-object JSON sizes (from existing output):

| Object Type   | ~Bytes each | Count       | Subtotal      |
|---------------|-------------|-------------|---------------|
| AccountRoot   | ~350 B      | 1,000,004   | ~350 MB       |
| RippleState   | ~500 B      | 4,000,000   | ~2,000 MB     |
| DirectoryNode | ~300 B      | 625,000     | ~188 MB       |
| Amendments    | ~10 KB      | 1           | ~10 KB        |
| FeeSettings   | ~200 B      | 1           | ~200 B        |
| Ledger header | ~500 B      | 1           | ~500 B        |
| **Total**     |             |             | **~2.5 GB**   |

The actual JSON will also include formatting whitespace (indentation). With
2-space indent, expect the file to be in the **2.5–3.5 GB** range.

## Estimated Generation Time

Based on existing benchmarks (`scripts/bench_accounts.py`):

### Account Generation (ed25519 + PyNaCl)

| Mode         | Rate       | Time for 1M  |
|--------------|------------|---------------|
| Sequential   | ~22,500/s  | ~44 sec       |
| Multiprocess | ~80,000/s* | ~12 sec       |

*Estimated with 8 workers, varies by CPU.

### Trustline Object Generation

| Mode         | Rate       | Time for 4M   |
|--------------|------------|---------------|
| Sequential   | ~6,600/s   | ~10 min       |
| Multiprocess | ~25,000/s* | ~2.5 min      |

*Estimated; trustline gen is less CPU-bound than account gen, so MP
 overhead may eat into gains. Needs measurement.

### JSON Serialization & Write

Writing 2.5–3.5 GB of JSON to disk:

| Step                  | Estimate       |
|-----------------------|----------------|
| Build Python dicts    | included above |
| `json.dumps()` 5.6M objects | ~30–90 sec |
| Write to disk (SSD)   | ~5–15 sec     |

### Total Estimated Wall Time

| Phase                     | Optimistic  | Pessimistic |
|---------------------------|-------------|-------------|
| Account generation (MP)   | 12 sec      | 45 sec      |
| Trustline generation (MP) | 2.5 min     | 10 min      |
| JSON serialization        | 30 sec      | 90 sec      |
| Disk write                | 5 sec       | 15 sec      |
| **Total**                 | **~3.5 min**| **~12.5 min** |

### Memory Estimate

All 5.6M objects must be in memory before serialization:

| Item                       | Estimate       |
|----------------------------|----------------|
| 1M AccountRoot dicts       | ~400 MB        |
| 4M RippleState dicts       | ~2.4 GB        |
| 625K DirectoryNode dicts   | ~250 MB        |
| Python object overhead     | ~500 MB–1 GB   |
| JSON string during dump    | ~2.5–3.5 GB    |
| **Peak memory**            | **~6–8 GB**    |

Streaming JSON serialization (write objects incrementally) would reduce peak
memory to ~3–4 GB but requires refactoring `json.dump()` to a streaming writer.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| OOM during JSON serialization | Crash | Stream-write JSON instead of `json.dumps()` on full dict |
| Slow trustline generation | >15 min wall time | Profile hotspots; consider Cython/Rust for index calc |
| Ledger too large for rippled | Fails to load | Test with rippled; may need binary format or chunking |
| DirectoryNode page overflow | Incorrect ledger | Verify page linking (NextPageMin/PrevPageMin) at scale |

## 10K Benchmark Results (2026-02-25)

First segment completed. Gateway topology generation is implemented and working.

```bash
gen ledger -n 10000 --algo ed25519 \
    --gateways 4 --assets-per-gateway 4 \
    --gateway-currencies "USD,EUR,GBP,JPY,BTC,ETH,CNY,MXN,CAD,AUD,CHF,KRW,SGD,HKD,NOK,SEK" \
    --gateway-coverage 0.5 --gateway-connectivity 0.5 \
    --gateway-seed 42 \
    -o /tmp/benchmark-10k
```

| Metric              | Estimated    | Actual       |
|---------------------|-------------|-------------|
| AccountRoot         | 10,005      | 10,001      |
| RippleState         | ~40,000     | 39,984      |
| DirectoryNode       | ~10,000     | 5,002       |
| Total objects       | ~56,000     | 54,989      |
| File size           | ~25 MB      | 33 MB       |
| Wall time           | <60 sec     | **~4 sec**  |
| lsfDefaultRipple    | 4           | 4           |

**Key takeaway:** The fast trustline path (skipping xrpl-py wallet/signing)
makes gateway generation extremely fast. 40K trustlines in ~3 seconds.

### Extrapolation to 1M

Based on 10K results (linear scaling assumption):

| Metric          | 10K actual  | 1M projected |
|-----------------|------------|-------------|
| Accounts        | 4 sec      | ~60 sec     |
| Trustlines      | ~3 sec     | ~5 min      |
| JSON write      | <1 sec     | ~30-60 sec  |
| **Total**       | **4 sec**  | **~6-7 min** |

The fast path eliminates the signing bottleneck entirely. Main concern at 1M
is memory (all objects in a Python dict before JSON dump).

## How to Run

```bash
# 10K benchmark (WORKING)
gen ledger -n 10000 --algo ed25519 \
    --gateways 4 --assets-per-gateway 4 \
    --gateway-coverage 0.5 --gateway-connectivity 0.5 \
    --gateway-seed 42 \
    -o /tmp/benchmark-10k

# 100K benchmark (next segment)
gen ledger -n 100000 --algo ed25519 \
    --gateways 4 --assets-per-gateway 4 \
    --gateway-coverage 0.5 --gateway-connectivity 0.5 \
    --gateway-seed 42 \
    -o /tmp/benchmark-100k

# 1M benchmark (final target)
gen ledger -n 1000000 --algo ed25519 \
    --gateways 4 --assets-per-gateway 4 \
    --gateway-coverage 0.5 --gateway-connectivity 0.5 \
    --gateway-seed 42 \
    -o /tmp/benchmark-1m

# Validate with rippled
# (test if rippled can load the generated ledger.json)
```

## Open Questions

1. **Can rippled load a 3 GB genesis ledger?** — Unknown. May hit memory or
   parser limits. Need to test with progressively larger ledgers (10K, 100K,
   500K, 1M).

2. **Should we use streaming JSON?** — Current approach builds the entire dict
   in memory then dumps. At 1M accounts this will need ~6–8 GB RAM. Streaming
   would halve peak memory.

3. **Gateway distribution strategy** — Current doc assumes uniform distribution
   (each gateway gets ~25% of trustline holders). Could also do weighted
   (e.g., GW0 gets 40%, GW3 gets 10%) for realism.

4. **Should DirectoryNode pages be pre-linked?** — At 31,250 pages per
   gateway, the page linking (NextPageMin) must be correct. Current
   implementation may not handle >32 entries per account directory. Needs
   verification.
