import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

WEAPON_COLS = [
    'Explosives', 'Firearms', 'Incendiary', 'Melee', 'Chemical', 'Unknown',
    'Sabotage Equipment', 'Biological', 'Radiological', 'Other', 'Fake Weapons',
    'Vehicle (not to include vehicle-borne explosives, i.e., car or truck bombs)'
]

TARGET_COLS = [
    'Utilities', 'Private Citizens & Property', 'Business', 'Police',
    'Military', 'Violent Political Party', 'Government (General)', 'Transportation',
    'Tourists', 'Government (Diplomatic)', 'Religious Figures/Institutions',
    'Abortion Related', 'Journalists & Media', 'NGO', 'Telecommunication',
    'Terrorists/Non-State Militia', 'Educational Institution', 'Airports & Aircraft',
    'Unknown', 'Maritime', 'Food or Water Supply', 'Other'
]

@st.cache_data(ttl=86400, show_spinner="Building Historical Analog Matrix... (this takes ~30s once per day)")
def build_historical_matrix(csv_path="data/globalterrorism.csv"):
    df = pd.read_csv(csv_path, low_memory=False)
    
    df['date'] = pd.to_datetime(df[['iyear', 'imonth']].assign(day=1).rename(columns={'iyear': 'year', 'imonth': 'month'}), errors='coerce')
    df = df.dropna(subset=['date', 'country_txt'])
    
    # We want a standard order of weapons and targets
    w_dummies = pd.get_dummies(df['weaptype1_txt'])
    t_dummies = pd.get_dummies(df['targtype1_txt'])
    
    for w in WEAPON_COLS:
        if w not in w_dummies.columns:
            w_dummies[w] = 0
    for t in TARGET_COLS:
        if t not in t_dummies.columns:
            t_dummies[t] = 0
            
    # Add prefixed names so we can extract them easily
    w_dummies.columns = ['W_' + str(c) for c in w_dummies.columns]
    t_dummies.columns = ['T_' + str(c) for c in t_dummies.columns]
    
    w_extract = ['W_' + c for c in WEAPON_COLS]
    t_extract = ['T_' + c for c in TARGET_COLS]
    
    agg_df = pd.concat([
        df[['country_txt', 'date']],
        w_dummies[w_extract],
        t_dummies[t_extract]
    ], axis=1)
    
    agg_df['casualties'] = df['nkill'].fillna(0) + df['nwound'].fillna(0)
    agg_df['incident_count'] = 1
    
    monthly = agg_df.groupby(['country_txt', 'date']).sum()
    
    windows = []
    
    for country, group in monthly.groupby(level='country_txt'):
        group = group.reset_index('country_txt', drop=True)
        if len(group) == 0:
            continue
            
        min_date = group.index.min()
        max_date = group.index.max()
        idx = pd.date_range(min_date, max_date, freq='MS')
        group = group.reindex(idx, fill_value=0)
        
        rolled = group.rolling(6).sum().dropna()
        rolled = rolled[rolled['incident_count'] >= 50]
        
        for end_date, row in rolled.iterrows():
            start_date = end_date - pd.DateOffset(months=5)
            
            w_vals = row[w_extract].values
            t_vals = row[t_extract].values
            
            w_sum = w_vals.sum()
            t_sum = t_vals.sum()
            
            w_norm = w_vals / (w_sum if w_sum > 0 else 1)
            t_norm = t_vals / (t_sum if t_sum > 0 else 1)
            
            avg_casualties = row['casualties'] / row['incident_count']
            l_val = np.log1p(avg_casualties)
            f_val = np.log1p(row['incident_count'] / 6.0)
            
            windows.append({
                'country': country,
                'start_date': start_date,
                'end_date': end_date,
                'incident_count': row['incident_count'],
                'casualties': row['casualties'],
                'w_norm': w_norm,
                't_norm': t_norm,
                'l_val': l_val,
                'f_val': f_val
            })
            
    res_df = pd.DataFrame(windows)
    
    if res_df.empty:
        return res_df, df
        
    l_min, l_max = res_df['l_val'].min(), res_df['l_val'].max()
    f_min, f_max = res_df['f_val'].min(), res_df['f_val'].max()
    
    l_range = l_max - l_min if l_max > l_min else 1
    f_range = f_max - f_min if f_max > f_min else 1
    
    res_df['l_norm'] = (res_df['l_val'] - l_min) / l_range
    res_df['f_norm'] = (res_df['f_val'] - f_min) / f_range
    
    w_weight = 0.35
    t_weight = 0.35
    l_weight = 0.15
    f_weight = 0.15
    
    vectors = []
    for _, row in res_df.iterrows():
        vec = np.concatenate([
            row['w_norm'] * w_weight,
            row['t_norm'] * t_weight,
            [row['l_norm'] * l_weight],
            [row['f_norm'] * f_weight]
        ])
        vectors.append(vec)
        
    res_df['vector'] = vectors
    return res_df, df

def get_subsequent_metrics(raw_df, country, start_date, end_date):
    """Calculates what happened in the 6 months *after* the historical analog window."""
    next_start = end_date + pd.DateOffset(months=1)
    next_start = next_start.replace(day=1)
    next_end = next_start + pd.DateOffset(months=5)
    
    # Dataset global boundary check
    global_max_date = raw_df['date'].max()
    out_of_bounds = next_end > global_max_date
    
    country_df = raw_df[raw_df['country_txt'] == country]
    
    # Baseline (the analog window)
    mask_base = (country_df['date'] >= start_date) & (country_df['date'] <= end_date)
    base_df = country_df[mask_base]
    base_incidents = len(base_df)
    base_casualties = base_df['nkill'].fillna(0).sum() + base_df['nwound'].fillna(0).sum()
    base_avg_cas = base_casualties / base_incidents if base_incidents > 0 else 0
    
    # Subsequent Window (the 6 months after)
    mask_next = (country_df['date'] >= next_start) & (country_df['date'] <= next_end)
    next_df = country_df[mask_next]
    next_incidents = len(next_df)
    next_casualties = next_df['nkill'].fillna(0).sum() + next_df['nwound'].fillna(0).sum()
    next_avg_cas = next_casualties / next_incidents if next_incidents > 0 else 0
    
    if next_incidents == 0:
        freq_change = -100.0
        cas_change = -100.0
        new_target = "None"
        new_weapon = "None"
    else:
        freq_change = ((next_incidents - base_incidents) / base_incidents) * 100 if base_incidents > 0 else 0
        cas_change = ((next_avg_cas - base_avg_cas) / base_avg_cas) * 100 if base_avg_cas > 0 else 0
        new_target = next_df['targtype1_txt'].value_counts().index[0]
        new_weapon = next_df['weaptype1_txt'].value_counts().index[0]
        
    return {
        'next_start': next_start,
        'next_end': next_end,
        'out_of_bounds': out_of_bounds,
        'next_incidents': next_incidents,
        'freq_change_pct': freq_change,
        'cas_change_pct': cas_change,
        'new_target': new_target,
        'new_weapon': new_weapon
    }

def find_historical_analog(query_country: str, csv_path="data/globalterrorism.csv"):
    res_df, raw_df = build_historical_matrix(csv_path)
    if res_df.empty:
        return None, "No data available."
        
    # Find the most recent window for the query country
    country_windows = res_df[res_df['country'] == query_country]
    if country_windows.empty:
        return None, f"Insufficient data for {query_country} (requires at least 50 incidents in a 6-month window)."
        
    # Sort to get the most recent end_date
    current_window = country_windows.sort_values('end_date', ascending=False).iloc[0]
    
    # Filter candidates: strictly exclude the query country
    candidates = res_df[res_df['country'] != query_country]
    if candidates.empty:
        return None, "No candidates available for comparison."
        
    # Cosine Similarity
    current_vec = np.array(current_window['vector']).reshape(1, -1)
    candidate_vecs = np.stack(candidates['vector'].values)
    
    sims = cosine_similarity(current_vec, candidate_vecs)[0]
    candidates = candidates.copy()
    candidates['similarity'] = sims
    
    best_match = candidates.sort_values('similarity', ascending=False).iloc[0]
    
    # What happened next?
    subsequent_stats = get_subsequent_metrics(
        raw_df, 
        best_match['country'], 
        best_match['start_date'], 
        best_match['end_date']
    )
    
    return {
        'query_window': current_window,
        'analog_window': best_match,
        'subsequent_stats': subsequent_stats
    }, None
