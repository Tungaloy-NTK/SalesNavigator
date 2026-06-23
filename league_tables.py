import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import database as db
from datetime import date

def medal(pos):
    if pos == 1: return "🥇"
    if pos == 2: return "🥈"
    if pos == 3: return "🥉"
    return f"#{pos}"

def render_league(title, data, cols, value_col, fmt="£", search=""):
    st.markdown(f"### {title}")
    if not data:
        st.info("No data available yet. Upload a GP report to populate league tables.")
        return
    df = pd.DataFrame([dict(r) for r in data])
    if df.empty:
        st.info("No data available for the selected date range.")
        return
    # Apply search filter across all text columns
    if search:
        mask = df.apply(lambda row: any(search.lower() in str(v).lower() for v in row), axis=1)
        df = df[mask]
        if df.empty:
            st.info(f"No results matching '{search}'.")
            return
    df = df.reset_index(drop=True)
    df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
    display_cols = ["Rank"] + cols
    col_config = {}
    if fmt == "£":
        col_config[value_col] = st.column_config.NumberColumn(value_col, format="£%.0f")
    elif fmt == "#":
        col_config[value_col] = st.column_config.NumberColumn(value_col, format="%,.0f")
    st.dataframe(df[display_cols].head(20), use_container_width=True,
                 hide_index=True, column_config=col_config)

def render_bar_chart(title, data, name_col, value_col, colour="#1a1a2e"):
    if not data:
        return
    df = pd.DataFrame([dict(r) for r in data]).head(10)
    if df.empty:
        return
    fig = go.Figure(go.Bar(
        x=df[value_col], y=df[name_col],
        orientation='h', marker_color=colour
    ))
    fig.update_layout(
        title=title, height=300,
        plot_bgcolor="white",
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)

def _date_filter_bar():
    db_min, db_max = db.get_league_date_range()
    today = date.today()
    if "lt_date_from" not in st.session_state:
        st.session_state["lt_date_from"] = date.fromisoformat(db_min[:10]) if db_min else date(2025,1,1)
    if "lt_date_to" not in st.session_state:
        st.session_state["lt_date_to"] = today
    dcol1, dcol2 = st.columns(2)
    date_from = dcol1.date_input("From", value=st.session_state["lt_date_from"], key="lt_date_from_input")
    date_to   = dcol2.date_input("To",   value=st.session_state["lt_date_to"],   key="lt_date_to_input")
    st.session_state["lt_date_from"] = date_from
    st.session_state["lt_date_to"]   = date_to
    st.caption(f"Showing data from **{date_from.strftime('%d %b %Y')}** to **{date_to.strftime('%d %b %Y')}**")
    st.divider()
    return date_from, date_to

def _items_table(data, sort_col, search=""):
    df = pd.DataFrame([dict(r) for r in data]) if data else pd.DataFrame()
    if df.empty:
        st.info("No item data available for the selected date range.")
        return
    if search:
        mask = df.apply(lambda row: any(search.lower() in str(v).lower() for v in row), axis=1)
        df = df[mask]
        if df.empty:
            st.info(f"No items matching '{search}'.")
            return
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce")
    df["total_qty"]   = pd.to_numeric(df["total_qty"],   errors="coerce")
    df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
    cols = ["Rank","item_code","item_desc","total_qty","total_sales"]
    rename = {"item_code":"Item","item_desc":"Description","total_qty":"Qty","total_sales":"Sales £"}
    st.dataframe(df[cols].head(30).rename(columns=rename),
                 use_container_width=True, hide_index=True,
                 column_config={
                     "Sales £": st.column_config.NumberColumn("Sales £", format="£%.0f"),
                     "Qty":     st.column_config.NumberColumn("Qty",     format="%,.0f"),
                 })

def _app_table(data, sort_col, title, search=""):
    df = pd.DataFrame([dict(r) for r in data]) if data else pd.DataFrame()
    if df.empty:
        st.info("No application data available for the selected date range.")
        return
    if search:
        mask = df.apply(lambda row: any(search.lower() in str(v).lower() for v in row), axis=1)
        df = df[mask]
        if df.empty:
            st.info(f"No applications matching '{search}'.")
            return
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce")
    df["total_qty"]   = pd.to_numeric(df["total_qty"],   errors="coerce")
    df = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
    cols = ["Rank","app_dsc","total_qty","total_sales"]
    rename = {"app_dsc":"Application","total_qty":"Qty","total_sales":"Sales £"}
    st.markdown(f"### {title}")
    st.dataframe(df[cols].head(30).rename(columns=rename),
                 use_container_width=True, hide_index=True,
                 column_config={
                     "Sales £": st.column_config.NumberColumn("Sales £", format="£%.0f"),
                     "Qty":     st.column_config.NumberColumn("Qty",     format="%,.0f"),
                 })

def page_league_tables():
    st.markdown('<div class="section-header">League Tables</div>', unsafe_allow_html=True)
    date_from, date_to = _date_filter_bar()

    # Role-based GP masking — reps can't see other reps' GP figures
    _role = st.session_state.get("role", "rep")
    _can_see_gp = _role in ("admin", "regional_manager", "marketing")

    # Fetch SM Names once (used by tabs 6 and 7)
    _all_sm_names = db.get_all_sm_names()

    # Search bar — filters dataframes across all tabs
    league_search = st.text_input(
        "🔍 Search league tables",
        placeholder="Search by SM Name, customer, item, application…",
        key="league_search",
        help="Type to filter results across all league table tabs"
    )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏆 SM Names by Sales",
        "💰 SM Names by GP",
        "📈 Sales Growth",
        "📋 Reps by Visits",
        "🏭 Customers & Items",
        "📊 Applications",
        "🎯 Free Holders",
    ])

    # ── Tab 1: Reps by Sales ──
    with tab1:
        data = db.get_league_reps_by_sales(date_from, date_to)
        col1, col2 = st.columns([1, 1])
        with col1:
            render_league("Top SM Names by Total Sales", data,
                          ["sm_name", "total_sales"], "total_sales", "£", search=league_search)
        with col2:
            render_bar_chart("Sales by SM Name", data, "sm_name", "total_sales", "#1a1a2e")
        if data:
            _df = pd.DataFrame([dict(r) for r in data])[["sm_name","total_sales"]].rename(
                columns={"sm_name":"SM Name","total_sales":"Total Sales"})
            st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                               file_name="league_reps_by_sales.csv", mime="text/csv", key="dl_tab1")

    # ── Tab 2: Reps by GP (restricted for reps) ──
    with tab2:
        if not _can_see_gp:
            st.info("🔒 GP data is restricted to managers and admin users. "
                    "You can see your own customer GP on individual customer detail pages.")
        else:
            gp_subtab1, gp_subtab2 = st.tabs(["£ Gross Profit", "% GP Margin"])

            with gp_subtab1:
                data = db.get_league_reps_by_gp(date_from, date_to)
                col1, col2 = st.columns([1, 1])
                with col1:
                    render_league("Top SM Names by Gross Profit", data,
                                  ["sm_name", "total_gp"], "total_gp", "£", search=league_search)
                with col2:
                    render_bar_chart("GP £ by SM Name", data, "sm_name", "total_gp", "#c0392b")
                if data:
                    _df = pd.DataFrame([dict(r) for r in data])[["sm_name","total_gp"]].rename(
                        columns={"sm_name":"SM Name","total_gp":"Gross Profit"})
                    st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                       file_name="league_reps_by_gp.csv", mime="text/csv", key="dl_tab2a")

            with gp_subtab2:
                data = db.get_league_reps_by_gp_pct(date_from, date_to)
                if data:
                    df = pd.DataFrame([dict(r) for r in data])
                    if league_search:
                        mask = df.apply(lambda row: any(league_search.lower() in str(v).lower() for v in row), axis=1)
                        df = df[mask]
                    if df.empty:
                        st.info(f"No results matching '{league_search}'." if league_search else "No data available.")
                    else:
                        df = df.reset_index(drop=True)
                        df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
                        df["gp_pct"]    = pd.to_numeric(df["gp_pct"],    errors="coerce")
                        df["total_gp"]  = pd.to_numeric(df["total_gp"],  errors="coerce")
                        df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce")
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.markdown("### Top SM Names by GP Margin %")
                            st.dataframe(
                                df[["Rank","sm_name","gp_pct","total_gp","total_sales"]].rename(
                                    columns={"sm_name":"SM Name","gp_pct":"GP %",
                                             "total_gp":"GP £","total_sales":"Sales £"}
                                ).head(20),
                                use_container_width=True, hide_index=True,
                                column_config={
                                    "GP %":   st.column_config.NumberColumn("GP %",   format="%.1f%%"),
                                    "GP £":   st.column_config.NumberColumn("GP £",   format="£%.0f"),
                                    "Sales £":st.column_config.NumberColumn("Sales £",format="£%.0f"),
                                }
                            )
                        with col2:
                            fig = go.Figure(go.Bar(
                                x=df["gp_pct"].head(15),
                                y=df["sm_name"].head(15),
                                orientation='h', marker_color="#8e44ad",
                                text=[f"{v:.1f}%" for v in df["gp_pct"].head(15)],
                                textposition="outside",
                            ))
                            fig.update_layout(
                                title="GP Margin % by SM Name", height=300,
                                plot_bgcolor="white",
                                margin=dict(l=0, r=40, t=40, b=0),
                                xaxis=dict(ticksuffix="%"),
                                yaxis=dict(autorange="reversed"),
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        _df = df[["sm_name","gp_pct","total_gp","total_sales"]].rename(
                            columns={"sm_name":"SM Name","gp_pct":"GP %","total_gp":"GP £","total_sales":"Sales £"})
                        st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                           file_name="league_reps_by_gp_margin.csv", mime="text/csv", key="dl_tab2b")
                else:
                    st.info("No data available yet.")

    # ── Tab 3: Sales Growth ──
    with tab3:
        st.markdown("#### Select the current period to compare vs same period last year")
        today = date.today()
        # Default: 1 Jan of current year → today
        default_g_from = date(today.year, 1, 1)
        default_g_to   = today
        if "lt_growth_from" not in st.session_state:
            st.session_state["lt_growth_from"] = default_g_from
        if "lt_growth_to" not in st.session_state:
            st.session_state["lt_growth_to"] = default_g_to

        gc1, gc2 = st.columns(2)
        g_from = gc1.date_input("Current period from", value=st.session_state["lt_growth_from"], key="lt_growth_from_input")
        g_to   = gc2.date_input("Current period to",   value=st.session_state["lt_growth_to"],   key="lt_growth_to_input")
        st.session_state["lt_growth_from"] = g_from
        st.session_state["lt_growth_to"]   = g_to

        prior_from = g_from.replace(year=g_from.year - 1)
        prior_to   = g_to.replace(year=g_to.year - 1)
        st.caption(f"Comparing **{g_from.strftime('%d %b %Y')} – {g_to.strftime('%d %b %Y')}** "
                   f"vs **{prior_from.strftime('%d %b %Y')} – {prior_to.strftime('%d %b %Y')}**")

        data = db.get_league_reps_by_sales_growth(g_from, g_to)
        if not data:
            st.info("No data available for the selected period.")
        else:
            df = pd.DataFrame([dict(r) for r in data])
            if league_search:
                mask = df.apply(lambda row: any(league_search.lower() in str(v).lower() for v in row), axis=1)
                df = df[mask]
            if df.empty:
                st.info(f"No results matching '{league_search}'." if league_search else "No data available.")
            else:
                for col in ["current_sales","prior_sales","growth_val","growth_pct"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                df_ranked   = df[df["growth_pct"].notna()].sort_values("growth_pct", ascending=False).reset_index(drop=True)
                df_no_prior = df[df["growth_pct"].isna()].copy()
                df_ranked.insert(0, "Rank", [medal(i+1) for i in range(len(df_ranked))])
                df_no_prior.insert(0, "Rank", ["—"] * len(df_no_prior))
                df_display = pd.concat([df_ranked, df_no_prior], ignore_index=True)

                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown("### Sales Growth by SM Name")
                    st.dataframe(
                        df_display[["Rank","sm_name","current_sales","prior_sales","growth_val","growth_pct"]].rename(
                            columns={"sm_name":"SM Name","current_sales":"Current £",
                                     "prior_sales":"Prior £","growth_val":"Growth £","growth_pct":"Growth %"}
                        ),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "Current £": st.column_config.NumberColumn("Current £", format="£%.0f"),
                            "Prior £":   st.column_config.NumberColumn("Prior £",   format="£%.0f"),
                            "Growth £":  st.column_config.NumberColumn("Growth £",  format="£%.0f"),
                            "Growth %":  st.column_config.NumberColumn("Growth %",  format="%.1f%%"),
                        }
                    )
                with col2:
                    df_chart = df_ranked.copy()
                    colours = ["#27ae60" if x >= 0 else "#c0392b" for x in df_chart["growth_pct"]]
                    fig = go.Figure(go.Bar(
                        x=df_chart["growth_pct"].head(15),
                        y=df_chart["sm_name"].head(15),
                        orientation="h", marker_color=colours[:15],
                        text=[f"{v:+.1f}%" for v in df_chart["growth_pct"].head(15)],
                        textposition="outside",
                    ))
                    fig.update_layout(
                        title="Growth % vs Same Period Last Year",
                        height=320, plot_bgcolor="white",
                        margin=dict(l=0, r=50, t=40, b=0),
                        xaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor="#999"),
                        yaxis=dict(autorange="reversed"),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                _df = df_display[["sm_name","current_sales","prior_sales","growth_val","growth_pct"]].rename(
                    columns={"sm_name":"SM Name","current_sales":"Current £","prior_sales":"Prior £",
                             "growth_val":"Growth £","growth_pct":"Growth %"})
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_sales_growth.csv", mime="text/csv", key="dl_tab3")

    # ── Tab 4: Reps by Visits ──
    with tab4:
        data = db.get_league_reps_by_visits(date_from, date_to)
        col1, col2 = st.columns([1, 1])
        with col1:
            render_league("Most Visits Logged", data,
                          ["full_name", "visit_count"], "visit_count", "#", search=league_search)
        with col2:
            render_bar_chart("Visits by Rep", data, "full_name", "visit_count", "#27ae60")
        if data:
            _df = pd.DataFrame([dict(r) for r in data])[["full_name","visit_count"]].rename(
                columns={"full_name":"Rep","visit_count":"Visit Count"})
            st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                               file_name="league_reps_by_visits.csv", mime="text/csv", key="dl_tab4")

    # ── Tab 5: Customers & Items ──
    with tab5:
        st.markdown("---")
        subtab1, subtab2, subtab3 = st.tabs(["Top Customers", "Top Items by Qty", "Top Items by Sales"])

        with subtab1:
            data = db.get_league_customers_by_spend(date_from, date_to)
            if data:
                df = pd.DataFrame([dict(r) for r in data])
                if league_search:
                    mask = df.apply(lambda row: any(league_search.lower() in str(v).lower() for v in row), axis=1)
                    df = df[mask]
                if df.empty:
                    st.info(f"No customers matching '{league_search}'.")
                else:
                    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce")
                    df = df.reset_index(drop=True)
                    df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
                    st.markdown("### Top Customers by Spend")
                    st.dataframe(
                        df[["Rank","customer_code","total_sales"]].head(50).rename(
                            columns={"customer_code":"Customer","total_sales":"Sales £"}),
                        use_container_width=True, hide_index=True,
                        column_config={"Sales £": st.column_config.NumberColumn("Sales £", format="£%.0f")}
                    )
                    _df = df[["customer_code","total_sales"]].rename(
                        columns={"customer_code":"Customer","total_sales":"Sales £"})
                    st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                       file_name="league_top_customers.csv", mime="text/csv", key="dl_tab5a")

        with subtab2:
            st.markdown("### Top Items by Quantity")
            _items_data = db.get_league_items_by_qty(date_from, date_to)
            _items_table(_items_data, "total_qty", search=league_search)
            if _items_data:
                _df = pd.DataFrame([dict(r) for r in _items_data])[["item_code","item_desc","total_qty","total_sales"]].rename(
                    columns={"item_code":"Item","item_desc":"Description","total_qty":"Qty","total_sales":"Sales £"})
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_items_by_qty.csv", mime="text/csv", key="dl_tab5b")

        with subtab3:
            st.markdown("### Top Items by Sales Value")
            _items_data = db.get_league_items_by_sales(date_from, date_to)
            _items_table(_items_data, "total_sales", search=league_search)
            if _items_data:
                _df = pd.DataFrame([dict(r) for r in _items_data])[["item_code","item_desc","total_qty","total_sales"]].rename(
                    columns={"item_code":"Item","item_desc":"Description","total_qty":"Qty","total_sales":"Sales £"})
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_items_by_sales.csv", mime="text/csv", key="dl_tab5c")

    # ── Tab 6: Applications ──
    with tab6:
        # SM Name filter (uses pre-fetched _all_sm_names)
        sm_options = ["All SM Names"] + sorted(_all_sm_names)
        sel_sm = st.selectbox("Filter by SM Name", sm_options, key="app_sm_filter")
        filter_sm = None if sel_sm == "All SM Names" else sel_sm

        subtab1, subtab2 = st.tabs(["By Quantity", "By Sales Value"])
        with subtab1:
            _app_data = db.get_league_app_dsc_by_qty(date_from, date_to, filter_sm)
            _app_table(_app_data, "total_qty", "Top Applications by Quantity", search=league_search)
            if _app_data:
                _df = pd.DataFrame([dict(r) for r in _app_data])[["app_dsc","total_qty","total_sales"]].rename(
                    columns={"app_dsc":"Application","total_qty":"Qty","total_sales":"Sales £"})
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_applications.csv", mime="text/csv", key="dl_tab6a")
        with subtab2:
            _app_data = db.get_league_app_dsc_by_sales(date_from, date_to, filter_sm)
            _app_table(_app_data, "total_sales", "Top Applications by Sales Value", search=league_search)
            if _app_data:
                _df = pd.DataFrame([dict(r) for r in _app_data])[["app_dsc","total_qty","total_sales"]].rename(
                    columns={"app_dsc":"Application","total_qty":"Qty","total_sales":"Sales £"})
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_applications_by_sales.csv", mime="text/csv", key="dl_tab6b")

    # ── Tab 7: Free Holders Leaderboard ──
    with tab7:
        st.markdown("#### Holders shipped at zero unit price — ranked by total qty")
        st.caption("Filters: Item Type = Holder  |  Unit price = £0  |  Qty ≥ 1")

        # SM Name filter (uses pre-fetched _all_sm_names)
        sm_options_fh = ["All SM Names"] + sorted(_all_sm_names)
        sel_sm_fh = st.selectbox("Filter by SM Name", sm_options_fh, key="zh_sm_filter")
        filter_sm_fh = None if sel_sm_fh == "All SM Names" else sel_sm_fh

        # Resolve to user_id for the existing DB function
        filter_user_id = None
        data = db.get_league_zero_price_holders_by_customer(date_from, date_to, filter_sm_fh)
        if not data:
            st.info("No zero-price holder lines found for this period.")
        else:
            df = pd.DataFrame([dict(r) for r in data])
            if league_search:
                mask = df.apply(lambda row: any(league_search.lower() in str(v).lower() for v in row), axis=1)
                df = df[mask]
            if df.empty:
                st.info(f"No holders matching '{league_search}'." if league_search else "No data.")
            else:
                df["total_qty"]  = pd.to_numeric(df["total_qty"],  errors="coerce")
                df["line_count"] = pd.to_numeric(df["line_count"], errors="coerce")
                df = df.sort_values("total_qty", ascending=False).reset_index(drop=True)
                df.insert(0, "Rank", [medal(i+1) for i in range(len(df))])
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.markdown("### Leaderboard")
                    show_cols = ["Rank", "customer_name", "total_qty"]
                    rename_map = {"customer_name": "Customer", "total_qty": "Total Qty"}
                    if not filter_sm_fh:
                        show_cols = ["Rank", "customer_name", "rep_name", "total_qty"]
                        rename_map["rep_name"] = "SM Name"
                    st.dataframe(
                        df[show_cols].rename(columns=rename_map),
                        use_container_width=True, hide_index=True,
                        column_config={
                            "Total Qty": st.column_config.NumberColumn("Total Qty", format="%,.0f"),
                        }
                    )
                with col2:
                    render_bar_chart("Qty of Zero-Price Holders by Customer", data, "customer_name", "total_qty", "#e67e22")
                _exp_cols = ["customer_name","total_qty"]
                _rename = {"customer_name":"Customer","total_qty":"Total Qty"}
                if not filter_sm_fh and "rep_name" in df.columns:
                    _exp_cols = ["customer_name","rep_name","total_qty"]
                    _rename["rep_name"] = "SM Name"
                _df = df[_exp_cols].rename(columns=_rename)
                st.download_button("📥 Export to CSV", data=_df.to_csv(index=False),
                                   file_name="league_free_holders.csv", mime="text/csv", key="dl_tab7")

def render_page():
    page_league_tables()
