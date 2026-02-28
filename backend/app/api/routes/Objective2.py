from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

router = APIRouter(prefix="/forecast", tags=["Demand Forecast"])


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

ACADEMIC_BRANCHES     = ['Conut']
N_BOOTSTRAP           = 2000
CI_LOWER, CI_UPPER    = 10, 90
RAMP_UP_THRESHOLD     = 0.30
OUTLIERS              = {'Conut - Tyre': [10]}
BRANCH_METHOD         = {
    'Conut':              'linear',
    'Conut - Tyre':       'linear',
    'Conut Jnah':         'log',
    'Main Street Coffee': 'linear',
}
RATIONALE = {
    'Conut':              'Clean linear trend — log adds distortion',
    'Conut - Tyre':       'Stable post-imputation — linear generalizes better',
    'Conut Jnah':         'Exponential growth pattern — log transform wins',
    'Main Street Coffee': 'Only 2 log points — linear more reliable',
}
ALL_METHOD_ACCURACY = {
    'Conut':              {'linear': 95.8, 'optimized': 86.4, 'ensemble': 92.9, 'log_mult': 79.9},
    'Conut - Tyre':       {'linear': 69.6, 'optimized': 96.6, 'ensemble': 100.0, 'log_mult': 77.9},
    'Conut Jnah':         {'linear': 40.3, 'optimized': 33.6, 'ensemble': 37.4,  'log_mult': 65.7},
    'Main Street Coffee': {'linear': 57.6, 'optimized': 40.5, 'ensemble': 54.7,  'log_mult': None},
}
RAW_DATA = [
    ('Conut',               8,  2025,  554074782.88),
    ('Conut',               9,  2025,  784385377.11),
    ('Conut',               10, 2025,  1137352241.41),
    ('Conut',               11, 2025,  1351165728.11),
    ('Conut',               12, 2025,  67887513.35),
    ('Conut - Tyre',        8,  2025,  477535459.07),
    ('Conut - Tyre',        9,  2025,  444800810.51),
    ('Conut - Tyre',        10, 2025,  2100816729.45),
    ('Conut - Tyre',        11, 2025,  1129526810.42),
    ('Conut - Tyre',        12, 2025,  1024205946.30),
    ('Conut Jnah',          8,  2025,  363540268.13),
    ('Conut Jnah',          9,  2025,  714037266.45),
    ('Conut Jnah',          10, 2025,  785925564.58),
    ('Conut Jnah',          11, 2025,  947652050.58),
    ('Conut Jnah',          12, 2025,  2878191130.49),
    ('Main Street Coffee',  9,  2025,  145842540.35),
    ('Main Street Coffee',  10, 2025,  920588160.21),
    ('Main Street Coffee',  11, 2025,  1171534376.20),
    ('Main Street Coffee',  12, 2025,  3074216293.59),
]


# ─────────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ─────────────────────────────────────────────

class ForecastRequest(BaseModel):
    branches: Optional[list[str]] = Field(
        default=None,
        description="List of branch names to forecast. Leave empty to run all branches."
    )
    n_bootstrap: Optional[int] = Field(
        default=N_BOOTSTRAP,
        description="Number of bootstrap iterations for confidence intervals."
    )


class MonthForecast(BaseModel):
    worst:    float
    expected: float
    best:     float
    note:     Optional[str] = None


class BranchForecast(BaseModel):
    branch:          str
    branch_type:     str
    method:          str
    accuracy_pct:    Optional[float]
    mape_pct:        Optional[float]
    outlier_imputed: bool
    rampup_removed:  bool
    ci_fallback:     bool
    dec_multiplier:  Optional[float]
    rationale:       str
    monthly:         dict[str, MonthForecast]


class ForecastResponse(BaseModel):
    branches:   list[BranchForecast]
    disclaimer: str


class LeaderboardRow(BaseModel):
    branch:       str
    linear_acc:   Optional[float]
    optimized_acc: Optional[float]
    ensemble_acc: Optional[float]
    log_mult_acc: Optional[float]
    best_method:  str
    best_accuracy: Optional[float]


class LeaderboardResponse(BaseModel):
    leaderboard: list[LeaderboardRow]


# ─────────────────────────────────────────────
# CORE HELPERS (unchanged logic)
# ─────────────────────────────────────────────

def impute_outliers(branch_df, branch_name):
    if branch_name not in OUTLIERS:
        return branch_df.copy(), False
    outlier_months = OUTLIERS[branch_name]
    clean_mean = branch_df[~branch_df['month'].isin(outlier_months)]['sales'].mean()
    result = branch_df.copy()
    result.loc[result['month'].isin(outlier_months), 'sales'] = clean_mean
    return result, True


def detect_rampup(branch_df):
    d = branch_df.sort_values('month').reset_index(drop=True)
    if len(d) >= 2:
        ratio = d['sales'].iloc[0] / d['sales'].iloc[1]
        if ratio < RAMP_UP_THRESHOLD:
            return d.iloc[1:].reset_index(drop=True), True, d['month'].iloc[0]
    return d, False, None


def bootstrap_ci_linear(X_train, y_train, future_idx, n_bootstrap=N_BOOTSTRAP, seed=42):
    rng   = np.random.default_rng(seed)
    base  = LinearRegression().fit(X_train, y_train)
    resids = y_train - base.predict(X_train)
    n     = len(X_train)
    boot  = np.zeros((n_bootstrap, len(future_idx)))
    for i in range(n_bootstrap):
        y_boot  = base.predict(X_train) + rng.choice(resids, size=n, replace=True)
        m       = LinearRegression().fit(X_train, y_boot)
        noise   = rng.choice(resids, size=len(future_idx), replace=True)
        boot[i] = np.maximum(m.predict(future_idx) + noise, 0)
    point = np.maximum(base.predict(future_idx), 0)
    lower = np.maximum(np.percentile(boot, CI_LOWER, axis=0), 0)
    upper = np.maximum(np.percentile(boot, CI_UPPER, axis=0), 0)
    return point, lower, upper


def bootstrap_ci_log(X_train, log_y, future_idx, n_bootstrap=N_BOOTSTRAP, seed=42):
    rng       = np.random.default_rng(seed)
    base      = LinearRegression().fit(X_train, log_y)
    point_log = base.predict(future_idx)
    resids    = log_y - base.predict(X_train)
    if np.std(resids) < 1e-8:
        point = np.exp(point_log)
        return point, point * 0.80, point * 1.20, True
    n    = len(X_train)
    boot = np.zeros((n_bootstrap, len(future_idx)))
    for i in range(n_bootstrap):
        y_boot  = base.predict(X_train) + rng.choice(resids, size=n, replace=True)
        m       = LinearRegression().fit(X_train, y_boot)
        noise   = rng.choice(resids, size=len(future_idx), replace=True)
        boot[i] = m.predict(future_idx) + noise
    point = np.exp(point_log)
    lower = np.exp(np.percentile(boot, CI_LOWER, axis=0))
    upper = np.exp(np.percentile(boot, CI_UPPER, axis=0))
    return np.maximum(point, 0), np.maximum(lower, 0), np.maximum(upper, 0), False


def run_forecast_engine(branches_filter=None, n_bootstrap=N_BOOTSTRAP):
    df = pd.DataFrame(RAW_DATA, columns=['branch', 'month', 'year', 'sales'])
    df['branch_type'] = df['branch'].apply(
        lambda x: 'academic' if x in ACADEMIC_BRANCHES else 'commercial'
    )

    all_branches = df['branch'].unique().tolist()
    if branches_filter:
        invalid = [b for b in branches_filter if b not in all_branches]
        if invalid:
            raise ValueError(f"Unknown branch(es): {invalid}. Valid: {all_branches}")
        target_branches = branches_filter
    else:
        target_branches = all_branches

    results = []

    for branch in target_branches:
        branch_df   = df[df['branch'] == branch].copy()
        branch_type = branch_df['branch_type'].iloc[0]
        method      = BRANCH_METHOD[branch]

        branch_df, outlier_imputed = impute_outliers(branch_df, branch)

        dec_row  = branch_df[branch_df['month'] == 12].copy()
        trend_df = branch_df[branch_df['month'] != 12].copy()

        rampup, rampup_month, ci_fallback = False, None, False
        if method == 'log':
            trend_df, rampup, rampup_month = detect_rampup(trend_df)

        trend_df = trend_df.reset_index(drop=True)
        trend_df['time_index'] = range(len(trend_df))
        X_all = trend_df[['time_index']].values
        y_all = trend_df['sales'].values

        # Holdout eval
        mape, acc = None, None
        if len(trend_df) >= 3:
            X_tr, y_tr = X_all[:-1], y_all[:-1]
            X_te, y_te = X_all[-1:], y_all[-1:]
            if method == 'linear':
                pred = LinearRegression().fit(X_tr, y_tr).predict(X_te)[0]
            else:
                log_tr = np.log(y_tr)
                pred   = np.exp(LinearRegression().fit(X_tr, log_tr).predict(X_te)[0])
            mape = abs(pred - y_te[0]) / y_te[0] * 100
            acc  = round(100 - mape, 1)
            mape = round(mape, 1)

        # December multiplier
        dec_mult = None
        if len(dec_row) > 0 and branch_type == 'commercial':
            dec_sales  = dec_row['sales'].values[0]
            nov_data   = trend_df[trend_df['month'] == 11]['sales'].values
            base_sales = nov_data[0] if len(nov_data) > 0 else y_all[-1]
            dec_mult   = dec_sales / base_sales

        # Forecast
        last_idx   = len(trend_df)
        n_future   = 4 if branch_type == 'academic' else 3
        future_idx = np.array([[last_idx + i] for i in range(1, n_future + 1)])

        if method == 'linear':
            point, lower, upper = bootstrap_ci_linear(X_all, y_all, future_idx, n_bootstrap)
        else:
            log_y = np.log(y_all)
            point, lower, upper, ci_fallback = bootstrap_ci_log(X_all, log_y, future_idx, n_bootstrap)

        month_labels = (
            ['August_2026', 'September_2026', 'October_2026', 'November_2026']
            if branch_type == 'academic'
            else ['January_2026', 'February_2026', 'March_2026']
        )

        monthly = {}
        for i, label in enumerate(month_labels):
            monthly[label] = MonthForecast(
                worst=round(lower[i], 0),
                expected=round(point[i], 0),
                best=round(upper[i], 0),
            )

        # December 2026
        if branch_type == 'academic':
            monthly['December_2026'] = MonthForecast(
                worst=50000000, expected=68000000, best=90000000,
                note='Semester break — based on 2025 observed (~68M)'
            )
        elif dec_mult:
            nov_step = np.array([[last_idx + 10]])
            if method == 'linear':
                nov_pt, nov_lo, nov_hi = bootstrap_ci_linear(X_all, y_all, nov_step, n_bootstrap)
            else:
                log_y = np.log(y_all)
                nov_pt, nov_lo, nov_hi, _ = bootstrap_ci_log(X_all, log_y, nov_step, n_bootstrap)

            monthly['November_2026'] = MonthForecast(
                worst=round(nov_lo[0], 0),
                expected=round(nov_pt[0], 0),
                best=round(nov_hi[0], 0),
            )
            monthly['December_2026'] = MonthForecast(
                worst=round(nov_lo[0] * dec_mult, 0),
                expected=round(nov_pt[0] * dec_mult, 0),
                best=round(nov_hi[0] * dec_mult, 0),
                note=f'Multiplier {dec_mult:.2f}x applied to Nov 2026 forecast'
            )

        results.append(BranchForecast(
            branch=branch,
            branch_type=branch_type,
            method=method,
            accuracy_pct=acc,
            mape_pct=mape,
            outlier_imputed=outlier_imputed,
            rampup_removed=rampup,
            ci_fallback=ci_fallback,
            dec_multiplier=round(dec_mult, 3) if dec_mult else None,
            rationale=RATIONALE.get(branch, ''),
            monthly=monthly,
        ))

    return results


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

@router.post("/run", response_model=ForecastResponse)
def run_forecast(request: ForecastRequest = ForecastRequest()):
    """
    Run the demand forecast engine for one or all branches.
    Returns per-branch monthly forecasts with P10/Expected/P90 confidence intervals.
    """
    try:
        branch_results = run_forecast_engine(
            branches_filter=request.branches,
            n_bootstrap=request.n_bootstrap,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast engine failed: {e}")

    return ForecastResponse(
        branches=branch_results,
        disclaimer=(
            "4-5 months of data only. Directional estimates ±20%. "
            "December 2026 assumes same seasonal pattern as 2025."
        )
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_accuracy_leaderboard():
    """
    Returns the accuracy leaderboard comparing all methods across all branches.
    """
    rows = []
    for branch, methods in ALL_METHOD_ACCURACY.items():
        best_method = BRANCH_METHOD[branch]
        # Look up chosen method's accuracy from the live engine
        try:
            results = run_forecast_engine(branches_filter=[branch], n_bootstrap=200)
            best_acc = results[0].accuracy_pct if results else None
        except Exception:
            best_acc = None

        rows.append(LeaderboardRow(
            branch=branch,
            linear_acc=methods.get('linear'),
            optimized_acc=methods.get('optimized'),
            ensemble_acc=methods.get('ensemble'),
            log_mult_acc=methods.get('log_mult'),
            best_method=best_method.upper(),
            best_accuracy=best_acc,
        ))

    return LeaderboardResponse(leaderboard=rows)


@router.get("/branches")
def list_branches():
    """
    Returns the list of all available branches and their assigned forecast methods.
    """
    return {
        "branches": [
            {"branch": b, "method": m, "rationale": RATIONALE[b]}
            for b, m in BRANCH_METHOD.items()
        ]
    }
