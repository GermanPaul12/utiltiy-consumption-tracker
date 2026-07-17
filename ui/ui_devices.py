# ui/ui_devices.py
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import database as db
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render_page(current_user_id, stats, rates):
    st.title(t("dev_title"))
    st.write(t("dev_subtitle"))
    
    # Haushalts- und Tarifparameter abrufen
    household_size = max(int(rates.get("household_size", 1)), 1)
    apartment_size = max(float(rates.get("apartment_size", 50.0)), 1.0)
    
    elec_tariff = float(rates.get("electricity_kwh", 0.282))
    water_tariff = float(rates.get("cold_water_m3", 4.50))
    
    # Formatierter Infokasten
    st.info(t("dev_info_basis").format(size=household_size, elec=elec_tariff, water=water_tariff))

    # Nutzt geladene Geräte aus dem Session-State (beschleunigt Ladezeit)
    df_devices = st.session_state.get("devices")
    if df_devices is None:
        df_devices = db.load_devices(current_user_id)
        st.session_state.devices = df_devices
    
    if df_devices.empty:
        st.warning(t("dev_no_devices_warning"))
        return

    # Hochgerechnete Jahreswerte aus manuellen Zählerständen
    actual_annual_elec = stats.get("Electricity (kWh)", {}).get("avg_daily_consumption", 0.0) * 365.25
    actual_annual_water = stats.get("Cold Water (m³)", {}).get("avg_daily_consumption", 0.0) * 365.25

    # ---------------------------------------------------------
    # FINANZIELLE BERWERTUNG & TOP-VERBRAUCHER DER GERÄTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.header(t("dev_financial_header"))
    st.write(t("dev_financial_subtitle"))

    # Kostenberechnungen für jedes Gerät hinzufügen
    df_devices_calc = df_devices.copy()
    df_devices_calc["yearly_elec_cost"] = df_devices_calc["avg_yearly_consumption_kwh"] * elec_tariff
    df_devices_calc["yearly_water_cost"] = df_devices_calc["avg_yearly_water_m3"] * water_tariff
    df_devices_calc["total_yearly_cost"] = df_devices_calc["yearly_elec_cost"] + df_devices_calc["yearly_water_cost"]

    # Sortieren nach den teuersten Verbrauchern
    df_devices_sorted = df_devices_calc.sort_values(by="total_yearly_cost", ascending=False)

    col_t1, col_t2 = st.columns([3, 2])
    
    with col_t1:
        st.markdown(f"##### {t('dev_rank_title')}")
        fig_cost_drivers = px.bar(
            df_devices_sorted,
            x="total_yearly_cost",
            y="device_name",
            orientation="h",
            color="device_group",
            title=t("dev_chart_title"),
            labels={
                "total_yearly_cost": t("dev_label_cost"), 
                "device_name": t("dev_label_device"), 
                "device_group": t("dev_label_category")
            },
            template="plotly_dark"
        )
        # Sortierung auf der Y-Achse beibehalten (teuerstes oben)
        fig_cost_drivers.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_cost_drivers, width="stretch")
        
    with col_t2:
        st.markdown(f"##### {t('dev_table_title')}")
        st.dataframe(
            df_devices_sorted[[
                "device_name", "device_group", "avg_yearly_consumption_kwh", 
                "avg_yearly_water_m3", "total_yearly_cost"
            ]].rename(columns={
                "device_name": t("dev_col_device"),
                "device_group": t("dev_col_category"),
                "avg_yearly_consumption_kwh": t("dev_col_elec"),
                "avg_yearly_water_m3": t("dev_col_water"),
                "total_yearly_cost": t("dev_col_cost")
            }),
            width="stretch"
        )

    # ---------------------------------------------------------
    # ERKLÄRBARKEITS-CHECK (STROM MIT INTERAKTIVEM 2% GRUPPIERUNGSFILTER)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header(t("dev_elec_explain_header"))
    
    if actual_annual_elec > 0:
        sum_device_elec = df_devices_calc["avg_yearly_consumption_kwh"].sum()
        elec_unbekannt = max(0.0, actual_annual_elec - sum_device_elec)
        explain_pct_elec = min(100.0, (sum_device_elec / actual_annual_elec) * 100)
        
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric(
            t("dev_metric_actual_consumption"), 
            f"{actual_annual_elec:,.0f} {t('dev_unit_kwh_year')}", 
            t("dev_unit_eur_year_formatted").format(val=actual_annual_elec * elec_tariff), 
            delta_color="off"
        )
        ec2.metric(
            t("dev_metric_explained"), 
            f"{sum_device_elec:,.0f} {t('dev_unit_kwh_year')}", 
            t("dev_unit_eur_year_formatted").format(val=sum_device_elec * elec_tariff), 
            delta_color="off"
        )
        ec3.metric(
            t("dev_metric_quote"), 
            f"{explain_pct_elec:.1f} %", 
            t("dev_unexplained_formatted").format(val=100.0 - explain_pct_elec), 
            delta_color="inverse" if explain_pct_elec < 80 else "normal"
        )
        
        # Analyse-Text Strom
        st.markdown(f"**{t('dev_elec_explain_analysis_title')}**")
        if explain_pct_elec < 100:
            st.write(
                t("dev_elec_explain_analysis_text").format(
                    pct=explain_pct_elec,
                    rem_pct=100.0 - explain_pct_elec,
                    unexplained_val=elec_unbekannt,
                    unexplained_cost=elec_unbekannt * elec_tariff
                )
            )
        else:
            st.success(t("dev_elec_explain_fully_covered"))
            
        # ---------------------------------------------------------
        # MATHEMATISCHE GRUPPIERUNG: GERÄTE UNTER 2% ZUSAMMENFASSEN
        # ---------------------------------------------------------
        threshold_2_percent = actual_annual_elec * 0.02
        
        main_elec_list = []
        small_elec_list = []
        
        # Aufteilung der Geräte in Hauptgeräte und Kleingeräte (< 2%)
        for _, r in df_devices_calc.iterrows():
            kwh = r["avg_yearly_consumption_kwh"]
            if kwh > 0:
                share_pct = (kwh / actual_annual_elec) * 100
                device_info = {
                    "device_name": r["device_name"],
                    "kwh": kwh,
                    "pct": share_pct
                }
                if kwh < threshold_2_percent:
                    small_elec_list.append(device_info)
                else:
                    main_elec_list.append(device_info)
                    
        # Daten-Liste für Pie-Chart initialisieren
        elec_data = []
        
        # 1. Hauptgeräte hinzufügen (haben Standard-Hoverinfo)
        for item in main_elec_list:
            elec_data.append({
                "Sektor": item["device_name"], 
                "Verbrauch (kWh)": item["kwh"],
                "Hoverinfo": ""
            })
            
        # 2. Kleingeräte aggregieren und formatierten Tooltip-Text erstellen
        if small_elec_list:
            small_sum_kwh = sum(x["kwh"] for x in small_elec_list)
            
            # HTML-Formatierter Tooltip für die Plotly-Legendeneinblendung
            hover_text_lines = [
                f"• {x['device_name']}: {x['pct']:.1f}% ({x['kwh']:.1f} kWh)" 
                for x in small_elec_list
            ]
            hover_details = "<br>".join(hover_text_lines)
            
            elec_data.append({
                "Sektor": t("dev_label_other_small_devices"), 
                "Verbrauch (kWh)": small_sum_kwh,
                "Hoverinfo": hover_details
            })
            
        # 3. Unbekannten Rest hinzufügen
        if elec_unbekannt > 0:
            elec_data.append({
                "Sektor": t("dev_label_unbekannt_elec"), 
                "Verbrauch (kWh)": elec_unbekannt,
                "Hoverinfo": ""
            })
        
        df_elec_pie = pd.DataFrame(elec_data)
        
        # Interaktives Pie-Chart rendern
        fig_elec_share = px.pie(
            df_elec_pie,
            values="Verbrauch (kWh)",
            names="Sektor",
            title=t("dev_elec_pie_title"),
            template="plotly_dark",
            hole=0.4,
            custom_data=["Hoverinfo"] # Übergibt Tooltip-Informationen an Plotly
        )
        
        # Definiert das Hover-Verhalten: Zeigt bei den Kleingeräten die Liste an
        fig_elec_share.update_traces(
            hovertemplate="<b>%{label}</b><br>%{value:.1f} kWh (%{percent})<br>%{customdata[0]}<extra></extra>"
        )
        
        st.plotly_chart(fig_elec_share, width="stretch")
    else:
        st.info(t("dev_elec_insufficient_data"))

    # ---------------------------------------------------------
    # ERKLÄRBARKEITS-CHECK (KALTWASSER)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header(t("dev_water_explain_header"))
    
    if actual_annual_water > 0:
        sum_device_water = df_devices_calc["avg_yearly_water_m3"].sum()
        water_unbekannt = max(0.0, actual_annual_water - sum_device_water)
        explain_pct_water = min(100.0, (sum_device_water / actual_annual_water) * 100)
        
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric(
            t("dev_metric_actual_consumption"), 
            f"{actual_annual_water:,.2f} {t('dev_unit_m3_year')}", 
            t("dev_unit_eur_year_formatted").format(val=actual_annual_water * water_tariff), 
            delta_color="off"
        )
        wc2.metric(
            t("dev_metric_explained"), 
            f"{sum_device_water:,.2f} {t('dev_unit_m3_year')}", 
            t("dev_unit_eur_year_formatted").format(val=sum_device_water * water_tariff), 
            delta_color="off"
        )
        wc3.metric(
            t("dev_metric_quote"), 
            f"{explain_pct_water:.1f} %", 
            t("dev_unexplained_formatted").format(val=100.0 - explain_pct_water), 
            delta_color="inverse" if explain_pct_water < 80 else "normal"
        )
        
        # Analyse-Text Wasser
        st.markdown(f"**{t('dev_water_explain_analysis_title')}**")
        if explain_pct_water < 100:
            st.write(
                t("dev_water_explain_analysis_text").format(
                    pct=explain_pct_water,
                    rem_pct=100.0 - explain_pct_water,
                    unexplained_liters=water_unbekannt * 1000, # Mathematische Berechnung vorab gelöst!
                    unexplained_cost=water_unbekannt * water_tariff
                )
            )
        else:
            st.success(t("dev_water_explain_fully_covered"))
            
        # Pie-Chart
        water_data = [{"Sektor": r["device_name"], "Verbrauch (m³)": r["avg_yearly_water_m3"]} for _, r in df_devices_calc.iterrows() if r["avg_yearly_water_m3"] > 0]
        if water_unbekannt > 0:
            water_data.append({"Sektor": t("dev_label_unbekannt_water"), "Verbrauch (m³)": water_unbekannt})
            
        fig_water_share = px.pie(
            pd.DataFrame(water_data),
            values="Verbrauch (m³)",
            names="Sektor",
            title=t("dev_water_pie_title"),
            template="plotly_dark",
            hole=0.4
        )
        st.plotly_chart(fig_water_share, width="stretch")
    else:
        st.info(t("dev_water_insufficient_data"))

    # ---------------------------------------------------------
    # DEUTSCHE DURCHSCHNITTS-VERTEILUNG (BDEW)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header(t("dev_bdew_header"))
    st.write(t("dev_bdew_subtitle"))

    german_avg_annual_elec = 1600.0 if household_size == 1 else (2800.0 if household_size == 2 else (3900.0 if household_size == 3 else 3900.0 + ((household_size - 3) * 800.0)))
    german_avg_annual_water = household_size * 45.625

    german_elec_distribution = pd.DataFrame([
        {"Sektor": "Kühlen & Gefrieren", "Verbrauch (kWh)": german_avg_annual_elec * 0.17},
        {"Sektor": "Waschen & Trocknen", "Verbrauch (kWh)": german_avg_annual_elec * 0.14},
        {"Sektor": "Kochen", "Verbrauch (kWh)": german_avg_annual_elec * 0.10},
        {"Sektor": "Beleuchtung", "Verbrauch (kWh)": german_avg_annual_elec * 0.10},
        {"Sektor": "TV, PC & Entertainment", "Verbrauch (kWh)": german_avg_annual_elec * 0.27},
        {"Sektor": "Geschirrspülen", "Verbrauch (kWh)": german_avg_annual_elec * 0.08},
        {"Sektor": "Sonstiges", "Verbrauch (kWh)": german_avg_annual_elec * 0.14}
    ])

    german_water_distribution = pd.DataFrame([
        {"Sektor": "Baden, Duschen, Körperpflege", "Verbrauch (m³)": german_avg_annual_water * 0.36},
        {"Sektor": "Toilettenspülung", "Verbrauch (m³)": german_avg_annual_water * 0.27},
        {"Sektor": "Wäschewaschen", "Verbrauch (m³)": german_avg_annual_water * 0.12},
        {"Sektor": "Geschirrspülen", "Verbrauch (m³)": german_avg_annual_water * 0.06},
        {"Sektor": "Putzen, Garten, Auto", "Verbrauch (m³)": german_avg_annual_water * 0.06},
        {"Sektor": "Kochen & Trinken", "Verbrauch (m³)": german_avg_annual_water * 0.04},
        {"Sektor": "Sonstiges", "Verbrauch (m³)": german_avg_annual_water * 0.09}
    ])

    df_user_elec_grouped = df_devices_calc.groupby("device_group")["avg_yearly_consumption_kwh"].sum().reset_index()
    df_user_elec_grouped.columns = ["Sektor", t("dev_bdew_col_user_elec")]
    
    df_user_water_grouped = df_devices_calc.groupby("device_group")["avg_yearly_water_m3"].sum().reset_index()
    df_user_water_grouped.columns = ["Sektor", t("dev_bdew_col_user_water")]

    col_el, col_er = st.columns(2)
    
    with col_el:
        st.subheader(t("dev_bdew_elec_subheader"))
        df_comp_elec = pd.merge(german_elec_distribution, df_user_elec_grouped, on="Sektor", how="outer").fillna(0.0)
        df_melted_elec = df_comp_elec.melt(id_vars=["Sektor"], value_vars=["Verbrauch (kWh)", t("dev_bdew_col_user_elec")], var_name="Vergleich", value_name="kWh")
        df_melted_elec["Vergleich"] = df_melted_elec["Vergleich"].replace({"Verbrauch (kWh)": t("dev_bdew_legend_avg"), t("dev_bdew_col_user_elec"): t("dev_bdew_legend_user")})
        
        fig_bar_elec = px.bar(df_melted_elec, x="Sektor", y="kWh", color="Vergleich", barmode="group", template="plotly_dark", color_discrete_sequence=["#64748b", "#eab308"])
        st.plotly_chart(fig_bar_elec, width="stretch")
        
    with col_er:
        st.subheader(t("dev_bdew_water_subheader"))
        df_comp_water = pd.merge(german_water_distribution, df_user_water_grouped, on="Sektor", how="outer").fillna(0.0)
        df_melted_water = df_comp_water.melt(id_vars=["Sektor"], value_vars=["Verbrauch (m³)", t("dev_bdew_col_user_water")], var_name="Vergleich", value_name="m³")
        df_melted_water["Vergleich"] = df_melted_water["Vergleich"].replace({"Verbrauch (m³)": t("dev_bdew_legend_avg"), t("dev_bdew_col_user_water"): t("dev_bdew_legend_user")})
        
        fig_bar_water = px.bar(df_melted_water, x="Sektor", y="m³", color="Vergleich", barmode="group", template="plotly_dark", color_discrete_sequence=["#64748b", "#3b82f6"])
        st.plotly_chart(fig_bar_water, width="stretch")