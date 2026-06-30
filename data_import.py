import pandas as pd
import sqlite3
from datetime import datetime
import database as db
from auth import SM_NAME_TO_USERNAME

COLUMN_MAP = {
    # Customer code / name variants
    "Customer":         "customer_code",
    "Cust. Desc.":      "customer_name",
    "Cust. Desc. 2":    "customer_name",   # newer export format
    "Customer Name":    "customer_name",
    # Sales manager
    "SM Name":          "sm_name",
    "SM Name ":         "sm_name",         # trailing space variant
    # Item
    "Item":             "item_code",
    "Item desc.":       "item_desc",
    # Date / period
    "Date":             "sale_date",
    "Month":            "month",
    "Year":             "year",
    # Financials
    "Unit price":       "unit_price",
    "Unit cost":        "unit_cost",
    "Sales val.":       "sales_val",
    "Cost val.":        "cost_val",
    "G.P val":          "gp_val",
    "Qty.":             "qty",
    # Reference
    "Invoice no.":      "invoice_no",
    "App Dsc":          "app_dsc",
    # Address / warehouse
    "Ship to Address":  "ship_to_address",
    "Ship To Address":  "ship_to_address",
    "Ship-to Address":  "ship_to_address",
    "Delivery Address": "ship_to_address",
    "whs":              "whs_code",
    "Whs":              "whs_code",
    "WHS":              "whs_code",
    # Customer enrichment (newer format includes these inline)
    "Post Area":        "post_area",
    "Main Distributors":"main_distributor",
    "Region":           "region",
    "Customer Type":    "customer_type",
    # Item enrichment
    "Brand":            "brand",
}

def parse_gp_excel(file_obj):
    """
    Parse the GP report Excel file. Returns a cleaned DataFrame.
    Looks for the 'Display' sheet and maps columns.
    """
    xl = pd.read_excel(file_obj, sheet_name=None, header=None, dtype=str)

    # Find the Display sheet (case-insensitive)
    sheet_name = None
    for name in xl.keys():
        if "display" in name.lower():
            sheet_name = name
            break
    if sheet_name is None:
        sheet_name = list(xl.keys())[0]

    raw = xl[sheet_name]

    # Find the header row — first row where 'Customer' or 'SM Name' appears
    header_row = 0
    for i, row in raw.iterrows():
        row_vals = [str(v).strip() for v in row.values]
        if "Customer" in row_vals or "SM Name" in row_vals:
            header_row = i
            break

    df = pd.read_excel(file_obj, sheet_name=sheet_name, header=header_row, dtype=str)

    # Case-insensitive column rename
    col_map_lower = {k.lower(): v for k, v in COLUMN_MAP.items()}
    rename = {col: col_map_lower[col.lower().strip()] for col in df.columns if col.lower().strip() in col_map_lower}
    df = df.rename(columns=rename)

    required = ["customer_code", "customer_name", "sm_name", "sale_date", "sales_val"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    # Drop rows with no customer code
    df = df[df["customer_code"].notna() & (df["customer_code"].str.strip() != "")]

    # Clean numeric columns
    for col in ["unit_price", "unit_cost", "sales_val", "cost_val", "gp_val", "qty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse dates
    if "sale_date" in df.columns:
        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    for col in ["month", "year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    df["customer_code"] = df["customer_code"].str.strip()
    df["customer_name"] = df["customer_name"].fillna("").str.strip()
    df["sm_name"] = df["sm_name"].fillna("").str.strip()

    return df

def import_to_db(df, import_batch=None):
    """
    Imports a parsed DataFrame into the database.
    Updates customers table and inserts new sales rows.
    Returns dict with counts.
    """
    if import_batch is None:
        import_batch = datetime.now().strftime("%Y-%m-%d %H:%M")

    customers_updated = 0
    sales_inserted = 0
    sales_skipped = 0
    address_backfilled = 0

    # Build user_id lookup from SM name mapping — single query
    sm_to_user = db.get_all_sm_name_mappings()

    # Upsert customers
    customer_rows = df[["customer_code","customer_name","sm_name"]].drop_duplicates("customer_code")
    with db.get_conn() as conn:
        for _, row in customer_rows.iterrows():
            user_id = sm_to_user.get(row["sm_name"])
            conn.execute("""
                INSERT INTO customers (customer_code, customer_name, sm_name, user_id)
                VALUES (?,?,?,?)
                ON CONFLICT(customer_code) DO UPDATE SET
                    customer_name=excluded.customer_name,
                    sm_name=excluded.sm_name,
                    user_id=excluded.user_id
            """, (row["customer_code"], row["customer_name"], row["sm_name"], user_id))
            customers_updated += 1

    # Insert sales (skip duplicates by invoice+item+customer)
    sales_cols = ["customer_code","sm_name","item_code","item_desc","sale_date",
                  "month","year","unit_price","unit_cost","sales_val","cost_val",
                  "gp_val","qty","invoice_no","app_dsc","ship_to_address","whs_code"]
    existing_cols = [c for c in sales_cols if c in df.columns]

    with db.get_conn() as conn:
        for _, row in df[existing_cols].iterrows():
            # Avoid duplicate imports: check invoice+item+customer combo
            inv  = row.get("invoice_no", None)
            item = row.get("item_code", None)
            cust = row["customer_code"]

            if inv and item:
                existing_row = conn.execute("""
                    SELECT id, ship_to_address, whs_code FROM sales
                    WHERE invoice_no=? AND item_code=? AND customer_code=?
                """, (str(inv), str(item), cust)).fetchone()
                if existing_row:
                    # Backfill ship_to_address if missing but present in this file
                    new_addr = row.get("ship_to_address", None)
                    if new_addr and not pd.isna(new_addr) and str(new_addr).strip() and not existing_row.get("ship_to_address"):
                        conn.execute(
                            "UPDATE sales SET ship_to_address=? WHERE id=?",
                            (str(new_addr).strip(), existing_row["id"])
                        )
                        address_backfilled += 1
                    # Backfill whs_code if missing but present in this file
                    new_whs = row.get("whs_code", None)
                    if new_whs and not pd.isna(new_whs) and str(new_whs).strip() and not existing_row.get("whs_code"):
                        conn.execute(
                            "UPDATE sales SET whs_code=? WHERE id=?",
                            (str(new_whs).strip(), existing_row["id"])
                        )
                    sales_skipped += 1
                    continue

            vals = {c: (None if pd.isna(row[c]) else row[c]) for c in existing_cols}
            vals["import_batch"] = import_batch

            cols = list(vals.keys())
            placeholders = ",".join(["?"] * len(cols))
            conn.execute(
                f"INSERT INTO sales ({','.join(cols)}) VALUES ({placeholders})",
                [vals[c] for c in cols]
            )
            sales_inserted += 1

    return {
        "customers_updated":  customers_updated,
        "sales_inserted":     sales_inserted,
        "sales_skipped":      sales_skipped,
        "address_backfilled": address_backfilled,
        "import_batch":       import_batch,
    }

def parse_item_info(file_obj):
    """
    Parse the Item Info Excel file.
    Expects columns: Item, Brand, Item Type.
    Returns a cleaned DataFrame.
    """
    df = pd.read_excel(file_obj, dtype=str)

    if df.columns[0].startswith("Unnamed"):
        df.columns = [str(v).strip() for v in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)

    col_map = {
        "Item":      "item_code",
        "Brand":     "brand",
        "Item Type": "item_type",
    }
    col_map_lower = {k.lower(): v for k, v in col_map.items()}
    rename = {c: col_map_lower[c.lower().strip()] for c in df.columns if c.lower().strip() in col_map_lower}
    df = df.rename(columns=rename)

    if "item_code" not in df.columns:
        raise ValueError("Could not find an 'Item' column in this file.")

    df = df[df["item_code"].notna() & (df["item_code"].str.strip() != "")]
    df["item_code"] = df["item_code"].str.strip()
    for col in ["brand", "item_type"]:
        if col in df.columns:
            df[col] = df[col].fillna("").str.strip()

    return df


def import_item_info(df):
    """
    Upsert item rows (brand, item_type) into the items table, keyed on item_code.
    Creates new items or updates existing ones.
    Returns dict with counts.
    """
    inserted = 0
    updated = 0

    upsert_cols = [c for c in ["brand", "item_type"] if c in df.columns]
    set_clause  = ", ".join(f"{c}=excluded.{c}" for c in upsert_cols)

    with db.get_conn() as conn:
        for _, row in df.iterrows():
            code   = row["item_code"]
            brand  = row.get("brand",     "") or None
            itype  = row.get("item_type", "") or None

            existing = conn.execute(
                "SELECT id FROM items WHERE item_code=?", (code,)
            ).fetchone()

            conn.execute(f"""
                INSERT INTO items (item_code, brand, item_type)
                VALUES (?, ?, ?)
                ON CONFLICT(item_code) DO UPDATE SET
                    {set_clause}
            """, (code, brand, itype))

            if existing:
                updated += 1
            else:
                inserted += 1

    return {"inserted": inserted, "updated": updated}


def parse_customer_info(file_obj):
    """
    Parse the Customer Info Excel file.
    Expects columns: Customer, Post Area, Main Distributors, Region, Customer Type.
    Returns a cleaned DataFrame with standardised column names.
    """
    df = pd.read_excel(file_obj, dtype=str)

    # If row 0 contains the real headers (unnamed columns), fix them
    if df.columns[0].startswith("Unnamed"):
        df.columns = [str(v).strip() for v in df.iloc[0]]
        df = df.iloc[1:].reset_index(drop=True)

    # Normalise column names
    col_map = {
        "Customer":          "customer_code",
        "Customer Code":     "customer_code",
        "Post Area":         "post_area",
        "Main Distributors": "main_distributor",
        "Region":            "region",
        "Customer Type":     "customer_type",
        "City":              "city",
        "Salesman Name":     "salesman_name",
        "SALESMAN_NAME":     "salesman_name",
    }
    col_map_lower = {k.lower(): v for k, v in col_map.items()}
    rename = {c: col_map_lower[c.lower().strip()] for c in df.columns if c.lower().strip() in col_map_lower}
    df = df.rename(columns=rename)

    if "customer_code" not in df.columns:
        raise ValueError("Could not find a 'Customer' column in this file.")

    df = df[df["customer_code"].notna() & (df["customer_code"].str.strip() != "")]
    df["customer_code"] = df["customer_code"].str.strip()
    for col in ["post_area", "main_distributor", "region", "customer_type"]:
        if col in df.columns:
            df[col] = df[col].fillna("").str.strip()

    return df


def import_customer_info(df):
    """
    Upsert customer info rows (post_area, main_distributor, region, customer_type)
    into the customers table, matching on customer_code.
    Only updates customers that already exist; skips unknown codes.
    Returns dict with counts.
    """
    updated = 0
    skipped = 0

    update_cols = [c for c in ["post_area", "main_distributor", "region", "customer_type", "city", "salesman_name"] if c in df.columns]

    with db.get_conn() as conn:
        for _, row in df.iterrows():
            code = row["customer_code"]
            existing = conn.execute(
                "SELECT id FROM customers WHERE customer_code=?", (code,)
            ).fetchone()

            if not existing:
                skipped += 1
                continue

            set_clause = ", ".join(f"{c}=?" for c in update_cols)
            values = [row[c] if row[c] != "" else None for c in update_cols]
            values.append(code)
            conn.execute(
                f"UPDATE customers SET {set_clause} WHERE customer_code=?",
                values
            )
            updated += 1

    return {"updated": updated, "skipped": skipped}


def preview_import(df, max_rows=10):
    """Returns a preview dict for display before confirming import."""
    return {
        "total_rows": len(df),
        "customers": df["customer_code"].nunique(),
        "sm_names": df["sm_name"].unique().tolist(),
        "date_range": (
            df["sale_date"].min() if "sale_date" in df.columns else "?",
            df["sale_date"].max() if "sale_date" in df.columns else "?",
        ),
        "sample": df.head(max_rows),
    }
