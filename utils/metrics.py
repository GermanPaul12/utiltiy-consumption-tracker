# metrics.py
import datetime
import pandas as pd

# utils/metrics.py (Berechnungen filtern)

def calculate_metrics(logs_df, rates):
    if logs_df.empty:
        return pd.DataFrame(), {}

    meters_meta = {
        "Electricity (kWh)": {"rate_key": "electricity_kwh", "prep_key": "electricity_prepayment", "co2_factor": 0.380, "unit": "kWh"},
        "Hot Water (MWh)": {"rate_key": "hot_water_mwh", "prep_key": "hot_water_prepayment", "co2_factor": 90.0, "unit": "MWh"},
        "Cold Water (m³)": {"rate_key": "cold_water_m3", "prep_key": "cold_water_prepayment", "co2_factor": 0.35, "unit": "m³"}
    }
    
    # NEU: Das jüngste (späteste) Datum aus Einzug & Tarifstart bestimmen
    effective_start_date = None
    move_in = rates.get("move_in_date")
    tariff_start = rates.get("tariff_start_date")
    
    if move_in and tariff_start:
        # Ermittelt den mathematisch spätesten (jüngsten) Startpunkt
        effective_start_date = max(pd.to_datetime(move_in).date(), pd.to_datetime(tariff_start).date())

    processed_dfs = []
    summary_stats = {}
    
    for meter_name, meta in meters_meta.items():
        meter_df = logs_df[logs_df['meter'] == meter_name].copy()
        if meter_df.empty:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        
        # NEU: Filtere alle Einträge heraus, die VOR dem jüngsten Startdatum lagen
        if effective_start_date is not None:
            # Stellt sicher, dass das Datumsformat der Zählerstände übereinstimmt
            meter_df['date'] = pd.to_datetime(meter_df['date']).dt.date
            meter_df = meter_df[meter_df['date'] >= effective_start_date].copy()
            
        if meter_df.empty:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        
        meter_df['days_elapsed'] = meter_df['date'].diff().apply(lambda x: x.days if pd.notnull(x) else 0)
        meter_df['consumption'] = meter_df['reading'].diff().fillna(0)
        
        meter_df['daily_rate'] = meter_df.apply(
            lambda row: row['consumption'] / row['days_elapsed'] if row['days_elapsed'] > 0 else 0,
            axis=1
        )
        
        unit_rate = rates[meta["rate_key"]]
        monthly_prepayment = rates.get(meta["prep_key"], 0.0)
        
        meter_df['cost'] = meter_df['consumption'] * unit_rate
        meter_df['daily_cost_rate'] = meter_df['daily_rate'] * unit_rate
        meter_df['cumulative_cost'] = meter_df['cost'].cumsum()
        meter_df['co2_emissions'] = meter_df['consumption'] * meta["co2_factor"]
        
        processed_dfs.append(meter_df)
        
        entries_count = len(meter_df)
        if entries_count > 1:
            first_date = meter_df['date'].iloc[0]
            last_date = meter_df['date'].iloc[-1]
            total_days = (last_date - first_date).days
            total_days = max(total_days, 1)
            
            total_consumption = meter_df['reading'].iloc[-1] - meter_df['reading'].iloc[0]
            avg_daily_consumption = total_consumption / total_days
            avg_daily_cost = avg_daily_consumption * unit_rate
            total_co2 = total_consumption * meta["co2_factor"]
            
            if meter_name == "Electricity (kWh)":
                daily_base = rates["electricity_base"] / 30.44
                avg_daily_cost += daily_base
                total_base_cost = (total_days / 30.44) * rates["electricity_base"]
                total_cost = (total_consumption * unit_rate) + total_base_cost
            else:
                total_cost = total_consumption * unit_rate
                
            avg_monthly_consumption = avg_daily_consumption * 30.44
            avg_monthly_cost = avg_daily_cost * 30.44
            
            elapsed_months = total_days / 30.44
            prepayment_paid_to_date = monthly_prepayment * elapsed_months
            standing_to_date = prepayment_paid_to_date - total_cost
            
            annual_prepayment = monthly_prepayment * 12
            projected_annual_cost = avg_daily_cost * 365.25
            projected_annual_standing = annual_prepayment - projected_annual_cost
            
            max_period = meter_df[meter_df['days_elapsed'] > 0]
            peak_daily_rate = max_period['daily_rate'].max() if not max_period.empty else 0.0
            
            summary_stats[meter_name] = {
                "unit": meta["unit"],
                "entries_count": entries_count,
                "first_date": first_date,
                "last_date": last_date,
                "days_since_last": (datetime.date.today() - last_date).days,
                "total_days": total_days,
                "total_consumption": total_consumption,
                "total_cost": total_cost,
                "total_co2": total_co2,
                "monthly_prepayment": monthly_prepayment,
                "prepayment_paid_to_date": prepayment_paid_to_date,
                "standing_to_date": standing_to_date,
                "projected_annual_cost": projected_annual_cost,
                "annual_prepayment": annual_prepayment,
                "projected_annual_standing": projected_annual_standing,
                "avg_daily_consumption": avg_daily_consumption,
                "avg_daily_cost": avg_daily_cost,
                "avg_monthly_consumption": avg_monthly_consumption,
                "avg_monthly_cost": avg_monthly_cost,
                "peak_daily_rate": peak_daily_rate,
                "last_reading": meter_df['reading'].iloc[-1]
            }
        else:
            summary_stats[meter_name] = {
                "unit": meta["unit"],
                "entries_count": entries_count,
                "last_reading": meter_df['reading'].iloc[-1],
                "last_date": meter_df['date'].iloc[-1],
                "days_since_last": (datetime.date.today() - meter_df['date'].iloc[-1]).days,
                "total_consumption": 0.0,
                "total_cost": 0.0,
                "total_co2": 0.0,
                "monthly_prepayment": monthly_prepayment,
                "prepayment_paid_to_date": 0.0,
                "standing_to_date": 0.0,
                "projected_annual_cost": 0.0,
                "annual_prepayment": monthly_prepayment * 12,
                "projected_annual_standing": 0.0,
                "avg_daily_consumption": 0.0,
                "avg_daily_cost": 0.0,
                "avg_monthly_consumption": 0.0,
                "avg_monthly_cost": 0.0,
                "peak_daily_rate": 0.0
            }
        
    if not processed_dfs:
        return pd.DataFrame(), {}
        
    combined_df = pd.concat(processed_dfs).sort_values(by='date')
    return combined_df, summary_stats