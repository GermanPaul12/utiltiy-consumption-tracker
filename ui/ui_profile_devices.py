# ui/ui_profile_devices.py
import streamlit as st
import pandas as pd
from utils import database as db
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render_page(current_user_id):
    st.title(t("mdev_title"))
    st.write(t("mdev_subtitle"))

    # Liste existierender Geräte laden (Nutzt den globalen State aus main.py)
    df_devices = st.session_state.get("devices")
    if df_devices is None:
        df_devices = db.load_devices(current_user_id)
        st.session_state.devices = df_devices
    
    # Auswahlliste zur Modus-Steuerung (Erstellen oder Editieren)
    device_options = [t("mdev_option_add")]
    device_records = []
    if not df_devices.empty:
        device_records = df_devices.to_dict(orient="records")
        device_options.extend([t("mdev_option_edit").format(name=d['device_name']) for d in device_records])
        
    selected_option = st.selectbox(t("mdev_select_action_label"), device_options)
    
    # Variablen initialisieren
    initial_name = ""
    initial_group = "Sonstiges"
    initial_elec = 150.0
    initial_water = 0.0
    is_edit_mode = False
    active_device_id = None
    
    # Falls ein Gerät zur Bearbeitung ausgewählt wurde, lade dessen Werte vorab
    if selected_option != t("mdev_option_add"):
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
    
    # Zuordnungstabelle der Übersetzungsschlüssel für Kategorien
    group_key_map = {
        "Kühlen & Gefrieren": "mdev_g_cooling",
        "Waschen & Trocknen": "mdev_g_laundry",
        "Kochen": "mdev_g_cooking",
        "Beleuchtung": "mdev_g_lighting",
        "TV, PC & Entertainment": "mdev_g_entertainment",
        "Geschirrspülen": "mdev_g_dishwashing",
        "Baden, Duschen, Körperpflege": "mdev_g_hygiene",
        "Toilettenspülung": "mdev_g_toilet",
        "Putzen, Garten, Auto": "mdev_g_cleaning",
        "Kochen & Trinken": "mdev_g_drinking",
        "Sonstiges": "mdev_g_other"
    }
    
    translated_groups = [t(group_key_map[item]) for item in available_groups]

    with st.form("device_crud_form"):
        form_header_key = "mdev_form_header_edit" if is_edit_mode else "mdev_form_header_create"
        st.write(f"**{t(form_header_key)}**")
        
        d_name = st.text_input(t("mdev_input_name_label"), value=initial_name, disabled=is_edit_mode)
        
        selected_group_trans = st.selectbox(
            t("mdev_select_group_label"), 
            options=translated_groups, 
            index=available_groups.index(initial_group) if initial_group in available_groups else 10
        )
        
        # Rück-Mapping der übersetzten Kategorie in den englischen DB-Standard
        selected_group_index = translated_groups.index(selected_group_trans)
        d_group = available_groups[selected_group_index]
        
        col_dev1, col_dev2 = st.columns(2)
        with col_dev1:
            d_elec = st.number_input(t("mdev_input_elec_label"), min_value=0.0, value=initial_elec, step=5.0)
        with col_dev2:
            d_water = st.number_input(t("mdev_input_water_label"), min_value=0.0, value=initial_water, step=0.1, help=t("mdev_input_water_help"))
            
        btn_label = t("mdev_btn_update") if is_edit_mode else t("mdev_btn_register")
        submitted_device = st.form_submit_button(btn_label)
        
        if submitted_device:
            target_name = initial_name if is_edit_mode else d_name.strip()
            if target_name:
                with st.spinner(t("mdev_saving_spinner").format(name=target_name)):
                    db.save_device(current_user_id, target_name, d_group, d_elec, d_water)
                
                # CACHE-BUSTING: Geräteliste im Cache verwerfen
                st.session_state.pop("devices", None)
                
                st.toast(t("mdev_save_success_toast").format(name=target_name), icon="💾")
                st.rerun()
            else:
                st.error(t("mdev_name_empty_err"))

    # Lösch-Formular nur anzeigen im Bearbeitungsmodus
    if is_edit_mode and active_device_id is not None:
        with st.form("delete_device_form"):
            st.write(f"**{t('mdev_danger_zone')}**")
            delete_submitted = st.form_submit_button(t("mdev_delete_btn"), type="primary")
            if delete_submitted:
                with st.spinner(t("mdev_deleting_spinner").format(name=initial_name)):
                    db.delete_device(current_user_id, active_device_id)
                
                # CACHE-BUSTING: Geräteliste im Cache verwerfen
                st.session_state.pop("devices", None)
                
                st.toast(t("mdev_delete_success_toast").format(name=initial_name), icon="🗑️")
                st.rerun()

    # Übersichtstabelle
    if not df_devices.empty:
        st.markdown(f"##### {t('mdev_overview_header')}")
        
        # Lokalisierte Spaltenübersetzungen und Gruppenbezeichnungen
        df_display = df_devices.copy()
        df_display["device_group"] = df_display["device_group"].apply(lambda g: t(group_key_map.get(g, g)))
        
        st.dataframe(
            df_display.rename(columns={
                "device_name": t("mdev_col_name"),
                "device_group": t("mdev_col_group"),
                "avg_yearly_consumption_kwh": t("mdev_col_elec"),
                "avg_yearly_water_m3": t("mdev_col_water")
            }).drop(columns=["user_id"], errors="ignore"),
            width="stretch"
        )