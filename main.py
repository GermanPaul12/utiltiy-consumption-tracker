import os
import hashlib
import datetime
import pandas as pd
import ssl
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Set Page Config
st.set_page_config(
    page_title="Utility Tracker - Mannheim",
    page_icon="⚡",
    layout="wide"
)

# 1. Establish Database Connection Engine with Auto-Cleanup & SSL Context
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Convert dialect for SQLAlchemy 2.0 & pg8000 compatibility
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)
    
    # pg8000 does not support standard PG query string parameters (like ?sslmode=require).
    # We strip them here since we handle SSL securely via connect_args below.
    if "?" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?")[0]
        
    db_url = DATABASE_URL
    
    # Create a secure default SSL Context for pg8000
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    engine = create_engine(
        db_url, 
        connect_args={"ssl_context": ssl_ctx},
        pool_pre_ping=True
    )
else:
    db_url = "sqlite:///utility_tracker.db"
    engine = create_engine(db_url)

# --- PRE-FLIGHT DATABASE CONNECTION CHECK ---
# Prevents raw python crash screens by displaying troubleshooting steps inside Streamlit
db_connection_ok = True
connection_error_detail = ""

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    db_connection_ok = False
    connection_error_detail = str(e)

if not db_connection_ok:
    st.error("### 🔌 Database Connection Failed")
    st.write("The application could not authenticate with your database. Please check your configuration.")
    
    st.info("""
    **Troubleshooting Checklist for your `.env` file:**
    
    1. **Format Check:** Ensure your `DATABASE_URL` is written without brackets:
       ```text
       DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.reqassdcxcsvrxalmmsh.supabase.co:5432/postgres
       ```
    2. **Password Verification:** Make sure the password is your actual **Supabase Database Password**, not your website login account password.
    3. **Special Characters:** If your password contains special characters, they must be URL-encoded:
       * `@` becomes `%40`
       * `:` becomes `%3A`
       * `#` becomes `%23`
       * `/` becomes `%2F`
    """)
    with st.expander("Show system error logs"):
        st.code(connection_error_detail)
    st.stop()


# Helper function to run SELECT queries
def run_query(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

# Helper function to execute transactions
def execute_db(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

# Cryptographically secure password hashing (PBKDF2)
def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        bytes.fromhex(salt), 
        100000
    ).hex()
    return pw_hash, salt

def verify_password(stored_hash, stored_salt, password_to_test):
    test_hash, _ = hash_password(password_to_test, stored_salt)
    return test_hash == stored_hash

# 2. Database Schema Initialization & Safe Migration
def initialize_database():
    is_sqlite = engine.dialect.name == 'sqlite'
    
    # Create users table
    if is_sqlite:
        execute_db("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, salt TEXT)")
        execute_db("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, meter TEXT, reading REAL)")
    else:
        execute_db("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(100) UNIQUE, password_hash TEXT, salt TEXT)")
        execute_db("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, user_id INTEGER, date DATE, meter VARCHAR(100), reading DOUBLE PRECISION)")

    # Check and Migrate 'rates' table
    try:
        df_rates_check = run_query("SELECT * FROM rates LIMIT 1")
        if not df_rates_check.empty and "user_id" not in df_rates_check.columns:
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE rates"))
            st.info("Upgrading database structures...")
    except Exception:
        pass

    # Create rates table
    if is_sqlite:
        execute_db("CREATE TABLE IF NOT EXISTS rates (user_id INTEGER PRIMARY KEY, electricity_kwh REAL, electricity_base REAL, hot_water_mwh REAL, cold_water_m3 REAL, electricity_prepayment REAL, hot_water_prepayment REAL, cold_water_prepayment REAL, household_size INTEGER DEFAULT 1, apartment_size REAL DEFAULT 50.0)")
    else:
        execute_db("CREATE TABLE IF NOT EXISTS rates (user_id INTEGER PRIMARY KEY, electricity_kwh DOUBLE PRECISION, electricity_base DOUBLE PRECISION, hot_water_mwh DOUBLE PRECISION, cold_water_m3 DOUBLE PRECISION, electricity_prepayment DOUBLE PRECISION, hot_water_prepayment DOUBLE PRECISION, cold_water_prepayment DOUBLE PRECISION, household_size INTEGER DEFAULT 1, apartment_size DOUBLE PRECISION DEFAULT 50.0)")

    # Run Migrations for missing columns
    df_rates_check = run_query("SELECT * FROM rates LIMIT 1")
    if "household_size" not in df_rates_check.columns:
        with engine.begin() as conn:
            if is_sqlite:
                conn.execute(text("ALTER TABLE rates ADD COLUMN household_size INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE rates ADD COLUMN apartment_size REAL DEFAULT 50.0"))
            else:
                conn.execute(text("ALTER TABLE rates ADD COLUMN household_size INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE rates ADD COLUMN apartment_size DOUBLE PRECISION DEFAULT 50.0"))

    # Migration check for 'logs' table
    try:
        df_logs_check = run_query("SELECT * FROM logs LIMIT 1")
        if "user_id" not in df_logs_check.columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE logs ADD COLUMN user_id INTEGER DEFAULT 1"))
    except Exception:
        pass

initialize_database()

# Authentication Helpers
def register_user(username, password):
    username_clean = username.strip().lower()
    if not username_clean or not password:
        return False, "Username and password cannot be empty."
        
    existing = run_query("SELECT id FROM users WHERE username = :username", {"username": username_clean})
    if not existing.empty:
        return False, "Username already exists."
        
    password_hash, salt = hash_password(password)
    
    execute_db("""
        INSERT INTO users (username, password_hash, salt) 
        VALUES (:username, :hash, :salt)
    """, {"username": username_clean, "hash": password_hash, "salt": salt})
    
    user_row = run_query("SELECT id FROM users WHERE username = :username", {"username": username_clean})
    new_uid = int(user_row.iloc[0]['id'])
    
    execute_db("""
        INSERT INTO rates (user_id, electricity_kwh, electricity_base, hot_water_mwh, cold_water_m3, 
                           electricity_prepayment, hot_water_prepayment, cold_water_prepayment,
                           household_size, apartment_size)
        VALUES (:uid, 0.282, 16.80, 95.00, 4.50, 0.0, 0.0, 0.0, 1, 50.0)
    """, {"uid": new_uid})
    
    return True, "Registration successful. You can now log in."

def authenticate_user(username, password):
    username_clean = username.strip().lower()
    user_row = run_query("SELECT id, password_hash, salt FROM users WHERE username = :username", {"username": username_clean})
    if user_row.empty:
        return None
        
    stored_hash = user_row.iloc[0]['password_hash']
    stored_salt = user_row.iloc[0]['salt']
    user_id = int(user_row.iloc[0]['id'])
    
    if verify_password(stored_hash, stored_salt, password):
        return {"id": user_id, "username": username_clean}
    return None

# User-Scoped Data Helpers
def load_rates(user_id):
    df = run_query("SELECT * FROM rates WHERE user_id = :uid", {"uid": user_id})
    if df.empty:
        execute_db("""
            INSERT INTO rates (user_id, electricity_kwh, electricity_base, hot_water_mwh, cold_water_m3, 
                               electricity_prepayment, hot_water_prepayment, cold_water_prepayment,
                               household_size, apartment_size)
            VALUES (:uid, 0.282, 16.80, 95.00, 4.50, 0.0, 0.0, 0.0, 1, 50.0)
        """, {"uid": user_id})
        df = run_query("SELECT * FROM rates WHERE user_id = :uid", {"uid": user_id})
    return df.iloc[0].to_dict()

def save_rates(user_id, rates_dict):
    execute_db("""
        UPDATE rates 
        SET electricity_kwh = :elec_kwh, 
            electricity_base = :elec_base, 
            hot_water_mwh = :hw_mwh, 
            cold_water_m3 = :cw_m3,
            electricity_prepayment = :elec_prep,
            hot_water_prepayment = :hw_prep,
            cold_water_prepayment = :cw_prep,
            household_size = :house_size,
            apartment_size = :apt_size
        WHERE user_id = :uid
    """, params={
        "uid": user_id,
        "elec_kwh": rates_dict["electricity_kwh"],
        "elec_base": rates_dict["electricity_base"],
        "hw_mwh": rates_dict["hot_water_mwh"],
        "cw_m3": rates_dict["cold_water_m3"],
        "elec_prep": rates_dict["electricity_prepayment"],
        "hw_prep": rates_dict["hot_water_prepayment"],
        "cw_prep": rates_dict["cold_water_prepayment"],
        "house_size": int(rates_dict["household_size"]),
        "apt_size": float(rates_dict["apartment_size"])
    })

def load_logs(user_id):
    df = run_query("SELECT * FROM logs WHERE user_id = :uid ORDER BY date ASC", {"uid": user_id})
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

# Metrics Calculation
def calculate_metrics(logs_df, rates):
    if logs_df.empty:
        return pd.DataFrame(), {}

    meters_meta = {
        "Electricity (kWh)": {"rate_key": "electricity_kwh", "prep_key": "electricity_prepayment", "co2_factor": 0.380, "unit": "kWh"},
        "Hot Water (MWh)": {"rate_key": "hot_water_mwh", "prep_key": "hot_water_prepayment", "co2_factor": 90.0, "unit": "MWh"},
        "Cold Water (m³)": {"rate_key": "cold_water_m3", "prep_key": "cold_water_prepayment", "co2_factor": 0.35, "unit": "m³"}
    }
    
    processed_dfs = []
    summary_stats = {}
    
    for meter_name, meta in meters_meta.items():
        meter_df = logs_df[logs_df['meter'] == meter_name].copy()
        if meter_df.empty:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        
        meter_df['days_elapsed'] = meter_df['date'].diff().apply(lambda x: x.days if pd.notnull(x) else 0)
        meter_df['consumption'] = meter_df['reading'].diff().fillna(0)
        
        meter_df['daily_rate'] = meter_df.apply(
            lambda row: row['consumption'] / row['days_elapsed'] if row['days_elapsed'] > 0 else 0,
            axis=1
        )
        
        unit_rate = rates[meta["rate_key"]]
        monthly_prepayment = rates.get(meta["prep_key"], 0.0)
        
        meter_df['cost'] = meter_df['consumption'] * unit_rate
        meter_df['daily_cost_rate'] = meter_df['daily_rate'] * unit_rate
        meter_df['cumulative_cost'] = meter_df['cost'].cumsum()
        meter_df['co2_emissions'] = meter_df['consumption'] * meta["co2_factor"]
        
        processed_dfs.append(meter_df)
        
        entries_count = len(meter_df)
        if entries_count > 1:
            first_date = meter_df['date'].iloc[0]
            last_date = meter_df['date'].iloc[-1]
            total_days = (last_date - first_date).days
            total_days = max(total_days, 1)
            
            total_consumption = meter_df['reading'].iloc[-1] - meter_df['reading'].iloc[0]
            avg_daily_consumption = total_consumption / total_days
            avg_daily_cost = avg_daily_consumption * unit_rate
            total_co2 = total_consumption * meta["co2_factor"]
            
            if meter_name == "Electricity (kWh)":
                daily_base = rates["electricity_base"] / 30.44
                avg_daily_cost += daily_base
                total_base_cost = (total_days / 30.44) * rates["electricity_base"]
                total_cost = (total_consumption * unit_rate) + total_base_cost
            else:
                total_cost = total_consumption * unit_rate
                
            avg_monthly_consumption = avg_daily_consumption * 30.44
            avg_monthly_cost = avg_daily_cost * 30.44
            
            elapsed_months = total_days / 30.44
            prepayment_paid_to_date = monthly_prepayment * elapsed_months
            standing_to_date = prepayment_paid_to_date - total_cost
            
            annual_prepayment = monthly_prepayment * 12
            projected_annual_cost = avg_daily_cost * 365.25
            projected_annual_standing = annual_prepayment - projected_annual_cost
            
            max_period = meter_df[meter_df['days_elapsed'] > 0]
            peak_daily_rate = max_period['daily_rate'].max() if not max_period.empty else 0.0
            
            summary_stats[meter_name] = {
                "unit": meta["unit"],
                "entries_count": entries_count,
                "first_date": first_date,
                "last_date": last_date,
                "days_since_last": (datetime.date.today() - last_date).days,
                "total_days": total_days,
                "total_consumption": total_consumption,
                "total_cost": total_cost,
                "total_co2": total_co2,
                "monthly_prepayment": monthly_prepayment,
                "prepayment_paid_to_date": prepayment_paid_to_date,
                "standing_to_date": standing_to_date,
                "projected_annual_cost": projected_annual_cost,
                "annual_prepayment": annual_prepayment,
                "projected_annual_standing": projected_annual_standing,
                "avg_daily_consumption": avg_daily_consumption,
                "avg_daily_cost": avg_daily_cost,
                "avg_monthly_consumption": avg_monthly_consumption,
                "avg_monthly_cost": avg_monthly_cost,
                "peak_daily_rate": peak_daily_rate,
                "last_reading": meter_df['reading'].iloc[-1]
            }
        else:
            summary_stats[meter_name] = {
                "unit": meta["unit"],
                "entries_count": entries_count,
                "last_reading": meter_df['reading'].iloc[-1],
                "last_date": meter_df['date'].iloc[-1],
                "days_since_last": (datetime.date.today() - meter_df['date'].iloc[-1]).days,
                "total_consumption": 0.0,
                "total_cost": 0.0,
                "total_co2": 0.0,
                "monthly_prepayment": monthly_prepayment,
                "prepayment_paid_to_date": 0.0,
                "standing_to_date": 0.0,
                "projected_annual_cost": 0.0,
                "annual_prepayment": monthly_prepayment * 12,
                "projected_annual_standing": 0.0,
                "avg_daily_consumption": 0.0,
                "avg_daily_cost": 0.0,
                "avg_monthly_consumption": 0.0,
                "avg_monthly_cost": 0.0,
                "peak_daily_rate": 0.0
            }
        
    if not processed_dfs:
        return pd.DataFrame(), {}
        
    combined_df = pd.concat(processed_dfs).sort_values(by='date')
    return combined_df, summary_stats

# --- THEME STYLING ENGINE ---
if "theme_preference" not in st.session_state:
    st.session_state.theme_preference = "🌙 Dark Mode"

def inject_theme(theme_mode):
    if theme_mode == "🌙 Dark Mode":
        css = """
        <style>
            .stApp {
                background-color: #0f172a !important;
                color: #f1f5f9 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #1e293b !important;
                border-right: 1px solid #334155;
            }
            div[data-testid="metric-container"] {
                background-color: #1e293b !important;
                border: 1px solid #334155 !important;
                padding: 18px !important;
                border-radius: 12px !important;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25) !important;
            }
            div[data-testid="stMetricLabel"] {
                color: #94a3b8 !important;
                font-size: 0.95rem !important;
                font-weight: 500 !important;
            }
            div[data-testid="stMetricValue"] {
                color: #38bdf8 !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #f8fafc !important;
                font-family: 'Inter', sans-serif !important;
            }
            button[data-baseweb="tab"] {
                color: #94a3b8 !important;
            }
            button[aria-selected="true"] {
                color: #38bdf8 !important;
                border-bottom-color: #38bdf8 !important;
            }
            div[data-testid="stForm"] {
                border: 1px solid #334155 !important;
                border-radius: 12px !important;
                background-color: #1e293b !important;
            }
        </style>
        """
    else: # ☀️ Light Mode
        css = """
        <style>
            .stApp {
                background-color: #f8fafc !important;
                color: #0f172a !important;
            }
            [data-testid="stSidebar"] {
                background-color: #ffffff !important;
                border-right: 1px solid #e2e8f0;
            }
            div[data-testid="metric-container"] {
                background-color: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                padding: 18px !important;
                border-radius: 12px !important;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04) !important;
            }
            div[data-testid="stMetricLabel"] {
                color: #64748b !important;
                font-size: 0.95rem !important;
                font-weight: 500 !important;
            }
            div[data-testid="stMetricValue"] {
                color: #0284c7 !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #0f172a !important;
                font-family: 'Inter', sans-serif !important;
            }
            button[data-baseweb="tab"] {
                color: #64748b !important;
            }
            button[aria-selected="true"] {
                color: #0284c7 !important;
                border-bottom-color: #0284c7 !important;
            }
            div[data-testid="stForm"] {
                border: 1px solid #e2e8f0 !important;
                border-radius: 12px !important;
                background-color: #ffffff !important;
            }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)

# Run Style Engine on start
inject_theme(st.session_state.theme_preference)

# --- SESSION STATE & AUTH PORTAL ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.write("")
        st.write("")
        st.title("⚡ Utility Consumption Tracker")
        st.write("Register an account or sign in to track your personal utility usage securely.")
        
        auth_mode = st.radio("Choose Action", ["Sign In", "Register Account"])
        
        with st.form("auth_form"):
            username_input = st.text_input("Username").strip()
            password_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Proceed")
            
            if submitted:
                if auth_mode == "Register Account":
                    success, message = register_user(username_input, password_input)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    user = authenticate_user(username_input, password_input)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
    st.stop()

# User Session Active
current_user_id = st.session_state.user["id"]
current_username = st.session_state.user["username"]

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("Utility Tracker")
st.sidebar.write(f"Logged in as: **{current_username}**")

# Theme Switcher
st.session_state.theme_preference = st.sidebar.selectbox(
    "Choose Theme Style",
    ["🌙 Dark Mode", "☀️ Light Mode"]
)

# Apply selected theme
inject_theme(st.session_state.theme_preference)
plotly_template = "plotly_dark" if st.session_state.theme_preference == "🌙 Dark Mode" else "plotly_white"

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

st.sidebar.caption("Mannheim (68163) Tariffs")
if DATABASE_URL:
    st.sidebar.success("CONNECTED TO CLOUD DB")
else:
    st.sidebar.warning("RUNNING LOCALLY (SQLITE)")

page = st.sidebar.radio(
    "Go to",
    ["Dashboard Overview", "Log Consumption", "Profile & Tariff Settings", "Manage History"]
)

# Load State for Current Logged In User
rates = load_rates(current_user_id)
logs = load_logs(current_user_id)
processed_logs, stats = calculate_metrics(logs, rates)

# --- PAGE 1: DASHBOARD OVERVIEW ---
if page == "Dashboard Overview":
    st.title("Utility Consumption Dashboard")
    
    if processed_logs.empty:
        st.info("Your database history is currently empty. Go to 'Log Consumption' to record your initial readings.")
    else:
        total_cost_all = sum(m.get("total_cost", 0.0) for m in stats.values())
        avg_monthly_cost_all = sum(m.get("avg_monthly_cost", 0.0) for m in stats.values())
        avg_daily_cost_all = sum(m.get("avg_daily_cost", 0.0) for m in stats.values())
        projected_annual_cost = avg_daily_cost_all * 365.25
        total_co2_all = sum(m.get("total_co2", 0.0) for m in stats.values())
        
        total_prepayments_to_date = sum(m.get("prepayment_paid_to_date", 0.0) for m in stats.values())
        global_standing_to_date = total_prepayments_to_date - total_cost_all
        
        total_annual_prepayments = sum(m.get("annual_prepayment", 0.0) for m in stats.values())
        global_projected_annual_standing = total_annual_prepayments - projected_annual_cost
        
        st.caption("ℹ️ Note: Baseline calculations require at least two sequential readings per meter.")
        
        # 1. Global Metrics Header
        st.subheader("Global Estimates & Projections")
        g_col1, g_col2, g_col3, g_col4 = st.columns(4)
        g_col1.metric("Total Cumulative Expenses", f"€{total_cost_all:,.2f}")
        g_col2.metric("Average Monthly Cost", f"€{avg_monthly_cost_all:,.2f}")
        g_col3.metric("Projected Annual Cost", f"€{projected_annual_cost:,.2f}")
        g_col4.metric("Total CO₂ Footprint", f"{total_co2_all:,.1f} kg")
        
        st.markdown("---")
        
        # 2. Financial Balance Section
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

        # 3. Personalized German Household Benchmarking
        st.subheader("Personalized German Benchmark Comparison")
        st.write(f"Evaluating benchmarks using your profile: **{rates['household_size']} Person(s)** living in a **{rates['apartment_size']:.1f} m²** apartment.")
        b_col1, b_col2, b_col3 = st.columns(3)
        
        with b_col1:
            st.markdown("**⚡ Electricity (Annual)**")
            elec_ann = stats.get("Electricity (kWh)", {}).get("avg_daily_consumption", 0.0) * 365.25
            if elec_ann > 0:
                # Dynamic VDE Formula
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
                # co2online formula for average German flats (130 kWh per m2 per year)
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
                # German water agency benchmark (125 Liters per person per day)
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
        
        # 4. Detailed Utility Tabs
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
        
        # 5. Dynamic Visualizations
        st.subheader("Historical Timeline Graphs")
        has_sufficient_data = any(m.get("entries_count", 0) > 1 for m in stats.values())
        
        if not has_sufficient_data:
            st.info("Visual charts require at least two logged points to show historical progression.")
        else:
            fig_cum = px.line(
                processed_logs[processed_logs['cumulative_cost'] > 0],
                x='date',
                y='cumulative_cost',
                color='meter',
                markers=True,
                title="Cumulative Spent Over Time (€)",
                labels={"cumulative_cost": "Total Spent (€)", "date": "Date"},
                template=plotly_template
            )
            st.plotly_chart(fig_cum, use_container_width=True)
            
            active_intervals = processed_logs[processed_logs['days_elapsed'] > 0]
            if not active_intervals.empty:
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
                    template=plotly_template
                )
                fig_rate.update_yaxes(matches=None)
                st.plotly_chart(fig_rate, use_container_width=True)

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
                INSERT INTO logs (user_id, date, meter, reading) 
                VALUES (:uid, :date, :meter, :reading)
            """, params={
                "uid": current_user_id,
                "date": log_date.strftime("%Y-%m-%d"),
                "meter": meter_type,
                "reading": reading_val
            })
                
            st.success(f"Successfully saved {reading_val} for {meter_type}.")
            st.rerun()

# --- PAGE 3: PROFILE & TARIFF SETTINGS ---
elif page == "Profile & Tariff Settings":
    st.title("Update Profile, Tariffs & Prepayments")
    st.write("Configure your domestic household size, tariffs, and monthly prepayment plans (*Abschlagszahlungen*) below.")
    
    with st.form("settings_form"):
        # Household Specifications
        st.subheader("🏠 Household & Apartment Profile")
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            h_size = st.number_input(
                "Household Size (Number of occupants)",
                min_value=1,
                max_value=15,
                value=int(rates.get("household_size", 1)),
                step=1
            )
        with p_col2:
            a_size = st.number_input(
                "Apartment Size (Square Meters - m²)",
                min_value=5.0,
                max_value=1000.0,
                value=float(rates.get("apartment_size", 50.0)),
                step=0.5,
                format="%.1f"
            )
            
        st.markdown("---")
        
        # Tariffs & Prepayments
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("⚡ Electricity Settings")
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
            elec_prep = st.number_input(
                "Monthly Electricity Prepayment (€ / month)",
                value=float(rates.get("electricity_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
        with col2:
            st.subheader("🔥 District Heating / Hot Water")
            hw_rate = st.number_input(
                "District Heating Tarif (€ / MWh)", 
                value=float(rates.get("hot_water_mwh", 95.00)), 
                step=0.50, 
                format="%.2f"
            )
            hw_prep = st.number_input(
                "Monthly District Heating Prepayment (€ / month)",
                value=float(rates.get("hot_water_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
            st.subheader("💧 Cold Water Settings")
            cw_rate = st.number_input(
                "Cold Water + Sewage Tarif (€ / m³)", 
                value=float(rates.get("cold_water_m3", 4.50)), 
                step=0.10, 
                format="%.2f"
            )
            cw_prep = st.number_input(
                "Monthly Cold Water Prepayment (€ / month)",
                value=float(rates.get("cold_water_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
        saved = st.form_submit_button("Update Profile & Tariffs")
        
        if saved:
            new_rates = {
                "electricity_kwh": elec_rate,
                "electricity_base": elec_base,
                "electricity_prepayment": elec_prep,
                "hot_water_mwh": hw_rate,
                "hot_water_prepayment": hw_prep,
                "cold_water_m3": cw_rate,
                "cold_water_prepayment": cw_prep,
                "household_size": h_size,
                "apartment_size": a_size
            }
            save_rates(current_user_id, new_rates)
            st.success("Profile and tariffs successfully updated.")
            st.rerun()

# --- PAGE 4: MANAGE HISTORY ---
elif page == "Manage History":
    st.title("Manage Data History")
    
    if logs.empty:
        st.info("No recorded database entries found.")
    else:
        st.subheader("Saved Log Entries")
        st.dataframe(logs.drop(columns=["user_id"], errors="ignore"), use_container_width=True)
        
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
            target_row = run_query("SELECT user_id FROM logs WHERE id = :id", {"id": int(delete_id)})
            if not target_row.empty and int(target_row.iloc[0]['user_id']) == current_user_id:
                execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(delete_id)})
                st.success(f"Record with ID {delete_id} deleted successfully.")
                st.rerun()
            else:
                st.error("Invalid entry ID or permission denied.")