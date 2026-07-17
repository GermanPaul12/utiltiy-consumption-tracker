# ui/ui_profile.py
import datetime
import pandas as pd
import streamlit as st
from utils import database as db
from utils import auth
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render_page(current_user_id, rates):
    st.title(t("profile_title"))
    st.write(t("profile_subtitle"))

    with st.form("settings_form"):
        st.subheader(t("profile_household_header"))
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            h_size = st.number_input(
                t("profile_household_size"),
                min_value=1,
                max_value=15,
                value=int(rates.get("household_size", 1)),
                step=1
            )
            
            # Einzugsdatum (Default auf heute, falls nicht vorhanden)
            default_move_in = datetime.date.today()
            if rates.get("move_in_date"):
                default_move_in = pd.to_datetime(rates.get("move_in_date")).date()
                
            move_in_val = st.date_input(t("profile_move_in_date"), default_move_in)
            
        with p_col2:
            a_size = st.number_input(
                t("profile_apartment_size"),
                min_value=5.0,
                max_value=1000.0,
                value=float(rates.get("apartment_size", 50.0)),
                step=0.5,
                format="%.1f"
            )
            
            # Tarifstartdatum (Default auf heute, falls nicht vorhanden)
            default_tariff_start = datetime.date.today()
            if rates.get("tariff_start_date"):
                default_tariff_start = pd.to_datetime(rates.get("tariff_start_date")).date()
                
            tariff_start_val = st.date_input(t("profile_tariff_start_date"), default_tariff_start)
            
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(t("profile_elec_header"))
            elec_rate = st.number_input(
                t("profile_elec_tariff"), 
                value=float(rates.get("electricity_kwh", 0.282)), 
                step=0.001, 
                format="%.4f"
            )
            elec_base = st.number_input(
                t("profile_elec_base_price"), 
                value=float(rates.get("electricity_base", 16.80)), 
                step=0.10, 
                format="%.2f"
            )
            elec_prep = st.number_input(
                t("profile_elec_prepayment"),
                value=float(rates.get("electricity_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
        with col2:
            st.subheader(t("profile_hw_header"))
            hw_rate = st.number_input(
                t("profile_hw_tariff"), 
                value=float(rates.get("hot_water_mwh", 95.00)), 
                step=0.50, 
                format="%.2f"
            )
            hw_prep = st.number_input(
                t("profile_hw_prepayment"),
                value=float(rates.get("hot_water_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
            st.subheader(t("profile_cw_header"))
            cw_rate = st.number_input(
                t("profile_cw_tariff"), 
                value=float(rates.get("cold_water_m3", 4.50)), 
                step=0.10, 
                format="%.2f"
            )
            cw_prep = st.number_input(
                t("profile_cw_prepayment"),
                value=float(rates.get("cold_water_prepayment", 0.0)),
                step=1.00,
                format="%.2f"
            )
            
        saved = st.form_submit_button(t("profile_submit_btn"))
        
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
                "apartment_size": a_size,
                "move_in_date": move_in_val.strftime("%Y-%m-%d"),
                "tariff_start_date": tariff_start_val.strftime("%Y-%m-%d")
            }
            db.save_rates(current_user_id, new_rates)
            
            # CACHE-BUSTING: Tarife und Berechnungen verwerfen
            st.session_state.pop("rates", None)
            st.session_state.pop("processed_logs", None)
            st.session_state.pop("stats", None)
            
            st.success(t("profile_success_msg"))
            st.rerun()

    st.markdown("---")
    st.subheader(t("profile_password_header"))
    st.write(t("profile_password_subtitle"))
    
    with st.form("change_password_form"):
        new_password = st.text_input(t("profile_password_new"), type="password")
        confirm_password = st.text_input(t("profile_password_confirm"), type="password")
        password_submitted = st.form_submit_button(t("profile_password_submit_btn"))
        
        if password_submitted:
            if not new_password or not confirm_password:
                st.error(t("profile_password_empty_err"))
            elif new_password != confirm_password:
                st.error(t("profile_password_match_err"))
            else:
                try:
                    auth.supabase.auth.update_user({"password": new_password})
                    st.success(t("profile_password_success"))
                except Exception as e:
                    st.error(f"{t('profile_password_fail')} {e}")