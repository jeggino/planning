#--------------------------------------------------------------------------------------------------------------------------
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime
import altair as alt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

from streamlit_calendar import calendar

# ---------------------------------------------------------
# BASIC CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Work Planner", layout="wide")

# ---------------------------------------------------------
# PASSWORD PROTECTION
# ---------------------------------------------------------
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "password_input" not in st.session_state:
        st.session_state["password_input"] = ""

    if not st.session_state["authenticated"]:
        st.subheader("Login")

        st.session_state["password_input"] = st.text_input(
            "Enter password",
            type="password"
        )

        if st.button("Login"):
            if st.session_state["password_input"] == st.secrets["PASSWORD"]:
                st.session_state["authenticated"] = True
                st.success("Access granted")
            else:
                st.error("Incorrect password")
                st.session_state["authenticated"] = False

        if not st.session_state["authenticated"]:
            st.stop()

check_password()

# ---------------------------------------------------------
# DARK MODE CSS
# ---------------------------------------------------------
dark_css = """
<style>
body {
    background-color: #0e1117;
    color: #fafafa;
}
</style>
"""
st.markdown(dark_css, unsafe_allow_html=True)

# ---------------------------------------------------------
# SUPABASE CLIENT
# ---------------------------------------------------------
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

supabase = get_supabase()

# ---------------------------------------------------------
# CACHED FETCH FUNCTIONS
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

@st.cache_data(ttl=3)
def get_planned_rounds():
    return supabase.table("planned_rounds").select(
        "*, assignments(name, type, hours_per_round, hourly_rate), areas(name, description)"
    ).order("planned_date").execute().data

def refresh():
    st.cache_data.clear()

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title("Navigation")

menu = st.sidebar.selectbox(
    "Choose section",
    [
        "Work Setup",
        "Work Activity",
        "Monthly Earnings"
    ]
)

subpage = None

if menu == "Work Setup":
    subpage = st.sidebar.radio("Setup", ["Assignments", "Areas"])

elif menu == "Work Activity":
    subpage = st.sidebar.radio("Activity", ["Log Work Day", "Planning", "Rounds Overview & Plot"])

else:
    subpage = "Monthly Earnings"

# =========================================================
# PAGE — ASSIGNMENTS
# =========================================================
if subpage == "Assignments":
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
        ["Deskwork", "Fieldwork", "Extra"],
        index=(
            0 if not selected else
            (0 if selected["type"] == "Deskwork"
             else 1 if selected["type"] == "Fieldwork"
             else 2)
        )
    )


    name = st.text_input("Assignment name", value=selected["name"] if selected else "")

    # NEW: Travel does NOT ask for hourly rate
    if assignment_type in ["Deskwork", "Fieldwork", "Extra"]:
        hourly_rate = st.number_input(
            "Hourly rate (€)",
            value=float(selected["hourly_rate"]) if selected and selected["hourly_rate"] is not None else 0.0
        )
    else:
        hourly_rate = None

    # Fieldwork-specific fields
    if assignment_type == "Fieldwork":
        hours_per_round = st.number_input(
            "Hours per round",
            value=float(selected["hours_per_round"]) if selected and selected["hours_per_round"] is not None else 0.0
        )
        min_days = st.number_input(
            "Minimum days between rounds",
            value=int(selected["min_days_between_rounds"]) if selected and selected["min_days_between_rounds"] is not None else 0
        )
    else:
        hours_per_round = None
        min_days = None

    if st.button("Save assignment"):
        data = {
            "name": name,
            "type": assignment_type,
            "hourly_rate": hourly_rate,
            "hours_per_round": hours_per_round,
            "min_days_between_rounds": min_days,
        }
    
        try:
            if selected:
                supabase.table("assignments").update(data).eq("id", selected["id"]).execute()
                st.success("Assignment updated.")
            else:
                supabase.table("assignments").insert(data).execute()
                st.success("Assignment created.")
        except Exception as e:
            st.error(str(e))
            # or st.write(e)
        refresh()


    st.subheader("All assignments")
    if assignments:
        df_a = pd.DataFrame(assignments).drop(columns=["created_at"], errors="ignore")
        st.dataframe(df_a, use_container_width=True)

    if assignments:
        del_sel = st.selectbox("Delete assignment", ["None"] + [f"{a['name']} ({a['type']})" for a in assignments])
        if del_sel != "None":
            if st.button("Confirm delete assignment"):
                a_id = next(a["id"] for a in assignments if f"{a['name']} ({a['type']})" == del_sel)
                supabase.table("assignments").delete().eq("id", a_id).execute()
                st.warning("Assignment deleted.")
                refresh()


# =========================================================
# PAGE — AREAS
# =========================================================
elif subpage == "Areas":
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
        df_ar = pd.DataFrame(areas).drop(columns=["created_at"], errors="ignore")
        st.dataframe(df_ar, use_container_width=True)

    if areas:
        del_sel = st.selectbox("Delete area", ["None"] + [a["name"] for a in areas])
        if del_sel != "None":
            if st.button("Confirm delete area"):
                a_id = next(a["id"] for a in areas if a["name"] == del_sel)
                supabase.table("areas").delete().eq("id", a_id).execute()
                st.warning("Area deleted.")
                refresh()

# =========================================================
# PAGE — LOG WORK DAY
# =========================================================
elif subpage == "Log Work Day":
    st.sidebar.image("https://copilot.microsoft.com/th/id/BCO.916d1e50-5bc3-44e6-8cb6-adcd2419be6d.png")

    assignments = get_assignments()
    areas = get_areas()

    if not assignments:
        st.info("You need assignments first.")
        st.stop()

    # NEW: Ask what kind of log this is
    log_type = st.radio("What do you want to log?", ["Work", "Travel cost"])

    work_date = st.date_input("Date", value=date.today())

    area_id = None
    hours = None
    travel_cost = None
    assignment_id = None

    if log_type == "Work":
        assignment = st.selectbox(
            "Assignment",
            assignments,
            format_func=lambda a: f"{a['name']} ({a['type']})"
        )
        assignment_id = assignment["id"]

        if assignment["type"] in ["Deskwork", "Extra"]:
            hours = st.number_input("Hours worked", min_value=0.0, step=0.25)

        elif assignment["type"] in ["Fieldwork", "Travel"]:
            area = st.selectbox("Area", areas, format_func=lambda a: a["name"])
            area_id = area["id"]

            if assignment["type"] == "Travel":
                travel_cost = st.number_input("Travel cost (€)", min_value=0.0, step=1.0)

    else:  # log_type == "Travel cost"
        area = st.selectbox("Area", areas, format_func=lambda a: a["name"])
        area_id = area["id"]
        travel_cost = st.number_input("Travel cost (€)", min_value=0.0, step=1.0)

    if st.button("Save"):
        supabase.table("rounds").insert({
            "assignment_id": assignment_id,
            "area_id": area_id,
            "work_date": work_date.isoformat(),
            "hours_worked": hours,
            "travel_cost": travel_cost
        }).execute()

        st.success("Saved.")
        refresh()



# ---------------------------------------------------------
# PAGE — ROUNDS OVERVIEW & PLOT (UPDATED WITH TRAVEL COSTS)
# ---------------------------------------------------------
elif subpage == "Rounds Overview & Plot":
    st.sidebar.image("https://copilot.microsoft.com/th/id/BCO.8913ea1b-eab7-4cbc-bb1b-75398b12618d.png")

    rounds = get_rounds()
    if not rounds:
        st.info("No rounds logged yet.")
    else:
        df = pd.DataFrame([
            {
                "id": r["id"],
                "date": datetime.strptime(r["work_date"], "%Y-%m-%d").date(),
                "assignment": r["assignments"]["name"] if r["assignments"] else None,
                "type": r["assignments"]["type"] if r["assignments"] else ("Travel" if r["travel_cost"] else None),
                "area": r["areas"]["name"] if r["areas"] else None,
                "hours_worked": r["hours_worked"],
                "hours_per_round": r["assignments"]["hours_per_round"] if r["assignments"] else None,
                "rate": r["assignments"]["hourly_rate"] if r["assignments"] else None,
                "travel_cost": r["travel_cost"]
            }
            for r in rounds
        ])

        df["date"] = pd.to_datetime(df["date"])

        # -------------------------------
        # FILTERS
        # -------------------------------
        st.subheader("Filters")

        col1, col2 = st.columns(2)

        with col1:
            assignment_filter = st.multiselect(
                "Filter by assignment",
                df["assignment"].dropna().unique()
            )

        with col2:
            area_filter = st.multiselect(
                "Filter by area",
                df["area"].dropna().unique()
            )

        df_filtered = df.copy()

        if assignment_filter:
            df_filtered = df_filtered[df_filtered["assignment"].isin(assignment_filter)]

        if area_filter:
            df_filtered = df_filtered[df_filtered["area"].isin(area_filter)]

        # -------------------------------
        # DESKWORK PLOT
        # -------------------------------
        st.subheader("Deskwork Activity")

        df_desk = df_filtered[df_filtered["type"] == "Deskwork"]

        if df_desk.empty:
            st.info("No deskwork logged.")
        else:
            chart_desk = (
                alt.Chart(df_desk)
                .mark_circle(size=150)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("assignment:N", title="Assignment"),
                    color=alt.Color("assignment:N", scale=alt.Scale(scheme="category10")),
                    tooltip=["date:T", "assignment:N", "hours_worked:Q"]
                )
                .interactive()
                .properties(height=350)
            )
            st.altair_chart(chart_desk, use_container_width=True)

        st.markdown("---")

        # -------------------------------
        # FIELDWORK PLOT
        # -------------------------------
        st.subheader("Fieldwork Activity")

        df_field = df_filtered[df_filtered["type"] == "Fieldwork"]

        if df_field.empty:
            st.info("No fieldwork logged.")
        else:
            chart_field = (
                alt.Chart(df_field)
                .mark_circle(size=150)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("area:N", title="Area"),
                    color=alt.Color("assignment:N", scale=alt.Scale(scheme="paired")),
                    tooltip=["date:T", "assignment:N", "area:N"]
                )
                .interactive()
                .properties(height=350)
            )
            st.altair_chart(chart_field, use_container_width=True)

        st.markdown("---")

        # -------------------------------
        # TRAVEL COSTS PLOT (NEW)
        # -------------------------------
        st.subheader("Travel Costs Activity")

        df_travel = df_filtered[df_filtered["travel_cost"].notna()]

        if df_travel.empty:
            st.info("No travel costs logged.")
        else:
            chart_travel = (
                alt.Chart(df_travel)
                .mark_square(size=200, color="orange")
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("area:N", title="Area"),
                    tooltip=["date:T", "area:N", "travel_cost:Q"]
                )
                .interactive()
                .properties(height=350)
            )
            st.altair_chart(chart_travel, use_container_width=True)

        st.markdown("---")

        # -------------------------------
        # EDIT / DELETE SECTION
        # -------------------------------
        st.subheader("Edit or Delete a Round")

        labels = [
            f"{row['date'].date()} — "
            f"{row['assignment'] if row['assignment'] else 'Travel'} "
            f"({row['type'] if row['type'] else 'Travel'})"
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
            new_travel = None

        elif row["type"] == "Fieldwork":
            new_hours = None
            new_travel = None

        else:  # Travel
            new_hours = None
            new_travel = st.number_input(
                "New travel cost (€)",
                value=float(row["travel_cost"] or 0.0),
                key="edit_travel"
            )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save changes"):
                update_data = {"work_date": new_date.isoformat()}

                if row["type"] == "Deskwork":
                    update_data["hours_worked"] = new_hours

                if row["type"] == "Travel":
                    update_data["travel_cost"] = new_travel

                supabase.table("rounds").update(update_data).eq("id", row["id"]).execute()
                st.success("Round updated.")
                refresh()

        with col2:
            if st.button("Delete round"):
                supabase.table("rounds").delete().eq("id", row["id"]).execute()
                st.warning("Round deleted.")
                refresh()
# # =========================================================
# # PAGE — PLANNING (FIELDWORK ONLY)
# # =========================================================
# elif subpage == "Planning":
#     st.sidebar.image("https://copilot.microsoft.com/th/id/BCO.2d3fe0e2-f66f-41f7-bc5f-c4b3f53ee37e.png")

#     assignments = get_assignments()
#     areas = get_areas()

#     if not assignments or not areas:
#         st.info("You need at least one assignment and one area to plan rounds.")
#         st.stop()

#     fieldwork_assignments = [a for a in assignments if a["type"] == "Fieldwork"]

#     if not fieldwork_assignments:
#         st.info("You have no Fieldwork assignments yet. Create one first in Work Setup → Assignments.")
#         st.stop()

#     st.subheader("Plan a new fieldwork round")

#     col1, col2, col3 = st.columns(3)

#     with col1:
#         planned_date = st.date_input("Planned date", value=date.today())

#     with col2:
#         selected_assignment = st.selectbox(
#             "Assignment (Fieldwork only)",
#             fieldwork_assignments,
#             format_func=lambda a: a["name"]
#         )

#     with col3:
#         selected_area = st.selectbox(
#             "Area",
#             areas,
#             format_func=lambda a: a["name"]
#         )

#     if st.button("Save planning"):
#         supabase.table("planned_rounds").insert({
#             "assignment_id": selected_assignment["id"],
#             "area_id": selected_area["id"],
#             "planned_date": planned_date.isoformat()
#         }).execute()
#         st.success("Planned round saved.")
#         refresh()

#     st.markdown("---")

#     st.subheader("Upcoming planned rounds")

#     planned = get_planned_rounds()

#     if not planned:
#         st.info("No planned rounds yet.")
#     else:
#         rows = []
#         today = date.today()

#         for r in planned:
#             pd_date = datetime.strptime(r["planned_date"], "%Y-%m-%d").date()
#             diff = (pd_date - today).days

#             if diff > 0:
#                 rel = f"in {diff} days"
#             elif diff == 0:
#                 rel = "today"
#             else:
#                 rel = f"{abs(diff)} days ago"

#             rows.append({
#                 "id": r["id"],
#                 "planned_date": pd_date,
#                 "assignment_id": r["assignment_id"],
#                 "area_id": r["area_id"],
#                 "assignment": r["assignments"]["name"] if r["assignments"] else None,
#                 "area": r["areas"]["name"] if r["areas"] else None,
#                 "days_diff": diff,
#                 "relative": rel
#             })

#         df_planned = pd.DataFrame(rows).sort_values("planned_date")

#         # List view
#         for _, row in df_planned.iterrows():
#             st.markdown(
#                 f"**📅 {row['planned_date'].isoformat()} ({row['relative']})**  \n"
#                 f"• {row['area']} — {row['assignment']}"
#             )


#         from streamlit_calendar import calendar
        
#         st.markdown("### Calendar view of planned rounds")
        
#         calendar_events = []
#         for r in rows:
#             calendar_events.append({
#                 "title": f"{r['area']} – {r['assignment']}",
#                 "start": r["planned_date"].isoformat(),
#                 "allDay": True,
#                 "id": r["id"],
#             })
        
#         calendar_options = {
#             "initialView": "dayGridMonth",
#             "headerToolbar": {
#                 "left": "prev,next today",
#                 "center": "title",
#                 "right": "dayGridMonth,timeGridWeek,listWeek",
#             },
#             "events": calendar_events,
#             "height": 650,
#         }
        
#         custom_css = """
#         /* Allow long titles to wrap instead of being cut off */
#         .fc-daygrid-event .fc-event-title {
#             white-space: normal;
#         }
        
#         /* Optional: make events taller so full text fits more often */
#         .fc-daygrid-event {
#             min-height: 2.2em;
#         }
#         """
        
#         calendar(
#             events=calendar_events,
#             options=calendar_options,
#             custom_css=custom_css,
#             key="planning_calendar",
#         )



        
#         st.markdown("---")

#         st.subheader("Edit, delete or confirm a planned round")

#         labels = [
#             f"{row['planned_date'].isoformat()} — {row['area']} — {row['assignment']} ({row['relative']})"
#             for _, row in df_planned.iterrows()
#         ]

#         selected_label = st.selectbox("Select planned round", labels)
#         idx = labels.index(selected_label)
#         row = df_planned.iloc[idx]

#         current_assignment = next(a for a in fieldwork_assignments if a["id"] == row["assignment_id"])
#         current_area = next(a for a in areas if a["id"] == row["area_id"])

#         col1, col2, col3 = st.columns(3)

#         with col1:
#             new_date = st.date_input(
#                 "New planned date",
#                 value=row["planned_date"],
#                 key=f"edit_planned_date_{row['id']}"
#             )

#         with col2:
#             new_assignment = st.selectbox(
#                 "New assignment (Fieldwork only)",
#                 fieldwork_assignments,
#                 index=fieldwork_assignments.index(current_assignment),
#                 format_func=lambda a: a["name"],
#                 key=f"edit_planned_assignment_{row['id']}"
#             )

#         with col3:
#             new_area = st.selectbox(
#                 "New area",
#                 areas,
#                 index=areas.index(current_area),
#                 format_func=lambda a: a["name"],
#                 key=f"edit_planned_area_{row['id']}"
#             )

#         col_a, col_b, col_c = st.columns(3)

#         with col_a:
#             if st.button("Save changes", key=f"btn_save_planning_{row['id']}"):
#                 supabase.table("planned_rounds").update({
#                     "planned_date": new_date.isoformat(),
#                     "assignment_id": new_assignment["id"],
#                     "area_id": new_area["id"]
#                 }).eq("id", row["id"]).execute()
#                 st.success("Planned round updated.")
#                 refresh()

#         with col_b:
#             if st.button("Delete planning", key=f"btn_delete_planning_{row['id']}"):
#                 supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()
#                 st.warning("Planned round deleted.")
#                 refresh()

#         with col_c:
#             if st.button("Confirm done", key=f"btn_confirm_planning_{row['id']}"):
#                 supabase.table("rounds").insert({
#                     "assignment_id": row["assignment_id"],
#                     "area_id": row["area_id"],
#                     "work_date": row["planned_date"].isoformat(),
#                     "hours_worked": None,
#                     "travel_cost": None
#                 }).execute()

#                 supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()

#                 st.success("Planned round confirmed and moved to rounds.")
#                 refresh()



from datetime import date, datetime
import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

# =========================================================
# PAGE — PLANNING (FIELDWORK ONLY) — FINAL VERSION
# =========================================================

elif subpage == "Planning":
    st.sidebar.image("https://copilot.microsoft.com/th/id/BCO.2d3fe0e2-f66f-41f7-bc5f-c4b3f53ee37e.png")

    assignments = get_assignments()
    areas = get_areas()

    if not assignments or not areas:
        st.info("You need at least one assignment and one area to plan rounds.")
        st.stop()

    fieldwork_assignments = [a for a in assignments if a["type"] == "Fieldwork"]

    if not fieldwork_assignments:
        st.info("You have no Fieldwork assignments yet. Create one first in Work Setup → Assignments.")
        st.stop()

    # -----------------------------------------------------
    # PLAN A NEW ROUND
    # -----------------------------------------------------
    st.subheader("Plan a new fieldwork round")

    col1, col2, col3 = st.columns(3)

    with col1:
        planned_date = st.date_input("Planned date", value=date.today())

    with col2:
        selected_assignment = st.selectbox(
            "Assignment (Fieldwork only)",
            fieldwork_assignments,
            format_func=lambda a: a["name"]
        )

    with col3:
        selected_area = st.selectbox(
            "Area",
            areas,
            format_func=lambda a: a["name"]
        )

    if st.button("Save planning"):
        supabase.table("planned_rounds").insert({
            "assignment_id": selected_assignment["id"],
            "area_id": selected_area["id"],
            "planned_date": planned_date.isoformat()
        }).execute()
        st.success("Planned round saved.")
        st.rerun()

    st.markdown("---")

    # -----------------------------------------------------
    # UPCOMING PLANNED ROUNDS
    # -----------------------------------------------------
    st.subheader("Upcoming planned rounds")

    planned = get_planned_rounds()

    if not planned:
        st.info("No planned rounds yet.")
        st.stop()

    rows = []
    today = date.today()

    for r in planned:
        pd_date = datetime.strptime(r["planned_date"], "%Y-%m-%d").date()
        diff = (pd_date - today).days

        if diff > 0:
            rel = f"in {diff} days"
        elif diff == 0:
            rel = "today"
        else:
            rel = f"{abs(diff)} days ago"

        rows.append({
            "id": r["id"],
            "planned_date": pd_date,
            "assignment_id": r["assignment_id"],
            "area_id": r["area_id"],
            "assignment": r["assignments"]["name"] if r["assignments"] else None,
            "area": r["areas"]["name"] if r["areas"] else None,
            "days_diff": diff,
            "relative": rel
        })

    df_planned = pd.DataFrame(rows).sort_values("planned_date")

    for _, row in df_planned.iterrows():
        st.markdown(
            f"**📅 {row['planned_date'].isoformat()} ({row['relative']})**  \n"
            f"• {row['area']} — {row['assignment']}"
        )

    # -----------------------------------------------------
    # CALENDAR VIEW
    # -----------------------------------------------------
    st.markdown("### Calendar view of planned rounds")

    calendar_events = [
        {
            "title": f"{r['area']} – {r['assignment']}",
            "start": r["planned_date"].isoformat(),
            "allDay": True,
            "id": r["id"],
        }
        for r in rows
    ]

    calendar_options = {
        "initialView": "dayGridMonth",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,listWeek",
        },
        "events": calendar_events,
        "height": 650,
    }

    custom_css = """
        .fc-daygrid-event .fc-event-title { white-space: normal; }
        .fc-daygrid-event { min-height: 2.2em; }
    """

    # IMPORTANT: use a unique key to avoid collisions
    calendar(
        events=calendar_events,
        options=calendar_options,
        custom_css=custom_css,
        key="fw_calendar_clicks",
    )

    st.markdown("---")

    # -----------------------------------------------------
    # HANDLE CALENDAR CLICK
    # -----------------------------------------------------
    clicked = st.session_state.get("fw_calendar_clicks")

    # clicked is expected to be something like:
    # {"event": {"id": ..., "title": ..., ...}, "jsEvent": {...}, ...}
    if not clicked or "event" not in clicked or "id" not in clicked["event"]:
        st.info("Click a planned round in the calendar to edit, delete or confirm it.")
        st.stop()

    selected_id = clicked["event"]["id"]
    row = next(r for r in rows if r["id"] == selected_id)

    st.subheader("Selected planned round")
    st.write(
        f"📅 **{row['planned_date']}** — {row['area']} — {row['assignment']} "
        f"({row['relative']})"
    )

    # -----------------------------------------------------
    # DIALOGS
    # -----------------------------------------------------

    @st.dialog("Confirm deletion")
    def delete_dialog():
        st.image(
            "https://copilot.microsoft.com/th/id/OGC.1f3c8f8e-7d8c-4f9e-9e2e-4b3f8b8e1c2f.png",
            width=220,
        )
        st.write(
            f"Are you sure you want to delete the planned round on "
            f"**{row['planned_date']}** for **{row['area']} – {row['assignment']}**?"
        )
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("Yes, delete", type="primary"):
                supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()
                st.success("Planned round deleted.")
                st.rerun()
        with col_d2:
            st.button("Cancel")

    @st.dialog("Edit planned round")
    def edit_dialog():
        # Pre-select current assignment and area
        current_assignment = next(
            a for a in fieldwork_assignments if a["id"] == row["assignment_id"]
        )
        current_area = next(
            a for a in areas if a["id"] == row["area_id"]
        )

        with st.form("edit_form"):
            new_date = st.date_input("New planned date", value=row["planned_date"])
            new_assignment = st.selectbox(
                "New assignment (Fieldwork only)",
                fieldwork_assignments,
                index=fieldwork_assignments.index(current_assignment),
                format_func=lambda a: a["name"],
            )
            new_area = st.selectbox(
                "New area",
                areas,
                index=areas.index(current_area),
                format_func=lambda a: a["name"],
            )

            submitted = st.form_submit_button("Save changes")
            if submitted:
                supabase.table("planned_rounds").update({
                    "planned_date": new_date.isoformat(),
                    "assignment_id": new_assignment["id"],
                    "area_id": new_area["id"],
                }).eq("id", row["id"]).execute()
                st.success("Planned round updated.")
                st.rerun()

    # -----------------------------------------------------
    # ACTION BUTTONS
    # -----------------------------------------------------
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("Edit"):
            edit_dialog()

    with col_b:
        if st.button("Delete"):
            delete_dialog()

    with col_c:
        if st.button("Confirm done"):
            supabase.table("rounds").insert({
                "assignment_id": row["assignment_id"],
                "area_id": row["area_id"],
                "work_date": row["planned_date"].isoformat(),
                "hours_worked": None,
                "travel_cost": None,
            }).execute()

            supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()

            st.success("Planned round confirmed and moved to rounds.")
            st.rerun()



# # ---------------------------------------------------------
# # PAGE — MONTHLY EARNINGS (UPDATED WITH TRAVEL COSTS)
# # ---------------------------------------------------------
# elif subpage == "Monthly Earnings":
#     st.header("Monthly Earnings")

#     rounds = get_rounds()
#     if not rounds:
#         st.info("No rounds yet.")
#     else:
#         df = pd.DataFrame([
#             {
#                 "date": datetime.strptime(r["work_date"], "%Y-%m-%d").date(),
#                 "assignment": r["assignments"]["name"] if r["assignments"] else None,
#                 "type": (
#                     r["assignments"]["type"]
#                     if r["assignments"]
#                     else ("Travel" if r["travel_cost"] else None)
#                 ),
#                 "area": r["areas"]["name"] if r["areas"] else None,
#                 "hours_worked": r["hours_worked"],
#                 "hours_per_round": r["assignments"]["hours_per_round"] if r["assignments"] else None,
#                 "rate": r["assignments"]["hourly_rate"] if r["assignments"] else None,
#                 "travel_cost": r["travel_cost"]
#             }
#             for r in rounds
#         ])

#         # ---------------------------------------------------------
#         # COMPUTE HOURS + AMOUNT
#         # ---------------------------------------------------------
#         def compute_amount(row):
#             if row["type"] == "Deskwork":
#                 return (row["hours_worked"] or 0) * (row["rate"] or 0)
#             elif row["type"] == "Fieldwork":
#                 return (row["hours_per_round"] or 0) * (row["rate"] or 0)
#             elif row["type"] == "Extra":
#                 return (row["hours_worked"] or 0) * (row["rate"] or 0)
#             else:
#                 return row["travel_cost"] or 0

#         df["amount"] = df.apply(compute_amount, axis=1)
#         df["month"] = df["date"].apply(lambda d: d.strftime("%Y-%m"))

#         # ---------------------------------------------------------
#         # MONTH SELECTION
#         # ---------------------------------------------------------
#         st.subheader("Select month(s)")
#         months = sorted(df["month"].unique())
#         selected_months = st.multiselect("Months", months, default=[months[-1]])

#         if not selected_months:
#             st.info("Select at least one month.")
#             st.stop()

#         df_month = df[df["month"].isin(selected_months)]

#         # ---------------------------------------------------------
#         # TOTALS
#         # ---------------------------------------------------------
#         subtotal = df_month["amount"].sum()
#         vat = subtotal * 0.21
#         total = subtotal + vat

#         st.metric("Subtotal", f"€ {subtotal:,.2f}")
#         st.metric("VAT 21%", f"€ {vat:,.2f}")
#         st.metric("Total", f"€ {total:,.2f}")

#         st.markdown("---")

#         # ---------------------------------------------------------
#         # HOURS PER ASSIGNMENT
#         # ---------------------------------------------------------
#         st.subheader("Hours per assignment")

#         df_hours = df_month[df_month["type"] != "Travel"].copy()
#         df_hours["hours"] = df_hours.apply(
#             lambda r: (
#                 r["hours_worked"]
#                 if r["type"] in ["Deskwork", "Extra"]
#                 else r["hours_per_round"]
#             ),
#             axis=1
#         )

#         hours_assignment = (
#             df_hours.groupby("assignment")["hours"]
#             .sum()
#             .reset_index()
#             .sort_values("hours", ascending=False)
#         )

#         st.dataframe(hours_assignment, use_container_width=True)

#         st.markdown("---")

#         # ---------------------------------------------------------
#         # TRAVEL COSTS TABLE
#         # ---------------------------------------------------------
#         st.subheader("Travel Costs")

#         df_travel = df_month[df_month["type"] == "Travel"]

#         if df_travel.empty:
#             st.info("No travel costs this month.")
#         else:
#             travel_table = df_travel[["date", "area", "travel_cost"]].sort_values("date")
#             st.dataframe(travel_table, use_container_width=True)

#         st.markdown("---")

#         # ---------------------------------------------------------
#         # EARNINGS PER ASSIGNMENT
#         # ---------------------------------------------------------
#         st.subheader("Total earnings per assignment")

#         earnings_assignment = (
#             df_month[df_month["type"] != "Travel"]
#             .groupby("assignment")["amount"]
#             .sum()
#             .reset_index()
#             .sort_values("amount", ascending=False)
#         )

#         st.dataframe(earnings_assignment, use_container_width=True)

#         st.markdown("---")

#         # ---------------------------------------------------------
#         # CLIENT INFO
#         # ---------------------------------------------------------
#         st.subheader("Client information (for invoice)")
#         klant_naam = st.text_input("Client name")
#         klant_adres = st.text_input("Client address")
#         klant_postcode = st.text_input("Client postcode")
#         klant_stad = st.text_input("Client city")

#         st.markdown("---")

# =========================================================
# PAGE — PLANNING (FIELDWORK ONLY) — REWRITTEN WITH DIALOGS
# =========================================================
elif subpage == "Planning":
    st.sidebar.image("https://copilot.microsoft.com/th/id/BCO.2d3fe0e2-f66f-41f7-bc5f-c4b3f53ee37e.png")

    assignments = get_assignments()
    areas = get_areas()

    if not assignments or not areas:
        st.info("You need at least one assignment and one area to plan rounds.")
        st.stop()

    fieldwork_assignments = [a for a in assignments if a["type"] == "Fieldwork"]

    if not fieldwork_assignments:
        st.info("You have no Fieldwork assignments yet. Create one first in Work Setup → Assignments.")
        st.stop()

    st.subheader("Plan a new fieldwork round")

    col1, col2, col3 = st.columns(3)

    with col1:
        planned_date = st.date_input("Planned date", value=date.today())

    with col2:
        selected_assignment = st.selectbox(
            "Assignment (Fieldwork only)",
            fieldwork_assignments,
            format_func=lambda a: a["name"]
        )

    with col3:
        selected_area = st.selectbox(
            "Area",
            areas,
            format_func=lambda a: a["name"]
        )

    if st.button("Save planning"):
        supabase.table("planned_rounds").insert({
            "assignment_id": selected_assignment["id"],
            "area_id": selected_area["id"],
            "planned_date": planned_date.isoformat()
        }).execute()
        st.success("Planned round saved.")
        st.rerun()

    st.markdown("---")

    # =========================================================
    # UPCOMING PLANNED ROUNDS
    # =========================================================

    st.subheader("Upcoming planned rounds")

    planned = get_planned_rounds()

    if not planned:
        st.info("No planned rounds yet.")
        st.stop()

    rows = []
    today = date.today()

    for r in planned:
        pd_date = datetime.strptime(r["planned_date"], "%Y-%m-%d").date()
        diff = (pd_date - today).days

        if diff > 0:
            rel = f"in {diff} days"
        elif diff == 0:
            rel = "today"
        else:
            rel = f"{abs(diff)} days ago"

        rows.append({
            "id": r["id"],
            "planned_date": pd_date,
            "assignment_id": r["assignment_id"],
            "area_id": r["area_id"],
            "assignment": r["assignments"]["name"] if r["assignments"] else None,
            "area": r["areas"]["name"] if r["areas"] else None,
            "days_diff": diff,
            "relative": rel
        })

    df_planned = pd.DataFrame(rows).sort_values("planned_date")

    for _, row in df_planned.iterrows():
        st.markdown(
            f"**📅 {row['planned_date'].isoformat()} ({row['relative']})**  \n"
            f"• {row['area']} — {row['assignment']}"
        )

    # =========================================================
    # CALENDAR VIEW
    # =========================================================

    from streamlit_calendar import calendar

    st.markdown("### Calendar view of planned rounds")

    calendar_events = [
        {
            "title": f"{r['area']} – {r['assignment']}",
            "start": r["planned_date"].isoformat(),
            "allDay": True,
            "id": r["id"],
        }
        for r in rows
    ]

    calendar_options = {
        "initialView": "dayGridMonth",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,listWeek",
        },
        "events": calendar_events,
        "height": 650,
    }

    custom_css = """
        .fc-daygrid-event .fc-event-title { white-space: normal; }
        .fc-daygrid-event { min-height: 2.2em; }
    """

    calendar(events=calendar_events, options=calendar_options, custom_css=custom_css, key="planning_calendar")

    st.markdown("---")

    # =========================================================
    # HANDLE CALENDAR CLICK
    # =========================================================

    clicked = st.session_state.get("planning_calendar")

    if not clicked:
        st.info("Click a planned round in the calendar to edit, delete or confirm it.")
        st.stop()

    selected_id = clicked["event"]["id"]
    row = next(r for r in rows if r["id"] == selected_id)

    st.subheader("Selected planned round")
    st.write(f"📅 **{row['planned_date']}** — {row['area']} — {row['assignment']} ({row['relative']})")

    # =========================================================
    # DELETE DIALOG
    # =========================================================

    @st.dialog("Confirm deletion")
    def delete_dialog():
        st.image("https://copilot.microsoft.com/th/id/OGC.1f3c8f8e-7d8c-4f9e-9e2e-4b3f8b8e1c2f.png", width=200)
        st.write(f"Are you sure you want to delete the planned round on **{row['planned_date']}**?")
        if st.button("Yes, delete"):
            supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()
            st.success("Deleted.")
            st.rerun()

    # =========================================================
    # EDIT DIALOG
    # =========================================================

    @st.dialog("Edit planned round")
    def edit_dialog():
        with st.form("edit_form"):
            new_date = st.date_input("New date", value=row["planned_date"])
            new_assignment = st.selectbox("Assignment", fieldwork_assignments, format_func=lambda a: a["name"])
            new_area = st.selectbox("Area", areas, format_func=lambda a: a["name"])

            if st.form_submit_button("Save changes"):
                supabase.table("planned_rounds").update({
                    "planned_date": new_date.isoformat(),
                    "assignment_id": new_assignment["id"],
                    "area_id": new_area["id"]
                }).eq("id", row["id"]).execute()
                st.success("Updated.")
                st.rerun()

    # =========================================================
    # ACTION BUTTONS
    # =========================================================

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Edit"):
            edit_dialog()

    with col2:
        if st.button("Delete"):
            delete_dialog()

    with col3:
        if st.button("Confirm done"):
            supabase.table("rounds").insert({
                "assignment_id": row["assignment_id"],
                "area_id": row["area_id"],
                "work_date": row["planned_date"].isoformat(),
                "hours_worked": None,
                "travel_cost": None
            }).execute()

            supabase.table("planned_rounds").delete().eq("id", row["id"]).execute()

            st.success("Confirmed and moved to rounds.")
            st.rerun()


        # # ---------------------------------------------------------
        # # PDF EXPORT (DUTCH INVOICE, 2 PAGES, AREA + ASSIGNMENT LIST)
        # # ---------------------------------------------------------
        # st.subheader("Export invoice as PDF")
        
        # if st.button("Generate PDF"):
        #     import random
        #     from reportlab.lib import colors
        #     from reportlab.platypus import Table, TableStyle
        
        #     bedrijf = st.secrets["bedrijf"]
        
        #     eigen_naam = bedrijf["naam"]
        #     eigen_adres = bedrijf["adres"]
        #     eigen_postcode = bedrijf["postcode"]
        #     eigen_stad = bedrijf["stad"]
        #     eigen_mobiel = bedrijf["mobiel"]
        #     eigen_email = bedrijf["email"]
        #     eigen_kvk = bedrijf["kvk"]
        #     eigen_btw = bedrijf["btw"]
        #     eigen_iban = bedrijf["iban"]
        
        #     if not klant_naam or not klant_adres or not klant_postcode or not klant_stad:
        #         st.error("Please fill in all client fields before generating the invoice.")
        #         st.stop()
        
        #     vandaag = datetime.today()
        #     factuurdatum = vandaag.strftime("%d-%m-%Y")
        #     factuurnummer = vandaag.strftime("%Y%m%d") + "-" + str(random.randint(1000, 9999))
        
        #     buffer = io.BytesIO()
        #     pdf = canvas.Canvas(buffer, pagesize=A4)
        #     width, height = A4
        
        #     # HEADER
        #     pdf.setFillColor(colors.blue)
        #     pdf.setFont("Helvetica-Bold", 22)
        #     pdf.drawRightString(width - 40, height - 70, f"Factuur {factuurnummer}")
        
        #     pdf.setFillColor(colors.black)
        #     pdf.setFont("Helvetica", 12)
        #     pdf.drawRightString(width - 40, height - 95, f"Periode(s): {', '.join(selected_months)}")
        
        #     pdf.setFont("Helvetica", 10)
        #     pdf.drawRightString(width - 40, height - 115, f"Datum: {factuurdatum}")
        
        #     y = height - 180
        
        #     # CLIENT
        #     pdf.setFont("Helvetica-Bold", 12)
        #     pdf.drawString(70, y, "Klant")
        #     y -= 18
        
        #     pdf.setFont("Helvetica", 10)
        #     pdf.drawString(70, y, klant_naam)
        #     y -= 14
        #     pdf.drawString(70, y, klant_adres)
        #     y -= 14
        #     pdf.drawString(70, y, f"{klant_postcode} {klant_stad}")
        
        #     y -= 20
        #     pdf.line(70, y, width / 2, y)
        
        #     # CONTRACTOR
        #     y -= 25
        #     pdf.setFont("Helvetica-Bold", 12)
        #     pdf.drawString(70, y, "Opdrachtnemer")
        #     y -= 18
        
        #     pdf.setFont("Helvetica", 10)
        #     pdf.drawString(70, y, eigen_naam)
        #     y -= 14
        #     pdf.drawString(70, y, eigen_adres)
        #     y -= 14
        #     pdf.drawString(70, y, f"{eigen_postcode} {eigen_stad}")
        #     y -= 14
        #     pdf.drawString(70, y, f"Telefoon: {eigen_mobiel}")
        #     y -= 14
        #     pdf.drawString(70, y, f"E-mail: {eigen_email}")
        #     y -= 14
        #     pdf.drawString(70, y, f"KvK: {eigen_kvk}")
        #     y -= 14
        #     pdf.drawString(70, y, f"BTW: {eigen_btw}")
        #     y -= 14
        #     pdf.drawString(70, y, f"IBAN: {eigen_iban}")
        
        #     y -= 30
        #     pdf.line(70, y, width - 40, y)
        #     y -= 40
        
        #     # ---------------------------------------------------------
        #     # GROUPED TABLES FOR INVOICE (DUTCH)
        #     # ---------------------------------------------------------
        
        #     df_assign = df_month[df_month["type"] != "Travel"].copy()
        #     df_assign["hours"] = df_assign.apply(
        #         lambda r: r["hours_worked"] if r["type"] in ["Deskwork", "Extra"] else r["hours_per_round"],
        #         axis=1
        #     )
        
        #     assign_summary = (
        #         df_assign.groupby("assignment")
        #         .agg(
        #             total_hours=("hours", "sum"),
        #             hourly_rate=("rate", "first"),
        #             total_amount=("amount", "sum")
        #         )
        #         .reset_index()
        #     )
        
        #     travel_summary = (
        #         df_month[df_month["type"] == "Travel"]
        #         .groupby("area")["travel_cost"]
        #         .sum()
        #         .reset_index()
        #     )
        
        #     # ---------------------------------------------------------
        #     # TABLE 1 — WORK SUMMARY
        #     # ---------------------------------------------------------
        
        #     y -= 6
        #     pdf.setFont("Helvetica-Bold", 12)
        #     pdf.drawString(70, y, "Overzicht werkzaamheden")
        #     y -= 30
        
        #     table1_data = [["Opdracht", "Uren", "Uurloon (€)", "Bedrag (€)"]]
        
        #     for _, row in assign_summary.iterrows():
        #         table1_data.append([
        #             row["assignment"],
        #             f"{row['total_hours']:.2f}",
        #             f"{row['hourly_rate']:,.2f}",
        #             f"{row['total_amount']:,.2f}"
        #         ])
        
        #     table1 = Table(table1_data, colWidths=[180, 60, 80, 80])
        #     table1.setStyle(TableStyle([
        #         ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        #         ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        #         ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        #         ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        #         ("FONTSIZE", (0, 0), (-1, -1), 8),
        #     ]))
        
        #     table1.wrapOn(pdf, width, height)
        #     table1_height = len(table1_data) * 15
        #     table1.drawOn(pdf, 70, y - table1_height)
        #     y -= table1_height + 20
        
        #     # ---------------------------------------------------------
        #     # TABLE 2 — TRAVEL COSTS (PLACED HERE)
        #     # ---------------------------------------------------------
        
        #     pdf.setFont("Helvetica-Bold", 12)
        #     pdf.drawString(70, y, "Reiskosten")
        #     y -= 20
        
        #     if travel_summary.empty:
        #         pdf.setFont("Helvetica", 10)
        #         pdf.drawString(70, y, "Geen reiskosten in deze periode.")
        #         y -= 20
        #     else:
        #         travel_data = [["Gebied", "Bedrag (€)"]]
        #         for _, row in travel_summary.iterrows():
        #             travel_data.append([
        #                 row["area"],
        #                 f"{row['travel_cost']:,.2f}"
        #             ])
        
        #         table2 = Table(travel_data, colWidths=[220, 100])
        #         table2.setStyle(TableStyle([
        #             ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        #             ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        #             ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        #             ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        #             ("FONTSIZE", (0, 0), (-1, -1), 8),
        #         ]))
        
        #         table2.wrapOn(pdf, width, height)
        #         table2_height = len(travel_data) * 15
        #         table2.drawOn(pdf, 70, y - table2_height)
        #         y -= table2_height + 30
        
        #     # ---------------------------------------------------------
        #     # TOTALS (WORK ONLY)
        #     # ---------------------------------------------------------
        
        #     pdf.setFont("Helvetica-Bold", 11)
        #     pdf.drawRightString(width - 40, y, f"Subtotaal werkzaamheden: € {subtotal:,.2f}")
        #     y -= 18
        #     pdf.drawRightString(width - 40, y, f"BTW 21%: € {vat:,.2f}")
        #     y -= 18
        #     pdf.drawRightString(width - 40, y, f"Totaal (excl. reiskosten): € {total:,.2f}")
        #     y -= 25
        
        #     # ---------------------------------------------------------
        #     # TRAVEL COSTS AFTER VAT
        #     # ---------------------------------------------------------
        
        #     travel_total = travel_summary["travel_cost"].sum() if not travel_summary.empty else 0
        
        #     pdf.drawRightString(width - 40, y, f"Reiskosten [1]: € {travel_total:,.2f}")
        #     y -= 18
        
        #     final_total = total + travel_total
        #     pdf.drawRightString(width - 40, y, f"Eindtotaal [2]: € {final_total:,.2f}")
        #     y -= 35
        
        #     # FOOTNOTES
        #     pdf.setFont("Helvetica", 8)
        #     pdf.drawString(70, y, "[1] Reiskosten zijn vrijgesteld van BTW.")
        #     y -= 12
        #     pdf.drawString(70, y, "[2] Betalingstermijn bedraagt **14 dagen** na factuurdatum.")
        
        #     # ---------------------------------------------------------
        #     # PAGE 2 — GROUPED LIST PER AREA
        #     # ---------------------------------------------------------
        
        #     pdf.showPage()
        #     y = height - 80
        
        #     pdf.setFont("Helvetica-Bold", 18)
        #     pdf.drawString(70, y, "Uren en inkomsten per gebied en opdracht")
        #     y -= 40
        
        #     # Compute hours per area + assignment
        #     df_area = df_month[df_month["type"] != "Travel"].copy()
        #     df_area["hours"] = df_area.apply(
        #         lambda r: r["hours_worked"] if r["type"] in ["Deskwork", "Extra"] else r["hours_per_round"],
        #         axis=1
        #     )
        
        #     area_summary = (
        #         df_area.groupby(["area", "assignment"])
        #         .agg(
        #             total_hours=("hours", "sum"),
        #             hourly_rate=("rate", "first"),
        #             total_amount=("amount", "sum")
        #         )
        #         .reset_index()
        #     )
        
        #     pdf.setFont("Helvetica", 10)
        
        #     current_area = None
        
        #     for _, row in area_summary.iterrows():
        #         area = row["area"]
        
        #         if area != current_area:
        #             pdf.setFont("Helvetica-Bold", 12)
        #             pdf.drawString(70, y, f"Gebied: {area}")
        #             y -= 20
        #             current_area = area
        
        #         pdf.setFont("Helvetica", 10)
        #         pdf.drawString(90, y, f"- Opdracht: {row['assignment']}")
        #         y -= 14
        #         pdf.drawString(110, y, f"Uren: {row['total_hours']:.2f}")
        #         y -= 14
        #         pdf.drawString(110, y, f"Uurloon: € {row['hourly_rate']:,.2f}")
        #         y -= 14
        #         pdf.drawString(110, y, f"Bedrag: € {row['total_amount']:,.2f}")
        #         y -= 20
        
        #         if y < 100:
        #             pdf.showPage()
        #             y = height - 80
        #             pdf.setFont("Helvetica-Bold", 18)
        #             pdf.drawString(70, y, "Uren en inkomsten per gebied en opdracht")
        #             y -= 40
        #             pdf.setFont("Helvetica", 10)
        
        #     pdf.save()
        #     buffer.seek(0)
        
        #     st.download_button(
        #         "Download PDF",
        #         buffer,
        #         file_name=f"factuur_{factuurnummer}.pdf",
        #         mime="application/pdf"
        #     )

        # ---------------------------------------------------------
        # PDF EXPORT (DUTCH INVOICE, 2 PAGES, AREA + ASSIGNMENT LIST)
        # ---------------------------------------------------------
        st.subheader("Export invoice as PDF")

        if st.button("Generate PDF"):
            import random
            import io
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            bedrijf = st.secrets["bedrijf"]

            eigen_naam = bedrijf["naam"]
            eigen_adres = bedrijf["adres"]
            eigen_postcode = bedrijf["postcode"]
            eigen_stad = bedrijf["stad"]
            eigen_mobiel = bedrijf["mobiel"]
            eigen_email = bedrijf["email"]
            eigen_kvk = bedrijf["kvk"]
            eigen_btw = bedrijf["btw"]
            eigen_iban = bedrijf["iban"]

            if not klant_naam or not klant_adres or not klant_postcode or not klant_stad:
                st.error("Please fill in all client fields before generating the invoice.")
                st.stop()

            vandaag = datetime.today()
            factuurdatum = vandaag.strftime("%d-%m-%Y")
            factuurnummer = vandaag.strftime("%Y%m%d") + "-" + str(random.randint(1000, 9999))

            # -----------------------------------------------------
            # PREPARE DATA
            # -----------------------------------------------------
            df_assign = df_month[df_month["type"] != "Travel"].copy()
            df_assign["hours"] = df_assign.apply(
                lambda r: r["hours_worked"] if r["type"] in ["Deskwork", "Extra"] else r["hours_per_round"],
                axis=1
            )

            assign_summary = (
                df_assign.groupby("assignment")
                .agg(
                    total_hours=("hours", "sum"),
                    hourly_rate=("rate", "first"),
                    total_amount=("amount", "sum")
                )
                .reset_index()
            )

            travel_summary = (
                df_month[df_month["type"] == "Travel"]
                .groupby("area")["travel_cost"]
                .sum()
                .reset_index()
            )

            df_area = df_month[df_month["type"] != "Travel"].copy()
            df_area["hours"] = df_area.apply(
                lambda r: r["hours_worked"] if r["type"] in ["Deskwork", "Extra"] else r["hours_per_round"],
                axis=1
            )

            area_summary = (
                df_area.groupby(["area", "assignment"])
                .agg(
                    total_hours=("hours", "sum"),
                    hourly_rate=("rate", "first"),
                    total_amount=("amount", "sum")
                )
                .reset_index()
            )

            travel_total = travel_summary["travel_cost"].sum() if not travel_summary.empty else 0
            final_total = total + travel_total

            # -----------------------------------------------------
            # PDF BUILD
            # -----------------------------------------------------
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=20 * mm,
                rightMargin=20 * mm,
                topMargin=20 * mm,
                bottomMargin=20 * mm,
            )

            styles = getSampleStyleSheet()
            normal = styles["Normal"]
            normal.italic = 0

            body = styles["BodyText"]
            body.italic = 0

            title_style = ParagraphStyle(
                "title_style",
                parent=styles["Heading1"],
                fontSize=20,
                textColor=colors.blue,
                alignment=2,  # right
                italic=0
            )

            right_text = ParagraphStyle(
                "right_text",
                parent=normal,
                alignment=2,
                italic=0
            )

            bold = ParagraphStyle(
                "bold",
                parent=styles["Heading4"],
                fontSize=12,
                spaceAfter=4,
                italic=0
            )

            heading_center = ParagraphStyle(
                "heading_center",
                parent=styles["Heading1"],
                fontSize=20,
                alignment=1,  # center
                italic=0,
                textColor=colors.blue,
            )

            indent1 = ParagraphStyle(
                "indent1",
                parent=normal,
                leftIndent=15,
                italic=0
            )
            indent2 = ParagraphStyle(
                "indent2",
                parent=normal,
                leftIndent=30,
                italic=0
            )

            red_total = ParagraphStyle(
                "red_total",
                parent=right_text,
                textColor=colors.red,
                fontSize=12,
                italic=0
            )

            story = []

            # -----------------------------------------------------
            # PAGE 1 HEADER
            # -----------------------------------------------------
            story.append(Paragraph(f"Factuur {factuurnummer}", title_style))
            story.append(Paragraph(f"Periode(s): {', '.join(selected_months)}", right_text))
            story.append(Paragraph(f"Datum: {factuurdatum}", right_text))
            story.append(Spacer(1, 12))

            # OPDRACHTGEVER
            story.append(Paragraph("<b>Opdrachtgever</b>", bold))
            story.append(Paragraph(klant_naam, normal))
            story.append(Paragraph(klant_adres, normal))
            story.append(Paragraph(f"{klant_postcode} {klant_stad}", normal))
            story.append(Spacer(1, 12))

            # OPDRACHTNEMER
            story.append(Paragraph("<b>Opdrachtnemer</b>", bold))
            story.append(Paragraph(eigen_naam, normal))
            story.append(Paragraph(eigen_adres, normal))
            story.append(Paragraph(f"{eigen_postcode} {eigen_stad}", normal))
            story.append(Paragraph(f"Telefoon: {eigen_mobiel}", normal))
            story.append(Paragraph(f"E-mail: {eigen_email}", normal))
            story.append(Paragraph(f"KvK: {eigen_kvk}", normal))
            story.append(Paragraph(f"BTW: {eigen_btw}", normal))
            story.append(Paragraph(f"IBAN: {eigen_iban}", normal))
            story.append(Spacer(1, 18))

            # -----------------------------------------------------
            # TABLE 1 — WORK SUMMARY
            # -----------------------------------------------------
            story.append(Paragraph("<b>Overzicht werkzaamheden</b>", bold))
            story.append(Spacer(1, 6))

            table1_data = [["Opdracht", "Uren", "Uurloon (€)", "Bedrag (€)"]]
            for _, row in assign_summary.iterrows():
                table1_data.append([
                    row["assignment"],
                    f"{row['total_hours']:.2f}",
                    f"{row['hourly_rate']:,.2f}",
                    f"{row['total_amount']:,.2f}",
                ])

            table1 = Table(table1_data, colWidths=[180, 60, 80, 80], hAlign="LEFT")
            table1.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]))
            story.append(table1)
            story.append(Spacer(1, 18))

            # -----------------------------------------------------
            # TABLE 2 — TRAVEL COSTS
            # -----------------------------------------------------
            story.append(Paragraph("<b>Reiskosten</b>", bold))
            story.append(Spacer(1, 6))

            if travel_summary.empty:
                story.append(Paragraph("Geen reiskosten in deze periode.", normal))
            else:
                travel_data = [["Gebied", "Bedrag (€)"]]
                for _, row in travel_summary.iterrows():
                    travel_data.append([
                        row["area"],
                        f"{row['travel_cost']:,.2f}",
                    ])

                table2 = Table(travel_data, colWidths=[220, 100], hAlign="LEFT")
                table2.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]))
                story.append(table2)

            story.append(Spacer(1, 18))

            # -----------------------------------------------------
            # PAGE BREAK
            # -----------------------------------------------------
            story.append(PageBreak())

            # -----------------------------------------------------
            # PAGE 2 — AREA SUMMARY (LIST, NOT ONE PER PAGE)
            # -----------------------------------------------------
            story.append(Paragraph("Uren en inkomsten per gebied en opdracht", heading_center))
            story.append(Spacer(1, 12))

            current_area = None
            for _, row in area_summary.iterrows():
                area = row["area"]

                if area != current_area:
                    story.append(Paragraph(f"<b>Gebied: {area}</b>", bold))
                    story.append(Spacer(1, 6))
                    current_area = area

                story.append(Paragraph(f"- Opdracht: {row['assignment']}", indent1))
                story.append(Paragraph(f"Uren: {row['total_hours']:.2f}", indent2))
                story.append(Paragraph(f"Uurloon: € {row['hourly_rate']:,.2f}", indent2))
                story.append(Paragraph(f"Bedrag: € {row['total_amount']:,.2f}", indent2))
                story.append(Spacer(1, 10))

            # -----------------------------------------------------
            # FOOTER + FIXED TOTALS ON PAGE 1
            # -----------------------------------------------------
            def first_page(canvas, doc_obj):
                canvas.saveState()
            
                # ---------------------------------------------------------
                # FOOTER (with bold "14 dagen")
                # ---------------------------------------------------------
                canvas.setFont("Helvetica", 7)
                x = doc_obj.leftMargin
                y = 12 * mm
                canvas.drawString(x, y + 8, "[1] Reiskosten zijn vrijgesteld van BTW.")
                canvas.setFont("Helvetica-Bold", 7)
                canvas.drawString(x, y, "[2] Betalingstermijn bedraagt 14 dagen na factuurdatum.")
                canvas.setFont("Helvetica", 7)
            
                # ---------------------------------------------------------
                # TOTALS BOX (shaded + horizontal line)
                # ---------------------------------------------------------
                tx = doc_obj.leftMargin + doc_obj.width
                box_top = 65 * mm
                box_bottom = 35 * mm
                box_left = doc_obj.leftMargin + 60
                box_right = doc_obj.leftMargin + doc_obj.width
            

            
                # ---------------------------------------------------------
                # TOTALS TEXT (right aligned)
                # ---------------------------------------------------------
                canvas.setFillColor(colors.black)
                canvas.setFont("Helvetica", 10)
            
                canvas.drawRightString(tx, box_top - 5, f"Subtotaal werkzaamheden: € {subtotal:,.2f}")
                canvas.drawRightString(tx, box_top - 20, f"BTW 21%: € {vat:,.2f}")
                canvas.drawRightString(tx, box_top - 35, f"Totaal (excl. reiskosten): € {total:,.2f}")
            
                # Space before Reiskosten + Eindtotaal group
                canvas.drawRightString(tx, box_top - 55, f"Reiskosten [1]: € {travel_total:,.2f}")
            
                # Eindtotaal — bold, red, larger
                canvas.setFont("Helvetica-Bold", 12)
                canvas.setFillColor(colors.red)
                canvas.drawRightString(tx, box_top - 75, f"Eindtotaal [2]: € {final_total:,.2f}")
            
                canvas.restoreState()



            def later_pages(canvas, doc_obj):
                pass

            doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
            buffer.seek(0)

            st.download_button(
                "Download PDF",
                buffer,
                file_name=f"factuur_{factuurnummer}.pdf",
                mime="application/pdf",
            )





