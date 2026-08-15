import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def build_historical_matrix(csv_path="data/globalterrorism.csv"):
    df = pd.read_csv(csv_path, low_memory=False)
    # Fix dates
    df['date'] = pd.to_datetime(df[['iyear', 'imonth']].assign(day=1).rename(columns={'iyear': 'year', 'imonth': 'month'}), errors='coerce')
    df = df.dropna(subset=['date', 'country_txt'])
    
    # One-hot encode
    weapon_cols = pd.get_dummies(df['weaptype1_txt'], prefix='W')
    target_cols = pd.get_dummies(df['targtype1_txt'], prefix='T')
    
    # Select columns to aggregate
    agg_df = pd.concat([
        df[['country_txt', 'date']],
        weapon_cols,
        target_cols
    ], axis=1)
    
    agg_df['casualties'] = df['nkill'].fillna(0) + df['nwound'].fillna(0)
    agg_df['incident_count'] = 1
    
    # Group by country and month
    monthly = agg_df.groupby(['country_txt', 'date']).sum()
    
    windows = []
    # Rolling 6-month sum per country
    for country, group in monthly.groupby(level='country_txt'):
        # Reindex to fill missing months so rolling works accurately over time
        group = group.reset_index('country_txt', drop=True)
        if len(group) == 0:
            continue
        min_date = group.index.min()
        max_date = group.index.max()
        idx = pd.date_range(min_date, max_date, freq='MS')
        group = group.reindex(idx, fill_value=0)
        
        rolled = group.rolling(6).sum().dropna()
        
        # Filter minimum 50 incidents
        rolled = rolled[rolled['incident_count'] >= 50]
        
        for end_date, row in rolled.iterrows():
            start_date = end_date - pd.DateOffset(months=5)
            
            # W and T extraction
            w_vals = row.filter(like='W_').values
            t_vals = row.filter(like='T_').values
            
            w_norm = w_vals / (w_vals.sum() or 1)
            t_norm = t_vals / (t_vals.sum() or 1)
            
            avg_casualties = row['casualties'] / row['incident_count']
            
            # Log scale
            l_val = np.log1p(avg_casualties)
            f_val = np.log1p(row['incident_count'] / 6.0)
            
            windows.append({
                'country': country,
                'start_date': start_date,
                'end_date': end_date,
                'incident_count': row['incident_count'],
                'w_norm': w_norm,
                't_norm': t_norm,
                'l_val': l_val,
                'f_val': f_val
            })
            
    res_df = pd.DataFrame(windows)
    
    # Global min-max scaling for L and F to 0-1
    res_df['l_norm'] = (res_df['l_val'] - res_df['l_val'].min()) / (res_df['l_val'].max() - res_df['l_val'].min())
    res_df['f_norm'] = (res_df['f_val'] - res_df['f_val'].min()) / (res_df['f_val'].max() - res_df['f_val'].min())
    
    # Weight vectors
    w_weight = 0.35
    t_weight = 0.35
    l_weight = 0.15
    f_weight = 0.15
    
    vectors = []
    for _, row in res_df.iterrows():
        # w_norm and t_norm sum to 1, we multiply by weight
        vec = np.concatenate([
            row['w_norm'] * w_weight,
            row['t_norm'] * t_weight,
            [row['l_norm'] * l_weight],
            [row['f_norm'] * f_weight]
        ])
        vectors.append(vec)
        
    res_df['vector'] = vectors
    return res_df, df

# Test it
res_df, raw_df = build_historical_matrix()
print(f"Built {len(res_df)} historical 6-month windows with >= 50 incidents.")
