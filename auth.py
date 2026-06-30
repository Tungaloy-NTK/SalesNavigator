import bcrypt
import re
import streamlit as st
import database as db
from datetime import datetime, timedelta

# ── Security constants ──────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS    = 5     # lock after this many bad passwords
LOCKOUT_MINUTES        = 30    # how long the lockout lasts
SESSION_TIMEOUT_MINUTES = 120  # auto-logout after 2 hours of inactivity
PASSWORD_MAX_AGE_DAYS  = 90    # force change after 90 days

# ── Pre-seeded user data ────────────────────────────────────────────────────────
# SM Name territory codes → person mapping
SM_NAME_TO_USERNAME = {
    "TURNOCK-WMIDS":        "simon.turnock",
    "BRASH-NORTHEAST":      "graeme.brash",
    "BOYLE-SOUTH":          "duncan.boyle",
    "SOUTHWEST-BOYLE":      "duncan.boyle",
    "DANBY-SOUTHEAST":      "rhys.danby",
    "HUXTABLE-WEST":        "simon.huxtable",
    "HUXTABLE-TUNG":        "simon.huxtable",
    "GITTOES (AGENT)":      "james.gittoes",
    "HOUSEACCOUNTS":        "rob.werhun",
    "HITCHENS-NORTHWEST ENG": "ashley.hitchens",
    "HITCHENS-YORKSHIRE":   "ashley.hitchens",
    "SCOTLAND-W-HAMILTON":  "kevin.hamilton",
    "SCOTLAND-EAST-HAMILTON": "kevin.hamilton",
    "IRVINE-IRELAND":       "phil.irvine",
    "IRVINE-NTK":           "phil.irvine",
    "EAST MIDS-TURNOCK":    "chris.gibson",
    "IMC CUSTOMERS":        "rob.werhun",
    "INTER COMPANY":        "rob.werhun",
    "CUSTOMER FREIGHT":     "rob.werhun",
}

# (username, full_name, email, role, reports_to_username)
SEED_USERS = [
    ("rob.werhun",     "Rob Werhun",     "Rob.Werhun@tungaloyuk.co.uk",               "admin",            None),
    ("phil.irvine",    "Phil Irvine",    "p.irvine@tungaloyuk.co.uk",                 "regional_manager", None),
    ("simon.turnock",  "Simon Turnock",  "Simon.Turnock@tungaloyuk.co.uk",            "rep",              None),
    ("graeme.brash",   "Graeme Brash",   "Graeme.Brash@tungaloyuk.co.uk",             "rep",              "phil.irvine"),
    ("duncan.boyle",   "Duncan Boyle",   "Duncan.Boyle@tungaloyuk.co.uk",             "rep",              None),
    ("rhys.danby",     "Rhys Danby",     "Rhys.danby@tungaloyuk.co.uk",               "rep",              None),
    ("simon.huxtable", "Simon Huxtable", "Simon.Huxtable@Tungaloy-NTK.co.uk",         "rep",              None),
    ("james.gittoes",  "James Gittoes",  "James.Gittoes@tungaloyuk.co.uk",            "rep",              None),
    ("ashley.hitchens","Ashley Hitchens","ashley.hitchens@tungaloyuk.co.uk",           "rep",              "phil.irvine"),
    ("kevin.hamilton", "Kevin Hamilton", "Kevin.Hamilton@tungaloyuk.co.uk",            "rep",              "phil.irvine"),
    ("chris.gibson",   "Chris Gibson",   "Chris.Gibson@tungaloyuk.co.uk",             "rep",              "phil.irvine"),
    ("sylwia.dubij",   "Sylwia Dubij",   "Sylwia@tungaloyuk.co.uk",                   "marketing",        None),
]

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def seed_users():
    """Insert all users with default passwords on first run."""
    all_users = db.get_all_users()
    if all_users:
        return  # Already seeded

    # First pass: insert users without manager refs
    user_id_map = {}
    for username, full_name, email, role, _ in SEED_USERS:
        default_pw = hash_password("Tungaloy2024!")
        db.upsert_user(username, full_name, email, role, None, default_pw)

    # Build username→id map (reuse query instead of calling get_all_users again)
    for user in db.get_all_users():
        user_id_map[user["username"]] = user["id"]
    # Note: seed only runs once on first startup, so this second call is acceptable

    # Second pass: set regional_manager_id
    with db.get_conn() as conn:
        for username, _, _, _, reports_to in SEED_USERS:
            if reports_to:
                mgr_id = user_id_map.get(reports_to)
                conn.execute(
                    "UPDATE users SET regional_manager_id=? WHERE username=?",
                    (mgr_id, username)
                )

    # Seed SM name → user mappings
    with db.get_conn() as conn:
        for sm_name, username in SM_NAME_TO_USERNAME.items():
            user_id = user_id_map.get(username)
            if user_id:
                conn.execute(
                    "INSERT OR IGNORE INTO sm_name_mapping (sm_name, user_id) VALUES (?,?)",
                    (sm_name, user_id)
                )

def _get_client_ip() -> str:
    """Best-effort client IP from Streamlit request headers."""
    try:
        headers = st.context.headers
        xff = headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return headers.get("X-Real-IP", "unknown")
    except Exception:
        return "unknown"


def validate_password_strength(password: str) -> list:
    """Returns a list of unmet requirements. Empty list = password is strong enough."""
    errors = []
    if len(password) < 8:
        errors.append("At least 8 characters")
    if not any(c.isupper() for c in password):
        errors.append("At least one uppercase letter")
    if not any(c.islower() for c in password):
        errors.append("At least one lowercase letter")
    if not any(c.isdigit() for c in password):
        errors.append("At least one number")
    return errors


def login(username: str, password: str):
    """
    Returns (user_dict, error_message).
    user_dict is None on failure; error_message is None on success.
    """
    uname = (username or "").lower().strip()
    ip    = _get_client_ip()
    user  = db.get_user_by_username(uname)

    # Account not found
    if not user:
        db.log_login_attempt(uname, ip, False, "unknown_user")
        return None, "Invalid username or password."

    # Check if account is currently locked
    locked_until = user.get("locked_until")
    if locked_until:
        try:
            lock_dt = datetime.fromisoformat(locked_until)
            if datetime.now() < lock_dt:
                remaining = int((lock_dt - datetime.now()).total_seconds() / 60) + 1
                db.log_login_attempt(uname, ip, False, "account_locked")
                return None, f"Account locked due to too many failed attempts. Try again in {remaining} minute(s)."
        except Exception:
            pass  # Malformed date — ignore lock

    # Check password
    if check_password(password, user["password_hash"]):
        db.reset_failed_logins(user["id"])
        db.log_login_attempt(uname, ip, True)

        # Check password age — force change if expired
        changed_at = user.get("password_changed_at")
        if changed_at:
            try:
                age_days = (datetime.now() - datetime.fromisoformat(changed_at)).days
                if age_days >= PASSWORD_MAX_AGE_DAYS:
                    with db.get_conn() as conn:
                        conn.execute("UPDATE users SET must_change_password=1 WHERE id=?", (user["id"],))
                    user = db.get_user_by_username(uname)  # re-fetch updated record
            except Exception:
                pass

        return user, None

    # Wrong password — increment counter
    new_count = db.increment_failed_logins(uname)
    if new_count >= MAX_FAILED_ATTEMPTS:
        lock_until = (datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        db.set_account_lock(uname, lock_until)
        db.log_login_attempt(uname, ip, False, "too_many_attempts")
        return None, f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes."

    remaining_attempts = MAX_FAILED_ATTEMPTS - new_count
    db.log_login_attempt(uname, ip, False, "bad_password")
    return None, f"Invalid username or password. {remaining_attempts} attempt(s) remaining before lockout."

def set_session(user):
    import hashlib
    st.session_state["user_id"]   = user["id"]
    st.session_state["username"]  = user["username"]
    st.session_state["full_name"] = user["full_name"]
    st.session_state["role"]      = user["role"]
    st.session_state["email"]     = user["email"]
    st.session_state["must_change_password"] = bool(user["must_change_password"])
    st.session_state["sm_names"]  = db.get_sm_names_for_user(user["id"])
    st.session_state["regional_manager_id"] = user["regional_manager_id"]
    st.session_state["logged_in"] = True
    st.session_state["last_activity"] = datetime.now()
    st.session_state.setdefault("page", "hub")

    # Create and store session token for persistence across page refreshes
    import secrets
    session_token = secrets.token_urlsafe(32)
    try:
        with db.get_conn() as conn:
            conn.execute("UPDATE users SET session_token=? WHERE id=?", (session_token, user["id"]))
        # Store token in URL query params for persistence
        st.query_params["session_token"] = session_token
        st.query_params["user_id"] = str(user["id"])
    except:
        # Column might not exist yet during initial deployment — skip token storage
        pass

def logout():
    for key in ["user_id","username","full_name","role","email","sm_names",
                "regional_manager_id","logged_in","page","selected_customer",
                "selected_test_request","selected_lead","last_activity"]:
        st.session_state.pop(key, None)

    # Clear session token from URL
    st.query_params.clear()


def check_session_timeout() -> bool:
    """
    Returns True if the session is still valid.
    Returns False if the session has timed out (caller should logout and rerun).
    Also refreshes last_activity on each valid call.
    """
    last = st.session_state.get("last_activity")
    if last is None:
        st.session_state["last_activity"] = datetime.now()
        return True
    if (datetime.now() - last).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        return False
    st.session_state["last_activity"] = datetime.now()
    return True

def is_logged_in():
    # Check if already logged in via session state
    if st.session_state.get("logged_in", False):
        return True

    # Check if we can restore session from query params (after page refresh)
    if st.query_params.get("session_token"):
        try:
            token = st.query_params.get("session_token")
            user_id = st.query_params.get("user_id")
            user_id = int(user_id)
            user = db.get_user_by_id(user_id)
            if user and user.get("session_token") == token:
                # Restore session
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user["id"]
                st.session_state["username"] = user["username"]
                st.session_state["full_name"] = user["full_name"]
                st.session_state["role"] = user["role"]
                st.session_state["email"] = user["email"]
                st.session_state["sm_names"] = [s.strip() for s in user.get("sm_names", "").split(",") if s.strip()]
                st.session_state["regional_manager_id"] = user.get("regional_manager_id")
                st.session_state["last_activity"] = datetime.now()
                return True
        except:
            # Token validation failed or column doesn't exist yet — require new login
            pass

    return False

def current_role():
    return st.session_state.get("role", "")

def current_user_id():
    return st.session_state.get("user_id")
