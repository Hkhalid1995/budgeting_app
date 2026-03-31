import streamlit as st
from db import get_profile, get_goals, save_goals
from utils.calculations import format_currency, months_until


def parse_amount(val):
    try:
        return float(str(val).replace(",","").replace(" ",""))
    except Exception:
        return 0.0


def render(user_id: str):
    profile  = get_profile(user_id)
    currency = profile.get("currency","PKR") if profile else "PKR"
    fmt      = lambda x: format_currency(x, currency)
    income   = profile["monthly_income"] if profile else 0

    st.markdown("## 🎯 Financial goals")
    st.divider()

    if "goals_edit" not in st.session_state:
        raw = get_goals(user_id)
        st.session_state["goals_edit"] = [dict(g) for g in raw] if raw else []

    goals = st.session_state["goals_edit"]

    if not goals:
        st.info("No goals yet. Add your first goal below.")

    # ── Existing goals ────────────────────────────────────────
    to_delete = None
    for i, g in enumerate(goals):
        with st.expander(f"{'🥇' if g.get('priority')==1 else '🥈' if g.get('priority')==2 else '🥉'} {g['name'] or f'Goal {i+1}'}", expanded=True):
            c1, c2 = st.columns([3,1])
            goals[i]["name"] = c1.text_input("Goal name", value=g["name"],
                                              key=f"gname_{i}", placeholder="e.g. Emergency fund")
            pri_map = {1:"High",2:"Medium",3:"Low"}
            pri_idx = int(g.get("priority",1)) - 1
            goals[i]["priority"] = c2.selectbox("Priority", [1,2,3], index=pri_idx,
                                                  key=f"gpri_{i}",
                                                  format_func=lambda x: pri_map[x])

            a1, a2 = st.columns(2)
            amt_str = a1.text_input("Target amount",
                                     value=str(int(g["target_amount"])) if g.get("target_amount") else "",
                                     key=f"gamt_{i}", placeholder="e.g. 500,000")
            goals[i]["target_amount"] = parse_amount(amt_str)
            goals[i]["deadline"] = a2.text_input("Deadline (YYYY-MM-DD)",
                                                   value=g.get("deadline","2027-12-31"),
                                                   key=f"gdl_{i}")

            # Progress summary
            if goals[i]["target_amount"] > 0 and goals[i]["deadline"]:
                months_left    = months_until(goals[i]["deadline"])
                monthly_needed = goals[i]["target_amount"] / max(months_left, 1)
                share          = income / max(len(goals), 1)
                on_track       = monthly_needed <= share
                st.markdown(
                    f"Need **{fmt(monthly_needed)}/mo** over {months_left} months "
                    f"· {'✅ On track' if on_track else '⚠️ Tight'}",
                    unsafe_allow_html=True,
                )

            if st.button("Remove goal", key=f"gdel_{i}"):
                to_delete = i

    if to_delete is not None:
        goals.pop(to_delete)
        st.session_state["goals_edit"] = goals
        st.rerun()

    st.divider()

    # ── Add goal ──────────────────────────────────────────────
    col1, col2 = st.columns(2)
    if col1.button("＋ Add another goal", use_container_width=True):
        if len(goals) < 6:
            goals.append({"name":"","target_amount":0.0,
                          "deadline":"2027-12-31","priority":2})
            st.session_state["goals_edit"] = goals
            st.rerun()
        else:
            st.warning("Maximum 6 goals.")

    if col2.button("💾 Save all goals", type="primary", use_container_width=True):
        valid = [g for g in goals if g["name"] and g["target_amount"] > 0]
        if not valid:
            st.error("Add at least one goal with a name and target amount.")
        else:
            save_goals(user_id, valid)
            st.session_state.pop("goals_edit", None)
            st.toast("✅ Goals saved!", icon="🎯")
            st.rerun()
