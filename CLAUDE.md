# Envira loss-experience service (practical test)

## Purpose
Take-home for Envira (2-hour budget). The goal is a small HTTP service reporting **loss experience** for a book of
Danish insurance policies: per portfolio and per peril, how much premium came in and what claims cost. The brief
(`candidate-pack/BRIEF.md`) is deliberately too big. **Priority: one correct, verified, runnable endpoint over breadth.**
Grading (`candidate-pack/SCORING.md`): correctness & verification 30%, scoping 25%, operability 15%,
live ownership 15%, code/tests 10%, communication 5%.

## Working agreement (read this first, Claude)
- The human writes the code. Claude acts as an **assistant**: explain, review, point out bugs and edge cases,
  suggest approaches, answer questions, run commands and checks. **Do not write implementation code unless the
  human explicitly asks for it** ("write X for me"). Small illustrative snippets in chat are fine.
- Keep everything smaller than you'd naturally propose. No abstractions, layers or infra the core doesn't need.
- Every number must be explainable. Prefer plain code the human can walk through live over clever code.
- Don't touch `candidate-pack/` or any `data/` folder. Never commit them.
- Commit little and often (the history is read by reviewers).

## Stack & layout
Backend: Python 3.11+, FastAPI + uvicorn, managed with `uv`. Data is loaded and cleaned once at startup, in memory.
Frontend: React + TypeScript + Vite; talks to the backend through a proxy (Vite in dev, nginx in Docker).
```
backend/load.py      # read + clean CSVs -> clean policies, kept claims, `issues` (excluded/corrected rows)
backend/metrics.py   # pure calculations, one small function per figure (no I/O)
backend/main.py      # FastAPI routes (thin)
backend/data/*.csv   # the data (gitignored); override the location with DATA_DIR
frontend/src/App.tsx # the page: pick a portfolio / compare all portfolios
docker-compose.yml   # backend on :8000, frontend on :8080; mounts backend/data read-only
```
Data setup: `cd backend && unzip ../candidate-pack/envira-loss-data.zip` creates `backend/data/*.csv`.
Run (dev): `cd backend && uv run uvicorn main:app --reload --port 8000`, then `cd frontend && npm run dev`.

## API
- `GET /portfolios`: list of portfolio IDs.
- `GET /portfolios/{portfolio_id}/loss-experience`: per peril, `policy_count, earned_premium_dkk,
  incurred_loss_dkk, loss_ratio, underwriting_result_dkk, claim_count, largest_claim_dkk`. Unknown ID → 404.
- `GET /portfolios/loss-experience`: the same figures per portfolio, sorted **worst loss ratio first**, plus
  `book_total`, `rankings` (worst/best loss ratio, smallest underwriting result, largest single claim) and `ordering`.

## Domain definitions (from the brief)
- **Incurred**: settled = paid; open = paid + reserve; withdrawn/declined = 0.
- **Earned premium**: full annual premium (no pro-rata). **Loss ratio** = incurred / earned, both in DKK.
- **Underwriting year** = calendar year of policy inception.
- Core endpoint `GET /portfolios/{portfolio_id}/loss-experience`: per peril, give policy count, earned premium,
  incurred, loss ratio, claim count, largest single claim, all in DKK.

## Data files (verified)
| file | rows | key | notes |
|---|---:|---|---|
| assets.csv | 4,200 | asset_id | 12 portfolios PF-01..PF-12, 5 regions, 5 asset types; all clean |
| policies.csv | 11,560 | policy_id (POL-500001..511560) | UW years 2022 (4,484), 2023 (6,045), 2024 (1,031); DKK 9,146 / EUR 2,414 |
| claims.csv | 4,509 | claim_id | settled 2,905 / open 1,031 / withdrawn 327 / declined 246; DKK 4,251 / EUR 258 |
| fx_rates.csv | 168 | (month, currency) | EUR & DKK, 2020-01..2026-12, no gaps; EUR 7.4324–7.4588, DKK = 1.0 |

**Checked and fine:** no empty cells; no duplicate IDs; no exact-duplicate rows (also none after
normalising dates); all policies reference an existing asset; all dates parse; expiry > inception (terms are 364/365 days);
reported ≥ loss date (lag 0–45 days); declined/withdrawn always have paid = reserve = 0; open always has paid>0 and reserve>0;
no claim exceeds the asset's sum insured; FX covers every month needed. Numeric formats are consistent: dot decimal,
no currency symbols, no thousand separators. Only the number of trailing decimals varies, which is harmless.

## Data-quality issues and the handling policy (agreed)
Impact is measured on the whole-book loss ratio. Reference LR under this policy is **0.737**.

| # | Issue | Rows | Policy | Why / impact |
|---|---|---:|---|---|
| 1 | **Peril labels inconsistent**: case (`FIRE`, `Fire`) and leading/trailing spaces (`' flood'`, `'hail  '`) | 1,321 policies | `strip().lower()` → 5 perils: fire, flood, hail, storm, subsidence | Otherwise one peril splits into up to 5 groups |
| 2 | **Mixed date formats in claims**: `YYYY-MM-DD` and `DD-MM-YYYY` in `loss_date` / `reported_date` | 572 loss, 578 reported | Parse both. Anything else raises an error | Verified DD-MM, not MM-DD: the middle field is never >12, and with DD-MM no claim is reported before its loss |
| 3 | **Mixed currencies**: premiums and claims in DKK or EUR, and the **claim currency ≠ policy currency** for 859 claims (758 EUR-policy/DKK-claim, 101 the reverse) | — | Convert **each amount by its own `currency` column**. Premium uses the FX rate of the inception month; claims use the rate of the loss-date month | The labels are genuine: EUR-policy/DKK-claim amounts sit on the DKK scale relative to sum insured. **Converting claims by the policy's currency gives LR 1.78 (wrong)**. Not converting premiums understates premium by 14M DKK. The choice of FX month is immaterial (<0.4% spread) |
| 4 | **Orphan claims**: `policy_id` not in policies.csv (all `POL-9xxxxx`, outside the real ID range) | 260, all settled, ≈11.7M DKK paid | **Exclude** from portfolio figures; report them in data quality with count + amount | Can't attribute them to a portfolio or peril. Including them would add ~0.15 to the LR |
| 5 | **Loss date before policy inception** (20–397 days before; none after expiry) | 310 (≈5.3M DKK incurred) | **Exclude**; report in data quality | The policy didn't cover the loss. 83 have a same-asset same-peril sibling policy covering the date and 51 have another-peril policy; 176 have no cover at all. Reassigning to a sibling is a possible later improvement. Keeping them: LR 0.803 |
| 6 | **Negative `paid_amount` on settled claims** | 262 raw; **245 reach the output** (17 are also pre-inception, so excluded by rule 5) | Treat as a **sign error → use abs()**; count and flag in data quality | No matching positive claim exists (so these aren't reversals). The magnitudes match normal payouts, and a net-negative settled claim is commercially implausible. Alternatives: keep negative → LR 0.701; zero them → LR 0.752 |
| 7 | **Settled claims with reserve > 0** | 721 | Ignore the reserve (the brief says settled = paid) | A leftover reserve that was never released. Including it → LR +0.03 |
| 8 | Two claims on the same policy with the same loss date | 2 pairs (CLM-900753/754: declined + settled; CLM-902101/102: both settled, different amounts) | Keep both | Amounts differ, so these are not provable duplicates |
| 9 | Overlapping terms for the same asset+peril (renewal overlaps) | ~2,000 pairs | Keep. Each policy counts its own full premium | Synthetic artefact. Doesn't break any definition |

**Claim count** = claims with status settled or open that survive rules 4–5 (i.e. claims that cost money); book total 3,401.
**Largest claim** = the largest single claim's *incurred* (paid + reserve for open), not paid alone.
**FX for open-claim reserves** uses the loss-month rate too (a valuation-date rate is arguable; immaterial here).
Reconciliation invariant: **4,509 claims = 260 orphan + 310 pre-inception + 3,939 kept (all statuses)**. No row is lost silently.
Loss *after* expiry is not checked: 0 such rows exist today, but a future one would pass silently.

**Commercially notable but genuine:** fire LR ≈ 1.8 (low frequency ~0.10/policy, high severity, median paid ≈38k DKK,
low median premium ≈2.6k DKK). This is an underpricing signal, not a data error.

## Reference numbers (from ad-hoc profiling, for cross-checking; the independent check script should reproduce them)
Whole book: earned premium **79,771,396 DKK**, incurred **58,779,302 DKK**, LR **0.737**.
Per portfolio (premium / incurred / LR): PF-01 6.93M/3.64M/0.525 · PF-02 6.53M/5.22M/0.799 · PF-03 6.59M/6.37M/0.967 ·
PF-04 7.15M/5.12M/0.716 · PF-05 6.19M/4.64M/0.750 · PF-06 7.38M/5.21M/0.706 · PF-07 6.53M/5.14M/0.787 ·
PF-08 6.25M/4.86M/0.777 · PF-09 7.12M/5.17M/0.726 · PF-10 6.10M/3.89M/0.638 · PF-11 6.44M/5.02M/0.780 · PF-12 6.57M/4.50M/0.685

## Progress (as of 2026-09-23)
Brief backlog item → status:
1. ✅ **Core per-portfolio endpoint.** Verified: matches an independent recomputation for all 60 portfolio × peril rows.
2. ✅ **All-portfolios comparison**, worst loss ratio first. Verified: ranks, rankings, and portfolios sum to `book_total`.
3. ⬜ Data-quality endpoint. `DATA["issues"]` already holds the rows. **Fix first:** 17 claims are logged twice
   (negative-paid "corrected" + pre-inception "excluded"); log the correction only after the exclusion checks.
4. ⬜ Filters (underwriting year / region / asset type). The fields are already on each policy.
5. ✅ Simple page (React), with number formatting in one locale (en-GB) so "." is always the decimal point.
6. 🟨 Dockerfiles + docker-compose added. Not yet verified end-to-end with `docker compose up`.
7. ⬜ Tests: none yet; pytest is not a dependency. Priority: one test per data-quality rule.
8. ✖ Database: deliberately not planned. Volumes are tiny, so in-memory is simpler; say so in DECISIONS.md.

Verification done: an independent script (no backend imports) reproduced every figure. It should become
`scripts/check.py` in the repo.

Open housekeeping:
- 🔴 `candidate-pack/` (the data zip, BRIEF, SCORING) was committed in `a717128` and pushed to origin/main and
  origin/task1. It must be removed from the repo, and ideally from history.
- README has no run instructions yet. DECISIONS.md has only the Started/Stopped times.

## Deliverables checklist
README (how to unzip data + run) · DECISIONS.md (Started/Stopped + the 3 exact headings, 10–20 lines, mention
AI use + one thing verified/rejected) · data not in git · real commit history.
