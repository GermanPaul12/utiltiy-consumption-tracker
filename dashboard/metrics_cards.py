# dashboard/metrics_cards.py
import streamlit as st

def render(stats, rates, total_cost_all, avg_monthly_cost_all, projected_annual_cost, total_co2_all, total_days_tracked, global_standing_to_date, total_prepayments_to_date, global_projected_annual_standing, total_annual_prepayments):
    st.subheader("Global Estimates & Projections")
    g_col1, g_col2, g_col3, g_col4 = st.columns(4)
    g_col1.metric("Total Cumulative Expenses", f"€{total_cost_all:,.2f}")
    g_col2.metric("Average Monthly Cost", f"€{avg_monthly_cost_all:,.2f}")
    g_col3.metric("Projected Annual Cost", f"€{projected_annual_cost:,.2f}")
    g_col4.metric("Total CO₂ Footprint", f"{total_co2_all:,.1f} kg")
    
    st.markdown("### 🏠 Household Efficiency Metrics")
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    
    cost_per_occupant = total_cost_all / max(rates['household_size'], 1)
    cost_per_m2 = total_cost_all / max(rates['apartment_size'], 1.0)
    co2_per_day = total_co2_all / max(total_days_tracked, 1)
    
    e_col1.metric("Cost per Occupant", f"€{cost_per_occupant:,.2f}", help="Total accumulated expenses divided by household size.")
    e_col2.metric("Cost per Square Meter", f"€{cost_per_m2:,.2f}/m²", help="Total accumulated expenses divided by apartment size.")
    e_col3.metric("Daily Avg CO₂ Emissions", f"{co2_per_day:.2f} kg/day", help="Average carbon footprint generated per day across all utilities.")
    e_col4.metric("Active Tracked Period", f"{total_days_tracked} Days", help="Total aggregate calendar days currently tracked in the database.")

    st.markdown("---")
    
    st.subheader("Financial Balance & Prepayment Settlements")
    f_col1, f_col2 = st.columns(2)
    
    with f_col1:
        st.markdown("### 📅 Current Standing (To Date)")
        st.write("Calculated by comparing pro-rated prepayments paid so far against incurred costs:")
        if global_standing_to_date >= 0:
            st.success(f"**Current Refund Estimate:** €{global_standing_to_date:,.2f} (You have overpaid so far)")
        else:
            st.warning(f"**Current Underpayment Estimate:** €{abs(global_standing_to_date):,.2f} (You owe more than you paid so far)")
        st.write(f"*Total Prepayments Paid to Date:* €{total_prepayments_to_date:,.2f}")
        st.write(f"*Total Incurred Cost to Date:* €{total_cost_all:,.2f}")
        
    with f_col2:
        st.markdown("### 🔮 Annual Projection Settlement")
        st.write("Projects your current consumption habits to a full 12-month billing cycle:")
        if global_projected_annual_standing >= 0:
            st.success(f"**Projected Annual Refund (Guthaben):** €{global_projected_annual_standing:,.2f}")
        else:
            st.error(f"**Projected Annual Backpayment (Nachzahlung):** €{abs(global_projected_annual_standing):,.2f}")
        st.write(f"*Total Annual Prepayments:* €{total_annual_prepayments:,.2f}")
        st.write(f"*Projected Annual Costs:* €{projected_annual_cost:,.2f}")