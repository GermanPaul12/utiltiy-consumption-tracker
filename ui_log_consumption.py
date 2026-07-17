# ui_log_consumption.py
import datetime
import streamlit as st
import database as db

def render_page(current_user_id, logs):
    st.title("Log Utility Readings")
    st.write("Tragen Sie hier Ihre kumulierten, physischen Zählerstände ein.")
    
    # ---------------------------------------------------------
    # UX-UPGRADE: GLOBALE KATEGORIE-ÜBERSICHT
    # ---------------------------------------------------------
    st.subheader("📋 Zuletzt erfasste Zählerstände (Übersicht)")
    
    categories = [
        {"name": "Electricity (kWh)", "icon": "⚡ Strom", "unit": "kWh"},
        {"name": "Hot Water (MWh)", "icon": "🔥 Warmwasser", "unit": "MWh"},
        {"name": "Cold Water (m³)", "icon": "💧 Kaltwasser", "unit": "m³"}
    ]
    
    col_elec, col_hw, col_cw = st.columns(3)
    cols = [col_elec, col_hw, col_cw]
    
    # Letzten Wert für jede Kategorie direkt anzeigen
    last_values_map = {}
    for i, cat in enumerate(categories):
        with cols[i]:
            cat_entries = logs[logs['meter'] == cat["name"]]
            if not cat_entries.empty:
                last_val = cat_entries.iloc[-1]['reading']
                last_dt = cat_entries.iloc[-1]['date']
                last_values_map[cat["name"]] = last_val
                st.info(
                    f"**{cat['icon']}**"
                    f"\n* Zählerstand: **{last_val:,.3f} {cat['unit']}**"
                    f"\n* Erfasst am: {last_dt}"
                )
            else:
                last_values_map[cat["name"]] = 0.0
                st.warning(
                    f"**{cat['icon']}**"
                    f"\n* Noch keine Daten erfasst."
                )

    st.markdown("---")
    st.subheader("✍️ Neuen Zählerwert eintragen")
    
    with st.form("log_form", clear_on_submit=True):
        col_input1, col_input2 = st.columns(2)
        
        with col_input1:
            log_date = st.date_input("Date of Reading", datetime.date.today())
            meter_type = st.selectbox(
                "Select Utility Meter",
                ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
            )
            
        with col_input2:
            last_val_selected = last_values_map.get(meter_type, 0.0)
            st.write(f"Ausgewählter Zähler: **{meter_type}**")
            st.write(f"Ihr letzter Zählerstand hierzu: **{last_val_selected:,.3f}**")
            
            reading_val = st.number_input(
                "Cumulative Reading Value", 
                min_value=0.0, 
                step=0.001, 
                format="%.3f"
            )
            
        submitted = st.form_submit_button("Submit Reading")
        
        if submitted:
            # Plausibilitätsprüfung
            if last_val_selected > 0 and reading_val < last_val_selected:
                st.warning(f"Note: Entered reading ({reading_val}) is lower than the last recorded reading ({last_val_selected}).")
            
            # UX-Verlauf: Präziser Ladestatus für den Schreibvorgang
            with st.spinner(f"💾 Übertrage {reading_val} für '{meter_type}' an die Cloud-Datenbank..."):
                db.execute_db("""
                    INSERT INTO logs (user_id, date, meter, reading) 
                    VALUES (:uid, :date, :meter, :reading)
                """, params={
                    "uid": current_user_id,
                    "date": log_date.strftime("%Y-%m-%d"),
                    "meter": meter_type,
                    "reading": reading_val
                })
            
            # CACHE-BUSTING: Entfernt die veralteten Werte aus dem RAM
            st.session_state.pop("logs", None)
            st.session_state.pop("processed_logs", None)
            st.session_state.pop("stats", None)
            
            # Diskreter Toast zur Bestätigung
            st.toast(f"Erfolgreich {reading_val} für {meter_type} gespeichert!", icon="✅")
            st.rerun()