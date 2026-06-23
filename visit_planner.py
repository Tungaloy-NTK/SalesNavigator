import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import database as db

PURPOSES = ["Routine check-in", "Test tool follow-up", "New business", "Issue resolution",
            "Product demo", "Quote follow-up", "Relationship building", "Other"]

def fmt_date(d):
    if not d: return "—"
    try: return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError): return d

def nav(page, **kwargs):
    st.session_state["page"] = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

def page_planner():
    st.markdown('<div class="section-header">Visit Planner</div>', unsafe_allow_html=True)
    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    # Month/year selector
    today = date.today()
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    sel_year  = col2.selectbox("Year", [today.year, today.year+1], index=0, key="plan_year")
    sel_month = col1.selectbox("Month", list(range(1,13)),
                               index=today.month-1, key="plan_month",
                               format_func=lambda m: calendar.month_name[m])

    # Rep selector for managers
    selected_rep_id = user_id
    if role in ("admin", "regional_manager", "marketing"):
        if role == "admin" or role == "marketing":
            all_reps = db.get_reps_and_managers()
        else:
            team = db.get_team_members(user_id)
            all_reps = [db.get_user_by_id(user_id)] + list(team)

        rep_options = [("all", "All Reps")] + [(str(u["id"]), u["full_name"]) for u in all_reps if u]
        sel = col3.selectbox("View", [r[1] for r in rep_options], key="plan_rep_view")
        selected_rep_id = next((r[0] for r in rep_options if r[1]==sel), "all")

    # New visit button
    if col4.button("➕ Plan a Visit", type="primary"):
        nav("plan_visit_new")

    # Get visits for selected month
    if selected_rep_id == "all":
        visits = db.get_all_planned_visits(sel_month, sel_year)
    else:
        visits = db.get_planned_visits_for_user(int(selected_rep_id), sel_month, sel_year)

    # Also get actual visits from the visits table for context
    st.markdown("---")

    # Build calendar grid
    cal = calendar.monthcalendar(sel_year, sel_month)
    visit_by_day = {}
    for v in visits:
        try:
            d = datetime.strptime(v["visit_date"][:10], "%Y-%m-%d").day
            visit_by_day.setdefault(d, []).append(v)
        except (ValueError, TypeError):
            pass

    # Render calendar
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for i, name in enumerate(day_names):
        header_cols[i].markdown(f"<div style='text-align:center;font-weight:700;font-size:13px;color:#888'>{name}</div>", unsafe_allow_html=True)

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].markdown("<div style='min-height:80px'></div>", unsafe_allow_html=True)
            else:
                is_today = (day == today.day and sel_month == today.month and sel_year == today.year)
                bg = "#fff3f3" if is_today else "#f8f9fa"
                border = "2px solid #c0392b" if is_today else "1px solid #eee"
                day_visits = visit_by_day.get(day, [])
                visits_html = ""
                for v in day_visits[:3]:
                    status_col = "#27ae60" if v["status"]=="completed" else "#3498db" if v["status"]=="planned" else "#e67e22"
                    name = v["customer_name"][:18]
                    rep = v["rep_name"].split()[0] if selected_rep_id == "all" else ""
                    visits_html += f"<div style='font-size:10px;padding:2px 4px;margin:1px 0;background:{status_col};color:white;border-radius:3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis'>{rep+': ' if rep else ''}{name}</div>"
                if len(day_visits) > 3:
                    visits_html += f"<div style='font-size:10px;color:#888'>+{len(day_visits)-3} more</div>"

                cols[i].markdown(f"""<div style='min-height:80px;background:{bg};border:{border};border-radius:6px;padding:4px 6px'>
                    <div style='font-size:13px;font-weight:{"700" if is_today else "400"};color:{"#c0392b" if is_today else "#0a0a0a"}'>{day}</div>
                    {visits_html}
                </div>""", unsafe_allow_html=True)

    # Visit list below calendar
    st.markdown("---")
    st.markdown(f"### Visits in {calendar.month_name[sel_month]} {sel_year}")

    if not visits:
        st.info("No visits planned for this month. Click 'Plan a Visit' above to schedule one, or select a different month to view existing plans.")
        return

    for v in visits:
        col1, col2, col3, col4, col5 = st.columns([2, 3, 2, 2, 1])
        col1.write(f"**{fmt_date(v['visit_date'])}**")
        col2.write(f"**{v['customer_name']}**")
        col3.write(v["rep_name"])
        purpose = v["purpose"] or "—"
        col4.write(purpose)
        status_col = "🟢" if v["status"]=="completed" else "🔵" if v["status"]=="planned" else "🟠"
        col5.write(f"{status_col} {v['status'].title()}")

def page_plan_visit_new():
    st.markdown('<div class="section-header">Plan a Visit</div>', unsafe_allow_html=True)
    if st.button("← Back"):
        nav("visit_planner")

    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    customers = db.get_all_customers()
    customer_options = {f"{c['customer_name']} ({c['customer_code']})": c for c in customers}

    # Manager can assign to any rep
    can_assign = role in ("admin", "regional_manager", "marketing")
    if can_assign:
        if role in ("admin", "marketing"):
            assignable = db.get_reps_and_managers()
        else:
            team = db.get_team_members(user_id)
            assignable = [db.get_user_by_id(user_id)] + list(team)
    else:
        assignable = [db.get_user_by_id(user_id)]

    # Customer picker outside form so contacts update when customer changes
    col1, col2 = st.columns(2)
    selected_cust = col1.selectbox("Customer *", list(customer_options.keys()), key="pv_cust")
    visit_date = col2.date_input("Visit Date *", min_value=date.today(), key="pv_date", help="Planned date for the customer visit")

    # Load contacts for selected customer
    cust_obj  = customer_options.get(selected_cust)
    cust_code = cust_obj["customer_code"] if cust_obj else None
    known_contacts = []
    if cust_code:
        with db.get_conn() as conn:
            known_contacts = conn.execute(
                "SELECT contact_name, email FROM customer_contacts "
                "WHERE customer_code=? ORDER BY contact_name", (cust_code,)
            ).fetchall()

    contact_display = (
        [f"{r['contact_name']} ({r['email']})" if r['email'] else r['contact_name']
         for r in known_contacts]
        + ["➕ Add a new contact"]
    )
    contact_choice = st.selectbox("Contact", contact_display, key="pv_contact")

    new_contact_name  = ""
    new_contact_email = ""
    if contact_choice == "➕ Add a new contact":
        nc1, nc2 = st.columns(2)
        new_contact_name  = nc1.text_input("Contact Name", placeholder="Full name", key="pv_nc_name")
        new_contact_email = nc2.text_input("Email", placeholder="email@company.com", key="pv_nc_email")

    with st.form("plan_visit_form"):
        col1, col2 = st.columns(2)
        if can_assign:
            assign_to = col1.selectbox("Assign to",
                                       options=[u["id"] for u in assignable if u],
                                       format_func=lambda uid: next((u["full_name"] for u in assignable if u and u["id"]==uid), ""))
        else:
            assign_to = user_id
            col1.text_input("Assigned to", value=st.session_state["full_name"], disabled=True)

        purpose = col2.selectbox("Purpose", PURPOSES, help="Main reason for the visit — helps managers see the balance of activity types")
        notes = st.text_area("Notes", placeholder="Any context for this visit...", help="Anything the rep should know before going, e.g. outstanding quotes, issues to discuss")
        submitted = st.form_submit_button("Plan Visit", type="primary")

    if submitted:
        cust = customer_options.get(selected_cust)

        # Resolve contact name
        if contact_choice == "➕ Add a new contact":
            contact_name_saved = new_contact_name.strip() or None
        else:
            contact_name_saved = contact_choice.split(" (")[0].strip()

        # Save new contact to DB + LACRM if provided
        if contact_choice == "➕ Add a new contact" and new_contact_name.strip():
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO customer_contacts "
                    "(customer_code, contact_name, email) VALUES (?,?,?)",
                    (cust_code, new_contact_name.strip(),
                     new_contact_email.strip() or None)
                )
            if new_contact_email.strip():
                try:
                    import lacrm as _lacrm, requests as _req
                    parts = new_contact_name.strip().split(" ", 1)
                    ok, contact_id = _lacrm.create_contact(
                        first_name   = parts[0],
                        last_name    = parts[1] if len(parts) > 1 else "",
                        email        = new_contact_email.strip(),
                        company_name = cust["customer_name"] if cust else "",
                        background   = "Added via Sales Navigator visit planner.",
                    )
                    if ok and contact_id:
                        _req.get("https://api.lessannoyingcrm.com", params={
                            "UserCode":  db.get_setting("lacrm_user_code"),
                            "APIToken":  db.get_setting("lacrm_api_key"),
                            "Function":  "AddContactToGroup",
                            "ContactId": contact_id,
                            "GroupName": "Sales Navigator",
                        }, timeout=10)
                    st.toast("New contact added to LACRM ✅")
                except Exception:
                    pass

        data = {
            "customer_code": cust["customer_code"] if cust else "",
            "customer_name": cust["customer_name"] if cust else selected_cust,
            "user_id":       assign_to,
            "assigned_by":   user_id if can_assign else None,
            "visit_date":    visit_date.strftime("%Y-%m-%d"),
            "purpose":       purpose,
            "notes":         notes.strip() or None,
            "status":        "planned",
            "contact_name":  contact_name_saved,
        }
        db.create_planned_visit(data)
        db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "create", "planned_visit",
                     entity_label=f"{cust['customer_name'] if cust else selected_cust} on {visit_date}",
                     details=f"Purpose: {purpose}")
        st.success(f"Visit planned for {fmt_date(visit_date.strftime('%Y-%m-%d'))}")
        st.balloons()
        nav("visit_planner")

def render_page():
    page = st.session_state.get("page", "visit_planner")
    if page == "plan_visit_new":
        page_plan_visit_new()
    else:
        page_planner()
