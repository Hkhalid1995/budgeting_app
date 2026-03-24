import streamlit as st
from db import (
    get_active_alerts, dismiss_alert, get_spending_by_category,
    get_categories, add_expense, create_alert, get_profile
)
from utils.calculations import check_alert_thresholds, format_currency


def render():
    profile = get_profile()
    currency = profile.get("currency", "PKR") if profile else "PKR"
    fmt = lambda x: format_currency(x, currency)

    st.markdown("## 🔔 Expense alerts")
    st.caption("Alerts fire automatically when you're 80%+ through a category budget.")

    # ── Active alerts ────────────────────────────────────────
    alerts = get_active_alerts()

    if not alerts:
        st.success("✅ No active alerts — you're within all your budget limits!")
    else:
        st.markdown(f"**{len(alerts)} alert{'s' if len(alerts)>1 else ''} need your attention**")
        st.divider()

        for alert in alerts:
            with st.container():
                severity = "🔴" if "Over budget" in alert["message"] else "🟠"
                st.markdown(f"### {severity} {alert['icon']} {alert['category_name']}")
                st.markdown(alert["message"])
                st.caption(f"Triggered: {alert['triggered_at'][:16]}")

                col1, col2, col3 = st.columns(3)

                # Option 1: Log the expense that triggered this
                with col1:
                    with st.popover("📝 Log expense"):
                        categories = get_categories()
                        cat = next((c for c in categories if c["id"] == alert["category_id"]), None)
                        if cat:
                            amt = st.number_input("Amount", min_value=0.01, step=10.0, key=f"amt_{alert['id']}")
                            note = st.text_input("Note", key=f"note_{alert['id']}", placeholder="What was this for?")
                            if st.button("Log it", key=f"log_{alert['id']}", type="primary"):
                                add_expense(cat["id"], amt, note, flagged=True)
                                dismiss_alert(alert["id"])
                                st.success("Logged and alert dismissed.")
                                st.rerun()

                # Option 2: Dismiss
                with col2:
                    if st.button("Dismiss", key=f"dis_{alert['id']}"):
                        dismiss_alert(alert["id"])
                        st.rerun()

                # Option 3: View category (go to dashboard)
                with col3:
                    if st.button("Go to dashboard →", key=f"dash_{alert['id']}"):
                        st.session_state["page"] = "dashboard"
                        st.rerun()

                st.divider()

    # ── Manual alert check ────────────────────────────────────
    st.markdown("### 🔍 Check current status")
    st.caption("Run a manual check across all categories.")

    if st.button("Check all budgets now", use_container_width=True):
        spending = get_spending_by_category()
        triggered = check_alert_thresholds(spending, threshold_pct=80)

        if not triggered:
            st.success("All categories are within safe limits (under 80%).")
        else:
            for t in triggered:
                status = "OVER BUDGET" if t["over"] else f"{t['pct']:.0f}% used"
                severity = "error" if t["over"] else "warning"
                msg = f"You've spent {fmt(t['spent'])} of {fmt(t['limit'])} on {t['category_name']} — {status}"
                create_alert(t["category_id"], msg)
                if severity == "error":
                    st.error(f"{t['icon']} {msg}")
                else:
                    st.warning(f"{t['icon']} {msg}")
            st.info("New alerts created. Check the alerts list above.")
            st.rerun()

    # ── Alert settings ────────────────────────────────────────
    st.divider()
    st.markdown("### ⚙️ Alert settings")
    threshold = st.slider(
        "Alert me when I reach this % of a category budget",
        min_value=50, max_value=100, value=80, step=5,
        format="%d%%"
    )
    st.caption(f"Currently set to **{threshold}%**. This applies to the next manual check or expense log.")
    st.session_state["alert_threshold"] = threshold
