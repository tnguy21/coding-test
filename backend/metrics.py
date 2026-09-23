"""Pure aggregation: cleaned policies + claims in, loss experience per peril out. No I/O.

Each figure has its own small function that takes a plain list of policies or claims,
so every calculation can be read and tested on its own.
"""

from collections import defaultdict

LOSS_STATUSES = {"settled", "open"}  # withdrawn/declined cost nothing and are not counted as claims


def policy_count(policies: list[dict]) -> int:
    return len(policies)


def earned_premium(policies: list[dict]) -> float:
    return sum(p["premium_dkk"] for p in policies)  # Earned = full annual premium


def loss_claims(claims: list[dict]) -> list[dict]:
    return [c for c in claims if c["status"] in LOSS_STATUSES]


def incurred_loss(claims: list[dict]) -> float:
    return sum(c["incurred_dkk"] for c in loss_claims(claims))


def claim_count(claims: list[dict]) -> int:
    return len(loss_claims(claims))


def largest_claim(claims: list[dict]) -> float:
    return max((c["incurred_dkk"] for c in loss_claims(claims)), default=0.0)


def loss_ratio(incurred: float, premium: float) -> float | None:
    return incurred / premium if premium else None


def underwriting_result(premium: float, incurred: float) -> float:
    # Positive = premium covered claims (before expenses); negative = losing money on claims alone.
    return premium - incurred


# --- Putting it together -----------------------------------------------------

def group_by_peril(policies: dict, claims: list[dict], portfolio_id: str) -> dict[str, tuple[list, list]]:
    """{peril: (policies, claims)} for one portfolio. A claim's peril is its policy's peril."""
    groups = defaultdict(lambda: ([], []))
    for p in policies.values():
        if p["portfolio_id"] == portfolio_id:
            groups[p["peril"]][0].append(p)
    for c in claims:
        p = policies[c["policy_id"]]  # load.py only keeps claims whose policy exists
        if p["portfolio_id"] == portfolio_id:
            groups[p["peril"]][1].append(c)
    return groups


def group_by_portfolio(policies: dict, claims: list[dict]) -> dict[str, tuple[list, list]]:
    """{portfolio_id: (policies, claims)}. A claim's portfolio is its policy's portfolio."""
    groups = defaultdict(lambda: ([], []))
    for p in policies.values():
        groups[p["portfolio_id"]][0].append(p)
    for c in claims:
        groups[policies[c["policy_id"]]["portfolio_id"]][1].append(c)
    return groups


def summarise(policies: list[dict], claims: list[dict]) -> dict:
    premium = earned_premium(policies)
    incurred = incurred_loss(claims)
    ratio = loss_ratio(incurred, premium)
    # Round only here, so the sums themselves are not affected by rounding.
    return {
        "policy_count": policy_count(policies),
        "earned_premium_dkk": round(premium, 2),
        "incurred_loss_dkk": round(incurred, 2),
        "loss_ratio": round(ratio, 4) if ratio is not None else None,
        "underwriting_result_dkk": round(underwriting_result(premium, incurred), 2),
        "claim_count": claim_count(claims),
        "largest_claim_dkk": round(largest_claim(claims), 2),
    }


def loss_experience(policies: dict, claims: list[dict], portfolio_id: str) -> dict[str, dict]:
    groups = group_by_peril(policies, claims, portfolio_id)
    return {peril: summarise(*groups[peril]) for peril in sorted(groups)}


def portfolios_loss_experience(policies: dict, claims: list[dict]) -> list[dict]:
    """Portfolio-level totals across all perils, worst loss ratio first.

    Worst first because the reader is an underwriter looking for loss-making business to act on.
    Loss ratio is size-neutral, which is fair here: all portfolios are of similar size.
    Ties (unlikely) fall back to portfolio_id so the order is deterministic.
    """
    groups = group_by_portfolio(policies, claims)
    rows = [{"portfolio_id": pid, **summarise(*groups[pid])} for pid in groups]
    rows.sort(key=lambda r: (-r["loss_ratio"], r["portfolio_id"]))
    return [{"rank": i, **row} for i, row in enumerate(rows, start=1)]


def book_total(policies: dict, claims: list[dict]) -> dict:
    """Whole-book figures: the average to compare portfolios against. Must equal the sum of portfolios."""
    return summarise(list(policies.values()), claims)


def rankings(portfolios: list[dict]) -> dict[str, str]:
    """Short summary of the ranked list; each name states which direction is bad or good."""
    return {
        "worst_loss_ratio": portfolios[0]["portfolio_id"],
        "best_loss_ratio": portfolios[-1]["portfolio_id"],
        "smallest_underwriting_result": min(portfolios, key=lambda r: r["underwriting_result_dkk"])["portfolio_id"],
        "largest_single_claim": max(portfolios, key=lambda r: r["largest_claim_dkk"])["portfolio_id"],
    }
