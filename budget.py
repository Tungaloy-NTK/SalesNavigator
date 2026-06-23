"""
budget.py — Budget vs Actual 2026 page for the Sales Navigator app.

Upload your 2026 budget Excel file, then view actual sales against budget
broken down by Application Family and Product Line.

Excel format expected:
  Sheet: "TL UK BUD 26", header row 3 (0-indexed)
  Col 0  : app_code       (AA, NB, AC …)
  Col 2  : App Dsc        (description)
  Col 3  : FAMILY         (TURN/GROOVE, TURNING, HOLE MAKING, MILLING …)
  Col 4  : PRODUCT LINE
  Col 5  : Qty 2026 B     (annual qty budget)
  Cols 6-17 : Jan-Dec 2026 monthly £ budget (datetime column headers)
  Col 18 : Sales 2026 B   (annual £ budget total)
"""

import io
import re
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import streamlit as st
from datetime import date, datetime
import database as db

# ── Colour palette ─────────────────────────────────────────────────────────────
FAMILY_COLOURS = {
    "TURN/GROOVE":  "#1a6fb5",
    "TURNING":      "#2196F3",
    "HOLE MAKING":  "#e67e22",
    "MILLING":      "#27ae60",
    "TOOLING":      "#8e44ad",
    "OTHERS":       "#7f8c8d",
    "INNOTOOL":     "#c0392b",
}
DEFAULT_COLOUR = "#34495e"

RAG_GREEN  = "#27ae60"
RAG_AMBER  = "#e67e22"
RAG_RED    = "#c0392b"

MONTH_COLS = db.BUDGET_MONTH_COLS  # budget_jan … budget_dec
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── Excel parsing ──────────────────────────────────────────────────────────────

def _parse_budget_excel(file_obj):
    """
    Parse the budget Excel file and return a list of row dicts ready for upsert.
    """
    xl = pd.read_excel(file_obj, sheet_name=None, header=None, dtype=object)

    # Find the budget sheet
    sheet_name = None
    for name in xl.keys():
        if "bud" in name.lower():
            sheet_name = name
            break
    if sheet_name is None:
        sheet_name = list(xl.keys())[0]

    # Read with header=3 (row index 3 = 4th row)
    df = pd.read_excel(file_obj, sheet_name=sheet_name, header=3, dtype=object)

    if len(df.columns) < 19:
        raise ValueError(
            f"Expected at least 19 columns but found {len(df.columns)}. "
            "Check the sheet and header row."
        )

    cols = list(df.columns)

    # Cols 6-17  = monthly QTY budget (datetime headers)
    # Cols 19-30 = monthly £ SALES budget (Excel serial date headers) — this is what we need
    monthly_col_indices = list(range(19, 31))

    rows = []
    for _, row in df.iterrows():
        app_code = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if not app_code or app_code in ("nan", "1", "None"):
            continue
        # Skip rows that look like subtotals/headers
        if len(app_code) > 6:
            continue

        app_desc    = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        family      = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        product_line= str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""

        def _num(val):
            try:
                v = float(val)
                return None if (pd.isna(v) or np.isnan(v)) else v
            except Exception:
                return None

        qty_budget   = _num(row.iloc[5])
        sales_budget = _num(row.iloc[18])

        monthly = {}
        for i, mcol in enumerate(MONTH_COLS):
            monthly[mcol] = _num(row.iloc[monthly_col_indices[i]])

        r = {
            "app_code":    app_code,
            "app_desc":    app_desc,
            "family":      family,
            "product_line":product_line,
            "sales_budget": sales_budget,   # stored as annual total in DB
            "qty_budget":  qty_budget,
        }
        r.update(monthly)
        rows.append(r)

    if not rows:
        raise ValueError("No valid budget rows found. Check the file format.")

    return rows


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rag(var_pct):
    """Return RAG colour based on variance %."""
    if var_pct is None:
        return "#999"
    if var_pct >= -5:
        return RAG_GREEN
    if var_pct >= -15:
        return RAG_AMBER
    return RAG_RED

def _fmt_gbp(val):
    if val is None:
        return "—"
    sign = "-" if val < 0 else ""
    return f"{sign}£{abs(val):,.0f}"

def _fmt_pct(val):
    if val is None:
        return "—"
    return f"{val:+.1f}%"

def _family_colour(family):
    return FAMILY_COLOURS.get(family, DEFAULT_COLOUR)


# ── Bar chart: actual vs budget by product line ────────────────────────────────

def _bar_chart(rows, family, date_from=None, date_to=None):
    labels   = [r["app_desc"] or r["app_code"] for r in rows]
    budgets  = [r["period_budget"] or 0 for r in rows]
    actuals  = [r["actual_sales"]  or 0 for r in rows]
    prior    = [r.get("prior_sales") or 0 for r in rows]
    colour   = _family_colour(family)

    # Build year labels for legend
    cur_yr  = (date_from or date(2026, 1, 1)).year
    pri_yr  = cur_yr - 1

    n  = len(labels)
    y  = np.arange(n)
    h  = 0.25   # thinner bars to fit 3 per row

    fig_h = max(4, n * 0.65)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    ax.barh(y + h,   prior,    h, color="#aaaaaa", label=f"Actual {pri_yr}", zorder=2)
    ax.barh(y,       actuals,  h, color=colour,    label=f"Actual {cur_yr}", zorder=2)
    ax.barh(y - h,   budgets,  h, color="#cccccc", label=f"Budget {cur_yr}",
            edgecolor="#888", linewidth=0.5, zorder=2)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, color="#333", fontsize=7)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"£{x/1000:.0f}k" if x >= 1000 else f"£{x:.0f}"))
    ax.tick_params(colors="#333", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#ddd")
    ax.legend(fontsize=7, facecolor="white", labelcolor="#333",
              framealpha=0.9, loc="lower right")
    ax.set_title(f"{family} — {pri_yr} vs {cur_yr} Actual vs Budget",
                 color="#333", fontsize=9, pad=6)
    ax.axvline(0, color="#ccc", linewidth=0.5)
    ax.invert_yaxis()
    plt.tight_layout(pad=1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Cumulative monthly chart ───────────────────────────────────────────────────

def _cumulative_chart(rows, family, current_month=None):
    """
    Line chart: cumulative budget vs cumulative actual by month (Jan-Dec).
    current_month: int 1-12, draws a vertical line at end of current month.
    """
    # Sum monthly budget across all product lines in this family
    bud_monthly = np.zeros(12)
    for r in rows:
        for i, mcol in enumerate(MONTH_COLS):
            bud_monthly[i] += r.get(mcol) or 0

    bud_cumul = np.cumsum(bud_monthly)

    # Actual monthly totals — rows carry actual_sales for total period,
    # but for the cumulative chart we need monthly breakdown via DB
    # (passed in via `rows` enriched with month data if available)
    act_monthly = np.zeros(12)
    for r in rows:
        for i in range(12):
            k = f"actual_m{i+1:02d}"
            act_monthly[i] += r.get(k) or 0
    act_cumul = np.cumsum(act_monthly)

    # Only plot actual up to current month
    if current_month:
        act_cumul[current_month:] = np.nan

    colour = _family_colour(family)
    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    ax.plot(MONTH_LABELS, bud_cumul, color="#888", linestyle="--",
            linewidth=1.5, label="Budget (cumulative)", zorder=2)
    ax.plot(MONTH_LABELS, act_cumul, color=colour, linewidth=2,
            label="Actual (cumulative)", zorder=3)

    if current_month and 1 <= current_month <= 12:
        ax.axvline(current_month - 1, color="#555", linewidth=0.8, linestyle=":")

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"£{x/1000:.0f}k"))
    ax.tick_params(colors="white", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#333")
    ax.legend(fontsize=7, facecolor="#1a1a2e", labelcolor="white", framealpha=0.8)
    ax.set_title(f"{family} — Cumulative Sales vs Budget", color="white", fontsize=9, pad=6)
    plt.tight_layout(pad=1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Upload panel (admin only) ──────────────────────────────────────────────────

def _upload_panel():
    st.markdown("#### Upload Budget File")
    st.caption("Upload your 2026 budget Excel (.xlsm / .xlsx). "
               "This will replace any previously loaded budget data.")

    uploaded = st.file_uploader(
        "Budget Excel file", type=["xlsx", "xlsm"],
        key="budget_upload"
    )
    col1, col2 = st.columns([3, 1])
    replace = col2.checkbox("Replace existing data", value=True, key="bud_replace")

    if col1.button("📥 Load Budget", type="primary", disabled=(uploaded is None)):
        try:
            rows = _parse_budget_excel(uploaded)
            if replace:
                db.clear_budget_2026()
            n = db.upsert_budget_rows(rows)
            st.success(f"Loaded {n} budget rows successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Error parsing file: {e}")


# ── Family overview ────────────────────────────────────────────────────────────

def _family_overview(date_from, date_to):
    """Summary metrics cards + family selector buttons."""
    all_rows = db.get_budget_vs_actual(date_from, date_to)
    if not all_rows:
        st.info("No budget data loaded. Use the Upload tab to load your 2026 budget file.")
        return None

    # Group by family
    family_totals = {}
    for r in all_rows:
        fam = r["family"] or "Other"
        if fam not in family_totals:
            family_totals[fam] = {"period_budget": 0, "actual_sales": 0}
        family_totals[fam]["period_budget"] += r["period_budget"] or 0
        family_totals[fam]["actual_sales"] += r["actual_sales"] or 0

    # Top-line summary
    total_bud = sum(v["period_budget"] for v in family_totals.values())
    total_act = sum(v["actual_sales"] for v in family_totals.values())
    total_var = total_act - total_bud
    total_pct = (total_var / total_bud * 100) if total_bud else None

    period_label = ""
    if date_from and date_to:
        period_label = f"{date_from.strftime('%b %Y')} – {date_to.strftime('%b %Y')}"
    elif date_from:
        period_label = f"From {date_from.strftime('%b %Y')}"
    elif date_to:
        period_label = f"To {date_to.strftime('%b %Y')}"
    else:
        period_label = "Full Year 2026"

    st.markdown(f"**Period: {period_label}**")
    st.markdown("---")
    st.markdown("**Select a Family to drill down:**")

    families = sorted(family_totals.keys())
    cols = st.columns(min(len(families), 4))
    for i, fam in enumerate(families):
        t = family_totals[fam]
        act = t["actual_sales"]
        bud = t["period_budget"]
        pct = ((act - bud) / bud * 100) if bud else None
        c = _family_colour(fam)
        with cols[i % 4]:
            rag = _rag(pct)
            label = f"{fam}\n£{act:,.0f} / £{bud:,.0f}"
            pct_str = _fmt_pct(pct)
            st.markdown(
                f"""<div style="background:{c}22;border:1px solid {c};border-radius:8px;
                    padding:10px 8px;margin-bottom:8px;cursor:pointer">
                    <div style="color:{c};font-weight:bold;font-size:11px">{fam}</div>
                    <div style="font-size:13px;color:white">£{act:,.0f}</div>
                    <div style="font-size:10px;color:#aaa">Budget £{bud:,.0f}</div>
                    <div style="font-size:11px;color:{rag};font-weight:bold">{pct_str}</div>
                </div>""",
                unsafe_allow_html=True
            )
            if st.button(f"View {fam}", key=f"fam_btn_{fam}", use_container_width=True):
                st.session_state["budget_family"] = fam

    return all_rows


# ── Family detail view ─────────────────────────────────────────────────────────

def _family_detail(family, date_from, date_to):
    rows = db.get_budget_vs_actual(date_from, date_to, family=family)
    if not rows:
        st.warning(f"No data for family: {family}")
        return

    # Enrich with monthly actuals for cumulative chart
    monthly_actuals = db.get_budget_monthly_actuals(date_from, date_to, family=family)
    # Build lookup: app_code -> {month_num: actual_sales}
    monthly_map = {}
    for m in monthly_actuals:
        desc = m["app_desc"]
        if desc not in monthly_map:
            monthly_map[desc] = {}
        monthly_map[desc][m["month_num"]] = m["actual_sales"]
    for r in rows:
        for mn in range(1, 13):
            r[f"actual_m{mn:02d}"] = (monthly_map.get(r["app_desc"]) or {}).get(mn, 0)

    # Filter out rows with no budget AND no actual
    rows = [r for r in rows if (r["period_budget"] or 0) + (r["actual_sales"] or 0) > 0]

    if not rows:
        st.info("No data to display for this family in the selected period.")
        return

    colour = _family_colour(family)
    st.markdown(f"<h4 style='color:{colour}'>{family}</h4>", unsafe_allow_html=True)

    if st.button("← Back to Overview", key="bud_back"):
        st.session_state.pop("budget_family", None)
        st.rerun()

    # Summary metrics for this family
    fam_bud = sum(r["period_budget"] or 0 for r in rows)
    fam_act = sum(r["actual_sales"] or 0 for r in rows)
    fam_var = fam_act - fam_bud
    fam_pct = (fam_var / fam_bud * 100) if fam_bud else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Budget £", f"£{fam_bud:,.0f}")
    c2.metric("Actual £", f"£{fam_act:,.0f}")
    c3.metric("Var £",    _fmt_gbp(fam_var))
    c4.metric("Var %",    _fmt_pct(fam_pct))

    st.markdown("---")

    # Detail table
    st.markdown("**Product Line Detail**")
    table_rows = []
    for r in rows:
        bud  = r["period_budget"] or 0
        act  = r["actual_sales"] or 0
        var  = act - bud
        pct  = r["var_pct"]
        rag  = _rag(pct)
        table_rows.append({
            "Code":         r["app_code"],
            "Description":  r["app_desc"] or "",
            "Product Line": r["product_line"] or "",
            "Budget £":     f"£{bud:,.0f}",
            "Actual £":     f"£{act:,.0f}",
            "Var £":        _fmt_gbp(var),
            "Var %":        _fmt_pct(pct),
            "_rag":         rag,
        })

    # Render as styled HTML table
    def _tbl_html(trows):
        html = """<table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr>
        <th style="text-align:left;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Code</th>
        <th style="text-align:left;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Description</th>
        <th style="text-align:left;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Product Line</th>
        <th style="text-align:right;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Budget £</th>
        <th style="text-align:right;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Actual £</th>
        <th style="text-align:right;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Var £</th>
        <th style="text-align:right;padding:4px 6px;border-bottom:1px solid #444;color:#aaa">Var %</th>
        </tr></thead><tbody>"""
        for tr in trows:
            rag = tr["_rag"]
            html += f"""<tr style="border-bottom:1px solid #2a2a2a">
            <td style="padding:4px 6px;color:#ccc">{tr['Code']}</td>
            <td style="padding:4px 6px;color:#ccc">{tr['Description']}</td>
            <td style="padding:4px 6px;color:#aaa;font-size:11px">{tr['Product Line']}</td>
            <td style="text-align:right;padding:4px 6px;color:#ccc">{tr['Budget £']}</td>
            <td style="text-align:right;padding:4px 6px;color:#ccc">{tr['Actual £']}</td>
            <td style="text-align:right;padding:4px 6px;color:#ccc">{tr['Var £']}</td>
            <td style="text-align:right;padding:4px 6px;font-weight:bold;color:{rag}">{tr['Var %']}</td>
            </tr>"""
        html += "</tbody></table>"
        return html

    st.markdown(_tbl_html(table_rows), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        buf = _bar_chart(rows, family, date_from=date_from, date_to=date_to)
        st.image(buf, use_container_width=True)
    with col2:
        current_month = date.today().month if date_from is None or date_from.year == 2026 else None
        buf2 = _cumulative_chart(rows, family, current_month=current_month)
        st.image(buf2, use_container_width=True)


# ── Date filter helper ─────────────────────────────────────────────────────────

def _date_filter():
    """Returns (date_from, date_to) based on quick-pick + optional custom range."""
    st.markdown("**Period filter**")
    col1, col2 = st.columns([2, 2])

    quick = col1.selectbox(
        "Quick pick",
        ["Full Year 2026", "Q1 (Jan-Mar)", "Q2 (Apr-Jun)",
         "Q3 (Jul-Sep)", "Q4 (Oct-Dec)", "YTD", "Custom"],
        key="bud_quick_period"
    )

    today = date.today()

    if quick == "Full Year 2026":
        return date(2026, 1, 1), date(2026, 12, 31)
    elif quick == "Q1 (Jan-Mar)":
        return date(2026, 1, 1), date(2026, 3, 31)
    elif quick == "Q2 (Apr-Jun)":
        return date(2026, 4, 1), date(2026, 6, 30)
    elif quick == "Q3 (Jul-Sep)":
        return date(2026, 7, 1), date(2026, 9, 30)
    elif quick == "Q4 (Oct-Dec)":
        return date(2026, 10, 1), date(2026, 12, 31)
    elif quick == "YTD":
        return date(2026, 1, 1), today
    else:  # Custom
        c1, c2 = st.columns(2)
        df = c1.date_input("From", value=date(2026, 1, 1), key="bud_from")
        dt = c2.date_input("To",   value=today,            key="bud_to")
        return df, dt


# ── Main entry point ───────────────────────────────────────────────────────────

def page_budget():
    st.markdown('<div class="section-header">Budget vs Actual 2026</div>',
                unsafe_allow_html=True)

    role = st.session_state.get("role", "rep")

    # Date filter always shown
    date_from, date_to = _date_filter()
    st.markdown("---")

    # Admin tab for uploading
    if role == "admin":
        tab_overview, tab_upload = st.tabs(["📊 Overview", "📥 Upload Budget"])
        with tab_upload:
            _upload_panel()
        with tab_overview:
            _budget_overview_section(date_from, date_to, role)
    else:
        _budget_overview_section(date_from, date_to, role)


def _budget_overview_section(date_from, date_to, role):
    # Check if drilled into a family
    selected_family = st.session_state.get("budget_family")

    if selected_family:
        _family_detail(selected_family, date_from, date_to)
    else:
        _family_overview(date_from, date_to)
