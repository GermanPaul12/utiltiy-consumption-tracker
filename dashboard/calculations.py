# dashboard/calculations.py
import datetime
import pandas as pd

def calculate_monthly_allocated_consumption(processed_logs, rates):
    if processed_logs.empty:
        return {}
        
    meters_meta = {
        "Electricity (kWh)": {"rate_key": "electricity_kwh", "unit": "kWh"},
        "Hot Water (MWh)": {"rate_key": "hot_water_mwh", "unit": "MWh"},
        "Cold Water (m³)": {"rate_key": "cold_water_m3", "unit": "m³"}
    }
    
    today = datetime.date.today()
    start_period = today - datetime.timedelta(days=365)
    date_range = pd.date_range(start=start_period, end=today).date
    
    monthly_data = {}
    
    for meter_name, meta in meters_meta.items():
        meter_df = processed_logs[processed_logs['meter'] == meter_name].copy()
        if len(meter_df) < 2:
            continue
            
        meter_df = meter_df.sort_values(by='date')
        df_days = pd.DataFrame({"date": date_range})
        df_days['rate'] = 0.0
        
        last_rate = 0.0
        last_date = None
        
        for j in range(1, len(meter_df)):
            start = meter_df.iloc[j-1]['date']
            end = meter_df.iloc[j]['date']
            days = (end - start).days
            if days > 0:
                rate = (meter_df.iloc[j]['reading'] - meter_df.iloc[j-1]['reading']) / days
                df_days.loc[(df_days['date'] > start) & (df_days['date'] <= end), 'rate'] = rate
                last_rate = rate
                last_date = end
                
        if last_date is not None:
            df_days.loc[df_days['date'] > last_date, 'rate'] = last_rate
            
        unit_rate = rates[meta["rate_key"]]
        if meter_name == "Electricity (kWh)":
            daily_base = rates["electricity_base"] / 30.44
            df_days['cost'] = df_days.apply(
                lambda r: (r['rate'] * unit_rate) + daily_base if r['rate'] > 0 else 0.0, 
                axis=1
            )
        else:
            df_days['cost'] = df_days['rate'] * unit_rate
            
        df_days = df_days[df_days['rate'] > 0]
        
        if df_days.empty:
            continue
            
        df_days['month'] = pd.to_datetime(df_days['date']).dt.to_period('M').astype(str)
        df_monthly = df_days.groupby('month').agg(
            total_consumption=('rate', 'sum'),
            total_cost=('cost', 'sum')
        ).reset_index()
        
        df_monthly['rolling_3mo'] = df_monthly['total_consumption'].rolling(window=3, min_periods=1).mean()
        df_monthly['mom_pct_change'] = df_monthly['total_consumption'].pct_change().fillna(0.0) * 100
        df_monthly = df_monthly.sort_values(by='month').tail(12)
        monthly_data[meter_name] = df_monthly
        
    return monthly_data


def get_daily_prorated_electricity(processed_logs):
    elec_df = processed_logs[processed_logs['meter'] == "Electricity (kWh)"].copy()
    if len(elec_df) < 2:
        return pd.DataFrame(columns=["date", "total_daily_kwh"])
    
    elec_df = elec_df.sort_values(by="date")
    first_date = elec_df['date'].iloc[0]
    last_date = elec_df['date'].iloc[-1]
    
    daily_records = []
    
    for i in range(1, len(elec_df)):
        start = elec_df.iloc[i-1]['date']
        end = elec_df.iloc[i]['date']
        days = (end - start).days
        if days > 0:
            daily_rate = (elec_df.iloc[i]['reading'] - elec_df.iloc[i-1]['reading']) / days
            curr = start + datetime.timedelta(days=1)
            while curr <= end:
                daily_records.append({"date": curr, "total_daily_kwh": daily_rate})
                curr += datetime.timedelta(days=1)
                
    return pd.DataFrame(daily_records)