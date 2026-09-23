"""Read the CSVs once, apply the data-quality policy from CLAUDE.md, return clean records.

Every policy gets its portfolio, normalised peril, underwriting year and premium in DKK attached.
Every kept claim gets its incurred amount in DKK attached. Anything excluded or corrected is
recorded in `issues`, so no row disappears silently.
"""

import csv
import os
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent / "data"))

KNOWN_STATUSES = {"settled", "open", "withdrawn", "declined"}


def load_csv(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(s: str) -> date:
    # Claims mix ISO and DD-MM-YYYY. Verified it is day-first: the middle field is never > 12.
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date format: {s!r}")


def load_fx() -> dict[tuple[str, str], float]:
    return {(r["month"], r["currency"]): float(r["rate_dkk_per_unit"]) for r in load_csv("fx_rates.csv")}


def to_dkk(amount: float, currency: str, on: date, fx: dict) -> float:
    # Month-end rate for the month of the transaction. A missing rate raises KeyError on purpose.
    return amount * fx[(f"{on:%Y-%m}", currency)]


def load_assets() -> dict[str, dict]:
    return {r["asset_id"]: r for r in load_csv("assets.csv")}


def load_policies(assets: dict, fx: dict) -> dict[str, dict]:
    policies = {}
    for r in load_csv("policies.csv"):
        asset = assets[r["asset_id"]]  # verified: every policy references an existing asset
        inception = parse_date(r["inception_date"])
        policies[r["policy_id"]] = {
            "policy_id": r["policy_id"],
            "portfolio_id": asset["portfolio_id"],
            "region": asset["region"],
            "asset_type": asset["asset_type"],
            "peril": r["peril"].strip().lower(),  # Standardizes peril type (Including cleaning)
            "inception": inception,
            "uw_year": inception.year,
            # rule 3: full annual premium is earned, converted at the inception month
            "premium_dkk": to_dkk(float(r["annual_premium"]), r["currency"], inception, fx),
        }
    return policies


def load_claims(policies: dict, fx: dict) -> tuple[list[dict], list[dict]]:
    claims, issues = [], []
    for r in load_csv("claims.csv"):
        status = r["status"]
        if status not in KNOWN_STATUSES:
            raise ValueError(f"Unknown claim status {status!r} on {r['claim_id']}")

        loss_date = parse_date(r["loss_date"])
        paid = float(r["paid_amount"])
        reserve = float(r["reserve_amount"])

        # rule 6: a negative paid amount is treated as a sign error
        if paid < 0:
            paid = abs(paid)
            issues.append(_issue(r, "negative_paid_amount", "corrected", paid, loss_date, fx))

        # rule 7: settled = paid only (leftover reserve ignored); open = paid + reserve
        if status == "settled":
            incurred = paid
        elif status == "open":
            incurred = paid + reserve
        else:
            incurred = 0.0

        # rule 4: claim points to a policy that does not exist -> cannot attribute it
        policy = policies.get(r["policy_id"])
        if policy is None:
            issues.append(_issue(r, "unknown_policy", "excluded", incurred, loss_date, fx))
            continue

        # rule 5: loss happened before the policy incepted -> not covered by this policy
        if loss_date < policy["inception"]:
            issues.append(_issue(r, "loss_before_inception", "excluded", incurred, loss_date, fx))
            continue

        claims.append({
            "claim_id": r["claim_id"],
            "policy_id": r["policy_id"],
            "status": status,
            # rule 3: convert by the claim's own currency, not the policy's
            "incurred_dkk": to_dkk(incurred, r["currency"], loss_date, fx),
        })
    return claims, issues


def _issue(r: dict, rule: str, action: str, amount: float, loss_date: date, fx: dict) -> dict:
    return {
        "claim_id": r["claim_id"],
        "policy_id": r["policy_id"],
        "rule": rule,
        "action": action,
        "amount_dkk": round(to_dkk(amount, r["currency"], loss_date, fx), 2),
    }


def load_all() -> dict:
    fx = load_fx()
    policies = load_policies(load_assets(), fx)
    claims, issues = load_claims(policies, fx)
    return {"policies": policies, "claims": claims, "issues": issues}
