# dashboard/history_timeline.py
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
            return "❄️ Winter (Dec-Feb)"
        elif month in [3, 4, 5]:
            return "🌱 Spring (Mar-May)"
        elif month in [6, 7, 8]:
            return "☀️ Summer (Jun-Aug)"
        else:
            return "🍂 Autumn (Sep-Nov)"
    except Exception:
        return "Unknown"

def render(processed_logs, stats, rates, color_map, plotly_template):
    st.subheader("Historical Timeline Graphs")
    has_sufficient_data = any(m.get("entries_count", 0) > 1 for m in stats.values())
    
    if not has_sufficient_data:
        st.info("Visual charts require at least two logged points to show historical progression.")
        return
        
    st.write("### 📅 Prorated Monthly Consumption, Trends & Seasonality")
    st.caption("This section displays your consumption distributed day-by-day and aggregated by calendar month, overlaid with rolling averages, change rates, and seasonal profiles.")
    
    monthly_allocated_data = calculate_monthly_allocated_consumption(processed_logs, rates)
    
    if monthly_allocated_data:
        # Sprachneutrale Zählerbezeichner
        meters = ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]
        headers = [t("dash_tab_elec"), t("dash_tab_hw"), t("dash_tab_cw")]
        
        # ---------------------------------------------------------
        # NEU: AUTOMATISCHER VOLL-BREAKDOWN OHNE SELECTBOX
        # ---------------------------------------------------------
        for meter_chart_name, header in zip(meters, headers):
            filtered_monthly = monthly_allocated_data.get(meter_chart_name)
            
            if filtered_monthly is not None and not filtered_monthly.empty:
                st.markdown("---")
                st.markdown(f"#### {header}")
                
                unit_label = meter_chart_name.split("(")[-1].replace(")", "")
                
                # 1. Monats-Trenddiagramm (Full Width)
                fig_allocated = go.Figure()
                
                fig_allocated.add_trace(go.Bar(
                    x=filtered_monthly['month'],
                    y=filtered_monthly['total_consumption'],
                    name='Monthly Consumption',
                    marker_color=color_map[meter_chart_name],
                    customdata=filtered_monthly[['total_cost']],
                    hovertemplate="<b>Month:</b> %{x}<br>" +
                                  f"<b>Consumption:</b> %{{y:.2f}} {unit_label}<br>" +
                                  "<b>Estimated Cost:</b> €%{customdata[0]:,.2f}<extra></extra>"
                ))
                
                fig_allocated.add_trace(go.Scatter(
                    x=filtered_monthly['month'],
                    y=filtered_monthly['rolling_3mo'],
                    name='3-Month Rolling Avg',
                    mode='lines+markers',
                    line=dict(color="#f43f5e" if meter_chart_name == "Electricity (kWh)" else "#10b981", width=3.5),
                    hovertemplate=f"<b>3-Month Trend:</b> %{{y:.2f}} {unit_label}<extra></extra>"
                ))
                
                fig_allocated.update_layout(
                    title=f"Calendar Monthly Consumption & 3-Month Trend Line - {header}",
                    xaxis_title="Month",
                    yaxis_title=f"Consumption ({unit_label})",
                    template=plotly_template,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_allocated, width="stretch")
                
                # 2. Detailanalysen (M-o-M & Saisonalität) nebeneinander im 2-Spalten-Layout
                col_adv1, col_col2 = st.columns(2)
                
                with col_adv1:
                    filtered_monthly['direction'] = filtered_monthly['mom_pct_change'].apply(
                        lambda val: "Saving (Decrease)" if val <= 0 else "Usage Increase"
                    )
                    
                    fig_mom = px.bar(
                        filtered_monthly,
                        x='month',
                        y='mom_pct_change',
                        color='direction',
                        color_discrete_map={"Saving (Decrease)": "#22c55e", "Usage Increase": "#ef4444"},
                        title=f"Month-over-Month Consumption Change Rate (%) - {header}",
                        labels={"mom_pct_change": "Change (%)", "month": "Month", "direction": "Trend"},
                        template=plotly_template
                    )
                    fig_mom.add_hline(y=0.0, line_color="#94a3b8", line_dash="dash")
                    st.plotly_chart(fig_mom, width="stretch")
                    
                with col_col2:
                    filtered_monthly['season'] = filtered_monthly['month'].apply(get_season_name)
                    df_seasonal = filtered_monthly.groupby('season').agg(
                        avg_consumption=('total_consumption', 'mean'),
                        avg_cost=('total_cost', 'mean')
                    ).reset_index()
                    
                    season_order = ["❄️ Winter (Dec-Feb)", "🌱 Spring (Mar-May)", "☀️ Summer (Jun-Aug)", "🍂 Autumn (Sep-Nov)"]
                    df_seasonal['season'] = pd.Categorical(df_seasonal['season'], categories=season_order, ordered=True)
                    df_seasonal = df_seasonal.sort_values('season')
                    
                    fig_season = px.bar(
                        df_seasonal,
                        x='season',
                        y='avg_consumption',
                        title=f"Average Consumption by Season - {header}",
                        labels={"avg_consumption": f"Average Usage ({unit_label})", "season": "Season"},
                        template=plotly_template,
                        color='season',
                        color_discrete_map={
                            "❄️ Winter (Dec-Feb)": "#38bdf8",
                            "🌱 Spring (Mar-May)": "#34d399",
                            "☀️ Summer (Jun-Aug)": "#f59e0b",
                            "🍂 Autumn (Sep-Nov)": "#fb7185"
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
                st.caption(f"Insufficient historical data to segment monthly allocated chart for {header}.")
    else:
        st.caption("Log more entries to calculate dynamic monthly tracking estimates.")
    
    st.markdown("---")

    # Kumulierter Gesamtverlauf über alle Messungen hinweg
    fig_cum = px.line(
        processed_logs[processed_logs['cumulative_cost'] > 0],
        x='date',
        y='cumulative_cost',
        color='meter',
        markers=True,
        title="Cumulative Spent Over Time (€)",
        labels={"cumulative_cost": "Total Spent (€)", "date": "Date"},
        template=plotly_template,
        color_discrete_map=color_map
    )
    st.plotly_chart(fig_cum, width="stretch")
    
    active_intervals = processed_logs[processed_logs['days_elapsed'] > 0]
    if not active_intervals.empty:
        # Tägliche finanzielle Burn-Rate
        fig_daily_cost = px.bar(
            active_intervals,
            x="date",
            y="daily_cost_rate",
            color="meter",
            title="Running Daily Financial Burn Rate (Standardized €/day)",
            labels={"daily_cost_rate": "Financial Burn Rate (€/day)", "date": "Date"},
            template=plotly_template,
            color_discrete_map=color_map
        )
        st.plotly_chart(fig_daily_cost, width="stretch")

        # Tägliche Verbrauchsänderung
        fig_rate = px.line(
            active_intervals,
            x='date',
            y='daily_rate',
            color='meter',
            markers=True,
            title="Usage Rate Changes Over Time (Consumption Unit / Day)",
            labels={"daily_rate": "Average Units Consumed per Day", "date": "Reading Date"},
            facet_col='meter',
            facet_col_wrap=3,
            category_orders={"meter": ["Electricity (kWh)", "Hot Water (MWh)", "Cold Water (m³)"]},
            template=plotly_template,
            color_discrete_map=color_map
        )
        fig_rate.update_yaxes(matches=None)
        st.plotly_chart(fig_rate, width="stretch")