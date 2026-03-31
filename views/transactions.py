import streamlit as st
from datetime import datetime
from db import (get_profile, get_categories, get_expenses_this_month,
                get_expenses_for_period, add_expense, update_expense,
                delete_expense, get_spending_by_category, create_alert,
                get_labels, add_label)
from utils.calculations import check_alert_thresholds, format_currency
from dateutil.relativedelta import relativedelta

PAYMENT_METHODS  = ["Cash", "Credit card", "Debit card", "Bank transfer", "Other"]
PAYMENT_STATUSES = ["Cleared", "Uncleared", "Pending", "Void"]
LABEL_COLOR_OPTIONS = {
    "Red":"#e74c3c","Orange":"#e67e22","Yellow":"#f0b429",
    "Green":"#2ecc71","Teal":"#1abc9c","Blue":"#3498db",
    "Purple":"#9b59b6","Pink":"#e91e8c","Gray":"#95a5a6",
}
COLOR_NAMES    = list(LABEL_COLOR_OPTIONS.keys())
COLOR_NAME_MAP = {v: k for k, v in LABEL_COLOR_OPTIONS.items()}


def parse_amount(val):
    try:
        return float(str(val).replace(",","").replace(" ",""))
    except Exception:
        return 0.0


def status_badge(status):
    styles = {"cleared":("✓","#2ecc71"),"uncleared":("○","#e67e22"),
              "pending":("⋯","#3498db"),"void":("✕","#95a5a6")}
    icon, color = styles.get((status or "cleared").lower(), ("○","#95a5a6"))
    return f'<span style="color:{color};font-size:11px;font-weight:500">{icon} {(status or "Cleared").title()}</span>'


def method_icon(method):
    return {"cash":"💵","credit card":"💳","debit card":"🏧",
            "bank transfer":"🏦","other":"💱"}.get((method or "cash").lower(),"💵")


def label_pill(lbl):
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:1px 8px;'
            f'border-radius:10px;font-size:11px;border:1px solid {c}55;font-weight:500">'
            f'{lbl["name"]}</span>')


def render(user_id: str):
    profile    = get_profile(user_id)
    currency   = profile.get("currency","PKR") if profile else "PKR"
    fmt        = lambda x: format_currency(x, currency)
    categories = get_categories(user_id)
    labels     = get_labels(user_id)
    cat_map    = {c["name"]: c for c in categories}
    label_map  = {str(l["id"]): l for l in labels}

    st.markdown("## 🧾 Transactions")
    st.divider()

    # ── Log new expense ───────────────────────────────────────
    with st.expander("➕ Log a new expense", expanded=False):
        if not categories:
            st.warning("No categories set up. Complete onboarding first.")
        else:
            fc1, fc2 = st.columns(2)
            cat_name   = fc1.selectbox("Category", [c["name"] for c in categories], key="tx_cat")
            amount_str = fc2.text_input("Amount", placeholder="e.g. 1,500", key="tx_amt")
            amount     = parse_amount(amount_str)
            note       = st.text_input("Note (optional)", key="tx_note")

            with st.expander("More details"):
                dc1, dc2 = st.columns(2)
                pay_method = dc1.selectbox("Payment method", PAYMENT_METHODS, key="tx_pm")
                pay_status = dc2.selectbox("Payment status", PAYMENT_STATUSES, key="tx_ps")
                location   = st.text_input("Location", key="tx_loc")
                warranty   = st.number_input("Warranty (months)", min_value=0, max_value=120, key="tx_war")

                if labels:
                    name_to_id     = {l["name"]: str(l["id"]) for l in labels}
                    sel_lbl_names  = st.multiselect("Labels", list(name_to_id.keys()), key="tx_lbls")
                    sel_label_ids  = [name_to_id[n] for n in sel_lbl_names]
                else:
                    sel_label_ids = []
                    st.caption("No labels yet — create them on the Labels page.")

            if st.button("Log expense", type="primary", key="tx_log"):
                if amount <= 0:
                    st.error("Enter a valid amount.")
                else:
                    cat = cat_map[cat_name]
                    add_expense(user_id, cat["id"], amount, note=note,
                                payment_method=pay_method, location=location,
                                warranty_months=int(warranty), payment_status=pay_status,
                                label_ids=",".join(sel_label_ids))
                    updated = get_spending_by_category(user_id)
                    for a in check_alert_thresholds(updated):
                        if a["category_id"] == cat["id"]:
                            msg = (f"Spent {fmt(a['spent'])} of {fmt(a['limit'])} "
                                   f"on {a['category_name']} ({a['pct']:.0f}%)."
                                   + (" Over budget!" if a["over"] else " Getting close."))
                            create_alert(user_id, a["category_id"], msg)
                    st.toast(f"✅ {fmt(amount)} logged under {cat['icon']} {cat_name}", icon="💰")
                    st.rerun()

    st.divider()

    # ── Filters ───────────────────────────────────────────────
    fa, fb, fc = st.columns(3)
    filter_cat    = fa.selectbox("Category", ["All"] + [c["name"] for c in categories], key="tx_f_cat")
    filter_status = fb.selectbox("Status", ["All"] + PAYMENT_STATUSES, key="tx_f_status")
    filter_method = fc.selectbox("Payment", ["All"] + PAYMENT_METHODS, key="tx_f_method")

    # ── Expense list ──────────────────────────────────────────
    now = datetime.now()
    expenses = get_expenses_for_period(user_id, "2000-01-01")  # all time for transactions page

    # Apply filters
    if filter_cat != "All":
        expenses = [e for e in expenses if e["category_name"] == filter_cat]
    if filter_status != "All":
        expenses = [e for e in expenses if (e.get("payment_status") or "cleared").lower() == filter_status.lower()]
    if filter_method != "All":
        expenses = [e for e in expenses if (e.get("payment_method") or "cash").lower() == filter_method.lower()]

    st.caption(f"{len(expenses)} transaction{'s' if len(expenses) != 1 else ''}")
    st.divider()

    if not expenses:
        st.info("No transactions match the current filters.")
        return

    for e in expenses[:50]:
        row1, row2 = st.columns([5, 2])
        with row1:
            warranty_tag = f" 🛡️{e.get('warranty_months',0)}mo" if e.get("warranty_months") else ""
            st.markdown(
                f"{'🚩 ' if e['flagged'] else ''}{e['icon']} **{e['category_name']}** "
                f"{method_icon(e.get('payment_method','cash'))} "
                f"`{(e.get('payment_method') or 'Cash').title()}`{warranty_tag}",
                unsafe_allow_html=True,
            )
            note_t = f" · {e['note']}"      if e.get("note")     else ""
            loc_t  = f" 📍 {e['location']}" if e.get("location") else ""
            st.markdown(
                f"<span style='font-size:12px'>{e['date'][:10]}{note_t}{loc_t} "
                f"{status_badge(e.get('payment_status','cleared'))}</span>",
                unsafe_allow_html=True,
            )
            ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
            if ids:
                pills = " ".join(label_pill(label_map[i]) for i in ids if i in label_map)
                if pills:
                    st.markdown(pills, unsafe_allow_html=True)

        with row2:
            st.markdown(f"**{fmt(e['amount'])}**")
            ec1, ec2 = st.columns(2)

            with ec1.popover("✏️ Edit"):
                st.markdown(f"**Edit — {e['category_name']}**")
                cat_names   = [c["name"] for c in categories]
                cur_cat_idx = cat_names.index(e["category_name"]) if e["category_name"] in cat_names else 0
                e_cat  = st.selectbox("Category", cat_names, index=cur_cat_idx, key=f"e_cat_{e['id']}")
                e_amt  = st.text_input("Amount", value=str(int(e["amount"])), key=f"e_amt_{e['id']}")
                e_note = st.text_input("Note", value=e.get("note",""), key=f"e_note_{e['id']}")

                ep1, ep2 = st.columns(2)
                pm_idx  = next((i for i,v in enumerate(PAYMENT_METHODS) if v.lower()==(e.get("payment_method") or "cash").lower()),0)
                ps_idx  = next((i for i,v in enumerate(PAYMENT_STATUSES) if v.lower()==(e.get("payment_status") or "cleared").lower()),0)
                e_pm    = ep1.selectbox("Payment method", PAYMENT_METHODS, index=pm_idx, key=f"e_pm_{e['id']}")
                e_ps    = ep2.selectbox("Status", PAYMENT_STATUSES, index=ps_idx, key=f"e_ps_{e['id']}")
                e_loc   = st.text_input("Location", value=e.get("location",""), key=f"e_loc_{e['id']}")
                e_war   = st.number_input("Warranty (months)", min_value=0, max_value=120,
                                          value=int(e.get("warranty_months") or 0), key=f"e_war_{e['id']}")

                # Labels
                cur_ids = [x for x in (e.get("label_ids") or "").split(",") if x.strip()]
                id_to_name = {str(l["id"]): l["name"] for l in labels}
                name_to_id = {l["name"]: str(l["id"]) for l in labels}
                cur_names  = [id_to_name[i] for i in cur_ids if i in id_to_name]
                e_lbls = st.multiselect("Labels", list(name_to_id.keys()),
                                        default=cur_names, key=f"e_lbls_{e['id']}")

                if st.button("Save", key=f"save_{e['id']}", type="primary"):
                    new_amt = parse_amount(e_amt)
                    if new_amt <= 0:
                        st.error("Invalid amount.")
                    else:
                        cat = cat_map.get(e_cat)
                        if cat:
                            update_expense(e["id"], user_id, cat["id"], new_amt,
                                           note=e_note, payment_method=e_pm,
                                           location=e_loc, warranty_months=int(e_war),
                                           payment_status=e_ps,
                                           label_ids=",".join(name_to_id[n] for n in e_lbls))
                            st.toast("✅ Updated", icon="✏️")
                            st.rerun()

            if ec2.button("🗑️", key=f"del_{e['id']}", help="Delete"):
                delete_expense(e["id"], user_id)
                st.toast("Deleted", icon="🗑️")
                st.rerun()
        st.divider()
