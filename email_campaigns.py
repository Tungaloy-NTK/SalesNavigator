"""Email Campaigns module — Templates, Campaigns, Analytics, Opt-outs, Landing Pages."""
import streamlit as st
import pandas as pd
import smtplib, ssl
from utils import smtp_connect
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import re, time
import database as db

BASE_URL = db.get_setting("site_base_url") or "https://tungaloy.co.uk"

# ── Email HTML wrapper ────────────────────────────────────────────────────────

def _wrap_html(body_html, subject, from_name, unsub_url, open_pixel_url):
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
<style>
  body{{margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;}}
  .wrapper{{max-width:620px;margin:30px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);}}
  .header{{background:#1a1a2e;padding:24px 32px;}}
  .header h1{{color:#fff;margin:0;font-size:22px;}}
  .header p{{color:rgba(255,255,255,.7);margin:4px 0 0;font-size:13px;}}
  .body{{padding:32px;color:#333;line-height:1.7;font-size:15px;}}
  .body h2{{color:#1a1a2e;font-size:18px;margin-top:0;}}
  .body a{{color:#c0392b;}}
  .cta{{display:inline-block;background:#c0392b;color:#fff!important;text-decoration:none;padding:12px 28px;border-radius:6px;font-weight:700;margin:16px 0;}}
  .footer{{background:#f4f4f4;padding:20px 32px;font-size:12px;color:#888;text-align:center;}}
  .footer a{{color:#888;}}
  hr{{border:none;border-top:1px solid #eee;margin:24px 0;}}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Tungaloy UK</h1>
    <p>Cutting Tools & Carbide Specialists</p>
  </div>
  <div class="body">
    {body_html}
  </div>
  <div class="footer">
    <p>Tungaloy UK &nbsp;|&nbsp; <a href="https://tungaloy.com/uk/">tungaloy.com/uk</a></p>
    <p>You are receiving this email because you are a Tungaloy UK customer.<br>
    <a href="{unsub_url}">Unsubscribe</a> &nbsp;·&nbsp; <a href="mailto:rob.werhun@tungaloyuk.co.uk">Contact Us</a></p>
  </div>
</div>
<img src="{open_pixel_url}" width="1" height="1" style="display:none;">
</body>
</html>"""


def _inject_click_tracking(html, send_id):
    """Wrap all href links with tracking redirects."""
    def replacer(m):
        orig_url = m.group(1)
        if "tungaloy.co.uk/track" in orig_url or "unsubscribe" in orig_url:
            return m.group(0)
        import urllib.parse
        encoded = urllib.parse.quote(orig_url, safe='')
        tracked = f"{BASE_URL}/track/c/{send_id}/{encoded}"
        return f'href="{tracked}"'
    return re.sub(r'href="([^"]+)"', replacer, html)


# ── SMTP sending ──────────────────────────────────────────────────────────────

def _send_email(to_email, to_name, subject, html_body, from_name, from_email, reply_to):
    host     = db.get_setting("smtp_host") or ""
    port     = int(db.get_setting("smtp_port") or 587)
    username = db.get_setting("smtp_username") or db.get_setting("smtp_user") or ""
    password = db.get_setting("smtp_password") or db.get_setting("smtp_pass") or ""

    if not host:
        raise ValueError("SMTP host not configured. Please set it in Admin → Settings.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((from_name, from_email))
    msg["To"]      = formataddr((to_name, to_email))
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(html_body, "html"))

    with smtp_connect(host, port, username, password) as server:
        server.sendmail(from_email, [to_email], msg.as_string())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(num, den):
    return f"{num/den*100:.1f}%" if den else "—"

def _fmt_dt(d):
    if not d: return "—"
    try:
        from datetime import datetime
        return datetime.strptime(str(d)[:19], "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y %H:%M")
    except:
        return str(d)[:16]

def _status_badge(status):
    colours = {"draft":"#888","sending":"#f39c12","sent":"#27ae60","failed":"#e74c3c"}
    c = colours.get(status, "#888")
    return f'<span style="background:{c};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;">{status.upper()}</span>'


# ── Tab 1: Campaigns ──────────────────────────────────────────────────────────

def tab_campaigns(user):
    st.markdown("### 📧 Email Campaigns")

    campaigns = db.email_get_campaigns()

    with st.expander("➕ Create New Campaign"):
        _campaign_form(user)

    if not campaigns:
        st.info("No campaigns yet. Create one above.")
        return

    for c in campaigns:
        sent = c['total_sent'] or 0
        with st.expander(
            f"**{c['name']}** &nbsp; {c['subject'][:50]}",
            expanded=False
        ):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**Status:** {c['status'].upper()}")
                st.caption(f"Created: {_fmt_dt(c['created_at'])}")
                if c['sent_at']:
                    st.caption(f"Sent: {_fmt_dt(c['sent_at'])}")
            with col2:
                st.metric("Sent", f"{sent:,}")
            with col3:
                st.metric("Opened", f"{c['total_opened'] or 0:,}",
                          delta=_pct(c['total_opened'] or 0, sent) if sent else None)
            with col4:
                st.metric("Clicked", f"{c['total_clicked'] or 0:,}",
                          delta=_pct(c['total_clicked'] or 0, sent) if sent else None)

            # Preview
            with st.expander("👁️ Preview Email"):
                st.markdown(c['body_html'], unsafe_allow_html=True)

            # Actions row
            a1, a2, a3, a4 = st.columns(4)
            with a1:
                if c['status'] == 'draft' and st.button("🚀 Send Campaign", key=f"send_{c['id']}"):
                    st.session_state[f"confirm_send_{c['id']}"] = True
            with a2:
                if c['status'] == 'draft' and st.button("✏️ Edit", key=f"edit_{c['id']}"):
                    st.session_state[f"edit_campaign"] = c['id']
            with a3:
                if c['status'] == 'sent':
                    if st.button("📋 View Sends", key=f"sends_{c['id']}"):
                        st.session_state[f"view_sends"] = c['id']
            with a4:
                if user['role'] == 'admin':
                    with st.popover("🗑 Delete", key=f"del_camp_{c['id']}"):
                        st.caption("Are you sure?")
                        if st.button("Yes, delete", key=f"confirm_del_camp_{c['id']}", type="primary"):
                            db.email_delete_campaign(c['id'])
                            db.log_audit(user['id'], user['full_name'], "delete", "email_campaign",
                                         entity_id=c['id'], entity_label=c['name'])
                            st.rerun()

            # Confirm send
            if st.session_state.get(f"confirm_send_{c['id']}"):
                _send_campaign_ui(c, user)

            # View sends detail
            if st.session_state.get("view_sends") == c['id']:
                _show_sends(c['id'])


def _campaign_form(user, campaign=None):
    segments   = db.crm_get_segments()
    templates  = db.email_get_templates()
    seg_opts   = {s['name']: s['id'] for s in segments}
    tmpl_opts  = {"— write from scratch —": None} | {t['name']: t['id'] for t in templates}

    cid = campaign['id'] if campaign else None

    with st.form(f"campaign_form_{cid or 'new'}"):
        c1, c2 = st.columns(2)
        with c1:
            name       = st.text_input("Campaign Name *",  value=campaign['name']    if campaign else "")
            subject    = st.text_input("Email Subject *",  value=campaign['subject'] if campaign else "")
            from_name  = st.text_input("From Name",        value=campaign['from_name']  if campaign else "Tungaloy UK")
            from_email = st.text_input("From Email",       value=campaign['from_email'] if campaign else "marketing@tungaloyuk.co.uk")
        with c2:
            reply_to   = st.text_input("Reply-To Email",   value=campaign['reply_to'] if campaign else "rob.werhun@tungaloyuk.co.uk")
            seg_sel    = st.selectbox("Send To Segment",   ["— no segment —"] + list(seg_opts.keys()),
                                      key=f"seg_sel_{cid or 'new'}")
            tmpl_sel   = st.selectbox("Load Template",     list(tmpl_opts.keys()),
                                      key=f"tmpl_sel_{cid or 'new'}")

        # Load template body if selected
        body_default = campaign['body_html'] if campaign else ""
        if tmpl_opts.get(tmpl_sel):
            t = db.email_get_template(tmpl_opts[tmpl_sel])
            if t:
                body_default = t['body_html']

        body_html = st.text_area("Email Body (HTML supported) *", value=body_default, height=300,
                                 help="Use HTML for formatting. <b>Bold</b>, <a href='...'>links</a>, etc.")

        if st.form_submit_button("💾 Save Campaign"):
            if name.strip() and subject.strip() and body_html.strip():
                seg_id = seg_opts.get(seg_sel)
                tmpl_id = tmpl_opts.get(tmpl_sel)
                db.email_save_campaign(
                    name.strip(), subject.strip(), body_html.strip(),
                    from_name, from_email, reply_to,
                    seg_id, tmpl_id, user['id'], cid
                )
                db.log_audit(user['id'], user['full_name'], "create" if not cid else "update", "email_campaign",
                             entity_id=cid, entity_label=name.strip(),
                             details=f"Subject: {subject.strip()}")
                st.success("Campaign saved!")
                st.rerun()
            else:
                st.warning("Name, subject and body are required.")


def _send_campaign_ui(campaign, user):
    st.markdown("---")
    st.warning("⚠️ **Confirm Send** — this will email real recipients.")

    # Build recipient list
    recipients = _build_recipients(campaign)
    # Fetch all opted-out emails in one query
    with db.get_conn() as conn:
        _opt_out_set = {r['email'].lower() for r in conn.execute(
            "SELECT email FROM email_opt_outs"
        ).fetchall()}
    opted_out = [r for r in recipients if r[1].lower() in _opt_out_set]
    to_send   = [r for r in recipients if r[1].lower() not in _opt_out_set]

    st.info(f"📬 **{len(to_send)}** emails will be sent  |  "
            f"**{len(opted_out)}** skipped (opted out)  |  "
            f"**{len(recipients)}** total recipients")

    if opted_out:
        with st.expander(f"See {len(opted_out)} opted-out (skipped)"):
            for r in opted_out:
                st.caption(f"• {r[2]} — {r[1]}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Yes, Send Now", key=f"go_send_{campaign['id']}"):
            if not to_send:
                st.error("No recipients to send to.")
                return
            _execute_send(campaign, to_send)
    with c2:
        if st.button("❌ Cancel", key=f"cancel_send_{campaign['id']}"):
            st.session_state.pop(f"confirm_send_{campaign['id']}", None)
            st.rerun()


def _build_recipients(campaign):
    """Return list of (customer_code, email, name) for this campaign."""
    recipients = []
    if campaign['segment_id']:
        members = db.crm_get_segment_members(campaign['segment_id'])
        member_codes = [m['customer_code'] for m in members]
        if member_codes:
            # Batch-fetch all contacts for all segment members in one query
            placeholders = ",".join("?" * len(member_codes))
            with db.get_conn() as conn:
                all_contacts = conn.execute(f"""
                    SELECT customer_code, contact_name, email
                    FROM customer_contacts
                    WHERE customer_code IN ({placeholders}) AND email IS NOT NULL AND email != ''
                    ORDER BY customer_code
                """, member_codes).fetchall()

                # Group contacts by customer_code
                contacts_by_code = {}
                for c in all_contacts:
                    contacts_by_code.setdefault(c['customer_code'], []).append(c)

                # Also batch-fetch customer emails for fallback
                custs_with_email = conn.execute(f"""
                    SELECT customer_code, email, customer_name FROM customers
                    WHERE customer_code IN ({placeholders}) AND email IS NOT NULL AND email != ''
                """, member_codes).fetchall()
                cust_email_map = {c['customer_code']: c for c in custs_with_email}

            for code in member_codes:
                code_contacts = contacts_by_code.get(code, [])
                if code_contacts:
                    for c in code_contacts:
                        recipients.append((code, c['email'], c['contact_name'] or ''))
                else:
                    cust = cust_email_map.get(code)
                    if cust:
                        recipients.append((code, cust['email'], cust['customer_name'] or ''))
    else:
        # All contacts with emails
        contacts = db.crm_get_contacts()
        for c in contacts:
            if c['email']:
                recipients.append((c['customer_code'], c['email'], c['contact_name'] or ''))
    return recipients


def _execute_send(campaign, recipients):
    db.email_create_sends(campaign['id'], recipients)
    sends = db.email_get_sends(campaign['id'])
    send_map = {s['contact_email']: s for s in sends}

    progress = st.progress(0, text="Sending emails…")
    sent_count = 0
    failed_count = 0
    total = len(recipients)

    for i, (code, email_addr, name) in enumerate(recipients):
        send = send_map.get(email_addr)
        if not send:
            continue
        try:
            unsub_url    = f"{BASE_URL}/unsubscribe/{send['token']}"
            open_pix_url = f"{BASE_URL}/track/o/{send['id']}"
            wrapped      = _wrap_html(campaign['body_html'], campaign['subject'],
                                      campaign['from_name'], unsub_url, open_pix_url)
            tracked      = _inject_click_tracking(wrapped, send['id'])
            _send_email(email_addr, name, campaign['subject'], tracked,
                        campaign['from_name'], campaign['from_email'], campaign['reply_to'])
            db.email_mark_sent(send['id'])
            sent_count += 1
        except Exception as e:
            db.email_mark_failed(send['id'])
            failed_count += 1
        progress.progress((i + 1) / total, text=f"Sending… {i+1}/{total}")
        time.sleep(0.05)  # small rate limit

    db.email_update_campaign_status(campaign['id'], 'sent', sent_count)
    progress.empty()
    st.success(f"✅ Campaign sent! {sent_count} delivered, {failed_count} failed.")
    st.session_state.pop(f"confirm_send_{campaign['id']}", None)
    st.rerun()


def _show_sends(campaign_id):
    sends = db.email_get_sends(campaign_id)
    if not sends:
        st.info("No send records found.")
        return
    df = pd.DataFrame([dict(s) for s in sends])
    df = df[['contact_name','contact_email','status','sent_at',
             'open_count','click_count','unsubscribed','bounced']].rename(columns={
        'contact_name':'Name','contact_email':'Email','status':'Status',
        'sent_at':'Sent At','open_count':'Opens','click_count':'Clicks',
        'unsubscribed':'Unsub','bounced':'Bounce'
    })
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── Tab 2: Templates ──────────────────────────────────────────────────────────

def tab_templates(user):
    st.markdown("### 📄 Email Templates")

    with st.expander("➕ Create New Template"):
        with st.form("new_template_form"):
            t1, t2 = st.columns(2)
            with t1:
                tmpl_name = st.text_input("Template Name *", placeholder="e.g. Price Increase Notice")
            with t2:
                tmpl_subj = st.text_input("Default Subject *", placeholder="e.g. Important update from Tungaloy UK")
            tmpl_body = st.text_area("Email Body (HTML) *", height=300,
                                     value=_starter_template(),
                                     help="Use HTML tags for formatting.")
            if st.form_submit_button("💾 Save Template"):
                if tmpl_name.strip() and tmpl_subj.strip() and tmpl_body.strip():
                    db.email_save_template(tmpl_name.strip(), tmpl_subj.strip(),
                                           tmpl_body.strip(), user['id'])
                    db.log_audit(user['id'], user['full_name'], "create", "email_template",
                                 entity_label=tmpl_name.strip(),
                                 details=f"Subject: {tmpl_subj.strip()}")
                    st.success("Template saved!")
                    st.rerun()
                else:
                    st.warning("All fields required.")

    templates = db.email_get_templates()
    if not templates:
        st.info("No templates yet.")
        return

    for t in templates:
        with st.expander(f"**{t['name']}** — {t['subject']}"):
            st.caption(f"Created by {t['author'] or '—'} on {_fmt_dt(t['created_at'])}")
            with st.expander("👁️ Preview"):
                st.markdown(t['body_html'], unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✏️ Edit", key=f"edit_tmpl_{t['id']}"):
                    st.session_state['edit_template'] = t['id']
            with col2:
                with st.popover("🗑 Delete", key=f"del_tmpl_{t['id']}"):
                    st.caption("Are you sure?")
                    if st.button("Yes, delete", key=f"confirm_del_tmpl_{t['id']}", type="primary"):
                        db.email_delete_template(t['id'])
                        db.log_audit(user['id'], user['full_name'], "delete", "email_template",
                                     entity_id=t['id'], entity_label=t['name'])
                        st.rerun()

            if st.session_state.get('edit_template') == t['id']:
                with st.form(f"edit_tmpl_form_{t['id']}"):
                    en = st.text_input("Name",    value=t['name'])
                    es = st.text_input("Subject", value=t['subject'])
                    eb = st.text_area("Body",     value=t['body_html'], height=300)
                    if st.form_submit_button("💾 Update"):
                        db.email_save_template(en, es, eb, user['id'], t['id'])
                        st.session_state.pop('edit_template', None)
                        st.success("Template updated!")
                        st.rerun()


def _starter_template():
    return """<h2>Hello [First Name],</h2>

<p>I hope you're well. I'm reaching out from Tungaloy UK with an important update.</p>

<p>[Your message here]</p>

<p>
  <a href="https://tungaloy.com/uk/" class="cta">Find Out More</a>
</p>

<hr>

<p>If you have any questions, please don't hesitate to get in touch with your local Tungaloy representative or contact us directly.</p>

<p>Kind regards,<br>
<strong>Rob Werhun</strong><br>
Tungaloy UK</p>"""


# ── Tab 3: Analytics ──────────────────────────────────────────────────────────

def tab_analytics(user):
    st.markdown("### 📊 Campaign Analytics")

    campaigns = db.email_get_campaigns()
    sent_camps = [c for c in campaigns if c['status'] == 'sent']

    if not sent_camps:
        st.info("No sent campaigns yet.")
        return

    # Summary table
    rows = []
    for c in sent_camps:
        sent = c['total_sent'] or 0
        rows.append({
            "Campaign":    c['name'],
            "Subject":     c['subject'][:45],
            "Sent":        sent,
            "Opened":      c['total_opened'] or 0,
            "Open Rate":   f"{(c['total_opened'] or 0)/sent*100:.1f}%" if sent else "—",
            "Clicked":     c['total_clicked'] or 0,
            "Click Rate":  f"{(c['total_clicked'] or 0)/sent*100:.1f}%" if sent else "—",
            "Sent At":     _fmt_dt(c['sent_at']),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Per-campaign drill-down
    st.markdown("---")
    st.markdown("#### Drill into a campaign")
    camp_sel = st.selectbox("Select campaign",
                            ["— select —"] + [c['name'] for c in sent_camps],
                            key="analytics_camp_sel")
    sel = next((c for c in sent_camps if c['name'] == camp_sel), None)
    if sel:
        sent = sel['total_sent'] or 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sent",      f"{sent:,}")
        m2.metric("Opened",    f"{sel['total_opened'] or 0:,}",
                  delta=_pct(sel['total_opened'] or 0, sent))
        m3.metric("Clicked",   f"{sel['total_clicked'] or 0:,}",
                  delta=_pct(sel['total_clicked'] or 0, sent))
        m4.metric("Segment",   sel['segment_name'] or "Custom")

        sends = db.email_get_sends(sel['id'])
        if sends:
            df2 = pd.DataFrame([dict(s) for s in sends])
            df2 = df2[['contact_name','contact_email','status',
                        'open_count','click_count','unsubscribed']].rename(columns={
                'contact_name':'Name','contact_email':'Email','status':'Status',
                'open_count':'Opens','click_count':'Clicks','unsubscribed':'Unsub'
            })
            st.dataframe(df2, use_container_width=True, hide_index=True)


# ── Tab 4: Opt-outs ───────────────────────────────────────────────────────────

def tab_optouts(user):
    st.markdown("### 🚫 Opt-out Management")
    st.caption("Contacts on this list will never receive campaign emails.")

    with st.expander("➕ Manually Add Opt-out"):
        with st.form("add_optout_form"):
            oo_email = st.text_input("Email Address *")
            oo_reason = st.text_input("Reason", value="Manual — requested by customer")
            if st.form_submit_button("Add to Opt-out List"):
                if oo_email.strip():
                    db.email_add_opt_out(oo_email.strip(), reason=oo_reason)
                    st.success(f"{oo_email} added to opt-out list.")
                    st.rerun()
                else:
                    st.warning("Email address required.")

    opt_outs = db.email_get_opt_outs()
    st.markdown(f"**{len(opt_outs)} opted-out email{'s' if len(opt_outs) != 1 else ''}**")

    if opt_outs:
        for o in opt_outs:
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                st.markdown(f"**{o['email']}**")
                if o['customer_name']:
                    st.caption(o['customer_name'])
            with col2:
                st.caption(f"{o['reason'] or '—'}  ·  {str(o['opted_out_at'] or '')[:10]}")
            with col3:
                if st.button("↩ Re-add", key=f"readd_{o['id']}", help="Remove from opt-out list"):
                    db.email_remove_opt_out(o['email'])
                    st.rerun()
            st.divider()
    else:
        st.success("No opt-outs on record.")


# ── Tab 5: Landing Pages ──────────────────────────────────────────────────────

def tab_landing_pages(user):
    st.markdown("### 🌐 Landing Pages")
    st.caption(f"Pages are live at **{BASE_URL}/l/[slug]** once the domain is configured.")

    with st.expander("➕ Create New Landing Page"):
        with st.form("new_lp_form"):
            lp1, lp2 = st.columns(2)
            with lp1:
                lp_name  = st.text_input("Page Name *", placeholder="e.g. April Price Hold Offer")
                lp_slug  = st.text_input("URL Slug *",  placeholder="e.g. price-hold-2026",
                                         help=f"Will be live at {BASE_URL}/l/[slug]")
            with lp2:
                lp_title = st.text_input("Page Title *", placeholder="e.g. Hold Your Prices Until End of 2026")

            lp_body = st.text_area("Page Content (HTML) *",
                                   value=_starter_landing_page(), height=350)
            if st.form_submit_button("💾 Save Landing Page"):
                if lp_name.strip() and lp_slug.strip() and lp_title.strip() and lp_body.strip():
                    db.lp_save_page(lp_name.strip(), lp_slug.strip(),
                                    lp_title.strip(), lp_body.strip(), user['id'])
                    st.success(f"Landing page saved! URL: {BASE_URL}/l/{lp_slug.strip().lower()}")
                    st.rerun()
                else:
                    st.warning("All fields required.")

    pages = db.lp_get_pages()
    if not pages:
        st.info("No landing pages yet. Create one above.")
        return

    for p in pages:
        with st.expander(f"**{p['name']}** — /{p['slug']}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                url = f"{BASE_URL}/l/{p['slug']}"
                st.markdown(f"🔗 [{url}]({url})")
                st.caption(f"Views: **{p['view_count'] or 0}**  ·  "
                           f"Created by {p['author'] or '—'}  ·  {_fmt_dt(p['created_at'])}")
            with col2:
                status = "🟢 Active" if p['is_active'] else "🔴 Inactive"
                st.markdown(status)

            with st.expander("👁️ Preview"):
                st.markdown(f"<h2>{p['title']}</h2>{p['body_html']}", unsafe_allow_html=True)

            da, db_ = st.columns(2)
            with da:
                if st.button("📋 Copy URL", key=f"copy_lp_{p['id']}"):
                    st.code(f"{BASE_URL}/l/{p['slug']}")
            with db_:
                with st.popover("🗑 Delete", key=f"del_lp_{p['id']}"):
                    st.caption("Are you sure?")
                    if st.button("Yes, delete", key=f"confirm_del_lp_{p['id']}", type="primary"):
                        db.lp_delete_page(p['id'])
                        st.rerun()


def _starter_landing_page():
    return """<div style="max-width:640px;margin:0 auto;font-family:Arial,sans-serif;padding:40px 20px;">

  <div style="background:#1a1a2e;color:#fff;padding:30px;border-radius:8px;text-align:center;margin-bottom:30px;">
    <h1 style="margin:0;font-size:28px;">Tungaloy UK</h1>
    <p style="margin:8px 0 0;opacity:.8;">Cutting Tools &amp; Carbide Specialists</p>
  </div>

  <h2 style="color:#1a1a2e;">Special Offer Headline Here</h2>

  <p>Your offer description goes here. Explain the benefit clearly and concisely.</p>

  <ul>
    <li>Benefit one</li>
    <li>Benefit two</li>
    <li>Benefit three</li>
  </ul>

  <div style="text-align:center;margin:30px 0;">
    <a href="mailto:rob.werhun@tungaloyuk.co.uk"
       style="background:#c0392b;color:#fff;padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:700;font-size:16px;">
      Get in Touch
    </a>
  </div>

  <hr style="border:none;border-top:1px solid #eee;margin:30px 0;">
  <p style="color:#888;font-size:13px;text-align:center;">
    Tungaloy UK &nbsp;|&nbsp; <a href="https://tungaloy.com/uk/" style="color:#888;">tungaloy.com/uk</a>
  </p>

</div>"""


# ── Tab 6: Segments ───────────────────────────────────────────────────────────

def tab_segments(user):
    st.markdown("### 👥 Customer Segments")
    st.caption("Create and manage customer segments for targeted campaigns")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ New Segment", type="primary"):
            st.session_state["show_segment_form"] = True

    segments = db.crm_get_segments()

    if st.session_state.get("show_segment_form"):
        st.markdown("---")
        st.markdown("#### Create New Segment")
        with st.form("new_segment_form"):
            seg_name = st.text_input("Segment Name *", placeholder="e.g. Active Stainless Steel Users")
            seg_desc = st.text_area("Description (optional)", placeholder="Notes about this segment")

            st.markdown("**Filter Customers By:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                filter_sm = col1.multiselect(
                    "Sales Manager",
                    options=[""] + sorted(list(set(r["sm_name"] for r in db.get_all_customers() if r.get("sm_name")))),
                    default=[]
                )

            with col2:
                industries = sorted(list(set(r.get("industry", "") for r in db.get_all_customers() if r.get("industry"))))
                filter_industry = col2.multiselect(
                    "Industry",
                    options=industries,
                    default=[]
                )

            with col3:
                regions = ["North", "South", "East", "West", "Scotland"]
                filter_region = col3.multiselect(
                    "Region",
                    options=regions,
                    default=[]
                )

            col1, col2 = st.columns(2)
            with col1:
                last_order_months = col1.slider("Last Order (months ago)", 0, 36, 12)

            if st.form_submit_button("Create Segment", type="primary"):
                if not seg_name.strip():
                    st.error("Segment name is required")
                    return

                import json
                filter_json = json.dumps({
                    "sm_names": filter_sm,
                    "industries": filter_industry,
                    "regions": filter_region,
                    "last_order_months": last_order_months
                })

                db.crm_save_segment(seg_name.strip(), seg_desc or None, user["id"], filter_json=filter_json, create_from_filters=True)
                st.success(f"✅ Segment '{seg_name.strip()}' created!")
                st.session_state["show_segment_form"] = False
                st.rerun()

        st.markdown("---")

    if not segments:
        st.info("No segments yet. Click '+ New Segment' to create one.")
        return

    for seg in segments:
        members = db.crm_get_segment_members(seg["id"])
        member_count = len(members) if members else 0

        with st.expander(f"**{seg['name']}** — {member_count} customers"):
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.caption(f"**Description:** {seg['description'] or 'N/A'}")
                if seg["filter_json"]:
                    try:
                        import json
                        filters = json.loads(seg["filter_json"])
                        st.caption(f"**Filters:** Sales Mgrs: {', '.join(filters.get('sm_names', [])) or 'All'} | Industries: {', '.join(filters.get('industries', [])) or 'All'}")
                    except:
                        pass
                st.caption(f"Created: {_fmt_dt(seg['created_at'])}")

            with col2:
                st.metric("Members", f"{member_count:,}")

            with col3:
                if st.button("🗑️ Delete", key=f"del_seg_{seg['id']}", use_container_width=True):
                    db.crm_delete_segment(seg["id"])
                    st.success("Segment deleted")
                    st.rerun()


# ── Main entry point ──────────────────────────────────────────────────────────

def render_page(user):
    st.title("📧 Email Campaigns")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📧 Campaigns",
        "📄 Templates",
        "👥 Segments",
        "📊 Analytics",
        "🚫 Opt-outs",
        "🌐 Landing Pages",
    ])

    with tab1: tab_campaigns(user)
    with tab2: tab_templates(user)
    with tab3: tab_segments(user)
    with tab4: tab_analytics(user)
    with tab5: tab_optouts(user)
    with tab6: tab_landing_pages(user)
