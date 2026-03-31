import streamlit as st
from db import (get_categories, get_spending_by_category, create_alert,
                add_expense, get_labels, add_label, get_profile)
from utils.calculations import check_alert_thresholds, format_currency

PAYMENT_METHODS  = ["Cash", "Credit card", "Debit card", "Bank transfer", "Other"]
PAYMENT_STATUSES = ["Cleared", "Uncleared", "Pending", "Void"]
LABEL_COLOR_OPTIONS = {
    "Red": "#e74c3c", "Orange": "#e67e22", "Yellow": "#f0b429",
    "Green": "#2ecc71", "Teal": "#1abc9c", "Blue": "#3498db",
    "Purple": "#9b59b6", "Pink": "#e91e8c", "Gray": "#95a5a6",
}
COLOR_NAMES    = list(LABEL_COLOR_OPTIONS.keys())
COLOR_NAME_MAP = {v: k for k, v in LABEL_COLOR_OPTIONS.items()}


def parse_amount(val: str) -> float:
    try:
        return float(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def label_pill_html(lbl):
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:2px 10px;'
            f'border-radius:10px;font-size:12px;border:1px solid {c}55;'
            f'font-weight:500;margin-right:4px">{lbl["name"]}</span>')


def render(user_id: str):
    profile    = get_profile(user_id)
    currency   = profile.get("currency", "PKR") if profile else "PKR"
    fmt        = lambda x: format_currency(x, currency)
    categories = get_categories(user_id)
    labels     = get_labels(user_id)
    cat_map    = {c["name"]: c for c in categories}

    # Back button
    if st.button("← Back to dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    st.markdown("## ➕ Log an expense")
    st.divider()

    if not categories:
        st.warning("No budget categories set up yet. Complete onboarding first.")
        return

    # ── Core fields ───────────────────────────────────────────
    fc1, fc2 = st.columns(2)
    cat_names = [c["name"] for c in categories]
    cat_name  = fc1.selectbox("Category", cat_names)
    amount_str = fc2.text_input("Amount", placeholder="e.g. 1,500")
    amount = parse_amount(amount_str)
    if amount_str and amount > 0:
        st.caption(f"✓ {fmt(amount)}")
    elif amount_str:
        st.warning("Enter a valid number — commas are fine.")

    note = st.text_input("Note (optional)", placeholder="e.g. Lunch at Hardees")

    st.divider()
    st.markdown("### More details")

    dc1, dc2 = st.columns(2)
    payment_method = dc1.selectbox("Payment method", PAYMENT_METHODS)
    payment_status = dc2.selectbox("Payment status", PAYMENT_STATUSES)

    lc1, lc2 = st.columns(2)
    location = lc1.text_input("Location / merchant", placeholder="e.g. Carrefour, Gulberg")
    warranty_months = lc2.number_input("Warranty (months, 0 = none)",
                                        min_value=0, max_value=120, value=0)

    # ── Labels ────────────────────────────────────────────────
    st.markdown("### 🏷️ Labels")
    fresh_labels = get_labels(user_id)
    if fresh_labels:
        name_to_id = {l["name"]: str(l["id"]) for l in fresh_labels}
        selected_names = st.multiselect(
            "Assign labels", options=list(name_to_id.keys()),
            placeholder="Pick labels...", label_visibility="collapsed",
        )
        selected_label_ids = [name_to_id[n] for n in selected_names]

        if selected_label_ids:
            id_map = {str(l["id"]): l for l in fresh_labels}
            pills  = " ".join(label_pill_html(id_map[i])
                              for i in selected_label_ids if i in id_map)
            st.markdown(pills, unsafe_allow_html=True)
    else:
        selected_label_ids = []
        st.caption("No labels yet — create one below.")

    # Inline label creator
    with st.expander("＋ Create a new label"):
        nc1, nc2 = st.columns([3, 2])
        new_lbl_name  = nc1.text_input("Name", placeholder="e.g. Business, Tax",
                                        key="ae_new_lbl_name", label_visibility="collapsed")
        chosen_color_name = nc2.selectbox("Color", COLOR_NAMES,
                                           key="ae_new_lbl_color", label_visibility="collapsed")
        chosen_hex = LABEL_COLOR_OPTIONS[chosen_color_name]
        nc2.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;margin-top:-6px">'
            f'<span style="display:inline-block;width:14px;height:14px;background:{chosen_hex};'
            f'border-radius:3px"></span>'
            f'<span style="font-size:12px;color:{chosen_hex};font-weight:600">{chosen_color_name}</span>'
            f'</div>', unsafe_allow_html=True,
        )
        if new_lbl_name.strip():
            st.markdown(f'Preview: {label_pill_html({"name": new_lbl_name.strip(), "color": chosen_hex})}',
                        unsafe_allow_html=True)
        if st.button("Create label", key="ae_create_lbl", type="primary"):
            if new_lbl_name.strip():
                existing = [l["name"].lower() for l in fresh_labels]
                if new_lbl_name.strip().lower() in existing:
                    st.warning("Label already exists.")
                else:
                    add_label(user_id, new_lbl_name.strip(), chosen_hex)
                    st.toast(f'✅ Label "{new_lbl_name.strip()}" created', icon="🏷️")
                    st.rerun()

    # ── Receipt attachment ─────────────────────────────────────
    st.markdown("### 📎 Receipt")
    uploaded = st.file_uploader("Attach receipt image",
                                 type=["jpg","jpeg","png","webp"],
                                 label_visibility="collapsed")
    receipt_image = uploaded.read() if uploaded else None
    if uploaded:
        st.image(uploaded, width=180)

    st.divider()

    # ── Submit ────────────────────────────────────────────────
    if st.button("✅ Log expense", type="primary", use_container_width=True):
        if amount <= 0:
            st.error("Please enter a valid amount.")
        else:
            cat = cat_map[cat_name]
            add_expense(
                user_id, cat["id"], amount,
                note=note,
                payment_method=payment_method,
                location=location,
                warranty_months=int(warranty_months),
                payment_status=payment_status,
                receipt_image=receipt_image,
                label_ids=",".join(selected_label_ids),
            )
            updated     = get_spending_by_category(user_id)
            alert_fired = False
            for a in check_alert_thresholds(updated):
                if a["category_id"] == cat["id"]:
                    msg = (f"Spent {fmt(a['spent'])} of {fmt(a['limit'])} "
                           f"on {a['category_name']} ({a['pct']:.0f}%)."
                           + (" Over budget!" if a["over"] else " Getting close."))
                    create_alert(user_id, a["category_id"], msg)
                    alert_fired = True
                    if a["over"]:
                        st.toast(f"🔴 Over budget on {cat['icon']} {cat_name}!", icon="⚠️")
                    else:
                        st.toast(f"🟠 {cat['icon']} {cat_name} at {a['pct']:.0f}% of budget", icon="⚠️")
            if not alert_fired:
                st.toast(f"✅ {fmt(amount)} logged under {cat['icon']} {cat_name}", icon="💰")

            # Return to dashboard
            st.session_state["page"] = "dashboard"
            st.rerun()
