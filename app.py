import streamlit as st
from db import init_db, get_profile

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="BudgetIQ",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Init DB ──────────────────────────────────────────────────
init_db()

# ── Determine first-time vs returning user ───────────────────
profile = get_profile()
if "page" not in st.session_state:
    st.session_state["page"] = "dashboard" if profile else "onboarding"

if profile and "onboarding_complete" not in st.session_state:
    st.session_state["onboarding_complete"] = True

# ── Sidebar nav (only shown after onboarding) ────────────────
if st.session_state.get("onboarding_complete"):
    with st.sidebar:
        st.markdown("## 💰 BudgetIQ")
        st.divider()

        pages = {
            "dashboard": "📊  Dashboard",
            "alerts":    "🔔  Alerts",
        }

        for key, label in pages.items():
            active = st.session_state["page"] == key
            if st.button(label, use_container_width=True, type="primary" if active else "secondary"):
                st.session_state["page"] = key
                st.rerun()

        st.divider()

        if profile:
            st.caption(f"👤 {profile['name']}")
            st.caption(f"💵 {profile['currency']} {profile['monthly_income']:,.0f}/mo")

        st.divider()
        if st.button("⚙️ Re-run onboarding", use_container_width=True):
            st.session_state["page"] = "onboarding"
            st.session_state["onboarding_complete"] = False
            st.session_state.pop("onboarding_step", None)
            st.rerun()

# ── Page routing ─────────────────────────────────────────────
page = st.session_state["page"]

if page == "onboarding":
    from pages.onboarding import render
    render()

elif page == "dashboard":
    from pages.dashboard import render
    render()

elif page == "alerts":
    from pages.alerts import render
    render()
