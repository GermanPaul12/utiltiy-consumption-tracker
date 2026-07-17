# dashboard/smart_devices.py
import pandas as pd
import streamlit as st
import plotly.express as px
from utils import database as db
from .calculations import get_daily_prorated_electricity

def render(current_user_id, processed_logs, smart_logs, stats, rates, color_map, plotly_template):
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
    
    # B. Advanced Comparison with Total Prorated Electricity & Cost Share
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
                
            st.plotly_chart(fig_compare_stacked, width="stretch")

            # Daily Electricity Cost Share Breakdown (considering daily average costs)
            st.markdown("#### 💶 Daily Electricity Cost Distribution (€ / Day)")
            st.write("Calculated using your actual electricity price per kWh and base price:")
            
            # Use latest metrics day for allocation, apply rate
            cost_allocation = []
            elec_rate = rates["electricity_kwh"]
            
            total_allocated_smart_cost = 0.0
            for _, dev_row in df_latest_smart.iterrows():
                dev_cost = dev_row["today_energy_kwh"] * elec_rate
                total_allocated_smart_cost += dev_cost
                cost_allocation.append({
                    "Group": dev_row["device_name"],
                    "Daily Cost (€/day)": dev_cost
                })
            
            # Total daily cost from manual zähler (using dynamic average)
            total_avg_daily_cost = stats.get("Electricity (kWh)", {}).get("avg_daily_cost", 0.0)
            unbekannt_cost = max(0.0, total_avg_daily_cost - total_allocated_smart_cost)
            
            cost_allocation.append({
                "Group": "Unbekannt (Rest)",
                "Daily Cost (€/day)": unbekannt_cost
            })
            
            df_cost_alloc = pd.DataFrame(cost_allocation)
            
            fig_cost_alloc_pie = px.pie(
                df_cost_alloc,
                values="Daily Cost (€/day)",
                names="Group",
                title=f"Electricity Cost Allocation (Total average: €{total_avg_daily_cost:.2f} / day)",
                template=plotly_template,
                color="Group",
                color_discrete_map=color_map,
                hole=0.4
            )
            st.plotly_chart(fig_cost_alloc_pie, width="stretch")
            
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