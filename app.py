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

config_path = os.path.join(os.path.dirname(__file__), "auth_config.yaml")
with open(config_path) as f:
    config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

try:
    authenticator.login()
    authentication_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")
    name     = st.session_state.get("name")
except TypeError:
    result = authenticator.login("Login", "main")
    if isinstance(result, tuple):
        name, authentication_status, username = result
    else:
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
        name     = st.session_state.get("name")

if authentication_status is False:
    st.error("Incorrect username or password.")
    st.stop()

if authentication_status is None:
    st.markdown("## 💰 BudgetIQ")
    st.info("Enter your credentials above to continue.")
    st.stop()

user_id = username

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
        # Main nav pages
        nav_pages = {
            "dashboard":    "📊  Dashboard",
            "transactions": "🧾  Transactions",
            "goals":        "🎯  Goals",
            "receipt":      "📸  Scan receipt",
            "alerts":       "🔔  Alerts",
            "labels":       "🏷️  Labels",
        }
        for key, label in nav_pages.items():
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
    authenticator.logout("Sign out", "sidebar")

# ── Routing ───────────────────────────────────────────────────
page = st.session_state["page"]

if page == "onboarding":
    from views.onboarding import render
    render(user_id)
elif page == "dashboard":
    from views.dashboard import render
    render(user_id)
elif page == "add_expense":
    from views.add_expense import render
    render(user_id)
elif page == "transactions":
    from views.transactions import render
    render(user_id)
elif page == "goals":
    from views.goals import render
    render(user_id)
elif page == "labels":
    from views.labels import render
    render(user_id)
elif page == "receipt":
    from views.receipt import render
    render(user_id)
elif page == "alerts":
    from views.alerts import render
    render(user_id)
