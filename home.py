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







