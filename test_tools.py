import streamlit as st
import pandas as pd
from datetime import date, datetime
import database as db
import alert_engine as ae

REASONS = [
    "New application",
    "Competitor replacement",
    "New customer",
    "Distribution partner trial",
    "Existing customer, new component",
    "Other",
]

APP_TYPES = ["Turning (IsoTurn)", "Drilling", "Milling"]

STATUS_LABELS = {
    "submitted":   ("Awaiting Approval", "#3498db"),
    "approved":    ("Approved",          "#27ae60"),
    "rejected":    ("Rejected",          "#c0392b"),
    "despatched":  ("Despatched",        "#8e44ad"),
    "in_progress": ("In Progress",       "#e67e22"),
    "completed":   ("Completed",         "#27ae60"),
    "closed":      ("Closed",            "#7f8c8d"),
}

TEST_STATUSES = [
    "Still in progress",
    "Waiting for material",
    "Failed",
    "Successful",
]

def status_badge(status):
    label, colour = STATUS_LABELS.get(status, (status, "#888"))
    return f'<span style="background:{colour};color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold">{label}</span>'

def urgency_badge(days_since_despatch):
    if days_since_despatch is None: return ""
    if days_since_despatch > 45: return "🔴"
    if days_since_despatch > 21: return "🟠"
    if days_since_despatch > 7:  return "🟡"
    return "🟢"

def fmt_date(d):
    if not d: return "—"
    try: return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError): return d

def nav(page, **kwargs):
    st.session_state["page"] = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

# ── Request form ────────────────────────────────────────────────────────────────

def page_new_request():
    st.markdown('<div class="section-header">New Test Tool Request</div>', unsafe_allow_html=True)

    if st.button("← Back"):
        for k in list(st.session_state.keys()):
            if k.startswith("tt_"):
                del st.session_state[k]
        nav("test_tools")

    customers = db.get_all_customers()
    customer_options = {f"{c['customer_name']} ({c['customer_code']})": c for c in customers}
    cust_keys = ["— Select or type new —"] + list(customer_options.keys())

    # ── 1. Customer Details (outside form so order is correct) ──────────────────
    st.markdown("### Customer Details")
    col1, col2 = st.columns(2)
    col1.selectbox("Customer *", cust_keys, key="tt_cust_sel")
    col1.text_input("Or enter new customer name", key="tt_cust_new")
    col2.text_input("Contact 1 Name *", key="tt_contact1_name")
    col2.text_input("Contact 1 Email", key="tt_contact1_email")
    col1.text_input("Contact 2 Name (optional)", key="tt_contact2_name")
    col2.text_input("Contact 2 Email (optional)", key="tt_contact2_email")

    diff_delivery = st.checkbox("🚚 Different delivery / ship-to address", key="tt_diff_delivery")
    if diff_delivery:
        st.markdown("**Ship-To Details**")
        col1, col2 = st.columns(2)
        col1.text_input("Company / Site Name", key="tt_ship_company")
        col2.text_input("Contact Name", key="tt_ship_contact")
        col1.text_input("Email", key="tt_ship_email")
        col2.text_input("Phone", key="tt_ship_phone")
        st.text_area("Delivery Address *", key="tt_ship_address", placeholder="Street, City, Postcode")

    st.markdown("---")

    # ── 2. Tool Details (outside form so Add Another Part button works) ─────────
    if "tt_num_lines" not in st.session_state:
        st.session_state["tt_num_lines"] = 1

    st.markdown("### Tool Details")
    h1, h2, h3 = st.columns([4, 4, 1])
    h1.markdown("**Part Number**")
    h2.markdown("**Description**")
    h3.markdown("**Qty**")

    for i in range(st.session_state["tt_num_lines"]):
        c1, c2, c3 = st.columns([4, 4, 1])
        c1.text_input("Part Number", key=f"tt_item_{i}",
                      label_visibility="collapsed", placeholder="7-digit number", max_chars=7)
        c2.text_input("Description", key=f"tt_desc_{i}",
                      label_visibility="collapsed", placeholder="Description (optional)")
        c3.number_input("Qty", key=f"tt_qty_{i}",
                        min_value=1, value=1, label_visibility="collapsed")

    if st.session_state["tt_num_lines"] < 5:
        if st.button("➕ Add Another Part"):
            st.session_state["tt_num_lines"] += 1
            st.rerun()

    st.markdown("---")

    # ── 3. Request Details (inside form with submit button) ──────────────────────
    with st.form("test_request_form"):
        st.markdown("### Request Details")
        col1, col2 = st.columns(2)
        reason         = col1.selectbox("Reason for Test *", REASONS, help="Why are we sending test tooling to this customer?")
        reason_other   = col2.text_input("If 'Other', please specify")
        needed_by      = col1.date_input("Needed By Date *", min_value=date.today(), help="When does the customer need the tools by?")
        trial_run_date = col2.date_input("When will trial be run? (optional)", value=None, help="Scheduled date for the machining trial, if known")
        col1, col2 = st.columns(2)
        trial_end_date = col1.date_input("Expected trial completion date (optional)", value=None)
        notes = st.text_area("Additional Notes")
        submitted = st.form_submit_button("Submit Request", type="primary")

    if submitted:
        # Read customer fields from session state
        selected_cust  = st.session_state.get("tt_cust_sel", "— Select or type new —")
        new_cust_name  = st.session_state.get("tt_cust_new", "")
        contact_name   = st.session_state.get("tt_contact1_name", "")
        contact_email  = st.session_state.get("tt_contact1_email", "")
        contact2_name  = st.session_state.get("tt_contact2_name", "")
        contact2_email = st.session_state.get("tt_contact2_email", "")

        # Read item lines from session state
        items = []
        for i in range(st.session_state["tt_num_lines"]):
            code = st.session_state.get(f"tt_item_{i}", "")
            if isinstance(code, str): code = code.strip()
            if code:
                items.append({
                    "item_code": code,
                    "item_desc": st.session_state.get(f"tt_desc_{i}", "") or "",
                    "quantity":  st.session_state.get(f"tt_qty_{i}", 1) or 1,
                })

        # Resolve customer
        cust_name, cust_code = "", ""
        if selected_cust != "— Select or type new —" and selected_cust in customer_options:
            c = customer_options[selected_cust]
            cust_code = c["customer_code"]
            cust_name = c["customer_name"]
        if new_cust_name.strip():
            cust_name = new_cust_name.strip()

        # Validate
        if not cust_name:
            st.error("Please select or enter a customer name.")
            return
        if not contact_name.strip():
            st.error("Contact 1 Name is required.")
            return
        if not items:
            st.error("Please enter at least one Part Number.")
            return
        invalid = [it["item_code"] for it in items if not it["item_code"].isdigit() or len(it["item_code"]) != 7]
        if invalid:
            st.error(f"Part numbers must be exactly 7 digits (numbers only). Please check: {', '.join(invalid)}")
            return

        # Check for duplicate test requests
        existing_requests = db.get_all_test_requests()
        dupe_items = []
        for item in items:
            dupe_request = any(
                r['customer_name'].lower() == cust_name.strip().lower()
                and r['item_code'].lower() == item['item_code'].strip().lower()
                and r['status'] in ('submitted', 'approved', 'despatched')
                for r in existing_requests
            )
            if dupe_request:
                dupe_items.append(item['item_code'])
        if dupe_items:
            st.warning(f"⚠️ An active test request already exists for item(s) {', '.join(dupe_items)} at this customer. Check existing requests before creating a duplicate.")
            return

        # Create ONE request with all items as JSON
        admin_email = db.get_setting("email_from") or "Rob.Werhun@tungaloyuk.co.uk"
        rep = db.get_user_by_id(st.session_state["user_id"])
        rep_name = rep["full_name"] if rep else "Unknown"

        diff_delivery = st.session_state.get("tt_diff_delivery", False)
        first_item = items[0]
        data = {
            "customer_code":         cust_code,
            "customer_name":         cust_name,
            "contact_name":          contact_name.strip(),
            "contact_email":         contact_email.strip() or None,
            "contact2_name":         contact2_name.strip() or None,
            "contact2_email":        contact2_email.strip() or None,
            "ship_to_company":       st.session_state.get("tt_ship_company", "").strip() or None if diff_delivery else None,
            "ship_to_address":       st.session_state.get("tt_ship_address", "").strip() or None if diff_delivery else None,
            "ship_to_contact":       st.session_state.get("tt_ship_contact", "").strip() or None if diff_delivery else None,
            "ship_to_email":         st.session_state.get("tt_ship_email", "").strip() or None if diff_delivery else None,
            "ship_to_phone":         st.session_state.get("tt_ship_phone", "").strip() or None if diff_delivery else None,
            "item_code":             first_item["item_code"],
            "item_desc":             first_item["item_desc"] or None,
            "quantity":              first_item["quantity"],
            "items":                 json.dumps(items),
            "reason":                reason,
            "reason_other":          reason_other.strip() or None,
            "needed_by_date":        needed_by.strftime("%Y-%m-%d"),
            "trial_run_date":        trial_run_date.strftime("%Y-%m-%d") if trial_run_date else None,
            "trial_completion_date": trial_end_date.strftime("%Y-%m-%d") if trial_end_date else None,
            "notes":                 notes.strip() or None,
            "requested_by":          st.session_state["user_id"],
            "sm_name":               "",
            "status":                "submitted",
        }
        req_id = db.create_test_request(data)
        db.log_test_update(req_id, st.session_state["user_id"], "created", None, "submitted", "Request submitted")
        db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "create", "test_request",
                     entity_id=req_id, entity_label=f"{cust_name} — {len(items)} items",
                     details=f"Reason: {reason}, Items: {', '.join(i['item_code'] for i in items)}")
        req_ids = [req_id]

        # Email approvers — list all items in one email
        items_html = "".join(
            f"<tr><td style='padding:4px 8px'>{it['item_code']}</td>"
            f"<td style='padding:4px 8px'>{it['item_desc'] or '—'}</td>"
            f"<td style='padding:4px 8px'>{it['quantity']}</td></tr>"
            for it in items
        )
        subject = f"Test Tool Request FOR APPROVAL — {cust_name} ({len(items)} items)"
        app_url = "https://tungsalesnav.streamlit.app"
        body = f"""<h2>New Test Tool Request — Awaiting Your Approval</h2>
        <p><b>Requester:</b> {rep_name}</p>
        <p><b>Customer:</b> {cust_name}</p>
        <p><b>Contact:</b> {contact_name.strip()}</p>
        <p><b>Reason:</b> {reason}{(' — ' + reason_other.strip()) if reason_other.strip() else ''}</p>
        <p><b>Needed By:</b> {needed_by.strftime('%d %b %Y')}</p>
        <table border="1" cellpadding="4" style="border-collapse:collapse;font-size:14px">
          <thead><tr style="background:#f0f0f0">
            <th>Part Number</th><th>Description</th><th>Qty</th>
          </tr></thead>
          <tbody>{items_html}</tbody>
        </table>
        <p style="margin-top:20px"><a href="{app_url}" style="background:#d32f2f;color:white;padding:10px 20px;text-decoration:none;border-radius:4px;font-weight:bold">👉 Review Request in Sales Navigator</a></p>
        <p style="font-size:12px;color:#666">Request IDs: {', '.join(f'#{r}' for r in req_ids)}</p>"""
        recipients = []
        admins = db.get_all_users()
        for user in admins:
            if user["role"] == "admin" and user.get("email"):
                recipients.append(user["email"])
        if rep and rep.get("regional_manager_id"):
            mgr = db.get_user_by_id(rep["regional_manager_id"])
            if mgr and mgr["email"] not in recipients:
                recipients.append(mgr["email"])
        if recipients:
            ae.send_email(recipients, subject, body)

        # Clear all tt_ state
        for k in list(st.session_state.keys()):
            if k.startswith("tt_"):
                del st.session_state[k]

        st.success(f"{len(items)} request(s) submitted (#{', #'.join(str(r) for r in req_ids)}). Approval email sent.")
        st.balloons()

# ── List view ───────────────────────────────────────────────────────────────────

def page_test_tools_list():
    st.markdown('<div class="section-header">Test Tool Requests</div>', unsafe_allow_html=True)
    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    filter_status = col1.selectbox("Status filter", ["All","Awaiting Approval","Approved","Despatched","In Progress","Completed","Rejected","Closed"])
    if col3.button("➕ New Request", type="primary"):
        nav("test_tools_new")
    if col4.button("📊 Success Tracker"):
        nav("test_tools_dashboard")

    if role in ("admin", "marketing"):
        requests = db.get_all_test_requests()
    elif role == "regional_manager":
        requests = db.get_test_requests_for_team(user_id)
    else:
        requests = db.get_test_requests_for_user(user_id)

    status_filter_map = {
        "Awaiting Approval": "submitted",
        "Approved": "approved",
        "Despatched": "despatched",
        "In Progress": "in_progress",
        "Completed": "completed",
        "Rejected": "rejected",
        "Closed": "closed",
    }
    if filter_status != "All":
        filt = status_filter_map.get(filter_status, "")
        requests = [r for r in requests if r["status"] == filt]

    if not requests:
        st.info("No test tool requests match the current filter. Click '+ New Request' above to create one, or change the status filter to see other requests.")
        return

    # Header
    hcols = st.columns([1, 3, 2, 2, 2, 1, 1])
    for hc, h in zip(hcols, ["#", "Customer / Part", "Requester", "Date", "Status", "", ""]):
        hc.markdown(f"**{h}**")
    st.markdown("<hr style='margin:4px 0'/>", unsafe_allow_html=True)

    for r in requests:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 3, 2, 2, 2, 1, 1])
        c1.write(f"#{r['id']}")
        items_display = r['item_code'] + f" × {r['quantity']}"
        if r.get("items"):
            try:
                items_list = json.loads(r["items"])
                items_display = ", ".join(f"{i['item_code']} × {i['quantity']}" for i in items_list)
            except:
                pass
        c2.write(f"**{r['customer_name']}**\n{items_display}")
        c3.write(r["requester_name"])
        c4.write(fmt_date(r["created_at"]))
        c5.markdown(status_badge(r["status"]), unsafe_allow_html=True)

        if r["status"] == "despatched" and r["despatch_date"]:
            days = ae.days_since(r["despatch_date"])
            c6.write(urgency_badge(days))
        if c7.button("View", key=f"tt_view_{r['id']}"):
            nav("test_tools_detail", selected_test_request=r["id"])

# ── Detail view ─────────────────────────────────────────────────────────────────

def page_test_tools_detail():
    req_id = st.session_state.get("selected_test_request")
    if not req_id:
        nav("test_tools")
        return

    r = db.get_test_request(req_id)
    if not r:
        st.error("Request not found.")
        return

    if st.button("← Back to Test Tools"):
        nav("test_tools")

    st.markdown(f"## Test Tool Request #{r['id']}")
    st.markdown(status_badge(r["status"]), unsafe_allow_html=True)

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Customer", r["customer_name"])
    items_count = len(json.loads(r["items"])) if r.get("items") else 1
    col2.metric("Items", f"{items_count} part(s)")
    col3.metric("Requested By", r["requester_name"])
    col4.metric("Needed By", fmt_date(r["needed_by_date"]))

    st.markdown("---")

    # Items table
    st.markdown("### 📦 Items Requested")
    items_list = []
    if r.get("items"):
        try:
            items_list = json.loads(r["items"])
        except:
            items_list = [{"item_code": r["item_code"], "item_desc": r["item_desc"], "quantity": r["quantity"]}]
    else:
        items_list = [{"item_code": r["item_code"], "item_desc": r["item_desc"], "quantity": r["quantity"]}]

    items_df = pd.DataFrame(items_list)
    st.dataframe(items_df[["item_code", "item_desc", "quantity"]], use_container_width=True, hide_index=True)

    st.markdown("---")

    # Details
    with st.expander("📋 Full Request Details", expanded=True):
        col1, col2 = st.columns(2)
        col1.write(f"**Contact 1:** {r['contact_name']}" + (f" ({r['contact_email']})" if r.get("contact_email") else ""))
        if r.get("contact2_name"):
            col1.write(f"**Contact 2:** {r['contact2_name']}" + (f" ({r['contact2_email']})" if r.get("contact2_email") else ""))
        col1.write(f"**Reason:** {r['reason']}" + (f" — {r['reason_other']}" if r.get("reason_other") else ""))
        if r.get("trial_run_date"):
            col1.write(f"**Trial Run Date:** {fmt_date(r['trial_run_date'])}")
        if r.get("trial_completion_date"):
            col1.write(f"**Trial Completion:** {fmt_date(r['trial_completion_date'])}")

        if r.get("ship_to_address"):
            col2.markdown("**🚚 Ship-To Address**")
            if r.get("ship_to_company"):
                col2.write(r["ship_to_company"])
            col2.write(r["ship_to_address"])
            if r.get("ship_to_contact"):
                col2.write(f"Contact: {r['ship_to_contact']}")
            if r.get("ship_to_email"):
                col2.write(f"Email: {r['ship_to_email']}")
            if r.get("ship_to_phone"):
                col2.write(f"Phone: {r['ship_to_phone']}")
        col1.write(f"**Application:** {r['application_type'] or '—'}")
        col1.write(f"**Material:** {r['material_being_cut'] or '—'}")
        col1.write(f"**Hardness:** {r['hardness'] or '—'}")

        col2.write(f"**Machine:** {r['machine_type'] or '—'}")
        col2.write(f"**Competitor Tool:** {r['competitor_tool'] or '—'}")
        col2.write(f"**Cutting Speed:** {r['cutting_speed'] or '—'}")
        col2.write(f"**Feed Rate:** {r['feed_rate'] or '—'}")
        col2.write(f"**Depth of Cut:** {r['depth_of_cut'] or '—'}")
        if r["width_of_cut"]:
            col2.write(f"**Width of Cut:** {r['width_of_cut']}")
        col2.write(f"**Coolant:** {r['coolant'] or '—'}")
        if r["notes"]:
            st.write(f"**Notes:** {r['notes']}")

    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    # ── Approval & Despatch (combined) ──
    if r["status"] == "submitted" and role in ("admin", "regional_manager", "marketing"):
        st.markdown("### ✅ Approval & Despatch")
        with st.form("approval_despatch_form"):
            col1, col2 = st.columns(2)
            order_no      = col1.text_input("Order / Shipping Number *", help="Internal order number or courier tracking reference")
            delivery_date = col2.date_input("Expected Delivery Date *", help="When the tools are expected to arrive at the customer")

            col1, col2, col3 = st.columns([2, 1, 1])
            approve_submit = col1.form_submit_button("✅ Approve & Send", type="primary")
            reject_submit = col2.form_submit_button("❌ Reject")

            reject_reason = col3.text_input("Rejection reason (if rejecting)", label_visibility="collapsed")

        if approve_submit and order_no.strip():
            db.update_test_request(r["id"], {
                "status": "despatched",
                "approved_by": user_id,
                "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "despatch_order_number": order_no.strip(),
                "despatch_date": date.today().strftime("%Y-%m-%d"),
                "expected_delivery_date": delivery_date.strftime("%Y-%m-%d"),
                "despatched_by": user_id,
            })
            db.log_test_update(r["id"], user_id, "status_change", "submitted", "despatched", f"Approved & despatched. Order: {order_no.strip()}")
            db.log_audit(user_id, st.session_state["full_name"], "update", "test_request",
                         entity_id=r["id"], entity_label=f"{r['customer_name']} — {r['item_code']}",
                         details=f"Approved & despatched. Order: {order_no.strip()}, Expected delivery: {delivery_date.strftime('%d %b %Y')}")
            rep = db.get_user_by_id(r["requested_by"])
            ae.send_email([rep["email"]], f"Test Tool #{r['id']} APPROVED — {r['item_code']}",
                         f"<h2>Your test tool request has been approved</h2>"
                         f"<p><b>{r['customer_name']}</b> — {r['item_code']}</p>"
                         f"<p>We are sending the tools now.</p>"
                         f"<p><b>Expected delivery:</b> {delivery_date.strftime('%d %b %Y')}</p>"
                         f"<p><b>Order number:</b> {order_no.strip()}</p>")
            st.success("Approved and despatched. Rep notified by email. 7-day follow-up clock started.")
            st.rerun()

        elif reject_submit:
            db.update_test_request(r["id"], {"status": "rejected", "approved_by": user_id, "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "rejection_reason": reject_reason or "No reason given"})
            db.log_test_update(r["id"], user_id, "status_change", "submitted", "rejected", reject_reason or "Rejected")
            db.log_audit(user_id, st.session_state["full_name"], "update", "test_request",
                         entity_id=r["id"], entity_label=f"{r['customer_name']} — {r['item_code']}",
                         details=f"Rejected: {reject_reason or 'No reason given'}")
            rep = db.get_user_by_id(r["requested_by"])
            ae.send_email([rep["email"]], f"Test Tool #{r['id']} REJECTED — {r['item_code']}",
                         f"<h2>Your test tool request has been rejected</h2>"
                         f"<p><b>{r['customer_name']}</b> — {r['item_code']}</p>"
                         f"<p><b>Reason:</b> {reject_reason or 'Not specified'}</p>")
            st.success("Rejected. Rep notified by email.")
            st.rerun()

    # ── Test report section (rep) ──
    if r["status"] in ("despatched", "in_progress"):
        st.markdown("### 📝 Test Report / Update")

        with st.form("test_report_form"):
            col1, col2 = st.columns(2)
            went_ahead  = col1.selectbox("Did the test go ahead?", ["", "Yes", "No", "Partially"])
            test_status = col2.selectbox("Current Status", [""] + TEST_STATUSES)
            performance = col1.selectbox("Performance vs Current Tool", ["", "Better", "Same", "Worse"])
            tool_life   = col2.text_input("Tool Life Achieved", placeholder="e.g. 250 parts")
            surface     = col1.text_input("Surface Finish", placeholder="e.g. Ra 0.8")
            parts_made  = col2.text_input("Parts Produced")

            cust_comments = st.text_area("Customer Comments")
            outcome       = st.selectbox("Outcome", ["", "Converted to order", "Still evaluating", "Rejected"])
            col1, col2 = st.columns(2)
            order_value = col1.number_input("Estimated Order Value (£)", min_value=0.0, value=0.0, step=100.0, help="Anticipated annual value if the customer converts to an order")
            rej_reason  = col2.text_input("If rejected — reason", help="Why did the customer decide not to proceed?")
            report_notes = st.text_area("Test Report Notes")

            st.markdown("### Application Details")
            col1, col2, col3 = st.columns(3)
            app_type        = col1.selectbox("Application Type", [""] + APP_TYPES, help="IsoTurn = ISO turning applications")
            material        = col2.text_input("Material Being Cut", help="e.g. Stainless 316, Inconel 718, Ti-6Al-4V")
            hardness        = col3.text_input("Hardness (e.g. HRC 45)", help="Rockwell C (HRC), Brinell (HB), or Vickers (HV)")
            col1, col2, col3 = st.columns(3)
            machine_type    = col1.text_input("Machine Type")
            competitor_tool = col2.text_input("Competitor Tool Used", help="Brand and model of the tool being replaced, if known")
            workpiece_mat   = col3.text_input("Workpiece Material", help="ISO material group or specific alloy, e.g. P20 steel, S-class superalloy")

            st.markdown("### Cutting Parameters")
            col1, col2, col3, col4 = st.columns(4)
            cutting_speed = col1.text_input("Cutting Speed (m/min)", help="Vc — surface speed in metres per minute")
            feed_rate     = col2.text_input("Feed Rate (mm/rev)", help="fn — feed per revolution (turning) or fz per tooth (milling)")
            depth_of_cut  = col3.text_input("Depth of Cut (mm)", help="ap — axial depth of cut")
            width_of_cut  = col4.text_input("Width of Cut (mm)", help="ae — radial width of cut (milling only)")
            coolant       = st.selectbox("Coolant", ["", "Wet", "Dry", "MQL", "Through-tool"], help="MQL = Minimum Quantity Lubrication")

            report_submit = st.form_submit_button("Save Test Report", type="primary")

        if report_submit:
            updates = {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
            if went_ahead: updates["test_went_ahead"] = went_ahead
            if test_status: updates["test_status"] = test_status
            if performance: updates["performance_vs_current"] = performance
            if tool_life: updates["tool_life_achieved"] = tool_life
            if surface: updates["surface_finish"] = surface
            if parts_made: updates["parts_produced"] = parts_made
            if cust_comments: updates["customer_comments"] = cust_comments
            if outcome: updates["outcome"] = outcome
            if order_value > 0: updates["estimated_order_value"] = order_value
            if rej_reason: updates["outcome_rejection_reason"] = rej_reason
            if report_notes: updates["test_report_notes"] = report_notes
            if app_type: updates["application_type"] = app_type
            if material: updates["material_being_cut"] = material
            if hardness: updates["hardness"] = hardness
            if machine_type: updates["machine_type"] = machine_type
            if competitor_tool: updates["competitor_tool"] = competitor_tool
            if workpiece_mat: updates["workpiece_material"] = workpiece_mat
            if cutting_speed: updates["cutting_speed"] = cutting_speed
            if feed_rate: updates["feed_rate"] = feed_rate
            if depth_of_cut: updates["depth_of_cut"] = depth_of_cut
            if width_of_cut: updates["width_of_cut"] = width_of_cut
            if coolant: updates["coolant"] = coolant

            if r["status"] == "despatched":
                updates["status"] = "in_progress"

            if outcome in ("Converted to order", "Rejected"):
                updates["status"] = "completed"
                updates["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

            db.update_test_request(r["id"], updates)
            db.log_test_update(r["id"], st.session_state["user_id"], "report_update", r["status"],
                              updates.get("status", r["status"]),
                              f"Test report updated. Status: {test_status or 'N/A'}")
            db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "update", "test_request",
                         entity_id=r["id"], entity_label=f"{r['customer_name']} — {r['item_code']}",
                         details=f"Test report: {outcome or test_status or 'updated'}")
            st.success("Test report saved.")
            st.rerun()

    # ── Despatch info ──
    if r["despatch_date"]:
        with st.expander("📦 Despatch Details"):
            st.write(f"**Order Number:** {r['despatch_order_number']}")
            st.write(f"**Despatched:** {fmt_date(r['despatch_date'])}")
            st.write(f"**Expected Delivery:** {fmt_date(r['expected_delivery_date'])}")
            days = ae.days_since(r["despatch_date"])
            st.write(f"**Days Since Despatch:** {days}")

    # ── Test report results ──
    if r["test_went_ahead"]:
        with st.expander("📊 Test Results", expanded=True):
            col1, col2 = st.columns(2)
            col1.write(f"**Test Went Ahead:** {r['test_went_ahead']}")
            col1.write(f"**Status:** {r['test_status'] or '—'}")
            col1.write(f"**Performance:** {r['performance_vs_current'] or '—'}")
            col1.write(f"**Tool Life:** {r['tool_life_achieved'] or '—'}")
            col2.write(f"**Surface Finish:** {r['surface_finish'] or '—'}")
            col2.write(f"**Parts Produced:** {r['parts_produced'] or '—'}")
            col2.write(f"**Outcome:** {r['outcome'] or '—'}")
            if r["estimated_order_value"]:
                col2.write(f"**Est. Order Value:** £{r['estimated_order_value']:,.0f}")
            if r["customer_comments"]:
                st.write(f"**Customer Comments:** {r['customer_comments']}")
            if r["test_report_notes"]:
                st.write(f"**Notes:** {r['test_report_notes']}")

    # ── Activity log ──
    with st.expander("📜 Activity Log"):
        updates = db.get_test_updates(r["id"])
        for u in updates:
            st.markdown(f"**{fmt_date(u['created_at'])}** — {u['full_name']} — "
                        f"{u['update_type'].replace('_',' ').title()}"
                        + (f": {u['notes']}" if u["notes"] else ""))

# ── Success Tracker Dashboard ───────────────────────────────────────────────────

def page_test_tools_dashboard():
    import plotly.graph_objects as go

    st.markdown('<div class="section-header">Test Tool Success Tracker</div>', unsafe_allow_html=True)

    if st.button("← Back to Test Tools"):
        nav("test_tools")

    all_requests = db.get_all_test_requests()
    if not all_requests:
        st.info("No test tool data to display yet. Once test tool requests are submitted and completed, conversion rates and rep performance will appear here.")
        return

    total = len(all_requests)
    completed = [r for r in all_requests if r["status"] in ("completed", "closed")]
    converted = [r for r in completed if r["outcome"] == "Converted to order"]
    failed    = [r for r in completed if r["outcome"] == "Rejected"]
    in_progress = [r for r in all_requests if r["status"] in ("despatched", "in_progress")]
    pending   = [r for r in all_requests if r["status"] == "submitted"]
    total_revenue = sum(r["estimated_order_value"] or 0 for r in converted)

    # Summary metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Requests", total)
    c2.metric("Completed", len(completed))
    c3.metric("Converted", len(converted))
    c4.metric("Conversion Rate", f"{len(converted)/max(len(completed),1)*100:.0f}%")
    c5.metric("Revenue from Tests", f"£{total_revenue:,.0f}")

    st.markdown("---")

    # Breakdown by rep
    st.markdown("### By Rep")
    rep_stats = {}
    for r in all_requests:
        name = r["requester_name"]
        rep_stats.setdefault(name, {"total":0, "completed":0, "converted":0, "revenue":0, "in_progress":0})
        rep_stats[name]["total"] += 1
        if r["status"] in ("completed","closed"):
            rep_stats[name]["completed"] += 1
            if r["outcome"] == "Converted to order":
                rep_stats[name]["converted"] += 1
                rep_stats[name]["revenue"] += r["estimated_order_value"] or 0
        if r["status"] in ("despatched","in_progress"):
            rep_stats[name]["in_progress"] += 1

    rows = []
    for name, s in sorted(rep_stats.items(), key=lambda x: x[1]["converted"], reverse=True):
        rate = f"{s['converted']/max(s['completed'],1)*100:.0f}%" if s["completed"] else "—"
        rows.append({
            "Rep": name,
            "Total": s["total"],
            "Completed": s["completed"],
            "Converted": s["converted"],
            "Rate": rate,
            "Revenue": f"£{s['revenue']:,.0f}",
            "In Progress": s["in_progress"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Chart
    col1, col2 = st.columns(2)
    with col1:
        labels = ["Converted", "Rejected", "In Progress", "Pending"]
        values = [len(converted), len(failed), len(in_progress), len(pending)]
        colours = ["#27ae60", "#c0392b", "#e67e22", "#3498db"]
        fig = go.Figure(go.Pie(labels=labels, values=values, marker=dict(colors=colours), hole=0.4))
        fig.update_layout(title="Test Tool Outcomes", height=300, margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if converted:
            st.markdown("### Top Conversions")
            for r in sorted(converted, key=lambda x: x["estimated_order_value"] or 0, reverse=True)[:5]:
                val = f"£{r['estimated_order_value']:,.0f}" if r["estimated_order_value"] else "—"
                st.write(f"**{r['customer_name']}** — {r['item_code']} — {val}")

# ── Router ──────────────────────────────────────────────────────────────────────

def render_page():
    page = st.session_state.get("page", "test_tools")
    if page == "test_tools_new":
        page_new_request()
    elif page == "test_tools_detail":
        page_test_tools_detail()
    elif page == "test_tools_dashboard":
        page_test_tools_dashboard()
    else:
        page_test_tools_list()
