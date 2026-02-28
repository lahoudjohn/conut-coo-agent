import pandas as pd
import numpy as np
import os

def clean_summary_by_division_robust(filepath):
    parsed_data = []
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            
            if not line or "Copyright" in line or "Summary By Division" in line or "Page" in line:
                continue
                
            parts = [p.strip() for p in line.split(',')]
            
            if 'DELIVERY' in parts and 'TOTAL' in parts:
                continue
            
            brand = parts[0] if len(parts) > 0 else ""
            division = parts[1] if len(parts) > 1 else ""
            
            if not division:
                continue
            
            if division.upper() == 'TOTAL':
                continue
                
            try:
                # FORMAT 1: Wide padded format
                if len(parts) >= 11:
                    delivery = float(parts[3]) if parts[3] else 0.0
                    table = float(parts[4]) if parts[4] else 0.0
                    takeaway = float(parts[6]) if parts[6] else 0.0
                    total = float(parts[7]) if parts[7] else 0.0
                    
                # FORMAT 2: Narrow shifted format
                elif len(parts) >= 6:
                    delivery = float(parts[2]) if parts[2] else 0.0
                    table = float(parts[3]) if parts[3] else 0.0
                    takeaway = float(parts[4]) if parts[4] else 0.0
                    total = float(parts[5]) if parts[5] else 0.0
                else:
                    continue
                    
                parsed_data.append([brand, division, delivery, table, takeaway, total])
                
            except ValueError:
                continue

    df = pd.DataFrame(parsed_data, columns=['Brand', 'Division', 'Delivery', 'Table', 'Take_Away', 'Total'])
    df['Brand'] = df['Brand'].replace('', np.nan).ffill()
    return df

if __name__ == "__main__":
    # Assumes your csv is in a 'data' folder
    input_file = os.path.join('data', 'REP_S_00136_SMRY.csv')
    df_136 = clean_summary_by_division_robust(input_file)
    
    if df_136 is not None:
        df_136.to_csv('clean_136_summary.csv', index=False)
        print("Successfully created clean_136_summary.csv")
        print(df_136.head())