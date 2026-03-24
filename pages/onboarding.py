import streamlit as st
from db import save_profile, save_goals, save_categories, get_profile

DEFAULT_CATEGORIES = [
    {"name": "Food & Dining",    "monthly_limit": 0.0, "icon": "🍽️"},
    {"name": "Transport",        "monthly_limit": 0.0, "icon": "🚗"},
    {"name": "Utilities",        "monthly_limit": 0.0, "icon": "💡"},
    {"name": "Shopping",         "monthly_limit": 0.0, "icon": "🛍️"},
    {"name": "Health",           "monthly_limit": 0.0, "icon": "🏥"},
    {"name": "Entertainment",    "monthly_limit": 0.0, "icon": "🎬"},
    {"name": "Education",        "monthly_limit": 0.0, "icon": "📚"},
    {"name": "Miscellaneous",    "monthly_limit": 0.0, "icon": "📦"},
]


def render():
    st.markdown("## 👋 Welcome — let's set up your budget")
    st.markdown("This takes about 2 minutes. We'll ask for your income, your financial goals, and your monthly spending limits.")
    st.divider()

    step = st.session_state.get("onboarding_step", 1)

    # ── Step indicator ──────────────────────────────────────
    cols = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, ["1 · Profile", "2 · Goals", "3 · Budget"]), 1):
        with col:
            if i < step:
                st.success(f"✓ {label}")
            elif i == step:
                st.info(f"**{label}**")
            else:
                st.markdown(f"<div style='color:gray'>{label}</div>", unsafe_allow_html=True)

    st.divider()

    # ── Step 1: Profile ─────────────────────────────────────
    if step == 1:
        st.markdown("### Your profile")
        name = st.text_input("Your name", placeholder="e.g. Ahmed")
        currency = st.selectbox("Currency", ["PKR", "USD", "EUR", "GBP"])
        income = st.number_input(
            "Monthly income (after tax)",
            min_value=0.0, step=1000.0,
            help="Enter your take-home monthly income"
        )

        if st.button("Continue →", type="primary", use_container_width=True):
            if not name:
                st.error("Please enter your name.")
            elif income <= 0:
                st.error("Please enter your monthly income.")
            else:
                save_profile(name, income, currency)
                st.session_state["onboarding_step"] = 2
                st.session_state["currency"] = currency
                st.rerun()

    # ── Step 2: Goals ────────────────────────────────────────
    elif step == 2:
        st.markdown("### Financial goals")
        st.caption("Add up to 4 goals — e.g. emergency fund, car, home down payment.")

        if "goals_draft" not in st.session_state:
            st.session_state["goals_draft"] = [
                {"name": "", "target_amount": 0.0, "deadline": "2026-12-31", "priority": 1}
            ]

        goals = st.session_state["goals_draft"]

        for i, g in enumerate(goals):
            with st.expander(f"Goal {i+1}: {g['name'] or 'untitled'}", expanded=True):
                c1, c2 = st.columns([2, 1])
                goals[i]["name"] = c1.text_input("Goal name", value=g["name"], key=f"gname_{i}", placeholder="e.g. Emergency fund")
                goals[i]["priority"] = c2.selectbox("Priority", [1, 2, 3], index=g["priority"]-1, key=f"gpri_{i}", format_func=lambda x: ["High","Medium","Low"][x-1])
                c3, c4 = st.columns(2)
                goals[i]["target_amount"] = c3.number_input("Target amount", value=g["target_amount"], step=1000.0, key=f"gamt_{i}")
                goals[i]["deadline"] = c4.text_input("Deadline (YYYY-MM-DD)", value=g["deadline"], key=f"gdl_{i}")

        c1, c2 = st.columns(2)
        if c1.button("+ Add goal") and len(goals) < 4:
            goals.append({"name": "", "target_amount": 0.0, "deadline": "2027-12-31", "priority": 2})
            st.rerun()

        st.divider()
        cc1, cc2 = st.columns(2)
        if cc1.button("← Back"):
            st.session_state["onboarding_step"] = 1
            st.rerun()

        if cc2.button("Continue →", type="primary", use_container_width=True):
            valid = [g for g in goals if g["name"] and g["target_amount"] > 0]
            if not valid:
                st.error("Add at least one goal with a name and amount.")
            else:
                save_goals(valid)
                st.session_state["onboarding_step"] = 3
                st.rerun()

    # ── Step 3: Budget categories ────────────────────────────
    elif step == 3:
        profile = get_profile()
        income = profile["monthly_income"] if profile else 0
        currency = profile.get("currency", "PKR") if profile else "PKR"

        st.markdown("### Monthly spending limits")
        st.caption(f"Set how much you plan to spend per category. Your income: **{currency} {income:,.0f}**")

        if "cats_draft" not in st.session_state:
            st.session_state["cats_draft"] = [dict(c) for c in DEFAULT_CATEGORIES]

        cats = st.session_state["cats_draft"]
        total_allocated = sum(c["monthly_limit"] for c in cats)
        remaining = income - total_allocated

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Income", f"{currency} {income:,.0f}")
        col_b.metric("Allocated", f"{currency} {total_allocated:,.0f}")
        col_c.metric("Remaining", f"{currency} {remaining:,.0f}", delta=f"{remaining/income*100:.0f}% free" if income > 0 else None)

        st.divider()

        for i, cat in enumerate(cats):
            c1, c2 = st.columns([1, 2])
            c1.markdown(f"**{cat['icon']} {cat['name']}**")
            cats[i]["monthly_limit"] = c2.number_input(
                f"Limit", value=cat["monthly_limit"], step=500.0,
                key=f"cat_{i}", label_visibility="collapsed"
            )

        st.divider()
        if remaining < 0:
            st.warning(f"⚠️ You've allocated {currency} {abs(remaining):,.0f} more than your income. Adjust your limits.")

        cc1, cc2 = st.columns(2)
        if cc1.button("← Back"):
            st.session_state["onboarding_step"] = 2
            st.rerun()

        if cc2.button("🚀 Launch my dashboard", type="primary", use_container_width=True):
            active_cats = [c for c in cats if c["monthly_limit"] > 0]
            if not active_cats:
                st.error("Set a limit for at least one category.")
            else:
                save_categories(active_cats)
                st.session_state["onboarding_complete"] = True
                st.session_state["page"] = "dashboard"
                st.session_state.pop("onboarding_step", None)
                st.session_state.pop("goals_draft", None)
                st.session_state.pop("cats_draft", None)
                st.rerun()
