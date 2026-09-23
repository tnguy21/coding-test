"""Pure aggregation: cleaned policies + claims in, loss experience per peril out. No I/O."""

from collections import defaultdict

LOSS_STATUSES = {"settled", "open"}  # withdrawn/declined cost nothing and are not counted as claims


def loss_experience(policies: dict, claims: list[dict], portfolio_id: str) -> dict[str, dict]:
    perils = defaultdict(lambda: {
        "policy_count": 0,
        "earned_premium_dkk": 0.0,
        "incurred_loss_dkk": 0.0,
        "claim_count": 0,
        "largest_claim_dkk": 0.0,
    })

    for p in policies.values():
        if p["portfolio_id"] == portfolio_id:
            row = perils[p["peril"]]
            row["policy_count"] += 1
            row["earned_premium_dkk"] += p["premium_dkk"]

    for c in claims:
        p = policies[c["policy_id"]]  # load.py only keeps claims whose policy exists
        if p["portfolio_id"] != portfolio_id or c["status"] not in LOSS_STATUSES:
            continue
        row = perils[p["peril"]]
        row["incurred_loss_dkk"] += c["incurred_dkk"]
        row["claim_count"] += 1
        row["largest_claim_dkk"] = max(row["largest_claim_dkk"], c["incurred_dkk"])

    # Round only at the end so the sums are not affected by rounding.
    result = {}
    for peril, row in sorted(perils.items()):
        premium = row["earned_premium_dkk"]
        result[peril] = {
            "policy_count": row["policy_count"],
            "earned_premium_dkk": round(premium, 2),
            "incurred_loss_dkk": round(row["incurred_loss_dkk"], 2),
            "loss_ratio": round(row["incurred_loss_dkk"] / premium, 4) if premium else None,
            "claim_count": row["claim_count"],
            "largest_claim_dkk": round(row["largest_claim_dkk"], 2),
        }
    return result
