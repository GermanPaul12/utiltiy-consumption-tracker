# ui/ui_profile_devices.py
import streamlit as st
import pandas as pd
from utils import database as db

def render_page(current_user_id):
    st.title("Haushaltsgeräte verwalten & editieren")
    st.write("Erfassen oder aktualisieren Sie Ihre Geräte, um sie den deutschen Standard-Kategorien zuzuordnen.")

    # Liste existierender Geräte laden (Nutzt den globalen State aus main.py)
    df_devices = st.session_state.get("devices")
    if df_devices is None:
        df_devices = db.load_devices(current_user_id)
        st.session_state.devices = df_devices
    
    # Auswahlliste zur Modus-Steuerung (Erstellen oder Editieren)
    device_options = ["➕ Neues Gerät hinzufügen"]
    device_records = []
    if not df_devices.empty:
        device_records = df_devices.to_dict(orient="records")
        device_options.extend([f"📝 {d['device_name']} bearbeiten" for d in device_records])
        
    selected_option = st.selectbox("Aktion wählen:", device_options)
    
    # Variablen initialisieren
    initial_name = ""
    initial_group = "Sonstiges"
    initial_elec = 150.0
    initial_water = 0.0
    is_edit_mode = False
    active_device_id = None
    
    # Falls ein Gerät zur Bearbeitung ausgewählt wurde, lade dessen Werte vorab
    if selected_option != "➕ Neues Gerät hinzufügen":
        is_edit_mode = True
        idx = device_options.index(selected_option) - 1
        selected_record = device_records[idx]
        active_device_id = selected_record["id"]
        initial_name = selected_record["device_name"]
        initial_group = selected_record.get("device_group", "Sonstiges")
        initial_elec = float(selected_record["avg_yearly_consumption_kwh"])
        initial_water = float(selected_record.get("avg_yearly_water_m3", 0.0))

    # Standard-Gruppenübereinstimmung für Strom & Wasser
    available_groups = [
        "Kühlen & Gefrieren",
        "Waschen & Trocknen",
        "Kochen",
        "Beleuchtung",
        "TV, PC & Entertainment",
        "Geschirrspülen",
        "Baden, Duschen, Körperpflege",
        "Toilettenspülung",
        "Putzen, Garten, Auto",
        "Kochen & Trinken",
        "Sonstiges"
    ]

    with st.form("device_crud_form"):
        st.write(f"**{'Gerät editieren' if is_edit_mode else 'Neues Gerät anlegen'}**")
        
        d_name = st.text_input("Gerätename", value=initial_name, disabled=is_edit_mode)
        d_group = st.selectbox("Zugeordnete Kategorie (BDEW-Vergleichsgruppe)", options=available_groups, index=available_groups.index(initial_group) if initial_group in available_groups else 10)
        
        col_dev1, col_dev2 = st.columns(2)
        with col_dev1:
            d_elec = st.number_input("Soll-Stromverbrauch (kWh / Jahr)", min_value=0.0, value=initial_elec, step=5.0)
        with col_dev2:
            d_water = st.number_input("Soll-Wasserverbrauch (m³ / Jahr)", min_value=0.0, value=initial_water, step=0.1, help="1 m³ = 1000 Liter")
            
        btn_label = "Spezifikationen aktualisieren" if is_edit_mode else "Gerät registrieren"
        submitted_device = st.form_submit_button(btn_label)
        
        if submitted_device:
            target_name = initial_name if is_edit_mode else d_name.strip()
            if target_name:
                with st.spinner(f"Verbinde mit Cloud-Datenbank... Speichere '{target_name}'"):
                    db.save_device(current_user_id, target_name, d_group, d_elec, d_water)
                
                # CACHE-BUSTING: Geräteliste im Cache verwerfen
                st.session_state.pop("devices", None)
                
                st.toast(f"Gerät '{target_name}' erfolgreich in Datenbank gesichert!", icon="💾")
                st.rerun()
            else:
                st.error("Bitte tragen Sie einen gültigen Gerätenamen ein.")

    # Lösch-Formular nur anzeigen im Bearbeitungsmodus
    if is_edit_mode and active_device_id is not None:
        with st.form("delete_device_form"):
            st.write("**Gefahrenbereich**")
            delete_submitted = st.form_submit_button("Gerät unwiderruflich löschen", type="primary")
            if delete_submitted:
                with st.spinner(f"Lösche Eintrag für '{initial_name}' aus Datenbank..."):
                    db.delete_device(current_user_id, active_device_id)
                
                # CACHE-BUSTING: Geräteliste im Cache verwerfen
                st.session_state.pop("devices", None)
                
                st.toast(f"Eintrag für '{initial_name}' gelöscht.", icon="🗑️")
                st.rerun()

    # Übersichtstabelle
    if not df_devices.empty:
        st.markdown("##### Registrierte Geräte in der Übersicht")
        st.dataframe(
            df_devices.rename(columns={
                "device_name": "Gerätename",
                "device_group": "Kategorie",
                "avg_yearly_consumption_kwh": "Stromsollwert (kWh/Jahr)",
                "avg_yearly_water_m3": "Wassersollwert (m³/Jahr)"
            }).drop(columns=["user_id"], errors="ignore"),
            width="stretch"
        )