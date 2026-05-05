import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime
import altair as alt

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
        "*, assignments(name, type, hours_per_round, min_days_between_rounds, hourly_rate), areas(name, description)"
    ).order("work_date").execute().data

def refresh():
    st.cache_data.clear()

# ---------------------------------------------------------
# Layout & navigation
# ---------------------------------------------------------
st.set_page_config(page_title="Work Planner", layout="wide")
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to:",
    ["Assignments", "Areas", "Log Work Day", "Rounds Overview & Plot", "Monthly Earnings"]
)

st.title("Work Planner")

# ---------------------------------------------------------
# PAGE — ASSIGNMENTS
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
            format_func=lambda a: f"{a['name']} ({a['type']})"
        )

    assignment_type = st.radio(
        "Type of assignment",
        ["Deskwork", "Fieldwork"],
        index=0 if not selected else (0 if selected["type"] == "Deskwork" else 1)
    )

    name = st.text_input("Assignment name", value=selected["name"] if selected else "")

    if assignment_type == "Deskwork":
        hourly_rate = st.number_input(
            "Hourly rate (€)",
            value=float(selected["hourly_rate"]) if selected and selected["type"] == "Deskwork" else 0.0
        )
        hours_per_round = None
        min_days = None
    else:
        hours_per_round = st.number_input(
            "Hours per round",
            value=float(selected["hours_per_round"]) if selected and selected["type"] == "Fieldwork" and selected["hours_per_round"] is not None else 0.0
        )
        min_days = st.number_input(
            "Minimum days between rounds",
            value=int(selected["min_days_between_rounds"]) if selected and selected["type"] == "Fieldwork" and selected["min_days_between_rounds"] is not None else 0
        )
        hourly_rate = st.number_input(
            "Hourly rate (€)",
            value=float(selected["hourly_rate"]) if selected and selected["type"] == "Fieldwork" else 0.0
        )

    if st.button("Save assignment"):
        data = {
            "name": name,
            "type": assignment_type,
            "hourly_rate": hourly_rate,
            "hours_per_round": hours_per_round if assignment_type == "Fieldwork" else None,
            "min_days_between_rounds": min_days if assignment_type == "Fieldwork" else None,
        }

        if selected:
            supabase.table("assignments").update(data).eq("id", selected["id"]).execute()
            st.success("Assignment updated.")
        else:
            supabase.table("assignments").insert(data).execute()
            st.success("Assignment created.")

        refresh()

    st.subheader("All assignments")
    if assignments:
        df_a = pd.DataFrame(assignments)
        df_a = df_a.drop(columns=["id", "created_at"], errors="ignore")
        st.dataframe(df_a, use_container_width=True)
    else:
        st.info("No assignments yet.")

    if assignments:
        del_sel = st.selectbox("Delete assignment", ["None"] + [f"{a['name']} ({a['type']})" for a in assignments])
        if del_sel != "None":
            if st.button("Confirm delete assignment"):
                a_id = next(a["id"] for a in assignments if f"{a['name']} ({a['type']})" == del_sel)
                supabase.table("assignments").delete().eq("id", a_id).execute()
                st.warning("Assignment deleted (and related rounds).")
                refresh()

# ---------------------------------------------------------
# PAGE — AREAS
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
    if areas:
        df_ar = pd.DataFrame(areas)
        df_ar = df_ar.drop(columns=["id", "created_at"], errors="ignore")
        st.dataframe(df_ar, use_container_width=True)
    else:
        st.info("No areas yet.")

    if areas:
        del_sel = st.selectbox("Delete area", ["None"] + [a["name"] for a in areas])
        if del_sel != "None":
            if st.button("Confirm delete area"):
                a_id = next(a["id"] for a in areas if a["name"] == del_sel)
                supabase.table("areas").delete().eq("id", a_id).execute()
                st.warning("Area deleted (related rounds will have area set to null).")
                refresh()

# ---------------------------------------------------------
# PAGE — LOG WORK DAY
# ---------------------------------------------------------
elif page == "Log Work Day":
    st.header("Log a Day of Work")

    assignments = get_assignments()
    areas = get_areas()

    if not assignments:
        st.warning("You must create assignments first.")
    else:
        work_date = st.date_input("Date", value=date.today())
        work_type = st.radio("Type of assignment", ["Deskwork", "Fieldwork"])

        filtered_assignments = [a for a in assignments if a["type"] == work_type]

        if not filtered_assignments:
            st.warning(f"No {work_type} assignments defined yet.")
        else:
            assignment = st.selectbox(
                "Assignment",
                filtered_assignments,
                format_func=lambda a: a["name"]
            )

            if work_type == "Deskwork":
                hours_worked = st.number_input("Hours worked", min_value=0.0, step=0.5)
                if st.button("Save work day"):
                    supabase.table("rounds").insert({
                        "assignment_id": assignment["id"],
                        "area_id": None,
                        "work_date": work_date.isoformat(),
                        "hours_worked": hours_worked
                    }).execute()
                    st.success("Deskwork day saved.")
                    refresh()

            else:  # Fieldwork
                if not areas:
                    st.warning("You must create areas first for Fieldwork.")
                else:
                    area = st.selectbox(
                        "Area",
                        areas,
                        format_func=lambda a: a["name"]
                    )

                    rounds = get_rounds()
                    relevant = [
                        r for r in rounds
                        if r["assignment_id"] == assignment["id"] and r["area_id"] == area["id"]
                    ]

                    if st.button("Save work day"):
                        if assignment["min_days_between_rounds"] is not None and relevant:
                            last_date = max(datetime.strptime(r["work_date"], "%Y-%m-%d").date() for r in relevant)
                            diff = (work_date - last_date).days

                            if diff < assignment["min_days_between_rounds"]:
                                st.error(
                                    f"Cannot save. Only {diff} days since last round in this area. "
                                    f"Minimum required: {assignment['min_days_between_rounds']}."
                                )
                                st.stop()

                        supabase.table("rounds").insert({
                            "assignment_id": assignment["id"],
                            "area_id": area["id"],
                            "work_date": work_date.isoformat(),
                            "hours_worked": None  # fixed by assignment.hours_per_round
                        }).execute()
                        st.success("Fieldwork day saved.")
                        refresh()

# ---------------------------------------------------------
# PAGE — ROUNDS OVERVIEW & PLOT
# ---------------------------------------------------------
elif page == "Rounds Overview & Plot":
    st.header("Work Activity Overview")

    rounds = get_rounds()
    if not rounds:
        st.info("No rounds logged yet.")
    else:
        df = pd.DataFrame([
            {
                "id": r["id"],
                "date": datetime.strptime(r["work_date"], "%Y-%m-%d").date(),
                "assignment": r["assignments"]["name"],
                "type": r["assignments"]["type"],
                "area": r["areas"]["name"] if r["areas"] else None,
                "hours_worked": r["hours_worked"],
                "hours_per_round": r["assignments"]["hours_per_round"],
                "rate": r["assignments"]["hourly_rate"]
            }
            for r in rounds
        ])

        df["date"] = pd.to_datetime(df["date"])

        # -------------------------------
        # DESKWORK PLOT
        # -------------------------------
        st.subheader("Deskwork Activity")

        df_desk = df[df["type"] == "Deskwork"]

        if df_desk.empty:
            st.info("No deskwork logged yet.")
        else:
            chart_desk = (
                alt.Chart(df_desk)
                .mark_circle(size=120)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("assignment:N", title="Assignment"),
                    color=alt.Color("assignment:N", title="Assignment"),
                    tooltip=["date:T", "assignment:N", "hours_worked:Q"]
                )
                .properties(height=350)
            )
            st.altair_chart(chart_desk, use_container_width=True)

        st.markdown("---")

        # -------------------------------
        # FIELDWORK PLOT
        # -------------------------------
        st.subheader("Fieldwork Activity")

        df_field = df[df["type"] == "Fieldwork"]

        if df_field.empty:
            st.info("No fieldwork logged yet.")
        else:
            chart_field = (
                alt.Chart(df_field)
                .mark_circle(size=120)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("area:N", title="Area"),
                    color=alt.Color("assignment:N", title="Assignment"),
                    tooltip=["date:T", "assignment:N", "area:N"]
                )
                .properties(height=350)
            )
            st.altair_chart(chart_field, use_container_width=True)

        st.markdown("---")

        # -------------------------------
        # EDIT / DELETE SECTION
        # -------------------------------
        st.subheader("Edit or Delete a Round")

        labels = [
            f"{row['date'].date()} — {row['assignment']} ({row['type']})"
            for _, row in df.iterrows()
        ]
        selected_label = st.selectbox("Select round", labels)
        idx = labels.index(selected_label)
        row = df.iloc[idx]

        new_date = st.date_input("New date", value=row["date"], key="edit_date")

        if row["type"] == "Deskwork":
            new_hours = st.number_input(
                "New hours worked",
                value=float(row["hours_worked"] or 0.0),
                key="edit_hours"
            )
        else:
            new_hours = None

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save changes"):
                update_data = {"work_date": new_date.isoformat()}
                if row["type"] == "Deskwork":
                    update_data["hours_worked"] = new_hours

                supabase.table("rounds").update(update_data).eq("id", row["id"]).execute()
                st.success("Round updated.")
                refresh()

        with col2:
            if st.button("Delete round"):
                supabase.table("rounds").delete().eq("id", row["id"]).execute()
                st.warning("Round deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE — MONTHLY EARNINGS
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
                "type": r["assignments"]["type"],
                "hours_worked": r["hours_worked"],
                "hours_per_round": r["assignments"]["hours_per_round"],
                "rate": r["assignments"]["hourly_rate"],
            }
            for r in rounds
        ])

        def compute_amount(row):
            if row["type"] == "Deskwork":
                return (row["hours_worked"] or 0) * row["rate"]
            else:
                return (row["hours_per_round"] or 0) * row["rate"]

        df["amount"] = df.apply(compute_amount, axis=1)
        df["month"] = df["date"].apply(lambda d: d.strftime("%Y-%m"))

        month = st.selectbox("Select month", sorted(df["month"].unique()))

        df_month = df[df["month"] == month]

        subtotal = df_month["amount"].sum()
        vat = subtotal * 0.21
        total = subtotal + vat

        st.metric("Subtotal", f"€ {subtotal:,.2f}")
        st.metric("VAT 21%", f"€ {vat:,.2f}")
        st.metric("Total", f"€ {total:,.2f}")

        st.markdown("---")

        # -------------------------------
        # TOTAL PER ASSIGNMENT
        # -------------------------------
        st.subheader("Total per Assignment")

        totals = (
            df_month.groupby("assignment")["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )

        st.bar_chart(
            data=totals,
            x="assignment",
            y="amount",
            use_container_width=True
        )

        st.markdown("---")

        # -------------------------------
        # STACKED BAR CHART BY TYPE
        # -------------------------------
        st.subheader("Monthly Earnings by Type (Stacked)")

        chart = (
            alt.Chart(df_month)
            .mark_bar()
            .encode(
                x=alt.X("assignment:N", title="Assignment"),
                y=alt.Y("amount:Q", title="Earnings (€)"),
                color=alt.Color("type:N", title="Type"),
                tooltip=["assignment:N", "type:N", "amount:Q"]
            )
            .properties(height=450)
        )

        st.altair_chart(chart, use_container_width=True)








