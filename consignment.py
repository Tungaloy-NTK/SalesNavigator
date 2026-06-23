"""Consignment Stock module — view full sales history for consignment warehouse accounts."""
import streamlit as st
import pandas as pd
from datetime import date, datetime
import database as db


def _fmt_date(d):
    if not d:
        return "—"
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return str(d)[:10]


def _card(label, value, colour="#1a1a2e"):
    st.markdown(f"""
        <div style="background:{colour};border-radius:8px;padding:14px 18px;text-align:center;">
            <div style="color:#fff;font-size:11px;opacity:.8;margin-bottom:4px;">{label}</div>
            <div style="color:#fff;font-size:22px;font-weight:700;">{value}</div>
        </div>""", unsafe_allow_html=True)


def _nav(page, **kwargs):
    st.session_state["page"] = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()


def render_page():
    st.markdown('<div class="section-header">Consignment Stock</div>', unsafe_allow_html=True)
    st.caption("Full sales history for all accounts that hold consignment stock — "
               "including non-consignment sales at those accounts.")

    role    = st.session_state.get("role", "rep")
    user_id = st.session_state.get("user_id")

    # ── Check we have consignment data ──
    warehouses = db.consignment_get_warehouses()
    if not warehouses:
        st.warning("No consignment warehouses configured yet.")
        if role in ("admin", "marketing"):
            st.info("Go to **Admin** to upload consignment warehouse mappings, "
                    "or ask Rob to load the spreadsheet.")
        return

    # ── Summary tab / Detail tab ──
    tab_summary, tab_detail = st.tabs(["📊 Account Summary", "🔍 Sales Detail"])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — Account Summary
    # ══════════════════════════════════════════════════════════════════════
    with tab_summary:
        summary = db.consignment_get_summary()
        if not summary:
            st.info("No sales data found for consignment accounts.")
            return

        yr = date.today().year

        # ── KPI cards ──
        total_accounts = len(summary)
        total_ytd      = sum(r['ytd_sales'] for r in summary)
        total_prev     = sum(r['prev_year_sales'] for r in summary)
        total_gp       = sum(r['ytd_gp'] for r in summary)
        total_items    = sum(r['unique_items'] for r in summary)

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1: _card("Consignment Accounts", f"{total_accounts}")
        with k2: _card(f"YTD {yr} Sales", f"£{total_ytd:,.0f}", "#2c3e50")
        with k3: _card(f"{yr-1} Sales", f"£{total_prev:,.0f}", "#34495e")
        with k4: _card(f"YTD {yr} GP", f"£{total_gp:,.0f}", "#16a085")
        with k5: _card("Unique Items", f"{total_items:,}", "#8e44ad")

        st.markdown("---")

        # ── Filter bar ──
        f1, f2 = st.columns([3, 2])
        search = f1.text_input("🔍 Search", placeholder="Customer name, WHS code…",
                               key="cons_summary_search")
        rep_names = sorted(set(r['rep_name'] for r in summary if r.get('rep_name')))
        rep_filter = f2.selectbox("Rep", ["All Reps"] + rep_names, key="cons_rep_filter")

        filtered = summary
        if search:
            s = search.lower()
            filtered = [r for r in filtered
                        if s in (r['customer_name'] or '').lower()
                        or s in (r.get('whs_codes') or '').lower()
                        or s in (r.get('customer_code') or '').lower()]
        if rep_filter != "All Reps":
            filtered = [r for r in filtered if r.get('rep_name') == rep_filter]

        st.markdown(f"**{len(filtered)} accounts**")

        # ── Account table ──
        if filtered:
            hcols = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
            headers = ["Customer", "WHS", "Rep", f"YTD {yr}", f"{yr-1}",
                       "YTD GP", "Last Order", ""]
            for hc, h in zip(hcols, headers):
                hc.markdown(f"**{h}**")
            st.markdown("<hr style='margin:4px 0'/>", unsafe_allow_html=True)

            for r in filtered:
                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([3, 1, 1, 1, 1, 1, 1, 1])
                c1.write(f"**{r['customer_name']}**")
                c2.caption(r.get('whs_codes') or '—')
                c3.caption(r.get('rep_name') or '—')
                c4.write(f"£{r['ytd_sales']:,.0f}")
                c5.write(f"£{r['prev_year_sales']:,.0f}")
                gp_pct = round(r['ytd_gp'] / r['ytd_sales'] * 100, 1) if r['ytd_sales'] else 0
                c6.write(f"£{r['ytd_gp']:,.0f}" + (f" ({gp_pct}%)" if r['ytd_sales'] else ""))
                c7.caption(_fmt_date(r.get('last_order')))
                if c8.button("Sales", key=f"cons_view_{r['customer_code']}"):
                    st.session_state["cons_detail_customer"] = r['customer_code']
                    st.rerun()

            # ── CSV export ──
            export_df = pd.DataFrame([{
                "Customer Code": r['customer_code'],
                "Customer Name": r['customer_name'],
                "WHS Codes":     r.get('whs_codes') or '',
                "SM Name":       r.get('sm_name') or '',
                "Rep":           r.get('rep_name') or '',
                f"YTD {yr}":     r['ytd_sales'],
                f"{yr-1} Sales": r['prev_year_sales'],
                f"YTD GP":       r['ytd_gp'],
                "Last Order":    r.get('last_order') or '',
                "Total Invoices": r['total_invoices'],
                "Unique Items":  r['unique_items'],
            } for r in filtered])
            st.download_button("📥 Export Summary CSV", data=export_df.to_csv(index=False),
                               file_name="consignment_summary.csv", mime="text/csv",
                               key="dl_cons_summary")

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — Sales Detail
    # ══════════════════════════════════════════════════════════════════════
    with tab_detail:
        # ── Filters ──
        # Build customer options from consignment accounts
        cons_codes = db.consignment_get_customer_codes()
        with db.get_conn() as conn:
            ph = ",".join("?" * len(cons_codes))
            cust_rows = conn.execute(f"""
                SELECT customer_code, customer_name FROM customers
                WHERE customer_code IN ({ph}) ORDER BY customer_name
            """, cons_codes).fetchall() if cons_codes else []
        cust_opts = {"All Accounts": None}
        for cr in cust_rows:
            cust_opts[f"{cr['customer_name']} ({cr['customer_code']})"] = cr['customer_code']

        # Pre-select if coming from summary tab
        pre_sel = st.session_state.pop("cons_detail_customer", None)
        default_idx = 0
        if pre_sel:
            for i, (label, code) in enumerate(cust_opts.items()):
                if code == pre_sel:
                    default_idx = i
                    break

        f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
        cust_sel = f1.selectbox("Account", list(cust_opts.keys()),
                                index=default_idx, key="cons_detail_cust")
        selected_code = cust_opts.get(cust_sel)

        # Date range
        yr = date.today().year
        f2_from = f2.date_input("From", value=date(yr - 1, 1, 1), key="cons_date_from")
        f2_to   = f3.date_input("To", value=date.today(), key="cons_date_to")
        item_search = f4.text_input("Item search", placeholder="Part number or desc…",
                                    key="cons_item_search")

        # ── Fetch data ──
        sales = db.consignment_get_sales(
            customer_code=selected_code,
            date_from=f2_from.strftime("%Y-%m-%d") if f2_from else None,
            date_to=f2_to.strftime("%Y-%m-%d") if f2_to else None,
            item_search=item_search.strip() or None,
        )

        if not sales:
            st.info("No sales found for these filters.")
            return

        # ── Quick stats for this view ──
        total_val = sum(float(s.get('sales_val') or 0) for s in sales)
        total_gp  = sum(float(s.get('gp_val') or 0) for s in sales)
        total_qty = sum(float(s.get('qty') or 0) for s in sales)
        gp_pct    = round(total_gp / total_val * 100, 1) if total_val else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: _card("Lines", f"{len(sales):,}", "#1a1a2e")
        with m2: _card("Sales Value", f"£{total_val:,.0f}", "#2c3e50")
        with m3: _card("GP Value", f"£{total_gp:,.0f}", "#16a085")
        with m4: _card("GP %", f"{gp_pct}%",
                       "#27ae60" if gp_pct >= 30 else "#e67e22" if gp_pct >= 20 else "#e74c3c")
        with m5: _card("Total Qty", f"{total_qty:,.0f}", "#8e44ad")

        st.markdown("---")

        # ── Monthly breakdown chart ──
        df = pd.DataFrame([dict(s) for s in sales])
        df['sales_val'] = pd.to_numeric(df['sales_val'], errors='coerce').fillna(0)
        df['gp_val']    = pd.to_numeric(df['gp_val'], errors='coerce').fillna(0)
        df['qty']       = pd.to_numeric(df['qty'], errors='coerce').fillna(0)

        if 'year' in df.columns and 'month' in df.columns:
            monthly = df.groupby(['year', 'month']).agg(
                sales=('sales_val', 'sum'), gp=('gp_val', 'sum'), qty=('qty', 'sum')
            ).reset_index()
            monthly['period'] = monthly.apply(
                lambda r: f"{int(r['year'])}-{str(int(r['month'])).zfill(2)}", axis=1)
            monthly = monthly.sort_values('period')

            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Bar(x=monthly['period'], y=monthly['sales'],
                                 name='Sales £', marker_color='#1a1a2e'))
            fig.add_trace(go.Bar(x=monthly['period'], y=monthly['gp'],
                                 name='GP £', marker_color='#16a085'))
            fig.update_layout(
                title="Monthly Sales & GP",
                barmode='group', height=320,
                plot_bgcolor="white",
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Top items for this view ──
        with st.expander("📦 Top Items", expanded=False):
            items_df = df.groupby(['item_code', 'item_desc']).agg(
                total_sales=('sales_val', 'sum'),
                total_gp=('gp_val', 'sum'),
                total_qty=('qty', 'sum'),
                orders=('invoice_no', 'nunique'),
                last_order=('sale_date', 'max'),
            ).reset_index().sort_values('total_sales', ascending=False).head(30)

            st.dataframe(
                items_df.rename(columns={
                    'item_code': 'Item Code', 'item_desc': 'Description',
                    'total_sales': 'Sales £', 'total_gp': 'GP £',
                    'total_qty': 'Qty', 'orders': 'Orders', 'last_order': 'Last Order',
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Sales £": st.column_config.NumberColumn("Sales £", format="£%.0f"),
                    "GP £":    st.column_config.NumberColumn("GP £", format="£%.0f"),
                    "Qty":     st.column_config.NumberColumn("Qty", format="%,.0f"),
                }
            )

        # ── Full sales table ──
        st.markdown(f"#### Sales Lines ({len(sales):,})")
        display_df = df[['sale_date', 'customer_name', 'item_code', 'item_desc',
                         'qty', 'sales_val', 'gp_val', 'invoice_no']].copy()
        display_df.columns = ['Date', 'Customer', 'Item Code', 'Description',
                              'Qty', 'Sales £', 'GP £', 'Invoice']

        st.dataframe(
            display_df,
            use_container_width=True, hide_index=True, height=500,
            column_config={
                "Sales £": st.column_config.NumberColumn("Sales £", format="£%.2f"),
                "GP £":    st.column_config.NumberColumn("GP £",    format="£%.2f"),
                "Qty":     st.column_config.NumberColumn("Qty",     format="%,.1f"),
            }
        )

        # ── CSV export ──
        export_df = pd.DataFrame([{
            "Date":          s.get('sale_date') or '',
            "Customer Code": s['customer_code'],
            "Customer Name": s.get('customer_name') or '',
            "SM Name":       s.get('sm_name') or '',
            "Item Code":     s.get('item_code') or '',
            "Description":   s.get('item_desc') or '',
            "Qty":           s.get('qty') or 0,
            "Unit Price":    s.get('unit_price') or 0,
            "Sales Value":   s.get('sales_val') or 0,
            "Cost Value":    s.get('cost_val') or 0,
            "GP Value":      s.get('gp_val') or 0,
            "Invoice":       s.get('invoice_no') or '',
            "Ship To":       s.get('ship_to_address') or '',
        } for s in sales])
        st.download_button("📥 Export Sales CSV", data=export_df.to_csv(index=False),
                           file_name="consignment_sales.csv", mime="text/csv",
                           key="dl_cons_sales")
