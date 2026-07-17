# ui_profile.py
import streamlit as st
from utils import database as db
from utils import auth

def render_page(current_user_id, rates):
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
            
            # CACHE-BUSTING: Tarife und Berechnungen verwerfen
            st.session_state.pop("rates", None)
            st.session_state.pop("processed_logs", None)
            st.session_state.pop("stats", None)
            
            st.success("Profile and tariffs successfully updated.")
            st.rerun()

    st.markdown("---")
    
    # ui_profile.py (Geräte-Sektion)
    st.markdown("---")
    st.subheader("🔌 Haushaltsgeräte verwalten & editieren")
    st.write("Erfassen oder aktualisieren Sie Ihre Geräte, um sie den deutschen Standard-Kategorien zuzuordnen.")

    # Liste existierender Geräte laden
    df_devices = db.load_devices(current_user_id)
    from database import execute_db
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
        
        # Name im Edit-Mode sperren, um Konflikte mit dem UNIQUE-Constraint zu vermeiden
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
                # UX-Verlauf: Zeigt dem User präzise an, welcher DB-Schritt gerade läuft
                with st.spinner(f"Verbinde mit Cloud-Datenbank... Speichere '{target_name}'"):
                    db.save_device(current_user_id, target_name, d_group, d_elec, d_water)
                
                # CACHE-BUSTING: Geräteliste im Cache verwerfen
                st.session_state.pop("devices", None)
                
                st.toast(f"Gerät '{target_name}' erfolgreich in Datenbank gesichert!", icon="💾")
                st.rerun()
            else:
                st.error("Bitte tragen Sie einen gültigen Gerätenamen ein.")

    # Lösch-Formular nur anzeigen, wenn Geräte vorhanden sind und wir uns im Bearbeitungsmodus befinden
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