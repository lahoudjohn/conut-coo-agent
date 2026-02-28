import pandas as pd
import numpy as np
import os

def calculate_expansion_metrics(processed_data_path="data/processed"):
    """
    Integrates 194, 435, 334, and 136 to output a prescriptive Expansion Feasibility report.
    """
    try:
        df_194 = pd.read_csv(os.path.join(processed_data_path, "REP_S_00194_SMRY_cleaned.csv"))
        df_334 = pd.read_csv(os.path.join(processed_data_path, "REP_S_00334_1_SMRY_cleaned.csv"))
        df_136 = pd.read_csv(os.path.join(processed_data_path, "Clean_Summary_by_division_menu_channel.csv"))
        df_435 = pd.read_csv(os.path.join(processed_data_path, "merged_cleaned_sales.csv"))
    except FileNotFoundError as e:
        return f"File Error: Ensure all cleaned CSVs are in {processed_data_path}. Missing: {e}"

    # --- STEP 1: Standardize Names ---
    df_136.rename(columns={'Brand': 'branch_name'}, inplace=True)
    df_435.rename(columns={'Branch': 'branch_name'}, inplace=True)

    # --- STEP 2: Process Economic Activity (194) ---
    econ_profile = df_194.groupby('branch_name')['total'].mean().reset_index()
    econ_profile.rename(columns={'total': 'econ_index'}, inplace=True)

    # --- STEP 3: Process Sales Growth, Volatility & Trend (334) ---
    # 3a. Calculate Averages and Volatility
    growth_profile = df_334.groupby('branch_name').agg({
        'total_sales': ['mean', 'std']
    }).reset_index()
    growth_profile.columns = ['branch_name', 'avg_monthly_sales', 'sales_volatility']
    growth_profile['sales_volatility'] = growth_profile['sales_volatility'].fillna(0)

    # 3b. Calculate Month-over-Month (MoM) Growth Trend
    df_334_sorted = df_334.sort_values(by=['branch_name', 'period_key'])
    df_334_sorted['mom_pct_change'] = df_334_sorted.groupby('branch_name')['total_sales'].pct_change()
    
    # Get the average MoM growth rate per branch
    trend_profile = df_334_sorted.groupby('branch_name')['mom_pct_change'].mean().reset_index()
    trend_profile.rename(columns={'mom_pct_change': 'avg_mom_growth'}, inplace=True)
    trend_profile['avg_mom_growth'] = trend_profile['avg_mom_growth'].fillna(0) # Fill for 1-month branches

    # Merge trend into growth profile
    growth_profile = growth_profile.merge(trend_profile, on='branch_name')

    # --- STEP 4: Process Operational Efficiency (136) ---
    ops_profile = df_136.groupby('branch_name')['Total'].sum().reset_index()
    ops_profile.rename(columns={'Total': 'ops_volume_index'}, inplace=True)

    # --- STEP 5: Process Menu Profitability (435) ---
    df_435_filtered = df_435[df_435['Menu Name'] != 'Total :']
    menu_profile = df_435_filtered.groupby('branch_name')['Avg Customer'].mean().reset_index()
    menu_profile.rename(columns={'Avg Customer': 'avg_ticket_size'}, inplace=True)

    # --- STEP 6: THE GRAND MERGE ---
    final_df = growth_profile.merge(econ_profile, on='branch_name', how='left') \
                             .merge(ops_profile, on='branch_name', how='left') \
                             .merge(menu_profile, on='branch_name', how='left')
    final_df.fillna(0, inplace=True)

    # --- STEP 7: CALCULATE SUCCESS SCORE (0-100) ---
    # Normalizing features
    def normalize_col(df, col_name, inverse=False):
        col_min, col_max = df[col_name].min(), df[col_name].max()
        if col_max == col_min:
            return 0.5
        norm = (df[col_name] - col_min) / (col_max - col_min)
        return 1 - norm if inverse else norm

    # Note: Volatility is inversely normalized (High volatility = 0, Low = 1)
    final_df['n_stability'] = normalize_col(final_df, 'sales_volatility', inverse=True)
    final_df['n_growth'] = normalize_col(final_df, 'avg_mom_growth')
    final_df['n_scale'] = normalize_col(final_df, 'avg_monthly_sales')
    final_df['n_ticket'] = normalize_col(final_df, 'avg_ticket_size')
    final_df['n_econ'] = normalize_col(final_df, 'econ_index')
    final_df['n_ops'] = normalize_col(final_df, 'ops_volume_index')

    # 🔥 NEW WEIGHTS: Emphasizing Trend and Stability over raw scale
    # 25% Growth, 20% Stability, 20% Ticket Size, 15% Scale, 15% Econ Density, 5% Ops
    final_df['branch_success_score'] = (
        (final_df['n_growth'] * 0.25) +
        (final_df['n_stability'] * 0.20) +
        (final_df['n_ticket'] * 0.20) +
        (final_df['n_scale'] * 0.15) +
        (final_df['n_econ'] * 0.15) +
        (final_df['n_ops'] * 0.05)
    ) * 100

    # Format Growth as a percentage for display readability
    final_df['avg_mom_growth_%'] = final_df['avg_mom_growth'] * 100

    display_cols = ['branch_name', 'branch_success_score', 'avg_mom_growth_%', 'n_stability', 
                    'avg_ticket_size', 'avg_monthly_sales', 'ops_volume_index']
    
    return final_df[display_cols].sort_values(by='branch_success_score', ascending=False)

def check_expansion_feasibility(results_df):
    """
    Evaluates the final results against hard business logic to output a Go/No-Go decision.
    """
    if isinstance(results_df, str):
        return results_df

    # RULE: A "Blueprint" branch must have positive MoM growth, above average stability, and a high ticket size.
    median_stability = results_df['n_stability'].median()
    
    blueprint_branches = results_df[
        (results_df['avg_mom_growth_%'] > 0) & 
        (results_df['n_stability'] >= median_stability) &
        (results_df['branch_success_score'] >= 50)
    ]

    report = "\n" + "="*60 + "\n"
    report += "CHIEF OF OPERATIONS: EXPANSION VERDICT\n"
    report += "="*60 + "\n"

    if len(blueprint_branches) > 0:
        report += "VERDICT: EXPANSION IS FEASIBLE.\n\n"
        report += "Reasoning:\n"
        report += f"We have identified {len(blueprint_branches)} branch(es) demonstrating sustained positive growth and operational stability.\n\n"
        report += "Expansion Strategy - Models to Replicate:\n"
        for _, row in blueprint_branches.iterrows():
            report += f"-> {row['branch_name']}: {row['avg_mom_growth_%']:.2f}% MoM Growth | Score: {row['branch_success_score']:.1f}/100\n"
    else:
        report += "VERDICT: EXPANSION IS HIGHLY RISKY (NO-GO).\n\n"
        report += "Reasoning:\n"
        report += "Current network relies heavily on volatile sales patterns or lacks sustained Month-over-Month growth.\n"
        report += "Recommendation: Focus on stabilizing operations and increasing ticket sizes at existing locations before opening a new branch.\n"
    
    return report

if __name__ == "__main__":
    processed_path = os.path.join("backend", "data", "processed")
    success_results = calculate_expansion_metrics(processed_path)
    
    if isinstance(success_results, str):
        print(f"\n❌ ERROR: {success_results}")
    else:
        # Clean up terminal print formatting
        pd.options.display.float_format = '{:.2f}'.format
        print("\n🏆 --- EXPANSION FEASIBILITY MATRIX --- 🏆")
        print(success_results.to_string(index=False))
        
        # Print the Agent's specific logic verdict
        print(check_expansion_feasibility(success_results))