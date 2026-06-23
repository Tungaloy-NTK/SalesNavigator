import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date, timedelta
import database as db
from utils import smtp_connect

THRESHOLDS = [30, 45, 60]

# ── Email ───────────────────────────────────────────────────────────────────────

def send_email(to_addresses: list, subject: str, body_html: str):
    """Send email via Microsoft 365 SMTP. Silently fails if not configured."""
    smtp_host = db.get_setting("email_smtp_host") or "smtp.office365.com"
    smtp_port = int(db.get_setting("email_smtp_port") or 587)
    from_addr = db.get_setting("email_from") or ""
    password   = db.get_setting("email_password") or ""

    if not from_addr or not password:
        return False, "Email not configured (set credentials in Admin > Settings)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_addresses)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtp_connect(smtp_host, smtp_port, from_addr, password) as server:
            server.sendmail(from_addr, to_addresses, msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)

def _level_label(days):
    if days >= 60: return "CRITICAL (60+ days)"
    if days >= 45: return "WARNING (45+ days)"
    return "REMINDER (30+ days)"

def _level_colour(days):
    if days >= 60: return "#c0392b"
    if days >= 45: return "#e67e22"
    return "#f1c40f"

def _email_body(alerts: list, rep_name: str, is_digest: bool = False) -> str:
    rows = ""
    for a in alerts:
        colour = _level_colour(a["days"])
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee">{a['customer_name']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{a['type_label']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;color:{colour};font-weight:bold">
            {a['days']} days
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee">{a.get('rep_name','')}</td>
        </tr>"""

    title = "Daily Digest" if is_digest else "Action Required"
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#0a0a0a">
      <div style="background:#1a1a2e;padding:20px">
        <h2 style="color:#fff;margin:0">Tungaloy-NTK Sales Navigator</h2>
        <p style="color:#aaa;margin:4px 0 0">Customer Visit & Sales Alert — {title}</p>
      </div>
      <div style="padding:20px">
        <p>Hi {rep_name},</p>
        <p>The following customers require your attention:</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <thead>
            <tr style="background:#f0f2f6">
              <th style="padding:8px;text-align:left">Customer</th>
              <th style="padding:8px;text-align:left">Alert Type</th>
              <th style="padding:8px;text-align:left">Days Overdue</th>
              <th style="padding:8px;text-align:left">Rep</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px;font-size:12px;color:#888">
          Log your visits at the Tungaloy-NTK Sales Navigator.
        </p>
      </div>
    </body></html>"""

# ── Alert computation ───────────────────────────────────────────────────────────

def days_since(date_str):
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (date.today() - d).days
    except Exception:
        return None

def check_item_reorder_alerts(customer_code):
    """
    For each item this customer has ordered, check if it's overdue for reorder.
    Only flags items where the average reorder interval is <= 90 days
    (i.e. purchased more than once within a 3-month period).
    Returns list of dicts with item info and days overdue.
    """
    items = db.get_customer_items(customer_code)
    alerts = []
    for item in items:
        if item["order_count"] < 2:
            continue
        try:
            first = datetime.strptime(item["first_ordered"][:10], "%Y-%m-%d").date()
            last  = datetime.strptime(item["last_ordered"][:10], "%Y-%m-%d").date()
            span_days = (last - first).days
            avg_interval = span_days / max(item["order_count"] - 1, 1)
            if avg_interval < 1:
                continue
            # Only include items bought regularly within a 3-month cycle
            if avg_interval > 90:
                continue
            days_overdue = (date.today() - last).days - avg_interval
            if days_overdue > (avg_interval * 0.5):  # 50% overdue threshold
                alerts.append({
                    "item_code": item["item_code"],
                    "item_desc": item["item_desc"],
                    "last_ordered": item["last_ordered"],
                    "avg_interval_days": round(avg_interval),
                    "days_overdue": round(days_overdue),
                })
        except Exception:
            continue
    return alerts

def check_spending_trend(customer_code, months=3):
    """
    Returns 'declining', 'growing', 'stable', or None if insufficient data.
    Looks at last N months of sales.
    """
    monthly = db.get_monthly_sales(customer_code)
    if len(monthly) < months:
        return None
    recent = monthly[-months:]
    totals = [r["total_sales"] or 0 for r in recent]
    if all(totals[i] > totals[i+1] for i in range(len(totals)-1)):
        return "declining"
    if all(totals[i] < totals[i+1] for i in range(len(totals)-1)):
        return "growing"
    return "stable"

def compute_alerts(scope_user_id=None, role="admin"):
    """
    Compute live alerts for all customers in scope WITHOUT saving to the log
    or sending emails. Used by the Alerts page for always-fresh display.
    Returns list of alert dicts.
    """
    all_customers = db.get_all_customers()
    all_alerts = []

    for cust in all_customers:
        code    = cust["customer_code"]
        name    = cust["customer_name"]
        sm_name = cust["sm_name"]
        user_id = cust["user_id"]

        if not user_id:
            continue
        user = db.get_user_by_id(user_id)
        if not user:
            continue

        # Scope filter
        if role == "rep" and user_id != scope_user_id:
            continue
        if role == "regional_manager":
            team_ids = {scope_user_id} | {u["id"] for u in (db.get_team_members(scope_user_id) or [])}
            if user_id not in team_ids:
                continue

        last_purchase = db.get_last_purchase_date(code)
        last_visit    = db.get_last_visit_date(code)
        purchase_days = days_since(last_purchase)
        visit_days    = days_since(last_visit)

        def _add(alert_type, d, label):
            candidates = [t for t in THRESHOLDS if d >= t]
            level = max(candidates) if candidates else THRESHOLDS[0]
            all_alerts.append({
                "customer_code": code,
                "customer_name": name,
                "sm_name":       sm_name,
                "user_id":       user_id,
                "type":          alert_type,
                "type_label":    label,
                "days":          d,
                "level":         level,
                "rep_name":      user["full_name"],
            })

        if purchase_days is not None and purchase_days >= THRESHOLDS[0]:
            _add("no_purchase", purchase_days, "No Purchase")

        if last_purchase and visit_days is not None and visit_days >= THRESHOLDS[0]:
            _add("no_visit", visit_days, "No Visit")
        elif last_purchase and visit_days is None and purchase_days is not None and purchase_days >= THRESHOLDS[0]:
            _add("no_visit", purchase_days, "No Visit (never visited)")

        trend = check_spending_trend(code)
        if trend == "declining":
            _add("declining_spend", 0, "Declining Spend (3 months)")

    return all_alerts


def run_alerts(send_emails=True, digest_mode=False):
    """
    Main alert runner. Checks all customers, generates alerts, sends emails.
    Returns list of alert dicts generated this run.
    """
    if db.get_setting("alerts_enabled") != "true":
        return []

    high_value_threshold = float(db.get_setting("high_value_monthly_gbp") or 2000)
    all_customers = db.get_all_customers()

    # Group alerts by user for digest emails
    alerts_by_user = {}   # user_id → list of alert dicts
    all_alerts = []

    for cust in all_customers:
        code     = cust["customer_code"]
        name     = cust["customer_name"]
        sm_name  = cust["sm_name"]
        user_id  = cust["user_id"]

        if not user_id:
            continue

        user = db.get_user_by_id(user_id)
        if not user:
            continue

        last_purchase = db.get_last_purchase_date(code)
        last_visit    = db.get_last_visit_date(code)

        purchase_days = days_since(last_purchase)
        visit_days    = days_since(last_visit)

        def add_alert(alert_type, d, label):
            candidates = [t for t in THRESHOLDS if d >= t]
            level = max(candidates) if candidates else THRESHOLDS[0]
            if db.alert_already_sent_today(code, alert_type, level):
                return
            db.log_alert(code, name, sm_name, alert_type, level, d)
            alert = {
                "customer_code": code,
                "customer_name": name,
                "sm_name": sm_name,
                "user_id": user_id,
                "user": user,
                "type": alert_type,
                "type_label": label,
                "days": d,
                "level": level,
                "rep_name": user["full_name"],
            }
            all_alerts.append(alert)
            alerts_by_user.setdefault(user_id, []).append(alert)

        # No purchase alert
        if purchase_days is not None and purchase_days >= THRESHOLDS[0]:
            add_alert("no_purchase", purchase_days, "No Purchase")

        # No visit alert (only if there's been any purchase history)
        if last_purchase and visit_days is not None and visit_days >= THRESHOLDS[0]:
            add_alert("no_visit", visit_days, "No Visit")
        elif last_purchase and visit_days is None and purchase_days is not None and purchase_days >= THRESHOLDS[0]:
            add_alert("no_visit", purchase_days, "No Visit (never visited)")

        # Declining spend alert
        trend = check_spending_trend(code)
        if trend == "declining":
            if not db.alert_already_sent_today(code, "declining_spend", 0):
                db.log_alert(code, name, sm_name, "declining_spend", 0, 0)
                alert = {
                    "customer_code": code, "customer_name": name,
                    "sm_name": sm_name, "user_id": user_id, "user": user,
                    "type": "declining_spend", "type_label": "Declining Spend (3 months)",
                    "days": 0, "level": 45, "rep_name": user["full_name"],
                }
                all_alerts.append(alert)
                alerts_by_user.setdefault(user_id, []).append(alert)

    if not send_emails:
        return all_alerts

    admin_email = db.get_setting("email_from") or "Rob.Werhun@tungaloyuk.co.uk"

    # Send individual triggered emails (non-digest)
    if not digest_mode:
        for user_id, alerts in alerts_by_user.items():
            user = db.get_user_by_id(user_id)
            if not user:
                continue

            critical = [a for a in alerts if a["level"] >= 60]
            non_critical = [a for a in alerts if a["level"] < 60]

            if non_critical:
                body = _email_body(non_critical, user["full_name"])
                send_email([user["email"]], "Sales Navigator: Customers Requiring Attention", body)

            # Critical (60-day) — escalate to manager + Rob
            if critical:
                mgr_id = user["regional_manager_id"]
                recipients = [user["email"], admin_email]
                if mgr_id:
                    mgr = db.get_user_by_id(mgr_id)
                    if mgr and mgr["email"] not in recipients:
                        recipients.append(mgr["email"])
                body = _email_body(critical, user["full_name"])
                subject = f"CRITICAL: {len(critical)} Customer(s) Not Visited/Ordered in 60+ Days"
                send_email(recipients, subject, body)
    else:
        # Digest mode: one email per user summarising all their alerts
        for user_id, alerts in alerts_by_user.items():
            user = db.get_user_by_id(user_id)
            if not user:
                continue
            body = _email_body(alerts, user["full_name"], is_digest=True)
            send_email([user["email"]], "Sales Navigator: Daily Customer Alert Digest", body)

        # Admin digest
        if all_alerts:
            body = _email_body(all_alerts, "Rob", is_digest=True)
            send_email([admin_email], f"Sales Navigator: Daily Digest — {len(all_alerts)} Alerts", body)

    return all_alerts

def get_customer_status(customer_code):
    """
    Returns a status dict for a single customer:
    last_purchase, purchase_days, last_visit, visit_days,
    alert_level (0/30/45/60), trend, item_alerts
    """
    last_purchase = db.get_last_purchase_date(customer_code)
    last_visit    = db.get_last_visit_date(customer_code)
    purchase_days = days_since(last_purchase)
    visit_days    = days_since(last_visit)

    def level(d):
        if d is None: return 0
        for t in reversed(THRESHOLDS):
            if d >= t: return t
        return 0

    purchase_level = level(purchase_days)
    visit_level    = level(visit_days)
    overall_level  = max(purchase_level, visit_level)

    return {
        "last_purchase":   last_purchase,
        "purchase_days":   purchase_days,
        "purchase_level":  purchase_level,
        "last_visit":      last_visit,
        "visit_days":      visit_days,
        "visit_level":     visit_level,
        "overall_level":   overall_level,
        "trend":           check_spending_trend(customer_code),
        "item_alerts":     check_item_reorder_alerts(customer_code),
    }
