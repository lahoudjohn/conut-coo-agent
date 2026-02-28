from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import pandas as pd
import numpy as np
import os

router = APIRouter(prefix="/expansion", tags=["Expansion"])


# --- Request / Response Models ---

class ExpansionRequest(BaseModel):
    processed_data_path: str = Field(default="data/processed", description="Path to the folder containing cleaned CSVs.")


class BranchScore(BaseModel):
    branch_name: str
    branch_success_score: float
    avg_mom_growth_pct: float
    n_stability: float
    avg_ticket_size: float
    avg_monthly_sales: float
    ops_volume_index: float


class ExpansionMetricsResponse(BaseModel):
    branches: list[BranchScore]


class ExpansionFeasibilityResponse(BaseModel):
    feasible: bool
    verdict: str
    blueprint_branches: list[BranchScore]
    report: str


# --- Core Logic (unchanged) ---

def calculate_expansion_metrics(processed_data_path="data/processed"):
    try:
        df_194 = pd.read_csv(os.path.join(processed_data_path, "REP_S_00194_SMRY_cleaned.csv"))
        df_334 = pd.read_csv(os.path.join(processed_data_path, "REP_S_00334_1_SMRY_cleaned.csv"))
        df_136 = pd.read_csv(os.path.join(processed_data_path, "Clean_Summary_by_division_menu_channel.csv"))
        df_435 = pd.read_csv(os.path.join(processed_data_path, "merged_cleaned_sales.csv"))
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Missing file: {e}")

    df_136.rename(columns={'Brand': 'branch_name'}, inplace=True)
    df_435.rename(columns={'Branch': 'branch_name'}, inplace=True)

    econ_profile = df_194.groupby('branch_name')['total'].mean().reset_index()
    econ_profile.rename(columns={'total': 'econ_index'}, inplace=True)

    growth_profile = df_334.groupby('branch_name').agg({'total_sales': ['mean', 'std']}).reset_index()
    growth_profile.columns = ['branch_name', 'avg_monthly_sales', 'sales_volatility']
    growth_profile['sales_volatility'] = growth_profile['sales_volatility'].fillna(0)

    df_334_sorted = df_334.sort_values(by=['branch_name', 'period_key'])
    df_334_sorted['mom_pct_change'] = df_334_sorted.groupby('branch_name')['total_sales'].pct_change()
    trend_profile = df_334_sorted.groupby('branch_name')['mom_pct_change'].mean().reset_index()
    trend_profile.rename(columns={'mom_pct_change': 'avg_mom_growth'}, inplace=True)
    trend_profile['avg_mom_growth'] = trend_profile['avg_mom_growth'].fillna(0)
    growth_profile = growth_profile.merge(trend_profile, on='branch_name')

    ops_profile = df_136.groupby('branch_name')['Total'].sum().reset_index()
    ops_profile.rename(columns={'Total': 'ops_volume_index'}, inplace=True)

    df_435_filtered = df_435[df_435['Menu Name'] != 'Total :']
    menu_profile = df_435_filtered.groupby('branch_name')['Avg Customer'].mean().reset_index()
    menu_profile.rename(columns={'Avg Customer': 'avg_ticket_size'}, inplace=True)

    final_df = growth_profile.merge(econ_profile, on='branch_name', how='left') \
                             .merge(ops_profile, on='branch_name', how='left') \
                             .merge(menu_profile, on='branch_name', how='left')
    final_df.fillna(0, inplace=True)

    def normalize_col(df, col_name, inverse=False):
        col_min, col_max = df[col_name].min(), df[col_name].max()
        if col_max == col_min:
            return 0.5
        norm = (df[col_name] - col_min) / (col_max - col_min)
        return 1 - norm if inverse else norm

    final_df['n_stability'] = normalize_col(final_df, 'sales_volatility', inverse=True)
    final_df['n_growth']    = normalize_col(final_df, 'avg_mom_growth')
    final_df['n_scale']     = normalize_col(final_df, 'avg_monthly_sales')
    final_df['n_ticket']    = normalize_col(final_df, 'avg_ticket_size')
    final_df['n_econ']      = normalize_col(final_df, 'econ_index')
    final_df['n_ops']       = normalize_col(final_df, 'ops_volume_index')

    final_df['branch_success_score'] = (
        (final_df['n_growth']    * 0.25) +
        (final_df['n_stability'] * 0.20) +
        (final_df['n_ticket']    * 0.20) +
        (final_df['n_scale']     * 0.15) +
        (final_df['n_econ']      * 0.15) +
        (final_df['n_ops']       * 0.05)
    ) * 100

    final_df['avg_mom_growth_%'] = final_df['avg_mom_growth'] * 100

    display_cols = ['branch_name', 'branch_success_score', 'avg_mom_growth_%',
                    'n_stability', 'avg_ticket_size', 'avg_monthly_sales', 'ops_volume_index']

    return final_df[display_cols].sort_values(by='branch_success_score', ascending=False)


def check_expansion_feasibility(results_df: pd.DataFrame):
    median_stability = results_df['n_stability'].median()

    blueprint_branches = results_df[
        (results_df['avg_mom_growth_%'] > 0) &
        (results_df['n_stability'] >= median_stability) &
        (results_df['branch_success_score'] >= 50)
    ]

    feasible = len(blueprint_branches) > 0

    report = "\n" + "="*60 + "\n"
    report += "CHIEF OF OPERATIONS: EXPANSION VERDICT\n"
    report += "="*60 + "\n"

    if feasible:
        report += "VERDICT: EXPANSION IS FEASIBLE.\n\n"
        report += f"We have identified {len(blueprint_branches)} branch(es) demonstrating sustained positive growth and operational stability.\n\n"
        report += "Expansion Strategy - Models to Replicate:\n"
        for _, row in blueprint_branches.iterrows():
            report += f"-> {row['branch_name']}: {row['avg_mom_growth_%']:.2f}% MoM Growth | Score: {row['branch_success_score']:.1f}/100\n"
    else:
        report += "VERDICT: EXPANSION IS HIGHLY RISKY (NO-GO).\n\n"
        report += "Current network relies heavily on volatile sales patterns or lacks sustained Month-over-Month growth.\n"
        report += "Recommendation: Focus on stabilizing operations and increasing ticket sizes at existing locations before opening a new branch.\n"

    return feasible, blueprint_branches, report


# --- API Endpoints ---

@router.post("/metrics", response_model=ExpansionMetricsResponse)
def get_expansion_metrics(request: ExpansionRequest = ExpansionRequest()):
    """
    Calculate and return the Expansion Feasibility Matrix — scored and ranked branches.
    """
    try:
        df = calculate_expansion_metrics(request.processed_data_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {e}")

    branches = [
        BranchScore(
            branch_name=row['branch_name'],
            branch_success_score=round(row['branch_success_score'], 2),
            avg_mom_growth_pct=round(row['avg_mom_growth_%'], 2),
            n_stability=round(row['n_stability'], 4),
            avg_ticket_size=round(row['avg_ticket_size'], 2),
            avg_monthly_sales=round(row['avg_monthly_sales'], 2),
            ops_volume_index=round(row['ops_volume_index'], 2),
        )
        for _, row in df.iterrows()
    ]
    return ExpansionMetricsResponse(branches=branches)


@router.post("/feasibility", response_model=ExpansionFeasibilityResponse)
def get_expansion_feasibility(request: ExpansionRequest = ExpansionRequest()):
    """
    Full Go/No-Go expansion verdict with blueprint branches and reasoning report.
    """
    try:
        df = calculate_expansion_metrics(request.processed_data_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {e}")

    try:
        feasible, blueprint_df, report = check_expansion_feasibility(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feasibility check failed: {e}")

    blueprint_branches = [
        BranchScore(
            branch_name=row['branch_name'],
            branch_success_score=round(row['branch_success_score'], 2),
            avg_mom_growth_pct=round(row['avg_mom_growth_%'], 2),
            n_stability=round(row['n_stability'], 4),
            avg_ticket_size=round(row['avg_ticket_size'], 2),
            avg_monthly_sales=round(row['avg_monthly_sales'], 2),
            ops_volume_index=round(row['ops_volume_index'], 2),
        )
        for _, row in blueprint_df.iterrows()
    ]

    return ExpansionFeasibilityResponse(
        feasible=feasible,
        verdict="EXPANSION IS FEASIBLE" if feasible else "EXPANSION IS HIGHLY RISKY (NO-GO)",
        blueprint_branches=blueprint_branches,
        report=report,
    )
