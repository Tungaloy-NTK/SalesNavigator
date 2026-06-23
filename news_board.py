import streamlit as st
from datetime import date, datetime
import database as db
import alert_engine as ae

def fmt_date(d):
    if not d: return "—"
    try: return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError): return d

def nav(page, **kwargs):
    st.session_state["page"] = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

def page_news_list():
    st.markdown('<div class="section-header">News & Updates</div>', unsafe_allow_html=True)
    role    = st.session_state["role"]
    user_id = st.session_state["user_id"]

    can_post = role in ("admin", "marketing")
    if can_post:
        col1, col2 = st.columns([4, 1])
        if col2.button("➕ Post Update", type="primary"):
            nav("news_new")

    if can_post:
        news = db.get_all_news()
    else:
        news = db.get_news_for_user(user_id)

    if not news:
        if can_post:
            st.info("No news posts yet. Click 'Post Update' above to share an announcement or action item with the team.")
        else:
            st.info("No news or updates to show right now. Check back later for announcements from management.")
        return

    for n in news:
        is_admin_view = "total_recipients" in n.keys()

        with st.container():
            col1, col2 = st.columns([5, 1])
            col1.markdown(f"### {n['title']}")
            col1.markdown(f"<small>Posted by {n['posted_by_name']} on {fmt_date(n['created_at'])}</small>",
                          unsafe_allow_html=True)
            col2_text = ""

            if is_admin_view:
                total = n["total_recipients"]
                read = n["read_count"]
                actioned = n["action_count"]
                col2.markdown(f"👁 {read}/{total} read")
                if n["action_required"]:
                    col2.markdown(f"✅ {actioned}/{total} actioned")
            else:
                if not n["read_at"]:
                    db.mark_news_read(n["id"], user_id)
                if n["action_required"] and not n["action_completed_at"]:
                    col2.markdown('<span style="background:#c0392b;color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold">Action Required</span>', unsafe_allow_html=True)

            st.markdown(n["body"])

            if n["action_required"]:
                st.markdown(f"**Action Required:** {n['action_required']}")
                if n["action_deadline"]:
                    st.markdown(f"**Deadline:** {fmt_date(n['action_deadline'])}")

            # Rep: action button
            if not is_admin_view and n["action_required"] and not n.get("action_completed_at"):
                with st.form(f"action_form_{n['id']}"):
                    action_notes = st.text_input("Your response / confirmation", key=f"an_{n['id']}")
                    if st.form_submit_button("Mark as Completed", key=f"ac_{n['id']}"):
                        db.complete_news_action(n["id"], user_id, action_notes.strip() or None)
                        st.success("Action completed.")
                        st.rerun()
            elif not is_admin_view and n.get("action_completed_at"):
                st.markdown(f"<span style='color:#27ae60'>✅ You completed this on {fmt_date(n['action_completed_at'])}</span>", unsafe_allow_html=True)

            # Admin: view recipients
            if is_admin_view:
                with st.expander(f"View recipients ({n['total_recipients']})"):
                    recipients = db.get_news_recipients(n["id"])
                    for r in recipients:
                        read_icon = "👁" if r["read_at"] else "—"
                        action_icon = f"✅ {fmt_date(r['action_completed_at'])}" if r["action_completed_at"] else ("⏳" if n["action_required"] else "—")
                        st.write(f"**{r['full_name']}** | Read: {read_icon} | Action: {action_icon}")
                        if r["action_notes"]:
                            st.write(f"  Response: _{r['action_notes']}_")

            st.markdown("<hr style='margin:8px 0 16px'/>", unsafe_allow_html=True)

def page_news_new():
    st.markdown('<div class="section-header">Post News / Update</div>', unsafe_allow_html=True)
    if st.button("← Back"):
        nav("news")

    all_users = [u for u in db.get_all_users() if u["role"] != "admin"]

    with st.form("news_form"):
        title = st.text_input("Title *", placeholder="e.g. New pricing effective 1st May")
        body  = st.text_area("Message *", height=150, placeholder="Write your update here...")

        st.markdown("### Action Required (optional)")
        action_required = st.text_input("What do you need them to do?",
                                        placeholder="e.g. Read and confirm / Update your price lists by Friday")
        action_deadline = st.date_input("Action deadline", value=None, min_value=date.today())

        st.markdown("### Recipients")
        send_all = st.checkbox("Send to all", value=True)

        selected_users = []
        if not send_all:
            for u in all_users:
                if st.checkbox(u["full_name"], key=f"nr_{u['id']}"):
                    selected_users.append(u["id"])
        else:
            selected_users = [u["id"] for u in all_users]

        submitted = st.form_submit_button("Post Update", type="primary")

    if submitted:
        if not title.strip() or not body.strip():
            st.error("Title and message are required.")
            return
        if not selected_users:
            st.error("Please select at least one recipient.")
            return

        news_id = db.create_news_post(
            title=title.strip(),
            body=body.strip(),
            action_required=action_required.strip() or None,
            action_deadline=action_deadline.strftime("%Y-%m-%d") if action_deadline else None,
            posted_by=st.session_state["user_id"],
            recipient_ids=selected_users,
        )
        db.log_audit(st.session_state["user_id"], st.session_state["full_name"], "create", "news",
                     entity_id=news_id, entity_label=title.strip(),
                     details=f"Recipients: {len(selected_users)}, Action required: {'Yes' if action_required.strip() else 'No'}")

        # Email all recipients
        for uid in selected_users:
            user = db.get_user_by_id(uid)
            if user:
                action_html = ""
                if action_required.strip():
                    action_html = f"<p style='color:#c0392b;font-weight:bold'>Action Required: {action_required.strip()}</p>"
                    if action_deadline:
                        action_html += f"<p>Deadline: {fmt_date(action_deadline.strftime('%Y-%m-%d'))}</p>"

                ae.send_email(
                    [user["email"]],
                    f"Sales Navigator Update: {title.strip()}",
                    f"""<div style="font-family:Arial;background:#1a1a2e;padding:20px">
                        <h2 style="color:#fff;margin:0">Tungaloy-NTK Sales Navigator</h2>
                        <p style="color:#c0392b;margin:4px 0 0">News & Update</p>
                    </div>
                    <div style="padding:20px;font-family:Arial">
                        <h3>{title.strip()}</h3>
                        <p>{body.strip()}</p>
                        {action_html}
                        <p style="font-size:12px;color:#888;margin-top:20px">
                            Log in to the Sales Navigator to view and respond.
                        </p>
                    </div>"""
                )

        st.success(f"Update posted to {len(selected_users)} people. Emails sent.")
        st.balloons()

def render_page():
    page = st.session_state.get("page", "news")
    if page == "news_new":
        page_news_new()
    else:
        page_news_list()
