# dashboard/metrics_cards.py
import streamlit as st
from utils.i18n import t  # Importiert das Übersetzungsmodul

def render(stats, rates, total_cost_all, avg_monthly_cost_all, projected_annual_cost, total_co2_all, total_days_tracked, global_standing_to_date, total_prepayments_to_date, global_projected_annual_standing, total_annual_prepayments):
    st.subheader(t("mc_global_header"))
    g_col1, g_col2, g_col3, g_col4 = st.columns(4)
    g_col1.metric(t("mc_metric_total_expenses"), f"€{total_cost_all:,.2f}")
    g_col2.metric(t("mc_metric_avg_monthly_cost"), f"€{avg_monthly_cost_all:,.2f}")
    g_col3.metric(t("mc_metric_projected_annual_cost"), f"€{projected_annual_cost:,.2f}")
    g_col4.metric(t("mc_metric_total_co2"), f"{total_co2_all:,.1f} kg")
    
    st.markdown(t("mc_efficiency_header"))
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    
    cost_per_occupant = total_cost_all / max(rates['household_size'], 1)
    cost_per_m2 = total_cost_all / max(rates['apartment_size'], 1.0)
    co2_per_day = total_co2_all / max(total_days_tracked, 1)
    
    e_col1.metric(t("mc_metric_cost_per_occupant"), f"€{cost_per_occupant:,.2f}", help=t("mc_help_cost_per_occupant"))
    e_col2.metric(t("mc_metric_cost_per_m2"), f"€{cost_per_m2:,.2f}/m²", help=t("mc_help_cost_per_m2"))
    e_col3.metric(t("mc_metric_daily_avg_co2"), f"{co2_per_day:.2f} kg/day", help=t("mc_help_daily_avg_co2"))
    e_col4.metric(t("mc_metric_active_period"), f"{total_days_tracked} Days", help=t("mc_help_active_period"))

    st.markdown("---")
    
    st.subheader(t("mc_financial_header"))
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        st.markdown(t("mc_standing_header"))
        st.write(t("mc_standing_desc"))
        
        if global_standing_to_date >= 0:
            st.success(t("mc_standing_refund_text").format(val=global_standing_to_date))
        else:
            st.warning(t("mc_standing_underpay_text").format(val=abs(global_standing_to_date)))
            
        st.write(t("mc_standing_prepayments_paid").format(val=total_prepayments_to_date))
        st.write(t("mc_standing_incurred_cost").format(val=total_cost_all))
        
    with f_col2:
        st.markdown(t("mc_annual_header"))
        st.write(t("mc_annual_desc"))
        
        if global_projected_annual_standing >= 0:
            st.success(t("mc_annual_refund_text").format(val=global_projected_annual_standing))
        else:
            st.error(t("mc_annual_backpayment_text").format(val=abs(global_projected_annual_standing)))
            
        st.write(t("mc_annual_total_prepayments").format(val=total_annual_prepayments))
        st.write(t("mc_annual_projected_costs").format(val=projected_annual_cost))