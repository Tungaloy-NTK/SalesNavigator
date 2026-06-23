"""
lacrm.py — Less Annoying CRM integration for Sales Navigator.

Uses LACRM v1 API (v2 requires different auth not yet available).
API base: https://api.lessannoyingcrm.com
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import database as db

BASE_URL = "https://api.lessannoyingcrm.com"

# ── Credentials ────────────────────────────────────────────────────────────────

def _creds():
    return (
        db.get_setting("lacrm_user_code") or "",
        db.get_setting("lacrm_api_key")   or "",
    )

def _params(extra=None):
    user_code, api_token = _creds()
    p = {"UserCode": user_code, "APIToken": api_token}
    if extra:
        p.update(extra)
    return p

# ── HTTP helpers ───────────────────────────────────────────────────────────────

_local = threading.local()

def _session():
    if not hasattr(_local, "s"):
        from requests.adapters import HTTPAdapter
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=10))
        _local.s = s
    return _local.s

def _get(function, extra=None):
    try:
        r = _session().get(BASE_URL, params=_params({"Function": function, **(extra or {})}), timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("Success") is False:
            return False, data.get("Error", "Unknown error")
        return True, data
    except Exception as e:
        return False, str(e)

def _post(function, payload):
    import json
    try:
        p = _params({"Function": function})
        r = _session().post(BASE_URL, params=p,
                            data={"Parameters": json.dumps(payload)},
                            timeout=15)
        # LACRM returns 400 with a JSON body on validation errors — read
        # the body before checking status so we get the real error message.
        try:
            data = r.json()
        except Exception:
            r.raise_for_status()
            return False, f"Non-JSON response: {r.text[:200]}"
        if isinstance(data, dict) and data.get("Success") is False:
            return False, data.get("Error", "Unknown error")
        return True, data
    except Exception as e:
        return False, str(e)


# ── Connection test ────────────────────────────────────────────────────────────

def test_connection():
    """Returns (success, message)."""
    user_code, api_token = _creds()
    if not user_code or not api_token:
        return False, "LACRM credentials not configured."
    ok, data = _get("SearchContacts", {"SearchTerms": "test", "Page": 1})
    if ok:
        return True, f"Connected to Less Annoying CRM (User: {user_code})"
    return False, str(data)


# ── Contacts ───────────────────────────────────────────────────────────────────

def search_contacts(search_term, page=1):
    """Search contacts by name/email. Returns list of contact dicts."""
    ok, data = _get("SearchContacts", {"SearchTerms": search_term, "Page": page})
    if not ok:
        return []
    return data.get("Result", data) if isinstance(data, dict) else data

def get_contact(contact_id):
    ok, data = _get("GetContact", {"ContactId": contact_id})
    if not ok:
        return None
    return data.get("Result", data)

def create_contact(first_name, last_name="", email="", phone="",
                   company_name="", background=""):
    """Create a new contact. Returns (success, contact_id or error)."""
    payload = {
        "FirstName":   first_name,
        "LastName":    last_name,
        "Email":       [{"Text": email, "Type": "Work"}] if email else [],
        "Phone":       [{"Text": phone, "Type": "Work"}] if phone else [],
        "CompanyName": company_name,
        "BackgroundInfo": background,
    }
    ok, data = _post("CreateContact", payload)
    if not ok:
        return False, data
    contact_id = data.get("ContactId") or (data.get("Result", {}) or {}).get("ContactId")
    return True, contact_id

def update_contact(contact_id, fields: dict):
    """Update fields on an existing contact."""
    payload = {"ContactId": contact_id, **fields}
    ok, data = _post("UpdateContact", payload)
    return ok, data


# ── Notes ──────────────────────────────────────────────────────────────────────

def create_note(contact_id, note_text):
    """Add a note to a contact."""
    ok, data = _post("CreateNote", {
        "ContactId": contact_id,
        "Note":      note_text,
    })
    return ok, data


# ── Groups ─────────────────────────────────────────────────────────────────────

def add_contact_to_group(contact_id, group_name):
    """
    Add a contact to a named group in LACRM. Auto-creates the group if it
    doesn't exist. Returns (success, data_or_error).
    """
    ok, data = _post("AddContactToGroup", {
        "ContactId": contact_id,
        "GroupName": group_name,
    })
    return ok, data


# ── Tasks ──────────────────────────────────────────────────────────────────────

def create_task(contact_id, description, due_date=None, assigned_to=None):
    """Create a task linked to a contact."""
    payload = {
        "ContactId":   contact_id,
        "Description": description,
    }
    if due_date:
        payload["DueDate"] = str(due_date)
    if assigned_to:
        payload["AssignedTo"] = assigned_to
    ok, data = _post("CreateTask", payload)
    return ok, data


# ── Pipelines ─────────────────────────────────────────────────────────────────

def get_pipelines():
    ok, data = _get("GetPipelines")
    if not ok:
        return []
    result = data.get("Result", data)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return list(result.values())
    return []

def create_pipeline_item(contact_id, pipeline_id, status_id=None, priority="Medium"):
    payload = {
        "ContactId":  contact_id,
        "PipelineId": pipeline_id,
        "Priority":   priority,
    }
    if status_id:
        payload["StatusId"] = status_id
    ok, data = _post("CreatePipelineItem", payload)
    return ok, data


# ── Bulk contact sync ──────────────────────────────────────────────────────────

def sync_contacts_to_lacrm(contact_rows, progress_callback=None):
    """
    Sync customer contacts from Sales Navigator to LACRM.
    Each row needs: contact_name, email, customer_name (company).
    Returns (synced, skipped, errors).
    """
    total   = len(contact_rows)
    synced  = 0
    skipped = 0
    errors  = []
    lock    = threading.Lock()
    done    = [0]

    def _sync_one(c):
        email = (c.get("email") or "").strip()
        if not email:
            return "skip", None

        name   = (c.get("contact_name") or "").strip()
        parts  = name.split(" ", 1)
        first  = parts[0] if parts else (c.get("customer_name") or "")
        last   = parts[1] if len(parts) > 1 else ""
        company= c.get("customer_name") or ""
        rep    = c.get("rep_name") or ""

        # Check if contact already exists
        results = search_contacts(email)
        existing_id = None
        for r in (results if isinstance(results, list) else []):
            emails = r.get("Email", []) or []
            for e in emails:
                if (e.get("Text") or "").lower() == email.lower():
                    existing_id = r.get("ContactId")
                    break
            if existing_id:
                break

        if existing_id:
            # Add a background note with rep info if not already there
            bg = f"Sales Rep: {rep} | Company: {company}" if rep else f"Company: {company}"
            update_contact(existing_id, {"BackgroundInfo": bg})
            return "ok", existing_id
        else:
            bg = f"Sales Rep: {rep} | Synced from Tungaloy Sales Navigator" if rep else "Synced from Tungaloy Sales Navigator"
            ok, result = create_contact(
                first_name   = first,
                last_name    = last,
                email        = email,
                company_name = company,
                background   = bg,
            )
            if ok:
                return "ok", result
            else:
                return "error", f"{email}: {result}"

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_sync_one, c): c for c in contact_rows}
        for future in as_completed(futures):
            result, msg = future.result()
            with lock:
                done[0] += 1
                if result == "ok":
                    synced += 1
                elif result == "skip":
                    skipped += 1
                else:
                    errors.append(msg)
                if progress_callback:
                    progress_callback(done[0], total)

    return synced, skipped, errors


# ── Visit → Note ───────────────────────────────────────────────────────────────

def log_visit_to_lacrm(visit: dict):
    """
    When a rep logs a visit in Sales Navigator, push it as a note in LACRM.
    visit dict needs: customer_name, visit_date, contact_name, notes, outcome, rep_name
    Returns (success, message).
    """
    customer_name = visit.get("customer_name", "")
    results = search_contacts(customer_name)
    contact_id = None
    for r in (results if isinstance(results, list) else []):
        if r.get("CompanyName", "").lower() == customer_name.lower():
            contact_id = r.get("ContactId")
            break
    if not contact_id and results:
        contact_id = results[0].get("ContactId") if isinstance(results, list) else None

    if not contact_id:
        return False, f"No LACRM contact found for '{customer_name}'"

    note = (
        f"Visit logged by {visit.get('rep_name', 'Rep')} on {visit.get('visit_date', '')}\n"
        f"Contact: {visit.get('contact_name', '')}\n"
        f"Notes: {visit.get('notes', '')}\n"
        f"Outcome: {visit.get('outcome', '')}"
    )
    ok, _ = create_note(contact_id, note.strip())
    return ok, "Note created in LACRM" if ok else "Failed to create note"
