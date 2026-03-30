import streamlit as st
from db import add_expense, get_categories, get_spending_by_category, create_alert, get_labels, add_label
from utils.ocr import extract_receipt_data
from utils.calculations import check_alert_thresholds, format_currency


def parse_amount(val: str) -> float:
    try:
        return float(str(val).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0


def render(user_id: str):
    profile = st.session_state.get("profile", {})
    currency = profile.get("currency", "PKR")
    fmt = lambda x: format_currency(x, currency)

    st.markdown("## 📸 Scan a receipt")
    st.caption("Upload a photo of your receipt — we'll extract the amount automatically.")

    categories = get_categories(user_id)
    if not categories:
        st.warning("No budget categories set up yet. Complete onboarding first.")
        return

    cat_map = {c["name"]: c for c in categories}

    # ── Upload ────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload receipt photo",
        type=["jpg", "jpeg", "png", "webp", "heic"],
        help="Take a clear photo of the receipt in good lighting for best results."
    )

    if not uploaded:
        st.info("📱 Tip: On mobile, you can take a photo directly from your camera.")
        return

    image_bytes = uploaded.read()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.image(image_bytes, caption="Uploaded receipt", use_container_width=True)

    with col2:
        with st.spinner("Reading receipt..."):
            result = extract_receipt_data(image_bytes)

        if result.get("error"):
            if "not configured" in result["error"]:
                st.warning("⚠️ OCR not set up yet — enter the amount manually below.")
            else:
                st.error(f"OCR error: {result['error']}")

        if result.get("raw_text"):
            with st.expander("Raw text extracted from receipt"):
                st.code(result["raw_text"])

        st.markdown("### Confirm expense details")
        st.caption("Review what we found and adjust if needed.")

        merchant = result.get("merchant") or ""
        ocr_amount = result.get("amount")
        detected_amount_str = f"{ocr_amount:,.0f}" if ocr_amount else ""
        if ocr_amount:
            st.success(f"✓ Detected amount: **{fmt(ocr_amount)}**")

        amount_input = st.text_input("Amount", value=detected_amount_str,
                                     placeholder="e.g. 1,250", key="receipt_amount")
        amount = parse_amount(amount_input)
        note_input = st.text_input("Note / merchant", value=merchant,
                                   placeholder="e.g. Lunch at Hardees", key="receipt_note")
        cat_name = st.selectbox("Category", list(cat_map.keys()), key="receipt_cat")

        # Extra fields
        PAYMENT_METHODS = ["Cash", "Credit card", "Debit card", "Bank transfer", "Other"]
        PAYMENT_STATUSES = ["Cleared", "Uncleared", "Pending", "Void"]
        with st.expander("More details"):
            rc1, rc2 = st.columns(2)
            payment_method = rc1.selectbox("Payment method", PAYMENT_METHODS, key="r_method")
            payment_status = rc2.selectbox("Payment status", PAYMENT_STATUSES, key="r_status")
            location = st.text_input("Location", value=merchant,
                                     placeholder="e.g. Carrefour, Gulberg", key="r_location")
            warranty_months = st.number_input("Warranty (months, 0 = none)",
                                              min_value=0, max_value=120, value=0, key="r_warranty")
            labels = get_labels(user_id)
            selected_labels = []
            if labels:
                st.markdown("**Labels**")
                lcols = st.columns(min(4, len(labels)))
                for i, lbl in enumerate(labels):
                    with lcols[i % len(lcols)]:
                        if st.checkbox(lbl["name"], key=f"r_lbl_{lbl['id']}"):
                            selected_labels.append(str(lbl["id"]))

        if amount > 0:
            st.info(f"Ready to log: **{fmt(amount)}** under {cat_map[cat_name]['icon']} {cat_name}")

        if st.button("✓ Log this expense", type="primary", use_container_width=True):
            if amount <= 0:
                st.error("Please enter a valid amount.")
            else:
                cat = cat_map[cat_name]
                add_expense(
                    user_id, cat["id"], amount,
                    note=note_input,
                    flagged=False,
                    receipt_text=result.get("raw_text", ""),
                    payment_method=payment_method,
                    location=location,
                    warranty_months=int(warranty_months),
                    payment_status=payment_status,
                    receipt_image=image_bytes,
                    label_ids=",".join(selected_labels),
                )

                updated = get_spending_by_category(user_id)
                alert_fired = False
                for a in check_alert_thresholds(updated):
                    if a["category_id"] == cat["id"]:
                        msg = (
                            f"Spent {fmt(a['spent'])} of {fmt(a['limit'])} "
                            f"on {a['category_name']} ({a['pct']:.0f}%)."
                            + (" Over budget!" if a["over"] else " Getting close.")
                        )
                        create_alert(user_id, a["category_id"], msg)
                        alert_fired = True
                        if a["over"]:
                            st.toast(f"🔴 Over budget on {cat['icon']} {cat_name}!", icon="⚠️")
                        else:
                            st.toast(f"🟠 {cat['icon']} {cat_name} at {a['pct']:.0f}% of budget", icon="⚠️")
                if not alert_fired:
                    st.toast(f"✅ {fmt(amount)} logged under {cat['icon']} {cat_name}", icon="📸")

                st.session_state.pop("receipt_amount", None)
                st.session_state.pop("receipt_note", None)
                st.rerun()
