# ui_log_consumption.py
import datetime
import streamlit as st
import database as db

def render_page(current_user_id, logs):
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