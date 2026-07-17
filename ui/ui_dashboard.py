# ui/ui_dashboard.py
import streamlit as st
from streamlit_option_menu import option_menu
from utils.i18n import t  # Importiert das Übersetzungsmodul

# Import der einzelnen Unter-Komponenten aus dem dashboard/ Ordner
from dashboard import metrics_cards
from dashboard import cross_utility
from dashboard import smart_devices
from dashboard import history_timeline

def render_page(processed_logs, stats, rates, plotly_template, smart_logs=None):
    
    # Interne, sprachneutrale Navigationsschlüssel
    menu_items = ["Finance & Overview", "Smart Plugs & Devices", "History & Analytics"]
    
    # Zuordnungstabelle der Übersetzungsschlüssel
    translation_key_map = {
        "Finance & Overview": "dash_nav_finance",
        "Smart Plugs & Devices": "dash_nav_smart_plugs",
        "History & Analytics": "dash_nav_history"
    }
    
    # Übersetzte Bezeichnungen erzeugen
    translated_options = [t(translation_key_map[item]) for item in menu_items]
    
    # ---------------------------------------------------------
    # MODERNE BOOTSTRAP-NAVBAR (ECHTES LAZY-LOADING & DYNAMISCH)
    # ---------------------------------------------------------
    selected_page_translated = option_menu(
        menu_title=None,
        options=translated_options,
        icons=["cash-coin", "plug-fill", "graph-up-arrow"],  # Bootstrap Icons
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#38bdf8", "font-size": "16px"}, 
            "nav-link": {
                "font-size": "14px", 
                "text-align": "center", 
                "margin": "0px", 
                "--hover-color": "#1e293b"
            },
            "nav-link-selected": {"background-color": "#0284c7", "font-weight": "600"},
        }
    )
    
    # Übersetztes Ereignis wieder in interne ID mappen
    selected_index = translated_options.index(selected_page_translated)
    dashboard_view = menu_items[selected_index]
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Gemeinsame Farb-Zuweisung für einheitliche Visualisierung
    color_map = {
        "Electricity (kWh)": "#eab308",
        "Hot Water (MWh)": "#ef4444",
        "Cold Water (m³)": "#3b82f6",
        "Actual cost to Date": "#ef4444",
        "Prepayments to Date": "#22c55e",
        "Actual Incurred Cost": "#ef4444",
        "Prepayments Paid to Date": "#22c55e",
        "Variable (Usage)": "#eab308",
        "Fixed (Base Standing Charge)": "#ef4444",
        "Unbekannt (Rest)": "#64748b"
    }

    # Globale leichtgewichtige Berechnungen (im RAM extrem schnell)
    total_cost_all = sum(m.get("total_cost", 0.0) for m in stats.values())
    avg_monthly_cost_all = sum(m.get("avg_monthly_cost", 0.0) for m in stats.values())
    avg_daily_cost_all = sum(m.get("avg_daily_cost", 0.0) for m in stats.values())
    projected_annual_cost = avg_daily_cost_all * 365.25
    total_co2_all = sum(m.get("total_co2", 0.0) for m in stats.values())
    
    total_prepayments_to_date = sum(m.get("prepayment_paid_to_date", 0.0) for m in stats.values())
    global_standing_to_date = total_prepayments_to_date - total_cost_all
    
    total_annual_prepayments = sum(m.get("annual_prepayment", 0.0) for m in stats.values())
    global_projected_annual_standing = total_annual_prepayments - projected_annual_cost
    
    total_days_tracked = max(sum(m.get("total_days", 0) for m in stats.values()), 1)

    # ---------------------------------------------------------
    # LAZY-LOADING: NUR DEN AUSGEWÄHLTEN BEREICH RENDERN
    # ---------------------------------------------------------
    if dashboard_view == "Finance & Overview":
        st.caption(t("dash_baseline_note"))
        
        # Rendert Metrik-Karten & finanzielle Bilanzen
        metrics_cards.render(
            stats, rates, total_cost_all, avg_monthly_cost_all, projected_annual_cost, 
            total_co2_all, total_days_tracked, global_standing_to_date, 
            total_prepayments_to_date, global_projected_annual_standing, total_annual_prepayments
        )
        
        # ---------------------------------------------------------
        # NEU: 3-SPALTEN-LAYOUT FÜR DIREKTEN VERGLEICH (STATT TABS)
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader(t("dash_utility_breakdown_header"))
        
        col_elec, col_hw, col_cw = st.columns(3)
        cols = [col_elec, col_hw, col_cw]
        meters = ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
        suffixes = ["kWh", "MWh", "m³"]
        headers = [t("dash_tab_elec"), t("dash_tab_hw"), t("dash_tab_cw")]
        
        for col, m_name, suffix, header in zip(cols, meters, suffixes, headers):
            with col:
                st.markdown(f"#### {header}")
                if m_name in stats and stats[m_name]["entries_count"] > 1:
                    s = stats[m_name]
                    
                    st.metric(t("dash_metric_total_consumption"), f"{s['total_consumption']:,.3f} {suffix}")
                    st.metric(t("dash_metric_daily_avg_consumption"), f"{s['avg_daily_consumption']:.4f} {suffix}/day")
                    st.metric(t("dash_metric_monthly_avg_consumption"), f"{s['avg_monthly_consumption']:.3f} {suffix}/month")
                    
                    st.markdown("---")
                    st.metric(t("dash_metric_total_cost"), f"€{s['total_cost']:,.2f}")
                    st.metric(t("dash_metric_daily_avg_cost"), f"€{s['avg_daily_cost']:.2f}/day")
                    st.metric(t("dash_metric_monthly_avg_cost"), f"€{s['avg_monthly_cost']:.2f}/month")
                    
                    st.markdown("---")
                    st.metric(t("dash_metric_monthly_prepayment"), f"€{s['monthly_prepayment']:.2f}/month")
                    if s['projected_annual_standing'] >= 0:
                        st.metric(t("dash_metric_projected_refund"), f"€{s['projected_annual_standing']:.2f}")
                    else:
                        st.metric(t("dash_metric_projected_backpayment"), f"-€{abs(s['projected_annual_standing']):.2f}", delta_color="inverse")
                else:
                    st.info(t("dash_insufficient_data"))

    elif dashboard_view == "Smart Plugs & Devices":
        # Rendert nur die Smart Plugs und Kosten-Breakdowns, falls vorhanden
        if smart_logs is not None and not smart_logs.empty:
            current_user_id = st.session_state.user["id"]
            smart_devices.render(
                current_user_id, processed_logs, smart_logs, stats, rates, color_map, plotly_template
            )
        else:
            st.info(t("dash_no_smart_logs"))

    elif dashboard_view == "History & Analytics":
        # Rendert die logarithmierten und normalisierten Auswertungen
        cross_utility.render(processed_logs, color_map, plotly_template)
        
        # Rendert die aufwendigen historischen Plotly-Zeitreihendiagramme
        history_timeline.render(processed_logs, stats, rates, color_map, plotly_template)