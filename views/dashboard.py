import streamlit as st
from datetime import datetime
from db import (get_profile, get_goals, get_spending_by_category,
                get_expenses_this_month, add_expense, update_expense,
                delete_expense, get_categories, create_alert, get_active_alerts,
                get_labels, add_label, delete_label)
from utils.calculations import compute_savings_plan, check_alert_thresholds, format_currency

PAYMENT_METHODS = ["Cash", "Credit card", "Debit card", "Bank transfer", "Other"]
PAYMENT_STATUSES = ["Cleared", "Uncleared", "Pending", "Void"]
LABEL_COLORS = ["#e74c3c","#e67e22","#f1c40f","#2ecc71","#1abc9c","#3498db","#9b59b6","#95a5a6"]


def parse_amount(val: str) -> float:
    try:
        return float(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def status_badge(status: str) -> str:
    colors = {
        "cleared":   ("✓", "#2ecc71"),
        "uncleared": ("○", "#e67e22"),
        "pending":   ("⋯", "#3498db"),
        "void":      ("✕", "#95a5a6"),
    }
    icon, color = colors.get((status or "cleared").lower(), ("○", "#95a5a6"))
    return f'<span style="color:{color};font-size:11px">{icon} {(status or "Cleared").title()}</span>'


def method_icon(method: str) -> str:
    icons = {"cash": "💵", "credit card": "💳", "debit card": "🏧",
             "bank transfer": "🏦", "other": "💱"}
    return icons.get((method or "cash").lower(), "💵")


def expense_detail_form(key_prefix, categories, labels, defaults=None):
    """Renders the full expense form fields. Returns dict of field values."""
    d = defaults or {}
    cat_names = [c["name"] for c in categories]
    default_cat = d.get("category_name", cat_names[0] if cat_names else "")
    cat_idx = cat_names.index(default_cat) if default_cat in cat_names else 0

    fc1, fc2 = st.columns(2)
    cat_name = fc1.selectbox("Category", cat_names, index=cat_idx, key=f"{key_prefix}_cat")
    amount_str = fc2.text_input(
        "Amount",
        value=str(int(d["amount"])) if d.get("amount") else "",
        placeholder="e.g. 1,500",
        key=f"{key_prefix}_amount"
    )
    note = st.text_input("Note (optional)", value=d.get("note", ""),
                         placeholder="e.g. Lunch at office", key=f"{key_prefix}_note")

    with st.expander("More details", expanded=bool(defaults)):
        dc1, dc2 = st.columns(2)

        pm_idx = next((i for i, v in enumerate(PAYMENT_METHODS)
                       if v.lower() == (d.get("payment_method") or "cash").lower()), 0)
        payment_method = dc1.selectbox("Payment method", PAYMENT_METHODS,
                                       index=pm_idx, key=f"{key_prefix}_method")

        ps_idx = next((i for i, v in enumerate(PAYMENT_STATUSES)
                       if v.lower() == (d.get("payment_status") or "cleared").lower()), 0)
        payment_status = dc2.selectbox("Payment status", PAYMENT_STATUSES,
                                       index=ps_idx, key=f"{key_prefix}_status")

        location = st.text_input("Location / merchant",
                                 value=d.get("location", ""),
                                 placeholder="e.g. Carrefour, Gulberg Lahore",
                                 key=f"{key_prefix}_location")

        wc1, wc2 = st.columns([3, 1])
        warranty_months = wc1.number_input("Warranty (months, 0 = none)",
                                           min_value=0, max_value=120,
                                           value=int(d.get("warranty_months") or 0),
                                           key=f"{key_prefix}_warranty")
        if warranty_months > 0:
            wc2.markdown(f"<div style='padding-top:28px;font-size:12px'>🛡️ {warranty_months}mo</div>",
                         unsafe_allow_html=True)

        # Labels
        st.markdown("**Labels**")
        current_ids = [x for x in (d.get("label_ids") or "").split(",") if x.strip()]
        selected_labels = []
        if labels:
            cols = st.columns(min(4, len(labels)))
            for i, lbl in enumerate(labels):
                with cols[i % len(cols)]:
                    if st.checkbox(lbl["name"], value=str(lbl["id"]) in current_ids,
                                   key=f"{key_prefix}_lbl_{lbl['id']}"):
                        selected_labels.append(str(lbl["id"]))
        else:
            st.caption("No labels yet — add one below.")

        lc1, lc2, lc3 = st.columns([3, 1, 1])
        new_label_name = lc1.text_input("New label", placeholder="e.g. Business, Family",
                                        key=f"{key_prefix}_new_label",
                                        label_visibility="collapsed")
        new_label_color = lc2.selectbox("Color", LABEL_COLORS,
                                        format_func=lambda x: "●",
                                        key=f"{key_prefix}_label_color",
                                        label_visibility="collapsed")
        if lc3.button("Add label", key=f"{key_prefix}_add_label"):
            if new_label_name.strip():
                add_label(st.session_state.get("_user_id", ""),
                          new_label_name.strip(), new_label_color)
                st.rerun()

        # Receipt attachment
        st.markdown("**Receipt attachment**")
        uploaded_img = st.file_uploader("Attach receipt",
                                        type=["jpg", "jpeg", "png", "webp"],
                                        key=f"{key_prefix}_receipt_img",
                                        label_visibility="collapsed")
        receipt_image = uploaded_img.read() if uploaded_img else d.get("receipt_image")
        if uploaded_img:
            st.image(uploaded_img, width=120)
        elif d.get("receipt_image"):
            st.image(d["receipt_image"], caption="Current receipt", width=120)

    return {
        "cat_name":       cat_name,
        "amount":         parse_amount(amount_str),
        "amount_str":     amount_str,
        "note":           note,
        "payment_method": payment_method,
        "payment_status": payment_status,
        "location":       location,
        "warranty_months": int(warranty_months),
        "label_ids":      ",".join(selected_labels),
        "receipt_image":  receipt_image,
    }


def render(user_id: str):
    st.session_state["_user_id"] = user_id

    profile = get_profile(user_id)
    if not profile:
        st.error("Profile not found. Please complete onboarding.")
        return

    currency = profile.get("currency", "PKR")
    fmt = lambda x: format_currency(x, currency)
    income = profile["monthly_income"]
    goals = get_goals(user_id)
    spending = get_spending_by_category(user_id)
    plan = compute_savings_plan(income, goals, spending)
    categories = get_categories(user_id)
    labels = get_labels(user_id)
    cat_map = {c["name"]: c for c in categories}
    label_map = {str(l["id"]): l for l in labels}

    st.markdown(f"## 👋 Hey {profile['name']}")
    st.caption(f"{datetime.now().strftime('%B %Y')} · {currency} overview")

    active_alerts = get_active_alerts(user_id)
    if active_alerts:
        for alert in active_alerts:
            st.warning(f"{alert['icon']} **{alert['category_name']}** — {alert['message']}", icon="🔔")

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly income", fmt(income))
    m2.metric("Total budgeted", fmt(plan["total_budgeted"]))
    m3.metric("Spent this month", fmt(plan["total_spent"]),
              delta=f"{fmt(plan['remaining_budget'])} left",
              delta_color="normal" if plan["remaining_budget"] >= 0 else "inverse")
    m4.metric("Savings rate", f"{plan['savings_rate_pct']:.1f}%")

    st.divider()
    st.markdown("### 📊 Budget vs spending")
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
                unsafe_allow_html=True)
        with col2:
            if over:
                st.error(f"Over {fmt(spent-limit)}")
            else:
                st.caption(f"{fmt(limit-spent)} left")

    st.divider()
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
            st.success(f"✅ After goals, **{fmt(surplus)}/month** to spare.")
        else:
            st.error(f"⚠️ **{fmt(abs(surplus))}/month short** of all goals.")

    st.divider()

    # ── Add expense form ──────────────────────────────────────
    st.markdown("### ➕ Log an expense")
    if not categories:
        st.info("No categories set up yet.")
        return

    form_values = expense_detail_form("new", categories, labels)
    if form_values["amount_str"] and form_values["amount"] > 0:
        st.caption(f"✓ {fmt(form_values['amount'])}")
    elif form_values["amount_str"]:
        st.warning("Enter a valid number.")

    if st.button("Log expense", type="primary", use_container_width=True):
        if form_values["amount"] <= 0:
            st.error("Please enter a valid amount.")
        else:
            cat = cat_map[form_values["cat_name"]]
            add_expense(
                user_id, cat["id"], form_values["amount"],
                note=form_values["note"],
                payment_method=form_values["payment_method"],
                location=form_values["location"],
                warranty_months=form_values["warranty_months"],
                payment_status=form_values["payment_status"],
                receipt_image=form_values["receipt_image"],
                label_ids=form_values["label_ids"],
            )
            updated = get_spending_by_category(user_id)
            alert_fired = False
            for a in check_alert_thresholds(updated):
                if a["category_id"] == cat["id"]:
                    msg = (f"Spent {fmt(a['spent'])} of {fmt(a['limit'])} "
                           f"on {a['category_name']} ({a['pct']:.0f}%)."
                           + (" Over budget!" if a["over"] else " Getting close."))
                    create_alert(user_id, a["category_id"], msg)
                    alert_fired = True
                    if a["over"]:
                        st.toast(f"🔴 Over budget on {cat['icon']} {form_values['cat_name']}!", icon="⚠️")
                    else:
                        st.toast(f"🟠 {cat['icon']} {form_values['cat_name']} at {a['pct']:.0f}% of budget", icon="⚠️")
            if not alert_fired:
                st.toast(f"✅ {fmt(form_values['amount'])} logged under {cat['icon']} {form_values['cat_name']}", icon="💰")
            st.rerun()

    st.divider()

    # ── Recent transactions ───────────────────────────────────
    st.markdown("### 🧾 Recent transactions")
    expenses = get_expenses_this_month(user_id)
    if not expenses:
        st.caption("No expenses this month yet.")
    else:
        for e in expenses[:20]:
            row1, row2 = st.columns([5, 2])
            with row1:
                warranty_tag = f" 🛡️ {e.get('warranty_months',0)}mo" if e.get("warranty_months") else ""
                st.markdown(
                    f"{'🚩 ' if e['flagged'] else ''}{e['icon']} **{e['category_name']}** &nbsp;"
                    f"{method_icon(e.get('payment_method','cash'))} "
                    f"`{(e.get('payment_method') or 'Cash').title()}`"
                    f"{warranty_tag}",
                    unsafe_allow_html=True
                )
                note_text = f" · {e['note']}" if e.get("note") else ""
                loc_text  = f" 📍 {e['location']}" if e.get("location") else ""
                st.markdown(
                    f"<span style='font-size:12px'>"
                    f"{e['date'][:10]}{note_text}{loc_text} &nbsp;"
                    f"{status_badge(e.get('payment_status','cleared'))}"
                    f"</span>",
                    unsafe_allow_html=True
                )
                ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                if ids:
                    pills = " ".join(
                        f'<span style="background:{label_map[i]["color"]}22;color:{label_map[i]["color"]};'
                        f'padding:1px 7px;border-radius:10px;font-size:11px;'
                        f'border:1px solid {label_map[i]["color"]}44">{label_map[i]["name"]}</span>'
                        for i in ids if i in label_map
                    )
                    if pills:
                        st.markdown(pills, unsafe_allow_html=True)

            with row2:
                st.markdown(f"**{fmt(e['amount'])}**")
                ec1, ec2 = st.columns(2)

                with ec1.popover("✏️ Edit"):
                    st.markdown(f"**Edit — {e['category_name']}**")
                    edit_vals = expense_detail_form(f"edit_{e['id']}", categories, labels, defaults=e)
                    if st.button("Save changes", key=f"save_{e['id']}", type="primary"):
                        if edit_vals["amount"] <= 0:
                            st.error("Invalid amount.")
                        else:
                            cat = cat_map.get(edit_vals["cat_name"])
                            if cat:
                                update_expense(
                                    e["id"], user_id, cat["id"], edit_vals["amount"],
                                    note=edit_vals["note"],
                                    payment_method=edit_vals["payment_method"],
                                    location=edit_vals["location"],
                                    warranty_months=edit_vals["warranty_months"],
                                    payment_status=edit_vals["payment_status"],
                                    receipt_image=edit_vals["receipt_image"],
                                    label_ids=edit_vals["label_ids"],
                                )
                                st.toast("✅ Expense updated", icon="✏️")
                                st.rerun()

                if ec2.button("🗑️", key=f"del_{e['id']}", help="Delete this expense"):
                    delete_expense(e["id"], user_id)
                    st.toast("Expense deleted", icon="🗑️")
                    st.rerun()

            st.divider()

    # ── Label manager ─────────────────────────────────────────
    with st.expander("🏷️ Manage labels"):
        current_labels = get_labels(user_id)
        if current_labels:
            for lbl in current_labels:
                lc1, lc2 = st.columns([5, 1])
                lc1.markdown(
                    f'<span style="background:{lbl["color"]}22;color:{lbl["color"]};'
                    f'padding:2px 10px;border-radius:10px;font-size:13px;'
                    f'border:1px solid {lbl["color"]}66">{lbl["name"]}</span>',
                    unsafe_allow_html=True
                )
                if lc2.button("Remove", key=f"dellbl_{lbl['id']}"):
                    delete_label(lbl["id"], user_id)
                    st.rerun()
        else:
            st.caption("No labels yet. Add them from the expense form above.")
