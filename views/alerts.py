import streamlit as st
from db import (get_active_alerts, dismiss_alert, get_spending_by_category,
                get_categories, add_expense, create_alert, get_profile)
from utils.calculations import check_alert_thresholds, format_currency


def render(user_id: str):
    profile = get_profile(user_id)
    currency = profile.get("currency", "PKR") if profile else "PKR"
    fmt = lambda x: format_currency(x, currency)

    st.markdown("## 🔔 Expense alerts")
    st.caption("Fires when you hit 80%+ of a category budget.")

    alerts = get_active_alerts(user_id)

    if not alerts:
        st.success("✅ No active alerts — all categories within limits!")
    else:
        st.markdown(f"**{len(alerts)} alert{'s' if len(alerts)>1 else ''} need attention**")
        st.divider()
        for alert in alerts:
            severity = "🔴" if "Over" in alert["message"] else "🟠"
            st.markdown(f"### {severity} {alert['icon']} {alert['category_name']}")
            st.markdown(alert["message"])
            st.caption(f"Triggered: {alert['triggered_at'][:16]}")
            col1, col2, col3 = st.columns(3)
            with col1:
                with st.popover("📝 Log expense"):
                    categories = get_categories(user_id)
                    cat = next((c for c in categories if c["id"] == alert["category_id"]), None)
                    if cat:
                        amt_str = st.text_input("Amount", key=f"amt_{alert['id']}", placeholder="e.g. 500")
                        note = st.text_input("Note", key=f"note_{alert['id']}")
                        if st.button("Log it", key=f"log_{alert['id']}", type="primary"):
                            try:
                                amt = float(amt_str.replace(",",""))
                                if amt > 0:
                                    add_expense(user_id, cat["id"], amt, note, flagged=True)
                                    dismiss_alert(alert["id"], user_id)
                                    st.rerun()
                            except Exception:
                                st.error("Enter a valid amount.")
            with col2:
                if st.button("Dismiss", key=f"dis_{alert['id']}"):
                    dismiss_alert(alert["id"], user_id)
                    st.rerun()
            with col3:
                if st.button("Dashboard →", key=f"dash_{alert['id']}"):
                    st.session_state["page"] = "dashboard"
                    st.rerun()
            st.divider()

    st.markdown("### 🔍 Manual check")
    if st.button("Check all budgets now", use_container_width=True):
        spending = get_spending_by_category(user_id)
        triggered = check_alert_thresholds(spending, threshold_pct=80)
        if not triggered:
            st.success("All categories under 80%.")
        else:
            for t in triggered:
                status = "OVER BUDGET" if t["over"] else f"{t['pct']:.0f}% used"
                msg = f"Spent {fmt(t['spent'])} of {fmt(t['limit'])} on {t['category_name']} — {status}"
                create_alert(user_id, t["category_id"], msg)
                if t["over"]:
                    st.error(f"{t['icon']} {msg}")
                else:
                    st.warning(f"{t['icon']} {msg}")
            st.rerun()
