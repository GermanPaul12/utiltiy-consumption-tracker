# ui/ui_dashboard.py
import streamlit as st
from streamlit_option_menu import option_menu

# Import der einzelnen Unter-Komponenten aus dem dashboard/ Ordner
from dashboard import metrics_cards
from dashboard import cross_utility
from dashboard import smart_devices
from dashboard import history_timeline

def render_page(processed_logs, stats, rates, plotly_template, smart_logs=None):
    
    # ---------------------------------------------------------
    # MODERNE BOOTSTRAP-NAVBAR (ECHTES LAZY-LOADING)
    # ---------------------------------------------------------
    dashboard_view = option_menu(
        menu_title=None,  # Kein Menü-Titel für eine saubere Navbar-Optik
        options=["Finanzen & Übersicht", "Smart Plugs & Geräte", "Historie & Analysen"],
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
    if dashboard_view == "Finanzen & Übersicht":
        st.caption("ℹ️ Note: Baseline calculations require at least two sequential readings per meter.")
        
        # Rendert Metrik-Karten & finanzielle Bilanzen
        metrics_cards.render(
            stats, rates, total_cost_all, avg_monthly_cost_all, projected_annual_cost, 
            total_co2_all, total_days_tracked, global_standing_to_date, 
            total_prepayments_to_date, global_projected_annual_standing, total_annual_prepayments
        )
        
        # Standard-Tabs für die einzelnen Utility-Klassen
        st.markdown("---")
        st.subheader("Utility Specific Breakdown")
        tab_elec, tab_hw, tab_cw = st.tabs(["⚡ Electricity", "🔥 Hot Water (Fernwärme)", "💧 Cold Water"])
        
        for tab, m_name, suffix in zip([tab_elec, tab_hw, tab_cw], ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"], ["kWh", "MWh", "m³"]):
            with tab:
                if m_name in stats and stats[m_name]["entries_count"] > 1:
                    s = stats[m_name]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Consumption", f"{s['total_consumption']:,.3f} {suffix}")
                        st.metric("Daily Avg Consumption", f"{s['avg_daily_consumption']:.4f} {suffix}/day")
                        st.metric("Monthly Avg Consumption", f"{s['avg_monthly_consumption']:.3f} {suffix}/month")
                    with col2:
                        st.metric("Total Cost", f"€{s['total_cost']:,.2f}")
                        st.metric("Daily Avg Cost", f"€{s['avg_daily_cost']:.2f}/day")
                        st.metric("Monthly Avg Cost", f"€{s['avg_monthly_cost']:.2f}/month")
                    with col3:
                        st.metric("Monthly Prepayment", f"€{s['monthly_prepayment']:.2f}/month")
                        if s['projected_annual_standing'] >= 0:
                            st.metric("Projected Annual Refund", f"€{s['projected_annual_standing']:.2f}")
                        else:
                            st.metric("Projected Annual Backpayment", f"-€{abs(s['projected_annual_standing']):.2f}", delta_color="inverse")
                else:
                    st.info(f"Log at least two readings to calculate {m_name} stats.")

    elif dashboard_view == "Smart Plugs & Geräte":
        # Rendert nur die Smart Plugs und Kosten-Breakdowns, falls vorhanden
        if smart_logs is not None and not smart_logs.empty:
            current_user_id = st.session_state.user["id"]
            smart_devices.render(
                current_user_id, processed_logs, smart_logs, stats, rates, color_map, plotly_template
            )
        else:
            st.info("Keine aktiven Smart-Device-Logs in der Datenbank gefunden.")

    elif dashboard_view == "Historie & Analysen":
        # Rendert die logarithmierten und normalisierten Auswertungen
        cross_utility.render(processed_logs, color_map, plotly_template)
        
        # Rendert die aufwendigen historischen Plotly-Zeitreihendiagramme
        history_timeline.render(processed_logs, stats, rates, color_map, plotly_template)