# styles.py
import streamlit as st

def inject_theme(theme_mode):
    if theme_mode == "🌙 Dark Mode":
        css = """
        <style>
            .stApp {
                background-color: #0f172a !important;
                color: #f1f5f9 !important;
            }
            [data-testid="stSidebar"] {
                background-color: #1e293b !important;
                border-right: 1px solid #334155;
            }
            div[data-testid="metric-container"] {
                background-color: #1e293b !important;
                border: 1px solid #334155 !important;
                padding: 18px !important;
                border-radius: 12px !important;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25) !important;
            }
            div[data-testid="stMetricLabel"] {
                color: #94a3b8 !important;
                font-size: 0.95rem !important;
                font-weight: 500 !important;
            }
            div[data-testid="stMetricValue"] {
                color: #38bdf8 !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #f8fafc !important;
                font-family: 'Inter', sans-serif !important;
            }
            button[data-baseweb="tab"] {
                color: #94a3b8 !important;
            }
            button[aria-selected="true"] {
                color: #38bdf8 !important;
                border-bottom-color: #38bdf8 !important;
            }
            div[data-testid="stForm"] {
                border: 1px solid #334155 !important;
                border-radius: 12px !important;
                background-color: #1e293b !important;
            }
        </style>
        """
    else: # ☀️ Light Mode
        css = """
        <style>
            .stApp {
                background-color: #f8fafc !important;
                color: #0f172a !important;
            }
            [data-testid="stSidebar"] {
                background-color: #ffffff !important;
                border-right: 1px solid #e2e8f0;
            }
            div[data-testid="metric-container"] {
                background-color: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                padding: 18px !important;
                border-radius: 12px !important;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04) !important;
            }
            div[data-testid="stMetricLabel"] {
                color: #64748b !important;
                font-size: 0.95rem !important;
                font-weight: 500 !important;
            }
            div[data-testid="stMetricValue"] {
                color: #0284c7 !important;
                font-weight: 700 !important;
                font-size: 1.8rem !important;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #0f172a !important;
                font-family: 'Inter', sans-serif !important;
            }
            button[data-baseweb="tab"] {
                color: #64748b !important;
            }
            button[aria-selected="true"] {
                color: #0284c7 !important;
                border-bottom-color: #0284c7 !important;
            }
            div[data-testid="stForm"] {
                border: 1px solid #e2e8f0 !important;
                border-radius: 12px !important;
                background-color: #ffffff !important;
            }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)