import os
import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from .env file if it exists
load_dotenv()

# Set Page Config
st.set_page_config(
    page_title="Utility Tracker - Mannheim",
    page_icon="⚡",
    layout="wide"
)

# 1. Establish Database Connection Engine
DB_PW = os.getenv("DB_PW")

if DB_PW:
    # Construct Supabase connection URL dynamically using pg8000 driver
    # We escape the password in case it contains special characters
    from urllib.parse import quote_plus
    escaped_pw = quote_plus(DB_PW)
    db_url = f"postgresql+pg8000://postgres:{escaped_pw}@db.reqassdcxcsvrxalmmsh.supabase.co:5432/postgres"
else:
    # Local fallback to SQLite if DB_PW is missing
    db_url = "sqlite:///utility_tracker.db"

engine = create_engine(db_url)

# Helper function to run SELECT queries and return a DataFrame
def run_query(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

# Helper function to execute INSERT/UPDATE/DELETE transactions
def execute_db(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

# 2. Database Initialization
def initialize_database():
    is_sqlite = engine.dialect.name == 'sqlite'
    
    # Create tables
    if is_sqlite:
        execute_db("CREATE TABLE IF NOT EXISTS rates (id INTEGER PRIMARY KEY, electricity_kwh REAL, electricity_base REAL, hot_water_mwh REAL, cold_water_m3 REAL)")
        execute_db("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, meter TEXT, reading REAL)")
    else:
        execute_db("CREATE TABLE IF NOT EXISTS rates (id INT PRIMARY KEY, electricity_kwh DOUBLE PRECISION, electricity_base DOUBLE PRECISION, hot_water_mwh DOUBLE PRECISION, cold_water_m3 DOUBLE PRECISION)")
        execute_db("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, date DATE, meter VARCHAR(100), reading DOUBLE PRECISION)")

    # Seed default rates if empty
    df_rates = run_query("SELECT * FROM rates")
    if df_rates.empty:
        execute_db("""
            INSERT INTO rates (id, electricity_kwh, electricity_base, hot_water_mwh, cold_water_m3)
            VALUES (1, 0.282, 16.80, 95.00, 4.50)
        """)

initialize_database()

# Data Helper Functions
def load_rates():
    df = run_query("SELECT * FROM rates WHERE id = 1")
    return df.iloc[0].to_dict()

def save_rates(rates_dict):
    execute_db("""
        UPDATE rates 
        SET electricity_kwh = :elec_kwh, 
            electricity_base = :elec_base, 
            hot_water_mwh = :hw_mwh, 
            cold_water_m3 = :cw_m3 
        WHERE id = 1
    """, params={
        "elec_kwh": rates_dict["electricity_kwh"],
        "elec_base": rates_dict["electricity_base"],
        "hw_mwh": rates_dict["hot_water_mwh"],
        "cw_m3": rates_dict["cold_water_m3"]
    })

def load_logs():
    df = run_query("SELECT * FROM logs ORDER BY date ASC")
    if not df.empty:
        # standardizing database date format
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

# Metrics Calculation
def calculate_metrics(logs_df, rates):
    if logs_df.empty:
        return pd.DataFrame(), {}

    meters = {
        "Electricity (kWh)": "electricity_kwh",
        "Hot Water (MWh)": "hot_water_mwh",
        "Cold Water (m³)": "cold_water_m3"
    }
    
    processed_dfs = []
    summary_stats = {}
    
    for meter_name, rate_key in meters.items():
        meter_df = logs_df[logs_df['meter'] == meter_name].copy()
        if meter_df.empty:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        meter_df['Consumption'] = meter_df['reading'].diff().fillna(0)
        
        unit_rate = rates[rate_key]
        meter_df['Cost'] = meter_df['Consumption'] * unit_rate
        
        processed_dfs.append(meter_df)
        
        total_consumption = meter_df['Consumption'].sum()
        total_variable_cost = meter_df['Cost'].sum()
        
        summary_stats[meter_name] = {
            "Total Consumption": total_consumption,
            "Variable Cost": total_variable_cost,
            "Last Reading": meter_df['reading'].iloc[-1],
            "Last Date": meter_df['date'].iloc[-1],
            "Entries Count": len(meter_df)
        }
        
    if not processed_dfs:
        return pd.DataFrame(), {}
        
    combined_df = pd.concat(processed_dfs).sort_values(by='date')
    
    # Calculate electricity monthly base cost
    elec_df = logs_df[logs_df['meter'] == "Electricity (kWh)"]
    if not elec_df.empty and len(elec_df) > 1:
        min_date = elec_df['date'].min()
        max_date = elec_df['date'].max()
        days_elapsed = (max_date - min_date).days
        months_elapsed = max(1.0, round(days_elapsed / 30.44, 2))
        base_cost_total = months_elapsed * rates['electricity_base']
        if "Electricity (kWh)" in summary_stats:
            summary_stats["Electricity (kWh)"]["Base Cost"] = base_cost_total
    else:
        if "Electricity (kWh)" in summary_stats:
            summary_stats["Electricity (kWh)"]["Base Cost"] = 0.0

    return combined_df, summary_stats

# Main Navigation
st.sidebar.title("Utility Tracker")
st.sidebar.caption("Mannheim (68163) Tariffs")
if DB_PW:
    st.sidebar.success("CONNECTED TO SUPABASE")
else:
    st.sidebar.warning("RUNNING LOCALLY (SQLITE)")

page = st.sidebar.radio(
    "Go to",
    ["Dashboard Overview", "Log Consumption", "Cost Settings", "Manage History"]
)

# Load State
rates = load_rates()
logs = load_logs()
processed_logs, stats = calculate_metrics(logs, rates)

# --- PAGE 1: DASHBOARD OVERVIEW ---
if page == "Dashboard Overview":
    st.title("Utility Consumption Dashboard")
    
    if processed_logs.empty:
        st.info("Your database history is currently empty. Go to 'Log Consumption' to record your initial readings.")
    else:
        # Cost Aggregations
        elec_var = stats.get("Electricity (kWh)", {}).get("Variable Cost", 0.0)
        elec_base = stats.get("Electricity (kWh)", {}).get("Base Cost", 0.0)
        elec_total = elec_var + elec_base
        
        hw_total = stats.get("Hot Water (MWh)", {}).get("Variable Cost", 0.0)
        cw_total = stats.get("Cold Water (m³)", {}).get("Variable Cost", 0.0)
        total_cost = elec_total + hw_total + cw_total
        
        st.caption("ℹ️ Note: The initial reading recorded for any meter acts as a baseline. Subsequent readings calculate consumption.")
        
        # Overview Cards
        st.subheader("Global Statistics")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cumulative Cost", f"€{total_cost:,.2f}")
        col2.metric("Electricity Cost", f"€{elec_total:,.2f}", f"Base: €{elec_base:,.2f}")
        col3.metric("Hot Water (Fernwärme)", f"€{hw_total:,.2f}")
        col4.metric("Cold Water Cost", f"€{cw_total:,.2f}")
        
        st.markdown("---")
        
        # Individual Stats
        st.subheader("Current Meter Status")
        m_col1, m_col2, m_col3 = st.columns(3)
        
        with m_col1:
            st.markdown("### ⚡ Electricity")
            if "Electricity (kWh)" in stats:
                st.write(f"**Current Reading:** {stats['Electricity (kWh)']['Last Reading']} kWh")
                st.write(f"**Total Consumption:** {stats['Electricity (kWh)']['Total Consumption']:.1f} kWh")
                st.write(f"**Last Logged:** {stats['Electricity (kWh)']['Last Date']}")
            else:
                st.caption("No electricity entries yet.")
                
        with m_col2:
            st.markdown("### 🔥 Hot Water (Fernwärme)")
            if "Hot Water (MWh)" in stats:
                st.write(f"**Current Reading:** {stats['Hot Water (MWh)']['Last Reading']} MWh")
                st.write(f"**Total Consumption:** {stats['Hot Water (MWh)']['Total Consumption']:.3f} MWh")
                st.write(f"**Last Logged:** {stats['Hot Water (MWh)']['Last Date']}")
            else:
                st.caption("No hot water entries yet.")
                
        with m_col3:
            st.markdown("### 💧 Cold Water")
            if "Cold Water (m³)" in stats:
                st.write(f"**Current Reading:** {stats['Cold Water (m³)']['Last Reading']} m³")
                st.write(f"**Total Consumption:** {stats['Cold Water (m³)']['Total Consumption']:.1f} m³")
                st.write(f"**Last Logged:** {stats['Cold Water (m³)']['Last Date']}")
            else:
                st.caption("No cold water entries yet.")

        st.markdown("---")
        
        # Charts
        st.subheader("Visual Analysis")
        has_sufficient_data = any(m.get("Entries Count", 0) > 1 for m in stats.values())
        
        if not has_sufficient_data:
            st.info("Charts will populate once you record at least two sequential readings for a meter.")
        else:
            chart_df = processed_logs.copy()
            chart_df['Month'] = pd.to_datetime(chart_df['date']).dt.to_period('M').astype(str)
            
            # Monthly Cost Distribution
            monthly_cost = chart_df.groupby(['Month', 'meter'])['Cost'].sum().reset_index()
            fig_cost = px.bar(
                monthly_cost, 
                x='Month', 
                y='Cost', 
                color='meter', 
                title="Variable Cost Distribution by Month (€)",
                labels={"Cost": "Cost (€)", "Month": "Month"},
                barmode='group'
            )
            st.plotly_chart(fig_cost, use_container_width=True)
            
            # Trend Lines
            trend_col1, trend_col2, trend_col3 = st.columns(3)
            
            with trend_col1:
                elec_trend = chart_df[chart_df['meter'] == "Electricity (kWh)"]
                if len(elec_trend) > 1:
                    fig = px.line(elec_trend, x='date', y='reading', title="Electricity Reading Trend (kWh)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Additional data required for trend rendering.")
                    
            with trend_col2:
                hw_trend = chart_df[chart_df['meter'] == "Hot Water (MWh)"]
                if len(hw_trend) > 1:
                    fig = px.line(hw_trend, x='date', y='reading', title="Hot Water Reading Trend (MWh)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Additional data required for trend rendering.")
                    
            with trend_col3:
                cw_trend = chart_df[chart_df['meter'] == "Cold Water (m³)"]
                if len(cw_trend) > 1:
                    fig = px.line(cw_trend, x='date', y='reading', title="Cold Water Reading Trend (m³)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.caption("Additional data required for trend rendering.")

# --- PAGE 2: LOG CONSUMPTION ---
elif page == "Log Consumption":
    st.title("Log Utility Readings")
    st.write("Enter cumulative physical readings below.")
    
    with st.form("log_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            log_date = st.date_input("Date of Reading", datetime.date.today())
            meter_type = st.selectbox(
                "Select Utility Meter",
                ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
            )
            
        with col2:
            last_entry = logs[logs['meter'] == meter_type]
            if not last_entry.empty:
                last_val = last_entry.iloc[-1]['reading']
                last_dt = last_entry.iloc[-1]['date']
                st.info(f"Last recorded reading: **{last_val}** on {last_dt}")
            else:
                st.info("No logs present for this meter. This input will establish your base reading.")
                
            reading_val = st.number_input(
                "Cumulative Reading Value", 
                min_value=0.0, 
                step=0.001, 
                format="%.3f"
            )
            
        submitted = st.form_submit_button("Submit Reading")
        
        if submitted:
            if not last_entry.empty and reading_val < last_val:
                st.warning(f"Note: Entered reading ({reading_val}) is lower than the last recorded reading ({last_val}).")
            
            execute_db("""
                INSERT INTO logs (date, meter, reading) 
                VALUES (:date, :meter, :reading)
            """, params={
                "date": log_date.strftime("%Y-%m-%d"),
                "meter": meter_type,
                "reading": reading_val
            })
                
            st.success(f"Successfully saved {reading_val} for {meter_type}.")
            st.rerun()

# --- PAGE 3: COST SETTINGS ---
elif page == "Cost Settings":
    st.title("Update Tariffs (Mannheim)")
    st.write("Adjust your local provider tariffs. Defaults are configured for MVV Mannheim averages.")
    
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            elec_rate = st.number_input(
                "Electricity Tariff (€ / kWh)", 
                value=float(rates.get("electricity_kwh", 0.282)), 
                step=0.001, 
                format="%.4f"
            )
            elec_base = st.number_input(
                "Electricity Base Price (€ / month)", 
                value=float(rates.get("electricity_base", 16.80)), 
                step=0.10, 
                format="%.2f"
            )
            
        with col2:
            hw_rate = st.number_input(
                "District Heating / Warm Water Tarif (€ / MWh)", 
                value=float(rates.get("hot_water_mwh", 95.00)), 
                step=0.50, 
                format="%.2f"
            )
            cw_rate = st.number_input(
                "Cold Water + Sewage Tarif (€ / m³)", 
                value=float(rates.get("cold_water_m3", 4.50)), 
                step=0.10, 
                format="%.2f"
            )
            
        saved = st.form_submit_button("Update Rates")
        
        if saved:
            new_rates = {
                "electricity_kwh": elec_rate,
                "electricity_base": elec_base,
                "hot_water_mwh": hw_rate,
                "cold_water_m3": cw_rate
            }
            save_rates(new_rates)
            st.success("Tariff rates successfully saved.")
            st.rerun()

# --- PAGE 4: MANAGE HISTORY ---
elif page == "Manage History":
    st.title("Manage Data History")
    
    if logs.empty:
        st.info("No recorded database entries found.")
    else:
        st.subheader("Saved Log Entries")
        st.dataframe(logs, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Delete Log Entry")
        
        delete_id = st.number_input(
            "Enter Entry 'id' to remove", 
            min_value=int(logs['id'].min()), 
            max_value=int(logs['id'].max()), 
            step=1
        )
        
        confirm_delete = st.button("Delete Entry", type="primary")
            
        if confirm_delete:
            execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(delete_id)})
            st.success(f"Record with ID {delete_id} deleted successfully.")
            st.rerun()