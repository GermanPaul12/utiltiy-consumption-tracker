# database.py
import os
import ssl
from dotenv import load_dotenv 
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import uuid
import datetime

load_dotenv()
# 1. Establish Database Connection Engine with Auto-Cleanup & SSL Context
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)
    
    if "?" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?")[0]
        
    db_url = DATABASE_URL
    
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    engine = create_engine(
        db_url, 
        connect_args={"ssl_context": ssl_ctx},
        pool_pre_ping=True
    )
else:
    db_url = "sqlite:///utility_tracker.db"
    engine = create_engine(db_url)

# Helper function to run SELECT queries
def run_query(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

# Helper function to execute transactions
def execute_db(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

# --- PRE-FLIGHT DATABASE CONNECTION CHECK ---
def check_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, ""
    except Exception as e:
        return False, str(e)

# Database Schema Initialization & Safe Migration
def initialize_database():
    is_sqlite = engine.dialect.name == 'sqlite'
    
    if is_sqlite:
        execute_db("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, date TEXT, meter TEXT, reading REAL)")
        execute_db("CREATE TABLE IF NOT EXISTS rates (user_id TEXT PRIMARY KEY, electricity_kwh REAL, electricity_base REAL, hot_water_mwh REAL, cold_water_m3 REAL, electricity_prepayment REAL, hot_water_prepayment REAL, cold_water_prepayment REAL, household_size INTEGER DEFAULT 1, apartment_size REAL DEFAULT 50.0)")
        execute_db("""
            CREATE TABLE IF NOT EXISTS smart_device_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id TEXT, 
                date TEXT, 
                device_name TEXT, 
                ip TEXT, 
                current_power_w REAL, 
                today_energy_kwh REAL, 
                month_energy_kwh REAL, 
                today_runtime_min INTEGER, 
                month_runtime_min INTEGER
            )
        """)
        execute_db("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id TEXT, 
                device_name TEXT, 
                device_group TEXT DEFAULT 'Sonstiges',
                avg_yearly_consumption_kwh REAL DEFAULT 0.0,
                avg_yearly_water_m3 REAL DEFAULT 0.0,
                UNIQUE (user_id, device_name)
            )
        """)
    else:
        execute_db("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, date DATE, meter VARCHAR(100), reading DOUBLE PRECISION)")
        execute_db("CREATE TABLE IF NOT EXISTS rates (user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, electricity_kwh DOUBLE PRECISION, electricity_base DOUBLE PRECISION, hot_water_mwh DOUBLE PRECISION, cold_water_m3 DOUBLE PRECISION, electricity_prepayment DOUBLE PRECISION, hot_water_prepayment DOUBLE PRECISION, cold_water_prepayment DOUBLE PRECISION, household_size INTEGER DEFAULT 1, apartment_size DOUBLE PRECISION DEFAULT 50.0)")
        execute_db("""
            CREATE TABLE IF NOT EXISTS smart_device_logs (
                id SERIAL PRIMARY KEY, user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, date DATE, device_name VARCHAR(100), ip VARCHAR(45), 
                current_power_w DOUBLE PRECISION, today_energy_kwh DOUBLE PRECISION, month_energy_kwh DOUBLE PRECISION, today_runtime_min INTEGER, month_runtime_min INTEGER
            )
        """)
        execute_db("""
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY, 
                user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, 
                device_name VARCHAR(100), 
                device_group VARCHAR(100) DEFAULT 'Sonstiges',
                avg_yearly_consumption_kwh DOUBLE PRECISION DEFAULT 0.0,
                avg_yearly_water_m3 DOUBLE PRECISION DEFAULT 0.0,
                UNIQUE (user_id, device_name)
            )
        """)
    if is_sqlite:
        execute_db("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY, 
                user_id TEXT, 
                user_email TEXT, 
                expires_at TEXT
            )
        """)
    else:
        execute_db("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id UUID PRIMARY KEY, 
                user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE, 
                user_email VARCHAR(255), 
                expires_at TIMESTAMP WITH TIME ZONE
            )
        """)

    # Sicherheits-Migrationen für bestehende Installationen
    try:
        if is_sqlite:
            execute_db("ALTER TABLE devices ADD COLUMN avg_yearly_water_m3 REAL DEFAULT 0.0")
        else:
            execute_db("ALTER TABLE devices ADD COLUMN avg_yearly_water_m3 DOUBLE PRECISION DEFAULT 0.0")
    except Exception:
        pass

    try:
        if is_sqlite:
            execute_db("ALTER TABLE devices ADD COLUMN device_group TEXT DEFAULT 'Sonstiges'")
        else:
            execute_db("ALTER TABLE devices ADD COLUMN device_group VARCHAR(100) DEFAULT 'Sonstiges'")
    except Exception:
        pass

    try:
        df_rates_check = run_query("SELECT * FROM rates LIMIT 1")
        if not df_rates_check.empty and "user_id" not in df_rates_check.columns:
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE rates"))
    except Exception:
        pass
    try:
        if is_sqlite:
            execute_db("ALTER TABLE rates ADD COLUMN move_in_date TEXT")
            execute_db("ALTER TABLE rates ADD COLUMN tariff_start_date TEXT")
        else:
            execute_db("ALTER TABLE rates ADD COLUMN move_in_date DATE")
            execute_db("ALTER TABLE rates ADD COLUMN tariff_start_date DATE")
    except Exception:
        pass # Spalten existieren bereits

    df_rates_check = run_query("SELECT * FROM rates LIMIT 1")
    if "household_size" not in df_rates_check.columns:
        with engine.begin() as conn:
            if is_sqlite:
                conn.execute(text("ALTER TABLE rates ADD COLUMN household_size INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE rates ADD COLUMN apartment_size REAL DEFAULT 50.0"))
            else:
                conn.execute(text("ALTER TABLE rates ADD COLUMN household_size INTEGER DEFAULT 1"))
                conn.execute(text("ALTER TABLE rates ADD COLUMN apartment_size DOUBLE PRECISION DEFAULT 50.0"))

# User-Scoped Data Helpers
# utils/database.py

def load_rates(user_id):
    df = run_query("SELECT * FROM rates WHERE user_id = :uid", {"uid": user_id})
    if df.empty:
        # Erstellt Default-Werte inklusive dem heutigen Datum als Einzug/Tarifstart
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        execute_db(f"""
            INSERT INTO rates (user_id, electricity_kwh, electricity_base, hot_water_mwh, cold_water_m3, 
                               electricity_prepayment, hot_water_prepayment, cold_water_prepayment,
                               household_size, apartment_size, move_in_date, tariff_start_date)
            VALUES (:uid, 0.282, 16.80, 95.00, 4.50, 0.0, 0.0, 0.0, 1, 50.0, '{today_str}', '{today_str}')
            ON CONFLICT (user_id) DO NOTHING
        """, {"uid": user_id})
        df = run_query("SELECT * FROM rates WHERE user_id = :uid", {"uid": user_id})
    return df.iloc[0].to_dict()

def save_rates(user_id, rates_dict):
    execute_db("""
        UPDATE rates 
        SET electricity_kwh = :elec_kwh, 
            electricity_base = :elec_base, 
            hot_water_mwh = :hw_mwh, 
            cold_water_m3 = :cw_m3,
            electricity_prepayment = :elec_prep,
            hot_water_prepayment = :hw_prep,
            cold_water_prepayment = :cw_prep,
            household_size = :house_size,
            apartment_size = :apt_size,
            move_in_date = :move_in,
            tariff_start_date = :tariff_start
        WHERE user_id = :uid
    """, params={
        "uid": user_id,
        "elec_kwh": rates_dict["electricity_kwh"],
        "elec_base": rates_dict["electricity_base"],
        "hw_mwh": rates_dict["hot_water_mwh"],
        "cw_m3": rates_dict["cold_water_m3"],
        "elec_prep": rates_dict["electricity_prepayment"],
        "hw_prep": rates_dict["hot_water_prepayment"],
        "cw_prep": rates_dict["cold_water_prepayment"],
        "house_size": int(rates_dict["household_size"]),
        "apt_size": float(rates_dict["apartment_size"]),
        "move_in": rates_dict["move_in_date"],
        "tariff_start": rates_dict["tariff_start_date"]
    })

def load_logs(user_id):
    df = run_query("SELECT * FROM logs WHERE user_id = :uid ORDER BY date ASC", {"uid": user_id})
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def load_smart_device_logs(user_id):
    df = run_query("SELECT * FROM smart_device_logs WHERE user_id = :uid ORDER BY date ASC", {"uid": user_id})
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

# Hilfsfunktionen für das Speichern und Löschen statischer Benchmarks
def load_devices(user_id):
    return run_query("SELECT * FROM devices WHERE user_id = :uid ORDER BY device_name ASC", {"uid": user_id})

def save_device(user_id, device_name, device_group, avg_yearly_kwh, avg_yearly_water_m3):
    is_sqlite = engine.dialect.name == 'sqlite'
    if is_sqlite:
        execute_db("""
            INSERT OR REPLACE INTO devices (user_id, device_name, device_group, avg_yearly_consumption_kwh, avg_yearly_water_m3)
            VALUES (:uid, :name, :group, :yearly_kwh, :yearly_water)
        """, {"uid": user_id, "name": device_name, "group": device_group, "yearly_kwh": avg_yearly_kwh, "yearly_water": avg_yearly_water_m3})
    else:
        execute_db("""
            INSERT INTO devices (user_id, device_name, device_group, avg_yearly_consumption_kwh, avg_yearly_water_m3)
            VALUES (:uid, :name, :group, :yearly_kwh, :yearly_water)
            ON CONFLICT (user_id, device_name) 
            DO UPDATE SET 
                device_group = EXCLUDED.device_group,
                avg_yearly_consumption_kwh = EXCLUDED.avg_yearly_consumption_kwh,
                avg_yearly_water_m3 = EXCLUDED.avg_yearly_water_m3
        """, {"uid": user_id, "name": device_name, "group": device_group, "yearly_kwh": avg_yearly_kwh, "yearly_water": avg_yearly_water_m3})

def delete_device(user_id, device_id):
    execute_db("DELETE FROM devices WHERE user_id = :uid AND id = :did", {"uid": user_id, "did": int(device_id)})
    

def create_user_session(user_id, user_email):
    # Generiert eine sichere, zufällige Sitzungs-ID (UUID)
    session_id = str(uuid.uuid4())
    # Gültigkeit: 30 Tage in der Zukunft
    expires_at = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    
    execute_db("""
        INSERT INTO user_sessions (id, user_id, user_email, expires_at)
        VALUES (:id, :uid, :email, :expires)
    """, {"id": session_id, "uid": user_id, "email": user_email, "expires": expires_at})
    
    return session_id

def validate_user_session(session_id):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prüft, ob die Sitzungs-ID existiert und noch nicht abgelaufen ist
    df = run_query("""
        SELECT user_id, user_email FROM user_sessions 
        WHERE id = :id AND expires_at > :now
    """, {"id": session_id, "now": now_str})
    
    if not df.empty:
        return {
            "id": str(df.iloc[0]["user_id"]),
            "email": str(df.iloc[0]["user_email"])
        }
    return None

def delete_user_session(session_id):
    execute_db("DELETE FROM user_sessions WHERE id = :id", {"id": session_id})