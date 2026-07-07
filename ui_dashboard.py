# ui_dashboard.py
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

def calculate_monthly_allocated_consumption(processed_logs, rates):
    if processed_logs.empty:
        return {}
        
    meters_meta = {
        "Electricity (kWh)": {"rate_key": "electricity_kwh", "unit": "kWh"},
        "Hot Water (MWh)": {"rate_key": "hot_water_mwh", "unit": "MWh"},
        "Cold Water (m³)": {"rate_key": "cold_water_m3", "unit": "m³"}
    }
    
    today = datetime.date.today()
    start_period = today - datetime.timedelta(days=365)
    # Generate all dates from 1 year ago to today
    date_range = pd.date_range(start=start_period, end=today).date
    
    monthly_data = {}
    
    for meter_name, meta in meters_meta.items():
        meter_df = processed_logs[processed_logs['meter'] == meter_name].copy()
        if len(meter_df) < 2:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        
        # Create a continuous daily timeline
        df_days = pd.DataFrame({"date": date_range})
        df_days['rate'] = 0.0
        
        last_rate = 0.0
        last_date = None
        
        # Fill in the actual logged intervals
        for j in range(1, len(meter_df)):
            start = meter_df.iloc[j-1]['date']
            end = meter_df.iloc[j]['date']
            days = (end - start).days
            if days > 0:
                rate = (meter_df.iloc[j]['reading'] - meter_df.iloc[j-1]['reading']) / days
                df_days.loc[(df_days['date'] > start) & (df_days['date'] <= end), 'rate'] = rate
                last_rate = rate
                last_date = end
                
        # Carry forward the last known rate up to today (handles the current month extrapolation)
        if last_date is not None:
            df_days.loc[df_days['date'] > last_date, 'rate'] = last_rate
            
        # Calculate daily costs (including pro-rated base charges for electricity)
        unit_rate = rates[meta["rate_key"]]
        if meter_name == "Electricity (kWh)":
            daily_base = rates["electricity_base"] / 30.44
            df_days['cost'] = df_days.apply(
                lambda r: (r['rate'] * unit_rate) + daily_base if r['rate'] > 0 else 0.0, 
                axis=1
            )
        else:
            df_days['cost'] = df_days['rate'] * unit_rate
            
        # Filter out days before tracking started (where rate is 0)
        df_days = df_days[df_days['rate'] > 0]
        
        if df_days.empty:
            continue
            
        # Aggregate daily data into calendar months
        df_days['month'] = pd.to_datetime(df_days['date']).dt.to_period('M').astype(str)
        df_monthly = df_days.groupby('month').agg(
            total_consumption=('rate', 'sum'),
            total_cost=('cost', 'sum')
        ).reset_index()
        
        # Calculate Rolling 3-Month Averages & Month-over-Month Percentage Change Rates
        df_monthly['rolling_3mo'] = df_monthly['total_consumption'].rolling(window=3, min_periods=1).mean()
        df_monthly['mom_pct_change'] = df_monthly['total_consumption'].pct_change().fillna(0.0) * 100
        
        # Sort and keep a maximum of 12 months back
        df_monthly = df_monthly.sort_values(by='month').tail(12)
        monthly_data[meter_name] = df_monthly
        
    return monthly_data


def get_daily_prorated_electricity(processed_logs):
    """
    Interpoliert die unregelmäßigen manuellen Stromzählerstände in tägliche kWh-Verbrauchswerte.
    """
    elec_df = processed_logs[processed_logs['meter'] == "Electricity (kWh)"].copy()
    if len(elec_df) < 2:
        return pd.DataFrame(columns=["date", "total_daily_kwh"])
    
    elec_df = elec_df.sort_values(by="date")
    first_date = elec_df['date'].iloc[0]
    last_date = elec_df['date'].iloc[-1]
    
    daily_records = []
    
    for i in range(1, len(elec_df)):
        start = elec_df.iloc[i-1]['date']
        end = elec_df.iloc[i]['date']
        days = (end - start).days
        if days > 0:
            daily_rate = (elec_df.iloc[i]['reading'] - elec_df.iloc[i-1]['reading']) / days
            curr = start + datetime.timedelta(days=1)
            while curr <= end:
                daily_records.append({"date": curr, "total_daily_kwh": daily_rate})
                curr += datetime.timedelta(days=1)
                
    return pd.DataFrame(daily_records)


def get_season_name(month_str):
    try:
        month = int(month_str.split("-")[1])
        if month in [12, 1, 2]:
            return "❄️ Winter (Dec-Feb)"
        elif month in [3, 4, 5]:
            return "🌱 Spring (Mar-May)"
        elif month in [6, 7, 8]:
            return "☀️ Summer (Jun-Aug)"
        else:
            return "🍂 Autumn (Sep-Nov)"
    except Exception:
        return "Unknown"


def render_page(processed_logs, stats, rates, plotly_template, smart_logs=None):
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
        "Fixed (Base Standing Charge)": "#ef4444",    # Red
        "Unbekannt (Rest)": "#64748b"                # Slate grey
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
        st.plotly_chart(fig_running_ledger, width="stretch")

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
        st.plotly_chart(fig_monthly_bars, width="stretch")
        
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
            st.plotly_chart(fig_elec_breakdown, width="stretch")
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
        st.plotly_chart(fig_cost_pie, width="stretch")

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
        st.plotly_chart(fig_co2_pie, width="stretch")

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
    st.plotly_chart(fig_compare_bar, width="stretch")

    st.markdown("---")

    # =========================================================
    # 5B. SMART DEVICE SUB-METER ANALYSIS
    # =========================================================
    if smart_logs is not None and not smart_logs.empty:
        st.subheader("🔌 Smart Device Log Analysis")
        st.write("Detailed historical breakdown of individual smart plugs compared directly to your main meter.")
        
        # 1. Standardize and deduplicate smart logs
        smart_logs['date'] = pd.to_datetime(smart_logs['date']).dt.date
        df_smart_clean = smart_logs.groupby(["date", "device_name"]).first().reset_index()
        
        # Latest sync date metrics
        latest_date = df_smart_clean['date'].max()
        df_latest_smart = df_smart_clean[df_smart_clean['date'] == latest_date].copy()
        
        st.info(f"Showing measurements from date: **{latest_date}**")
        
        # A. Line Chart: Smart Device Daily Energy Consumption Over Time
        fig_smart_time = px.line(
            df_smart_clean,
            x="date",
            y="today_energy_kwh",
            color="device_name",
            markers=True,
            title="Daily Smart Plug Energy Consumption Over Time (kWh)",
            labels={"today_energy_kwh": "Energy Consumed Today (kWh)", "date": "Date", "device_name": "Device Group"},
            template=plotly_template
        )
        st.plotly_chart(fig_smart_time, width="stretch")
        
        # B. Advanced Comparison with Total Prorated Electricity
        df_daily_manual = get_daily_prorated_electricity(processed_logs)
        
        if not df_daily_manual.empty:
            # Pivot smart logs to align with manual readings on dates
            df_smart_pivot = df_smart_clean.pivot(index="date", columns="device_name", values="today_energy_kwh").fillna(0.0)
            df_compare = pd.merge(df_daily_manual, df_smart_pivot, on="date", how="inner")
            
            if not df_compare.empty:
                device_cols = list(df_smart_pivot.columns)
                df_compare["Smart_Sum"] = df_compare[device_cols].sum(axis=1)
                
                # Calculate the remainder as Unbekannt (Rest)
                df_compare["Unbekannt (Rest)"] = (df_compare["total_daily_kwh"] - df_compare["Smart_Sum"]).clip(lower=0.0)
                
                melt_cols = device_cols + ["Unbekannt (Rest)"]
                df_compare_melted = df_compare.melt(
                    id_vars=["date"],
                    value_vars=melt_cols,
                    var_name="Category",
                    value_name="Daily Energy (kWh)"
                )
                
                st.markdown("#### ⚖️ Smart Devices vs. Total Electricity Consumption")
                st.write("Compare the proportion of energy tracked by your smart devices against the total daily electricity consumption calculated from your manual meter readings.")
                
                # Scaling toggle selector
                scale_mode = st.radio(
                    "Choose Y-Axis Scale Transformation:",
                    ["Linear Scale (Normal)", "Logarithmic Scale (Log10 - Best for highlighting smaller device trends)"],
                    horizontal=True
                )
                
                fig_compare_stacked = px.area(
                    df_compare_melted,
                    x="date",
                    y="Daily Energy (kWh)",
                    color="Category",
                    title="Daily Electricity Allocation Breakdown Over Time",
                    labels={"Daily Energy (kWh)": "Consumption (kWh / Day)", "date": "Date"},
                    template=plotly_template,
                    color_discrete_map=color_map
                )
                
                if "Logarithmic" in scale_mode:
                    fig_compare_stacked.update_yaxes(type="log")
                    fig_compare_stacked.update_layout(title="Daily Electricity Allocation Breakdown Over Time (Logarithmic Scale)")
                    
                st.plotly_chart(fig_compare_stacked, width="stretch")
                
            else:
                st.warning("No overlapping dates found between manual meter logs and smart device logs to calculate the remainder analysis.")
        else:
            st.info("Log at least two manual electricity readings to enable the smart device comparison model.")
            
        # Summary Row Table
        st.markdown("#### Smart Plugs: Activity & Usage Table")
        st.dataframe(
            df_latest_smart[[
                "device_name", "ip", "current_power_w", 
                "today_energy_kwh", "month_energy_kwh", 
                "today_runtime_min", "month_runtime_min"
            ]].rename(columns={
                "device_name": "Device Name",
                "ip": "IP Address",
                "current_power_w": "Power (W)",
                "today_energy_kwh": "Today (kWh)",
                "month_energy_kwh": "Month (kWh)",
                "today_runtime_min": "Runtime Today (Min)",
                "month_runtime_min": "Runtime Month (Min)"
            }),
            width="stretch"
        )
        st.markdown("---")

    # =========================================================
    # 5C. CROSS-UTILITY NORMALIZATION & LOG ANALYSIS (NEW)
    # =========================================================
    st.subheader("📈 Cross-Utility Normalization & Log Analysis")
    st.write(
        "Comparing utilities with vastly different scales (e.g., Megawatt hours of heating vs. Liters of water) "
        "is challenging. Below are two normalized, scale-free comparisons designed to balance these differences:"
    )
    
    active_intervals = processed_logs[processed_logs['days_elapsed'] > 0].copy()
    
    if len(active_intervals['meter'].unique()) > 1:
        col_norm1, col_norm2 = st.columns(2)
        
        with col_norm1:
            st.markdown("#### 💵 Logarithmic Daily Financial Burn Rate (€ / Day)")
            st.caption(
                "By converting physical units into daily financial costs (€/day), we establish a common scale. "
                "A **Logarithmic Y-Axis** ensures that small water costs (e.g., €0.20/day) remain visible alongside "
                "large electricity or heating spikes (e.g., €15.00/day)."
            )
            
            fig_log_burn = px.line(
                active_intervals,
                x='date',
                y='daily_cost_rate',
                color='meter',
                markers=True,
                title="Daily Burn Rate (€ / Day) - Logarithmic Scale",
                labels={"daily_cost_rate": "Burn Rate (€ / Day)", "date": "Reading Date", "meter": "Utility"},
                template=plotly_template,
                color_discrete_map=color_map
            )
            fig_log_burn.update_yaxes(type="log")
            st.plotly_chart(fig_log_burn, width="stretch")
            
        with col_norm2:
            st.markdown("#### 📊 Unit-Free Relative Fluctuations (% of baseline)")
            st.caption(
                "This chart normalizes all physical consumption units by expressing them as a percentage "
                "of your utility-specific average. This isolates behavioral changes from the scale of the unit."
            )
            
            # Group and calculate percent of baseline
            normalized_list = []
            for meter_name in active_intervals['meter'].unique():
                sub_df = active_intervals[active_intervals['meter'] == meter_name].copy()
                avg_rate = sub_df['daily_rate'].mean()
                if avg_rate > 0:
                    sub_df['percent_of_baseline'] = (sub_df['daily_rate'] / avg_rate) * 100
                    normalized_list.append(sub_df)
            
            if normalized_list:
                df_normalized = pd.concat(normalized_list).sort_values(by='date')
                
                fig_norm_fluct = px.line(
                    df_normalized,
                    x='date',
                    y='percent_of_baseline',
                    color='meter',
                    markers=True,
                    title="Usage Fluctuations relative to Personal Baseline (Average = 100%)",
                    labels={"percent_of_baseline": "Relative Usage (% of Personal Average)", "date": "Reading Date"},
                    template=plotly_template,
                    color_discrete_map=color_map
                )
                fig_norm_fluct.add_hline(y=100.0, line_dash="dash", line_color="#64748b", annotation_text="Your Baseline (100%)")
                st.plotly_chart(fig_norm_fluct, width="stretch")
            else:
                st.caption("Insufficient usage delta to calculate standard baseline.")
                
        st.markdown("---")
    else:
        st.info("Log entries for at least two different utilities to activate cross-utility normalization metrics.")

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
        # 8A. Calendar Monthly Consumption Chart (Combined Bar & Line Trend)
        st.write("### 📅 Prorated Monthly Consumption & Trend Line")
        st.caption("This chart displays your consumption distributed day-by-day and aggregated by calendar month, overlaid with a **3-Month Rolling Average Trend Line** to smooth out minor log date variations.")
        
        monthly_allocated_data = calculate_monthly_allocated_consumption(processed_logs, rates)
        if monthly_allocated_data:
            selected_meter_chart = st.selectbox(
                "Select Utility to View Calendar Month Consumption:",
                ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
            )
            filtered_monthly = monthly_allocated_data.get(selected_meter_chart)
            if filtered_monthly is not None and not filtered_monthly.empty:
                # Extract corresponding unit from selection name
                unit_label = selected_meter_chart.split("(")[-1].replace(")", "")
                
                # We use Plotly Graph Objects to gracefully combine Bar and Line traces
                fig_allocated = go.Figure()
                
                # 1. Bar Chart Trace (Physical Units consumed)
                fig_allocated.add_trace(go.Bar(
                    x=filtered_monthly['month'],
                    y=filtered_monthly['total_consumption'],
                    name='Monthly Consumption',
                    marker_color=color_map[selected_meter_chart],
                    customdata=filtered_monthly[['total_cost']],
                    hovertemplate="<b>Month:</b> %{x}<br>" +
                                  f"<b>Consumption:</b> %{{y:.2f}} {unit_label}<br>" +
                                  "<b>Estimated Cost:</b> €%{customdata[0]:,.2f}<extra></extra>"
                ))
                
                # 2. Line Chart Trace (Rolling 3-Month average trend line)
                fig_allocated.add_trace(go.Scatter(
                    x=filtered_monthly['month'],
                    y=filtered_monthly['rolling_3mo'],
                    name='3-Month Rolling Avg',
                    mode='lines+markers',
                    # Use a contrasting vibrant color to separate the line from the bars
                    line=dict(color="#f43f5e" if selected_meter_chart == "Electricity (kWh)" else "#10b981", width=3.5),
                    hovertemplate=f"<b>3-Month Trend:</b> %{{y:.2f}} {unit_label}<extra></extra>"
                ))
                
                fig_allocated.update_layout(
                    title=f"Calendar Monthly Consumption & 3-Month Trend Line - {selected_meter_chart}",
                    xaxis_title="Month",
                    yaxis_title=f"Consumption ({unit_label})",
                    template=plotly_template,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_allocated, width="stretch")
                
                # 8B. Advanced Sparse Data Analytics
                st.write("### 🍂 Sparse Data Analytics & Trends")
                st.caption("These specialized visual metrics are designed to help make sense of historical habits across seasonal cycles.")
                
                col_adv1, col_col2 = st.columns(2)
                
                with col_adv1:
                    # Month-Over-Month Change Rate (%)
                    # We render a dynamic bar chart that highlights Savings in Green and Increases in Red
                    filtered_monthly['direction'] = filtered_monthly['mom_pct_change'].apply(
                        lambda val: "Saving (Decrease)" if val <= 0 else "Usage Increase"
                    )
                    
                    fig_mom = px.bar(
                        filtered_monthly,
                        x='month',
                        y='mom_pct_change',
                        color='direction',
                        color_discrete_map={"Saving (Decrease)": "#22c55e", "Usage Increase": "#ef4444"},
                        title=f"Month-over-Month Consumption Change Rate (%) - {selected_meter_chart}",
                        labels={"mom_pct_change": "Change (%)", "month": "Month", "direction": "Trend"},
                        template=plotly_template
                    )
                    fig_mom.add_hline(y=0.0, line_color="#94a3b8", line_dash="dash")
                    st.plotly_chart(fig_mom, width="stretch")
                    
                with col_col2:
                    # Seasonal Consumption Profile Grouping
                    filtered_monthly['season'] = filtered_monthly['month'].apply(get_season_name)
                    df_seasonal = filtered_monthly.groupby('season').agg(
                        avg_consumption=('total_consumption', 'mean'),
                        avg_cost=('total_cost', 'mean')
                    ).reset_index()
                    
                    # Sort seasons chronologically to keep the chart cohesive
                    season_order = ["❄️ Winter (Dec-Feb)", "🌱 Spring (Mar-May)", "☀️ Summer (Jun-Aug)", "🍂 Autumn (Sep-Nov)"]
                    df_seasonal['season'] = pd.Categorical(df_seasonal['season'], categories=season_order, ordered=True)
                    df_seasonal = df_seasonal.sort_values('season')
                    
                    fig_season = px.bar(
                        df_seasonal,
                        x='season',
                        y='avg_consumption',
                        title=f"Average Consumption by Season - {selected_meter_chart}",
                        labels={"avg_consumption": f"Average Usage ({unit_label})", "season": "Season"},
                        template=plotly_template,
                        color='season',
                        color_discrete_map={
                            "❄️ Winter (Dec-Feb)": "#38bdf8",  # Sky blue
                            "🌱 Spring (Mar-May)": "#34d399",  # Emerald green
                            "☀️ Summer (Jun-Aug)": "#f59e0b",  # Amber
                            "🍂 Autumn (Sep-Nov)": "#fb7185"   # Rose
                        }
                    )
                    # Custom hover detailing showing average seasonal costs in €
                    fig_season.update_traces(
                        hovertemplate="<b>Season:</b> %{x}<br>" +
                                      f"<b>Avg Consumption:</b> %{{y:.2f}} {unit_label}<br>" +
                                      "<b>Avg Monthly Cost:</b> €%{customdata[0]:,.2f}<extra></extra>",
                        customdata=df_seasonal[['avg_cost']]
                    )
                    st.plotly_chart(fig_season, width="stretch")
                
            else:
                st.caption(f"Insufficient historical data to segment monthly allocated chart for {selected_meter_chart}.")
        else:
            st.caption("Log more entries to calculate dynamic monthly tracking estimates.")
        
        st.markdown("---")

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
        st.plotly_chart(fig_cum, width="stretch")
        
        active_intervals = processed_logs[processed_logs['days_elapsed'] > 0]
        if not active_intervals.empty:
            # 8C. Daily Cost Stacked Bar (Bar Color Mapped)
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
            st.plotly_chart(fig_daily_cost, width="stretch")

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
            st.plotly_chart(fig_rate, width="stretch")
