# dashboard/cross_utility.py
import pandas as pd
import streamlit as st
import plotly.express as px
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render(processed_logs, color_map, plotly_template):
    st.subheader(t("cu_header"))
    st.write(t("cu_subtitle"))
    
    active_intervals = processed_logs[processed_logs['days_elapsed'] > 0].copy()
    
    # Zuordnungstabelle der Übersetzungsschlüssel für die Legenden
    option_key_map = {
        "Electricity (kWh)": "log_option_elec",
        "Hot Water (MWh)": "log_option_hw",
        "Cold Water (m³)": "log_option_cw"
    }

    if len(active_intervals['meter'].unique()) > 1:
        # Dynamische Übersetzung der Legenden-Namen im verarbeiteten DataFrame
        active_intervals["translated_meter"] = active_intervals["meter"].apply(lambda m: t(option_key_map.get(m, m)))
        
        # Generiert ein übersetztes Color-Mapping für Plotly
        translated_color_map = {t(option_key_map.get(k, k)): v for k, v in color_map.items()}

        col_norm1, col_norm2 = st.columns(2)
        
        with col_norm1:
            st.markdown(t("cu_burn_header"))
            st.caption(t("cu_burn_desc"))
            
            fig_log_burn = px.line(
                active_intervals,
                x='date',
                y='daily_cost_rate',
                color='translated_meter',
                markers=True,
                title=t("cu_burn_title"),
                labels={
                    "daily_cost_rate": t("cu_burn_y_label"), 
                    "date": t("cu_label_date"), 
                    "translated_meter": t("cu_label_utility")
                },
                template=plotly_template,
                color_discrete_map=translated_color_map
            )
            fig_log_burn.update_yaxes(type="log")
            st.plotly_chart(fig_log_burn, width="stretch")
            
        with col_norm2:
            st.markdown(t("cu_fluct_header"))
            st.caption(t("cu_fluct_desc"))
            
            normalized_list = []
            for meter_name in active_intervals['meter'].unique():
                sub_df = active_intervals[active_intervals['meter'] == meter_name].copy()
                avg_rate = sub_df['daily_rate'].mean()
                if avg_rate > 0:
                    sub_df['percent_of_baseline'] = (sub_df['daily_rate'] / avg_rate) * 100
                    normalized_list.append(sub_df)
            
            if normalized_list:
                df_normalized = pd.concat(normalized_list).sort_values(by='date')
                df_normalized["translated_meter"] = df_normalized["meter"].apply(lambda m: t(option_key_map.get(m, m)))
                
                fig_norm_fluct = px.line(
                    df_normalized,
                    x='date',
                    y='percent_of_baseline',
                    color='translated_meter',
                    markers=True,
                    title=t("cu_fluct_title"),
                    labels={
                        "percent_of_baseline": t("cu_fluct_y_label"), 
                        "date": t("cu_label_date"),
                        "translated_meter": t("cu_label_utility")
                    },
                    template=plotly_template,
                    color_discrete_map=translated_color_map
                )
                fig_norm_fluct.add_hline(
                    y=100.0, 
                    line_dash="dash", 
                    line_color="#64748b", 
                    annotation_text=t("cu_fluct_baseline_annotation")
                )
                st.plotly_chart(fig_norm_fluct, width="stretch")
            else:
                st.caption(t("cu_insufficient_delta"))
                
        st.markdown("---")
    else:
        st.info(t("cu_no_utilities"))