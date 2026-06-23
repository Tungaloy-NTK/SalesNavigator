"""CRM module — Customer 360, Contacts, Notes, Tasks, Segments."""
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import database as db

# ── Helpers ───────────────────────────────────────────────────────────────────

PRIORITY_COLOUR = {"🔴 High": "#e74c3c", "🟡 Medium": "#f39c12", "🟢 Low": "#27ae60"}
TYPE_ICONS = {"📞 Call": "📞", "📧 Email": "📧", "🤝 Meeting": "🤝",
              "🏭 Site Visit": "🏭", "💬 Other": "💬"}

def _card(label, value, colour="#1a1a2e"):
    st.markdown(f"""
        <div style="background:{colour};border-radius:8px;padding:14px 18px;text-align:center;">
            <div style="color:#fff;font-size:11px;opacity:.8;margin-bottom:4px;">{label}</div>
            <div style="color:#fff;font-size:22px;font-weight:700;">{value}</div>
        </div>""", unsafe_allow_html=True)

def _fmt_date(d):
    if not d:
        return "—"
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except:
        return str(d)[:10]

def _customer_picker(key_suffix="", label="Customer"):
    with db.get_conn() as conn:
        custs = conn.execute(
            "SELECT customer_code, customer_name FROM customers ORDER BY customer_name"
        ).fetchall()
    options = {f"{r['customer_name']} ({r['customer_code']})": r['customer_code'] for r in custs}
    sel = st.selectbox(label, ["— select —"] + list(options.keys()), key=f"cust_pick_{key_suffix}")
    return options.get(sel), sel.split("(")[0].strip() if sel != "— select —" else None

def _all_reps():
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT id, full_name FROM users WHERE role IN ('rep','regional_manager','admin') ORDER BY full_name"
        ).fetchall()

# ── Tab 1: Customer 360 ───────────────────────────────────────────────────────

def _360_detail(code, cust_name, user):
    """Render the full 360 detail panel for a selected customer."""
    with st.spinner("Loading customer data…"):
        summary  = db.crm_customer_summary(code)
        contacts = db.crm_get_contacts(customer_code=code)
        notes    = db.crm_get_notes(customer_code=code, limit=10)
        tasks    = db.crm_get_tasks(customer_code=code, status="open")
        products = db.crm_customer_top_products(code)

    yr = date.today().year

    # ── KPI row
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: _card(f"YTD {yr} Sales",  f"£{(summary['ytd_sales'] or 0):,.0f}",  "#1a1a2e")
    with c2: _card(f"{yr-1} Sales",    f"£{(summary['prev_sales'] or 0):,.0f}", "#2c3e50")
    with c3: _card("YTD GP",           f"£{(summary['ytd_gp'] or 0):,.0f}",     "#16a085")
    with c4: _card("Last Order",       _fmt_date(summary['last_order']),         "#8e44ad")
    with c5: _card("Open Tasks",       str(len(tasks)),
                   "#e74c3c" if tasks else "#27ae60")

    st.markdown("---")

    # ── Detail columns
    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### 📋 Account Info")
        st.markdown(f"""
        | | |
        |---|---|
        | **Rep** | {summary['rep_name'] or '—'} |
        | **Town** | {summary['addr_town'] or '—'} |
        | **Postcode** | {summary['addr_postcode'] or '—'} |
        | **Region** | {summary['region'] or '—'} |
        | **Type** | {summary['customer_type'] or '—'} |
        | **Distributor** | {summary['main_distributor'] or '—'} |
        """)

        st.markdown("#### 👥 Contacts")
        if contacts:
            for c in contacts:
                primary = " ⭐" if c['is_primary'] else ""
                st.markdown(f"**{c['contact_name']}{primary}**")
                details = []
                if c['job_title']: details.append(c['job_title'])
                if c['email']:     details.append(f"✉ {c['email']}")
                if c['phone']:     details.append(f"📱 {c['phone']}")
                if details:
                    st.caption(" · ".join(details))
        else:
            st.caption("No contacts recorded.")

        if products:
            st.markdown(f"#### 📦 Top Products {yr}")
            df = pd.DataFrame([dict(r) for r in products])
            df['total_sales'] = pd.to_numeric(df['total_sales'], errors='coerce')
            df['total_qty']   = pd.to_numeric(df['total_qty'],   errors='coerce')
            st.dataframe(
                df[['item_desc','total_qty','total_sales']].rename(
                    columns={'item_desc':'Product','total_qty':'Qty','total_sales':'Sales £'}),
                use_container_width=True, hide_index=True,
                column_config={
                    "Sales £": st.column_config.NumberColumn("Sales £", format="£%.0f"),
                    "Qty":     st.column_config.NumberColumn("Qty",     format="%,.0f"),
                }
            )

    with right:
        st.markdown("#### 📝 Recent Notes")
        if notes:
            for n in notes:
                icon = TYPE_ICONS.get(n['note_type'], "💬")
                with st.container():
                    st.markdown(f"""
                    <div style="border-left:3px solid #c0392b;padding:6px 12px;margin-bottom:8px;background:#fafafa;border-radius:0 6px 6px 0;">
                        <div style="font-size:11px;color:#888;">{icon} {n['note_type']} &nbsp;·&nbsp; {_fmt_date(n['created_at'])} &nbsp;·&nbsp; {n['author'] or '—'}</div>
                        <div style="margin-top:4px;">{n['note_text']}</div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.caption("No notes yet.")

        st.markdown("#### ✅ Open Tasks")
        if tasks:
            for t in tasks:
                overdue = t['due_date'] and t['due_date'] < date.today().isoformat()
                colour  = "#e74c3c" if overdue else PRIORITY_COLOUR.get(t['priority'], "#888")
                due_str = f"Due {_fmt_date(t['due_date'])}" if t['due_date'] else "No due date"
                if overdue:
                    due_str = f"⚠ OVERDUE — {_fmt_date(t['due_date'])}"
                st.markdown(f"""
                <div style="border-left:3px solid {colour};padding:6px 12px;margin-bottom:8px;background:#fafafa;border-radius:0 6px 6px 0;">
                    <div style="font-weight:600;">{t['title']}</div>
                    <div style="font-size:11px;color:#888;">{t['priority']} &nbsp;·&nbsp; {due_str} &nbsp;·&nbsp; {t['assigned_name'] or '—'}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.success("No open tasks — all clear! ✅")

        # Quick note
        st.markdown("#### ➕ Quick Note")
        with st.form(f"quick_note_{code}"):
            qn_type = st.selectbox("Type", db.NOTE_TYPES)
            qn_text = st.text_area("Note", height=80)
            if st.form_submit_button("💾 Save Note"):
                if qn_text.strip():
                    db.crm_add_note(code, user['id'], qn_text.strip(), qn_type)
                    db.log_audit(user['id'], user['full_name'], "create", "note",
                                 entity_label=f"{cust_name or code}",
                                 details=f"Type: {qn_type}")
                    st.success("Note saved!")
                    st.rerun()
                else:
                    st.warning("Please enter a note.")


def tab_customer_360(user):
    st.markdown("### 🔍 Customer 360")

    role    = user["role"]
    user_id = user["id"]

    # ── KPI summary cards ──
    totals = db.crm_overview_totals(user_id=user_id, role=role)
    k1, k2, k3, k4 = st.columns(4)
    with k1: _card("Contacts on File",  f"{totals['total_contacts']:,}",  "#1a1a2e")
    with k2: _card("Open Tasks",        f"{totals['open_tasks']:,}",      "#2c3e50")
    with k3: _card("Overdue Tasks",     f"{totals['overdue_tasks']:,}",
                   "#e74c3c" if totals['overdue_tasks'] else "#27ae60")
    with k4: _card("Notes (30 days)",   f"{totals['notes_30d']:,}",       "#8e44ad")

    st.markdown("---")

    # ── Filters ──
    with st.spinner("Loading CRM overview…"):
        customers = db.crm_customer_overview(user_id=user_id, role=role)

    # Build filter options from data
    rep_names   = sorted(set(c['rep_name'] for c in customers if c.get('rep_name')))
    regions     = sorted(set(c['region']   for c in customers if c.get('region')))
    post_areas  = sorted(set(c['post_area'] for c in customers if c.get('post_area')))
    cust_types  = sorted(set(c['customer_type'] for c in customers if c.get('customer_type')))

    f1, f2, f3 = st.columns([3, 2, 2])
    search     = f1.text_input("🔍 Search", placeholder="Customer name or code…", key="crm360_search")
    rep_filter = f2.selectbox("Rep", ["All Reps"] + rep_names, key="crm360_rep")
    reg_filter = f3.selectbox("Region", ["All Regions"] + regions, key="crm360_region")

    f4, f5, f6 = st.columns([2, 2, 2])
    pa_filter   = f4.selectbox("Post Area", ["All Post Areas"] + post_areas, key="crm360_postarea")
    type_filter = f5.selectbox("Type", ["All Types"] + cust_types, key="crm360_type")
    activity_filter = f6.selectbox("Activity", ["All", "Has Open Tasks", "Has Overdue Tasks",
                                                 "Has Contacts", "No Contacts", "No Notes (30d)"],
                                    key="crm360_activity")

    # ── Apply filters ──
    filtered = customers
    if search:
        s = search.lower()
        filtered = [c for c in filtered
                    if s in (c['customer_name'] or '').lower()
                    or s in (c['customer_code'] or '').lower()
                    or s in (c.get('sm_name') or '').lower()]
    if rep_filter != "All Reps":
        filtered = [c for c in filtered if c.get('rep_name') == rep_filter]
    if reg_filter != "All Regions":
        filtered = [c for c in filtered if c.get('region') == reg_filter]
    if pa_filter != "All Post Areas":
        filtered = [c for c in filtered if c.get('post_area') == pa_filter]
    if type_filter != "All Types":
        filtered = [c for c in filtered if c.get('customer_type') == type_filter]
    if activity_filter == "Has Open Tasks":
        filtered = [c for c in filtered if c['open_tasks'] > 0]
    elif activity_filter == "Has Overdue Tasks":
        filtered = [c for c in filtered if c['overdue_tasks'] > 0]
    elif activity_filter == "Has Contacts":
        filtered = [c for c in filtered if c['contact_count'] > 0]
    elif activity_filter == "No Contacts":
        filtered = [c for c in filtered if c['contact_count'] == 0]
    elif activity_filter == "No Notes (30d)":
        filtered = [c for c in filtered if c['note_count'] == 0]

    st.markdown(f"**{len(filtered)}** customers")

    if not filtered:
        st.info("No customers match these filters. Adjust the filters above or upload data to populate the CRM.")
        return

    # ── Customer table ──
    hcols = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
    for hc, h in zip(hcols, ["Customer", "Rep", "Contacts", "Tasks", "Last Note",
                              "Last Order", "YTD Sales", ""]):
        hc.markdown(f"**{h}**")
    st.markdown("<hr style='margin:4px 0'/>", unsafe_allow_html=True)

    # Sort: overdue tasks first, then open tasks, then by name
    sorted_custs = sorted(filtered, key=lambda c: (
        -c['overdue_tasks'], -c['open_tasks'], (c['customer_name'] or '').lower()
    ))

    yr = date.today().year
    for c in sorted_custs[:100]:
        r1, r2, r3, r4, r5, r6, r7, r8 = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
        r1.write(f"**{c['customer_name']}**")
        r2.caption(c.get('rep_name') or '—')
        r3.write(f"👥 {c['contact_count']}" if c['contact_count'] else "—")
        # Tasks with colour coding
        if c['overdue_tasks'] > 0:
            r4.markdown(f"<span style='color:#e74c3c;font-weight:700'>⚠ {c['open_tasks']}</span>",
                        unsafe_allow_html=True)
        elif c['open_tasks'] > 0:
            r4.write(f"📋 {c['open_tasks']}")
        else:
            r4.write("✅")
        r5.caption(_fmt_date(c.get('last_note_date')))
        r6.caption(_fmt_date(c.get('last_sale')))
        ytd = c.get('ytd_sales') or 0
        r7.write(f"£{ytd:,.0f}" if ytd else "—")
        if r8.button("360", key=f"crm360_{c['customer_code']}"):
            st.session_state["crm360_selected"] = c['customer_code']
            st.session_state["crm360_name"] = c['customer_name']
            st.rerun()

    if len(filtered) > 100:
        st.caption(f"Showing first 100 of {len(filtered)} customers. Use filters to narrow down.")

    # ── Selected customer detail ──
    selected_code = st.session_state.get("crm360_selected")
    if selected_code:
        st.markdown("---")
        sel_name = st.session_state.get("crm360_name", selected_code)
        col_hdr, col_close = st.columns([8, 1])
        col_hdr.markdown(f"## {sel_name}")
        col_hdr.caption(f"Code: {selected_code}")
        if col_close.button("✖ Close", key="crm360_close"):
            st.session_state.pop("crm360_selected", None)
            st.session_state.pop("crm360_name", None)
            st.rerun()
        _360_detail(selected_code, sel_name, user)

# ── Tab 2: Contacts ───────────────────────────────────────────────────────────

def tab_contacts(user):
    st.markdown("### 👥 Contacts")

    search_col, cust_col = st.columns([1, 1])
    with search_col:
        search = st.text_input("🔍 Search contacts", placeholder="Name, email, phone…", key="contact_search")
    with cust_col:
        code_filter, _ = _customer_picker("contacts_filter", "Filter by Customer")

    contacts = db.crm_get_contacts(customer_code=code_filter, search=search or None)

    st.markdown(f"**{len(contacts)} contact{'s' if len(contacts) != 1 else ''} found**")

    # ── Add new contact form
    with st.expander("➕ Add New Contact"):
        with st.form("add_contact_form"):
            ac1, ac2 = st.columns(2)
            with ac1:
                new_cust_code, _ = _customer_picker("new_contact")
                new_name  = st.text_input("Contact Name *")
                new_email = st.text_input("Email")
            with ac2:
                new_phone = st.text_input("Phone")
                new_title = st.text_input("Job Title")
                new_primary = st.checkbox("Primary contact")
            if st.form_submit_button("💾 Save Contact"):
                if new_cust_code and new_name.strip():
                    # Check for duplicates
                    existing = db.crm_get_contacts(customer_code=new_cust_code)
                    dupe_name = any(c['contact_name'].lower() == new_name.strip().lower() for c in existing)
                    dupe_email = new_email and any(
                        c['email'] and c['email'].lower() == new_email.strip().lower() for c in existing
                    )
                    if dupe_name:
                        st.warning(f"A contact called '{new_name.strip()}' already exists for this customer.")
                    elif dupe_email:
                        st.warning(f"A contact with email '{new_email.strip()}' already exists for this customer.")
                    else:
                        db.crm_save_contact(new_cust_code, new_name.strip(), new_email or None,
                                            new_phone or None, new_title or None,
                                            1 if new_primary else 0)
                        db.log_audit(user['id'], user['full_name'], "create", "contact",
                                     entity_label=f"{new_name.strip()} at {new_cust_code}",
                                     details=f"Email: {new_email or 'N/A'}, Title: {new_title or 'N/A'}")
                        st.success(f"Contact '{new_name}' saved!")
                        st.rerun()
                else:
                    st.warning("Customer and Contact Name are required.")

    # ── Contact table
    if contacts:
        for c in contacts:
            with st.container():
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    primary = " ⭐" if c['is_primary'] else ""
                    st.markdown(f"**{c['contact_name']}{primary}**")
                    st.caption(c['customer_name'] or c['customer_code'])
                with col2:
                    parts = []
                    if c['job_title']: parts.append(c['job_title'])
                    if c['email']:     parts.append(f"✉ {c['email']}")
                    if c['phone']:     parts.append(f"📱 {c['phone']}")
                    st.markdown(" &nbsp;·&nbsp; ".join(parts) if parts else "—")
                with col3:
                    with st.popover("🗑", key=f"del_contact_{c['id']}", help="Delete contact"):
                        st.caption("Are you sure?")
                        if st.button("Yes, delete", key=f"confirm_del_contact_{c['id']}", type="primary"):
                            db.crm_delete_contact(c['id'])
                            db.log_audit(user['id'], user['full_name'], "delete", "contact",
                                         entity_id=c['id'], entity_label=f"{c['contact_name']}",
                                         details=f"Customer: {c['customer_name'] or c['customer_code']}")
                            st.rerun()
            st.divider()
    else:
        st.info("No contacts found.")

    # ── CSV Export ──
    if contacts:
        export_df = pd.DataFrame([{
            "Contact Name": c['contact_name'],
            "Customer":     c['customer_name'] or c['customer_code'],
            "Job Title":    c.get('job_title') or "",
            "Email":        c.get('email') or "",
            "Phone":        c.get('phone') or "",
            "Primary":      "Yes" if c['is_primary'] else "No",
        } for c in contacts])
        st.download_button(
            "📥 Export Contacts",
            data=export_df.to_csv(index=False),
            file_name="contacts.csv",
            mime="text/csv",
            key="dl_contacts",
        )

# ── Tab 3: Notes & Interactions ───────────────────────────────────────────────

def tab_notes(user):
    st.markdown("### 📝 Notes & Interactions")

    # Filters row
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    with f1: code_filter, _ = _customer_picker("notes_filter", "Filter by Customer")
    with f2:
        type_filter = st.selectbox("Type", ["All Types"] + db.NOTE_TYPES, key="note_type_filter")
    with f3:
        reps = _all_reps()
        rep_opts = {r['full_name']: r['id'] for r in reps}
        rep_sel = st.selectbox("Rep", ["All Reps"] + list(rep_opts.keys()), key="note_rep_filter")
    with f4:
        st.markdown("<br>", unsafe_allow_html=True)

    # Log new note
    with st.expander("➕ Log a New Interaction"):
        with st.form("log_note_form"):
            n1, n2 = st.columns(2)
            with n1:
                note_cust_code, _ = _customer_picker("log_note")
                note_type = st.selectbox("Interaction Type", db.NOTE_TYPES)
            with n2:
                # contacts for selected customer
                if note_cust_code:
                    conts = db.crm_get_contacts(customer_code=note_cust_code)
                    cont_opts = ["— none —"] + [c['contact_name'] for c in conts]
                else:
                    cont_opts = ["— none —"]
                note_contact = st.selectbox("Contact (optional)", cont_opts)
            note_text = st.text_area("Notes *", height=100)
            if st.form_submit_button("💾 Log Interaction"):
                if note_cust_code and note_text.strip():
                    contact = note_contact if note_contact != "— none —" else None
                    db.crm_add_note(note_cust_code, user['id'], note_text.strip(), note_type, contact)
                    db.log_audit(user['id'], user['full_name'], "create", "note",
                                 entity_label=f"{note_cust_code}",
                                 details=f"Type: {note_type}, Contact: {contact or 'N/A'}")
                    st.success("Interaction logged!")
                    st.rerun()
                else:
                    st.warning("Customer and notes are required.")

    st.markdown("---")

    # Fetch and display
    notes = db.crm_get_notes(
        customer_code=code_filter,
        user_id=rep_opts.get(rep_sel) if rep_sel != "All Reps" else None,
        note_type=type_filter if type_filter != "All Types" else None,
        limit=100
    )

    st.markdown(f"**{len(notes)} interaction{'s' if len(notes) != 1 else ''}**")

    for n in notes:
        icon = TYPE_ICONS.get(n['note_type'], "💬")
        contact_str = f" · {n['contact_name']}" if n['contact_name'] else ""
        with st.container():
            hdr_col, del_col = st.columns([10, 1])
            with hdr_col:
                st.markdown(f"""
                <div style="border-left:4px solid #c0392b;padding:8px 14px;margin-bottom:6px;background:#fafafa;border-radius:0 8px 8px 0;">
                    <div style="font-size:11px;color:#888;margin-bottom:4px;">
                        {icon} <b>{n['note_type']}</b> &nbsp;·&nbsp;
                        <b>{n['customer_name'] or n['customer_code']}</b>{contact_str} &nbsp;·&nbsp;
                        {_fmt_date(n['created_at'])} &nbsp;·&nbsp; {n['author'] or '—'}
                    </div>
                    <div>{n['note_text']}</div>
                </div>""", unsafe_allow_html=True)
            with del_col:
                if user['role'] == 'admin' or n['user_id'] == user['id']:
                    with st.popover("🗑", key=f"del_note_{n['id']}"):
                        st.caption("Are you sure?")
                        if st.button("Yes, delete", key=f"confirm_del_note_{n['id']}", type="primary"):
                            db.crm_delete_note(n['id'])
                            st.rerun()

    if not notes:
        st.info("No interactions found for these filters.")

# ── Tab 4: Tasks ──────────────────────────────────────────────────────────────

def tab_tasks(user):
    st.markdown("### ✅ Tasks & Follow-ups")

    # Summary counts
    all_tasks     = db.crm_get_tasks(limit=1000)
    open_tasks    = [t for t in all_tasks if t['status'] == 'open']
    overdue_tasks = [t for t in open_tasks if t['due_date'] and t['due_date'] < date.today().isoformat()]
    due_today     = [t for t in open_tasks if t['due_date'] == date.today().isoformat()]
    my_tasks      = [t for t in open_tasks if t['assigned_to'] == user['id']]

    m1, m2, m3, m4 = st.columns(4)
    with m1: _card("Open Tasks",    str(len(open_tasks)),    "#2c3e50")
    with m2: _card("Overdue",       str(len(overdue_tasks)), "#e74c3c" if overdue_tasks else "#27ae60")
    with m3: _card("Due Today",     str(len(due_today)),     "#f39c12" if due_today else "#27ae60")
    with m4: _card("Assigned to Me",str(len(my_tasks)),      "#8e44ad")

    st.markdown("---")

    # ── New task form
    with st.expander("➕ Create New Task"):
        with st.form("new_task_form"):
            t1, t2 = st.columns(2)
            with t1:
                task_cust, _ = _customer_picker("new_task")
                task_title   = st.text_input("Task Title *")
                task_desc    = st.text_area("Description", height=80)
            with t2:
                reps     = _all_reps()
                rep_opts = {r['full_name']: r['id'] for r in reps}
                task_rep = st.selectbox("Assign To", list(rep_opts.keys()), key="task_assign")
                task_due = st.date_input("Due Date", value=date.today() + timedelta(days=7))
                task_pri = st.selectbox("Priority", db.TASK_PRIORITIES, index=1)
            if st.form_submit_button("💾 Create Task"):
                if task_cust and task_title.strip():
                    db.crm_save_task(
                        task_cust, task_title.strip(), task_desc or None,
                        rep_opts.get(task_rep), user['id'],
                        task_due.isoformat(), task_pri
                    )
                    db.log_audit(user['id'], user['full_name'], "create", "task",
                                 entity_label=f"{task_title.strip()} — {task_cust}",
                                 details=f"Priority: {task_pri}, Due: {task_due.isoformat()}, Assigned: {task_rep}")
                    st.success("Task created!")
                    st.rerun()
                else:
                    st.warning("Customer and Task Title are required.")

    st.markdown("---")

    # ── Filters
    tf1, tf2, tf3 = st.columns(3)
    with tf1:
        view_filter = st.selectbox("View", ["All Open Tasks", "My Tasks", "Overdue", "Completed"], key="task_view")
    with tf2:
        pri_filter = st.selectbox("Priority", ["All"] + db.TASK_PRIORITIES, key="task_pri_filter")
    with tf3:
        reps        = _all_reps()
        rep_opts2   = {r['full_name']: r['id'] for r in reps}
        task_rep_f  = st.selectbox("Assigned To", ["All Reps"] + list(rep_opts2.keys()), key="task_rep_f")

    # Fetch tasks
    status_filter = "completed" if view_filter == "Completed" else "open"
    tasks = db.crm_get_tasks(
        assigned_to=rep_opts2.get(task_rep_f) if task_rep_f != "All Reps" else None,
        status=status_filter,
        overdue_only=(view_filter == "Overdue"),
        limit=200
    )
    if view_filter == "My Tasks":
        tasks = [t for t in tasks if t['assigned_to'] == user['id']]
    if pri_filter != "All":
        tasks = [t for t in tasks if t['priority'] == pri_filter]

    st.markdown(f"**{len(tasks)} task{'s' if len(tasks) != 1 else ''}**")

    for t in tasks:
        overdue = t['due_date'] and t['due_date'] < date.today().isoformat() and t['status'] == 'open'
        colour  = "#e74c3c" if overdue else PRIORITY_COLOUR.get(t['priority'], "#888")
        due_str = _fmt_date(t['due_date']) if t['due_date'] else "No due date"

        with st.container():
            row1, row2 = st.columns([8, 2])
            with row1:
                overdue_badge = " ⚠️ OVERDUE" if overdue else ""
                st.markdown(f"""
                <div style="border-left:4px solid {colour};padding:8px 14px;background:#fafafa;border-radius:0 8px 8px 0;">
                    <div style="font-weight:700;">{t['title']}{overdue_badge}</div>
                    <div style="font-size:11px;color:#888;margin-top:3px;">
                        {t['customer_name'] or t['customer_code']} &nbsp;·&nbsp;
                        {t['priority']} &nbsp;·&nbsp; Due: {due_str} &nbsp;·&nbsp;
                        👤 {t['assigned_name'] or '—'}
                    </div>
                    {f'<div style="margin-top:5px;font-size:13px;">{t["description"]}</div>' if t['description'] else ''}
                </div>""", unsafe_allow_html=True)
            with row2:
                if t['status'] == 'open':
                    if st.button("✅ Done", key=f"complete_{t['id']}"):
                        db.crm_complete_task(t['id'])
                        db.log_audit(user['id'], user['full_name'], "update", "task",
                                     entity_id=t['id'], entity_label=f"{t['title']}",
                                     details="Marked as completed")
                        st.rerun()
                else:
                    st.caption(f"✅ Done\n{_fmt_date(t['completed_at'])}")
                    if st.button("↩ Reopen", key=f"reopen_{t['id']}"):
                        db.crm_reopen_task(t['id'])
                        st.rerun()
                with st.popover("🗑", key=f"del_task_{t['id']}"):
                    st.caption("Are you sure?")
                    if st.button("Yes, delete", key=f"confirm_del_task_{t['id']}", type="primary"):
                        db.crm_delete_task(t['id'])
                        st.rerun()
        st.divider()

    if not tasks:
        st.success("No tasks found for these filters. 🎉")

# ── Tab 5: Segments ───────────────────────────────────────────────────────────

def tab_segments(user):
    st.markdown("### 🏷️ Customer Segments")

    segments = db.crm_get_segments()

    # ── Create segment
    with st.expander("➕ Create New Segment"):
        st.markdown("**Build a segment by filtering your customer list**")
        with st.form("create_segment_form"):
            seg_name = st.text_input("Segment Name *", placeholder="e.g. No Order Q2 2026")
            seg_desc = st.text_area("Description", height=60)

            st.markdown("**Filters** (leave blank to ignore)")
            sf1, sf2, sf3 = st.columns(3)
            with sf1:
                # Rep filter
                reps     = _all_reps()
                rep_opts = {"All Reps": None} | {r['full_name']: r['id'] for r in reps}
                seg_rep  = st.selectbox("Rep", list(rep_opts.keys()), key="seg_rep")
            with sf2:
                seg_no_order_since = st.date_input(
                    "No order since", value=None,
                    help="Include customers with NO orders after this date")
            with sf3:
                seg_min_spend = st.number_input(
                    "Min 2025 spend (£)", min_value=0, value=0, step=1000,
                    help="Only include customers who spent at least this in 2025")

            if st.form_submit_button("🔍 Preview & Save Segment"):
                if not seg_name.strip():
                    st.warning("Segment name is required.")
                else:
                    with db.get_conn() as conn:
                        where = ["1=1"]
                        params = []
                        rep_id = rep_opts.get(seg_rep)
                        if rep_id:
                            where.append("c.user_id = ?")
                            params.append(rep_id)
                        if seg_no_order_since:
                            where.append("""
                                c.customer_code NOT IN (
                                    SELECT customer_code FROM sales WHERE sale_date >= ?
                                )
                            """)
                            params.append(seg_no_order_since.isoformat())
                        if seg_min_spend > 0:
                            where.append("""
                                c.customer_code IN (
                                    SELECT customer_code FROM sales WHERE year=2025
                                    GROUP BY customer_code HAVING SUM(sales_val) >= ?
                                )
                            """)
                            params.append(seg_min_spend)

                        rows = conn.execute(f"""
                            SELECT c.customer_code, c.customer_name, u.full_name AS rep
                            FROM customers c
                            LEFT JOIN users u ON c.user_id = u.id
                            WHERE {' AND '.join(where)}
                            ORDER BY c.customer_name
                        """, params).fetchall()

                    if rows:
                        st.success(f"Found {len(rows)} customers — saving segment…")
                        codes = [r['customer_code'] for r in rows]
                        db.crm_save_segment(seg_name.strip(), seg_desc or None, user['id'], codes)
                        db.log_audit(user['id'], user['full_name'], "create", "segment",
                                     entity_label=seg_name.strip(),
                                     details=f"{len(codes)} customers")
                        st.rerun()
                    else:
                        st.warning("No customers matched these filters.")

    st.markdown("---")

    if not segments:
        st.info("No segments yet. Create one above.")
        return

    # ── Pre-fetch all segment members in one batch (avoids N+1 queries)
    _seg_members_cache = {}
    for seg in segments:
        _seg_members_cache[seg['id']] = db.crm_get_segment_members(seg['id'])

    # ── Segment cards
    for seg in segments:
        with st.expander(f"**{seg['name']}** — {seg['member_count']} customers"):
            if seg['description']:
                st.caption(seg['description'])
            st.caption(f"Created by {seg['created_by_name'] or '—'} on {_fmt_date(seg['created_at'])}")

            members = _seg_members_cache.get(seg['id'], [])
            if members:
                df = pd.DataFrame([dict(r) for r in members])
                df['ytd_2026']   = pd.to_numeric(df['ytd_2026'],   errors='coerce').fillna(0)
                df['total_2025'] = pd.to_numeric(df['total_2025'], errors='coerce').fillna(0)
                st.dataframe(
                    df[['customer_name','rep_name','addr_town','last_order','ytd_2026','total_2025']].rename(
                        columns={'customer_name':'Customer','rep_name':'Rep',
                                 'addr_town':'Town','last_order':'Last Order',
                                 'ytd_2026':'2026 YTD £','total_2025':'2025 £'}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "2026 YTD £": st.column_config.NumberColumn("2026 YTD £", format="£%.0f"),
                        "2025 £":     st.column_config.NumberColumn("2025 £",     format="£%.0f"),
                    }
                )

                # Bulk actions
                ba1, ba2, ba3 = st.columns(3)
                with ba1:
                    if st.button(f"📝 Add Note to All", key=f"bulk_note_{seg['id']}"):
                        st.session_state[f"bulk_note_open_{seg['id']}"] = True
                with ba3:
                    with st.popover("🗑 Delete Segment", key=f"del_seg_{seg['id']}"):
                        st.caption("Are you sure?")
                        if st.button("Yes, delete", key=f"confirm_del_seg_{seg['id']}", type="primary"):
                            db.crm_delete_segment(seg['id'])
                            db.log_audit(user['id'], user['full_name'], "delete", "segment",
                                         entity_id=seg['id'], entity_label=seg['name'])
                            st.rerun()

                # Bulk note form
                if st.session_state.get(f"bulk_note_open_{seg['id']}"):
                    with st.form(f"bulk_note_form_{seg['id']}"):
                        bn_type = st.selectbox("Type", db.NOTE_TYPES)
                        bn_text = st.text_area("Note to add to all customers in this segment *", height=80)
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.form_submit_button("💾 Add Note to All"):
                                if bn_text.strip():
                                    count = 0
                                    for code in [r['customer_code'] for r in members]:
                                        db.crm_add_note(code, user['id'], bn_text.strip(), bn_type)
                                        count += 1
                                    st.success(f"Note added to {count} customers!")
                                    st.session_state.pop(f"bulk_note_open_{seg['id']}", None)
                                    st.rerun()
                                else:
                                    st.warning("Please enter a note.")
                        with bc2:
                            if st.form_submit_button("Cancel"):
                                st.session_state.pop(f"bulk_note_open_{seg['id']}", None)
                                st.rerun()

# ── Tab 6: Prospects ──────────────────────────────────────────────────────────

PROSPECT_STATUSES = ["new", "contacted", "interested", "not interested", "converted", "dead"]
STATUS_COLOURS = {
    "new":           "#3498db",
    "contacted":     "#f39c12",
    "interested":    "#27ae60",
    "not interested":"#888888",
    "converted":     "#8e44ad",
    "dead":          "#e74c3c",
}

def tab_prospects(user):
    st.markdown("### 🎯 Prospects")
    st.caption("People from ActiveCampaign who aren't yet linked to an existing customer account.")

    # ── Summary metrics
    counts = db.crm_get_prospect_counts_by_status()
    total  = sum(r['cnt'] for r in counts)
    cols   = st.columns(min(len(counts) + 1, 6))
    with cols[0]:
        _card("Total Prospects", f"{total:,}", "#1a1a2e")
    for i, r in enumerate(counts[:5], 1):
        colour = STATUS_COLOURS.get(r['status'], "#888")
        with cols[i]:
            _card(r['status'].title(), f"{r['cnt']:,}", colour)

    st.markdown("---")

    # ── Filters
    sm_areas, regions, statuses = db.crm_get_prospect_filters()

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    with f1:
        search = st.text_input("🔍 Search", placeholder="Name, company, email…", key="pros_search")
    with f2:
        sm_sel = st.selectbox("SM Area", ["All"] + sm_areas, key="pros_sm")
    with f3:
        reg_sel = st.selectbox("Region", ["All"] + regions, key="pros_reg")
    with f4:
        stat_sel = st.selectbox("Status", ["All"] + PROSPECT_STATUSES, key="pros_stat")

    prospects = db.crm_get_prospects(
        search=search or None,
        sm_area=sm_sel if sm_sel != "All" else None,
        region=reg_sel if reg_sel != "All" else None,
        status=stat_sel if stat_sel != "All" else None,
        limit=300
    )

    st.markdown(f"**{len(prospects)} prospect{'s' if len(prospects) != 1 else ''} shown**")

    if not prospects:
        st.info("No prospects match these filters.")
        return

    # ── Table view (collapsed detail on click)
    for p in prospects:
        status_colour = STATUS_COLOURS.get(p['status'], "#888")
        with st.expander(
            f"**{p['contact_name']}** — {p['company_name'] or 'Unknown Company'}  ·  {p['email']}"
        ):
            row1, row2 = st.columns([3, 2])
            with row1:
                st.markdown(f"""
                | | |
                |---|---|
                | **Email** | {p['email']} |
                | **Company** | {p['company_name'] or '—'} |
                | **Job Title** | {p['job_title'] or '—'} |
                | **SM Area** | {p['sm_area'] or '—'} |
                | **Region** | {p['region'] or '—'} |
                | **Postcode** | {p['post_code'] or '—'} |
                | **Type** | {p['customer_type'] or '—'} |
                | **Source** | {p['source'] or '—'} |
                | **Added** | {_fmt_date(p['created_at'])} |
                """)
                if p['tags']:
                    # Show AC tags as pills
                    tag_list = [t.strip() for t in p['tags'].split(',') if t.strip()][:8]
                    pills = " ".join([
                        f'<span style="background:#eee;border-radius:10px;'
                        f'padding:2px 8px;font-size:11px;margin:2px;display:inline-block;">{t}</span>'
                        for t in tag_list
                    ])
                    st.markdown(f"**Tags:** {pills}", unsafe_allow_html=True)

            with row2:
                # Status update
                current_idx = PROSPECT_STATUSES.index(p['status']) if p['status'] in PROSPECT_STATUSES else 0
                new_status = st.selectbox("Status", PROSPECT_STATUSES,
                                          index=current_idx, key=f"ps_{p['id']}")
                if new_status != p['status']:
                    db.crm_update_prospect_status(p['id'], new_status)
                    st.rerun()

                # Notes
                new_notes = st.text_area("Notes", value=p['notes'] or "",
                                         height=80, key=f"pn_{p['id']}")
                if st.button("💾 Save Notes", key=f"psn_{p['id']}"):
                    db.crm_update_prospect_notes(p['id'], new_notes.strip() or None)
                    st.success("Saved!")

                # Convert to customer contact
                st.markdown("**Convert to Customer Contact**")
                with db.get_conn() as conn:
                    custs = conn.execute(
                        "SELECT customer_code, customer_name FROM customers ORDER BY customer_name"
                    ).fetchall()
                cust_opts = {"— select customer —": None} | {
                    f"{c['customer_name']} ({c['customer_code']})": c['customer_code']
                    for c in custs
                }
                link_sel = st.selectbox("Link to customer", list(cust_opts.keys()),
                                        key=f"plc_{p['id']}")
                if cust_opts.get(link_sel) and st.button("✅ Convert", key=f"pconv_{p['id']}"):
                    db.crm_convert_prospect_to_customer(p['id'], cust_opts[link_sel])
                    db.log_audit(user['id'], user['full_name'], "update", "prospect",
                                 entity_id=p['id'], entity_label=f"{p['contact_name']}",
                                 details=f"Converted to customer: {link_sel.split('(')[0].strip()}")
                    st.success(f"Moved to customer contacts for {link_sel.split('(')[0].strip()}!")
                    st.rerun()

                # Delete
                with st.popover("🗑 Remove Prospect", key=f"pdel_{p['id']}"):
                    st.caption("Are you sure?")
                    if st.button("Yes, delete", key=f"confirm_pdel_{p['id']}", type="primary"):
                        db.crm_delete_prospect(p['id'])
                        db.log_audit(user['id'], user['full_name'], "delete", "prospect",
                                     entity_id=p['id'], entity_label=f"{p['contact_name']} — {p['company_name'] or 'Unknown'}")
                        st.rerun()

    # ── CSV Export ──
    export_df = pd.DataFrame([{
        "Name":    p['contact_name'],
        "Company": p['company_name'] or "",
        "Email":   p['email'],
        "SM Area": p.get('sm_area') or "",
        "Region":  p.get('region') or "",
        "Status":  p.get('status') or "",
        "Tags":    p.get('tags') or "",
    } for p in prospects])
    st.download_button(
        "📥 Export Prospects",
        data=export_df.to_csv(index=False),
        file_name="prospects.csv",
        mime="text/csv",
        key="dl_prospects",
    )

    # ── Bulk export to email campaign
    st.markdown("---")
    st.markdown("#### 📧 Use Prospects in an Email Campaign")
    st.info(
        "To email these prospects, go to **Email Campaigns → Campaigns**, create a new campaign "
        "and it will pull from your CRM segments. You can also create a segment in the Segments tab "
        "using the prospect list as a basis once they're converted to customers."
    )


# ── Main entry point ─────────────────────────────────────────────────────────

def render_page(user):
    st.title("📋 CRM")

    total_prospects = db.crm_get_prospect_count()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔍 Customer 360",
        "👥 Contacts",
        "📝 Notes & Interactions",
        "✅ Tasks",
        "🏷️ Segments",
        f"🎯 Prospects ({total_prospects:,})",
    ])

    with tab1: tab_customer_360(user)
    with tab2: tab_contacts(user)
    with tab3: tab_notes(user)
    with tab4: tab_tasks(user)
    with tab5: tab_segments(user)
    with tab6: tab_prospects(user)
