import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, datetime
import altair as alt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

# ---------------------------------------------------------
# PASSWORD PROTECTION
# ---------------------------------------------------------
def check_password():
    # Initialize session state variables
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "password_input" not in st.session_state:
        st.session_state["password_input"] = ""

    # If not authenticated, show login UI
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

        # Stop the app until authenticated
        if not st.session_state["authenticated"]:
            st.stop()

# Run the check
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
# Sidebar Navigation (Grouped)
# ---------------------------------------------------------
st.set_page_config(page_title="Work Planner", layout="wide")
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
    subpage = st.sidebar.radio("Activity", ["Log Work Day", "Rounds Overview & Plot"])

else:
    subpage = "Monthly Earnings"

st.title("Work Planner")

# ---------------------------------------------------------
# PAGE — ASSIGNMENTS
# ---------------------------------------------------------
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
        ["Deskwork", "Fieldwork"],
        index=0 if not selected else (0 if selected["type"] == "Deskwork" else 1)
    )

    name = st.text_input("Assignment name", value=selected["name"] if selected else "")

    if assignment_type == "Deskwork":
        hourly_rate = st.number_input(
            "Hourly rate (€)",
            value=float(selected["hourly_rate"]) if selected else 0.0
        )
        hours_per_round = None
        min_days = None
    else:
        hours_per_round = st.number_input(
            "Hours per round",
            value=float(selected["hours_per_round"]) if selected else 0.0
        )
        min_days = st.number_input(
            "Minimum days between rounds",
            value=int(selected["min_days_between_rounds"]) if selected else 0
        )
        hourly_rate = st.number_input(
            "Hourly rate (€)",
            value=float(selected["hourly_rate"]) if selected else 0.0
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
        df_a = pd.DataFrame(assignments).drop(columns=["id", "created_at"], errors="ignore")
        st.dataframe(df_a, use_container_width=True)

    if assignments:
        del_sel = st.selectbox("Delete assignment", ["None"] + [f"{a['name']} ({a['type']})" for a in assignments])
        if del_sel != "None":
            if st.button("Confirm delete assignment"):
                a_id = next(a["id"] for a in assignments if f"{a['name']} ({a['type']})" == del_sel)
                supabase.table("assignments").delete().eq("id", a_id).execute()
                st.warning("Assignment deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE — AREAS
# ---------------------------------------------------------
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
        df_ar = pd.DataFrame(areas).drop(columns=["id", "created_at"], errors="ignore")
        st.dataframe(df_ar, use_container_width=True)

    if areas:
        del_sel = st.selectbox("Delete area", ["None"] + [a["name"] for a in areas])
        if del_sel != "None":
            if st.button("Confirm delete area"):
                a_id = next(a["id"] for a in areas if a["name"] == del_sel)
                supabase.table("areas").delete().eq("id", a_id).execute()
                st.warning("Area deleted.")
                refresh()

# ---------------------------------------------------------
# PAGE — LOG WORK DAY
# ---------------------------------------------------------
elif subpage == "Log Work Day":
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
                            "hours_worked": None
                        }).execute()
                        st.success("Fieldwork day saved.")
                        refresh()

# ---------------------------------------------------------
# PAGE — ROUNDS OVERVIEW & PLOT
# ---------------------------------------------------------
elif subpage == "Rounds Overview & Plot":
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
        # FILTERS (NO DATE FILTER)
        # -------------------------------
        st.subheader("Filters")

        col1, col2 = st.columns(2)

        with col1:
            assignment_filter = st.multiselect("Filter by assignment", df["assignment"].unique())

        with col2:
            area_filter = st.multiselect("Filter by area", df["area"].dropna().unique())

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
                    color=alt.Color(
                        "assignment:N",
                        title="Assignment",
                        scale=alt.Scale(scheme="category10")   # VERY DISTINCT COLORS
                    ),
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
                    color=alt.Color(
                        "assignment:N",
                        title="Assignment",
                        scale=alt.Scale(scheme="paired")   # ALSO VERY DISTINCT
                    ),
                    tooltip=["date:T", "assignment:N", "area:N"]
                )
                .interactive()
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
elif subpage == "Monthly Earnings":
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
                "area": r["areas"]["name"] if r["areas"] else None,
                "hours_worked": r["hours_worked"],
                "hours_per_round": r["assignments"]["hours_per_round"],
                "rate": r["assignments"]["hourly_rate"],
            }
            for r in rounds
        ])

        # ---------------------------------------------------------
        # CORRECT HOURS + AMOUNT (Deskwork vs Fieldwork)
        # ---------------------------------------------------------
        def compute_hours(row):
            if row["type"] == "Deskwork":
                return row["hours_worked"] or 0
            else:
                return row["hours_per_round"] or 0

        df["hours"] = df.apply(compute_hours, axis=1)
        df["amount"] = df["hours"] * df["rate"]
        df["month"] = df["date"].apply(lambda d: d.strftime("%Y-%m"))

        # ---------------------------------------------------------
        # MULTI-MONTH SELECTION
        # ---------------------------------------------------------
        st.subheader("Select month(s)")
        months = sorted(df["month"].unique())
        selected_months = st.multiselect("Months", months, default=[months[-1]])

        if not selected_months:
            st.info("Select at least one month.")
            st.stop()

        df_month = df[df["month"].isin(selected_months)]

        # ---------------------------------------------------------
        # TOTALS
        # ---------------------------------------------------------
        subtotal = df_month["amount"].sum()
        vat = subtotal * 0.21
        total = subtotal + vat

        st.metric("Subtotal", f"€ {subtotal:,.2f}")
        st.metric("VAT 21%", f"€ {vat:,.2f}")
        st.metric("Total", f"€ {total:,.2f}")

        st.markdown("---")

        # ---------------------------------------------------------
        # HOURS PER ASSIGNMENT
        # ---------------------------------------------------------
        st.subheader("Hours per assignment")

        hours_assignment = (
            df_month.groupby("assignment")["hours"]
            .sum()
            .reset_index()
            .sort_values("hours", ascending=False)
        )
        st.dataframe(hours_assignment, use_container_width=True)

        st.markdown("---")

        # ---------------------------------------------------------
        # HOURS & MONEY PER AREA (NESTED BY ASSIGNMENT)
        # ---------------------------------------------------------
        st.subheader("Hours and earnings per area (by assignment)")

        df_area = df_month.dropna(subset=["area"])

        area_assignment = (
            df_area.groupby(["area", "assignment"])
            .agg(hours=("hours", "sum"), amount=("amount", "sum"))
            .reset_index()
        )

        for area in sorted(area_assignment["area"].unique()):
            st.markdown(f"**Area: {area}**")
            df_area_block = area_assignment[area_assignment["area"] == area].sort_values("assignment")
            for _, row in df_area_block.iterrows():
                st.markdown(
                    f"- {row['assignment']}: "
                    f"{row['hours']:.2f} hours — € {row['amount']:,.2f}"
                )
            st.markdown("")

        st.markdown("---")

        # ---------------------------------------------------------
        # TOTAL EARNINGS PER ASSIGNMENT
        # ---------------------------------------------------------
        st.subheader("Total earnings per assignment")

        earnings_assignment = (
            df_month.groupby("assignment")["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )

        st.dataframe(earnings_assignment, use_container_width=True)

        st.markdown("---")

        # ---------------------------------------------------------
        # HOURLY WAGE PER ASSIGNMENT
        # ---------------------------------------------------------
        wage_assignment = (
            df_month.groupby("assignment")["rate"]
            .first()
            .reset_index()
            .sort_values("assignment")
        )

        st.subheader("Hourly wage per assignment")
        st.dataframe(wage_assignment, use_container_width=True)

        st.markdown("---")

        # ---------------------------------------------------------
        # CLIENT INFO (RIGHT SIDE OF INVOICE)
        # ---------------------------------------------------------
        st.subheader("Client information (for invoice)")
        klant_naam = st.text_input("Client name")
        klant_adres = st.text_input("Client address")
        klant_postcode = st.text_input("Client postcode")
        klant_stad = st.text_input("Client city")

        # ---------------------------------------------------------
        # PDF EXPORT (DUTCH ONLY, ADVANCED LAYOUT + QR + FOOTER)
        # ---------------------------------------------------------
        st.subheader("Export invoice as PDF")


        # --- CALCULATE TOTAL HOURS + INCOME FOR VELDWERK ---
        total_vw_hours = area_assignment["hours"].sum()
        total_vw_income = area_assignment["amount"].sum()
        
        if st.button("Generate PDF"):
            import random
            import qrcode
            from reportlab.lib import colors
            from reportlab.lib.utils import ImageReader
            from reportlab.platypus import Table, TableStyle
        
            # ---------------------------------------------------------
            # LOAD BUSINESS INFO FROM SECRETS
            # ---------------------------------------------------------
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
        
            # ---------------------------------------------------------
            # VALIDATE CLIENT INFO
            # ---------------------------------------------------------
            if not klant_naam or not klant_adres or not klant_postcode or not klant_stad:
                st.error("Please fill in all client fields before generating the invoice.")
                st.stop()
        
            # ---------------------------------------------------------
            # FACTUURNUMMER + FACTUURDATUM
            # ---------------------------------------------------------
            vandaag = datetime.today()
            factuurdatum = vandaag.strftime("%d-%m-%Y")
            factuurnummer = vandaag.strftime("%Y%m%d") + "-" + str(random.randint(1000, 9999))
        
            # ---------------------------------------------------------
            # PDF START
            # ---------------------------------------------------------
            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
        
            # ---------------------------------------------------------
            # PAGE 1 — HEADER (TOP RIGHT)
            # ---------------------------------------------------------
            pdf.setFont("Helvetica-Bold", 22)
            pdf.drawRightString(width - 40, height - 70, f"Factuur {factuurnummer}")
        
            pdf.setFont("Helvetica", 12)
            pdf.drawRightString(width - 40, height - 95, f"Periode(s): {', '.join(selected_months)}")
        
            pdf.setFont("Helvetica", 10)
            pdf.drawRightString(width - 40, height - 115, f"Factuurdatum: {factuurdatum}")
        
            # ---------------------------------------------------------
            # ORIGINAL Y POSITION (unchanged)
            # ---------------------------------------------------------
            y = height - 180
        
            # ---------------------------------------------------------
            # OPDRACHTGEVER
            # ---------------------------------------------------------
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(70, y, "Opdrachtgever")
            y -= 18
        
            pdf.setFont("Helvetica", 10)
            pdf.drawString(70, y, klant_naam)
            y -= 14
            pdf.drawString(70, y, klant_adres)
            y -= 14
            pdf.drawString(70, y, f"{klant_postcode} {klant_stad}")
        
            # HALF LINE
            y -= 10
            pdf.setLineWidth(0.5)
            pdf.setStrokeColor(colors.grey)
            pdf.line(70, y, width - 40, y)
        
            # ---------------------------------------------------------
            # OPDRACHTNEMER
            # ---------------------------------------------------------
            y -= 25
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(70, y, "Opdrachtnemer")
            y -= 18
        
            pdf.setFont("Helvetica", 10)
            pdf.drawString(70, y, eigen_naam)
            y -= 14
            pdf.drawString(70, y, eigen_adres)
            y -= 14
            pdf.drawString(70, y, f"{eigen_postcode} {eigen_stad}")
            y -= 14
            pdf.drawString(70, y, f"Mobiel: {eigen_mobiel}")
            y -= 14
            pdf.drawString(70, y, f"E-mail: {eigen_email}")
            y -= 14
            pdf.drawString(70, y, f"KvK: {eigen_kvk}")
            y -= 14
            pdf.drawString(70, y, f"BTW: {eigen_btw}")
            y -= 14
            pdf.drawString(70, y, f"IBAN: {eigen_iban}")
        
            # ---------------------------------------------------------
            # FULL LINE BEFORE TABLE
            # ---------------------------------------------------------
            y -= 20
            pdf.setLineWidth(1)
            pdf.setStrokeColor(colors.black)
            pdf.line(70, y, width - 40, y)
        
            y -= 80
        
            # ---------------------------------------------------------
            # BUILD TABLE DATA (A3 VERSION 2, WIDER + SMALLER FONT)
            # ---------------------------------------------------------
            table_data = [
                ["Opdracht", "Uurtarief", "Uren", "Inkomsten"]
            ]
        
            for _, row in hours_assignment.iterrows():
                rate = wage_assignment.loc[
                    wage_assignment["assignment"] == row["assignment"], "rate"
                ].values[0]
        
                amount = earnings_assignment.loc[
                    earnings_assignment["assignment"] == row["assignment"], "amount"
                ].values[0]
        
                table_data.append([
                    row["assignment"],
                    f"€ {rate:,.2f} / uur",
                    f"{row['hours']:.0f}",
                    f"€ {amount:,.2f}"
                ])
        
                table_data.append(["", "", "", ""])  # padding row
        
            # ---------------------------------------------------------
            # CREATE TABLE (WIDER + SMALLER FONT)
            # ---------------------------------------------------------
            table = Table(
                table_data,
                colWidths=[180, 120, 60, 120]   # wider table
            )
        
            table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),   # smaller header
        
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),   # smaller rows
        
                ("ALIGN", (1, 1), (-1, -1), "LEFT"),
        
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("LINEABOVE", (0, 0), (-1, 0), 2, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
        
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
        
            table_height = len(table_data) * 16
            table.wrapOn(pdf, width, height)
            table.drawOn(pdf, 70, y - table_height)
        
            y = y - table_height - 40
        
            # ---------------------------------------------------------
            # TOTALS
            # ---------------------------------------------------------
            pdf.setFont("Helvetica-Bold", 12)
            pdf.setFillColor(colors.black)
            pdf.drawString(70, y, f"Subtotaal: € {subtotal:,.2f}")
        
            y -= 18
            pdf.drawString(70, y, f"BTW 21%: € {vat:,.2f}")
        
            y -= 18
            pdf.setFillColor(colors.red)
            pdf.drawString(70, y, f"Totaal: € {total:,.2f}")
        
            # FOOTER PAGE 1
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(colors.grey)
            pdf.drawString(70, 30, f"Betaling dient binnen 2 weken na factuurdatum te geschieden.")
            pdf.drawRightString(width - 40, 30, "Pagina 1")
        
            pdf.showPage()
        
            # ---------------------------------------------------------
            # PAGE 2 — VELDWERK (WITH TOTALS IN BRACKETS)
            # ---------------------------------------------------------
            pdf.setFont("Helvetica-Bold", 18)
            pdf.setFillColor(colors.black)
            pdf.drawString(
                70,
                height - 70,
                f"Veldwerk ({total_vw_hours:.2f} uuren — € {total_vw_income:,.2f})"
            )
        
            pdf.setLineWidth(1)
            pdf.line(70, height - 80, width - 40, height - 80)
        
            y = height - 120
            pdf.setFont("Helvetica", 10)
        
            for area in sorted(area_assignment["area"].unique()):
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(70, y, f"Gebied: {area}")
                y -= 18
        
                pdf.setFont("Helvetica", 10)
                df_area_block = area_assignment[area_assignment["area"] == area].sort_values("assignment")
                for _, row in df_area_block.iterrows():
                    pdf.drawString(
                        80,
                        y,
                        f"- {row['assignment']}: {row['hours']:.2f} uur — € {row['amount']:,.2f}"
                    )
                    y -= 14
        
                    if y < 70:
                        break
        
                y -= 10
                if y < 70:
                    break
        
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(colors.grey)
            # pdf.drawString(70, 30, f"{eigen_naam} • {eigen_email} • IBAN: {eigen_iban}")
            pdf.drawRightString(width - 40, 30, "Pagina 2")
        
            pdf.showPage()
            pdf.save()
        
            buffer.seek(0)
        
            st.download_button(
                label="Download PDF invoice",
                data=buffer,
                file_name=f"factuur_{factuurnummer}.pdf",
                mime="application/pdf"
            )
