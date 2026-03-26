import streamlit as st
import yaml
import os
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from db import init_db, get_profile

st.set_page_config(
    page_title="BudgetIQ",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Load auth config ─────────────────────────────────────────
config_path = os.path.join(os.path.dirname(__file__), "auth_config.yaml")
with open(config_path) as f:
    config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

# ── Login screen ─────────────────────────────────────────────
name, authentication_status, username = authenticator.login(
    location="main",
    fields={
        "Form name": "💰 BudgetIQ — Sign in",
        "Username": "Username",
        "Password": "Password",
        "Login": "Sign in",
    }
)

if authentication_status is False:
    st.error("Incorrect username or password.")
    st.stop()

if authentication_status is None:
    st.info("Enter your credentials to continue.")
    st.stop()

# ── Authenticated ────────────────────────────────────────────
user_id = username  # use username as the unique user key

# Cache profile in session state to avoid repeated DB reads
if "profile" not in st.session_state or st.session_state.get("profile_user") != user_id:
    st.session_state["profile"] = get_profile(user_id)
    st.session_state["profile_user"] = user_id

profile = st.session_state["profile"]

if "page" not in st.session_state or st.session_state.get("auth_user") != user_id:
    st.session_state["page"] = "dashboard" if profile else "onboarding"
    st.session_state["auth_user"] = user_id

if profile and "onboarding_complete" not in st.session_state:
    st.session_state["onboarding_complete"] = True

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 BudgetIQ")
    st.divider()

    if st.session_state.get("onboarding_complete"):
        pages = {
            "dashboard": "📊  Dashboard",
            "receipt":   "📸  Scan receipt",
            "alerts":    "🔔  Alerts",
        }
        for key, label in pages.items():
            active = st.session_state["page"] == key
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary"):
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

    st.divider()
    authenticator.logout("Sign out", location="sidebar")

# ── Page routing ──────────────────────────────────────────────
page = st.session_state["page"]

if page == "onboarding":
    from views.onboarding import render
    render(user_id)

elif page == "dashboard":
    from views.dashboard import render
    render(user_id)

elif page == "receipt":
    from views.receipt import render
    render(user_id)

elif page == "alerts":
    from views.alerts import render
    render(user_id)
