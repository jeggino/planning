import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime

# -----------------------------
# Supabase client
# -----------------------------
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = get_supabase()

# -----------------------------
# Database helpers
# -----------------------------
@st.cache_data(ttl=5)
def get_assignments():
    return supabase.table("assignments").select("*").execute().data

@st.cache_data(ttl=5)
def get_rounds():
    return supabase.table("rounds").select(
        "*, assignments(name, area, hourly_rate, hours_per_round, min_days_between_rounds)"
    ).execute().data

def refresh():
    st.cache_data.clear()

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Work Planner", layout="wide")
st.title("Work Planner with Supabase")

tab1, tab2, tab3 = st.tabs(["📅 Rounds", "⚙ Assignments", "💶 Earnings"])

# ============================================================
# TAB 2 — ASSIGNMENTS
# ============================================================
with tab2:
    st.header("Assignment Settings")

    assignments = get_assignments()

    mode = st.radio("Mode", ["Create new", "Edit existing"])

    if mode == "Edit existing" and assignments:
        selected = st.selectbox(
            "Select assignment",
            assignments,
            format_func=lambda a: f"{a['name']} ({a['area']})"
        )
    else:
        selected = None

    name = st.text_input("Name", value=selected["name"] if selected else "")
    area = st.text_input("Area", value=selected["area"] if selected else "")
    hourly_rate = st.number_input("Hourly rate (€)", value=float(selected["hourly_rate"]) if selected else 0.0)
    hours_per_round = st.number_input("Hours per round", value=float(selected["hours_per_round"]) if selected else 0.0)
    min_days = st.number_input("Min days between rounds", value=int(selected["min_days_between_rounds"]) if selected else 0)

    if st.button("Save assignment"):
        data = {
            "name": name,
            "area": area,
            "hourly_rate": hourly_rate,
            "hours_per_round": hours_per_round,
            "min_days_between_rounds": min_days
        }

        if selected:
            supabase.table("assignments").update(data).eq("id", selected["id"]).execute()
            st.success("Updated!")
        else:
            supabase.table("assignments").insert(data).execute()
            st.success("Created!")

        refresh()

    st.subheader("All assignments")
    st.dataframe(assignments)

# ============================================================
# TAB 1 — ROUNDS
# ============================================================
with tab1:
    st.header("Plan Your Rounds")

    assignments = get_assignments()
    if not assignments:
        st.warning("Create an assignment first.")
    else:
        assignment = st.selectbox(
            "Assignment",
            assignments,
            format_func=lambda a: f"{a['name']} ({a['area']})"
        )

        work_date = st.date_input("Work date", value=date.today())
        kind = st.text_input("Kind (morning, night, etc.)")

        if st.button("Add round"):
            supabase.table("rounds").insert({
                "assignment_id": assignment["id"],
                "work_date": work_date.isoformat(),
                "kind": kind
            }).execute()
            st.success("Round added!")
            refresh()

        st.subheader("All rounds")
        rounds = get_rounds()

        if rounds:
            df = pd.DataFrame([
                {
                    "id": r["id"],
                    "date": r["work_date"],
                    "assignment": r["assignments"]["name"],
                    "area": r["assignments"]["area"],
                    "kind": r["kind"],
                    "hours": r["assignments"]["hours_per_round"],
                    "rate": r["assignments"]["hourly_rate"],
                    "min_days": r["assignments"]["min_days_between_rounds"]
                }
                for r in rounds
            ])

            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            st.dataframe(df)

            # Warning system
            st.subheader("Warnings")
            warnings = []
            for a in df["assignment"].unique():
                subset = df[df["assignment"] == a].sort_values("date")
                prev = None
                for _, row in subset.iterrows():
                    if prev is not None:
                        diff = (row["date"] - prev).days
                        if diff < row["min_days"]:
                            warnings.append(
                                f"{a}: Only {diff} days between {prev.date()} and {row['date'].date()} (min {row['min_days']})"
                            )
                    prev = row["date"]

            if warnings:
                for w in warnings:
                    st.error(w)
            else:
                st.success("All rounds respect minimum spacing.")

# ============================================================
# TAB 3 — EARNINGS
# ============================================================
with tab3:
    st.header("Monthly Earnings")

    rounds = get_rounds()
    if not rounds:
        st.info("No rounds yet.")
    else:
        df = pd.DataFrame([
            {
                "date": datetime.strptime(r["work_date"], "%Y-%m-%d").date(),
                "assignment": r["assignments"]["name"],
                "hours": r["assignments"]["hours_per_round"],
                "rate": r["assignments"]["hourly_rate"],
                "amount": r["assignments"]["hours_per_round"] * r["assignments"]["hourly_rate"]
            }
            for r in rounds
        ])

        df["month"] = df["date"].apply(lambda d: d.strftime("%Y-%m"))

        month = st.selectbox("Select month", sorted(df["month"].unique()))

        df_month = df[df["month"] == month]

        subtotal = df_month["amount"].sum()
        btw = subtotal * 0.21
        total = subtotal + btw

        st.metric("Subtotal", f"€ {subtotal:,.2f}")
        st.metric("BTW 21%", f"€ {btw:,.2f}")
        st.metric("Total", f"€ {total:,.2f}")

        st.dataframe(df_month)


