# dashboard/smart_devices.py
import pandas as pd
import streamlit as st
import plotly.express as px
from utils import database as db
from utils.i18n import t  # Importiert das Übersetzungsmodul
from .calculations import get_daily_prorated_electricity

def render(current_user_id, processed_logs, smart_logs, stats, rates, color_map, plotly_template):
    st.subheader(t("sm_header"))
    st.write(t("sm_subtitle"))
    
    # 1. Standardize and deduplicate smart logs
    smart_logs['date'] = pd.to_datetime(smart_logs['date']).dt.date
    df_smart_clean = smart_logs.groupby(["date", "device_name"]).first().reset_index()
    
    # Latest sync date metrics
    latest_date = df_smart_clean['date'].max()
    df_latest_smart = df_smart_clean[df_smart_clean['date'] == latest_date].copy()
    
    st.info(t("sm_showing_date").format(date=latest_date))
    
    # A. Line Chart: Smart Device Daily Energy Consumption Over Time
    fig_smart_time = px.line(
        df_smart_clean,
        x="date",
        y="today_energy_kwh",
        color="device_name",
        markers=True,
        title=t("sm_title_time"),
        labels={
            "today_energy_kwh": t("sm_label_energy"), 
            "date": t("sm_label_date"), 
            "device_name": t("sm_label_group")
        },
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
            
            st.markdown(f"#### {t('sm_compare_header')}")
            
            # Scaling toggle selector
            scale_mode = st.radio(
                t("sm_scale_label"),
                [t("sm_scale_linear"), t("sm_scale_log")],
                horizontal=True
            )
            
            fig_compare_stacked = px.area(
                df_compare_melted,
                x="date",
                y="Daily Energy (kWh)",
                color="Category",
                title=t("sm_title_allocation"),
                labels={
                    "Daily Energy (kWh)": t("sm_label_consumption"), 
                    "date": t("sm_label_date"),
                    "Category": t("sm_label_group")
                },
                template=plotly_template,
                color_discrete_map=color_map
            )
            
            if t("sm_scale_log") in scale_mode:
                fig_compare_stacked.update_yaxes(type="log")
                
            st.plotly_chart(fig_compare_stacked, width="stretch")

            # ---------------------------------------------------------
            # MATHEMATISCHES NEU-DESIGN: ALLZEIT-MITTELWERTE SEIT EINZUG
            # ---------------------------------------------------------
            st.markdown(f"#### {t('sm_cost_header')}")
            st.write(t("sm_cost_desc"))
            
            # 1. Ermittle effektiven Startpunkt (jüngstes Datum aus Einzug & Tarifstart)
            move_in = rates.get("move_in_date")
            tariff_start = rates.get("tariff_start_date")
            effective_start_date = None
            if move_in and tariff_start:
                effective_start_date = max(pd.to_datetime(move_in).date(), pd.to_datetime(tariff_start).date())
            
            # 2. Filtere Smart-Logs auf den aktiven Zeitraum
            if effective_start_date is not None:
                df_smart_active_period = df_smart_clean[df_smart_clean['date'] >= effective_start_date]
            else:
                df_smart_active_period = df_smart_clean
                
            # 3. Berechne den historischen Durchschnitt pro Tag für jedes Gerät
            df_device_averages = df_smart_active_period.groupby("device_name")["today_energy_kwh"].mean().reset_index()
            
            # Kosten-Allokation berechnen anhand des Allzeit-Durchschnitts
            cost_allocation = []
            elec_rate = rates["electricity_kwh"]
            total_allocated_smart_cost = 0.0
            
            for _, dev_row in df_device_averages.iterrows():
                dev_cost = dev_row["today_energy_kwh"] * elec_rate
                total_allocated_smart_cost += dev_cost
                cost_allocation.append({
                    "Group": dev_row["device_name"],
                    "Daily Cost (€/day)": dev_cost
                })
            
            # Gesamter täglicher Zähler-Durchschnitt aus stats holen
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
                title=t("sm_cost_title").format(val=total_avg_daily_cost),
                template=plotly_template,
                color="Group",
                color_discrete_map=color_map,
                hole=0.4
            )
            st.plotly_chart(fig_cost_alloc_pie, width="stretch")
            
        else:
            st.warning(t("sm_no_overlap_warning"))
    else:
        st.info(t("sm_no_manual_logs"))

    # Summary Row Table
    st.markdown(f"#### {t('sm_table_header')}")
    st.dataframe(
        df_latest_smart[[
            "device_name", "ip", "current_power_w", 
            "today_energy_kwh", "month_energy_kwh", 
            "today_runtime_min", "month_runtime_min"
        ]].rename(columns={
            "device_name": t("sm_col_name"),
            "ip": t("sm_col_ip"),
            "current_power_w": t("sm_col_power"),
            "today_energy_kwh": t("sm_col_today"),
            "month_energy_kwh": t("sm_col_month"),
            "today_runtime_min": t("sm_col_rt_today"),
            "month_runtime_min": t("sm_col_rt_month")
        }),
        width="stretch"
    )
    st.markdown("---")