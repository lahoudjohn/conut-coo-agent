from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
import os
from datetime import datetime

app = FastAPI(
    title="Coffee & Milkshake Growth Strategy API",
    description="Executes a Targeted 4-Phase Strategy Engine for Coffee and Milkshake Growth.",
    version="1.0.0"
)


# --- Request / Response Models ---

class StrategyRequest(BaseModel):
    processed_data_path: str = "data/processed"
    raw_data_path: str = "data"


class StrategyResponse(BaseModel):
    success: bool
    report: str
    generated_at: str


# --- Core Logic (unchanged) ---

def generate_growth_strategy(processed_data_path="data/processed", raw_data_path="data"):
    """
    Executes a Targeted 4-Phase Strategy Engine for Coffee and Milkshake Growth.
    """
    report = "\n" + "="*80 + "\n"
    report += "CHIEF OF OPERATIONS: COFFEE & MILKSHAKE GROWTH STRATEGY\n"
    report += "="*80 + "\n"

    # =========================================================================
    # PHASE 1: BEHAVIORAL CHURN (RFM)
    # =========================================================================
    try:
        df_150 = pd.read_csv(os.path.join(processed_data_path, "Clean_Customer orders.csv"))
        date_col, freq_col, branch_col = 'Last_Order', 'Num_Orders', 'Branch'

        df_150[date_col] = pd.to_datetime(df_150[date_col], format='%Y-%m-%d %H:%M:%S', errors='coerce')
        current_date = df_150[date_col].max()
        df_150['Recency'] = (current_date - df_150[date_col]).dt.days

        at_risk_df = df_150[(df_150[freq_col] > 1) & (df_150['Recency'] > 14)]

        report += "\n[PHASE 1: RETENTION & RECOVERY (RFM)]\n"
        report += f"-> Global Risk: {len(at_risk_df)} habitual customers have not ordered in >14 days.\n"

        if not at_risk_df.empty:
            risk_by_branch = at_risk_df.groupby(branch_col).size().sort_values(ascending=False)
            report += f"-> Critical Branch: {risk_by_branch.index[0]} leads with {risk_by_branch.iloc[0]} at-risk profiles.\n"
        else:
            report += "-> Status: No at-risk habitual customers detected at this time.\n"

        report += "-> STRATEGY: Automated 'Win-Back' vouchers specifically for Coffee/Milkshake categories.\n"
    except Exception as e:
        report += f"\n[PHASE 1 ERROR]: {e}\n"

    # =========================================================================
    # PHASE 2: ATTACHMENT GAPS & BUNDLE TARGETS (Dataset 502)
    # =========================================================================
    try:
        file_name = "REP_S_00502_cleaned_updated.csv"
        df_502 = pd.read_csv(os.path.join(processed_data_path, file_name), low_memory=False)

        qty_col = df_502.columns[2]
        item_col = df_502.columns[3]
        order_col = df_502.columns[7]

        df_clean = df_502.groupby([order_col, item_col])[qty_col].sum().reset_index()
        df_clean = df_clean[df_clean[qty_col] > 0]

        coffee_keys = ['coffee', 'latte', 'cappuccino', 'espresso', 'americano', 'mocha']
        shake_keys = ['shake', 'milkshake', 'frappe']

        df_clean['is_coffee'] = df_clean[item_col].str.contains('|'.join(coffee_keys), case=False, na=False)
        df_clean['is_shake'] = df_clean[item_col].str.contains('|'.join(shake_keys), case=False, na=False)

        order_summary = df_clean.groupby(order_col).agg({
            'is_coffee': 'any',
            'is_shake': 'any'
        }).reset_index()

        total_orders = len(order_summary)

        if total_orders > 0:
            coffee_attach = (order_summary['is_coffee'].sum() / total_orders) * 100
            shake_attach = (order_summary['is_shake'].sum() / total_orders) * 100

            food_only_orders = order_summary[~(order_summary['is_coffee'] | order_summary['is_shake'])][order_col]
            non_food_keys = ['delivery', 'service', 'discount', 'packaging', 'vat', 'tip', 'tax']
            food_only_df = df_clean[df_clean[order_col].isin(food_only_orders)]
            food_only_df = food_only_df[~food_only_df[item_col].str.contains('|'.join(non_food_keys), case=False, na=False)]

            top_food_targets = food_only_df[item_col].value_counts().head(3)

            report += "\n[PHASE 2: ATTACHMENT GAPS & BUNDLE TARGETS]\n"
            report += f"-> Coffee Attach Rate: {coffee_attach:.1f}% | Milkshake Attach Rate: {shake_attach:.1f}%\n"
            report += "-> Priority Bundle Targets (Food often bought alone):\n"

            if not top_food_targets.empty:
                for item, count in top_food_targets.items():
                    report += f"   * {item} ({count} solo orders)\n"
                report += f"-> STRATEGY: Introduce 'The {top_food_targets.index[0]} + Coffee' breakfast bundle to close the gap.\n"
            else:
                report += "   * No specific food-only patterns detected.\n"
        else:
            report += "\n[PHASE 2]: No completed orders available after refund wash-out.\n"

    except Exception as e:
        report += f"\n[PHASE 2 ERROR]: {e}\n"

    # =========================================================================
    # PHASE 3: MENU ENGINEERING (Dataset 191)
    # =========================================================================
    try:
        df_191 = pd.read_csv(os.path.join(processed_data_path, "Clean_Sales by items and groups.csv"))

        if 'Group' in df_191.columns:
            group_col = 'Group'
        elif 'Division' in df_191.columns:
            group_col = 'Division'
        else:
            group_col = df_191.columns[0]

        sales_col = df_191.select_dtypes(include=[np.number]).columns[-1]

        bev_mask = df_191[group_col].str.contains('bev|coffee|shake|drink', case=False, na=False)
        df_bev = df_191[bev_mask].groupby(group_col)[sales_col].sum().reset_index()

        df_bev = df_bev.sort_values(by=sales_col, ascending=False).reset_index(drop=True)
        df_bev['cum_pct'] = df_bev[sales_col].cumsum() / df_bev[sales_col].sum()

        dead_weight = df_bev[df_bev['cum_pct'] > 0.95]

        report += "\n[PHASE 3: MENU ENGINEERING (Pareto Analysis)]\n"
        report += f"-> Identified {len(dead_weight)} Beverage Groups in Class C (Bottom 5% revenue).\n"

        if not dead_weight.empty:
            prune_list = dead_weight[group_col].astype(str).unique()[:5]
            report += f"-> Actionable Pruning (Top 5): {', '.join(prune_list)}\n"

        report += "-> STRATEGY: Prune low-margin/low-volume beverage groups to reduce SKU complexity.\n"
    except Exception as e:
        report += f"\n[PHASE 3 ERROR]: {e}\n"

    # =========================================================================
    # PHASE 4: BENCHMARKING (Dataset 435)
    # =========================================================================
    try:
        df_435 = pd.read_csv(os.path.join(processed_data_path, "merged_cleaned_sales.csv"))
        branch_perf = df_435[df_435['Menu Name'] != 'Total :'].groupby('Branch')['Avg Customer'].mean().sort_values(ascending=False)

        if not branch_perf.empty:
            top_branch, top_val = branch_perf.index[0], branch_perf.iloc[0]
            bot_branch, bot_val = branch_perf.index[-1], branch_perf.iloc[-1]

            report += "\n[PHASE 4: UPSIDE BENCHMARKING]\n"
            report += f"-> {top_branch} (Premium Model) vs {bot_branch} (Volume Model).\n"
            report += f"-> Ticket Delta: {top_val - bot_val:,.2f} units.\n"
            report += "-> STRATEGY: Adopt High-Performer upselling modifiers (Oat milk, extra shots) in low-ticket branches.\n"
    except Exception as e:
        report += f"\n[PHASE 4 ERROR]: {e}\n"

    report += "\n" + "="*80 + "\n"
    report += "AGENT VERDICT: BIFURCATED GROWTH PLAN\n"
    report += "1. COFFEE: Focus on 'Morning Routine' bundles with top-targeted food items.\n"
    report += "2. MILKSHAKES: Aggressive upsell on Delivery/Takeaway channels via premium packaging.\n"
    report += "="*80 + "\n"

    return report


# --- API Endpoint ---

@app.post("/growth-strategy", response_model=StrategyResponse)
def run_growth_strategy(request: StrategyRequest = StrategyRequest()):
    """
    Run the 4-Phase Coffee & Milkshake Growth Strategy engine.

    Optionally pass custom data paths in the request body:
    - `processed_data_path`: path to the folder with cleaned CSVs (default: "data/processed")
    - `raw_data_path`: path to the raw data folder (default: "data")
    """
    try:
        report = generate_growth_strategy(
            processed_data_path=request.processed_data_path,
            raw_data_path=request.raw_data_path
        )
        return StrategyResponse(
            success=True,
            report=report,
            generated_at=datetime.utcnow().isoformat() + "Z"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy engine failed: {str(e)}")


# --- Run locally ---
# uvicorn growth_strategy_api:app --reload
