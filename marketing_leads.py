import streamlit as st
import pandas as pd
from datetime import date, datetime
import database as db
import alert_engine as ae

ACTIVITY_TYPES = [
    "Browsing product pages",
    "Basket abandoned",
    "Quote request",
    "Downloaded brochure",
    "Webshop account created",
    "Other",
]

URGENCY_LEVELS = ["Low", "Medium", "High"]

ACTION_OPTIONS = ["Called", "Visited", "Emailed", "No action needed"]

STATUS_COLOURS = {
    "pending":  ("#3498db", "Pending"),
    "actioned": ("#27ae60", "Actioned"),
    "closed":   ("#7f8c8d", "Closed"),
}

def status_badge(status):
    colour, label = STATUS_COLOURS.get(status, ("#888", status))
    return f'<span style="background:{colour};color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold">{label}</span>'

def urgency_badge(level):
    colours = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
    return colours.get(level, "⚪")

def fmt_date(d):
    if not d: return "—"
    try: return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError): return d

def nav(page, **kwargs):
    st.session_state["page"] = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

# ── Submit lead form ────────────────────────────────────────────────────────────

def page_new_lead():
    st.markdown('<div class="section-header">Submit Marketing Lead</div>', unsafe_allow_html=True)

    if st.button("← Back"):
        nav("marketing_leads")

    customers = db.get_all_customers()
    customer_options = {f"{c['customer_name']} ({c['customer_code']})": c for c in customers}
    all_users = db.get_reps_and_managers()

    with st.form("lead_form"):
        st.markdown("### Customer Details")
        col1, col2 = st.columns(2)

        selected_cust = col1.selectbox("Customer *", ["— Select or type new —"] + list(customer_options.keys()))
        new_cust_name = col1.text_input("Or enter new customer/company name")
        contact_name  = col2.text_input("Contact Name *")
        contact_email = col2.text_input("Contact Email")

        st.markdown("### Activity Details")
        col1, col2 = st.columns(2)
        activity_type = col1.selectbox("Type of Activity *", ACTIVITY_TYPES, help="What did the customer do on the website or at the event?")
        urgency       = col2.selectbox("Urgency *", URGENCY_LEVELS, index=1, help="High = hot lead needing same-day follow-up, Low = informational only")
        products      = st.text_area("Product(s) Viewed / Items of Interest *",
                                     placeholder="e.g. TungSix TXN drill, AH8015 grade inserts, page: /products/milling/...",
                                     help="List specific product names, grades, or webshop pages the customer viewed")

        st.markdown("### Assignment")
        user_map = {u["id"]: u["full_name"] for u in all_users}
        assign_to = st.selectbox(
            "Assign to rep *",
            options=list(user_map.keys()),
            format_func=lambda uid: user_map.get(uid, str(uid))
        )

        notes = st.text_area("Notes", placeholder="Any context — where did this come from, what caught your attention?")

        submitted = st.form_submit_button("Submit Lead", type="primary")

    if submitted:
        cust_name = new_cust_name.strip() if new_cust_name.strip() else ""
        cust_code = ""
        if selected_cust != "— Select or type new —" and selected_cust in customer_options:
            c = customer_options[selected_cust]
            cust_code = c["customer_code"]
            cust_name = c["customer_name"]

        if not cust_name:
            st.error("Please select or enter a customer name.")
            return
        if not contact_name.strip():
            st.error("Contact Name is required.")
            return
        if not products.strip():
            st.error("Please describe the products viewed.")
            return

        # Check for duplicate leads
        existing_leads = db.get_all_marketing_leads()
        dupe_contact = any(
            l['contact_name'].lower() == contact_name.strip().lower()
            and l['customer_name'].lower() == cust_name.strip().lower()
            and l['status'] == 'pending'
            for l in existing_leads
        )
        if dupe_contact:
            st.warning("⚠️ A pending lead already exists for this contact at this customer. Please check existing leads before creating a duplicate.")
            return

        data = {
            "customer_code": cust_code,
            "customer_name": cust_name,
            "contact_name": contact_name.strip(),
            "contact_email": contact_email.strip() or None,
            "products_viewed": products.strip(),
            "activity_type": activity_type,
            "urgency": urgency,
            "notes": notes.strip() or None,
            "submitted_by": st.session_state["user_id"],
            "assigned_to": assign_to,
            "status": "pending",
        }

        lead_id = db.create_marketing_lead(data)
        db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "create", "marketing_lead",
                     entity_id=lead_id, entity_label=f"{cust_name} — {contact_name.strip()}",
                     details=f"Activity: {activity_type}, Urgency: {urgency}")

        # Email the assigned rep
        rep = db.get_user_by_id(assign_to)
        submitter = db.get_user_by_id(st.session_state["user_id"])
        urg_emoji = urgency_badge(urgency)
        subject = f"{urg_emoji} Marketing Lead: {cust_name} — {activity_type}"
        body = f"""
        <div style="font-family:Arial;background:#1a1a2e;padding:20px">
            <h2 style="color:#fff;margin:0">Tungaloy-NTK Sales Navigator</h2>
            <p style="color:#c0392b;margin:4px 0 0">New Marketing Lead</p>
        </div>
        <div style="padding:20px;font-family:Arial">
            <p>Hi {rep['full_name']},</p>
            <p>A new marketing lead has been submitted for your attention:</p>
            <table style="border-collapse:collapse;font-size:14px">
                <tr><td style="padding:6px;font-weight:bold">Customer:</td><td style="padding:6px">{cust_name}</td></tr>
                <tr><td style="padding:6px;font-weight:bold">Contact:</td><td style="padding:6px">{contact_name.strip()}</td></tr>
                <tr><td style="padding:6px;font-weight:bold">Activity:</td><td style="padding:6px">{activity_type}</td></tr>
                <tr><td style="padding:6px;font-weight:bold">Products:</td><td style="padding:6px">{products.strip()}</td></tr>
                <tr><td style="padding:6px;font-weight:bold">Urgency:</td><td style="padding:6px">{urg_emoji} {urgency}</td></tr>
            </table>
            <p>Please follow up and log your action in the Sales Navigator.</p>
            <p style="font-size:12px;color:#888">Submitted by {submitter['full_name']}</p>
        </div>"""
        ae.send_email([rep["email"]], subject, body)

        st.success(f"Lead #{lead_id} submitted. {rep['full_name']} has been emailed.")
        st.balloons()

# ── List view ───────────────────────────────────────────────────────────────────

def page_leads_list():
    st.markdown('<div class="section-header">Marketing Leads</div>', unsafe_allow_html=True)
    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    col1, col2, col3 = st.columns([2, 2, 1])
    filter_status = col1.selectbox("Status", ["All", "Pending", "Actioned", "Closed"])

    can_submit = role in ("admin", "marketing")
    if can_submit and col3.button("➕ Submit Lead", type="primary"):
        nav("marketing_leads_new")

    if role in ("admin", "marketing"):
        leads = db.get_all_marketing_leads()
    elif role == "regional_manager":
        # Show team's leads
        team = db.get_team_members(user_id)
        team_ids = [user_id] + [u["id"] for u in team]
        all_leads = db.get_all_marketing_leads()
        leads = [l for l in all_leads if l["assigned_to"] in team_ids]
    else:
        leads = db.get_marketing_leads_for_rep(user_id)

    if filter_status != "All":
        leads = [l for l in leads if l["status"] == filter_status.lower()]

    if not leads:
        if can_submit:
            st.info("No marketing leads match the current filter. Click 'Submit Lead' above to create one, or change the status filter to see other leads.")
        else:
            st.info("No marketing leads assigned to you right now. When marketing submits a lead for your territory, it will appear here.")
        return

    # Header
    hcols = st.columns([1, 3, 2, 2, 1, 1, 1])
    for hc, h in zip(hcols, ["#", "Customer / Activity", "Assigned To", "Date", "Urgency", "Status", ""]):
        hc.markdown(f"**{h}**")
    st.markdown("<hr style='margin:4px 0'/>", unsafe_allow_html=True)

    for l in leads:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 3, 2, 2, 1, 1, 1])
        c1.write(f"#{l['id']}")
        c2.write(f"**{l['customer_name']}**\n{l['activity_type']}")
        c3.write(l.get("rep_name") or "—")
        c4.write(fmt_date(l["created_at"]))
        c5.write(urgency_badge(l["urgency"]))
        c6.markdown(status_badge(l["status"]), unsafe_allow_html=True)
        if c7.button("View", key=f"ml_view_{l['id']}"):
            nav("marketing_leads_detail", selected_lead=l["id"])

# ── Detail view ─────────────────────────────────────────────────────────────────

def page_lead_detail():
    lead_id = st.session_state.get("selected_lead")
    if not lead_id:
        nav("marketing_leads")
        return

    l = db.get_marketing_lead(lead_id)
    if not l:
        st.error("Lead not found.")
        return

    if st.button("← Back to Marketing Leads"):
        nav("marketing_leads")

    st.markdown(f"## Marketing Lead #{l['id']}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Customer", l["customer_name"])
    col2.metric("Activity", l["activity_type"])
    col3.metric("Urgency", f"{urgency_badge(l['urgency'])} {l['urgency']}")
    col4.markdown(f"**Status**<br>{status_badge(l['status'])}", unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("📋 Full Details", expanded=True):
        col1, col2 = st.columns(2)
        col1.write(f"**Contact:** {l['contact_name']}")
        if l["contact_email"]:
            col1.write(f"**Email:** {l['contact_email']}")
        col1.write(f"**Submitted By:** {l['submitter_name']}")
        col1.write(f"**Submitted:** {fmt_date(l['created_at'])}")

        col2.write(f"**Assigned To:** {l.get('rep_name') or '—'}")
        col2.write(f"**Products Viewed:**")
        col2.write(l["products_viewed"])
        if l["notes"]:
            st.write(f"**Notes:** {l['notes']}")

    # Action section (for the assigned rep)
    if l["status"] == "pending":
        st.markdown("### ✅ Log Your Action")
        with st.form("action_form"):
            action = st.selectbox("Action Taken *", [""] + ACTION_OPTIONS)
            action_notes = st.text_area("Notes", placeholder="Brief summary of what happened…")
            action_submit = st.form_submit_button("Mark as Actioned", type="primary")

        if action_submit:
            if not action:
                st.error("Please select an action.")
            else:
                db.update_marketing_lead(l["id"], {
                    "status": "actioned",
                    "action_taken": action,
                    "action_notes": action_notes.strip() or None,
                    "actioned_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "update", "marketing_lead",
                             entity_id=l["id"], entity_label=f"{l['customer_name']}",
                             details=f"Actioned: {action}")
                # Notify submitter
                submitter = db.get_user_by_id(l["submitted_by"])
                rep = db.get_user_by_id(l["assigned_to"])
                ae.send_email(
                    [submitter["email"]],
                    f"Marketing Lead #{l['id']} — Actioned by {rep['full_name']}",
                    f"<p><b>{rep['full_name']}</b> has actioned the lead for <b>{l['customer_name']}</b>.</p>"
                    f"<p><b>Action:</b> {action}</p>"
                    f"<p><b>Notes:</b> {action_notes or 'None'}</p>"
                )
                st.success("Lead marked as actioned. Submitter notified.")
                st.rerun()

    # Show outcome if actioned
    if l["action_taken"]:
        with st.expander("✅ Action Taken", expanded=True):
            st.write(f"**Action:** {l['action_taken']}")
            st.write(f"**Date:** {fmt_date(l['actioned_at'])}")
            if l["action_notes"]:
                st.write(f"**Notes:** {l['action_notes']}")

    # Close button (admin/marketing)
    if l["status"] == "actioned" and st.session_state["role"] in ("admin", "marketing"):
        if st.button("Close this lead", key="close_lead"):
            db.update_marketing_lead(l["id"], {"status": "closed"})
            st.success("Lead closed.")
            st.rerun()

# ── Router ──────────────────────────────────────────────────────────────────────

def render_page():
    page = st.session_state.get("page", "marketing_leads")
    if page == "marketing_leads_new":
        page_new_lead()
    elif page == "marketing_leads_detail":
        page_lead_detail()
    else:
        page_leads_list()
