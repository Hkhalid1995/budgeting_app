import streamlit as st
from datetime import datetime
from db import (get_profile, get_goals, get_spending_by_category,
                get_expenses_this_month, add_expense, update_expense,
                delete_expense, get_categories, create_alert, get_active_alerts,
                get_labels, add_label, delete_label, update_label)
from utils.calculations import compute_savings_plan, check_alert_thresholds, format_currency

PAYMENT_METHODS  = ["Cash", "Credit card", "Debit card", "Bank transfer", "Other"]
PAYMENT_STATUSES = ["Cleared", "Uncleared", "Pending", "Void"]

LABEL_COLOR_OPTIONS = {
    "Red":    "#e74c3c",
    "Orange": "#e67e22",
    "Yellow": "#f0b429",
    "Green":  "#2ecc71",
    "Teal":   "#1abc9c",
    "Blue":   "#3498db",
    "Purple": "#9b59b6",
    "Pink":   "#e91e8c",
    "Gray":   "#95a5a6",
}
COLOR_NAME_MAP = {v: k for k, v in LABEL_COLOR_OPTIONS.items()}
COLOR_NAMES    = list(LABEL_COLOR_OPTIONS.keys())


def parse_amount(val: str) -> float:
    try:
        return float(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def status_badge(status: str) -> str:
    styles = {
        "cleared":   ("✓", "#2ecc71"),
        "uncleared": ("○", "#e67e22"),
        "pending":   ("⋯", "#3498db"),
        "void":      ("✕", "#95a5a6"),
    }
    icon, color = styles.get((status or "cleared").lower(), ("○", "#95a5a6"))
    return (f'<span style="color:{color};font-size:11px;font-weight:500">'
            f'{icon} {(status or "Cleared").title()}</span>')


def method_icon(method: str) -> str:
    return {"cash": "💵", "credit card": "💳", "debit card": "🏧",
            "bank transfer": "🏦", "other": "💱"}.get((method or "cash").lower(), "💵")


def label_pill(lbl: dict) -> str:
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:1px 8px;'
            f'border-radius:10px;font-size:11px;border:1px solid {c}55;'
            f'font-weight:500">{lbl["name"]}</span>')


def color_swatch_row(colors: dict) -> str:
    """Renders a single-row HTML strip of color swatches for reference."""
    swatches = "".join(
        f'<span title="{name}" style="display:inline-block;width:18px;height:18px;'
        f'background:{hex_val};border-radius:4px;margin-right:4px;'
        f'border:1px solid {hex_val}cc;vertical-align:middle"></span>'
        for name, hex_val in colors.items()
    )
    return f'<div style="line-height:2;margin-bottom:4px">{swatches}</div>'


def color_selectbox(key: str, current_color: str = None) -> str:
    """
    Renders a color selectbox where each option shows a colored square swatch.
    Returns the selected hex color value.
    Uses st.markdown for a visual swatch strip + selectbox synced together.
    """
    current_name = COLOR_NAME_MAP.get(current_color, COLOR_NAMES[0])
    idx = COLOR_NAMES.index(current_name) if current_name in COLOR_NAMES else 0

    selected_name = st.selectbox(
        "Color",
        COLOR_NAMES,
        index=idx,
        key=key,
        label_visibility="collapsed",
        format_func=lambda n: n,  # plain name — no bullet
    )
    hex_val = LABEL_COLOR_OPTIONS[selected_name]

    # Show a live swatch of the selected color below the dropdown
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;margin-top:-8px;margin-bottom:6px">'
        f'<span style="display:inline-block;width:20px;height:20px;background:{hex_val};'
        f'border-radius:4px;border:1px solid {hex_val}cc"></span>'
        f'<span style="font-size:12px;color:{hex_val};font-weight:600">{selected_name}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    return hex_val


def color_swatch_select(key: str, current_color: str = None) -> str:
    """
    Click-to-select color grid using radio buttons rendered as swatches.
    Much better UX than a dropdown for colors.
    """
    current_name = COLOR_NAME_MAP.get(current_color, COLOR_NAMES[0])

    # Build HTML swatch strip for visual reference
    st.markdown(color_swatch_row(LABEL_COLOR_OPTIONS), unsafe_allow_html=True)

    selected_name = st.radio(
        "Pick a color",
        COLOR_NAMES,
        index=COLOR_NAMES.index(current_name),
        key=key,
        horizontal=True,
        label_visibility="collapsed",
        format_func=lambda n: "",   # hide text — swatches above are the guide
    )
    # This approach doesn't work well because radio button labels can't be hidden cleanly.
    # Fall back to the selectbox with live swatch approach.
    return LABEL_COLOR_OPTIONS[selected_name]


def inline_label_creator(key_prefix: str, user_id: str) -> bool:
    """
    Mini label creation form inside the expense form expander.
    Returns True if a new label was just created (triggers rerun).
    """
    with st.expander("＋ Create a new label", expanded=False):
        nc1, nc2 = st.columns([3, 2])
        new_name = nc1.text_input(
            "Label name",
            placeholder="e.g. Business, Tax, Family",
            key=f"{key_prefix}_inline_lbl_name",
            label_visibility="collapsed",
        )

        # Color selector with visual swatch
        selected_color_name = nc2.selectbox(
            "Color",
            COLOR_NAMES,
            key=f"{key_prefix}_inline_lbl_color",
            label_visibility="collapsed",
        )
        hex_val = LABEL_COLOR_OPTIONS[selected_color_name]

        # Live preview of what the label pill will look like
        if new_name.strip():
            preview_lbl = {"name": new_name.strip(), "color": hex_val}
            st.markdown(
                f'Preview: &nbsp;{label_pill(preview_lbl)}',
                unsafe_allow_html=True,
            )

        # Color swatch strip
        st.markdown(color_swatch_row(LABEL_COLOR_OPTIONS), unsafe_allow_html=True)

        # Show selected color swatch
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
            f'<span style="display:inline-block;width:16px;height:16px;background:{hex_val};'
            f'border-radius:3px;border:1px solid {hex_val}cc"></span>'
            f'<span style="font-size:12px;color:{hex_val};font-weight:600">{selected_color_name}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if st.button("Create label", key=f"{key_prefix}_inline_create_lbl", type="primary"):
            if not new_name.strip():
                st.warning("Enter a label name.")
            else:
                existing = get_labels(user_id)
                if new_name.strip().lower() in [l["name"].lower() for l in existing]:
                    st.warning(f'"{new_name.strip()}" already exists.')
                else:
                    add_label(user_id, new_name.strip(), hex_val)
                    st.toast(f'✅ Label "{new_name.strip()}" created', icon="🏷️")
                    return True
    return False


def label_multiselect(key_prefix: str, labels: list, current_ids: list) -> list:
    """
    Multiselect for labels. Shows a colored emoji swatch before each label name
    in the dropdown. Returns list of selected label id strings.
    """
    if not labels:
        st.caption("No labels yet — use 'Create a new label' below.")
        return []

    # Build display options with color emoji prefix so the dropdown looks visual
    def label_display(lbl: dict) -> str:
        color_name = COLOR_NAME_MAP.get(lbl["color"], "Gray")
        return f"{COLOR_EMOJI.get(color_name, '⬜')} {lbl['name']}"

    display_to_id = {label_display(l): str(l["id"]) for l in labels}
    id_to_display = {str(l["id"]): label_display(l) for l in labels}
    default_displays = [id_to_display[i] for i in current_ids if i in id_to_display]

    selected_displays = st.multiselect(
        "Labels",
        options=list(display_to_id.keys()),
        default=default_displays,
        key=f"{key_prefix}_labels_ms",
        placeholder="Assign labels...",
    )
    return [display_to_id[d] for d in selected_displays]


def expense_detail_form(key_prefix, categories, labels, defaults=None, user_id=""):
    """Full expense form. Returns dict of all field values."""
    d = defaults or {}
    cat_names  = [c["name"] for c in categories]
    default_cat = d.get("category_name", cat_names[0] if cat_names else "")
    cat_idx    = cat_names.index(default_cat) if default_cat in cat_names else 0

    fc1, fc2 = st.columns(2)
    cat_name   = fc1.selectbox("Category", cat_names, index=cat_idx, key=f"{key_prefix}_cat")
    amount_str = fc2.text_input(
        "Amount",
        value=str(int(d["amount"])) if d.get("amount") else "",
        placeholder="e.g. 1,500",
        key=f"{key_prefix}_amount",
    )
    note = st.text_input("Note (optional)", value=d.get("note", ""),
                         placeholder="e.g. Lunch at office", key=f"{key_prefix}_note")

    # Initialise mutable state for warranty inside this form
    warranty_val = int(d.get("warranty_months") or 0)

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
                                            value=warranty_val,
                                            key=f"{key_prefix}_warranty")
        if warranty_months > 0:
            wc2.markdown(
                f"<div style='padding-top:28px;font-size:12px'>🛡️ {warranty_months}mo</div>",
                unsafe_allow_html=True,
            )

        # ── Labels ────────────────────────────────────────────
        st.markdown("**Labels**")
        # Refresh labels in case user just created one inline
        fresh_labels = get_labels(user_id) if user_id else labels
        current_ids  = [x for x in (d.get("label_ids") or "").split(",") if x.strip()]
        selected_label_ids = label_multiselect(key_prefix, fresh_labels, current_ids)

        # Show selected pills live
        if selected_label_ids:
            id_to_label = {str(l["id"]): l for l in fresh_labels}
            pills = " ".join(label_pill(id_to_label[i])
                             for i in selected_label_ids if i in id_to_label)
            if pills:
                st.markdown(pills, unsafe_allow_html=True)

        # Inline label creator
        if user_id:
            created = inline_label_creator(key_prefix, user_id)
            if created:
                st.rerun()

        # ── Receipt attachment ────────────────────────────────
        st.markdown("**Receipt attachment**")
        uploaded_img = st.file_uploader(
            "Attach receipt",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"{key_prefix}_receipt_img",
            label_visibility="collapsed",
        )
        receipt_image = uploaded_img.read() if uploaded_img else d.get("receipt_image")
        if uploaded_img:
            st.image(uploaded_img, width=120)
        elif d.get("receipt_image"):
            st.image(d["receipt_image"], caption="Current receipt", width=120)

    return {
        "cat_name":        cat_name,
        "amount":          parse_amount(amount_str),
        "amount_str":      amount_str,
        "note":            note,
        "payment_method":  payment_method,
        "payment_status":  payment_status,
        "location":        location,
        "warranty_months": int(warranty_months),
        "label_ids":       ",".join(selected_label_ids),
        "receipt_image":   receipt_image,
    }


def label_manager(user_id: str):
    """Dedicated section for managing all labels."""
    st.markdown("### 🏷️ Labels")
    labels = get_labels(user_id)

    if labels:
        for lbl in labels:
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])

            # Current pill
            c1.markdown(label_pill(lbl), unsafe_allow_html=True)

            # Color selectbox — plain names, no bullet
            current_name = COLOR_NAME_MAP.get(lbl["color"], COLOR_NAMES[0])
            new_color_name = c2.selectbox(
                "Color",
                COLOR_NAMES,
                index=COLOR_NAMES.index(current_name),
                key=f"lbl_color_{lbl['id']}",
                label_visibility="collapsed",
            )
            new_hex = LABEL_COLOR_OPTIONS[new_color_name]

            # Live color swatch next to dropdown
            c2.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;margin-top:-10px">'
                f'<span style="display:inline-block;width:14px;height:14px;background:{new_hex};'
                f'border-radius:3px;border:1px solid {new_hex}cc"></span>'
                f'<span style="font-size:11px;color:{new_hex};font-weight:600">{new_color_name}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if c3.button("Save", key=f"lbl_save_{lbl['id']}"):
                update_label(lbl["id"], user_id, lbl["name"], new_hex)
                st.toast(f'✅ "{lbl["name"]}" updated', icon="🏷️")
                st.rerun()

            if c4.button("✕", key=f"lbl_del_{lbl['id']}", help="Delete label"):
                delete_label(lbl["id"], user_id)
                st.rerun()
    else:
        st.caption("No labels yet — create your first one below.")

    # ── Create new label ──────────────────────────────────────
    st.markdown("**Create a new label**")
    nc1, nc2 = st.columns([3, 2])
    new_name = nc1.text_input(
        "Label name",
        placeholder="e.g. Business, Family, Tax",
        key="mgr_new_lbl_name",
        label_visibility="collapsed",
    )
    chosen_name = nc2.selectbox(
        "Color",
        COLOR_NAMES,
        key="mgr_new_lbl_color",
        label_visibility="collapsed",
    )
    chosen_hex = LABEL_COLOR_OPTIONS[chosen_name]

    # Swatch + color name preview
    nc2.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;margin-top:-10px">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{chosen_hex};'
        f'border-radius:3px;border:1px solid {chosen_hex}cc"></span>'
        f'<span style="font-size:11px;color:{chosen_hex};font-weight:600">{chosen_name}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Live pill preview
    if new_name.strip():
        st.markdown(
            f'Preview: &nbsp;{label_pill({"name": new_name.strip(), "color": chosen_hex})}',
            unsafe_allow_html=True,
        )

    if st.button("Create label", type="primary", key="mgr_create_lbl"):
        if not new_name.strip():
            st.warning("Enter a label name.")
        else:
            existing = get_labels(user_id)
            if new_name.strip().lower() in [l["name"].lower() for l in existing]:
                st.warning(f'"{new_name.strip()}" already exists.')
            else:
                add_label(user_id, new_name.strip(), chosen_hex)
                st.toast(f'✅ Label "{new_name.strip()}" created', icon="🏷️")
                st.rerun()


def render(user_id: str):
    st.session_state["_user_id"] = user_id

    profile = get_profile(user_id)
    if not profile:
        st.error("Profile not found. Please complete onboarding.")
        return

    currency   = profile.get("currency", "PKR")
    fmt        = lambda x: format_currency(x, currency)
    income     = profile["monthly_income"]
    goals      = get_goals(user_id)
    spending   = get_spending_by_category(user_id)
    plan       = compute_savings_plan(income, goals, spending)
    categories = get_categories(user_id)
    labels     = get_labels(user_id)
    cat_map    = {c["name"]: c for c in categories}
    label_map  = {str(l["id"]): l for l in labels}

    st.markdown(f"## 👋 Hey {profile['name']}")
    st.caption(f"{datetime.now().strftime('%B %Y')} · {currency} overview")

    active_alerts = get_active_alerts(user_id)
    if active_alerts:
        for alert in active_alerts:
            st.warning(f"{alert['icon']} **{alert['category_name']}** — {alert['message']}", icon="🔔")

    st.divider()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly income",   fmt(income))
    m2.metric("Total budgeted",   fmt(plan["total_budgeted"]))
    m3.metric("Spent this month", fmt(plan["total_spent"]),
              delta=f"{fmt(plan['remaining_budget'])} left",
              delta_color="normal" if plan["remaining_budget"] >= 0 else "inverse")
    m4.metric("Savings rate",     f"{plan['savings_rate_pct']:.1f}%")

    st.divider()
    st.markdown("### 📊 Budget vs spending")
    for cat in spending:
        limit     = cat["monthly_limit"]
        spent     = cat["spent"]
        pct       = min((spent / limit * 100) if limit > 0 else 0, 100)
        over      = spent > limit
        bar_color = "#d62728" if over else ("#ff7f0e" if pct >= 80 else "#2ca02c")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"{cat['icon']} **{cat['name']}** — {fmt(spent)} / {fmt(limit)}")
            st.markdown(
                f'<div style="background:#e0e0e0;border-radius:6px;height:10px;margin-bottom:12px">'
                f'<div style="width:{pct:.0f}%;background:{bar_color};height:10px;border-radius:6px">'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with col2:
            if over:
                st.error(f"Over {fmt(spent - limit)}")
            else:
                st.caption(f"{fmt(limit - spent)} left")

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
    st.markdown("### ➕ Log an expense")
    if not categories:
        st.info("No categories set up yet.")
    else:
        form_values = expense_detail_form("new", categories, labels, user_id=user_id)
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
                            st.toast(f"🔴 Over budget on {cat['icon']} {form_values['cat_name']}!", icon="⚠️")
                        else:
                            st.toast(f"🟠 {cat['icon']} {form_values['cat_name']} at {a['pct']:.0f}% of budget", icon="⚠️")
                if not alert_fired:
                    st.toast(f"✅ {fmt(form_values['amount'])} logged under {cat['icon']} {form_values['cat_name']}", icon="💰")
                st.rerun()

    st.divider()
    st.markdown("### 🧾 Recent transactions")
    expenses = get_expenses_this_month(user_id)

    # Refresh label_map in case labels changed
    label_map = {str(l["id"]): l for l in get_labels(user_id)}

    if not expenses:
        st.caption("No expenses this month yet.")
    else:
        for e in expenses[:20]:
            row1, row2 = st.columns([5, 2])
            with row1:
                warranty_tag = f" 🛡️ {e.get('warranty_months', 0)}mo" if e.get("warranty_months") else ""
                st.markdown(
                    f"{'🚩 ' if e['flagged'] else ''}{e['icon']} **{e['category_name']}** &nbsp;"
                    f"{method_icon(e.get('payment_method', 'cash'))} "
                    f"`{(e.get('payment_method') or 'Cash').title()}`"
                    f"{warranty_tag}",
                    unsafe_allow_html=True,
                )
                note_text = f" · {e['note']}"       if e.get("note")     else ""
                loc_text  = f" 📍 {e['location']}"  if e.get("location") else ""
                st.markdown(
                    f"<span style='font-size:12px'>"
                    f"{e['date'][:10]}{note_text}{loc_text} &nbsp;"
                    f"{status_badge(e.get('payment_status', 'cleared'))}"
                    f"</span>",
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
                    fresh_labels = get_labels(user_id)
                    edit_vals = expense_detail_form(
                        f"edit_{e['id']}", categories, fresh_labels,
                        defaults=e, user_id=user_id,
                    )
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
                if ec2.button("🗑️", key=f"del_{e['id']}", help="Delete"):
                    delete_expense(e["id"], user_id)
                    st.toast("Expense deleted", icon="🗑️")
                    st.rerun()
            st.divider()

    st.divider()
    label_manager(user_id)
