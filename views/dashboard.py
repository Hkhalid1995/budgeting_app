import streamlit as st
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
from db import (get_profile, get_goals, get_spending_by_category,
                get_expenses_this_month, get_spending_by_category_for_period,
                get_expenses_for_period, get_categories, get_active_alerts,
                get_labels)
from utils.calculations import compute_savings_plan, format_currency

# ── Time period options ───────────────────────────────────────
PERIODS = {
    "This month":   None,       # handled specially — uses current month boundary
    "3 months":     3,
    "6 months":     6,
    "12 months":    12,
    "All time":     -1,
}


def since_date_for_period(label: str) -> str:
    """Return ISO date string for the start of the selected period."""
    now = datetime.now()
    months = PERIODS[label]
    if months is None:
        # First day of current month
        return now.replace(day=1).strftime("%Y-%m-%d")
    if months == -1:
        return "2000-01-01"
    return (now - relativedelta(months=months)).strftime("%Y-%m-%d")


def fmt_currency(x, currency):
    return format_currency(x, currency)


def label_pill_html(lbl):
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:1px 8px;'
            f'border-radius:10px;font-size:11px;border:1px solid {c}55;'
            f'font-weight:500">{lbl["name"]}</span>')


def render(user_id: str):
    profile = get_profile(user_id)
    if not profile:
        st.error("Profile not found. Please complete onboarding.")
        return

    currency = profile.get("currency", "PKR")
    fmt      = lambda x: format_currency(x, currency)
    income   = profile["monthly_income"]
    goals    = get_goals(user_id)
    labels   = get_labels(user_id)
    label_map = {str(l["id"]): l for l in labels}

    # ── Active alerts banner ──────────────────────────────────
    for a in get_active_alerts(user_id):
        st.warning(f"{a['icon']} **{a['category_name']}** — {a['message']}", icon="🔔")

    # ── Header row ────────────────────────────────────────────
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown(f"## 👋 Hey {profile['name']}")
        st.caption(f"{datetime.now().strftime('%B %Y')} · {currency} overview")
    with h2:
        st.markdown("<div style='padding-top:16px'>", unsafe_allow_html=True)
        if st.button("➕ Add", type="primary", use_container_width=True):
            st.session_state["page"] = "add_expense"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Time period selector ──────────────────────────────────
    period_col, _ = st.columns([3, 5])
    with period_col:
        period_label = st.segmented_control(
            "Period", list(PERIODS.keys()),
            default="This month", key="dash_period",
        )
    if period_label is None:
        period_label = "This month"

    since = since_date_for_period(period_label)

    # ── Load data for selected period ─────────────────────────
    spending = get_spending_by_category_for_period(user_id, since)
    expenses = get_expenses_for_period(user_id, since)

    # Summary metrics always use current-month plan for goals/savings
    this_month_spending = get_spending_by_category(user_id)
    plan = compute_savings_plan(income, goals, this_month_spending)

    total_spent    = sum(s["spent"] for s in spending)
    total_budgeted = sum(s["monthly_limit"] for s in spending)

    # ── Summary metrics ───────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly income",   fmt(income))
    m2.metric("Total budgeted",   fmt(plan["total_budgeted"]))
    m3.metric(f"Spent ({period_label.lower()})", fmt(total_spent),
              delta=f"{fmt(total_budgeted - total_spent)} left" if period_label == "This month" else None,
              delta_color="normal" if total_budgeted >= total_spent else "inverse")
    m4.metric("Savings rate", f"{plan['savings_rate_pct']:.1f}%",
              help="Based on this month's budget")

    st.divider()

    # ── Category filter pills ─────────────────────────────────
    cats_with_data = [s for s in spending if s["spent"] > 0 or s["monthly_limit"] > 0]

    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = None

    # Pill row — "All" + up to 5 categories inline, rest in selectbox
    pill_cols = st.columns(min(len(cats_with_data) + 1, 7))
    with pill_cols[0]:
        is_all = st.session_state["selected_category"] is None
        if st.button("All", type="primary" if is_all else "secondary",
                     use_container_width=True):
            st.session_state["selected_category"] = None
            st.rerun()

    visible_cats = cats_with_data[:6]
    for i, cat in enumerate(visible_cats):
        with pill_cols[i + 1]:
            is_active = st.session_state["selected_category"] == cat["name"]
            label = f"{cat['icon']} {cat['name']}"
            if st.button(label, type="primary" if is_active else "secondary",
                         use_container_width=True, key=f"pill_{cat['name']}"):
                st.session_state["selected_category"] = None if is_active else cat["name"]
                st.rerun()

    if len(cats_with_data) > 6:
        extra_names = [c["name"] for c in cats_with_data[6:]]
        current_sel = st.session_state["selected_category"]
        default_idx = extra_names.index(current_sel) + 1 if current_sel in extra_names else 0
        chosen = st.selectbox(
            "More categories", ["— more —"] + extra_names,
            index=default_idx, label_visibility="collapsed",
        )
        if chosen != "— more —" and chosen != current_sel:
            st.session_state["selected_category"] = chosen
            st.rerun()

    selected_cat = st.session_state["selected_category"]

    # Filter data
    if selected_cat:
        filtered_spending = [s for s in spending if s["name"] == selected_cat]
        filtered_expenses = [e for e in expenses if e["category_name"] == selected_cat]
        cat_obj           = filtered_spending[0] if filtered_spending else None
    else:
        filtered_spending = spending
        filtered_expenses = expenses
        cat_obj           = None

    st.divider()

    # ══════════════════════════════════════════════════════════
    # DRILLDOWN VIEW — single category selected
    # ══════════════════════════════════════════════════════════
    if selected_cat and cat_obj:
        st.markdown(f"### {cat_obj['icon']} {selected_cat}")
        st.caption(f"Showing: {period_label.lower()}")

        d1, d2, d3 = st.columns(3)
        d1.metric("Spent",  fmt(cat_obj["spent"]))
        d2.metric("Budget", fmt(cat_obj["monthly_limit"]))
        pct = (cat_obj["spent"] / cat_obj["monthly_limit"] * 100) \
              if cat_obj["monthly_limit"] > 0 else 0
        d3.metric("Used", f"{pct:.0f}%",
                  delta="Over budget" if pct > 100 else f"{100 - pct:.0f}% remaining",
                  delta_color="inverse" if pct > 100 else "normal")

        if filtered_expenses:
            # Daily spending line chart
            daily: dict[str, float] = {}
            for e in filtered_expenses:
                day = e["date"][:10]
                daily[day] = daily.get(day, 0) + e["amount"]
            days_sorted = sorted(daily)
            amounts     = [daily[d] for d in days_sorted]

            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=days_sorted, y=amounts,
                mode="lines+markers",
                line=dict(color="#1abc9c", width=2),
                marker=dict(size=6, color="#1abc9c"),
                fill="tozeroy",
                fillcolor="rgba(26,188,156,0.08)",
                hovertemplate="%{x}<br>" + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig_line.update_layout(
                title=f"Daily spending — {selected_cat}",
                height=260, margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.12)"),
                font=dict(size=12),
            )
            st.plotly_chart(fig_line, use_container_width=True)

            # By-label pie (only if labels are used)
            label_totals: dict[str, float] = {}
            for e in filtered_expenses:
                ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                if ids:
                    for lid in ids:
                        name = label_map.get(lid, {}).get("name", "Unknown")
                        label_totals[name] = label_totals.get(name, 0) + e["amount"]
                else:
                    label_totals["Unlabelled"] = label_totals.get("Unlabelled", 0) + e["amount"]

            label_colors = [label_map.get(lid, {}).get("color", "#95a5a6")
                            for lid in label_map if label_map[lid]["name"] in label_totals]

            if label_totals and not (len(label_totals) == 1 and "Unlabelled" in label_totals):
                fig_lbl = go.Figure(go.Pie(
                    labels=list(label_totals.keys()),
                    values=list(label_totals.values()),
                    hole=0.5,
                    textinfo="label+percent",
                    marker=dict(colors=label_colors or [
                        "#3498db","#2ecc71","#e74c3c","#9b59b6","#e67e22","#1abc9c"
                    ]),
                    hovertemplate="%{label}<br>" + currency + " %{value:,.0f}<extra></extra>",
                ))
                fig_lbl.update_layout(
                    title="Breakdown by label",
                    height=280, margin=dict(l=0, r=0, t=40, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.25),
                )
                st.plotly_chart(fig_lbl, use_container_width=True)

            # Transaction list
            st.markdown(f"**Transactions — {period_label.lower()}**")
            for e in filtered_expenses[:20]:
                r1, r2, r3 = st.columns([2, 4, 2])
                r1.caption(e["date"][:10])
                note = e.get("note") or "—"
                loc  = f" · 📍 {e['location']}" if e.get("location") else ""
                r2.markdown(f"{note}{loc}")
                # Label pills
                ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                if ids:
                    pills = " ".join(label_pill_html(label_map[i])
                                    for i in ids if i in label_map)
                    if pills:
                        r2.markdown(pills, unsafe_allow_html=True)
                r3.markdown(f"**{fmt(e['amount'])}**")
        else:
            st.info(f"No expenses for {selected_cat} in this period.")

    # ══════════════════════════════════════════════════════════
    # OVERVIEW — all categories
    # ══════════════════════════════════════════════════════════
    else:
        # Pie + Bar side by side
        chart1, chart2 = st.columns(2)

        # Pie: spend by category
        with chart1:
            cats_spent = [s for s in spending if s["spent"] > 0]
            if cats_spent:
                PALETTE = ["#3498db","#2ecc71","#e74c3c","#9b59b6",
                           "#e67e22","#1abc9c","#f0b429","#e91e8c","#95a5a6"]
                fig_pie = go.Figure(go.Pie(
                    labels=[f"{s['icon']} {s['name']}" for s in cats_spent],
                    values=[s["spent"] for s in cats_spent],
                    hole=0.45,
                    textinfo="percent",
                    marker=dict(colors=PALETTE[:len(cats_spent)]),
                    hovertemplate="%{label}<br>" + currency + " %{value:,.0f}<extra></extra>",
                ))
                fig_pie.update_layout(
                    title=f"Spend by category ({period_label.lower()})",
                    height=300, margin=dict(l=0, r=0, t=40, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="v", font=dict(size=11)),
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No spending recorded in this period.")

        # Bar: budget vs spent
        with chart2:
            if spending:
                cat_names  = [s["name"] for s in spending]
                cat_icons  = [s["icon"] for s in spending]
                budgets    = [s["monthly_limit"] for s in spending]
                spents     = [s["spent"] for s in spending]
                bar_colors = ["#e74c3c" if sp > bu else "#2ecc71"
                              for sp, bu in zip(spents, budgets)]

                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    name="Budget", x=cat_names, y=budgets,
                    marker_color="rgba(52,152,219,0.3)",
                    hovertemplate="%{x}<br>Budget: " + currency + " %{y:,.0f}<extra></extra>",
                ))
                fig_bar.add_trace(go.Bar(
                    name="Spent", x=cat_names, y=spents,
                    marker_color=bar_colors,
                    hovertemplate="%{x}<br>Spent: " + currency + " %{y:,.0f}<extra></extra>",
                ))
                fig_bar.update_layout(
                    title=f"Budget vs spent ({period_label.lower()})",
                    barmode="group", height=300,
                    margin=dict(l=0, r=0, t=40, b=60),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickangle=-30, showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.12)"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # Spending over time — line chart (all categories combined)
        if expenses:
            daily: dict[str, float] = {}
            for e in expenses:
                day = e["date"][:10]
                daily[day] = daily.get(day, 0) + e["amount"]
            days_sorted = sorted(daily)
            amounts     = [daily[d] for d in days_sorted]

            # Cumulative line
            cumulative = []
            running = 0.0
            for a in amounts:
                running += a
                cumulative.append(running)

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=days_sorted, y=amounts, name="Daily",
                marker_color="rgba(52,152,219,0.4)",
                hovertemplate="%{x}<br>" + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig_trend.add_trace(go.Scatter(
                x=days_sorted, y=cumulative, name="Cumulative",
                mode="lines", line=dict(color="#e74c3c", width=2),
                yaxis="y2",
                hovertemplate="%{x}<br>Total: " + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig_trend.update_layout(
                title=f"Spending trend ({period_label.lower()})",
                height=280, margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.12)",
                           title="Daily spend"),
                yaxis2=dict(overlaying="y", side="right", showgrid=False,
                            title="Cumulative"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # Budget progress bars
        st.markdown("### 📊 Budget progress")
        for cat in spending:
            limit     = cat["monthly_limit"]
            spent     = cat["spent"]
            pct       = min((spent / limit * 100) if limit > 0 else 0, 100)
            over      = spent > limit
            bar_color = "#e74c3c" if over else ("#ff7f0e" if pct >= 80 else "#2ecc71")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{cat['icon']} **{cat['name']}** — {fmt(spent)} / {fmt(limit)}")
                st.markdown(
                    f'<div style="background:rgba(128,128,128,0.15);border-radius:6px;'
                    f'height:8px;margin-bottom:10px">'
                    f'<div style="width:{pct:.0f}%;background:{bar_color};height:8px;'
                    f'border-radius:6px"></div></div>',
                    unsafe_allow_html=True,
                )
            with col2:
                if over:
                    st.error(f"Over {fmt(spent - limit)}", icon="🔴")
                else:
                    st.caption(f"{fmt(limit - spent)} left")

    st.divider()

    # ── Goals snapshot ────────────────────────────────────────
    st.markdown("### 🎯 Goals")
    if not plan["goal_allocations"]:
        st.info("No goals set yet.")
    else:
        gcols = st.columns(min(len(plan["goal_allocations"]), 3))
        for i, g in enumerate(plan["goal_allocations"]):
            with gcols[i % len(gcols)]:
                st.markdown(f"**{g['name']}**")
                st.caption(f"Target: {fmt(g['target'])} · {g['months_left']}mo left")
                st.caption(f"Need {fmt(g['monthly_needed'])}/mo")
                if g["on_track"]:
                    st.success("On track ✓")
                else:
                    st.warning("Tight ⚠️")
