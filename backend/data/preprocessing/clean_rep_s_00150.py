import csv
import pandas as pd
import numpy as np
import os

def clean_customer_orders_robust(filepath):
    data = []
    current_branch = None
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            row_clean = [x.strip() for x in row if x.strip()]
            
            if not row_clean: continue
            if any(kw in row_clean[0] for kw in ["Customer Name", "From Date:", "Customer Orders", "Page"]):
                continue
            if 'Total By Branch' in row_clean:
                continue
            if len(row_clean) == 1 and row[0].strip():
                current_branch = row[0].strip()
                continue
                
            if row[0].strip().startswith("Person_"):
                name = row[0].strip()
                address = row[1].strip()
                phone = row[2].strip()
                tail = [x.strip() for x in row[3:] if x.strip()]
                
                if len(tail) >= 4:
                    first_order = tail[0]
                    last_order = tail[1]
                    total_str = tail[2].replace(',', '').replace('"', '')
                    try:
                        total = float(total_str)
                        orders = int(tail[3])
                        data.append([current_branch, name, address, phone, first_order, last_order, total, orders])
                    except ValueError:
                        pass
                        
    df = pd.DataFrame(data, columns=[
        'Branch', 'Customer_Name', 'Address', 'Phone', 
        'First_Order', 'Last_Order', 'Total', 'Num_Orders'
    ])
    
    # Time formatting fix for GitHub/Local environment
    df['First_Order'] = df['First_Order'].str.rstrip(':') + ':00'
    df['Last_Order'] = df['Last_Order'].str.rstrip(':') + ':00'
    df['First_Order'] = pd.to_datetime(df['First_Order'], errors='coerce')
    df['Last_Order'] = pd.to_datetime(df['Last_Order'], errors='coerce')
    
    return df

if __name__ == "__main__":
    input_file = os.path.join('data', 'rep_s_00150.csv')
    df_150 = clean_customer_orders_robust(input_file)
    
    if df_150 is not None:
        df_150.to_csv('clean_150_customer_orders.csv', index=False)
        print("Successfully created clean_150_customer_orders.csv")
        print(df_150.head())