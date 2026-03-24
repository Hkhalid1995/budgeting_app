from datetime import datetime


def months_until(deadline_str: str) -> int:
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        now = datetime.now()
        return max(1, (deadline.year - now.year) * 12 + (deadline.month - now.month))
    except Exception:
        return 12


def compute_savings_plan(monthly_income: float, goals: list[dict], spending: list[dict]) -> dict:
    total_budget = sum(s["monthly_limit"] for s in spending)
    total_spent_this_month = sum(s["spent"] for s in spending)
    disposable = monthly_income - total_budget

    goal_allocations = []
    total_monthly_needed = 0
    for g in goals:
        months = months_until(g["deadline"])
        monthly_needed = g["target_amount"] / months
        total_monthly_needed += monthly_needed
        goal_allocations.append({
            "name": g["name"],
            "target": g["target_amount"],
            "months_left": months,
            "monthly_needed": monthly_needed,
            "on_track": monthly_needed <= (disposable / max(len(goals), 1)),
        })

    savings_rate = (disposable / monthly_income * 100) if monthly_income > 0 else 0

    return {
        "monthly_income": monthly_income,
        "total_budgeted": total_budget,
        "total_spent": total_spent_this_month,
        "remaining_budget": total_budget - total_spent_this_month,
        "disposable_income": disposable,
        "savings_rate_pct": savings_rate,
        "goal_allocations": goal_allocations,
        "total_monthly_for_goals": total_monthly_needed,
        "surplus_after_goals": disposable - total_monthly_needed,
    }


def check_alert_thresholds(spending: list[dict], threshold_pct: float = 80.0) -> list[dict]:
    """Return categories that have crossed the alert threshold."""
    alerts = []
    for s in spending:
        if s["monthly_limit"] > 0:
            pct = (s["spent"] / s["monthly_limit"]) * 100
            if pct >= threshold_pct:
                alerts.append({
                    "category_id": s["id"],
                    "category_name": s["name"],
                    "icon": s["icon"],
                    "spent": s["spent"],
                    "limit": s["monthly_limit"],
                    "pct": pct,
                    "over": pct >= 100,
                })
    return alerts


def format_currency(amount: float, currency: str = "PKR") -> str:
    if currency == "PKR":
        return f"Rs {amount:,.0f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "EUR":
        return f"€{amount:,.2f}"
    return f"{currency} {amount:,.2f}"
