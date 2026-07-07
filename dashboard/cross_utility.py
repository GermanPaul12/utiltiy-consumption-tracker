# dashboard/cross_utility.py
import pandas as pd
import streamlit as st
import plotly.express as px

def render(processed_logs, color_map, plotly_template):
    st.subheader("📈 Cross-Utility Normalization & Log Analysis")
    st.write(
        "Comparing utilities with vastly different scales (e.g., Megawatt hours of heating vs. Liters of water) "
        "is challenging. Below are two normalized, scale-free comparisons designed to balance these differences:"
    )
    
    active_intervals = processed_logs[processed_logs['days_elapsed'] > 0].copy()
    
    if len(active_intervals['meter'].unique()) > 1:
        col_norm1, col_norm2 = st.columns(2)
        
        with col_norm1:
            st.markdown("#### 💵 Logarithmic Daily Financial Burn Rate (€ / Day)")
            st.caption(
                "By converting physical units into daily financial costs (€/day), we establish a common scale. "
                "A **Logarithmic Y-Axis** ensures that small water costs (e.g., €0.20/day) remain visible alongside "
                "large electricity or heating spikes (e.g., €15.00/day)."
            )
            
            fig_log_burn = px.line(
                active_intervals,
                x='date',
                y='daily_cost_rate',
                color='meter',
                markers=True,
                title="Daily Burn Rate (€ / Day) - Logarithmic Scale",
                labels={"daily_cost_rate": "Burn Rate (€ / Day)", "date": "Reading Date", "meter": "Utility"},
                template=plotly_template,
                color_discrete_map=color_map
            )
            fig_log_burn.update_yaxes(type="log")
            st.plotly_chart(fig_log_burn, width="stretch")
            
        with col_norm2:
            st.markdown("#### 📊 Unit-Free Relative Fluctuations (% of baseline)")
            st.caption(
                "This chart normalizes all physical consumption units by expressing them as a percentage "
                "of your utility-specific average. This isolates behavioral changes from the scale of the unit."
            )
            
            normalized_list = []
            for meter_name in active_intervals['meter'].unique():
                sub_df = active_intervals[active_intervals['meter'] == meter_name].copy()
                avg_rate = sub_df['daily_rate'].mean()
                if avg_rate > 0:
                    sub_df['percent_of_baseline'] = (sub_df['daily_rate'] / avg_rate) * 100
                    normalized_list.append(sub_df)
            
            if normalized_list:
                df_normalized = pd.concat(normalized_list).sort_values(by='date')
                
                fig_norm_fluct = px.line(
                    df_normalized,
                    x='date',
                    y='percent_of_baseline',
                    color='meter',
                    markers=True,
                    title="Usage Fluctuations relative to Personal Baseline (Average = 100%)",
                    labels={"percent_of_baseline": "Relative Usage (% of Personal Average)", "date": "Reading Date"},
                    template=plotly_template,
                    color_discrete_map=color_map
                )
                fig_norm_fluct.add_hline(y=100.0, line_dash="dash", line_color="#64748b", annotation_text="Your Baseline (100%)")
                st.plotly_chart(fig_norm_fluct, width="stretch")
            else:
                st.caption("Insufficient usage delta to calculate standard baseline.")
                
        st.markdown("---")
    else:
        st.info("Log entries for at least two different utilities to activate cross-utility normalization metrics.")