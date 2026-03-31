import streamlit as st
from db import get_labels, add_label, delete_label, update_label

LABEL_COLOR_OPTIONS = {
    "Red":"#e74c3c","Orange":"#e67e22","Yellow":"#f0b429",
    "Green":"#2ecc71","Teal":"#1abc9c","Blue":"#3498db",
    "Purple":"#9b59b6","Pink":"#e91e8c","Gray":"#95a5a6",
}
COLOR_NAMES    = list(LABEL_COLOR_OPTIONS.keys())
COLOR_NAME_MAP = {v: k for k, v in LABEL_COLOR_OPTIONS.items()}


def label_pill(lbl):
    c = lbl["color"]
    return (f'<span style="background:{c}22;color:{c};padding:3px 12px;'
            f'border-radius:12px;font-size:13px;border:1px solid {c}55;'
            f'font-weight:500">{lbl["name"]}</span>')


def color_preview(hex_val, name):
    return (f'<div style="display:flex;align-items:center;gap:8px;margin-top:-4px;margin-bottom:4px">'
            f'<span style="display:inline-block;width:16px;height:16px;background:{hex_val};'
            f'border-radius:3px;border:1px solid {hex_val}99"></span>'
            f'<span style="font-size:12px;color:{hex_val};font-weight:600">{name}</span></div>')


def render(user_id: str):
    st.markdown("## 🏷️ Labels")
    st.caption("Create labels to tag your expenses. Use them to filter and group spending on the dashboard.")
    st.divider()

    labels = get_labels(user_id)

    # ── Existing labels ───────────────────────────────────────
    if labels:
        st.markdown("### Your labels")
        for lbl in labels:
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            c1.markdown(label_pill(lbl), unsafe_allow_html=True)

            cur_name = COLOR_NAME_MAP.get(lbl["color"], COLOR_NAMES[0])
            new_color_name = c2.selectbox(
                "Color", COLOR_NAMES,
                index=COLOR_NAMES.index(cur_name),
                key=f"lc_{lbl['id']}",
                label_visibility="collapsed",
            )
            new_hex = LABEL_COLOR_OPTIONS[new_color_name]
            c2.markdown(color_preview(new_hex, new_color_name), unsafe_allow_html=True)

            if c3.button("Save", key=f"ls_{lbl['id']}"):
                update_label(lbl["id"], user_id, lbl["name"], new_hex)
                st.toast(f'✅ "{lbl["name"]}" updated', icon="🏷️")
                st.rerun()

            if c4.button("✕", key=f"ld_{lbl['id']}", help="Delete label"):
                delete_label(lbl["id"], user_id)
                st.rerun()
    else:
        st.info("No labels yet. Create your first one below.")

    st.divider()

    # ── Create new label ──────────────────────────────────────
    st.markdown("### Create a new label")
    nc1, nc2 = st.columns([3, 2])
    new_name = nc1.text_input("Label name", placeholder="e.g. Business, Family, Tax",
                               key="lbl_new_name", label_visibility="collapsed")
    chosen_name = nc2.selectbox("Color", COLOR_NAMES, key="lbl_new_color",
                                 label_visibility="collapsed")
    chosen_hex  = LABEL_COLOR_OPTIONS[chosen_name]
    nc2.markdown(color_preview(chosen_hex, chosen_name), unsafe_allow_html=True)

    if new_name.strip():
        st.markdown(
            f'Preview: &nbsp;{label_pill({"name": new_name.strip(), "color": chosen_hex})}',
            unsafe_allow_html=True,
        )

    if st.button("Create label", type="primary", key="lbl_create"):
        if not new_name.strip():
            st.warning("Enter a label name.")
        else:
            existing = [l["name"].lower() for l in labels]
            if new_name.strip().lower() in existing:
                st.warning(f'"{new_name.strip()}" already exists.')
            else:
                add_label(user_id, new_name.strip(), chosen_hex)
                st.toast(f'✅ Label "{new_name.strip()}" created', icon="🏷️")
                st.rerun()
