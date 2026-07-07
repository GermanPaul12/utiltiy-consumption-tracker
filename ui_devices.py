# ui_devices.py
import streamlit as st
import pandas as pd
import plotly.express as px
import database as db

def render_page(current_user_id, stats, rates):
    st.title("Haushaltsgeräte & Benchmark-Analyse")
    st.write("Detaillierte Analyse Ihrer statischen Haushaltsgeräte, deren Erklärungsrate am Gesamtverbrauch und die jährlichen Kosten.")
    
    # Haushalts- und Tarifparameter abrufen
    household_size = max(int(rates.get("household_size", 1)), 1)
    apartment_size = max(float(rates.get("apartment_size", 50.0)), 1.0)
    
    elec_tariff = float(rates.get("electricity_kwh", 0.282))
    water_tariff = float(rates.get("cold_water_m3", 4.50))
    
    st.info(
        f"ℹ️ Berechnungsgrundlage: **{household_size} Person(en)** | "
        f"Stromtarif: **{elec_tariff:.4f} €/kWh** | Kaltwassertarif: **{water_tariff:.2f} €/m³**"
    )

    df_devices = db.load_devices(current_user_id)
    
    if df_devices.empty:
        st.warning("Sie haben noch keine Geräte spezifiziert. Gehen Sie auf 'Profile & Tariff Settings', um Ihre Geräte anzulegen.")
        return

    # Hochgerechnete Jahreswerte aus manuellen Zählerständen
    actual_annual_elec = stats.get("Electricity (kWh)", {}).get("avg_daily_consumption", 0.0) * 365.25
    actual_annual_water = stats.get("Cold Water (m³)", {}).get("avg_daily_consumption", 0.0) * 365.25

    # ---------------------------------------------------------
    # FINANZIELLE BERWERTUNG & TOP-VERBRAUCHER DER GERÄTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.header("💵 Finanzielle Bewertung Ihrer Haushaltsgeräte")
    st.write("Hier sehen Sie die hochgerechneten jährlichen Betriebskosten Ihrer Geräte basierend auf Ihren Tarifen:")

    # Kostenberechnungen für jedes Gerät hinzufügen
    df_devices["yearly_elec_cost"] = df_devices["avg_yearly_consumption_kwh"] * elec_tariff
    df_devices["yearly_water_cost"] = df_devices["avg_yearly_water_m3"] * water_tariff
    df_devices["total_yearly_cost"] = df_devices["yearly_elec_cost"] + df_devices["yearly_water_cost"]

    # Sortieren nach den teuersten Verbrauchern
    df_devices_sorted = df_devices.sort_values(by="total_yearly_cost", ascending=False)

    col_t1, col_t2 = st.columns([3, 2])
    
    with col_t1:
        st.markdown("##### 🏆 Rangliste der Kostenfaktoren (€ / Jahr)")
        fig_cost_drivers = px.bar(
            df_devices_sorted,
            x="total_yearly_cost",
            y="device_name",
            orientation="h",
            color="device_group",
            title="Jährliche Betriebskosten nach Gerät",
            labels={"total_yearly_cost": "Kosten (€ / Jahr)", "device_name": "Gerät", "device_group": "Kategorie"},
            template="plotly_dark"
        )
        # Sortierung auf der Y-Achse beibehalten (teuerstes oben)
        fig_cost_drivers.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_cost_drivers, width="stretch")
        
    with col_t2:
        st.markdown("##### 📋 Gerätespezifische Kostenübersicht")
        st.dataframe(
            df_devices_sorted[[
                "device_name", "device_group", "avg_yearly_consumption_kwh", 
                "avg_yearly_water_m3", "total_yearly_cost"
            ]].rename(columns={
                "device_name": "Gerät",
                "device_group": "Kategorie",
                "avg_yearly_consumption_kwh": "Strom (kWh/J)",
                "avg_yearly_water_m3": "Wasser (m³/J)",
                "total_yearly_cost": "Kosten (€/Jahr)"
            }),
            width="stretch"
        )

    # ---------------------------------------------------------
    # ERKLÄRBARKEITS-CHECK (STROM)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header("⚡ Erklärungsrate Stromverbrauch (Wohnung)")
    
    if actual_annual_elec > 0:
        sum_device_elec = df_devices["avg_yearly_consumption_kwh"].sum()
        elec_unbekannt = max(0.0, actual_annual_elec - sum_device_elec)
        explain_pct_elec = min(100.0, (sum_device_elec / actual_annual_elec) * 100)
        
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("Tatsächlicher Verbrauch", f"{actual_annual_elec:,.0f} kWh/Jahr", f"€{actual_annual_elec*elec_tariff:,.2f}/Jahr", delta_color="off")
        ec2.metric("Durch Geräte erklärt", f"{sum_device_elec:,.0f} kWh/Jahr", f"€{sum_device_elec*elec_tariff:,.2f}/Jahr", delta_color="off")
        ec3.metric("Erklärungs-Quote", f"{explain_pct_elec:.1f} %", f"Unerklärt: {100 - explain_pct_elec:.1f} %", delta_color="inverse" if explain_pct_elec < 80 else "normal")
        
        # Analyse-Text
        st.markdown("**🔍 Analyse des Stromverbrauchs:**")
        if explain_pct_elec < 100:
            st.write(
                f"Ihre Haushaltsgeräte erklären **{explain_pct_elec:.1f}%** Ihres Stromverbrauchs. "
                f"Die restlichen **{100 - explain_pct_elec:.1f}%** ({elec_unbekannt:,.0f} kWh / ca. **€{elec_unbekannt*elec_tariff:,.2f}** pro Jahr) "
                "entstehen durch alltägliche Grundlasten, die Sie nicht als separates Gerät erfasst haben. "
                "Dazu gehören typischerweise: "
                "\n* **Standby-Verbräuche & Kleingeräte** (Staubsauger, Wasserkocher, Toaster, Ladegeräte)"
                "\n* **WLAN-Router & Modems** (laufen 24/7 und verbrauchen ca. 60–100 kWh/Jahr)"
                "\n* **Deckenbeleuchtungen** in der gesamten Wohnung"
            )
        else:
            st.success(
                "💡 Ihre eingetragenen Geräte decken Ihren tatsächlichen Stromverbrauch vollständig ab. "
                "Dies deutet auf eine sehr effiziente Haushaltsführung oder großzügig bemessene Sollwerte hin."
            )
            
        # Pie-Chart
        elec_data = [{"Sektor": r["device_name"], "Verbrauch (kWh)": r["avg_yearly_consumption_kwh"]} for _, r in df_devices.iterrows() if r["avg_yearly_consumption_kwh"] > 0]
        if elec_unbekannt > 0:
            elec_data.append({"Sektor": "Unbekannt (Rest / Grundlast)", "Verbrauch (kWh)": elec_unbekannt})
        
        fig_elec_share = px.pie(
            pd.DataFrame(elec_data),
            values="Verbrauch (kWh)",
            names="Sektor",
            title="Zusammensetzung des gesamten Strom-Jahresverbrauchs",
            template="plotly_dark",
            hole=0.4
        )
        st.plotly_chart(fig_elec_share, width="stretch")
    else:
        st.info("Tragen Sie mindestens zwei Stromzählerstände ein, um die Erklärbarkeits-Analyse zu aktivieren.")

    # ---------------------------------------------------------
    # ERKLÄRBARKEITS-CHECK (KALTWASSER)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header("💧 Erklärungsrate Kaltwasserverbrauch")
    
    if actual_annual_water > 0:
        sum_device_water = df_devices["avg_yearly_water_m3"].sum()
        water_unbekannt = max(0.0, actual_annual_water - sum_device_water)
        explain_pct_water = min(100.0, (sum_device_water / actual_annual_water) * 100)
        
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric("Tatsächlicher Verbrauch", f"{actual_annual_water:,.2f} m³/Jahr", f"€{actual_annual_water*water_tariff:,.2f}/Jahr", delta_color="off")
        wc2.metric("Durch Geräte erklärt", f"{sum_device_water:,.2f} m³/Jahr", f"€{sum_device_water*water_tariff:,.2f}/Jahr", delta_color="off")
        wc3.metric("Erklärungs-Quote", f"{explain_pct_water:.1f} %", f"Unerklärt: {100 - explain_pct_water:.1f} %", delta_color="inverse" if explain_pct_water < 80 else "normal")
        
        # Analyse-Text
        st.markdown("**🔍 Analyse des Kaltwasserverbrauchs:**")
        if explain_pct_water < 100:
            st.write(
                f"Ihre erfassten Geräte erklären **{explain_pct_water:.1f}%** Ihres Wasserverbrauchs. "
                f"Die verbleibenden **{100 - explain_pct_water:.1f}%** ({water_unbekannt*1000:,.0f} Liter / ca. **€{water_unbekannt*water_tariff:,.2f}** pro Jahr) "
                "lassen sich durch manuelle Tätigkeiten im Haushalt erklären, die nicht direkt über Großgeräte abgedeckt sind:"
                "\n* **Tägliche Körperpflege** (Händewaschen, Zähneputzen, Duschen/Baden)"
                "\n* **Manuelles Spülen** in der Küche sowie Kochen & Trinken"
                "\n* **Hausarbeits-Verbräuche** wie Putzen, Pflanzen gießen oder Toilettenspülungen (falls nicht separat erfasst)"
            )
        else:
            st.success(
                "💡 Der Wasserverbrauch Ihrer Geräte deckt den gemessenen Kaltwasserverbrauch vollständig ab."
            )
            
        # Pie-Chart
        water_data = [{"Sektor": r["device_name"], "Verbrauch (m³)": r["avg_yearly_water_m3"]} for _, r in df_devices.iterrows() if r["avg_yearly_water_m3"] > 0]
        if water_unbekannt > 0:
            water_data.append({"Sektor": "Unbekannt (Rest / Manueller Verbrauch)", "Verbrauch (m³)": water_unbekannt})
            
        fig_water_share = px.pie(
            pd.DataFrame(water_data),
            values="Verbrauch (m³)",
            names="Sektor",
            title="Zusammensetzung des gesamten Kaltwasser-Jahresverbrauchs",
            template="plotly_dark",
            hole=0.4
        )
        st.plotly_chart(fig_water_share, width="stretch")
    else:
        st.info("Tragen Sie mindestens zwei Kaltwasser-Zählerstände ein, um die Erklärbarkeits-Analyse zu aktivieren.")

    # ---------------------------------------------------------
    # DEUTSCHE DURCHSCHNITTS-VERTEILUNG (BDEW)
    # ---------------------------------------------------------
    st.markdown("---")
    st.header("📊 Vergleich mit dem deutschen Durchschnitt (BDEW)")
    st.write("Vergleichen Sie Ihre erfassten Verbrauchergruppen mit dem standardisierten Verteilungsmuster in Deutschland:")

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

    df_user_elec_grouped = df_devices.groupby("device_group")["avg_yearly_consumption_kwh"].sum().reset_index()
    df_user_elec_grouped.columns = ["Sektor", "Ihr Verbrauch (kWh)"]
    
    df_user_water_grouped = df_devices.groupby("device_group")["avg_yearly_water_m3"].sum().reset_index()
    df_user_water_grouped.columns = ["Sektor", "Ihr Verbrauch (m³)"]

    col_el, col_er = st.columns(2)
    
    with col_el:
        st.subheader("⚡ Strom-Kategorien (kWh / Jahr)")
        df_comp_elec = pd.merge(german_elec_distribution, df_user_elec_grouped, on="Sektor", how="outer").fillna(0.0)
        df_melted_elec = df_comp_elec.melt(id_vars=["Sektor"], value_vars=["Verbrauch (kWh)", "Ihr Verbrauch (kWh)"], var_name="Vergleich", value_name="kWh")
        df_melted_elec["Vergleich"] = df_melted_elec["Vergleich"].replace({"Verbrauch (kWh)": "Dt. Durchschnitt", "Ihr Verbrauch (kWh)": "Ihre Geräte"})
        
        fig_bar_elec = px.bar(df_melted_elec, x="Sektor", y="kWh", color="Vergleich", barmode="group", template="plotly_dark", color_discrete_sequence=["#64748b", "#eab308"])
        st.plotly_chart(fig_bar_elec, width="stretch")
        
    with col_er:
        st.subheader("💧 Wasser-Kategorien (m³ / Jahr)")
        df_comp_water = pd.merge(german_water_distribution, df_user_water_grouped, on="Sektor", how="outer").fillna(0.0)
        df_melted_water = df_comp_water.melt(id_vars=["Sektor"], value_vars=["Verbrauch (m³)", "Ihr Verbrauch (m³)"], var_name="Vergleich", value_name="m³")
        df_melted_water["Vergleich"] = df_melted_water["Vergleich"].replace({"Verbrauch (m³)": "Dt. Durchschnitt", "Ihr Verbrauch (m³)": "Ihre Geräte"})
        
        fig_bar_water = px.bar(df_melted_water, x="Sektor", y="m³", color="Vergleich", barmode="group", template="plotly_dark", color_discrete_sequence=["#64748b", "#3b82f6"])
        st.plotly_chart(fig_bar_water, width="stretch")