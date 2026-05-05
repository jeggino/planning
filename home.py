import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime

# ---------------------------------------------------------
# Supabase client
# ---------------------------------------------------------
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = get_supabase()

# ---------------------------------------------------------
# Cached fetch functions
# ---------------------------------------------------------
@st.cache_data(ttl=3)
def get_assignments():
    return supabase.table("assignments").select("*").order("created_at").execute().data

@st.cache_data(ttl=3)
def get_areas():
    return supabase.table("areas").select("*").order("created_at").execute().data

@st.cache_data(ttl=3)
def get_rounds():
    return supabase.table("rounds").select(
        "*, assignments(name, hours_per_round, min_days_between_rounds, hourly_rate), areas(name)"
    ).order("work_date").execute().data

def refresh():
    st.cache_data.clear()

# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------
st.set_page_config(page_title="Work Planner", layout="wide")
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to:",
    ["Assignments", "Areas", "Rounds", "Monthly Earnings"]
)

st.title("Work Planner")

# ---------------------------------------------------------
# PAGE 1 — ASSIGNMENTS
# ---------------------------------------------------------
if page == "Assignments":
    st.header("Assignment Setup")

    assignments = get_assignments()

    mode = st.radio("Mode", ["Create new", "Edit existing"])

    selected = None
    if mode == "Edit existing" and assignments:
        selected = st.selectbox(
            "Select assignment",
            assignments,
            format_func=lambda a: a["name"]
        )

    name = st.text_input("Assignment name", value=selected["name"] if selected else "")
    hours = st.number_input("Hours per round", value=float(selected["hours_per_round"]) if selected else 0.0)
    min_days = st.number_input("Minimum days between rounds", value=int(selected["min_days_between_rounds"]) if selected else 0)
    rate = st.number_input("Hourly rate (€)", value=float(selected["hourly_rate"]) if selected else 0.0)

    if st.button("Save assignment"):
        data = {
            "name": name,
            "hours_per_round": hours,
            "min_days_between_rounds": min_days,
            "hourly_rate": rate
        }

        if selected:
            supabase.table("assignments").update(data).eq("id", selected["id"]).execute()
            st.success("Assignment updated.")
        else:
            supabase.table("assignments").insert(data).execute()
            st.success("Assignment created.")

        refresh()

    st.subheader("All assignments")
    st.dataframe(assignments)

    if assignments:
        del_sel = st.selectbox("Delete assignment", ["None"] + [a["name"] for a in assignments])
        if del_sel != "None":
            if st.button("Confirm delete"):
                a_id = next(a["id"] for a in assignments if a["name"] == del_sel)
                supabase.table("assignments").delete().eq("id", a_id).execute()
                st.warning("Assignment deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE 2 — AREAS
# ---------------------------------------------------------
elif page == "Areas":
    st.header("Area Setup")

    areas = get_areas()

    mode = st.radio("Mode", ["Create new", "Edit existing"])

    selected = None
    if mode == "Edit existing" and areas:
        selected = st.selectbox(
            "Select area",
            areas,
            format_func=lambda a: a["name"]
        )

    name = st.text_input("Area name", value=selected["name"] if selected else "")
    desc = st.text_area("Description", value=selected["description"] if selected else "")

    if st.button("Save area"):
        data = {"name": name, "description": desc}

        if selected:
            supabase.table("areas").update(data).eq("id", selected["id"]).execute()
            st.success("Area updated.")
        else:
            supabase.table("areas").insert(data).execute()
            st.success("Area created.")

        refresh()

    st.subheader("All areas")
    st.dataframe(areas)

    if areas:
        del_sel = st.selectbox("Delete area", ["None"] + [a["name"] for a in areas])
        if del_sel != "None":
            if st.button("Confirm delete"):
                a_id = next(a["id"] for a in areas if a["name"] == del_sel)
                supabase.table("areas").delete().eq("id", a_id).execute()
                st.warning("Area deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE 3 — ROUNDS
# ---------------------------------------------------------
elif page == "Rounds":
    st.header("Add a Round")

    assignments = get_assignments()
    areas = get_areas()

    if not assignments or not areas:
        st.warning("You must create assignments and areas first.")
    else:
        assignment = st.selectbox(
            "Assignment",
            assignments,
            format_func=lambda a: a["name"]
        )

        area = st.selectbox(
            "Area",
            areas,
            format_func=lambda a: a["name"]
        )

        work_date = st.date_input("Work date", value=date.today())

        # VALIDATION: check last round
        rounds = get_rounds()
        relevant = [
            r for r in rounds
            if r["assignment_id"] == assignment["id"] and r["area_id"] == area["id"]
        ]

        if st.button("Save round"):
            if relevant:
                last_date = max(datetime.strptime(r["work_date"], "%Y-%m-%d").date() for r in relevant)
                diff = (work_date - last_date).days

                if diff < assignment["min_days_between_rounds"]:
                    st.error(
                        f"Cannot save. Only {diff} days since last round. "
                        f"Minimum required: {assignment['min_days_between_rounds']}."
                    )
                    st.stop()

            supabase.table("rounds").insert({
                "assignment_id": assignment["id"],
                "area_id": area["id"],
                "work_date": work_date.isoformat()
            }).execute()

            st.success("Round saved.")
            refresh()

    st.subheader("All rounds")
    rounds = get_rounds()

    if rounds:
        df = pd.DataFrame([
            {
                "id": r["id"],
                "date": r["work_date"],
                "assignment": r["assignments"]["name"],
                "area": r["areas"]["name"],
                "hours": r["assignments"]["hours_per_round"],
                "rate": r["assignments"]["hourly_rate"]
            }
            for r in rounds
        ])
        st.dataframe(df)

        # Delete
        del_sel = st.selectbox("Delete round", ["None"] + [f"{row['date']} - {row['assignment']} ({row['area']})" for _, row in df.iterrows()])
        if del_sel != "None":
            idx = [f"{row['date']} - {row['assignment']} ({row['area']})" for _, row in df.iterrows()].index(del_sel)
            r_id = df.iloc[idx]["id"]
            if st.button("Confirm delete"):
                supabase.table("rounds").delete().eq("id", r_id).execute()
                st.warning("Round deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE 4 — MONTHLY EARNINGS
# ---------------------------------------------------------
elif page == "Monthly Earnings":
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
        vat = subtotal * 0.21
        total = subtotal + vat

        st.metric("Subtotal", f"€ {subtotal:,.2f}")
        st.metric("VAT 21%", f"€ {vat:,.2f}")
        st.metric("Total", f"€ {total:,.2f}")

        st.subheader("Details")
        st.dataframe(df_month)



