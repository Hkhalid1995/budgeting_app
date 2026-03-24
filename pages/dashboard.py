import streamlit as st
from datetime import datetime
from db import (
    get_profile, get_goals, get_spending_by_category,
    get_expenses_this_month, add_expense, get_categories,
    create_alert, get_active_alerts
)
from utils.calculations import compute_savings_plan, check_alert_thresholds, format_currency


def parse_amount(val: str) -> float:
    try:
        return float(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def render():
    profile = get_profile()
    if not profile:
        st.error("Profile not found. Please complete onboarding.")
        return

    currency = profile.get("currency", "PKR")
    fmt = lambda x: format_currency(x, currency)
    name = profile["name"]
    income = profile["monthly_income"]

    goals = get_goals()
    spending = get_spending_by_category()
    plan = compute_savings_plan(income, goals, spending)

    # ── Header ───────────────────────────────────────────────────
    st.markdown(f"## 👋 Hey {name}")
    st.caption(f"{datetime.now().strftime('%B %Y')} · {currency} budget overview")

    # ── Active alerts banner ──────────────────────────────────────
    active_alerts = get_active_alerts()
    if active_alerts:
        for alert in active_alerts:
            st.warning(f"{alert['icon']} **{alert['category_name']}** — {alert['message']}", icon="🔔")

    st.divider()

    # ── Top metrics ───────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly income", fmt(income))
    m2.metric("Total budgeted", fmt(plan["total_budgeted"]))
    m3.metric(
        "Spent this month",
        fmt(plan["total_spent"]),
        delta=f"{fmt(plan['remaining_budget'])} left",
        delta_color="normal" if plan["remaining_budget"] >= 0 else "inverse"
    )
    m4.metric(
        "Savings rate",
        f"{plan['savings_rate_pct']:.1f}%",
        help="Disposable income after all budget categories"
    )

    st.divider()

    # ── Budget vs expense per category ────────────────────────────
    st.markdown("### 📊 Budget vs spending")

    if not spending:
        st.info("No budget categories set up yet.")
    else:
        for cat in spending:
            limit = cat["monthly_limit"]
            spent = cat["spent"]
            pct = min((spent / limit * 100) if limit > 0 else 0, 100)
            over = spent > limit

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{cat['icon']} **{cat['name']}** — {fmt(spent)} / {fmt(limit)}")
                st.markdown(
                    f"""<div style="background:#e0e0e0;border-radius:6px;height:10px;margin-bottom:12px">
                        <div style="width:{pct:.0f}%;background:{'#d62728' if over else ('#ff7f0e' if pct>=80 else '#2ca02c')};
                        height:10px;border-radius:6px"></div></div>""",
                    unsafe_allow_html=True,
                )
            with col2:
                if over:
                    st.error(f"Over {fmt(spent - limit)}")
                else:
                    st.caption(f"{fmt(limit - spent)} left")

    st.divider()

    # ── Savings goals ─────────────────────────────────────────────
    st.markdown("### 🎯 Goals progress")
    if not plan["goal_allocations"]:
        st.info("No goals set yet.")
    else:
        for g in plan["goal_allocations"]:
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f"**{g['name']}** — target {fmt(g['target'])} in {g['months_left']} months")
            c2.metric("Need / month", fmt(g["monthly_needed"]))
            c3.success("On track ✓") if g["on_track"] else c3.warning("Tight ⚠️")

        surplus = plan["surplus_after_goals"]
        if surplus >= 0:
            st.success(f"✅ After goals, you have **{fmt(surplus)}/month** to spare.")
        else:
            st.error(f"⚠️ You're **{fmt(abs(surplus))}/month short** of all goals.")

    st.divider()

    # ── Log a new expense ─────────────────────────────────────────
    st.markdown("### ➕ Log an expense")

    categories = get_categories()
    if not categories:
        st.info("No categories set up yet.")
        return

    cat_map = {c["name"]: c for c in categories}

    fc1, fc2 = st.columns(2)
    cat_name = fc1.selectbox("Category", list(cat_map.keys()), key="exp_cat")
    amount_str = fc2.text_input("Amount", placeholder="e.g. 1,500", key="exp_amount")
    note = st.text_input("Note (optional)", placeholder="e.g. Lunch at office", key="exp_note")

    amount = parse_amount(amount_str)
    if amount_str and amount > 0:
        st.caption(f"✓ Amount: {fmt(amount)}")
    elif amount_str:
        st.warning("Enter a valid number (commas are fine).")

    if st.button("Log expense", type="primary", use_container_width=True, key="log_btn"):
        if amount <= 0:
            st.error("Please enter a valid amount greater than 0.")
        else:
            cat = cat_map[cat_name]
            add_expense(cat["id"], amount, note)

            # Check thresholds and fire alerts
            updated_spending = get_spending_by_category()
            alerts = check_alert_thresholds(updated_spending)
            for a in alerts:
                if a["category_id"] == cat["id"]:
                    msg = (
                        f"You've spent {fmt(a['spent'])} of your {fmt(a['limit'])} "
                        f"{a['category_name']} budget ({a['pct']:.0f}%)."
                        + (" **Over budget!**" if a["over"] else " Getting close.")
                    )
                    create_alert(a["category_id"], msg)

            st.success(f"✓ Logged {fmt(amount)} under {cat['icon']} {cat_name}")
            st.rerun()

    st.divider()

    # ── Recent transactions ───────────────────────────────────────
    st.markdown("### 🧾 Recent transactions")
    expenses = get_expenses_this_month()
    if not expenses:
        st.caption("No expenses logged this month yet.")
    else:
        for e in expenses[:15]:
            date_str = e["date"][:10]
            flag = "🚩 " if e["flagged"] else ""
            cols = st.columns([1, 3, 2, 2])
            cols[0].caption(date_str)
            cols[1].markdown(f"{flag}{e['icon']} {e['category_name']}")
            cols[2].caption(e["note"] or "—")
            cols[3].markdown(f"**{fmt(e['amount'])}**")
