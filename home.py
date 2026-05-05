import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

# ---------- Supabase client ----------
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

st.set_page_config(page_title="Assignments & Rounds", layout="wide")

st.title("Assignments planner with Supabase")

# ---------- Helpers ----------
def fetch_assignments():
    return supabase.table("assignments").select("*").order("inserted_at", desc=True).execute().data

def fetch_rounds():
    return supabase.table("rounds").select("*, assignments(name, area, hourly_rate, hours_per_round, min_days_between_rounds)").order("work_date", desc=True).execute().data

def days_between(d1, d2):
    return abs((d2 - d1).days)

# ---------- Tabs ----------
tab1, tab2, tab3 = st.tabs(["1) Plan rounds (calendar)", "2) Assignment settings", "3) Monthly earnings & invoice"])

# =========================================================
# TAB 2: ASSIGNMENT SETTINGS (do this first logically)
# =========================================================
with tab2:
    st.header("Assignment configuration")

    st.subheader("Create / edit assignment")

    # For editing existing assignment
    assignments = fetch_assignments()
    assignment_names = ["New assignment"] + [f"{a['name']} ({a['area']})" for a in assignments]
    selected_idx = st.selectbox("Select assignment to edit", range(len(assignment_names)), format_func=lambda i: assignment_names[i])

    editing_existing = selected_idx > 0
    current = assignments[selected_idx - 1] if editing_existing else None

    with st.form("assignment_form", clear_on_submit=not editing_existing):
        name = st.text_input("Assignment name", value=current["name"] if current else "")
        area = st.text_input("Area", value=current["area"] if current else "")
        hourly_rate = st.number_input("Hourly rate (€ / hour)", min_value=0.0, step=1.0, value=float(current["hourly_rate"]) if current else 0.0)
        hours_per_round = st.number_input("Hours per round", min_value=0.0, step=0.5, value=float(current["hours_per_round"]) if current else 0.0)
        min_days_between_rounds = st.number_input("Min days between rounds", min_value=0, step=1, value=int(current["min_days_between_rounds"]) if current else 0)

        submitted = st.form_submit_button("Save assignment")

        if submitted:
            payload = {
                "name": name,
                "area": area,
                "hourly_rate": hourly_rate,
                "hours_per_round": hours_per_round,
                "min_days_between_rounds": int(min_days_between_rounds),
            }
            if editing_existing:
                supabase.table("assignments").update(payload).eq("id", current["id"]).execute()
                st.success("Assignment updated.")
            else:
                supabase.table("assignments").insert(payload).execute()
                st.success("Assignment created.")

    st.subheader("Assignments overview")

    assignments = fetch_assignments()
    if assignments:
        st.dataframe(assignments, use_container_width=True)

        # Delete assignment
        delete_ids = [a["id"] for a in assignments]
        delete_labels = [f"{a['name']} ({a['area']})" for a in assignments]
        to_delete = st.selectbox("Delete assignment", ["None"] + delete_labels)
        if to_delete != "None":
            idx = delete_labels.index(to_delete)
            if st.button("Confirm delete assignment"):
                supabase.table("assignments").delete().eq("id", delete_ids[idx]).execute()
                st.warning("Assignment deleted (and its rounds).")
    else:
        st.info("No assignments yet. Create one above.")

# =========================================================
# TAB 1: PLAN ROUNDS (CALENDAR-LIKE)
# =========================================================
with tab1:
    st.header("Plan your rounds")

    assignments = fetch_assignments()
    if not assignments:
        st.warning("You need at least one assignment (configure it in tab 2).")
    else:
        # Form to add / edit a round
        st.subheader("Add a round")

        assignment_options = {f"{a['name']} ({a['area']})": a for a in assignments}
        assignment_label = st.selectbox("Assignment", list(assignment_options.keys()))
        selected_assignment = assignment_options[assignment_label]

        work_date = st.date_input("Work date", value=date.today())
        kind = st.text_input("Kind of assignment / shift (e.g. morning, night, etc.)", value="round")

        if st.button("Add round"):
            supabase.table("rounds").insert({
                "assignment_id": selected_assignment["id"],
                "work_date": work_date.isoformat(),
                "kind": kind,
            }).execute()
            st.success("Round added.")

        st.subheader("Calendar-like overview")

        rounds = fetch_rounds()
        if rounds:
            # Show as table grouped by month
            df_rows = []
            for r in rounds:
                a = r["assignments"]
                df_rows.append({
                    "id": r["id"],
                    "date": r["work_date"],
                    "assignment": a["name"],
                    "area": a["area"],
                    "kind": r["kind"],
                    "hours": float(a["hours_per_round"]),
                    "hourly_rate": float(a["hourly_rate"]),
                    "min_days_between_rounds": int(a["min_days_between_rounds"]),
                })

            import pandas as pd
            df = pd.DataFrame(df_rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")

            # Simple month filter
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                month_ref = st.date_input("Reference month", value=date.today().replace(day=1))
            with col_m2:
                show_month = st.checkbox("Show only selected month", value=True)

            if show_month:
                df_month = df[(df["date"].dt.month == month_ref.month) & (df["date"].dt.year == month_ref.year)]
            else:
                df_month = df

            st.dataframe(df_month, use_container_width=True)

            # Edit / delete a round
            st.subheader("Edit / delete rounds")

            round_labels = [f"{row['date'].date()} - {row['assignment']} ({row['kind']})" for _, row in df.iterrows()]
            round_ids = list(df["id"])
            selected_round_label = st.selectbox("Select round", round_labels)
            idx = round_labels.index(selected_round_label)
            selected_round_id = round_ids[idx]
            selected_round_row = df.iloc[idx]

            # Edit date and kind
            new_date = st.date_input("New date", value=selected_round_row["date"].date(), key="edit_date")
            new_kind = st.text_input("New kind", value=selected_round_row["kind"], key="edit_kind")

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                if st.button("Save changes"):
                    supabase.table("rounds").update({
                        "work_date": new_date.isoformat(),
                        "kind": new_kind,
                    }).eq("id", selected_round_id).execute()
                    st.success("Round updated.")
            with col_e2:
                if st.button("Delete round"):
                    supabase.table("rounds").delete().eq("id", selected_round_id).execute()
                    st.warning("Round deleted.")

            # Warning about min days between rounds
            st.subheader("Rounds spacing warnings")

            # For each assignment, check consecutive rounds
            warnings = []
            for assignment in assignments:
                a_id = assignment["id"]
                a_name = assignment["name"]
                min_days = int(assignment["min_days_between_rounds"])
                if min_days <= 0:
                    continue

                a_rounds = df[df["assignment"] == a_name].sort_values("date")
                prev_date = None
                for _, row in a_rounds.iterrows():
                    if prev_date is not None:
                        d = days_between(prev_date.date(), row["date"].date())
                        if d < min_days:
                            warnings.append(f"{a_name}: only {d} days between {prev_date.date()} and {row['date'].date()} (min {min_days}).")
                    prev_date = row["date"]

            if warnings:
                for w in warnings:
                    st.error(w)
            else:
                st.success("All rounds respect the minimum days between rounds.")
        else:
            st.info("No rounds yet. Add one above.")

# =========================================================
# TAB 3: MONTHLY EARNINGS & INVOICE
# =========================================================
with tab3:
    st.header("Monthly earnings and invoice")

    rounds = fetch_rounds()
    if not rounds:
        st.info("No rounds yet.")
    else:
        import pandas as pd

        rows = []
        for r in rounds:
            a = r["assignments"]
            work_date = datetime.strptime(r["work_date"], "%Y-%m-%d").date()
            hours = float(a["hours_per_round"])
            rate = float(a["hourly_rate"])
            amount = hours * rate
            rows.append({
                "date": work_date,
                "assignment": a["name"],
                "area": a["area"],
                "kind": r["kind"],
                "hours": hours,
                "rate": rate,
                "amount": amount,
            })

        df = pd.DataFrame(rows)
        df["year_month"] = df["date"].apply(lambda d: d.strftime("%Y-%m"))

        # Select month
        months = sorted(df["year_month"].unique())
        selected_month = st.selectbox("Select month", months, index=len(months) - 1)

        df_month = df[df["year_month"] == selected_month]
        total_hours = df_month["hours"].sum()
        total_amount = df_month["amount"].sum()
        btw = total_amount * 0.21
        total_with_btw = total_amount + btw

        st.subheader(f"Invoice preview for {selected_month}")
        st.write("Detailed rounds:")
        st.dataframe(df_month[["date", "assignment", "area", "kind", "hours", "rate", "amount"]], use_container_width=True)

        st.markdown("#### Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total hours", f"{total_hours:.2f}")
        col2.metric("Subtotal (€)", f"{total_amount:,.2f}")
        col3.metric("BTW 21% (€)", f"{btw:,.2f}")
        col4.metric("Total incl. BTW (€)", f"{total_with_btw:,.2f}")

        st.markdown("#### Invoice text (copy-paste)")
        invoice_text = f"""
Invoice month: {selected_month}

Total hours: {total_hours:.2f}
Subtotal (excl. BTW): € {total_amount:,.2f}
BTW 21%: € {btw:,.2f}
Total (incl. BTW): € {total_with_btw:,.2f}
"""
        st.text_area("Invoice", value=invoice_text, height=150)
