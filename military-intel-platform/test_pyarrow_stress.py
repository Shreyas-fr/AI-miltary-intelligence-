import os
import pyarrow as pa
import pyarrow.compute as pc
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor

# Mimic Streamlit's script runner threading
def load_and_convert(task_id):
    try:
        # Generate dummy data similar to large DataFrames used in the app
        df = pd.DataFrame(np.random.randn(500000, 5), columns=['a', 'b', 'c', 'd', 'e'])
        df['country'] = 'TestCountry'
        
        # This triggers PyArrow NdarrayToArrow conversion internally, which is where it crashed
        table = pa.Table.from_pandas(df)
        
        # Do some computations to stress PyArrow memory allocator
        sum_a = pc.sum(table['a'])
        
        return f"Task {task_id} completed successfully (sum: {sum_a})."
    except Exception as e:
        return f"Task {task_id} failed: {e}"

if __name__ == "__main__":
    pool = os.environ.get("ARROW_DEFAULT_MEMORY_POOL", "Not Set")
    print(f"Starting Stress Test. ARROW_DEFAULT_MEMORY_POOL = {pool}")
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(load_and_convert, range(10)))
        
    for res in results:
        print(res)
        
    print(f"Stress test finished in {time.time() - start:.2f} seconds.")
