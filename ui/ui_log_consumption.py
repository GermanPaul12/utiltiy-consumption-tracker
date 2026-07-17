# ui/ui_log_consumption.py
import datetime
import streamlit as st
from utils import database as db
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render_page(current_user_id, logs):
    st.title(t("log_title"))
    st.write(t("log_subtitle"))
    
    # ---------------------------------------------------------
    # GLOBALE KATEGORIE-ÜBERSICHT (Dynamisch lokalisiert)
    # ---------------------------------------------------------
    st.subheader(t("log_last_readings_header"))
    
    categories = [
        {"name": "Electricity (kWh)", "key_label": "log_cat_elec", "unit": "kWh"},
        {"name": "Hot Water (MWh)", "key_label": "log_cat_hw", "unit": "MWh"},
        {"name": "Cold Water (m³)", "key_label": "log_cat_cw", "unit": "m³"}
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
                    f"**{t(cat['key_label'])}**\n* "
                    f"{t('log_last_val').format(val=last_val, unit=cat['unit'])}\n* "
                    f"{t('log_recorded_on').format(date=last_dt)}"
                )
            else:
                last_values_map[cat["name"]] = 0.0
                st.warning(
                    f"**{t(cat['key_label'])}**\n* "
                    f"{t('log_no_data')}"
                )

    st.markdown("---")
    st.subheader(t("log_new_entry_header"))
    
    # Sprachneutrale Datenbank-Spezifikationen der Zählertypen
    db_meters = ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
    
    # Zuordnungstabelle der Übersetzungsschlüssel für die Auswahlliste
    option_key_map = {
        "Electricity (kWh)": "log_option_elec",
        "Hot Water (MWh)": "log_option_hw",
        "Cold Water (m³)": "log_option_cw"
    }
    
    translated_meters = [t(option_key_map[item]) for item in db_meters]
    
    with st.form("log_form", clear_on_submit=True):
        col_input1, col_input2 = st.columns(2)
        
        with col_input1:
            log_date = st.date_input(t("log_date_label"), datetime.date.today())
            selected_trans = st.selectbox(
                t("log_meter_select_label"),
                options=translated_meters
            )
            
            # Rück-Mapping der übersetzten Auswahl in den englischen Datenbank-Zählertyp
            selected_index = translated_meters.index(selected_trans)
            meter_type = db_meters[selected_index]
            
        with col_input2:
            last_val_selected = last_values_map.get(meter_type, 0.0)
            
            st.write(t("log_selected_meter").format(meter=t(option_key_map[meter_type])))
            st.write(t("log_last_val_comparison").format(val=last_val_selected))
            
            reading_val = st.number_input(
                t("log_input_reading_label"), 
                min_value=0.0, 
                step=0.001, 
                format="%.3f"
            )
            
        submitted = st.form_submit_button(t("log_submit_btn"))
        
        if submitted:
            # Plausibilitätsprüfung
            if last_val_selected > 0 and reading_val < last_val_selected:
                st.warning(t("log_plausibility_warning").format(reading=reading_val, last=last_val_selected))
            
            # Präziser Ladespinner für den Schreibvorgang
            with st.spinner(t("log_saving_spinner").format(reading=reading_val, meter=t(option_key_map[meter_type]))):
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
            st.toast(t("log_success_toast").format(reading=reading_val, meter=t(option_key_map[meter_type])), icon="✅")
            st.rerun()