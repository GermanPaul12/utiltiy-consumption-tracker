# main.py
import datetime
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

# 1. Load environment variables FIRST to avoid import initialization errors
load_dotenv()

# 2. Import your custom modules
import database as db
import auth
import metrics
import styles

# Set Page Config
st.set_page_config(
    page_title="Utility Tracker - Mannheim",
    page_icon="⚡",
    layout="wide"
)

# 3. Database Connection Check
db_connection_ok, connection_error_detail = db.check_db_connection()

if not db_connection_ok:
    st.error("### 🔌 Database Connection Failed")
    st.write("The application could not authenticate with your database. Please check your configuration.")
    st.info("""
    **Troubleshooting Checklist for your `.env` file:**
    1. **Format Check:** Ensure your `DATABASE_URL` is written without brackets.
    2. **Password Verification:** Make sure the password is your actual **Supabase Database Password**.
    """)
    with st.expander("Show system error logs"):
        st.code(connection_error_detail)
    st.stop()

# Initialize Database Schema
db.initialize_database()

# Theme setup
if "theme_preference" not in st.session_state:
    st.session_state.theme_preference = "🌙 Dark Mode"

styles.inject_theme(st.session_state.theme_preference)

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
        
        auth_mode = st.radio("Choose Action", ["Sign In", "Register Account", "Forgot Password"])
        
        if auth_mode == "Forgot Password":
            with st.form("forgot_password_form"):
                reset_email = st.text_input("Enter your Email address").strip()
                submitted = st.form_submit_button("Send Reset Link")
                
                if submitted:
                    if reset_email:
                        try:
                            # Triggers Supabase recovery email
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
                        user = auth.authenticate_user(email_input, password_input)
                        if user:
                            st.session_state.user = user
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
    st.session_state.user = None
    st.rerun()

st.sidebar.caption("Mannheim (68163) Tariffs")
if db.DATABASE_URL:
    st.sidebar.success("CONNECTED TO CLOUD DB")
else:
    st.sidebar.warning("RUNNING LOCALLY (SQLITE)")

page = st.sidebar.radio(
    "Go to",
    ["Dashboard Overview", "Log Consumption", "Profile & Tariff Settings", "Manage History"]
)

# Load State for Current Logged In User
rates = db.load_rates(current_user_id)
logs = db.load_logs(current_user_id)
processed_logs, stats = metrics.calculate_metrics(logs, rates)

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
        
        st.subheader("Global Estimates & Projections")
        g_col1, g_col2, g_col3, g_col4 = st.columns(4)
        g_col1.metric("Total Cumulative Expenses", f"€{total_cost_all:,.2f}")
        g_col2.metric("Average Monthly Cost", f"€{avg_monthly_cost_all:,.2f}")
        g_col3.metric("Projected Annual Cost", f"€{projected_annual_cost:,.2f}")
        g_col4.metric("Total CO₂ Footprint", f"{total_co2_all:,.1f} kg")
        
        st.markdown("---")
        
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
            
            db.execute_db("""
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
            db.save_rates(current_user_id, new_rates)
            st.success("Profile and tariffs successfully updated.")
            st.rerun()

    # --- Change Password Section (Supabase Integrated) ---
    st.markdown("---")
    st.subheader("🔑 Change Password")
    st.write("If you logged in via a password reset link, you can set your new password here:")
    
    with st.form("change_password_form"):
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        password_submitted = st.form_submit_button("Update Password")
        
        if password_submitted:
            if not new_password or not confirm_password:
                st.error("Password fields cannot be empty.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    auth.supabase.auth.update_user({"password": new_password})
                    st.success("Your password has been successfully updated.")
                except Exception as e:
                    st.error(f"Failed to update password: {e}")

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
            target_row = db.run_query("SELECT user_id FROM logs WHERE id = :id", {"id": int(delete_id)})
            if not target_row.empty and str(target_row.iloc[0]['user_id']) == str(current_user_id):
                db.execute_db("DELETE FROM logs WHERE id = :id", params={"id": int(delete_id)})
                st.success(f"Record with ID {delete_id} deleted successfully.")
                st.rerun()
            else:
                st.error("Invalid entry ID or permission denied.")