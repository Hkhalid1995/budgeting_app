import streamlit as st
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
from db import (get_profile, get_goals, get_spending_by_category,
                get_spending_by_category_for_period,
                get_expenses_for_period, get_active_alerts, get_labels)
from utils.calculations import compute_savings_plan, format_currency

PERIODS = {
    "This month": None,
    "3 months":   3,
    "6 months":   6,
    "12 months":  12,
    "All time":   -1,
}
PALETTE = ["#3498db","#2ecc71","#e74c3c","#9b59b6",
           "#e67e22","#1abc9c","#f0b429","#e91e8c","#95a5a6"]


def since_date(label):
    now = datetime.now()
    months = PERIODS[label]
    if months is None:
        return now.replace(day=1).strftime("%Y-%m-%d")
    if months == -1:
        return "2000-01-01"
    return (now - relativedelta(months=months)).strftime("%Y-%m-%d")


def label_pill(lbl):
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:1px 8px;'
            f'border-radius:10px;font-size:11px;border:1px solid {c}55;'
            f'font-weight:500">{lbl["name"]}</span>')


def floating_add_button():
    """Inject a fixed floating ➕ button via CSS/HTML that navigates to add_expense."""
    st.markdown("""
    <style>
    .fab-container {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 9999;
    }
    .fab-btn {
        width: 56px;
        height: 56px;
        border-radius: 50%;
        background: #e74c3c;
        color: white;
        font-size: 28px;
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        line-height: 1;
    }
    .fab-btn:hover { background: #c0392b; transform: scale(1.08); }
    </style>
    <div class="fab-container">
        <button class="fab-btn" onclick="
            // Trigger Streamlit button via parent frame
            window.parent.postMessage({type:'streamlit:setComponentValue', value: true}, '*');
        " title="Add expense">＋</button>
    </div>
    """, unsafe_allow_html=True)


def render(user_id: str):
    profile = get_profile(user_id)
    if not profile:
        st.error("Profile not found. Please complete onboarding.")
        return

    currency  = profile.get("currency", "PKR")
    fmt       = lambda x: format_currency(x, currency)
    income    = profile["monthly_income"]
    goals     = get_goals(user_id)
    labels    = get_labels(user_id)
    label_map = {str(l["id"]): l for l in labels}

    # Alerts banner
    for a in get_active_alerts(user_id):
        st.warning(f"{a['icon']} **{a['category_name']}** — {a['message']}", icon="🔔")

    # ── Header ────────────────────────────────────────────────
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown(f"## 👋 Hey {profile['name']}")
        st.caption(f"{datetime.now().strftime('%B %Y')} · {currency} overview")
    with h2:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        if st.button("➕ Add", type="primary", use_container_width=True):
            st.session_state["page"] = "add_expense"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # ── Period selector ───────────────────────────────────────
    period_label = st.segmented_control(
        "Period", list(PERIODS.keys()),
        default="This month", key="dash_period",
    )
    if not period_label:
        period_label = "This month"

    sd       = since_date(period_label)
    spending = get_spending_by_category_for_period(user_id, sd)
    expenses = get_expenses_for_period(user_id, sd)

    # Plan always uses current month for goals/savings rate
    this_month_spending = get_spending_by_category(user_id)
    plan         = compute_savings_plan(income, goals, this_month_spending)
    total_spent  = sum(s["spent"] for s in spending)
    total_budget = sum(s["monthly_limit"] for s in spending)

    # ── Metrics ───────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly income",   fmt(income))
    m2.metric("Total budgeted",   fmt(plan["total_budgeted"]))
    remaining = total_budget - total_spent
    m3.metric(f"Spent ({period_label.lower()})", fmt(total_spent),
              delta=f"{fmt(remaining)} left" if period_label == "This month" else None,
              delta_color="normal" if remaining >= 0 else "inverse")
    m4.metric("Savings rate", f"{plan['savings_rate_pct']:.1f}%")

    st.divider()

    # ── Category filter pills ─────────────────────────────────
    cats = [s for s in spending if s["spent"] > 0 or s["monthly_limit"] > 0]
    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = None

    pill_cols = st.columns(min(len(cats) + 1, 7))
    with pill_cols[0]:
        if st.button("All",
                     type="primary" if st.session_state["selected_category"] is None else "secondary",
                     use_container_width=True):
            st.session_state["selected_category"] = None
            st.rerun()

    for i, cat in enumerate(cats[:6]):
        with pill_cols[i + 1]:
            active = st.session_state["selected_category"] == cat["name"]
            if st.button(f"{cat['icon']} {cat['name']}",
                         type="primary" if active else "secondary",
                         use_container_width=True,
                         key=f"pill_{cat['name']}"):
                st.session_state["selected_category"] = None if active else cat["name"]
                st.rerun()

    if len(cats) > 6:
        extra = [c["name"] for c in cats[6:]]
        sel   = st.session_state["selected_category"]
        idx   = extra.index(sel) + 1 if sel in extra else 0
        chosen = st.selectbox("More", ["— more —"] + extra,
                              index=idx, label_visibility="collapsed")
        if chosen != "— more —" and chosen != sel:
            st.session_state["selected_category"] = chosen
            st.rerun()

    selected = st.session_state["selected_category"]
    f_spend  = [s for s in spending if s["name"] == selected] if selected else spending
    f_exp    = [e for e in expenses if e["category_name"] == selected] if selected else expenses
    cat_obj  = f_spend[0] if selected and f_spend else None

    st.divider()

    # ══════════════════════════════════════════════════════════
    # DRILLDOWN — single category
    # ══════════════════════════════════════════════════════════
    if selected and cat_obj:
        st.markdown(f"### {cat_obj['icon']} {selected}")
        d1, d2, d3 = st.columns(3)
        d1.metric("Spent",  fmt(cat_obj["spent"]))
        d2.metric("Budget", fmt(cat_obj["monthly_limit"]))
        pct = (cat_obj["spent"] / cat_obj["monthly_limit"] * 100) if cat_obj["monthly_limit"] else 0
        d3.metric("Used", f"{pct:.0f}%",
                  delta="Over budget" if pct > 100 else f"{100-pct:.0f}% remaining",
                  delta_color="inverse" if pct > 100 else "normal")

        if f_exp:
            # Daily line chart
            daily: dict = {}
            for e in f_exp:
                day = e["date"][:10]
                daily[day] = daily.get(day, 0) + e["amount"]
            days = sorted(daily)

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=days, y=[daily[d] for d in days],
                mode="lines+markers",
                line=dict(color="#1abc9c", width=2),
                marker=dict(size=6),
                fill="tozeroy", fillcolor="rgba(26,188,156,0.08)",
                hovertemplate="%{x}<br>" + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                title=f"Daily spending — {selected} ({period_label.lower()})",
                height=250, margin=dict(l=0, r=0, t=40, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, type="category"),
                yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.12)"),
            )
            st.plotly_chart(fig, use_container_width=True)

            # By-label breakdown
            label_totals: dict = {}
            for e in f_exp:
                ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                for lid in (ids or []):
                    name = label_map.get(lid, {}).get("name", "Unknown")
                    label_totals[name] = label_totals.get(name, 0) + e["amount"]
                if not ids:
                    label_totals["Unlabelled"] = label_totals.get("Unlabelled", 0) + e["amount"]

            if len(label_totals) > 1 or "Unlabelled" not in label_totals:
                lbl_colors = []
                for name in label_totals:
                    match = next((l for l in labels if l["name"] == name), None)
                    lbl_colors.append(match["color"] if match else "#95a5a6")

                fig_l = go.Figure(go.Pie(
                    labels=list(label_totals.keys()),
                    values=list(label_totals.values()),
                    hole=0.5, textinfo="label+percent",
                    marker=dict(colors=lbl_colors),
                    hovertemplate="%{label}<br>" + currency + " %{value:,.0f}<extra></extra>",
                ))
                fig_l.update_layout(
                    title="Breakdown by label", height=300,
                    margin=dict(l=0, r=0, t=40, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="top", y=-0.1, font=dict(size=11)),
                )
                st.plotly_chart(fig_l, use_container_width=True)

            # Transaction list
            st.markdown(f"**Transactions — {selected}**")
            for e in f_exp[:20]:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.caption(e["date"][:10])
                note = e.get("note") or "—"
                loc  = f" · 📍 {e['location']}" if e.get("location") else ""
                c2.markdown(f"{note}{loc}")
                ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                if ids:
                    pills = " ".join(label_pill(label_map[i]) for i in ids if i in label_map)
                    if pills:
                        c2.markdown(pills, unsafe_allow_html=True)
                c3.markdown(f"**{fmt(e['amount'])}**")
        else:
            st.info(f"No expenses for {selected} in this period.")

    # ══════════════════════════════════════════════════════════
    # OVERVIEW — all categories
    # ══════════════════════════════════════════════════════════
    else:
        chart1, chart2 = st.columns(2)

        # Pie — spend by category
        with chart1:
            cats_spent = [s for s in spending if s["spent"] > 0]
            if cats_spent:
                fig_pie = go.Figure(go.Pie(
                    labels=[s["name"] for s in cats_spent],
                    values=[s["spent"] for s in cats_spent],
                    hole=0.42,
                    textinfo="percent",
                    textposition="inside",
                    insidetextorientation="radial",
                    marker=dict(colors=PALETTE[:len(cats_spent)],
                                line=dict(color="rgba(0,0,0,0.2)", width=1)),
                    hovertemplate="<b>%{label}</b><br>" + currency + " %{value:,.0f}<br>%{percent}<extra></extra>",
                ))
                fig_pie.update_layout(
                    title=dict(text=f"Spend by category ({period_label.lower()})",
                               font=dict(size=13)),
                    height=320,
                    margin=dict(l=0, r=0, t=44, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(
                        orientation="v",
                        x=1.02, y=0.5,
                        font=dict(size=11),
                        itemsizing="constant",
                    ),
                    showlegend=True,
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No spending recorded in this period.")

        # Bar — budget vs spent
        with chart2:
            if spending:
                names      = [s["name"] for s in spending]
                budgets    = [s["monthly_limit"] for s in spending]
                spents     = [s["spent"] for s in spending]
                bar_colors = ["#e74c3c" if sp > bu else "#2ecc71"
                              for sp, bu in zip(spents, budgets)]

                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(
                    name="Budget", x=names, y=budgets,
                    marker_color="rgba(52,152,219,0.35)",
                    hovertemplate="<b>%{x}</b><br>Budget: " + currency + " %{y:,.0f}<extra></extra>",
                ))
                fig_bar.add_trace(go.Bar(
                    name="Spent", x=names, y=spents,
                    marker_color=bar_colors,
                    hovertemplate="<b>%{x}</b><br>Spent: " + currency + " %{y:,.0f}<extra></extra>",
                ))
                fig_bar.update_layout(
                    title=dict(text=f"Budget vs spent ({period_label.lower()})",
                               font=dict(size=13)),
                    barmode="group", height=320,
                    margin=dict(l=0, r=0, t=44, b=80),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickangle=-35, showgrid=False,
                               tickfont=dict(size=11)),
                    yaxis=dict(showgrid=True,
                               gridcolor="rgba(128,128,128,0.12)"),
                    legend=dict(orientation="h",
                                x=0, y=1.12,
                                font=dict(size=11)),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # Spending trend — daily bars + cumulative line
        if expenses:
            daily: dict = {}
            for e in expenses:
                day = e["date"][:10]
                daily[day] = daily.get(day, 0) + e["amount"]
            days    = sorted(daily)
            amounts = [daily[d] for d in days]
            cumul   = []
            running = 0.0
            for a in amounts:
                running += a
                cumul.append(running)

            fig_t = go.Figure()
            fig_t.add_trace(go.Bar(
                x=days, y=amounts, name="Daily spend",
                marker_color="rgba(52,152,219,0.5)",
                hovertemplate="<b>%{x}</b><br>Daily: " + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig_t.add_trace(go.Scatter(
                x=days, y=cumul, name="Cumulative",
                mode="lines", line=dict(color="#e74c3c", width=2),
                yaxis="y2",
                hovertemplate="<b>%{x}</b><br>Total: " + currency + " %{y:,.0f}<extra></extra>",
            ))
            fig_t.update_layout(
                title=dict(text=f"Spending trend ({period_label.lower()})",
                           font=dict(size=13)),
                height=280,
                margin=dict(l=0, r=60, t=44, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, type="category",
                           tickangle=-30, tickfont=dict(size=10)),
                yaxis=dict(title="Daily",
                           showgrid=True,
                           gridcolor="rgba(128,128,128,0.12)",
                           titlefont=dict(size=11)),
                yaxis2=dict(title="Cumulative", overlaying="y", side="right",
                            showgrid=False, titlefont=dict(size=11)),
                legend=dict(orientation="h", x=0, y=1.12, font=dict(size=11)),
            )
            st.plotly_chart(fig_t, use_container_width=True)

        # Budget progress bars
        st.markdown("### 📊 Budget progress")
        for cat in spending:
            limit     = cat["monthly_limit"]
            spent     = cat["spent"]
            pct       = min((spent / limit * 100) if limit else 0, 100)
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
                    st.error(f"Over {fmt(spent-limit)}", icon="🔴")
                else:
                    st.caption(f"{fmt(limit-spent)} left")

    st.divider()

    # ── Goals snapshot ────────────────────────────────────────
    st.markdown("### 🎯 Goals")
    if not plan["goal_allocations"]:
        st.info("No goals set yet — add them from the Goals page.")
    else:
        gcols = st.columns(min(len(plan["goal_allocations"]), 3))
        for i, g in enumerate(plan["goal_allocations"]):
            with gcols[i % len(gcols)]:
                st.markdown(f"**{g['name']}**")
                st.caption(f"Target: {fmt(g['target'])} · {g['months_left']}mo left")
                st.caption(f"Need {fmt(g['monthly_needed'])}/mo")
                st.success("On track ✓") if g["on_track"] else st.warning("Tight ⚠️")
