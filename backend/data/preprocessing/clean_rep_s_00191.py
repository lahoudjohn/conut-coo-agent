import csv
import pandas as pd
import os

def clean_sales_by_items_robust(filepath):
    data = []
    current_branch = None
    current_division = None
    current_group = None
    
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return None

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            row_clean = [str(x).strip() for x in row]
            first_col = row_clean[0] if len(row_clean) > 0 else ""
            
            if not first_col: continue
            if first_col in ["Description", "Conut - Tyre", "Sales by Items By Group"] or "Page" in first_col or "Years:" in first_col:
                continue
            if first_col.startswith("Total by"):
                continue
            if first_col.startswith("Branch:"):
                current_branch = first_col.replace("Branch:", "").strip()
                continue
            if first_col.startswith("Division:"):
                current_division = first_col.replace("Division:", "").strip()
                continue
            if first_col.startswith("Group:"):
                current_group = first_col.replace("Group:", "").strip()
                continue
                
            description = first_col
            barcode = row_clean[1] if len(row_clean) > 1 else ""
            qty_str = row_clean[2] if len(row_clean) > 2 else "0"
            total_str = row_clean[3] if len(row_clean) > 3 else "0"
            total_str = total_str.replace(',', '').replace('"', '')
            
            try:
                qty = float(qty_str)
                total = float(total_str)
                data.append([current_branch, current_division, current_group, description, barcode, qty, total])
            except ValueError:
                continue

    df = pd.DataFrame(data, columns=['Branch', 'Division', 'Group', 'Item_Description', 'Barcode', 'Quantity', 'Total_Amount'])
    return df

if __name__ == "__main__":
    input_file = os.path.join('data', 'rep_s_00191_SMRY.csv')
    df_191 = clean_sales_by_items_robust(input_file)
    
    if df_191 is not None:
        df_191.to_csv('clean_191_sales_by_items.csv', index=False)
        print("Successfully created clean_191_sales_by_items.csv")
        print(df_191.head())