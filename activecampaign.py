"""
activecampaign.py — ActiveCampaign API integration for Sales Navigator.

Provides:
  - Connection test
  - Contact sync (create / update by email)
  - Tag management
  - List retrieval
  - Bulk customer sync
"""

import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import database as db

# Thread-local session for connection reuse
_local = threading.local()

def _session():
    if not hasattr(_local, "session"):
        s = requests.Session()
        s.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=20))
        _local.session = s
    return _local.session

# ── API helpers ────────────────────────────────────────────────────────────────

def _creds():
    url = db.get_setting("ac_api_url") or ""
    key = db.get_setting("ac_api_key") or ""
    return url.rstrip("/"), key

def _headers():
    _, key = _creds()
    return {"Api-Token": key, "Content-Type": "application/json"}

def _get(endpoint, params=None):
    base, _ = _creds()
    try:
        r = _session().get(f"{base}/api/3/{endpoint}",
                           headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)

def _post(endpoint, payload):
    base, _ = _creds()
    try:
        r = _session().post(f"{base}/api/3/{endpoint}",
                            headers=_headers(), json=payload, timeout=15)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)

def _put(endpoint, payload):
    base, _ = _creds()
    try:
        r = _session().put(f"{base}/api/3/{endpoint}",
                           headers=_headers(), json=payload, timeout=15)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)


# ── Connection test ────────────────────────────────────────────────────────────

def test_connection():
    """Returns (success: bool, message: str)."""
    base, key = _creds()
    if not base or not key:
        return False, "API URL or Key not configured."
    ok, data = _get("users/me")
    if ok:
        user = data.get("user", {})
        name = user.get("firstName", "") + " " + user.get("lastName", "")
        email = user.get("email", "")
        return True, f"Connected as {name.strip()} ({email})"
    return False, data


# ── Lists ──────────────────────────────────────────────────────────────────────

def get_lists():
    """Returns list of {id, name} dicts."""
    ok, data = _get("lists", params={"limit": 100})
    if not ok:
        return []
    return [{"id": l["id"], "name": l["name"]} for l in data.get("lists", [])]


# ── Tags ───────────────────────────────────────────────────────────────────────

def get_tags():
    """Returns list of {id, tag} dicts."""
    ok, data = _get("tags", params={"limit": 100})
    if not ok:
        return []
    return [{"id": t["id"], "tag": t["tag"]} for t in data.get("tags", [])]

def ensure_tag(tag_name):
    """Get or create a tag by name. Returns tag id or None."""
    tags = get_tags()
    for t in tags:
        if t["tag"].lower() == tag_name.lower():
            return t["id"]
    ok, data = _post("tags", {"tag": {"tag": tag_name, "tagType": "contact"}})
    if ok:
        return data.get("tag", {}).get("id")
    return None

def add_tag_to_contact(contact_id, tag_id):
    ok, _ = _post("contactTags", {"contactTag": {
        "contact": str(contact_id),
        "tag":     str(tag_id)
    }})
    return ok


# ── Contact sync ───────────────────────────────────────────────────────────────

def sync_contact(email, first_name="", last_name="",
                 phone="", organisation="",
                 list_ids=None, tag_names=None,
                 custom_fields=None):
    """
    Create or update a contact in ActiveCampaign.
    Returns (success: bool, contact_id or error_message).

    custom_fields: list of {"field": field_id, "value": "..."}
    """
    payload = {"contact": {
        "email":     email,
        "firstName": first_name,
        "lastName":  last_name,
        "phone":     phone or "",
    }}
    ok, data = _post("contact/sync", payload)
    if not ok:
        return False, data

    contact_id = data.get("contact", {}).get("id")
    if not contact_id:
        return False, "No contact ID returned"

    # Add to lists
    for lid in (list_ids or []):
        _post("contactLists", {"contactList": {
            "list":    str(lid),
            "contact": str(contact_id),
            "status":  "1"
        }})

    # Add tags
    for tag_name in (tag_names or []):
        tag_id = ensure_tag(tag_name)
        if tag_id:
            add_tag_to_contact(contact_id, tag_id)

    # Custom fields
    for cf in (custom_fields or []):
        _post("fieldValues", {"fieldValue": {
            "contact": str(contact_id),
            "field":   str(cf["field"]),
            "value":   str(cf["value"]),
        }})

    return True, contact_id


def get_contact_by_email(email):
    """Returns contact dict or None."""
    ok, data = _get("contacts", params={"email": email})
    if not ok:
        return None
    contacts = data.get("contacts", [])
    return contacts[0] if contacts else None


# ── Custom fields ──────────────────────────────────────────────────────────────

def get_custom_fields():
    """Returns list of {id, title, type} dicts."""
    ok, data = _get("fields", params={"limit": 100})
    if not ok:
        return []
    return [{"id": f["id"], "title": f["title"], "type": f["type"]}
            for f in data.get("fields", [])]

def ensure_custom_field(title, field_type="TEXT"):
    """Get or create a custom field. Returns field id or None."""
    fields = get_custom_fields()
    for f in fields:
        if f["title"].lower() == title.lower():
            return f["id"]
    ok, data = _post("fields", {"field": {
        "title": title,
        "type":  field_type,
        "visible": "1",
        "perstag": title.upper().replace(" ", "_"),
    }})
    if ok:
        return data.get("field", {}).get("id")
    return None


# ── Bulk customer sync ─────────────────────────────────────────────────────────

def sync_customers_to_ac(customer_rows, list_id=None, tag_name="Sales Navigator",
                          progress_callback=None):
    """
    Sync customer contacts to ActiveCampaign efficiently.
    Pre-fetches tags and custom fields once, then does minimal calls per contact.
    Returns (synced_count, skipped_count, errors).
    """
    total = len(customer_rows)

    # ── Pre-flight: resolve/create all tags once ──────────────────────────────
    needed_tags = {tag_name}
    for c in customer_rows:
        if c.get("rep_name"):
            needed_tags.add(c["rep_name"])

    existing_tags = {t["tag"]: t["id"] for t in get_tags()}
    tag_id_cache = {}
    for t in needed_tags:
        if t in existing_tags:
            tag_id_cache[t] = existing_tags[t]
        else:
            ok, data = _post("tags", {"tag": {"tag": t, "tagType": "contact"}})
            if ok:
                tag_id_cache[t] = data.get("tag", {}).get("id")

    # ── Pre-flight: resolve/create custom fields once ─────────────────────────
    existing_fields = {f["title"].lower(): f["id"] for f in get_custom_fields()}

    def _get_or_create_field(title):
        key = title.lower()
        if key in existing_fields:
            return existing_fields[key]
        ok, data = _post("fields", {"field": {
            "title": title, "type": "TEXT", "visible": "1",
            "perstag": title.upper().replace(" ", "_"),
        }})
        if ok:
            fid = data.get("field", {}).get("id")
            existing_fields[key] = fid
            return fid
        return None

    rep_fid  = _get_or_create_field("Sales Rep")
    reg_fid  = _get_or_create_field("Region")
    type_fid = _get_or_create_field("Customer Type")
    code_fid = _get_or_create_field("Customer Code")

    # ── Sync contacts in parallel ─────────────────────────────────────────────
    synced  = 0
    skipped = 0
    errors  = []
    lock    = threading.Lock()
    done    = [0]

    def _sync_one(c):
        email = (c.get("email") or "").strip()
        if not email:
            return "skip", None

        name  = (c.get("contact_name") or c.get("customer_name") or "").strip()
        parts = name.split(" ", 1)
        first = parts[0] if parts else ""
        last  = parts[1] if len(parts) > 1 else ""

        ok, data = _post("contact/sync", {"contact": {
            "email": email, "firstName": first, "lastName": last,
        }})
        if not ok:
            return "error", f"{email}: {data}"

        contact_id = data.get("contact", {}).get("id")

        if list_id and contact_id:
            _post("contactLists", {"contactList": {
                "list": str(list_id), "contact": str(contact_id), "status": "1"
            }})

        tags_to_apply = [tag_name]
        if c.get("rep_name"):
            tags_to_apply.append(c["rep_name"])
        for t in tags_to_apply:
            tid = tag_id_cache.get(t)
            if tid and contact_id:
                _post("contactTags", {"contactTag": {
                    "contact": str(contact_id), "tag": str(tid)
                }})

        field_vals = []
        if rep_fid  and c.get("rep_name"):      field_vals.append((rep_fid,  c["rep_name"]))
        if reg_fid  and c.get("region"):        field_vals.append((reg_fid,  c["region"]))
        if type_fid and c.get("customer_type"): field_vals.append((type_fid, c["customer_type"]))
        if code_fid and c.get("customer_code"): field_vals.append((code_fid, c["customer_code"]))
        for fid, val in field_vals:
            _post("fieldValues", {"fieldValue": {
                "contact": str(contact_id), "field": str(fid), "value": str(val)
            }})

        return "ok", None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_sync_one, c): c for c in customer_rows}
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


def sync_ac_contacts_to_db(progress_callback=None):
    """
    Pull ALL data from Active Campaign (contacts + prospects, excluding unsubscribed).
    Extracts: email, name, phone, address, city, state, postal code, country, company, notes.
    Returns (imported_count, skipped_unsubscribed, error_count, errors_list)
    """
    imported = 0
    skipped_unsub = 0
    errors = []
    all_people = []

    try:
        # Fetch all contacts from AC
        ok, contacts_data = _get("contacts", params={"limit": 100})
        if ok:
            all_people.extend(contacts_data.get("contacts", []))

        # Fetch all prospects from AC (if endpoint exists)
        ok, prospects_data = _get("contacts", params={"limit": 100, "filters[p_stage]": "prospect"})
        if ok:
            all_people.extend(prospects_data.get("contacts", []))

        total = len(all_people)
        if total == 0:
            return 0, 0, 1, ["No contacts or prospects found in ActiveCampaign"]

        with db.get_conn() as conn:
            for i, ac_contact in enumerate(all_people):
                try:
                    email = ac_contact.get("email", "").strip()
                    if not email:
                        continue

                    # Skip unsubscribed contacts
                    unsub_status = ac_contact.get("unsubscribeStatus", "")
                    if unsub_status == "2" or ac_contact.get("deleted") == 1:
                        skipped_unsub += 1
                        continue

                    # Extract all available fields (handle None values)
                    first_name = (ac_contact.get("firstName") or "").strip()
                    last_name = (ac_contact.get("lastName") or "").strip()
                    full_name = f"{first_name} {last_name}".strip()
                    company = ((ac_contact.get("organization") or "") or (ac_contact.get("company") or "")).strip()
                    phone = (ac_contact.get("phone") or "").strip()
                    address = (ac_contact.get("address") or "").strip()
                    city = (ac_contact.get("city") or "").strip()
                    state = (ac_contact.get("state") or "").strip()
                    postal_code = ((ac_contact.get("zipcode") or "") or (ac_contact.get("postal_code") or "")).strip()
                    country = (ac_contact.get("country") or "").strip()
                    notes = (ac_contact.get("notes") or "").strip()
                    ac_id = ac_contact.get("id") or ""

                    # Insert or update contact in database with all fields
                    conn.execute("""
                        INSERT OR REPLACE INTO customer_contacts
                        (email, first_name, last_name, full_name, company, phone, address,
                         city, state, postal_code, country, notes, synced_from_ac, ac_contact_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """, (email, first_name, last_name, full_name, company, phone, address,
                          city, state, postal_code, country, notes, ac_id))

                    imported += 1
                    if progress_callback:
                        progress_callback(i + 1, total)

                except Exception as e:
                    errors.append(f"Contact import error: {str(e)}")

    except Exception as e:
        errors.append(f"AC sync failed: {str(e)}")

    return imported, skipped_unsub, len(errors), errors
