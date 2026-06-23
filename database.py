import sqlite3
import os
import time as _time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "sales_navigator.db")

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                regional_manager_id INTEGER,
                password_hash TEXT NOT NULL,
                must_change_password INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (regional_manager_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sm_name_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sm_name TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT UNIQUE NOT NULL,
                customer_name TEXT NOT NULL,
                sm_name TEXT NOT NULL,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                sm_name TEXT,
                item_code TEXT,
                item_desc TEXT,
                sale_date TEXT,
                month INTEGER,
                year INTEGER,
                unit_price REAL,
                unit_cost REAL,
                sales_val REAL,
                cost_val REAL,
                gp_val REAL,
                qty REAL,
                invoice_no TEXT,
                app_dsc TEXT,
                import_batch TEXT
            );

            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                visit_date TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                notes TEXT,
                outcome TEXT,
                next_action TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                customer_name TEXT,
                sm_name TEXT,
                alert_type TEXT NOT NULL,
                alert_level INTEGER NOT NULL,
                days_since INTEGER,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS test_tool_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT,
                customer_name TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                item_code TEXT NOT NULL,
                item_desc TEXT,
                quantity INTEGER NOT NULL,
                reason TEXT NOT NULL,
                reason_other TEXT,
                needed_by_date TEXT,
                material_being_cut TEXT,
                machine_type TEXT,
                competitor_tool TEXT,
                application_type TEXT,
                cutting_speed TEXT,
                feed_rate TEXT,
                depth_of_cut TEXT,
                width_of_cut TEXT,
                coolant TEXT,
                workpiece_material TEXT,
                hardness TEXT,
                notes TEXT,
                requested_by INTEGER NOT NULL,
                sm_name TEXT,
                status TEXT DEFAULT 'submitted',
                approved_by INTEGER,
                approved_at TEXT,
                rejection_reason TEXT,
                despatch_order_number TEXT,
                despatch_date TEXT,
                expected_delivery_date TEXT,
                despatched_by INTEGER,
                test_went_ahead TEXT,
                test_status TEXT,
                performance_vs_current TEXT,
                tool_life_achieved TEXT,
                customer_comments TEXT,
                outcome TEXT,
                estimated_order_value REAL,
                outcome_rejection_reason TEXT,
                surface_finish TEXT,
                parts_produced TEXT,
                test_report_notes TEXT,
                test_report_filename TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                last_followup_sent TEXT,
                followup_count INTEGER DEFAULT 0,
                FOREIGN KEY (requested_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS test_tool_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                update_type TEXT,
                old_status TEXT,
                new_status TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES test_tool_requests(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS marketing_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT,
                customer_name TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                contact_email TEXT,
                products_viewed TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                urgency TEXT NOT NULL,
                notes TEXT,
                submitted_by INTEGER NOT NULL,
                assigned_to INTEGER,
                sm_name TEXT,
                status TEXT DEFAULT 'pending',
                action_taken TEXT,
                action_notes TEXT,
                actioned_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_reminder_sent TEXT,
                reminder_count INTEGER DEFAULT 0,
                FOREIGN KEY (submitted_by) REFERENCES users(id),
                FOREIGN KEY (assigned_to) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS planned_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT,
                customer_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_by INTEGER,
                visit_date TEXT NOT NULL,
                visit_time TEXT,
                purpose TEXT,
                notes TEXT,
                status TEXT DEFAULT 'planned',
                completed_visit_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (assigned_by) REFERENCES users(id),
                FOREIGN KEY (completed_visit_id) REFERENCES visits(id)
            );

            CREATE TABLE IF NOT EXISTS customer_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                note_text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS news_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                action_required TEXT,
                action_deadline TEXT,
                posted_by INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (posted_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS news_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                read_at TEXT,
                action_completed_at TEXT,
                action_notes TEXT,
                FOREIGN KEY (news_id) REFERENCES news_posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(news_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                item_code TEXT UNIQUE NOT NULL,
                brand     TEXT,
                item_type TEXT
            );

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
                FOREIGN KEY (user_id)     REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS budget_2026 (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                app_code         TEXT NOT NULL,
                app_desc         TEXT,
                family           TEXT,
                product_line     TEXT,
                sales_budget     REAL,
                qty_budget       REAL,
                budget_jan       REAL, budget_feb  REAL, budget_mar  REAL,
                budget_apr       REAL, budget_may  REAL, budget_jun  REAL,
                budget_jul       REAL, budget_aug  REAL, budget_sep  REAL,
                budget_oct       REAL, budget_nov  REAL, budget_dec  REAL,
                UNIQUE(app_code)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                entity_label TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS customer_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                job_title TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crm_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                assigned_to INTEGER,
                created_by INTEGER,
                due_date TEXT,
                priority TEXT DEFAULT '🟡 Medium',
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (assigned_to) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS crm_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                filter_json TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS crm_segment_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                segment_id INTEGER NOT NULL,
                customer_code TEXT NOT NULL,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (segment_id) REFERENCES crm_segments(id),
                UNIQUE(segment_id, customer_code)
            );

            CREATE TABLE IF NOT EXISTS crm_prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                contact_name TEXT,
                email TEXT,
                job_title TEXT,
                region TEXT,
                post_code TEXT,
                sm_area TEXT,
                customer_type TEXT,
                tags TEXT,
                source TEXT,
                status TEXT DEFAULT 'new',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS email_opt_outs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                customer_code TEXT,
                opted_out_at TEXT,
                reason TEXT
            );

            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT,
                body_html TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS email_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                template_id INTEGER,
                segment_id INTEGER,
                from_name TEXT,
                from_email TEXT,
                reply_to TEXT,
                subject TEXT,
                body_html TEXT,
                status TEXT DEFAULT 'draft',
                scheduled_at TEXT,
                sent_at TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                total_sent INTEGER DEFAULT 0,
                total_opened INTEGER DEFAULT 0,
                total_clicked INTEGER DEFAULT 0,
                FOREIGN KEY (template_id) REFERENCES email_templates(id),
                FOREIGN KEY (segment_id) REFERENCES crm_segments(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS email_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                customer_code TEXT,
                contact_email TEXT NOT NULL,
                contact_name TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TEXT,
                open_count INTEGER DEFAULT 0,
                click_count INTEGER DEFAULT 0,
                unsubscribed INTEGER DEFAULT 0,
                bounced INTEGER DEFAULT 0,
                token TEXT UNIQUE,
                FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id),
                UNIQUE(campaign_id, contact_email)
            );

            CREATE TABLE IF NOT EXISTS email_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                send_id INTEGER NOT NULL,
                campaign_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (send_id) REFERENCES email_sends(id),
                FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id)
            );

            CREATE TABLE IF NOT EXISTS landing_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE,
                title TEXT,
                body_html TEXT,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                view_count INTEGER DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS consignment_warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                whs_code TEXT NOT NULL UNIQUE,
                customer_desc TEXT NOT NULL,
                customer_code TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Add extra columns to customers if they don't exist yet
        existing_cust = [r["name"] for r in conn.execute("PRAGMA table_info(customers)").fetchall()]
        for col, typedef in [
            ("addr_line1",       "TEXT"),
            ("addr_line2",       "TEXT"),
            ("addr_town",        "TEXT"),
            ("addr_postcode",    "TEXT"),
            ("post_area",        "TEXT"),
            ("main_distributor", "TEXT"),
            ("region",           "TEXT"),
            ("email",            "TEXT"),
            ("customer_type",    "TEXT"),
        ]:
            if col not in existing_cust:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {col} {typedef}")

        # Add new columns to test_tool_requests if they don't exist yet
        existing = [r["name"] for r in conn.execute("PRAGMA table_info(test_tool_requests)").fetchall()]
        for col, typedef in [
            ("contact2_name",         "TEXT"),
            ("contact2_email",        "TEXT"),
            ("trial_run_date",        "TEXT"),
            ("trial_completion_date", "TEXT"),
            ("ship_to_company",       "TEXT"),
            ("ship_to_address",       "TEXT"),
            ("ship_to_contact",       "TEXT"),
            ("ship_to_email",         "TEXT"),
            ("ship_to_phone",         "TEXT"),
            ("items",                 "TEXT"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE test_tool_requests ADD COLUMN {col} {typedef}")

        # Add ship_to_address and whs_code to sales if not present
        existing_sales = [r["name"] for r in conn.execute("PRAGMA table_info(sales)").fetchall()]
        if "ship_to_address" not in existing_sales:
            conn.execute("ALTER TABLE sales ADD COLUMN ship_to_address TEXT")
        if "whs_code" not in existing_sales:
            conn.execute("ALTER TABLE sales ADD COLUMN whs_code TEXT")

        # Add missing columns to customer_notes (note_type, contact_name)
        existing_notes = [r["name"] for r in conn.execute("PRAGMA table_info(customer_notes)").fetchall()]
        for col, typedef in [("note_type", "TEXT"), ("contact_name", "TEXT")]:
            if col not in existing_notes:
                conn.execute(f"ALTER TABLE customer_notes ADD COLUMN {col} {typedef}")

        # Add missing contact_name column to planned_visits
        existing_pv = [r["name"] for r in conn.execute("PRAGMA table_info(planned_visits)").fetchall()]
        if "contact_name" not in existing_pv:
            conn.execute("ALTER TABLE planned_visits ADD COLUMN contact_name TEXT")

        # Create expenses table if not present (migration for existing databases)
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
                FOREIGN KEY (user_id)     REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        """)

        # Add missing columns to expenses (migration for existing databases)
        existing_exp = [r["name"] for r in conn.execute("PRAGMA table_info(expenses)").fetchall()]
        for col, typedef in [("vat_amount", "REAL"), ("account_code", "TEXT")]:
            if col not in existing_exp:
                conn.execute(f"ALTER TABLE expenses ADD COLUMN {col} {typedef}")

        # Create budget_2026 table if not present (migration for existing databases)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budget_2026 (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                app_code         TEXT NOT NULL,
                app_desc         TEXT,
                family           TEXT,
                product_line     TEXT,
                sales_budget     REAL,
                qty_budget       REAL,
                budget_jan       REAL, budget_feb  REAL, budget_mar  REAL,
                budget_apr       REAL, budget_may  REAL, budget_jun  REAL,
                budget_jul       REAL, budget_aug  REAL, budget_sep  REAL,
                budget_oct       REAL, budget_nov  REAL, budget_dec  REAL,
                UNIQUE(app_code)
            )
        """)

        # ── Security tables ───────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_audit (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                username       TEXT NOT NULL,
                ip_address     TEXT,
                success        INTEGER NOT NULL,
                failure_reason TEXT,
                timestamp      TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Security columns on users
        existing_users = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        for col, typedef in [
            ("failed_login_attempts", "INTEGER DEFAULT 0"),
            ("locked_until",          "TEXT"),
            ("password_changed_at",   "TEXT"),
        ]:
            if col not in existing_users:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_audit_user ON login_audit(username, timestamp)")

        # Performance indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales(customer_code, sale_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_customer_date ON visits(customer_code, visit_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_user ON customers(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_smname_date ON sales(sm_name, sale_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_user_date ON visits(user_id, visit_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_log_customer ON alert_log(customer_code, alert_type, sent_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_assigned_status ON marketing_leads(assigned_to, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_code ON items(item_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_opt_outs_email ON email_opt_outs(email)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_contacts_code ON customer_contacts(customer_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sm_mapping_user ON sm_name_mapping(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planned_visits_user_date ON planned_visits(user_id, visit_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planned_visits_date ON planned_visits(visit_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_test_requests_status ON test_tool_requests(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_marketing_leads_status ON marketing_leads(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id, expense_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_recipients_user ON news_recipients(user_id, news_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_item_code ON sales(item_code)")

        # Default settings
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('no_purchase_thresholds', '30,45,60')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('no_visit_thresholds', '30,45,60')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('high_value_monthly_gbp', '2000')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('email_smtp_host', 'smtp.office365.com')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('email_smtp_port', '587')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('email_from', 'Rob.Werhun@tungaloyuk.co.uk')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('email_password', '')")
        conn.execute("INSERT OR IGNORE INTO settings VALUES ('alerts_enabled', 'true')")

def get_setting(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

def set_setting(key, value):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))

# ── Security / login audit ─────────────────────────────────────────────────────

def log_login_attempt(username, ip_address, success, failure_reason=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_audit (username, ip_address, success, failure_reason) VALUES (?,?,?,?)",
            (username, ip_address or "unknown", 1 if success else 0, failure_reason)
        )

def get_login_audit(limit=200):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM login_audit ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()

def increment_failed_logins(username):
    """Increments failed attempt counter. Returns new count."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET failed_login_attempts = COALESCE(failed_login_attempts,0)+1 WHERE username=?",
            (username,)
        )
        row = conn.execute(
            "SELECT failed_login_attempts FROM users WHERE username=?", (username,)
        ).fetchone()
        return row["failed_login_attempts"] if row else 1

def reset_failed_logins(user_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE id=?", (user_id,)
        )

def set_account_lock(username, locked_until_iso):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET locked_until=? WHERE username=?", (locked_until_iso, username)
        )

def update_password_changed_at(user_id):
    from datetime import datetime
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_changed_at=? WHERE id=?",
            (datetime.now().isoformat(), user_id)
        )

# ── In-memory cache ───────────────────────────────────────────────────────────

_cache = {}
_CACHE_TTL = 30  # seconds

def _cached(key, fn, ttl=_CACHE_TTL):
    """Simple TTL cache for frequently-called read-only queries."""
    now = _time.time()
    if key in _cache and (now - _cache[key][1]) < ttl:
        return _cache[key][0]
    result = fn()
    _cache[key] = (result, now)
    return result

def invalidate_cache(prefix=None):
    """Clear cache entries. Call after writes that affect cached data."""
    global _cache
    if prefix:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(prefix)}
    else:
        _cache = {}

# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_username(username):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()

def get_user_by_id(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

def get_all_users():
    return _cached("all_users", lambda: _get_all_users_raw())

def _get_all_users_raw():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()

def get_reps_and_managers():
    """Return active users with role rep or regional_manager. Cached."""
    return _cached("reps_and_managers", lambda: _get_reps_and_managers_raw())

def _get_reps_and_managers_raw():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE role IN ('rep','regional_manager') AND is_active=1 ORDER BY full_name"
        ).fetchall()

def get_all_sm_names():
    """Return all SM names that have a mapping to a rep/regional_manager."""
    return _cached("all_sm_names", lambda: _get_all_sm_names_raw())

def _get_all_sm_names_raw():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT sm.sm_name FROM sm_name_mapping sm
            JOIN users u ON sm.user_id = u.id
            WHERE u.role IN ('rep','regional_manager')
            ORDER BY sm.sm_name
        """).fetchall()
        return [r["sm_name"] for r in rows]

def get_team_members(regional_manager_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE regional_manager_id=? AND is_active=1 ORDER BY full_name",
            (regional_manager_id,)
        ).fetchall()

def update_password(user_id, password_hash):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
            (password_hash, user_id)
        )
    invalidate_cache("all_users")

def upsert_user(username, full_name, email, role, regional_manager_id, password_hash):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (username, full_name, email, role, regional_manager_id, password_hash)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(username) DO UPDATE SET
                full_name=excluded.full_name,
                email=excluded.email,
                role=excluded.role,
                regional_manager_id=excluded.regional_manager_id
        """, (username, full_name, email, role, regional_manager_id, password_hash))
    invalidate_cache("all_users")

def get_sm_names_for_user(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT sm_name FROM sm_name_mapping WHERE user_id=?", (user_id,)
        ).fetchall()
        return [r["sm_name"] for r in rows]

def get_user_id_for_sm_name(sm_name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM sm_name_mapping WHERE sm_name=?", (sm_name,)
        ).fetchone()
        return row["user_id"] if row else None

def get_all_sm_name_mappings():
    """Returns full {sm_name: user_id} dict in one query."""
    with get_conn() as conn:
        rows = conn.execute("SELECT sm_name, user_id FROM sm_name_mapping").fetchall()
        return {r["sm_name"]: r["user_id"] for r in rows}

# ── Customers ──────────────────────────────────────────────────────────────────

def get_hub_counts(user_id, role):
    """Fast single-query hub counts — no per-customer looping."""
    with get_conn() as conn:
        # Build WHERE clause for role
        if role == "rep":
            where = "WHERE c.user_id = ?"
            params = [user_id]
        elif role == "regional_manager":
            where = "WHERE (c.user_id = ? OR c.user_id IN (SELECT id FROM users WHERE regional_manager_id=?))"
            params = [user_id, user_id]
        else:
            where = ""
            params = []

        row = conn.execute(f"""
            SELECT
                COUNT(DISTINCT c.customer_code) as total_customers,
                SUM(CASE WHEN (
                    CAST(julianday('now') - julianday(ls.last_sale) AS INTEGER) >= 30
                    OR
                    CAST(julianday('now') - julianday(lv.last_visit) AS INTEGER) >= 30
                ) THEN 1 ELSE 0 END) as alert_count
            FROM customers c
            LEFT JOIN (
                SELECT customer_code, MAX(sale_date) as last_sale
                FROM sales GROUP BY customer_code
            ) ls ON ls.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, MAX(visit_date) as last_visit
                FROM visits GROUP BY customer_code
            ) lv ON lv.customer_code = c.customer_code
            {where}
        """, params).fetchone()

        return {
            "total_customers": row["total_customers"] or 0,
            "alert_count":     row["alert_count"] or 0,
        }

_CUSTOMER_STATUS_SQL = """
    SELECT
        c.*,
        u.full_name                                                              AS rep_name,
        ls.last_sale,
        lv.last_visit,
        CAST(julianday('now') - julianday(ls.last_sale)  AS INTEGER)            AS purchase_days,
        CAST(julianday('now') - julianday(lv.last_visit) AS INTEGER)            AS visit_days,
        COALESCE(lms.last_month_sales, 0)                                       AS last_month_sales
    FROM customers c
    LEFT JOIN users u ON c.user_id = u.id
    LEFT JOIN (
        SELECT customer_code, MAX(sale_date) AS last_sale
        FROM sales GROUP BY customer_code
    ) ls ON ls.customer_code = c.customer_code
    LEFT JOIN (
        SELECT customer_code, MAX(visit_date) AS last_visit
        FROM visits GROUP BY customer_code
    ) lv ON lv.customer_code = c.customer_code
    LEFT JOIN (
        SELECT customer_code, SUM(sales_val) AS last_month_sales
        FROM sales
        WHERE strftime('%Y-%m', sale_date) = (
            SELECT strftime('%Y-%m', MAX(sale_date)) FROM sales
        )
        GROUP BY customer_code
    ) lms ON lms.customer_code = c.customer_code
"""

def get_customers_for_user(user_id):
    with get_conn() as conn:
        return conn.execute(
            _CUSTOMER_STATUS_SQL + " WHERE c.user_id=? ORDER BY c.customer_name",
            (user_id,)
        ).fetchall()

def get_customers_for_team(regional_manager_id):
    with get_conn() as conn:
        return conn.execute(
            _CUSTOMER_STATUS_SQL + " WHERE u.regional_manager_id=? OR u.id=? ORDER BY u.full_name, c.customer_name",
            (regional_manager_id, regional_manager_id)
        ).fetchall()

def get_all_customers():
    return _cached("all_customers", lambda: _get_all_customers_raw(), ttl=15)

def _get_all_customers_raw():
    with get_conn() as conn:
        return conn.execute(
            _CUSTOMER_STATUS_SQL + " ORDER BY u.full_name, c.customer_name"
        ).fetchall()

def get_customer(customer_code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM customers WHERE customer_code=?", (customer_code,)
        ).fetchone()

# ── Sales ──────────────────────────────────────────────────────────────────────

def get_last_purchase_date(customer_code):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(sale_date) as last_date FROM sales WHERE customer_code=?",
            (customer_code,)
        ).fetchone()
        return row["last_date"] if row else None

def get_monthly_sales(customer_code):
    with get_conn() as conn:
        return conn.execute("""
            SELECT year, month, SUM(sales_val) as total_sales, SUM(gp_val) as total_gp
            FROM sales WHERE customer_code=?
            GROUP BY year, month
            ORDER BY year, month
        """, (customer_code,)).fetchall()

def get_customer_items(customer_code):
    with get_conn() as conn:
        return conn.execute("""
            SELECT item_code, item_desc,
                   COUNT(*) as order_count,
                   MAX(sale_date) as last_ordered,
                   MIN(sale_date) as first_ordered,
                   SUM(qty) as total_qty,
                   SUM(sales_val) as total_sales
            FROM sales
            WHERE customer_code=? AND item_code IS NOT NULL AND item_code != ''
            GROUP BY item_code, item_desc
            ORDER BY last_ordered DESC
        """, (customer_code,)).fetchall()

def get_sales_summary_for_user(user_id):
    sm_names = get_sm_names_for_user(user_id)
    if not sm_names:
        return []
    placeholders = ",".join("?" * len(sm_names))
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT customer_code, SUM(sales_val) as total_sales,
                   MAX(sale_date) as last_purchase,
                   year, month
            FROM sales WHERE sm_name IN ({placeholders})
            GROUP BY customer_code
        """, sm_names).fetchall()

def get_recent_sales_import_batches():
    with get_conn() as conn:
        return conn.execute(
            "SELECT DISTINCT import_batch FROM sales ORDER BY import_batch DESC LIMIT 10"
        ).fetchall()

# ── Visits ──────────────────────────────────────────────────────────────────────

def log_visit(customer_code, customer_name, user_id, visit_date, contact_name,
              notes=None, outcome=None, next_action=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO visits (customer_code, customer_name, user_id, visit_date,
                                contact_name, notes, outcome, next_action)
            VALUES (?,?,?,?,?,?,?,?)
        """, (customer_code, customer_name, user_id, visit_date,
              contact_name, notes, outcome, next_action))

def get_visits_for_customer(customer_code):
    with get_conn() as conn:
        return conn.execute("""
            SELECT v.*, u.full_name as rep_name
            FROM visits v JOIN users u ON v.user_id=u.id
            WHERE v.customer_code=?
            ORDER BY v.visit_date DESC
        """, (customer_code,)).fetchall()

def get_last_visit_date(customer_code):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(visit_date) as last_date FROM visits WHERE customer_code=?",
            (customer_code,)
        ).fetchone()
        return row["last_date"] if row else None

def get_visits_for_user(user_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT v.*, u.full_name as rep_name
            FROM visits v JOIN users u ON v.user_id=u.id
            WHERE v.user_id=?
            ORDER BY v.visit_date DESC
        """, (user_id,)).fetchall()

# ── Alert log ──────────────────────────────────────────────────────────────────

def alert_already_sent_today(customer_code, alert_type, alert_level):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT id FROM alert_log
            WHERE customer_code=? AND alert_type=? AND alert_level=?
            AND date(sent_at) = date('now')
        """, (customer_code, alert_type, alert_level)).fetchone()
        return row is not None

def log_alert(customer_code, customer_name, sm_name, alert_type, alert_level, days_since):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO alert_log (customer_code, customer_name, sm_name, alert_type, alert_level, days_since)
            VALUES (?,?,?,?,?,?)
        """, (customer_code, customer_name, sm_name, alert_type, alert_level, days_since))

# ── Audit Trail ───────────────────────────────────────────────────────────────

def log_audit(user_id, user_name, action, entity_type, entity_id=None, entity_label=None, details=None):
    """Log an action to the audit trail.
    action: 'create', 'update', 'delete', 'login', 'logout', 'import', 'export'
    entity_type: 'visit', 'contact', 'note', 'task', 'test_request', 'marketing_lead',
                 'planned_visit', 'news', 'expense', 'customer', 'user', 'setting', 'campaign', 'sales_data'
    """
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, user_name, action, entity_type, entity_id, entity_label, details) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, user_name, action, entity_type, str(entity_id) if entity_id else None,
             entity_label, details)
        )

def get_audit_log(limit=100, offset=0, user_id=None, entity_type=None, action=None):
    """Retrieve audit log entries with optional filters."""
    with get_conn() as conn:
        conditions = []
        params = []
        if user_id:
            conditions.append("a.user_id = ?")
            params.append(user_id)
        if entity_type:
            conditions.append("a.entity_type = ?")
            params.append(entity_type)
        if action:
            conditions.append("a.action = ?")
            params.append(action)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        return conn.execute(f"""
            SELECT a.*, u.full_name as actor_name
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            {where}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
        """, params).fetchall()

def get_audit_log_count(user_id=None, entity_type=None, action=None):
    """Count audit log entries with optional filters."""
    with get_conn() as conn:
        conditions = []
        params = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if action:
            conditions.append("action = ?")
            params.append(action)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        row = conn.execute(f"SELECT COUNT(*) as c FROM audit_log{where}", params).fetchone()
        return row["c"]

# ── Reorder Alerts ────────────────────────────────────────────────────────────

def get_reorder_alerts(user_id=None, role="rep"):
    """
    Identify customers who are due to reorder based on their historical ordering pattern.
    Returns customers where days_since_last_order > avg_order_interval - 5 (i.e. due within 5 days or overdue).
    """
    with get_conn() as conn:
        role_clause = ""
        params = []
        if role == "rep" and user_id:
            role_clause = "AND c.user_id = ?"
            params.append(user_id)
        elif role == "regional_manager" and user_id:
            role_clause = "AND (c.user_id = ? OR c.user_id IN (SELECT id FROM users WHERE regional_manager_id = ?))"
            params.extend([user_id, user_id])

        return conn.execute(f"""
            WITH order_dates AS (
                SELECT customer_code,
                       sale_date,
                       LAG(sale_date) OVER (PARTITION BY customer_code ORDER BY sale_date) AS prev_date
                FROM (
                    SELECT DISTINCT customer_code, sale_date
                    FROM sales
                    WHERE sale_date IS NOT NULL
                )
            ),
            intervals AS (
                SELECT customer_code,
                       AVG(CAST(julianday(sale_date) - julianday(prev_date) AS INTEGER)) AS avg_interval,
                       COUNT(*) AS order_count
                FROM order_dates
                WHERE prev_date IS NOT NULL
                GROUP BY customer_code
                HAVING COUNT(*) >= 3
            )
            SELECT
                c.customer_code,
                COALESCE(c.customer_name, c.customer_code) AS customer_name,
                c.sm_name,
                u.full_name AS rep_name,
                ROUND(i.avg_interval, 0) AS avg_days_between_orders,
                ls.last_sale AS last_order_date,
                CAST(julianday('now') - julianday(ls.last_sale) AS INTEGER) AS days_since_last_order,
                ROUND(i.avg_interval - (julianday('now') - julianday(ls.last_sale)), 0) AS days_until_expected,
                i.order_count AS historical_orders,
                COALESCE(lms.recent_sales, 0) AS recent_monthly_sales
            FROM intervals i
            JOIN customers c ON c.customer_code = i.customer_code
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN (
                SELECT customer_code, MAX(sale_date) AS last_sale
                FROM sales GROUP BY customer_code
            ) ls ON ls.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, SUM(sales_val) AS recent_sales
                FROM sales
                WHERE sale_date >= date('now', '-90 days')
                GROUP BY customer_code
            ) lms ON lms.customer_code = c.customer_code
            WHERE CAST(julianday('now') - julianday(ls.last_sale) AS INTEGER) >= (i.avg_interval - 5)
            {role_clause}
            ORDER BY days_until_expected ASC
        """, params).fetchall()

# ── Test Tool Requests ─────────────────────────────────────────────────────────

def create_test_request(data: dict):
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO test_tool_requests ({','.join(cols)}) VALUES ({placeholders})",
            [data[c] for c in cols]
        )
        return cur.lastrowid

def get_test_request(request_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id WHERE t.id=?", (request_id,)
        ).fetchone()

def get_test_requests_for_user(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id WHERE t.requested_by=? "
            "ORDER BY t.created_at DESC", (user_id,)
        ).fetchall()

def get_test_requests_for_team(regional_manager_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id "
            "WHERE u.regional_manager_id=? OR u.id=? "
            "ORDER BY t.created_at DESC", (regional_manager_id, regional_manager_id)
        ).fetchall()

def get_all_test_requests():
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id ORDER BY t.created_at DESC"
        ).fetchall()

def get_test_requests_pending_approval():
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id WHERE t.status='submitted' "
            "ORDER BY t.created_at ASC"
        ).fetchall()

def get_test_requests_needing_followup():
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.*, u.full_name as requester_name FROM test_tool_requests t "
            "JOIN users u ON t.requested_by=u.id "
            "WHERE t.status='despatched' AND t.outcome IS NULL "
            "ORDER BY t.despatch_date ASC"
        ).fetchall()

def update_test_request(request_id, updates: dict):
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [request_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE test_tool_requests SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)

def log_test_update(request_id, user_id, update_type, old_status, new_status, notes=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO test_tool_updates (request_id,user_id,update_type,old_status,new_status,notes) "
            "VALUES (?,?,?,?,?,?)",
            (request_id, user_id, update_type, old_status, new_status, notes)
        )

def get_test_updates(request_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT tu.*, u.full_name FROM test_tool_updates tu "
            "JOIN users u ON tu.user_id=u.id WHERE tu.request_id=? "
            "ORDER BY tu.created_at DESC", (request_id,)
        ).fetchall()

# ── Marketing Leads ────────────────────────────────────────────────────────────

def create_marketing_lead(data: dict):
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO marketing_leads ({','.join(cols)}) VALUES ({placeholders})",
            [data[c] for c in cols]
        )
        return cur.lastrowid

def get_marketing_lead(lead_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT m.*, u.full_name as submitter_name, a.full_name as rep_name "
            "FROM marketing_leads m "
            "JOIN users u ON m.submitted_by=u.id "
            "LEFT JOIN users a ON m.assigned_to=a.id "
            "WHERE m.id=?", (lead_id,)
        ).fetchone()

def get_marketing_leads_for_rep(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT m.*, u.full_name as submitter_name, a.full_name as rep_name "
            "FROM marketing_leads m "
            "JOIN users u ON m.submitted_by=u.id "
            "LEFT JOIN users a ON m.assigned_to=a.id "
            "WHERE m.assigned_to=? ORDER BY m.created_at DESC", (user_id,)
        ).fetchall()

def get_all_marketing_leads():
    with get_conn() as conn:
        return conn.execute(
            "SELECT m.*, u.full_name as submitter_name, a.full_name as rep_name "
            "FROM marketing_leads m "
            "JOIN users u ON m.submitted_by=u.id "
            "LEFT JOIN users a ON m.assigned_to=a.id "
            "ORDER BY m.created_at DESC"
        ).fetchall()

def get_pending_marketing_leads_count(user_id=None):
    with get_conn() as conn:
        if user_id:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM marketing_leads WHERE assigned_to=? AND status='pending'",
                (user_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as c FROM marketing_leads WHERE status='pending'").fetchone()
        return row["c"]

def update_marketing_lead(lead_id, updates: dict):
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [lead_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE marketing_leads SET {sets} WHERE id=?", vals)

# ── Planned Visits ─────────────────────────────────────────────────────────────

def create_planned_visit(data: dict):
    cols = list(data.keys())
    placeholders = ",".join(["?"] * len(cols))
    with get_conn() as conn:
        cur = conn.execute(
            f"INSERT INTO planned_visits ({','.join(cols)}) VALUES ({placeholders})",
            [data[c] for c in cols]
        )
        return cur.lastrowid

def get_planned_visits_for_user(user_id, month=None, year=None):
    with get_conn() as conn:
        sql = ("SELECT pv.*, u.full_name as rep_name, ab.full_name as assigned_by_name "
               "FROM planned_visits pv "
               "JOIN users u ON pv.user_id=u.id "
               "LEFT JOIN users ab ON pv.assigned_by=ab.id "
               "WHERE pv.user_id=?")
        params = [user_id]
        if month and year:
            sql += " AND CAST(strftime('%m', pv.visit_date) AS INTEGER)=? AND CAST(strftime('%Y', pv.visit_date) AS INTEGER)=?"
            params += [month, year]
        sql += " ORDER BY pv.visit_date"
        return conn.execute(sql, params).fetchall()

def get_planned_visits_for_team(manager_id, month=None, year=None):
    with get_conn() as conn:
        sql = ("SELECT pv.*, u.full_name as rep_name, ab.full_name as assigned_by_name "
               "FROM planned_visits pv "
               "JOIN users u ON pv.user_id=u.id "
               "LEFT JOIN users ab ON pv.assigned_by=ab.id "
               "WHERE (u.regional_manager_id=? OR u.id=?)")
        params = [manager_id, manager_id]
        if month and year:
            sql += " AND CAST(strftime('%m', pv.visit_date) AS INTEGER)=? AND CAST(strftime('%Y', pv.visit_date) AS INTEGER)=?"
            params += [month, year]
        sql += " ORDER BY pv.visit_date"
        return conn.execute(sql, params).fetchall()

def get_all_planned_visits(month=None, year=None):
    with get_conn() as conn:
        sql = ("SELECT pv.*, u.full_name as rep_name, ab.full_name as assigned_by_name "
               "FROM planned_visits pv "
               "JOIN users u ON pv.user_id=u.id "
               "LEFT JOIN users ab ON pv.assigned_by=ab.id WHERE 1=1")
        params = []
        if month and year:
            sql += " AND CAST(strftime('%m', pv.visit_date) AS INTEGER)=? AND CAST(strftime('%Y', pv.visit_date) AS INTEGER)=?"
            params += [month, year]
        sql += " ORDER BY pv.visit_date"
        return conn.execute(sql, params).fetchall()

def update_planned_visit(visit_id, updates: dict):
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [visit_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE planned_visits SET {sets} WHERE id=?", vals)

def delete_planned_visit(visit_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM planned_visits WHERE id=?", (visit_id,))

# ── Customer Notes ─────────────────────────────────────────────────────────────

def add_customer_note(customer_code, user_id, note_text):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO customer_notes (customer_code, user_id, note_text) VALUES (?,?,?)",
            (customer_code, user_id, note_text)
        )

def get_customer_notes(customer_code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT cn.*, u.full_name FROM customer_notes cn "
            "JOIN users u ON cn.user_id=u.id WHERE cn.customer_code=? "
            "ORDER BY cn.created_at DESC", (customer_code,)
        ).fetchall()

# ── News / Announcements ──────────────────────────────────────────────────────

def create_news_post(title, body, action_required, action_deadline, posted_by, recipient_ids):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO news_posts (title, body, action_required, action_deadline, posted_by) "
            "VALUES (?,?,?,?,?)",
            (title, body, action_required, action_deadline, posted_by)
        )
        news_id = cur.lastrowid
        for uid in recipient_ids:
            conn.execute(
                "INSERT INTO news_recipients (news_id, user_id) VALUES (?,?)",
                (news_id, uid)
            )
        return news_id

def get_news_for_user(user_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT np.*, nr.read_at, nr.action_completed_at, nr.action_notes, "
            "u.full_name as posted_by_name "
            "FROM news_posts np "
            "JOIN news_recipients nr ON np.id=nr.news_id "
            "JOIN users u ON np.posted_by=u.id "
            "WHERE nr.user_id=? ORDER BY np.created_at DESC", (user_id,)
        ).fetchall()

def get_all_news():
    with get_conn() as conn:
        return conn.execute(
            "SELECT np.*, u.full_name as posted_by_name, "
            "(SELECT COUNT(*) FROM news_recipients WHERE news_id=np.id) as total_recipients, "
            "(SELECT COUNT(*) FROM news_recipients WHERE news_id=np.id AND read_at IS NOT NULL) as read_count, "
            "(SELECT COUNT(*) FROM news_recipients WHERE news_id=np.id AND action_completed_at IS NOT NULL) as action_count "
            "FROM news_posts np JOIN users u ON np.posted_by=u.id "
            "ORDER BY np.created_at DESC"
        ).fetchall()

def mark_news_read(news_id, user_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE news_recipients SET read_at=CURRENT_TIMESTAMP WHERE news_id=? AND user_id=?",
            (news_id, user_id)
        )

def complete_news_action(news_id, user_id, action_notes=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE news_recipients SET action_completed_at=CURRENT_TIMESTAMP, action_notes=? "
            "WHERE news_id=? AND user_id=?",
            (action_notes, news_id, user_id)
        )

def get_news_recipients(news_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT nr.*, u.full_name FROM news_recipients nr "
            "JOIN users u ON nr.user_id=u.id WHERE nr.news_id=? "
            "ORDER BY u.full_name", (news_id,)
        ).fetchall()

# ── League Table queries ──────────────────────────────────────────────────────

def _date_clause(date_from=None, date_to=None, col="s.sale_date"):
    """Returns (extra_where_sql, params_list) for optional date filtering."""
    parts, params = [], []
    if date_from:
        parts.append(f"{col} >= ?")
        params.append(str(date_from))
    if date_to:
        parts.append(f"{col} <= ?")
        params.append(str(date_to))
    return (" AND " + " AND ".join(parts) if parts else ""), params

def get_league_date_range():
    """Returns (min_date, max_date) of sales data as strings."""
    with get_conn() as conn:
        row = conn.execute("SELECT MIN(sale_date) as mn, MAX(sale_date) as mx FROM sales").fetchone()
        return row["mn"], row["mx"]

def get_league_reps_by_sales(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.sm_name, SUM(s.sales_val) as total_sales
            FROM sales s
            JOIN sm_name_mapping sm ON s.sm_name=sm.sm_name
            JOIN users u ON sm.user_id=u.id
            WHERE u.role IN ('rep','regional_manager'){clause}
            GROUP BY s.sm_name ORDER BY total_sales DESC
        """, params).fetchall()

def get_league_reps_by_sales_growth(date_from, date_to):
    """Compare sales in selected period vs same period one year prior, ranked by growth %, grouped by SM name."""
    prior_from = date_from.replace(year=date_from.year - 1)
    prior_to   = date_to.replace(year=date_to.year - 1)
    with get_conn() as conn:
        return conn.execute("""
            SELECT
                s.sm_name,
                SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) AS current_sales,
                SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) AS prior_sales,
                SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) -
                SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) AS growth_val,
                CASE WHEN SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) > 0
                     THEN ROUND(
                         (SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END) -
                          SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END)) * 100.0 /
                          SUM(CASE WHEN s.sale_date BETWEEN ? AND ? THEN s.sales_val ELSE 0 END), 1)
                     ELSE NULL END AS growth_pct
            FROM sales s
            JOIN sm_name_mapping sm ON s.sm_name = sm.sm_name
            JOIN users u ON sm.user_id = u.id
            WHERE u.role IN ('rep','regional_manager')
              AND (s.sale_date BETWEEN ? AND ? OR s.sale_date BETWEEN ? AND ?)
            GROUP BY s.sm_name
            ORDER BY growth_pct DESC
        """, (
            str(date_from), str(date_to),       # current_sales
            str(prior_from), str(prior_to),     # prior_sales
            str(date_from), str(date_to),       # growth_val current
            str(prior_from), str(prior_to),     # growth_val prior
            str(prior_from), str(prior_to),     # growth_pct denominator check
            str(date_from), str(date_to),       # growth_pct numerator current
            str(prior_from), str(prior_to),     # growth_pct numerator prior
            str(prior_from), str(prior_to),     # growth_pct denominator
            str(date_from), str(date_to),       # WHERE current period
            str(prior_from), str(prior_to),     # WHERE prior period
        )).fetchall()

def get_league_reps_by_gp(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.sm_name, SUM(s.gp_val) as total_gp
            FROM sales s
            JOIN sm_name_mapping sm ON s.sm_name=sm.sm_name
            JOIN users u ON sm.user_id=u.id
            WHERE u.role IN ('rep','regional_manager'){clause}
            GROUP BY s.sm_name ORDER BY total_gp DESC
        """, params).fetchall()

def get_league_reps_by_gp_pct(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.sm_name,
                   SUM(s.gp_val)    as total_gp,
                   SUM(s.sales_val) as total_sales,
                   CASE WHEN SUM(s.sales_val) > 0
                        THEN ROUND(SUM(s.gp_val) * 100.0 / SUM(s.sales_val), 1)
                        ELSE 0 END  as gp_pct
            FROM sales s
            JOIN sm_name_mapping sm ON s.sm_name=sm.sm_name
            JOIN users u ON sm.user_id=u.id
            WHERE u.role IN ('rep','regional_manager'){clause}
            GROUP BY s.sm_name
            HAVING SUM(s.sales_val) > 0
            ORDER BY gp_pct DESC
        """, params).fetchall()

def get_league_reps_by_visits(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to, col="v.visit_date")
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT u.full_name, COUNT(v.id) as visit_count
            FROM visits v
            JOIN users u ON v.user_id=u.id
            WHERE u.role IN ('rep','regional_manager'){clause}
            GROUP BY u.id ORDER BY visit_count DESC
        """, params).fetchall()

def get_league_customers_by_spend(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT customer_code, MAX(s.sm_name) as sm_name,
                   SUM(s.sales_val) as total_sales
            FROM sales s
            WHERE 1=1{clause}
            GROUP BY customer_code
            ORDER BY total_sales DESC LIMIT 50
        """, params).fetchall()

def get_league_items_by_qty(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.item_code, MAX(s.item_desc) as item_desc,
                   SUM(s.qty) as total_qty, SUM(s.sales_val) as total_sales
            FROM sales s WHERE s.item_code IS NOT NULL AND s.item_code != ''{clause}
            GROUP BY s.item_code ORDER BY total_qty DESC LIMIT 50
        """, params).fetchall()

def get_league_items_by_sales(date_from=None, date_to=None):
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.item_code, MAX(s.item_desc) as item_desc,
                   SUM(s.qty) as total_qty, SUM(s.sales_val) as total_sales
            FROM sales s WHERE s.item_code IS NOT NULL AND s.item_code != ''{clause}
            GROUP BY s.item_code ORDER BY total_sales DESC LIMIT 50
        """, params).fetchall()

def get_league_app_dsc_by_qty(date_from=None, date_to=None, sm_name=None):
    clause, params = _date_clause(date_from, date_to)
    sm_clause = ""
    if sm_name:
        sm_clause = " AND s.sm_name = ?"
        params = list(params) + [sm_name]
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.app_dsc, SUM(s.qty) as total_qty, SUM(s.sales_val) as total_sales
            FROM sales s
            WHERE s.app_dsc IS NOT NULL AND s.app_dsc != ''{clause}{sm_clause}
            GROUP BY s.app_dsc ORDER BY total_qty DESC LIMIT 30
        """, params).fetchall()

def get_league_app_dsc_by_sales(date_from=None, date_to=None, sm_name=None):
    clause, params = _date_clause(date_from, date_to)
    sm_clause = ""
    if sm_name:
        sm_clause = " AND s.sm_name = ?"
        params = list(params) + [sm_name]
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT s.app_dsc, SUM(s.qty) as total_qty, SUM(s.sales_val) as total_sales
            FROM sales s
            WHERE s.app_dsc IS NOT NULL AND s.app_dsc != ''{clause}{sm_clause}
            GROUP BY s.app_dsc ORDER BY total_sales DESC LIMIT 30
        """, params).fetchall()

def get_league_zero_price_holders(date_from=None, date_to=None):
    """Reps ranked by qty of Holder items sold at zero unit price."""
    clause, params = _date_clause(date_from, date_to)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT u.full_name,
                   SUM(s.qty)   AS total_qty,
                   COUNT(*)     AS line_count
            FROM   sales s
            JOIN   items i        ON s.item_code = i.item_code
            JOIN   sm_name_mapping sm ON s.sm_name = sm.sm_name
            JOIN   users u        ON sm.user_id  = u.id
            WHERE  LOWER(COALESCE(i.item_type,'')) LIKE '%holder%'
              AND  s.qty        >= 1
              AND  s.unit_price  = 0
              {clause}
            GROUP  BY u.full_name
            ORDER  BY total_qty DESC
        """, params).fetchall()

def get_league_zero_price_holders_by_customer(date_from=None, date_to=None, sm_name=None):
    """Customers ranked by qty of Holder items received at zero unit price. Optionally filter by SM name."""
    clause, params = _date_clause(date_from, date_to)
    rep_clause = ""
    if sm_name:
        rep_clause = "AND s.sm_name = ?"
        params = list(params) + [sm_name]
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT COALESCE(c.customer_name, s.customer_code) AS customer_name,
                   s.customer_code,
                   s.sm_name    AS rep_name,
                   SUM(s.qty)   AS total_qty,
                   COUNT(*)     AS line_count
            FROM   sales s
            LEFT JOIN customers c         ON s.customer_code = c.customer_code
            JOIN   items i                ON s.item_code     = i.item_code
            JOIN   sm_name_mapping sm     ON s.sm_name       = sm.sm_name
            JOIN   users u                ON sm.user_id      = u.id
            WHERE  LOWER(COALESCE(i.item_type,'')) LIKE '%holder%'
              AND  s.qty        >= 1
              AND  s.unit_price  = 0
              {clause}
              {rep_clause}
            GROUP  BY s.customer_code
            ORDER  BY total_qty DESC
        """, params).fetchall()

# ── Alert log ──────────────────────────────────────────────────────────────────

def get_report_data(user_id, role,
                    date_from=None, date_to=None,
                    sm_names=None, customer_codes=None,
                    customer_search=None, item_search=None,
                    app_filter=None,
                    region_filter=None, customer_type_filter=None,
                    post_area_filter=None, distributor_filter=None,
                    brand_filter=None, item_type_filter=None):
    """
    Flexible sales report query scoped by role.
    Returns list of dicts with all key sales columns.
    """
    with get_conn() as conn:
        conditions = []
        params = []

        # Role scoping
        if role == "rep":
            rep_sm_names = [r["sm_name"] for r in conn.execute(
                "SELECT sm_name FROM sm_name_mapping WHERE user_id=?", (user_id,)).fetchall()]
            if not rep_sm_names:
                return []
            placeholders = ",".join("?" * len(rep_sm_names))
            conditions.append(f"s.sm_name IN ({placeholders})")
            params.extend(rep_sm_names)
        elif role == "regional_manager" and sm_names:
            placeholders = ",".join("?" * len(sm_names))
            conditions.append(f"s.sm_name IN ({placeholders})")
            params.extend(sm_names)
        elif sm_names:
            placeholders = ",".join("?" * len(sm_names))
            conditions.append(f"s.sm_name IN ({placeholders})")
            params.extend(sm_names)

        if customer_codes:
            placeholders = ",".join("?" * len(customer_codes))
            conditions.append(f"s.customer_code IN ({placeholders})")
            params.extend(customer_codes)
        if date_from:
            conditions.append("s.sale_date >= ?")
            params.append(str(date_from))
        if date_to:
            conditions.append("s.sale_date <= ?")
            params.append(str(date_to))
        if customer_search:
            conditions.append("(c.customer_name LIKE ? OR s.customer_code LIKE ?)")
            params.extend([f"%{customer_search}%", f"%{customer_search}%"])
        if item_search:
            conditions.append("(s.item_code LIKE ? OR s.item_desc LIKE ?)")
            params.extend([f"%{item_search}%", f"%{item_search}%"])
        def _in(col, val):
            """Add an IN clause supporting either a single value or a list."""
            if not val:
                return
            lst = val if isinstance(val, list) else [val]
            if not lst:
                return
            phs = ",".join("?" * len(lst))
            conditions.append(f"{col} IN ({phs})")
            params.extend(lst)

        _in("s.app_dsc",          app_filter)
        _in("c.region",           region_filter)
        _in("c.customer_type",    customer_type_filter)
        _in("c.post_area",        post_area_filter)
        _in("c.main_distributor", distributor_filter)
        _in("i.brand",            brand_filter)
        _in("i.item_type",        item_type_filter)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        return conn.execute(f"""
            SELECT
                s.sale_date         AS "Date",
                s.customer_code     AS "Cust Code",
                COALESCE(c.customer_name, s.customer_code) AS "Customer",
                c.region            AS "Region",
                c.customer_type     AS "Customer Type",
                c.main_distributor  AS "Distributor",
                s.ship_to_address   AS "Ship To Address",
                u.full_name         AS "Salesman",
                s.sm_name           AS "SM Name",
                s.item_code         AS "Item Code",
                s.item_desc         AS "Description",
                i.brand             AS "Brand",
                i.item_type         AS "Item Type",
                s.app_dsc           AS "Application",
                s.qty               AS "Qty",
                s.sales_val         AS "Sales £",
                s.cost_val          AS "Cost £",
                s.gp_val            AS "GP £",
                CASE WHEN s.sales_val > 0
                     THEN ROUND(s.gp_val * 100.0 / s.sales_val, 1)
                     ELSE NULL END  AS "GP %",
                s.invoice_no        AS "Invoice",
                s.whs_code          AS "WHS"
            FROM sales s
            LEFT JOIN customers c ON s.customer_code = c.customer_code
            LEFT JOIN items i     ON s.item_code = i.item_code
            LEFT JOIN sm_name_mapping sm ON s.sm_name = sm.sm_name
            LEFT JOIN users u ON sm.user_id = u.id
            {where}
            ORDER BY s.sale_date DESC, c.customer_name
        """, params).fetchall()


def get_report_filter_options(user_id, role):
    """Returns distinct applications and sm_names available to this user."""
    with get_conn() as conn:
        if role == "rep":
            sm_rows = conn.execute(
                "SELECT sm_name FROM sm_name_mapping WHERE user_id=?", (user_id,)).fetchall()
            sm_names = [r["sm_name"] for r in sm_rows]
        elif role == "regional_manager":
            team = conn.execute("""
                SELECT sm.sm_name FROM sm_name_mapping sm
                JOIN users u ON sm.user_id = u.id
                WHERE u.id=? OR u.regional_manager_id=?
            """, (user_id, user_id)).fetchall()
            sm_names = [r["sm_name"] for r in team]
        else:
            sm_rows = conn.execute("SELECT sm_name FROM sm_name_mapping").fetchall()
            sm_names = [r["sm_name"] for r in sm_rows]

        apps = conn.execute(
            "SELECT DISTINCT app_dsc FROM sales WHERE app_dsc IS NOT NULL AND app_dsc != '' ORDER BY app_dsc"
        ).fetchall()

        reps = conn.execute("""
            SELECT u.id, u.full_name, sm.sm_name
            FROM users u JOIN sm_name_mapping sm ON sm.user_id = u.id
            WHERE u.role IN ('rep','regional_manager')
            ORDER BY u.full_name
        """).fetchall()

        # Customers scoped by role
        if role == "rep":
            sm_ph = ",".join("?" * len(sm_names)) if sm_names else "''"
            custs = conn.execute(f"""
                SELECT DISTINCT c.customer_code, c.customer_name
                FROM customers c
                WHERE c.sm_name IN ({sm_ph})
                ORDER BY c.customer_name
            """, sm_names or []).fetchall() if sm_names else []
        elif role == "regional_manager":
            custs = conn.execute(f"""
                SELECT DISTINCT c.customer_code, c.customer_name
                FROM customers c
                JOIN sm_name_mapping sm ON c.sm_name = sm.sm_name
                JOIN users u ON sm.user_id = u.id
                WHERE u.id=? OR u.regional_manager_id=?
                ORDER BY c.customer_name
            """, (user_id, user_id)).fetchall()
        else:
            custs = conn.execute(
                "SELECT DISTINCT customer_code, customer_name FROM customers ORDER BY customer_name"
            ).fetchall()

        regions = conn.execute(
            "SELECT DISTINCT region FROM customers WHERE region IS NOT NULL AND region != '' ORDER BY region"
        ).fetchall()

        cust_types = conn.execute(
            "SELECT DISTINCT customer_type FROM customers WHERE customer_type IS NOT NULL AND customer_type != '' ORDER BY customer_type"
        ).fetchall()

        post_areas = conn.execute(
            "SELECT DISTINCT post_area FROM customers WHERE post_area IS NOT NULL AND post_area != '' ORDER BY post_area"
        ).fetchall()

        distributors = conn.execute(
            "SELECT DISTINCT main_distributor FROM customers WHERE main_distributor IS NOT NULL AND main_distributor != '' ORDER BY main_distributor"
        ).fetchall()

        brands = conn.execute(
            "SELECT DISTINCT brand FROM items WHERE brand IS NOT NULL AND brand != '' ORDER BY brand"
        ).fetchall()

        item_types = conn.execute(
            "SELECT DISTINCT item_type FROM items WHERE item_type IS NOT NULL AND item_type != '' ORDER BY item_type"
        ).fetchall()

        return {
            "sm_names":      sm_names,
            "applications":  [r["app_dsc"] for r in apps],
            "reps":          [dict(r) for r in reps],
            "customers":     [{"code": r["customer_code"], "name": r["customer_name"]} for r in custs],
            "regions":       [r["region"] for r in regions],
            "customer_types":[r["customer_type"] for r in cust_types],
            "post_areas":    [r["post_area"] for r in post_areas],
            "distributors":  [r["main_distributor"] for r in distributors],
            "brands":        [r["brand"] for r in brands],
            "item_types":    [r["item_type"] for r in item_types],
        }


def get_active_alerts(scope_user_id, role):
    """Return alerts for customers in this user's scope."""
    with get_conn() as conn:
        if role == "admin":
            return conn.execute("""
                SELECT al.*, c.customer_name, u.full_name as rep_name
                FROM alert_log al
                JOIN customers c ON al.customer_code = c.customer_code
                JOIN users u ON c.user_id = u.id
                ORDER BY al.alert_level DESC, al.sent_at DESC
            """).fetchall()
        elif role == "regional_manager":
            return conn.execute("""
                SELECT al.*, c.customer_name, u.full_name as rep_name
                FROM alert_log al
                JOIN customers c ON al.customer_code = c.customer_code
                JOIN users u ON c.user_id = u.id
                WHERE u.regional_manager_id=? OR u.id=?
                ORDER BY al.alert_level DESC, al.sent_at DESC
            """, (scope_user_id, scope_user_id)).fetchall()
        else:
            return conn.execute("""
                SELECT al.*, c.customer_name, u.full_name as rep_name
                FROM alert_log al
                JOIN customers c ON al.customer_code = c.customer_code
                JOIN users u ON c.user_id = u.id
                WHERE u.id=?
                ORDER BY al.alert_level DESC, al.sent_at DESC
            """, (scope_user_id,)).fetchall()


# ── Expenses ─────────────────────────────────────────────────────────────────────

def submit_expense(user_id, expense_date, amount, category, notes, receipt_filename,
                    vat_amount=None, account_code=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO expenses (user_id, expense_date, amount, category, notes,
                                  receipt_filename, vat_amount, account_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, expense_date, amount, category, notes or "",
              receipt_filename or "", vat_amount, account_code))

def get_expenses_for_user(user_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT e.*, u.full_name as rep_name
            FROM expenses e
            JOIN users u ON e.user_id = u.id
            WHERE e.user_id = ?
            ORDER BY e.submitted_at DESC
        """, (user_id,)).fetchall()

def get_all_expenses(role, user_id):
    with get_conn() as conn:
        if role == "regional_manager":
            return conn.execute("""
                SELECT e.*, u.full_name as rep_name,
                       r.full_name as reviewer_name
                FROM expenses e
                JOIN users u ON e.user_id = u.id
                LEFT JOIN users r ON e.reviewed_by = r.id
                WHERE u.id = ? OR u.regional_manager_id = ?
                ORDER BY e.submitted_at DESC
            """, (user_id, user_id)).fetchall()
        else:
            return conn.execute("""
                SELECT e.*, u.full_name as rep_name,
                       r.full_name as reviewer_name
                FROM expenses e
                JOIN users u ON e.user_id = u.id
                LEFT JOIN users r ON e.reviewed_by = r.id
                ORDER BY e.submitted_at DESC
            """).fetchall()

def get_expense_by_id(expense_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT e.*, u.full_name as rep_name, u.email as rep_email,
                   r.full_name as reviewer_name
            FROM expenses e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN users r ON e.reviewed_by = r.id
            WHERE e.id = ?
        """, (expense_id,)).fetchone()

def update_expense_status(expense_id, status, reviewed_by, reviewer_notes=""):
    with get_conn() as conn:
        conn.execute("""
            UPDATE expenses
            SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP, reviewer_notes=?
            WHERE id=?
        """, (status, reviewed_by, reviewer_notes or "", expense_id))

def get_expense_summary(role, user_id):
    """Counts by status for badge display."""
    with get_conn() as conn:
        if role == "regional_manager":
            rows = conn.execute("""
                SELECT e.status, COUNT(*) as cnt
                FROM expenses e JOIN users u ON e.user_id = u.id
                WHERE u.id=? OR u.regional_manager_id=?
                GROUP BY e.status
            """, (user_id, user_id)).fetchall()
        elif role in ("admin",):
            rows = conn.execute("""
                SELECT status, COUNT(*) as cnt FROM expenses GROUP BY status
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT status, COUNT(*) as cnt FROM expenses
                WHERE user_id=? GROUP BY status
            """, (user_id,)).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


def search_receipts(role, user_id, date_from=None, date_to=None,
                    category=None, amount_min=None, amount_max=None,
                    search_text=None, rep_user_id=None):
    """
    Search the receipt catalog. Respects role-based visibility.
    Returns list of expense dicts ordered by expense_date DESC.
    """
    with get_conn() as conn:
        clauses = []
        params  = []

        # Role-based visibility
        if role == "regional_manager":
            clauses.append("(e.user_id = ? OR u.regional_manager_id = ?)")
            params += [user_id, user_id]
        elif role not in ("admin",):
            clauses.append("e.user_id = ?")
            params.append(user_id)

        if date_from:
            clauses.append("e.expense_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("e.expense_date <= ?")
            params.append(date_to)
        if category:
            clauses.append("e.category = ?")
            params.append(category)
        if amount_min is not None:
            clauses.append("e.amount >= ?")
            params.append(amount_min)
        if amount_max is not None:
            clauses.append("e.amount <= ?")
            params.append(amount_max)
        if search_text:
            clauses.append("(e.notes LIKE ? OR u.full_name LIKE ?)")
            params += [f"%{search_text}%", f"%{search_text}%"]
        if rep_user_id:
            clauses.append("e.user_id = ?")
            params.append(rep_user_id)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        return conn.execute(f"""
            SELECT e.*, u.full_name as rep_name,
                   r.full_name as reviewer_name
            FROM expenses e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN users r ON e.reviewed_by = r.id
            {where}
            ORDER BY e.expense_date DESC
        """, params).fetchall()


# ── Budget 2026 ────────────────────────────────────────────────────────────────

BUDGET_MONTH_COLS = [
    "budget_jan", "budget_feb", "budget_mar",
    "budget_apr", "budget_may", "budget_jun",
    "budget_jul", "budget_aug", "budget_sep",
    "budget_oct", "budget_nov", "budget_dec",
]

def upsert_budget_rows(rows):
    """
    Insert or replace budget rows.
    `rows` is a list of dicts with keys:
        app_code, app_desc, family, product_line,
        sales_budget, qty_budget,
        budget_jan … budget_dec
    Returns count of rows upserted.
    """
    cols = ["app_code", "app_desc", "family", "product_line",
            "sales_budget", "qty_budget"] + BUDGET_MONTH_COLS
    placeholders = ",".join("?" * len(cols))
    set_clause = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "app_code")
    sql = f"""
        INSERT INTO budget_2026 ({','.join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(app_code) DO UPDATE SET {set_clause}
    """
    count = 0
    with get_conn() as conn:
        for row in rows:
            vals = [row.get(c) for c in cols]
            conn.execute(sql, vals)
            count += 1
    return count

def get_budget_families():
    """Returns sorted list of distinct family names."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT family FROM budget_2026 WHERE family IS NOT NULL AND family != '' ORDER BY family"
        ).fetchall()
        return [r["family"] for r in rows]

def get_budget_vs_actual(date_from=None, date_to=None, family=None):
    """
    Returns list of dicts combining budget data and actual sales.
    Join key: budget_2026.app_desc = sales.app_dsc (both use the description format).
    date_from / date_to filter the actual sales period.
    Budget for period = sum of monthly budget columns that fall within the date range.
    family filters to a single FAMILY group.
    """
    # Determine which month numbers are in scope (1=Jan … 12=Dec)
    month_col_map = {i+1: col for i, col in enumerate(BUDGET_MONTH_COLS)}
    if date_from and date_to:
        active_months = [m for m in range(1, 13)
                         if date_from.month <= m <= date_to.month
                         or date_from.year < date_to.year]
        # Simpler: any month whose mid-point falls in range
        from datetime import date as _date
        active_months = []
        for m in range(1, 13):
            import calendar
            last_day = calendar.monthrange(2026, m)[1]
            m_start = _date(2026, m, 1)
            m_end   = _date(2026, m, last_day)
            # include month if it overlaps the selected range
            df2 = date_from or _date(2026, 1, 1)
            dt2 = date_to   or _date(2026, 12, 31)
            if m_start <= dt2 and m_end >= df2:
                active_months.append(m)
    else:
        active_months = list(range(1, 13))

    with get_conn() as conn:
        # Build conditions for actual sales
        sale_conds = ["s.app_dsc IS NOT NULL", "s.app_dsc != ''"]
        sale_params = []
        if date_from:
            sale_conds.append("s.sale_date >= ?")
            sale_params.append(str(date_from))
        if date_to:
            sale_conds.append("s.sale_date <= ?")
            sale_params.append(str(date_to))
        sale_where = " AND ".join(sale_conds)

        # Join on description — matches existing sales data format
        actuals = conn.execute(f"""
            SELECT s.app_dsc AS app_desc,
                   SUM(s.sales_val) AS actual_sales,
                   SUM(s.qty)       AS actual_qty
            FROM sales s
            WHERE {sale_where}
            GROUP BY s.app_dsc
        """, sale_params).fetchall()
        actual_map = {r["app_desc"]: r for r in actuals}

        # Prior year (2025) — same calendar period shifted back one year
        from datetime import date as _d
        py_conds = ["s.app_dsc IS NOT NULL", "s.app_dsc != ''"]
        py_params = []
        _df = date_from or _d(2026, 1, 1)
        _dt = date_to   or _d(2026, 12, 31)
        py_conds.append("s.sale_date >= ?")
        py_params.append(str(_df.replace(year=_df.year - 1)))
        py_conds.append("s.sale_date <= ?")
        py_params.append(str(_dt.replace(year=_dt.year - 1)))
        py_where = " AND ".join(py_conds)
        prior_rows = conn.execute(f"""
            SELECT s.app_dsc AS app_desc,
                   SUM(s.sales_val) AS prior_sales
            FROM sales s
            WHERE {py_where}
            GROUP BY s.app_dsc
        """, py_params).fetchall()
        prior_map = {r["app_desc"]: r["prior_sales"] or 0.0 for r in prior_rows}

        bud_cond = "WHERE 1=1"
        bud_params = []
        if family:
            bud_cond += " AND family=?"
            bud_params.append(family)

        budget_rows = conn.execute(f"""
            SELECT * FROM budget_2026 {bud_cond} ORDER BY family, product_line, app_code
        """, bud_params).fetchall()

        result = []
        for b in budget_rows:
            act = actual_map.get(b["app_desc"], {})  # join on description
            actual_sales = act.get("actual_sales") or 0.0
            actual_qty   = act.get("actual_qty")   or 0.0
            # Sum only the monthly budget columns in the active period
            bud_sales = sum((b[month_col_map[m]] or 0) for m in active_months)
            var_gbp   = actual_sales - bud_sales
            var_pct   = (var_gbp / bud_sales * 100) if bud_sales else None
            row = dict(b)
            row["actual_sales"]    = actual_sales
            row["actual_qty"]      = actual_qty
            row["prior_sales"]     = prior_map.get(b["app_desc"], 0.0)
            row["period_budget"]   = bud_sales   # period-scoped budget
            row["var_gbp"]         = var_gbp
            row["var_pct"]         = var_pct
            result.append(row)

        return result

def get_budget_monthly_actuals(date_from=None, date_to=None, family=None):
    """
    Returns per-month actual sales summed by app_code, for the cumulative chart.
    Returns list of dicts: app_code, month_num (1-12), actual_sales
    """
    with get_conn() as conn:
        conds = ["s.app_dsc IS NOT NULL", "s.app_dsc != ''"]
        params = []
        if date_from:
            conds.append("s.sale_date >= ?")
            params.append(str(date_from))
        if date_to:
            conds.append("s.sale_date <= ?")
            params.append(str(date_to))
        if family:
            conds.append("s.app_dsc IN (SELECT app_desc FROM budget_2026 WHERE family=?)")
            params.append(family)
        where = " AND ".join(conds)
        return conn.execute(f"""
            SELECT s.app_dsc AS app_desc,
                   CAST(strftime('%m', s.sale_date) AS INTEGER) AS month_num,
                   SUM(s.sales_val) AS actual_sales
            FROM sales s
            WHERE {where}
            GROUP BY s.app_dsc, month_num
        """, params).fetchall()

def clear_budget_2026():
    """Delete all budget rows (used before re-uploading)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM budget_2026")


# ── CRM ────────────────────────────────────────────────────────────────────────

def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today():
    from datetime import date
    return date.today().isoformat()

# ── Contacts ──────────────────────────────────────────────────────────────────

def crm_get_contacts(customer_code=None, search=None):
    with get_conn() as conn:
        where = []
        params = []
        if customer_code:
            where.append("cc.customer_code = ?")
            params.append(customer_code)
        if search:
            where.append("(cc.contact_name LIKE ? OR cc.email LIKE ? OR cc.phone LIKE ? OR cc.job_title LIKE ?)")
            params += [f"%{search}%"] * 4
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return conn.execute(f"""
            SELECT cc.*, c.customer_name
            FROM customer_contacts cc
            LEFT JOIN customers c ON cc.customer_code = c.customer_code
            {w}
            ORDER BY cc.is_primary DESC, cc.contact_name
        """, params).fetchall()

def crm_save_contact(customer_code, contact_name, email=None, phone=None,
                     job_title=None, is_primary=0, contact_id=None):
    with get_conn() as conn:
        if contact_id:
            conn.execute("""
                UPDATE customer_contacts
                SET contact_name=?, email=?, phone=?, job_title=?, is_primary=?
                WHERE id=?
            """, (contact_name, email, phone, job_title, is_primary, contact_id))
        else:
            conn.execute("""
                INSERT INTO customer_contacts
                    (customer_code, contact_name, email, phone, job_title, is_primary, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (customer_code, contact_name, email, phone, job_title, is_primary, _now()))

def crm_delete_contact(contact_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM customer_contacts WHERE id=?", (contact_id,))

# ── Notes & Interactions ──────────────────────────────────────────────────────

NOTE_TYPES = ["📞 Call", "📧 Email", "🤝 Meeting", "🏭 Site Visit", "💬 Other"]

def crm_get_notes(customer_code=None, user_id=None, note_type=None, limit=200):
    with get_conn() as conn:
        where = []
        params = []
        if customer_code:
            where.append("cn.customer_code = ?")
            params.append(customer_code)
        if user_id:
            where.append("cn.user_id = ?")
            params.append(user_id)
        if note_type:
            where.append("cn.note_type = ?")
            params.append(note_type)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return conn.execute(f"""
            SELECT cn.*, u.full_name AS author, c.customer_name
            FROM customer_notes cn
            LEFT JOIN users u ON cn.user_id = u.id
            LEFT JOIN customers c ON cn.customer_code = c.customer_code
            {w}
            ORDER BY cn.created_at DESC
            LIMIT ?
        """, params + [limit]).fetchall()

def crm_add_note(customer_code, user_id, note_text, note_type="💬 Other", contact_name=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO customer_notes
                (customer_code, user_id, note_text, note_type, contact_name, created_at)
            VALUES (?,?,?,?,?,?)
        """, (customer_code, user_id, note_text, note_type, contact_name, _now()))

def crm_delete_note(note_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM customer_notes WHERE id=?", (note_id,))

# ── Tasks ─────────────────────────────────────────────────────────────────────

TASK_PRIORITIES = ["🔴 High", "🟡 Medium", "🟢 Low"]

def crm_get_tasks(customer_code=None, assigned_to=None, status=None,
                  overdue_only=False, limit=200):
    with get_conn() as conn:
        where = []
        params = []
        if customer_code:
            where.append("t.customer_code = ?")
            params.append(customer_code)
        if assigned_to:
            where.append("t.assigned_to = ?")
            params.append(assigned_to)
        if status:
            where.append("t.status = ?")
            params.append(status)
        if overdue_only:
            where.append("t.due_date < ? AND t.status = 'open'")
            params.append(_today())
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return conn.execute(f"""
            SELECT t.*,
                   u.full_name  AS assigned_name,
                   uc.full_name AS created_name,
                   c.customer_name
            FROM crm_tasks t
            LEFT JOIN users u  ON t.assigned_to = u.id
            LEFT JOIN users uc ON t.created_by  = uc.id
            LEFT JOIN customers c ON t.customer_code = c.customer_code
            {w}
            ORDER BY
                CASE t.status WHEN 'open' THEN 0 ELSE 1 END,
                CASE t.priority WHEN '🔴 High' THEN 0 WHEN '🟡 Medium' THEN 1 ELSE 2 END,
                t.due_date
            LIMIT ?
        """, params + [limit]).fetchall()

def crm_save_task(customer_code, title, description=None, assigned_to=None,
                  created_by=None, due_date=None, priority="🟡 Medium", task_id=None):
    with get_conn() as conn:
        if task_id:
            conn.execute("""
                UPDATE crm_tasks
                SET customer_code=?, title=?, description=?, assigned_to=?,
                    due_date=?, priority=?
                WHERE id=?
            """, (customer_code, title, description, assigned_to, due_date, priority, task_id))
        else:
            conn.execute("""
                INSERT INTO crm_tasks
                    (customer_code, title, description, assigned_to, created_by,
                     due_date, priority, status, created_at)
                VALUES (?,?,?,?,?,?,?,'open',?)
            """, (customer_code, title, description, assigned_to, created_by,
                  due_date, priority, _now()))

def crm_complete_task(task_id):
    with get_conn() as conn:
        conn.execute("""
            UPDATE crm_tasks SET status='completed', completed_at=? WHERE id=?
        """, (_now(), task_id))

def crm_reopen_task(task_id):
    with get_conn() as conn:
        conn.execute("""
            UPDATE crm_tasks SET status='open', completed_at=NULL WHERE id=?
        """, (task_id,))

def crm_delete_task(task_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM crm_tasks WHERE id=?", (task_id,))

# ── Segments ──────────────────────────────────────────────────────────────────

def crm_get_segments():
    with get_conn() as conn:
        return conn.execute("""
            SELECT s.*, u.full_name AS created_by_name,
                   COUNT(m.id) AS member_count
            FROM crm_segments s
            LEFT JOIN users u ON s.created_by = u.id
            LEFT JOIN crm_segment_members m ON s.id = m.segment_id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """).fetchall()

def crm_save_segment(name, description=None, created_by=None, customer_codes=None, segment_id=None):
    with get_conn() as conn:
        if segment_id:
            conn.execute("""
                UPDATE crm_segments SET name=?, description=?, updated_at=? WHERE id=?
            """, (name, description, _now(), segment_id))
        else:
            cur = conn.execute("""
                INSERT INTO crm_segments (name, description, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?)
            """, (name, description, created_by, _now(), _now()))
            segment_id = cur.lastrowid
        if customer_codes is not None:
            conn.execute("DELETE FROM crm_segment_members WHERE segment_id=?", (segment_id,))
            for code in customer_codes:
                conn.execute("""
                    INSERT OR IGNORE INTO crm_segment_members (segment_id, customer_code, added_at)
                    VALUES (?,?,?)
                """, (segment_id, code, _now()))
    return segment_id

def crm_get_segment_members(segment_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT m.customer_code, c.customer_name,
                   c.addr_town, c.region,
                   u.full_name AS rep_name,
                   MAX(s.sale_date) AS last_order,
                   SUM(CASE WHEN s.year=2026 THEN s.sales_val ELSE 0 END) AS ytd_2026,
                   SUM(CASE WHEN s.year=2025 THEN s.sales_val ELSE 0 END) AS total_2025
            FROM crm_segment_members m
            LEFT JOIN customers c ON m.customer_code = c.customer_code
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN sales s ON m.customer_code = s.customer_code
            WHERE m.segment_id = ?
            GROUP BY m.customer_code
            ORDER BY c.customer_name
        """, (segment_id,)).fetchall()

def crm_delete_segment(segment_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM crm_segment_members WHERE segment_id=?", (segment_id,))
        conn.execute("DELETE FROM crm_segments WHERE id=?", (segment_id,))

# ── CRM Overview ─────────────────────────────────────────────────────────────

def crm_customer_overview(user_id=None, role="rep"):
    """Return customer list with CRM metrics for the 360 landing page.
    One efficient query instead of N+1 per customer."""
    with get_conn() as conn:
        from datetime import date
        yr = date.today().year
        role_clause = ""
        params = [yr, yr]
        if role == "rep" and user_id:
            role_clause = "WHERE c.user_id = ?"
            params.append(user_id)
        elif role == "regional_manager" and user_id:
            role_clause = "WHERE (c.user_id = ? OR c.user_id IN (SELECT id FROM users WHERE regional_manager_id = ?))"
            params.extend([user_id, user_id])
        # admin / marketing see all

        return conn.execute(f"""
            SELECT
                c.customer_code,
                c.customer_name,
                c.sm_name,
                c.region,
                c.customer_type,
                c.post_area,
                c.addr_town,
                u.full_name AS rep_name,
                COALESCE(cc_cnt.contact_count, 0) AS contact_count,
                COALESCE(tk.open_tasks, 0)         AS open_tasks,
                COALESCE(tk.overdue_tasks, 0)      AS overdue_tasks,
                nt.last_note_date,
                COALESCE(nt.note_count, 0)         AS note_count,
                ls.last_sale,
                CAST(julianday('now') - julianday(ls.last_sale) AS INTEGER) AS purchase_days,
                lv.last_visit,
                CAST(julianday('now') - julianday(lv.last_visit) AS INTEGER) AS visit_days,
                COALESCE(ytd.ytd_sales, 0)         AS ytd_sales,
                COALESCE(py.prev_sales, 0)         AS prev_sales
            FROM customers c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN (
                SELECT customer_code, COUNT(*) AS contact_count
                FROM customer_contacts GROUP BY customer_code
            ) cc_cnt ON cc_cnt.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code,
                       SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open_tasks,
                       SUM(CASE WHEN status='open' AND due_date < date('now') THEN 1 ELSE 0 END) AS overdue_tasks
                FROM crm_tasks GROUP BY customer_code
            ) tk ON tk.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code,
                       MAX(created_at) AS last_note_date,
                       COUNT(*) AS note_count
                FROM customer_notes GROUP BY customer_code
            ) nt ON nt.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, MAX(sale_date) AS last_sale
                FROM sales GROUP BY customer_code
            ) ls ON ls.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, MAX(visit_date) AS last_visit
                FROM visits GROUP BY customer_code
            ) lv ON lv.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, SUM(sales_val) AS ytd_sales
                FROM sales WHERE year = ? GROUP BY customer_code
            ) ytd ON ytd.customer_code = c.customer_code
            LEFT JOIN (
                SELECT customer_code, SUM(sales_val) AS prev_sales
                FROM sales WHERE year = ? GROUP BY customer_code
            ) py ON py.customer_code = c.customer_code
            {role_clause}
            ORDER BY c.customer_name
        """, params).fetchall()

def crm_overview_totals(user_id=None, role="rep"):
    """Quick aggregate counts for the CRM landing page KPI cards."""
    with get_conn() as conn:
        role_clause = ""
        params = []
        if role == "rep" and user_id:
            role_clause = "AND c.user_id = ?"
            params.append(user_id)
        elif role == "regional_manager" and user_id:
            role_clause = "AND (c.user_id = ? OR c.user_id IN (SELECT id FROM users WHERE regional_manager_id = ?))"
            params.extend([user_id, user_id])

        row = conn.execute(f"""
            SELECT
                (SELECT COUNT(*) FROM customer_contacts cc
                 JOIN customers c ON cc.customer_code = c.customer_code WHERE 1=1 {role_clause}) AS total_contacts,
                (SELECT COUNT(*) FROM crm_tasks t
                 JOIN customers c ON t.customer_code = c.customer_code
                 WHERE t.status='open' {role_clause}) AS open_tasks,
                (SELECT COUNT(*) FROM crm_tasks t
                 JOIN customers c ON t.customer_code = c.customer_code
                 WHERE t.status='open' AND t.due_date < date('now') {role_clause}) AS overdue_tasks,
                (SELECT COUNT(*) FROM customer_notes cn
                 JOIN customers c ON cn.customer_code = c.customer_code
                 WHERE cn.created_at >= date('now', '-30 days') {role_clause}) AS notes_30d
        """, params * 4).fetchone()
        return row

# ── Customer 360 ──────────────────────────────────────────────────────────────

def crm_customer_summary(customer_code):
    with get_conn() as conn:
        from datetime import date
        yr = date.today().year
        return conn.execute("""
            SELECT
                c.customer_name, c.addr_town, c.addr_postcode, c.region,
                c.customer_type, c.main_distributor,
                u.full_name AS rep_name,
                SUM(CASE WHEN s.year=? THEN s.sales_val ELSE 0 END)  AS ytd_sales,
                SUM(CASE WHEN s.year=?-1 THEN s.sales_val ELSE 0 END) AS prev_sales,
                SUM(CASE WHEN s.year=? THEN s.gp_val ELSE 0 END)     AS ytd_gp,
                MAX(s.sale_date)                                       AS last_order,
                COUNT(DISTINCT s.invoice_no)                          AS invoice_count
            FROM customers c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN sales s ON c.customer_code = s.customer_code
            WHERE c.customer_code = ?
        """, (yr, yr, yr, customer_code)).fetchone()

def crm_customer_top_products(customer_code, limit=8):
    with get_conn() as conn:
        from datetime import date
        yr = date.today().year
        return conn.execute("""
            SELECT item_desc, SUM(qty) AS total_qty, SUM(sales_val) AS total_sales
            FROM sales
            WHERE customer_code=? AND year=?
            GROUP BY item_desc
            ORDER BY total_sales DESC
            LIMIT ?
        """, (customer_code, yr, limit)).fetchall()


# ── Prospects ─────────────────────────────────────────────────────────────────

def crm_get_prospects(search=None, sm_area=None, status=None, region=None, limit=500):
    with get_conn() as conn:
        where = []
        params = []
        if search:
            where.append("(p.contact_name LIKE ? OR p.company_name LIKE ? OR p.email LIKE ?)")
            params += [f"%{search}%"] * 3
        if sm_area:
            where.append("p.sm_area = ?")
            params.append(sm_area)
        if status:
            where.append("p.status = ?")
            params.append(status)
        if region:
            where.append("p.region = ?")
            params.append(region)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return conn.execute(f"""
            SELECT p.* FROM crm_prospects p
            {w}
            ORDER BY p.company_name, p.contact_name
            LIMIT ?
        """, params + [limit]).fetchall()

def crm_get_prospect_filters():
    """Return distinct sm_area, region, status values for filter dropdowns."""
    with get_conn() as conn:
        sm_areas = [r['sm_area'] for r in conn.execute(
            "SELECT DISTINCT sm_area FROM crm_prospects WHERE sm_area IS NOT NULL ORDER BY sm_area"
        ).fetchall()]
        regions = [r['region'] for r in conn.execute(
            "SELECT DISTINCT region FROM crm_prospects WHERE region IS NOT NULL ORDER BY region"
        ).fetchall()]
        statuses = [r['status'] for r in conn.execute(
            "SELECT DISTINCT status FROM crm_prospects WHERE status IS NOT NULL ORDER BY status"
        ).fetchall()]
        return sm_areas, regions, statuses

def crm_update_prospect_status(prospect_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE crm_prospects SET status=? WHERE id=?", (status, prospect_id))

def crm_update_prospect_notes(prospect_id, notes):
    with get_conn() as conn:
        conn.execute("UPDATE crm_prospects SET notes=? WHERE id=?", (notes, prospect_id))

def crm_delete_prospect(prospect_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM crm_prospects WHERE id=?", (prospect_id,))

def crm_convert_prospect_to_customer(prospect_id, customer_code):
    """Link a prospect to an existing customer and remove from prospects."""
    with get_conn() as conn:
        p = conn.execute("SELECT * FROM crm_prospects WHERE id=?", (prospect_id,)).fetchone()
        if not p:
            return False
        conn.execute("""
            INSERT OR IGNORE INTO customer_contacts
                (customer_code, contact_name, email, job_title, created_at)
            VALUES (?,?,?,?,datetime('now'))
        """, (customer_code, p['contact_name'], p['email'], p['job_title']))
        conn.execute("DELETE FROM crm_prospects WHERE id=?", (prospect_id,))
        return True

def crm_get_prospect_count():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM crm_prospects").fetchone()
        return row['cnt'] if row else 0

def crm_get_prospect_counts_by_status():
    with get_conn() as conn:
        return conn.execute("""
            SELECT status, COUNT(*) as cnt FROM crm_prospects
            GROUP BY status ORDER BY cnt DESC
        """).fetchall()

# ── Email Campaigns ────────────────────────────────────────────────────────────

import secrets as _secrets

def _email_token():
    return _secrets.token_urlsafe(24)

# ── Templates ─────────────────────────────────────────────────────────────────

def email_get_templates():
    with get_conn() as conn:
        return conn.execute("""
            SELECT t.*, u.full_name AS author
            FROM email_templates t
            LEFT JOIN users u ON t.created_by = u.id
            ORDER BY t.created_at DESC
        """).fetchall()

def email_get_template(template_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM email_templates WHERE id=?", (template_id,)).fetchone()

def email_save_template(name, subject, body_html, created_by, template_id=None):
    with get_conn() as conn:
        if template_id:
            conn.execute("""
                UPDATE email_templates SET name=?, subject=?, body_html=?, updated_at=?
                WHERE id=?
            """, (name, subject, body_html, _now(), template_id))
            return template_id
        else:
            cur = conn.execute("""
                INSERT INTO email_templates (name, subject, body_html, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
            """, (name, subject, body_html, created_by, _now(), _now()))
            return cur.lastrowid

def email_delete_template(template_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM email_templates WHERE id=?", (template_id,))

# ── Campaigns ─────────────────────────────────────────────────────────────────

def email_get_campaigns():
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.*, u.full_name AS author,
                   s.name AS segment_name,
                   t.name AS template_name
            FROM email_campaigns c
            LEFT JOIN users u ON c.created_by = u.id
            LEFT JOIN crm_segments s ON c.segment_id = s.id
            LEFT JOIN email_templates t ON c.template_id = t.id
            ORDER BY c.created_at DESC
        """).fetchall()

def email_get_campaign(campaign_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM email_campaigns WHERE id=?", (campaign_id,)).fetchone()

def email_save_campaign(name, subject, body_html, from_name, from_email, reply_to,
                        segment_id=None, template_id=None, created_by=None, campaign_id=None):
    with get_conn() as conn:
        if campaign_id:
            conn.execute("""
                UPDATE email_campaigns
                SET name=?, subject=?, body_html=?, from_name=?, from_email=?,
                    reply_to=?, segment_id=?, template_id=?
                WHERE id=?
            """, (name, subject, body_html, from_name, from_email, reply_to,
                  segment_id, template_id, campaign_id))
            return campaign_id
        else:
            cur = conn.execute("""
                INSERT INTO email_campaigns
                    (name, subject, body_html, from_name, from_email, reply_to,
                     segment_id, template_id, status, created_by, created_at)
                VALUES (?,?,?,?,?,?,?,?,'draft',?,?)
            """, (name, subject, body_html, from_name, from_email, reply_to,
                  segment_id, template_id, created_by, _now()))
            return cur.lastrowid

def email_delete_campaign(campaign_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM email_sends WHERE campaign_id=?", (campaign_id,))
        conn.execute("DELETE FROM email_events WHERE campaign_id=?", (campaign_id,))
        conn.execute("DELETE FROM email_campaigns WHERE id=?", (campaign_id,))

# ── Sends & Events ────────────────────────────────────────────────────────────

def email_create_sends(campaign_id, recipients):
    """recipients = list of (customer_code, contact_email, contact_name)"""
    with get_conn() as conn:
        for code, email_addr, name in recipients:
            token = _email_token()
            conn.execute("""
                INSERT OR IGNORE INTO email_sends
                    (campaign_id, customer_code, contact_email, contact_name, status, token)
                VALUES (?,?,?,?,'pending',?)
            """, (campaign_id, code, email_addr, name, token))

def email_get_sends(campaign_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM email_sends WHERE campaign_id=? ORDER BY contact_name
        """, (campaign_id,)).fetchall()

def email_mark_sent(send_id):
    with get_conn() as conn:
        conn.execute("""
            UPDATE email_sends SET status='sent', sent_at=? WHERE id=?
        """, (_now(), send_id))

def email_mark_failed(send_id):
    with get_conn() as conn:
        conn.execute("UPDATE email_sends SET status='failed' WHERE id=?", (send_id,))

def email_record_open(send_id):
    with get_conn() as conn:
        send = conn.execute("SELECT campaign_id FROM email_sends WHERE id=?", (send_id,)).fetchone()
        if not send:
            return
        conn.execute("UPDATE email_sends SET open_count=open_count+1 WHERE id=?", (send_id,))
        conn.execute("""
            UPDATE email_campaigns SET total_opened=total_opened+1 WHERE id=?
        """, (send['campaign_id'],))
        conn.execute("""
            INSERT INTO email_events (send_id, campaign_id, event_type, created_at)
            VALUES (?,?,'open',?)
        """, (send_id, send['campaign_id'], _now()))

def email_record_click(send_id, url):
    with get_conn() as conn:
        send = conn.execute("SELECT campaign_id FROM email_sends WHERE id=?", (send_id,)).fetchone()
        if not send:
            return
        conn.execute("UPDATE email_sends SET click_count=click_count+1 WHERE id=?", (send_id,))
        conn.execute("""
            UPDATE email_campaigns SET total_clicked=total_clicked+1 WHERE id=?
        """, (send['campaign_id'],))
        conn.execute("""
            INSERT INTO email_events (send_id, campaign_id, event_type, event_data, created_at)
            VALUES (?,?,'click',?,?)
        """, (send_id, send['campaign_id'], url, _now()))

def email_record_unsubscribe(token):
    with get_conn() as conn:
        send = conn.execute("SELECT * FROM email_sends WHERE token=?", (token,)).fetchone()
        if not send:
            return False
        conn.execute("UPDATE email_sends SET unsubscribed=1 WHERE id=?", (send['id'],))
        conn.execute("""
            INSERT OR IGNORE INTO email_opt_outs (email, customer_code, opted_out_at, reason)
            VALUES (?,?,?,?)
        """, (send['contact_email'], send['customer_code'],
              _now(), 'Unsubscribed via email link'))
        return True

def email_update_campaign_status(campaign_id, status, sent_count=None):
    with get_conn() as conn:
        if sent_count is not None:
            conn.execute("""
                UPDATE email_campaigns SET status=?, sent_at=?, total_sent=? WHERE id=?
            """, (status, _now(), sent_count, campaign_id))
        else:
            conn.execute("UPDATE email_campaigns SET status=? WHERE id=?", (status, campaign_id))

def email_get_opt_outs():
    with get_conn() as conn:
        return conn.execute("""
            SELECT o.*, c.customer_name FROM email_opt_outs o
            LEFT JOIN customers c ON o.customer_code = c.customer_code
            ORDER BY o.opted_out_at DESC
        """).fetchall()

def email_add_opt_out(email_addr, customer_code=None, reason="Manual"):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO email_opt_outs (email, customer_code, opted_out_at, reason)
            VALUES (?,?,?,?)
        """, (email_addr, customer_code, _now(), reason))

def email_remove_opt_out(email_addr):
    with get_conn() as conn:
        conn.execute("DELETE FROM email_opt_outs WHERE email=?", (email_addr,))

def email_is_opted_out(email_addr):
    with get_conn() as conn:
        r = conn.execute("SELECT id FROM email_opt_outs WHERE email=?", (email_addr,)).fetchone()
        return r is not None

def email_get_send_by_token(token):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM email_sends WHERE token=?", (token,)).fetchone()

# ── Landing Pages ─────────────────────────────────────────────────────────────

def lp_get_pages():
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.*, u.full_name AS author
            FROM landing_pages p
            LEFT JOIN users u ON p.created_by = u.id
            ORDER BY p.created_at DESC
        """).fetchall()

def lp_get_page(slug):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM landing_pages WHERE slug=? AND is_active=1", (slug,)).fetchone()

def lp_get_page_by_id(page_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM landing_pages WHERE id=?", (page_id,)).fetchone()

def lp_save_page(name, slug, title, body_html, created_by, page_id=None):
    with get_conn() as conn:
        slug = slug.lower().replace(" ", "-")
        if page_id:
            conn.execute("""
                UPDATE landing_pages SET name=?, slug=?, title=?, body_html=? WHERE id=?
            """, (name, slug, title, body_html, page_id))
            return page_id
        else:
            cur = conn.execute("""
                INSERT INTO landing_pages (name, slug, title, body_html, created_by, created_at)
                VALUES (?,?,?,?,?,?)
            """, (name, slug, title, body_html, created_by, _now()))
            return cur.lastrowid

def lp_record_view(page_id):
    with get_conn() as conn:
        conn.execute("UPDATE landing_pages SET view_count=view_count+1 WHERE id=?", (page_id,))

def lp_delete_page(page_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM landing_pages WHERE id=?", (page_id,))

# ── Consignment Stock ─────────────────────────────────────────────────────────

def consignment_get_warehouses():
    """Return all consignment warehouses with their linked customer info."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT cw.*, c.customer_name, c.sm_name, u.full_name AS rep_name
            FROM consignment_warehouses cw
            LEFT JOIN customers c ON cw.customer_code = c.customer_code
            LEFT JOIN users u ON c.user_id = u.id
            WHERE cw.is_active = 1
            ORDER BY cw.customer_desc
        """).fetchall()

def consignment_get_customer_codes():
    """Return the set of customer_codes that have consignment stock."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT customer_code FROM consignment_warehouses WHERE is_active=1 AND customer_code IS NOT NULL"
        ).fetchall()
        return [r['customer_code'] for r in rows]

def consignment_get_summary():
    """Return per-account summary for all consignment customers."""
    with get_conn() as conn:
        codes = [r['customer_code'] for r in conn.execute(
            "SELECT DISTINCT customer_code FROM consignment_warehouses WHERE is_active=1 AND customer_code IS NOT NULL"
        ).fetchall()]
        if not codes:
            return []
        ph = ",".join("?" * len(codes))
        from datetime import date
        yr = date.today().year
        return conn.execute(f"""
            SELECT
                c.customer_code,
                c.customer_name,
                c.sm_name,
                u.full_name AS rep_name,
                GROUP_CONCAT(DISTINCT cw.whs_code) AS whs_codes,
                COUNT(DISTINCT s.invoice_no) AS total_invoices,
                COALESCE(SUM(s.sales_val), 0) AS total_sales,
                COALESCE(SUM(s.gp_val), 0) AS total_gp,
                COALESCE(SUM(s.qty), 0) AS total_qty,
                COALESCE(SUM(CASE WHEN s.year = ? THEN s.sales_val ELSE 0 END), 0) AS ytd_sales,
                COALESCE(SUM(CASE WHEN s.year = ? THEN s.gp_val ELSE 0 END), 0) AS ytd_gp,
                COALESCE(SUM(CASE WHEN s.year = ?-1 THEN s.sales_val ELSE 0 END), 0) AS prev_year_sales,
                MAX(s.sale_date) AS last_order,
                COUNT(DISTINCT s.item_code) AS unique_items
            FROM customers c
            JOIN consignment_warehouses cw ON cw.customer_code = c.customer_code AND cw.is_active = 1
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN sales s ON s.customer_code = c.customer_code
            WHERE c.customer_code IN ({ph})
            GROUP BY c.customer_code
            ORDER BY total_sales DESC
        """, [yr, yr, yr] + codes).fetchall()

def consignment_get_sales(customer_code=None, date_from=None, date_to=None,
                          item_search=None, sm_name=None):
    """Return full sales history for consignment accounts with optional filters."""
    with get_conn() as conn:
        codes_rows = conn.execute(
            "SELECT DISTINCT customer_code FROM consignment_warehouses WHERE is_active=1 AND customer_code IS NOT NULL"
        ).fetchall()
        codes = [r['customer_code'] for r in codes_rows]
        if not codes:
            return []

        conditions = [f"s.customer_code IN ({','.join('?' * len(codes))})"]
        params = list(codes)

        if customer_code:
            conditions.append("s.customer_code = ?")
            params.append(customer_code)
        if date_from:
            conditions.append("s.sale_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("s.sale_date <= ?")
            params.append(date_to)
        if item_search:
            conditions.append("(s.item_code LIKE ? OR s.item_desc LIKE ?)")
            params.extend([f"%{item_search}%", f"%{item_search}%"])
        if sm_name:
            conditions.append("s.sm_name = ?")
            params.append(sm_name)

        where = " AND ".join(conditions)
        return conn.execute(f"""
            SELECT s.*, c.customer_name
            FROM sales s
            JOIN customers c ON s.customer_code = c.customer_code
            WHERE {where}
            ORDER BY s.sale_date DESC, c.customer_name
        """, params).fetchall()

def consignment_upsert_warehouse(whs_code, customer_desc, customer_code=None):
    """Insert or update a consignment warehouse mapping."""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO consignment_warehouses (whs_code, customer_desc, customer_code)
            VALUES (?, ?, ?)
            ON CONFLICT(whs_code) DO UPDATE SET
                customer_desc = excluded.customer_desc,
                customer_code = excluded.customer_code
        """, (whs_code, customer_desc, customer_code))

def consignment_delete_warehouse(whs_code):
    with get_conn() as conn:
        conn.execute("UPDATE consignment_warehouses SET is_active=0 WHERE whs_code=?", (whs_code,))
