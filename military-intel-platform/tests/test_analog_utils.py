import pytest
import pandas as pd
import numpy as np
from utils.analog_utils import get_subsequent_metrics, find_historical_analog

def test_get_subsequent_metrics():
    # Create mock GTD dataframe
    dates = pd.to_datetime(['2014-01-01', '2014-02-01', '2014-07-01', '2014-08-01'])
    df = pd.DataFrame({
        'country_txt': ['Testland'] * 4,
        'date': dates,
        'nkill': [1, 2, 3, 4],
        'nwound': [1, 1, 1, 1],
        'weaptype1_txt': ['Explosives', 'Firearms', 'Explosives', 'Explosives'],
        'targtype1_txt': ['Military', 'Police', 'Civilian', 'Civilian']
    })
    
    start_date = pd.to_datetime('2014-01-01')
    end_date = pd.to_datetime('2014-06-01')
    
    # Base window: Jan-Jun (2 incidents, total cas = 5, avg cas = 2.5)
    # Next window: Jul-Dec (2 incidents, total cas = 9, avg cas = 4.5)
    # Freq change: 0%
    # Cas change: ((4.5 - 2.5) / 2.5) * 100 = 80%
    
    res = get_subsequent_metrics(df, 'Testland', start_date, end_date)
    
    assert res['next_incidents'] == 2
    assert res['freq_change_pct'] == 0.0
    assert abs(res['cas_change_pct'] - 80.0) < 1e-5
    assert res['new_weapon'] == 'Explosives'
    assert res['new_target'] == 'Civilian'

def test_find_historical_analog_self_exclusion(monkeypatch):
    # Mock build_historical_matrix to return synthetic data
    def mock_build(*args, **kwargs):
        res_df = pd.DataFrame({
            'country': ['Iraq', 'Iraq', 'Syria'],
            'start_date': pd.to_datetime(['2010-01-01', '2017-07-01', '2017-07-01']),
            'end_date': pd.to_datetime(['2010-06-01', '2017-12-01', '2017-12-01']),
            'incident_count': [100, 150, 120],
            'vector': [
                np.array([1, 0, 0, 0]),
                np.array([1, 0.1, 0, 0]), # Query window
                np.array([1, 0.2, 0, 0])  # Match
            ]
        })
        raw_df = pd.DataFrame({
            'country_txt': ['Syria'],
            'date': pd.to_datetime(['2018-01-01']),
            'nkill': [0],
            'nwound': [0],
            'weaptype1_txt': ['Unknown'],
            'targtype1_txt': ['Unknown']
        })
        return res_df, raw_df
        
    monkeypatch.setattr('utils.analog_utils.build_historical_matrix', mock_build)
    
    res, err = find_historical_analog('Iraq', csv_path='dummy.csv')
    assert err is None
    # Self exclusion should prevent Iraq from matching Iraq 2010
    # It must match Syria
    assert res['analog_window']['country'] == 'Syria'
