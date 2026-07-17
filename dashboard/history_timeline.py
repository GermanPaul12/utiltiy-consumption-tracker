# dashboard/history_timeline.py (Fehlerfrei korrigiert)
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from utils.i18n import t  # Importiert das Übersetzungsmodul
from .calculations import calculate_monthly_allocated_consumption

def get_season_name(month_str):
    try:
        month = int(month_str.split("-")[1])
        if month in [12, 1, 2]:
            return t("ht_season_winter")
        elif month in [3, 4, 5]:
            return t("ht_season_spring")
        elif month in [6, 7, 8]:
            return t("ht_season_summer")
        else:
            return t("ht_season_autumn")
    except Exception:
        return t("ht_season_unknown")

def render(processed_logs, stats, rates, color_map, plotly_template):
    st.subheader(t("ht_header"))
    has_sufficient_data = any(m.get("entries_count", 0) > 1 for m in stats.values())
    
    if not has_sufficient_data:
        st.info("Visual charts require at least two logged points to show historical progression.")
        return
        
    st.write(f"### {t('ht_subheader')}")
    st.caption(t("ht_desc"))
    
    monthly_allocated_data = calculate_monthly_allocated_consumption(processed_logs, rates)
    
    # Zuordnungstabelle der Übersetzungsschlüssel für Zähler
    option_key_map = {
        "Electricity (kWh)": "log_option_elec",
        "Hot Water (MWh)": "log_option_hw",
        "Cold Water (m³)": "log_option_cw"
    }

    if monthly_allocated_data:
        meters = ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
        headers = [t("dash_tab_elec"), t("dash_tab_hw"), t("dash_tab_cw")]
        
        for meter_chart_name, header in zip(meters, headers):
            filtered_monthly = monthly_allocated_data.get(meter_chart_name)
            
            if filtered_monthly is not None and not filtered_monthly.empty:
                st.markdown("---")
                
                col_chart_l, col_chart_r = st.columns([3, 2])
                unit_label = meter_chart_name.split("(")[-1].replace(")", "")
                
                with col_chart_l:
                    # 1. Monats-Trenddiagramm
                    fig_allocated = go.Figure()
                    
                    fig_allocated.add_trace(go.Bar(
                        x=filtered_monthly['month'],
                        y=filtered_monthly['total_consumption'],
                        name=t("ht_monthly_consumption"),
                        marker_color=color_map[meter_chart_name],
                        customdata=filtered_monthly[['total_cost']],
                        hovertemplate="<b>Month:</b> %{x}<br>" +
                                      f"<b>Consumption:</b> %{{y:.2f}} {unit_label}<br>" +
                                      "<b>Estimated Cost:</b> €%{customdata[0]:,.2f}<extra></extra>"
                    ))
                    
                    fig_allocated.add_trace(go.Scatter(
                        x=filtered_monthly['month'],
                        y=filtered_monthly['rolling_3mo'],
                        name=t("ht_rolling_avg"),
                        mode='lines+markers',
                        line=dict(color="#f43f5e" if meter_chart_name == "Electricity (kWh)" else "#10b981", width=3.5),
                        hovertemplate=f"<b>3-Month Trend:</b> %{{y:.2f}} {unit_label}<extra></extra>"
                    ))
                    
                    fig_allocated.update_layout(
                        title=t("ht_title_monthly_trend").format(header=header),
                        xaxis_title=t("ht_label_month"),
                        yaxis_title=t("ht_label_consumption").format(unit=unit_label),
                        template=plotly_template,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_allocated, width="stretch")
                    
                with col_chart_r:
                    # 2. Saisonalitäts-Profil
                    # NEU: Zuweisung der Jahreszeit vor der Gruppierung (Löst KeyError)
                    filtered_monthly['season'] = filtered_monthly['month'].apply(get_season_name)
                    
                    df_seasonal = filtered_monthly.groupby('season').agg(
                        avg_consumption=('total_consumption', 'mean'),
                        avg_cost=('total_cost', 'mean')
                    ).reset_index()
                    
                    # Sortiert Jahreszeiten chronologisch
                    season_order = [t("ht_season_winter"), t("ht_season_spring"), t("ht_season_summer"), t("ht_season_autumn")]
                    df_seasonal['season'] = pd.Categorical(df_seasonal['season'], categories=season_order, ordered=True)
                    df_seasonal = df_seasonal.sort_values('season')
                    
                    fig_season = px.bar(
                        df_seasonal,
                        x='season',
                        y='avg_consumption',
                        title=t("ht_title_season").format(header=header),
                        labels={
                            "avg_consumption": t("ht_label_avg_usage").format(unit=unit_label), 
                            "season": t("ht_label_season")
                        },
                        template=plotly_template,
                        color='season',
                        color_discrete_map={
                            t("ht_season_winter"): "#38bdf8",
                            t("ht_season_spring"): "#34d399",
                            t("ht_season_summer"): "#f59e0b",
                            t("ht_season_autumn"): "#fb7185"
                        }
                    )
                    fig_season.update_traces(
                        hovertemplate="<b>Season:</b> %{x}<br>" +
                                      f"<b>Avg Consumption:</b> %{{y:.2f}} {unit_label}<br>" +
                                      "<b>Avg Monthly Cost:</b> €%{customdata[0]:,.2f}<extra></extra>",
                        customdata=df_seasonal[['avg_cost']]
                    )
                    st.plotly_chart(fig_season, width="stretch")
            else:
                st.caption(t("dash_insufficient_data"))
    else:
        st.caption("Log more entries to calculate dynamic monthly tracking estimates.")
    
    st.markdown("---")

    # ---------------------------------------------------------
    # ÜBERGREIFENDE SPEZIAL-PLOTS (DYNAMISCH ÜBERSETZT)
    # ---------------------------------------------------------
    active_intervals = processed_logs[processed_logs['days_elapsed'] > 0].copy()
    
    if not active_intervals.empty:
        # Erzeugt ein Duplikat mit übersetzten Zähler-Legenden
        active_intervals_display = active_intervals.copy()
        active_intervals_display["translated_meter"] = active_intervals_display["meter"].apply(lambda m: t(option_key_map.get(m, m)))
        
        # Übersetztes Farbschema für Plotly Legenden
        translated_color_map = {t(option_key_map.get(k, k)): v for k, v in color_map.items()}

        # 1. Tägliche finanzielle Burn-Rate (Einziger übergreifender Kosten-Plot)
        fig_daily_cost = px.bar(
            active_intervals_display,
            x="date",
            y="daily_cost_rate",
            color="translated_meter",
            title=t("ht_title_burn"),
            labels={"daily_cost_rate": t("ht_label_burn_rate"), "date": t("ht_label_date"), "translated_meter": t("cu_label_utility")},
            template=plotly_template,
            color_discrete_map=translated_color_map
        )
        st.plotly_chart(fig_daily_cost, width="stretch")

        # 2. Tägliche Verbrauchsratenschwankung (Zählereinheit / Tag)
        translated_categories = [t("log_option_elec"), t("log_option_hw"), t("log_option_cw")]
        
        fig_rate = px.line(
            active_intervals_display,
            x='date',
            y='daily_rate',
            color='translated_meter',
            markers=True,
            title=t("ht_title_usage_changes"),
            labels={
                "daily_rate": t("ht_label_avg_units_day"), 
                "date": t("ht_label_reading_date"),
                "translated_meter": t("cu_label_utility")
            },
            facet_col='translated_meter',
            facet_col_wrap=3,
            category_orders={"translated_meter": translated_categories},
            template=plotly_template,
            color_discrete_map=translated_color_map
        )
        fig_rate.update_yaxes(matches=None)
        st.plotly_chart(fig_rate, width="stretch")