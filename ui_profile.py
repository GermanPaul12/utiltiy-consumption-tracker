# ui_profile.py
import streamlit as st
import database as db
import auth

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
            st.success("Profile and tariffs successfully updated.")
            st.rerun()

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