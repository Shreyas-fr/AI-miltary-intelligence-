from utils.analog_utils import find_historical_analog

for country in ["Iraq", "Afghanistan", "Colombia"]:
    res, err = find_historical_analog(country)
    if err:
        print(f"Error for {country}: {err}")
    else:
        q = res['query_window']
        a = res['analog_window']
        n = res['subsequent_stats']
        print(f"--- {country} ---")
        print(f"Query Range: {q['start_date'].strftime('%Y-%m')} to {q['end_date'].strftime('%Y-%m')}")
        print(f"Analog Match: {a['country']} ({a['start_date'].strftime('%Y-%m')} to {a['end_date'].strftime('%Y-%m')})")
        print(f"Similarity: {a['similarity']*100:.1f}%")
        if n.get('out_of_bounds'):
            print("What happened next: Out of bounds (post-Dec 2017)")
        else:
            print(f"What happened next: Freq {n['freq_change_pct']:.1f}%, Cas {n['cas_change_pct']:.1f}%")
