# auth.py
import os
from dotenv import load_dotenv

# Force load environment variables immediately on module import
load_dotenv()

from supabase import create_client, Client
from database import execute_db

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def register_user(email, password):
    email_clean = email.strip().lower()
    if not email_clean or not password:
        return False, "Email and password cannot be empty."
    
    try:
        response = supabase.auth.sign_up({
            "email": email_clean,
            "password": password
        })
        
        if response.user:
            # Lazy initialize standard rates for this new user UUID
            execute_db("""
                INSERT INTO rates (user_id, electricity_kwh, electricity_base, hot_water_mwh, cold_water_m3, 
                                   electricity_prepayment, hot_water_prepayment, cold_water_prepayment,
                                   household_size, apartment_size)
                VALUES (:uid, 0.282, 16.80, 95.00, 4.50, 0.0, 0.0, 0.0, 1, 50.0)
                ON CONFLICT (user_id) DO NOTHING
            """, {"uid": response.user.id})
            
            return True, "Registration successful! Check your email inbox to confirm your account if required."
        return False, "Failed to create user."
    except Exception as e:
        return False, str(e)

def authenticate_user(email, password):
    email_clean = email.strip().lower()
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email_clean,
            "password": password
        })
        if response.user and response.session:
            # Gibt User-Daten UND die Session-Tokens zur Persistierung zurück
            return {
                "id": response.user.id, 
                "email": response.user.email,
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token
            }
    except Exception:
        return None
    return None