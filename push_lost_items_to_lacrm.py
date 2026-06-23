"""
push_lost_items_to_lacrm.py

Finds items a customer ordered 3+ times in 2025 but hasn't ordered in 2026,
then for each customer:
  1. Adds them to the LACRM group "Regular items not ordered 2026"
  2. Creates a note listing the lost items with order history & avg price

Run: python push_lost_items_to_lacrm.py
"""

import sys
import json
import time
from collections import defaultdict
from datetime import datetime

# Make Windows console handle UTF-8 for pound sign etc.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import database as db
import lacrm

GROUP_NAME = "Regular items not ordered 2026"
MAX_ITEMS_PER_NOTE = 20

# Keywords that mark a sales line as admin/freight, not a real product to chase
NON_PRODUCT_KEYWORDS = [
    "FREIGHT", "CARRIAGE", "HANDLING", "ENGINEERING CHARGE",
    "UPLIFT", "ADMIN", "EXTRA CHARGE", "DELIVERY CHARGE",
    "RESTOCK", "SERVICE CHARGE", "MIN ORDER",
]

# Customer codes to skip — internal / house / freight accounts
SKIP_CUSTOMER_CODES = set()


def _is_real_product(item_code, item_desc):
    code = (item_code or "").strip().upper()
    desc = (item_desc or "").strip().upper()
    if not code:
        return False
    # Filter known admin codes
    if code.startswith("10000"):  # legacy admin range
        return False
    for kw in NON_PRODUCT_KEYWORDS:
        if kw in desc:
            return False
    return True


def _fetch_lost_items():
    """Returns dict keyed by (customer_code, customer_name) -> list of item dicts."""
    sql = """
    WITH item_2025 AS (
        SELECT customer_code, item_code, item_desc,
               COUNT(DISTINCT invoice_no) AS order_count,
               SUM(qty)        AS total_qty,
               SUM(sales_val)  AS total_sales,
               AVG(unit_price) AS avg_price,
               MAX(sale_date)  AS last_order_date
        FROM sales
        WHERE year = 2025
          AND item_code IS NOT NULL AND TRIM(item_code) != ''
          AND sales_val > 0
        GROUP BY customer_code, item_code
        HAVING COUNT(DISTINCT invoice_no) >= 3
    ),
    item_2026 AS (
        SELECT DISTINCT customer_code, item_code
        FROM sales
        WHERE year = 2026 AND item_code IS NOT NULL
    )
    SELECT i.customer_code, c.customer_name,
           i.item_code, i.item_desc,
           i.order_count, i.total_qty, i.total_sales,
           i.avg_price, i.last_order_date
    FROM item_2025 i
    JOIN customers c ON c.customer_code = i.customer_code
    LEFT JOIN item_2026 j
      ON i.customer_code = j.customer_code AND i.item_code = j.item_code
    WHERE j.item_code IS NULL
    ORDER BY i.customer_code, i.total_sales DESC
    """
    with db.get_conn() as conn:
        rows = conn.execute(sql).fetchall()

    by_cust = defaultdict(list)
    for r in rows:
        if r["customer_code"] in SKIP_CUSTOMER_CODES:
            continue
        if not _is_real_product(r["item_code"], r["item_desc"]):
            continue
        by_cust[(r["customer_code"], r["customer_name"])].append(dict(r))
    return by_cust


def _build_note(customer_name, items):
    total_lost = sum(i["total_sales"] for i in items)
    note  = f"REGULAR ITEMS NOT RE-ORDERED IN 2026\n"
    note += f"Auto-generated from Tungaloy Sales Navigator on {datetime.now().strftime('%d %b %Y')}\n"
    note += f"\n"
    note += f"{customer_name} ordered {len(items)} product(s) at least 3 times in 2025 "
    note += f"that have NOT been re-ordered in 2026 so far.\n"
    note += f"Combined 2025 revenue at risk: £{total_lost:,.0f}\n"
    note += f"\n"

    shown = items[:MAX_ITEMS_PER_NOTE]
    for idx, i in enumerate(shown, 1):
        note += f"{idx}. {i['item_code']}  {i['item_desc'] or ''}\n"
        note += f"   2025 orders: {i['order_count']}"
        note += f"  |  Qty: {i['total_qty']:,.0f}"
        note += f"  |  Sales: £{i['total_sales']:,.0f}"
        note += f"  |  Avg price: £{i['avg_price']:,.2f}\n"
        note += f"   Last ordered: {i['last_order_date']}\n\n"

    if len(items) > MAX_ITEMS_PER_NOTE:
        remaining = len(items) - MAX_ITEMS_PER_NOTE
        remaining_val = sum(i["total_sales"] for i in items[MAX_ITEMS_PER_NOTE:])
        note += f"... plus {remaining} more item(s) worth £{remaining_val:,.0f} in 2025. "
        note += f"See Sales Navigator for the full list.\n"

    return note


def _match_lacrm_contact(customer_name):
    """Find the best matching LACRM contact for a customer name. Returns contact_id or None."""
    if not customer_name:
        return None
    results = lacrm.search_contacts(customer_name)
    if not isinstance(results, list) or not results:
        return None

    cname_upper = customer_name.strip().upper()

    # 1. Exact match on CompanyName
    for r in results:
        if (r.get("CompanyName") or "").strip().upper() == cname_upper:
            return r.get("ContactId")

    # 2. Case-insensitive contains (either direction)
    for r in results:
        company = (r.get("CompanyName") or "").strip().upper()
        if company and (company in cname_upper or cname_upper in company):
            return r.get("ContactId")

    # 3. First result as last resort
    return results[0].get("ContactId") if results else None


def main():
    print("=" * 60)
    print("Regular Items Not Ordered 2026 — LACRM Push")
    print("=" * 60)
    print()

    # Check LACRM creds
    ok, msg = lacrm.test_connection()
    if not ok:
        print(f"LACRM connection failed: {msg}")
        sys.exit(1)
    print(f"LACRM: {msg}\n")

    # Build dataset
    by_cust = _fetch_lost_items()
    total_customers = len(by_cust)
    total_items     = sum(len(v) for v in by_cust.values())
    total_value     = sum(sum(i["total_sales"] for i in v) for v in by_cust.values())
    print(f"Customers to process : {total_customers}")
    print(f"Total items          : {total_items:,}")
    print(f"Total 2025 revenue   : £{total_value:,.0f}")
    print()

    # Sort customers by lost revenue (biggest first)
    cust_list = sorted(
        by_cust.items(),
        key=lambda kv: -sum(i["total_sales"] for i in kv[1])
    )

    stats = {
        "ok": 0,
        "no_match": 0,
        "group_ok": 0,
        "group_fail": 0,
        "note_ok": 0,
        "note_fail": 0,
    }
    errors = []
    no_match = []

    for idx, ((code, name), items) in enumerate(cust_list, 1):
        cust_value = sum(i["total_sales"] for i in items)
        print(f"[{idx:>3}/{total_customers}] {name} ({code}) — {len(items)} items — £{cust_value:,.0f}")

        contact_id = _match_lacrm_contact(name)
        if not contact_id:
            print(f"    [SKIP] no LACRM contact matched")
            stats["no_match"] += 1
            no_match.append(f"{name} ({code})")
            continue

        # 1. Add to group
        ok, result = lacrm.add_contact_to_group(contact_id, GROUP_NAME)
        if ok:
            stats["group_ok"] += 1
            print(f"    [OK] added to group")
        else:
            stats["group_fail"] += 1
            print(f"    [FAIL] group add failed: {result}")
            errors.append(f"{name}: group add - {result}")

        # 2. Add note
        note_text = _build_note(name, items)
        ok, result = lacrm.create_note(contact_id, note_text)
        if ok:
            stats["note_ok"] += 1
            stats["ok"] += 1
            print(f"    [OK] note created")
        else:
            stats["note_fail"] += 1
            print(f"    [FAIL] note failed: {result}")
            errors.append(f"{name}: note - {result}")

        # Gentle pacing — LACRM doesn't publish rate limits but be polite
        time.sleep(0.15)

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Customers processed successfully : {stats['ok']}")
    print(f"Groups added                     : {stats['group_ok']}")
    print(f"Notes created                    : {stats['note_ok']}")
    print(f"No LACRM match                   : {stats['no_match']}")
    print(f"Group-add failures               : {stats['group_fail']}")
    print(f"Note failures                    : {stats['note_fail']}")

    # Save unmatched + errors to log files
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if no_match:
        with open(f"lost_items_unmatched_{ts}.txt", "w", encoding="utf-8") as f:
            f.write("Customers with no LACRM contact match:\n\n")
            for n in no_match:
                f.write(f"{n}\n")
        print(f"\nUnmatched customers saved to lost_items_unmatched_{ts}.txt")
    if errors:
        with open(f"lost_items_errors_{ts}.txt", "w", encoding="utf-8") as f:
            f.write("Errors:\n\n")
            for e in errors:
                f.write(f"{e}\n")
        print(f"Errors saved to lost_items_errors_{ts}.txt")


if __name__ == "__main__":
    main()
