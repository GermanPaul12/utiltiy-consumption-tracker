# ui_dashboard.py
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px

def render_page(processed_logs, stats, rates, plotly_template):
    st.title("Utility Consumption Dashboard")
    
    if processed_logs.empty:
        st.info("Your database history is currently empty. Go to 'Log Consumption' to record your initial readings.")
        return

    # =========================================================
    # GLOBAL STRICT COLOR PALETTE CONFIGURATION
    # =========================================================
    color_map = {
        "Electricity (kWh)": "#eab308",              # Yellow
        "Hot Water (MWh)": "#ef4444",                # Red
        "Cold Water (m³)": "#3b82f6",                # Blue
        "Actual cost to Date": "#ef4444",            # Red
        "Prepayments to Date": "#22c55e",            # Green
        "Actual Incurred Cost": "#ef4444",           # Red
        "Prepayments Paid to Date": "#22c55e",       # Green
        "Variable (Usage)": "#eab308",               # Yellow
        "Fixed (Base Standing Charge)": "#ef4444"     # Red
    }

    # Basic Calculations
    total_cost_all = sum(m.get("total_cost", 0.0) for m in stats.values())
    avg_monthly_cost_all = sum(m.get("avg_monthly_cost", 0.0) for m in stats.values())
    avg_daily_cost_all = sum(m.get("avg_daily_cost", 0.0) for m in stats.values())
    projected_annual_cost = avg_daily_cost_all * 365.25
    total_co2_all = sum(m.get("total_co2", 0.0) for m in stats.values())
    
    total_prepayments_to_date = sum(m.get("prepayment_paid_to_date", 0.0) for m in stats.values())
    global_standing_to_date = total_prepayments_to_date - total_cost_all
    
    total_annual_prepayments = sum(m.get("annual_prepayment", 0.0) for m in stats.values())
    global_projected_annual_standing = total_annual_prepayments - projected_annual_cost
    
    total_days_tracked = max(sum(m.get("total_days", 0) for m in stats.values()), 1)
    
    st.caption("ℹ️ Note: Baseline calculations require at least two sequential readings per meter.")
    
    # =========================================================
    # 1. GLOBAL ESTIMATES & PROJECTIONS
    # =========================================================
    st.subheader("Global Estimates & Projections")
    g_col1, g_col2, g_col3, g_col4 = st.columns(4)
    g_col1.metric("Total Cumulative Expenses", f"€{total_cost_all:,.2f}")
    g_col2.metric("Average Monthly Cost", f"€{avg_monthly_cost_all:,.2f}")
    g_col3.metric("Projected Annual Cost", f"€{projected_annual_cost:,.2f}")
    g_col4.metric("Total CO₂ Footprint", f"{total_co2_all:,.1f} kg")
    
    # =========================================================
    # 2. HOUSEHOLD EFFICIENCY METRICS
    # =========================================================
    st.markdown("### 🏠 Household Efficiency Metrics")
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    
    cost_per_occupant = total_cost_all / max(rates['household_size'], 1)
    cost_per_m2 = total_cost_all / max(rates['apartment_size'], 1.0)
    co2_per_day = total_co2_all / max(total_days_tracked, 1)
    
    e_col1.metric("Cost per Occupant", f"€{cost_per_occupant:,.2f}", help="Total accumulated expenses divided by household size.")
    e_col2.metric("Cost per Square Meter", f"€{cost_per_m2:,.2f}/m²", help="Total accumulated expenses divided by apartment size.")
    e_col3.metric("Daily Avg CO₂ Emissions", f"{co2_per_day:.2f} kg/day", help="Average carbon footprint generated per day across all utilities.")
    e_col4.metric("Active Tracked Period", f"{total_days_tracked} Days", help="Total aggregate calendar days currently tracked in the database.")

    st.markdown("---")
    
    # =========================================================
    # 3. FINANCIAL BALANCE & SETTLEMENTS
    # =========================================================
    st.subheader("Financial Balance & Prepayment Settlements")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        st.markdown("### 📅 Current Standing (To Date)")
        st.write("Calculated by comparing pro-rated prepayments paid so far against incurred costs:")
        if global_standing_to_date >= 0:
            st.success(f"**Current Refund Estimate:** €{global_standing_to_date:,.2f} (You have overpaid so far)")
        else:
            st.warning(f"**Current Underpayment Estimate:** €{abs(global_standing_to_date):,.2f} (You owe more than you paid so far)")
        st.write(f"*Total Prepayments Paid to Date:* €{total_prepayments_to_date:,.2f}")
        st.write(f"*Total Incurred Cost to Date:* €{total_cost_all:,.2f}")
        
    with f_col2:
        st.markdown("### 🔮 Annual Projection Settlement")
        st.write("Projects your current consumption habits to a full 12-month billing cycle:")
        if global_projected_annual_standing >= 0:
            st.success(f"**Projected Annual Refund (Guthaben):** €{global_projected_annual_standing:,.2f}")
        else:
            st.error(f"**Projected Annual Backpayment (Nachzahlung):** €{abs(global_projected_annual_standing):,.2f}")
        st.write(f"*Total Annual Prepayments:* €{total_annual_prepayments:,.2f}")
        st.write(f"*Projected Annual Costs:* €{projected_annual_cost:,.2f}")
        
    st.markdown("---")

    # =========================================================
    # 4. MULTI-PERSPECTIVE COST ANALYSIS
    # =========================================================
    st.subheader("💵 Multi-Perspective Financial Deep Dive")
    
    summary_list = []
    for m_name, m_data in stats.items():
        summary_list.append({
            "Utility": m_name,
            "Total Cost (€)": m_data.get("total_cost", 0.0),
            "CO₂ Emissions (kg)": m_data.get("total_co2", 0.0),
            "Average Monthly Cost (€/mo)": m_data.get("avg_monthly_cost", 0.0),
            "Actual cost to Date": m_data.get("total_cost", 0.0),
            "Prepayments to Date": m_data.get("prepayment_paid_to_date", 0.0)
        })
    df_summary = pd.DataFrame(summary_list)

    # 4A. PREPAYMENT SETTLEMENT LEDGER TREND (Line Color Mapped)
    running_dfs = []
    for m_name, m_data in stats.items():
        meter_df = processed_logs[processed_logs['meter'] == m_name].copy()
        if meter_df.empty:
            continue
        
        first_date = meter_df['date'].iloc[0]
        meter_df['days_from_start'] = meter_df['date'].apply(lambda d: (d - first_date).days)
        monthly_prepayment = m_data.get("monthly_prepayment", 0.0)
        
        meter_df['pro_rated_prepayment'] = (meter_df['days_from_start'] / 30.44) * monthly_prepayment
        meter_df['running_standing'] = meter_df['pro_rated_prepayment'] - meter_df['cumulative_cost']
        running_dfs.append(meter_df)
        
    if running_dfs:
        df_running = pd.concat(running_dfs).sort_values(by="date")
        
        fig_running_ledger = px.line(
            df_running,
            x="date",
            y="running_standing",
            color="meter",
            markers=True,
            title="Running Financial Settlement Balance Over Time (Surplus vs. Deficit)",
            labels={"running_standing": "Balance (€) (Above 0 = Refund, Below 0 = Underpayment)", "date": "Date"},
            template=plotly_template,
            color_discrete_map=color_map  # Enforced
        )
        fig_running_ledger.add_hline(y=0.0, line_dash="dash", line_color="#94a3b8", annotation_text="Break-even (€0)")
        st.plotly_chart(fig_running_ledger, use_container_width=True)

    col_deep_left, col_deep_right = st.columns(2)
    
    with col_deep_left:
        # 4B. COMPARE MONTHLY BASELINES (Bar Color Mapped)
        fig_monthly_bars = px.bar(
            df_summary,
            x="Utility",
            y="Average Monthly Cost (€/mo)",
            color="Utility",
            title="Baseline Monthly Expense Comparison (Standardized)",
            labels={"Average Monthly Cost (€/mo)": "Monthly Average (€)"},
            template=plotly_template,
            color_discrete_map=color_map  # Enforced
        )
        st.plotly_chart(fig_monthly_bars, use_container_width=True)
        
    with col_deep_right:
        # 4C. FIXED VS. VARIABLE CHARGES BREAKDOWN (For Electricity) (Pie Color Mapped)
        elec_stats = stats.get("Electricity (kWh)")
        if elec_stats and elec_stats.get("entries_count", 0) > 1:
            elec_variable = elec_stats["total_consumption"] * rates["electricity_kwh"]
            elec_fixed = elec_stats["total_cost"] - elec_variable
            
            df_elec_breakdown = pd.DataFrame([
                {"Charge Type": "Variable (Usage)", "Amount (€)": elec_variable},
                {"Charge Type": "Fixed (Base Standing Charge)", "Amount (€)": elec_fixed}
            ])
            
            fig_elec_breakdown = px.pie(
                df_elec_breakdown,
                values="Amount (€)",
                names="Charge Type",
                title="Electricity Cost Breakdown: Usage vs. Base Price",
                template=plotly_template,
                color="Charge Type",
                color_discrete_map=color_map,  # Enforced
                hole=0.4
            )
            st.plotly_chart(fig_elec_breakdown, use_container_width=True)
        else:
            st.info("Log more electricity readings to view the Fixed vs. Variable cost split.")

    st.markdown("---")

    # =========================================================
    # 5. GENERAL CONSUMPTION & COST SHARE
    # =========================================================
    st.subheader("📊 Aggregate Utility Share")
    
    col_chart_left, col_chart_right = st.columns(2)
    
    with col_chart_left:
        # Pie Chart Cost Share (Pie Color Mapped)
        fig_cost_pie = px.pie(
            df_summary, 
            values="Total Cost (€)", 
            names="Utility", 
            title="Expense Distribution Share (%)",
            template=plotly_template,
            color="Utility",
            color_discrete_map=color_map,  # Enforced
            hole=0.4
        )
        st.plotly_chart(fig_cost_pie, use_container_width=True)

    with col_chart_right:
        # Pie Chart CO2 Share (Pie Color Mapped)
        fig_co2_pie = px.pie(
            df_summary, 
            values="CO₂ Emissions (kg)", 
            names="Utility", 
            title="CO₂ Emissions Share (%)",
            template=plotly_template,
            color="Utility",
            color_discrete_map=color_map,  # Enforced
            hole=0.4
        )
        st.plotly_chart(fig_co2_pie, use_container_width=True)

    # Actual vs Prepayment Bar Chart (Grouped Bar Color Mapped)
    st.markdown("#### Utility Settlement Check: Actual Expenses vs Prepayments Paid")
    df_melted = df_summary.melt(
        id_vars=["Utility"], 
        value_vars=["Actual cost to Date", "Prepayments to Date"], 
        var_name="Type", 
        value_name="Amount (€)"
    )
    
    fig_compare_bar = px.bar(
        df_melted, 
        x="Utility", 
        y="Amount (€)", 
        color="Type", 
        barmode="group",
        title="Incurred Cost vs Pro-Rated Prepayments (To Date)",
        labels={"Amount (€)": "Expenses (€)"},
        template=plotly_template,
        color_discrete_map=color_map  # Enforced: Red (Costs) vs. Green (Prepayments)
    )
    st.plotly_chart(fig_compare_bar, use_container_width=True)

    st.markdown("---")

    # =========================================================
    # 6. PERSONALIZED BENCHMARKS
    # =========================================================
    st.subheader("Personalized German Benchmark Comparison")
    st.write(f"Evaluating benchmarks using your profile: **{rates['household_size']} Person(s)** living in a **{rates['apartment_size']:.1f} m²** apartment.")
    b_col1, b_col2, b_col3 = st.columns(3)
    
    with b_col1:
        st.markdown("**⚡ Electricity (Annual)**")
        elec_ann = stats.get("Electricity (kWh)", {}).get("avg_daily_consumption", 0.0) * 365.25
        if elec_ann > 0:
            benchmark_electricity = 1200 + (rates['household_size'] * 400) + (rates['apartment_size'] * 9)
            diff_pct = ((elec_ann - benchmark_electricity) / benchmark_electricity) * 100
            
            st.write(f"Projected Use: **{elec_ann:,.0f} kWh / year**")
            st.write(f"Personalized Benchmark: **{benchmark_electricity:,.0f} kWh / year**")
            
            if diff_pct <= -15:
                st.success(f"Status: Highly Efficient ({abs(diff_pct):.1f}% below benchmark)")
            elif diff_pct <= 15:
                st.info(f"Status: Normal Consumption ({diff_pct:+.1f}% of benchmark)")
            else:
                st.warning(f"Status: Above Average ({diff_pct:+.1f}% above benchmark)")
        else:
            st.caption("Log more data to see benchmarks.")

    with b_col2:
        st.markdown("**🔥 Heating / Hot Water (Annual)**")
        hw_ann = stats.get("Hot Water (MWh)", {}).get("avg_daily_consumption", 0.0) * 365.25 * 1000
        if hw_ann > 0:
            benchmark_heating = rates['apartment_size'] * 130
            diff_pct = ((hw_ann - benchmark_heating) / benchmark_heating) * 100
            
            st.write(f"Projected Use: **{hw_ann:,.0f} kWh / year** ({hw_ann/1000:.3f} MWh)")
            st.write(f"Personalized Benchmark: **{benchmark_heating:,.0f} kWh / year** ({benchmark_heating/1000:.3f} MWh)")
            
            if diff_pct <= -15:
                st.success(f"Status: Highly Efficient ({abs(diff_pct):.1f}% below benchmark)")
            elif diff_pct <= 15:
                st.info(f"Status: Normal Consumption ({diff_pct:+.1f}% of benchmark)")
            else:
                st.warning(f"Status: Above Average ({diff_pct:+.1f}% above benchmark)")
            st.caption("*(Note: Heating consumption is seasonal; projections will overstate costs in winter).*")
        else:
            st.caption("Log more data to see benchmarks.")

    with b_col3:
        st.markdown("**💧 Cold Water (Daily)**")
        cw_day = stats.get("Cold Water (m³)", {}).get("avg_daily_consumption", 0.0) * 1000
        if cw_day > 0:
            benchmark_water = rates['household_size'] * 125
            diff_pct = ((cw_day - benchmark_water) / benchmark_water) * 100
            
            st.write(f"Projected Daily Use: **{cw_day:,.0f} Liters / day**")
            st.write(f"Personalized Benchmark: **{benchmark_water:,.0f} Liters / day**")
            
            if diff_pct <= -15:
                st.success(f"Status: Highly Efficient ({abs(diff_pct):.1f}% below benchmark)")
            elif diff_pct <= 15:
                st.info(f"Status: Normal Consumption ({diff_pct:+.1f}% of benchmark)")
            else:
                st.warning(f"Status: Above Average ({diff_pct:+.1f}% above benchmark)")
        else:
            st.caption("Log more data to see benchmarks.")

    st.markdown("---")
    
    # =========================================================
    # 7. UTILITY SPECIFIC TABS
    # =========================================================
    st.subheader("Utility Specific Breakdown")
    tab_elec, tab_hw, tab_cw = st.tabs(["⚡ Electricity", "🔥 Hot Water (Fernwärme)", "💧 Cold Water"])
    
    with tab_elec:
        m_name = "Electricity (kWh)"
        if m_name in stats and stats[m_name]["entries_count"] > 1:
            s = stats[m_name]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Consumption", f"{s['total_consumption']:,.1f} kWh")
                st.metric("Daily Avg Consumption", f"{s['avg_daily_consumption']:.2f} kWh/day")
                st.metric("Monthly Avg Consumption", f"{s['avg_monthly_consumption']:.1f} kWh/month")
            with col2:
                st.metric("Total Cost", f"€{s['total_cost']:,.2f}")
                st.metric("Daily Avg Cost", f"€{s['avg_daily_cost']:.2f}/day")
                st.metric("Monthly Avg Cost", f"€{s['avg_monthly_cost']:.2f}/month")
            with col3:
                st.metric("Monthly Prepayment", f"€{s['monthly_prepayment']:.2f}/month")
                if s['projected_annual_standing'] >= 0:
                    st.metric("Projected Annual Refund", f"€{s['projected_annual_standing']:.2f}")
                else:
                    st.metric("Projected Annual Backpayment", f"-€{abs(s['projected_annual_standing']):.2f}", delta_color="inverse")
        else:
            st.info("Log at least two readings to calculate Electricity stats.")
            
    with tab_hw:
        m_name = "Hot Water (MWh)"
        if m_name in stats and stats[m_name]["entries_count"] > 1:
            s = stats[m_name]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Consumption", f"{s['total_consumption']:,.3f} MWh")
                st.metric("Daily Avg Consumption", f"{s['avg_daily_consumption']:.4f} MWh/day")
                st.metric("Monthly Avg Consumption", f"{s['avg_monthly_consumption']:.3f} MWh/month")
            with col2:
                st.metric("Total Cost", f"€{s['total_cost']:,.2f}")
                st.metric("Daily Avg Cost", f"€{s['avg_daily_cost']:.2f}/day")
                st.metric("Monthly Avg Cost", f"€{s['avg_monthly_cost']:.2f}/month")
            with col3:
                st.metric("Monthly Prepayment", f"€{s['monthly_prepayment']:.2f}/month")
                if s['projected_annual_standing'] >= 0:
                    st.metric("Projected Annual Refund", f"€{s['projected_annual_standing']:.2f}")
                else:
                    st.metric("Projected Annual Backpayment", f"-€{abs(s['projected_annual_standing']):.2f}", delta_color="inverse")
        else:
            st.info("Log at least two readings to calculate Hot Water stats.")
            
    with tab_cw:
        m_name = "Cold Water (m³)"
        if m_name in stats and stats[m_name]["entries_count"] > 1:
            s = stats[m_name]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Consumption", f"{s['total_consumption']:,.1f} m³")
                st.metric("Daily Avg Consumption", f"{s['avg_daily_consumption']:.3f} m³/day")
                st.metric("Monthly Avg Consumption", f"{s['avg_monthly_consumption']:.1f} m³/month")
            with col2:
                st.metric("Total Cost", f"€{s['total_cost']:,.2f}")
                st.metric("Daily Avg Cost", f"€{s['avg_daily_cost']:.2f}/day")
                st.metric("Monthly Avg Cost", f"€{s['avg_monthly_cost']:.2f}/month")
            with col3:
                st.metric("Monthly Prepayment", f"€{s['monthly_prepayment']:.2f}/month")
                if s['projected_annual_standing'] >= 0:
                    st.metric("Projected Annual Refund", f"€{s['projected_annual_standing']:.2f}")
                else:
                    st.metric("Projected Annual Backpayment", f"-€{abs(s['projected_annual_standing']):.2f}", delta_color="inverse")
        else:
            st.info("Log at least two readings to calculate Cold Water stats.")

    st.markdown("---")
    
    # =========================================================
    # 8. HISTORICAL TIMELINE GRAPHS
    # =========================================================
    st.subheader("Historical Timeline Graphs")
    has_sufficient_data = any(m.get("entries_count", 0) > 1 for m in stats.values())
    
    if not has_sufficient_data:
        st.info("Visual charts require at least two logged points to show historical progression.")
    else:
        # Cumulative Cost Line (Line Color Mapped)
        fig_cum = px.line(
            processed_logs[processed_logs['cumulative_cost'] > 0],
            x='date',
            y='cumulative_cost',
            color='meter',
            markers=True,
            title="Cumulative Spent Over Time (€)",
            labels={"cumulative_cost": "Total Spent (€)", "date": "Date"},
            template=plotly_template,
            color_discrete_map=color_map  # Enforced
        )
        st.plotly_chart(fig_cum, use_container_width=True)
        
        active_intervals = processed_logs[processed_logs['days_elapsed'] > 0]
        if not active_intervals.empty:
            # 8B. Daily Cost Stacked Bar (Bar Color Mapped)
            fig_daily_cost = px.bar(
                active_intervals,
                x="date",
                y="daily_cost_rate",
                color="meter",
                title="Running Daily Financial Burn Rate (Standardized €/day)",
                labels={"daily_cost_rate": "Financial Burn Rate (€/day)", "date": "Date"},
                template=plotly_template,
                color_discrete_map=color_map  # Enforced
            )
            st.plotly_chart(fig_daily_cost, use_container_width=True)

            # Daily Usage Rates Line (Line Color Mapped)
            fig_rate = px.line(
                active_intervals,
                x='date',
                y='daily_rate',
                color='meter',
                markers=True,
                title="Usage Rate Changes Over Time (Consumption Unit / Day)",
                labels={"daily_rate": "Average Units Consumed per Day", "date": "Reading Date"},
                facet_col='meter',
                facet_col_wrap=3,
                category_orders={"meter": ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]},
                template=plotly_template,
                color_discrete_map=color_map  # Enforced
            )
            fig_rate.update_yaxes(matches=None)
            st.plotly_chart(fig_rate, use_container_width=True)