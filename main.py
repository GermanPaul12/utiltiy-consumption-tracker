# main.py
import streamlit as st
from dotenv import load_dotenv

# 1. Load environment variables FIRST to avoid import initialization errors
load_dotenv()

# 2. Import your module logic layers
from utils import database as db
from utils import auth
from utils import metrics
from utils import styles

# 3. Import your UI Page Renderers
from ui import ui_dashboard
from ui import ui_log_consumption
from ui import ui_profile
from ui import ui_manage_history
from ui import ui_devices

# Cookie-Controller für persistentes Login
from streamlit_cookies_controller import CookieController

# Set Page Config
st.set_page_config(
    page_title="Utility Tracker - Mannheim",
    page_icon="⚡",
    layout="wide"
)

# Database Connection Check
db_connection_ok, connection_error_detail = db.check_db_connection()

if not db_connection_ok:
    st.error("### 🔌 Database Connection Failed")
    st.write("The application could not authenticate with your database. Please check your configuration.")
    with st.expander("Show system error logs"):
        st.code(connection_error_detail)
    st.stop()

# Initialize Database Schema
db.initialize_database()

# Theme setup
if "theme_preference" not in st.session_state:
    st.session_state.theme_preference = "🌙 Dark Mode"

styles.inject_theme(st.session_state.theme_preference)

# --- COOKIE-BASED SESSION RESTORATION ---
cookie_controller = CookieController()

if "user" not in st.session_state:
    st.session_state.user = None

# Auto-Login-Versuch ausführen, falls kein User in der Session ist
if st.session_state.user is None:
    try:
        saved_session = cookie_controller.get("supabase_session")
        if saved_session and isinstance(saved_session, dict):
            # Session in Supabase wiederherstellen
            res = auth.supabase.auth.set_session(
                saved_session["access_token"], 
                saved_session["refresh_token"]
            )
            if res.user:
                st.session_state.user = {
                    "id": res.user.id,
                    "email": res.user.email
                }
    except Exception:
        pass # Ignoriere Fehler bei fehlenden/ungültigen Cookies

# --- AUTH PORTAL ---
if st.session_state.user is None:
    col_l, col_m, col_r = st.columns([1, 2, 1])
    with col_m:
        st.write("")
        st.write("")
        st.title("⚡ Utility Consumption Tracker")
        st.write("Register an account or sign in to track your personal utility usage securely.")
        
        auth_mode = st.radio("Choose Action", ["Sign In", "Register Account", "Forgot Password"])
        
        if auth_mode == "Forgot Password":
            with st.form("forgot_password_form"):
                reset_email = st.text_input("Enter your Email address").strip()
                submitted = st.form_submit_button("Send Reset Link")
                
                if submitted:
                    if reset_email:
                        try:
                            auth.supabase.auth.reset_password_for_email(reset_email)
                            st.success("A password reset link has been sent to your email inbox.")
                        except Exception as e:
                            st.error(f"Failed to send link: {e}")
                    else:
                        st.error("Please enter a valid email address.")
        else:
            with st.form("auth_form"):
                email_input = st.text_input("Email").strip()
                password_input = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Proceed")
                
                if submitted:
                    if auth_mode == "Register Account":
                        success, message = auth.register_user(email_input, password_input)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        user_data = auth.authenticate_user(email_input, password_input)
                        if user_data:
                            st.session_state.user = {
                                "id": user_data["id"],
                                "email": user_data["email"]
                            }
                            # Session dauerhaft im Browser-Cookie sichern (Gültigkeit z.B. 30 Tage)
                            cookie_controller.set("supabase_session", {
                                "access_token": user_data["access_token"],
                                "refresh_token": user_data["refresh_token"]
                            })
                            st.rerun()
                        else:
                            st.error("Invalid email or password.")
    st.stop()

# User Session Active
current_user_id = st.session_state.user["id"]
current_username = st.session_state.user["email"]

# Print the UUID to your terminal console for debugging (Console Only)
print(f"\n--- DEBUG: Current Logged-In User UUID: {current_user_id} ---\n", flush=True)

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("Utility Tracker")
st.sidebar.write(f"Logged in as: **{current_username}**")

st.session_state.theme_preference = st.sidebar.selectbox(
    "Choose Theme Style",
    ["🌙 Dark Mode", "☀️ Light Mode"]
)

styles.inject_theme(st.session_state.theme_preference)
plotly_template = "plotly_dark" if st.session_state.theme_preference == "🌙 Dark Mode" else "plotly_white"

if st.sidebar.button("Logout"):
    # Cookies und Session State beim Logout leeren
    try:
        cookie_controller.remove("supabase_session")
        auth.supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.user = None
    st.rerun()

st.sidebar.caption("Mannheim (68163) Tariffs")
if db.DATABASE_URL:
    st.sidebar.success("CONNECTED TO CLOUD DB")
else:
    st.sidebar.warning("RUNNING LOCALLY (SQLITE)")

page = st.sidebar.radio(
    "Go to",
    ["Dashboard Overview", "Log Consumption", "Device Analysis", "Profile & Tariff Settings", "Manage History"]
)

# --- ZENTRALISIERTES CACHING ÜBER SESSION STATE ---
if "rates" not in st.session_state:
    st.session_state.rates = db.load_rates(current_user_id)

if "logs" not in st.session_state:
    st.session_state.logs = db.load_logs(current_user_id)

if "smart_logs" not in st.session_state:
    st.session_state.smart_logs = db.load_smart_device_logs(current_user_id)

# Wir cachen auch die statische Geräteliste, um DB-Queries auf den Unterseiten einzusparen
if "devices" not in st.session_state:
    st.session_state.devices = db.load_devices(current_user_id)

# Berechnungen der Metriken im RAM zwischenspeichern
if "processed_logs" not in st.session_state or "stats" not in st.session_state:
    processed_logs, stats = metrics.calculate_metrics(st.session_state.logs, st.session_state.rates)
    st.session_state.processed_logs = processed_logs
    st.session_state.stats = stats

# Lokale Variablen aus dem Session State zuweisen
rates = st.session_state.rates
logs = st.session_state.logs
smart_logs = st.session_state.smart_logs
processed_logs = st.session_state.processed_logs
stats = st.session_state.stats

# --- ROUTER DISPATCHER ---
if page == "Dashboard Overview":
    ui_dashboard.render_page(processed_logs, stats, rates, plotly_template, smart_logs)

elif page == "Log Consumption":
    ui_log_consumption.render_page(current_user_id, logs)

elif page == "Device Analysis":
    ui_devices.render_page(current_user_id, stats, rates)

elif page == "Profile & Tariff Settings":
    ui_profile.render_page(current_user_id, rates)

elif page == "Manage History":
    ui_manage_history.render_page(current_user_id, logs)