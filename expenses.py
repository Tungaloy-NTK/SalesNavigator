"""
expenses.py — Receipt capture, catalog, and expense management for Sales Navigator.

Rep view     : Photograph/upload receipts, categorise, submit.
Catalog view : Searchable receipt catalog — find any receipt by date, amount, rep, category.
Manager view : Review all team receipts, mark as Processed, add notes.

Email delivery  : Stub — activate by setting SMTP credentials in settings table.
Folder delivery : Stub — activate by setting EXPENSES_FOLDER path in settings table.
"""

import os
import uuid
import streamlit as st
from datetime import date, datetime, timedelta
import database as db

# ── Config ────────────────────────────────────────────────────────────────────
RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), "receipts")
os.makedirs(RECEIPTS_DIR, exist_ok=True)

# Ensure expenses table exists (safe to call every time — no-op if already present)
def _ensure_table():
    with db.get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                submitted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                expense_date     TEXT NOT NULL,
                amount           REAL NOT NULL,
                category         TEXT NOT NULL,
                notes            TEXT,
                receipt_filename TEXT,
                status           TEXT DEFAULT 'pending',
                reviewed_by      INTEGER,
                reviewed_at      TEXT,
                reviewer_notes   TEXT,
                vat_amount       REAL,
                account_code     TEXT,
                FOREIGN KEY (user_id)     REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        """)

_ensure_table()

# ── Categories from Tungaloy expenses template ───────────────────────────────
# Key = display label, value = account code
EXPENSE_CATEGORIES = {
    "TRAVEL":      "32011900",
    "CUST ENT":    "32012100",
    "PROM/MARK":   "32015008",
    "ADVERT":      "32015005",
    "GIVE AWAY":   "32015020",
    "EXHIBITION":  "32015004",
    "MOTOR EX":    "32012300",
    "POST":        "33014500",
    "FUEL":        "32012200",
    "PRINT/STAT":  "33014313",
    "COMP STAT":   "33014311",
    "FREIGHT":     "32015029",
}

CATEGORY_LABELS = list(EXPENSE_CATEGORIES.keys())

STATUS_COLOURS = {
    "pending":    "#e67e22",
    "reviewed":   "#2980b9",
    "processed":  "#27ae60",
    "rejected":   "#c0392b",
}

STATUS_LABELS = {
    "pending":   "Pending",
    "reviewed":  "Reviewed",
    "processed": "Processed",
    "rejected":  "Rejected",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_receipt_file(uploaded_file, user_id):
    """Save uploaded receipt to local receipts/ folder. Returns filename."""
    ext      = os.path.splitext(uploaded_file.name)[-1].lower() or ".jpg"
    filename = f"{date.today().isoformat()}_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    path     = os.path.join(RECEIPTS_DIR, filename)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filename


def _copy_to_destination_folder(filename):
    """
    STUB — Copy receipt to a network/OneDrive folder when path is configured.
    Activate by setting 'expenses_folder' in the settings table.
    """
    dest_folder = db.get_setting("expenses_folder") if hasattr(db, "get_setting") else None
    if not dest_folder or not os.path.isdir(dest_folder):
        return False
    import shutil
    src = os.path.join(RECEIPTS_DIR, filename)
    dst = os.path.join(dest_folder, filename)
    try:
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def _send_email_notification(expense_id, rep_name, amount, category, expense_date):
    """
    STUB — Email accounts team when a receipt is submitted.
    Activate by setting email_smtp_host, email_smtp_port, email_from,
    email_password, and expenses_notify_email in the settings table.
    """
    try:
        host     = db.get_setting("email_smtp_host")
        port     = int(db.get_setting("email_smtp_port") or 587)
        sender   = db.get_setting("email_from")
        password = db.get_setting("email_password")
        notify   = db.get_setting("expenses_notify_email")
        if not all([host, sender, password, notify]):
            return False
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg            = MIMEMultipart()
        msg["From"]    = sender
        msg["To"]      = notify
        msg["Subject"] = f"New Expense Receipt — {rep_name} — £{amount:.2f}"
        body = (
            f"A new expense has been submitted.\n\n"
            f"Rep:      {rep_name}\n"
            f"Date:     {expense_date}\n"
            f"Amount:   £{amount:.2f}\n"
            f"Category: {category}\n"
            f"Ref:      #{expense_id}\n\n"
            f"Log in to Sales Navigator to view the receipt image."
        )
        msg.attach(MIMEText(body, "plain"))
        from utils import smtp_connect
        with smtp_connect(host, port, sender, password) as smtp:
            smtp.send_message(msg)
        return True
    except Exception:
        return False


def _status_badge(status):
    colour = STATUS_COLOURS.get(status, "#999")
    label  = STATUS_LABELS.get(status, status.title())
    return f'<span style="background:{colour};color:white;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:bold">{label}</span>'


def _show_receipt_image(exp, key_suffix=""):
    """Render receipt image or PDF download button."""
    if not exp.get("receipt_filename"):
        return
    img_path = os.path.join(RECEIPTS_DIR, exp["receipt_filename"])
    if not os.path.exists(img_path):
        return
    ext = os.path.splitext(exp["receipt_filename"])[-1].lower()
    if ext == ".pdf":
        with open(img_path, "rb") as f:
            st.download_button("Download Receipt PDF", f.read(),
                               file_name=exp["receipt_filename"],
                               mime="application/pdf",
                               key=f"dl_{exp['id']}{key_suffix}")
    else:
        st.image(img_path, caption="Receipt", use_container_width=True)


# ── Rep submission view ───────────────────────────────────────────────────────

def _rep_view(user_id, full_name):
    st.markdown("### Submit a Receipt")
    st.caption("Take a photo of your receipt and submit it here. "
               "The receipt is saved to a searchable catalog so you can find it when accounts need it.")

    with st.form("expense_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        expense_date = col1.date_input(
            "Receipt Date",
            value=date.today(),
            max_value=date.today(),
            help="The date on the receipt"
        )
        amount = col2.number_input(
            "Total (£)",
            min_value=0.01, step=0.01, format="%.2f",
            help="Total amount on the receipt including VAT"
        )
        vat_amount = col3.number_input(
            "VAT (£)",
            min_value=0.00, step=0.01, format="%.2f", value=0.00,
            help="VAT amount if shown on the receipt — leave as 0 if not applicable"
        )

        col4, col5 = st.columns(2)
        category = col4.selectbox(
            "Category",
            CATEGORY_LABELS,
            help="Choose the expense category from the accounts template"
        )
        account_code = EXPENSE_CATEGORIES[category]
        col5.text_input("Account Code", value=account_code, disabled=True,
                        help="Auto-filled from category")

        notes = st.text_area(
            "Notes (optional)",
            placeholder="Customer visited, journey details, what the expense was for...",
            height=80
        )
        receipt_img = st.file_uploader(
            "Receipt Photo / Scan",
            type=["jpg", "jpeg", "png", "pdf", "heic"],
            help="Take a photo or upload a scan of your receipt"
        )
        submitted = st.form_submit_button("Submit Receipt", type="primary", use_container_width=True)

    if submitted:
        if not receipt_img:
            st.error("Please attach a receipt image before submitting.")
        elif amount <= 0:
            st.error("Please enter a valid amount.")
        else:
            filename = _save_receipt_file(receipt_img, user_id)
            db.submit_expense(
                user_id, str(expense_date), amount, category, notes, filename,
                vat_amount=vat_amount if vat_amount > 0 else None,
                account_code=account_code
            )

            expenses = db.get_expenses_for_user(user_id)
            new_id   = expenses[0]["id"] if expenses else 0

            db.log_audit(user_id, full_name, "create", "expense",
                         entity_id=new_id, entity_label=f"£{amount:.2f} — {category}",
                         details=f"Date: {expense_date}")

            _copy_to_destination_folder(filename)
            _send_email_notification(new_id, full_name, amount, category, str(expense_date))

            st.success(f"Receipt submitted — **£{amount:.2f}** · {category}")
            st.rerun()

    # ── Own submission history ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### My Receipts")

    my_expenses = db.get_expenses_for_user(user_id)
    if not my_expenses:
        st.info("You haven't submitted any receipts yet. Use the form above to upload your first receipt.")
        return

    for exp in my_expenses:
        status_html = _status_badge(exp["status"])
        with st.expander(
            f"£{exp['amount']:.2f}  |  {exp['category']}  |  {exp['expense_date']}",
            expanded=False
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Category:** {exp['category']}")
                st.markdown(f"**Date:** {exp['expense_date']}")
                st.markdown(f"**Submitted:** {exp['submitted_at'][:16]}")
                if exp.get("vat_amount"):
                    st.markdown(f"**VAT:** £{exp['vat_amount']:.2f}")
                if exp.get("account_code"):
                    st.markdown(f"**Account Code:** {exp['account_code']}")
                if exp.get("notes"):
                    st.markdown(f"**Notes:** {exp['notes']}")
                if exp.get("reviewer_notes"):
                    st.info(f"**Accounts note:** {exp['reviewer_notes']}")
            with col2:
                st.markdown(f"**Amount:** £{exp['amount']:.2f}")
                st.markdown("**Status:**")
                st.markdown(status_html, unsafe_allow_html=True)

            _show_receipt_image(exp, key_suffix="_my")


# ── Receipt Catalog (searchable) ─────────────────────────────────────────────

def _catalog_view(user_id, role):
    st.markdown("### Receipt Catalog")
    st.caption("Search for any receipt by date, amount, category, or rep name. "
               "Use this when accounts request a receipt for a specific transaction.")

    # Filters
    fc1, fc2, fc3, fc4 = st.columns(4)
    date_from = fc1.date_input(
        "From Date",
        value=date.today().replace(day=1) - timedelta(days=90),
        key="cat_date_from"
    )
    date_to = fc2.date_input(
        "To Date",
        value=date.today(),
        key="cat_date_to"
    )
    cat_filter = fc3.selectbox(
        "Category",
        ["All"] + CATEGORY_LABELS,
        key="cat_category"
    )
    search_text = fc4.text_input(
        "Search notes / rep name",
        placeholder="e.g. customer name, journey...",
        key="cat_search"
    )

    # Extra filters row
    fc5, fc6, fc7 = st.columns(3)
    amount_min = fc5.number_input("Min Amount (£)", min_value=0.00, value=0.00,
                                  step=1.00, format="%.2f", key="cat_min")
    amount_max = fc6.number_input("Max Amount (£)", min_value=0.00, value=0.00,
                                  step=1.00, format="%.2f", key="cat_max",
                                  help="Leave at 0 for no upper limit")

    # Rep filter for managers/admin
    rep_filter = None
    if role in ("admin", "regional_manager"):
        with db.get_conn() as conn:
            if role == "admin":
                reps = conn.execute(
                    "SELECT id, full_name FROM users WHERE role IN ('rep','regional_manager') ORDER BY full_name"
                ).fetchall()
            else:
                reps = conn.execute(
                    "SELECT id, full_name FROM users WHERE id=? OR regional_manager_id=? ORDER BY full_name",
                    (user_id, user_id)
                ).fetchall()
        rep_options = {"All Reps": None}
        rep_options.update({r["full_name"]: r["id"] for r in reps})
        rep_label = fc7.selectbox("Rep", list(rep_options.keys()), key="cat_rep")
        rep_filter = rep_options[rep_label]

    # Run search
    results = db.search_receipts(
        role=role,
        user_id=user_id,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
        category=cat_filter if cat_filter != "All" else None,
        amount_min=amount_min if amount_min > 0 else None,
        amount_max=amount_max if amount_max > 0 else None,
        search_text=search_text.strip() if search_text and search_text.strip() else None,
        rep_user_id=rep_filter,
    )

    st.markdown(f"**{len(results)} receipt{'s' if len(results) != 1 else ''} found**")

    if not results:
        st.info("No receipts match your search. Try widening the date range or removing filters.")
        return

    # Summary bar
    total_val = sum(r["amount"] for r in results)
    total_vat = sum(r.get("vat_amount") or 0 for r in results)
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Receipts", len(results))
    sc2.metric("Total Value", f"£{total_val:,.2f}")
    sc3.metric("Total VAT", f"£{total_vat:,.2f}")

    st.markdown("---")

    # Results
    for exp in results:
        status_html = _status_badge(exp["status"])
        rep_label = exp.get("rep_name", "")
        header = f"{exp['expense_date']}  |  £{exp['amount']:.2f}  |  {exp['category']}  |  {rep_label}"
        with st.expander(header, expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Rep:** {rep_label}")
                st.markdown(f"**Category:** {exp['category']}")
                st.markdown(f"**Date:** {exp['expense_date']}")
                st.markdown(f"**Amount:** £{exp['amount']:.2f}")
                if exp.get("vat_amount"):
                    st.markdown(f"**VAT:** £{exp['vat_amount']:.2f}")
                if exp.get("account_code"):
                    st.markdown(f"**Account Code:** {exp['account_code']}")
                if exp.get("notes"):
                    st.markdown(f"**Notes:** {exp['notes']}")
                st.markdown(f"**Submitted:** {exp['submitted_at'][:16]}")
                st.markdown(f"**Status:** {status_html}", unsafe_allow_html=True)
            with col2:
                _show_receipt_image(exp, key_suffix="_cat")


# ── Manager / Admin review view ───────────────────────────────────────────────

def _manager_view(user_id, role):
    st.markdown("### Review Team Expenses")

    all_expenses = db.get_all_expenses(role, user_id)
    if not all_expenses:
        st.info("No expense submissions from the team yet. "
                "Receipts will appear here once reps submit them.")
        return

    # Summary counts
    from collections import Counter
    counts = Counter(e["status"] for e in all_expenses)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",      len(all_expenses))
    c2.metric("Pending",    counts.get("pending", 0))
    c3.metric("Reviewed",   counts.get("reviewed", 0))
    c4.metric("Processed",  counts.get("processed", 0))

    st.markdown("---")

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    all_reps     = sorted({e["rep_name"] for e in all_expenses})
    filter_rep   = fc1.selectbox("Filter by Rep", ["All"] + all_reps, key="exp_filter_rep")
    filter_status= fc2.selectbox("Filter by Status",
                                 ["All", "pending", "reviewed", "processed", "rejected"],
                                 key="exp_filter_status")
    filter_month = fc3.text_input("Filter by Month (YYYY-MM)", placeholder="e.g. 2026-01",
                                  key="exp_filter_month")

    filtered = all_expenses
    if filter_rep    != "All":
        filtered = [e for e in filtered if e["rep_name"] == filter_rep]
    if filter_status != "All":
        filtered = [e for e in filtered if e["status"] == filter_status]
    if filter_month.strip():
        filtered = [e for e in filtered if e["expense_date"].startswith(filter_month.strip())]

    st.markdown(f"**{len(filtered)} records**")

    for exp in filtered:
        status_html = _status_badge(exp["status"])
        header = f"{exp['rep_name']}  |  £{exp['amount']:.2f}  |  {exp['category']}  |  {exp['expense_date']}"
        with st.expander(header, expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Rep:** {exp['rep_name']}")
                st.markdown(f"**Category:** {exp['category']}")
                st.markdown(f"**Expense Date:** {exp['expense_date']}")
                st.markdown(f"**Submitted:** {exp['submitted_at'][:16]}")
                if exp.get("vat_amount"):
                    st.markdown(f"**VAT:** £{exp['vat_amount']:.2f}")
                if exp.get("account_code"):
                    st.markdown(f"**Account Code:** {exp['account_code']}")
                if exp.get("notes"):
                    st.markdown(f"**Notes:** {exp['notes']}")
                if exp.get("reviewer_name"):
                    st.markdown(f"**Reviewed by:** {exp['reviewer_name']} at "
                                f"{(exp.get('reviewed_at') or '')[:16]}")
                if exp.get("reviewer_notes"):
                    st.info(f"**Review note:** {exp['reviewer_notes']}")
            with col2:
                st.markdown(f"**Amount:** £{exp['amount']:.2f}")
                st.markdown("**Status:**")
                st.markdown(status_html, unsafe_allow_html=True)

            _show_receipt_image(exp, key_suffix="_mgr")

            # Status update form
            if exp["status"] != "processed":
                st.markdown("**Update Status:**")
                uc1, uc2, uc3 = st.columns([2, 1, 1])
                reviewer_note = uc1.text_input("Note to rep (optional)", key=f"note_{exp['id']}")
                with uc2:
                    new_status_options = {
                        "Mark Reviewed":  "reviewed",
                        "Mark Processed": "processed",
                        "Reject":         "rejected",
                    }
                    for btn_label, btn_status in new_status_options.items():
                        if exp["status"] == "processed" and btn_status == "reviewed":
                            continue
                        if st.button(btn_label, key=f"{btn_status}_{exp['id']}",
                                     type="primary" if btn_status == "processed" else "secondary",
                                     use_container_width=True):
                            db.update_expense_status(exp["id"], btn_status, user_id, reviewer_note)
                            db.log_audit(user_id, st.session_state["full_name"], "update", "expense",
                                         entity_id=exp["id"],
                                         entity_label=f"£{exp['amount']:.2f} — {exp['rep_name']}",
                                         details=f"Status: {btn_status}"
                                                 f"{', Note: ' + reviewer_note if reviewer_note else ''}")
                            st.success(f"Updated to {btn_status}")
                            st.rerun()


# ── Main entry point ──────────────────────────────────────────────────────────

def page_expenses():
    st.markdown('<div class="section-header">Expenses & Receipts</div>', unsafe_allow_html=True)

    user_id   = st.session_state["user_id"]
    role      = st.session_state["role"]
    full_name = st.session_state["full_name"]

    can_review = role in ("admin", "regional_manager")

    if can_review:
        tab1, tab2, tab3 = st.tabs(["Submit Receipt", "Receipt Catalog", "Review Team Expenses"])
        with tab1:
            _rep_view(user_id, full_name)
        with tab2:
            _catalog_view(user_id, role)
        with tab3:
            _manager_view(user_id, role)
    else:
        tab1, tab2 = st.tabs(["Submit Receipt", "My Receipt Catalog"])
        with tab1:
            _rep_view(user_id, full_name)
        with tab2:
            _catalog_view(user_id, role)
