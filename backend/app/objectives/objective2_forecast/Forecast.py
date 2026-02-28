import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error

# ─────────────────────────────────────────────
# RAW DATA
# ─────────────────────────────────────────────

raw_data = [
    ('Conut',               8,  2025,  554074782.88),
    ('Conut',               9,  2025,  784385377.11),
    ('Conut',               10, 2025,  1137352241.41),
    ('Conut',               11, 2025,  1351165728.11),
    ('Conut',               12, 2025,  67887513.35),

    ('Conut - Tyre',        8,  2025,  477535459.07),
    ('Conut - Tyre',        9,  2025,  444800810.51),
    ('Conut - Tyre',        10, 2025,  2100816729.45),  # outlier
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

df = pd.DataFrame(raw_data, columns=['branch', 'month', 'year', 'sales'])

ACADEMIC_BRANCHES = ['Conut']
MONTH_NAMES = {1:'January', 2:'February', 3:'March',  4:'April',
               5:'May',     6:'June',     7:'July',   8:'August',
               9:'September',10:'October',11:'November',12:'December'}

df['branch_type'] = df['branch'].apply(
    lambda x: 'academic' if x in ACADEMIC_BRANCHES else 'commercial'
)

# ─────────────────────────────────────────────
# METHOD ASSIGNMENT
# Based on head-to-head accuracy from all experiments:
#
#   Conut            → Linear      (95.8%  — clean linear trend)
#   Conut - Tyre     → Linear      (69.6%  — ensemble was 100% but
#                                    relied on single holdout point;
#                                    linear is more stable/generalizable)
#   Conut Jnah       → Log+Mult    (65.7%  — exponential growth pattern)
#   Main Street      → Linear      (57.6%  — only 2 log points available)
# ─────────────────────────────────────────────

BRANCH_METHOD = {
    'Conut':              'linear',
    'Conut - Tyre':       'linear',
    'Conut Jnah':         'log',
    'Main Street Coffee': 'linear',
}

OUTLIERS          = {'Conut - Tyre': [10]}
RAMP_UP_THRESHOLD = 0.30
N_BOOTSTRAP       = 2000
CI_LOWER          = 10
CI_UPPER          = 90

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def impute_outliers(branch_df, branch_name):
    if branch_name not in OUTLIERS:
        return branch_df.copy(), False
    outlier_months = OUTLIERS[branch_name]
    clean_mean     = branch_df[~branch_df['month'].isin(outlier_months)]['sales'].mean()
    result         = branch_df.copy()
    result.loc[result['month'].isin(outlier_months), 'sales'] = clean_mean
    return result, True

def detect_rampup(branch_df):
    d = branch_df.sort_values('month').reset_index(drop=True)
    if len(d) >= 2:
        ratio = d['sales'].iloc[0] / d['sales'].iloc[1]
        if ratio < RAMP_UP_THRESHOLD:
            return d.iloc[1:].reset_index(drop=True), True, d['month'].iloc[0]
    return d, False, None

def bootstrap_ci_linear(X_train, y_train, future_idx, seed=42):
    """Bootstrap CI on raw scale for linear model."""
    rng   = np.random.default_rng(seed)
    base  = LinearRegression().fit(X_train, y_train)
    resids = y_train - base.predict(X_train)
    n     = len(X_train)
    boot  = np.zeros((N_BOOTSTRAP, len(future_idx)))
    for i in range(N_BOOTSTRAP):
        y_boot  = base.predict(X_train) + rng.choice(resids, size=n, replace=True)
        m       = LinearRegression().fit(X_train, y_boot)
        noise   = rng.choice(resids, size=len(future_idx), replace=True)
        boot[i] = np.maximum(m.predict(future_idx) + noise, 0)
    point = np.maximum(base.predict(future_idx), 0)
    lower = np.maximum(np.percentile(boot, CI_LOWER, axis=0), 0)
    upper = np.maximum(np.percentile(boot, CI_UPPER, axis=0), 0)
    return point, lower, upper

def bootstrap_ci_log(X_train, log_y, future_idx, seed=42):
    """Bootstrap CI on log scale → exponentiate back."""
    rng       = np.random.default_rng(seed)
    base      = LinearRegression().fit(X_train, log_y)
    point_log = base.predict(future_idx)
    resids    = log_y - base.predict(X_train)
    # Fallback: ±20% if zero residuals (2-point fit)
    if np.std(resids) < 1e-8:
        point = np.exp(point_log)
        return point, point * 0.80, point * 1.20, True
    n    = len(X_train)
    boot = np.zeros((N_BOOTSTRAP, len(future_idx)))
    for i in range(N_BOOTSTRAP):
        y_boot  = base.predict(X_train) + rng.choice(resids, size=n, replace=True)
        m       = LinearRegression().fit(X_train, y_boot)
        noise   = rng.choice(resids, size=len(future_idx), replace=True)
        boot[i] = m.predict(future_idx) + noise
    point = np.exp(point_log)
    lower = np.exp(np.percentile(boot, CI_LOWER, axis=0))
    upper = np.exp(np.percentile(boot, CI_UPPER, axis=0))
    return np.maximum(point,0), np.maximum(lower,0), np.maximum(upper,0), False

# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

results   = {}
eval_rows = []

for branch in df['branch'].unique():
    branch_df   = df[df['branch'] == branch].copy()
    branch_type = branch_df['branch_type'].iloc[0]
    method      = BRANCH_METHOD[branch]

    print(f"\n{'='*65}")
    print(f"Branch: {branch}  [{branch_type.upper()}]  →  Method: {method.upper()}")

    # ── Impute outliers ──
    branch_df, outlier_imputed = impute_outliers(branch_df, branch)
    if outlier_imputed:
        print(f"  [Outlier Imputed] Month(s) {OUTLIERS[branch]} → branch mean")

    # ── Separate December ──
    dec_row  = branch_df[branch_df['month'] == 12].copy()
    trend_df = branch_df[branch_df['month'] != 12].copy()

    # ── Ramp-up removal (only for log branches with opening months) ──
    rampup, rampup_month = False, None
    if method == 'log':
        trend_df, rampup, rampup_month = detect_rampup(trend_df)
        if rampup:
            print(f"  [Ramp-up Removed] Month {rampup_month} excluded")

    trend_df = trend_df.reset_index(drop=True)
    trend_df['time_index'] = range(len(trend_df))

    X_all = trend_df[['time_index']].values
    y_all = trend_df['sales'].values

    # ── Holdout eval ──
    ci_fallback = False
    if len(trend_df) >= 3:
        X_tr = X_all[:-1];  y_tr = y_all[:-1]
        X_te = X_all[-1:];  y_te = y_all[-1:]
        if method == 'linear':
            eval_mod  = LinearRegression().fit(X_tr, y_tr)
            pred_sale = eval_mod.predict(X_te)[0]
        else:
            log_tr    = np.log(y_tr)
            eval_mod  = LinearRegression().fit(X_tr, log_tr)
            pred_sale = np.exp(eval_mod.predict(X_te)[0])
        mape = abs(pred_sale - y_te[0]) / y_te[0] * 100
        acc  = 100 - mape
        print(f"  MAPE: {mape:.1f}%  →  Accuracy: {acc:.1f}%")
    else:
        mape, acc = None, None
        print(f"  Only {len(trend_df)} trend points — holdout skipped")

    # ── December multiplier ──
    dec_mult = None
    if len(dec_row) > 0 and branch_type == 'commercial':
        dec_sales  = dec_row['sales'].values[0]
        nov_data   = trend_df[trend_df['month'] == 11]['sales'].values
        base_sales = nov_data[0] if len(nov_data) > 0 else y_all[-1]
        dec_mult   = dec_sales / base_sales
        print(f"  [Dec Multiplier] {base_sales:,.0f} → {dec_sales:,.0f} = {dec_mult:.3f}x")

    # ── Forecast future months ──
    last_idx  = len(trend_df)
    n_future  = 4 if branch_type == 'academic' else 3
    future_idx = np.array([[last_idx + i] for i in range(1, n_future + 1)])

    if method == 'linear':
        point, lower, upper = bootstrap_ci_linear(X_all, y_all, future_idx)
    else:
        log_y = np.log(y_all)
        point, lower, upper, ci_fallback = bootstrap_ci_log(X_all, log_y, future_idx)
        if ci_fallback:
            print(f"  [CI Fallback] Only 2 training points → ±20% band")

    # ── Build monthly forecast dict ──
    if branch_type == 'academic':
        month_labels = ['August_2026', 'September_2026', 'October_2026', 'November_2026']
    else:
        month_labels = ['January_2026', 'February_2026', 'March_2026']

    monthly = {}
    print(f"\n  {'Month':<22} {'⬇ Worst (P10)':>15} {'● Expected':>14} {'⬆ Best (P90)':>14}")
    print(f"  {'-'*68}")
    for i, label in enumerate(month_labels):
        monthly[label] = {
            'worst':    round(lower[i], 0),
            'expected': round(point[i], 0),
            'best':     round(upper[i], 0),
        }
        print(f"  {label:<22} {lower[i]:>15,.0f} {point[i]:>14,.0f} {upper[i]:>14,.0f}")

    # ── December 2026 projection ──
    if branch_type == 'academic':
        monthly['December_2026'] = {
            'worst': 50000000, 'expected': 68000000, 'best': 90000000,
            'note': 'Semester break — based on 2025 observed (~68M)'
        }
        print(f"  {'December_2026':<22} {'50,000,000':>15} {'68,000,000':>14} {'90,000,000':>14}  ← semester break")

    elif dec_mult:
        nov_step   = np.array([[last_idx + 10]])   # Nov 2026
        if method == 'linear':
            nov_pt, nov_lo, nov_hi = bootstrap_ci_linear(X_all, y_all, nov_step)
        else:
            log_y   = np.log(y_all)
            nov_pt, nov_lo, nov_hi, _ = bootstrap_ci_log(X_all, log_y, nov_step)
        monthly['November_2026'] = {
            'worst': round(nov_lo[0],0), 'expected': round(nov_pt[0],0),
            'best':  round(nov_hi[0],0)
        }
        monthly['December_2026'] = {
            'worst':    round(nov_lo[0] * dec_mult, 0),
            'expected': round(nov_pt[0] * dec_mult, 0),
            'best':     round(nov_hi[0] * dec_mult, 0),
            'note':     f'Multiplier {dec_mult:.2f}x applied to Nov 2026 forecast'
        }
        print(f"  {'November_2026':<22} {nov_lo[0]:>15,.0f} {nov_pt[0]:>14,.0f} {nov_hi[0]:>14,.0f}  ← trend")
        print(f"  {'December_2026':<22} {nov_lo[0]*dec_mult:>15,.0f} "
              f"{nov_pt[0]*dec_mult:>14,.0f} {nov_hi[0]*dec_mult:>14,.0f}  ← {dec_mult:.2f}x Nov")

    eval_rows.append({
        'branch':          branch,
        'branch_type':     branch_type,
        'method':          method,
        'outlier_imputed': outlier_imputed,
        'rampup_removed':  rampup,
        'trend_points':    len(trend_df),
        'ci_fallback':     ci_fallback,
        'MAPE_pct':        round(mape, 1) if mape is not None else 'N/A',
        'Accuracy_pct':    round(acc,  1) if acc  is not None else 'N/A',
        'Dec_multiplier':  round(dec_mult, 3) if dec_mult else ('~68M fixed' if branch_type=='academic' else 'N/A'),
    })

    results[branch] = {
        'branch_type':     branch_type,
        'method':          method,
        'outlier_imputed': outlier_imputed,
        'rampup':          rampup,
        'ci_fallback':     ci_fallback,
        'monthly':         monthly,
        'mape':            round(mape, 1) if mape is not None else None,
        'accuracy':        round(acc,  1) if acc  is not None else None,
        'dec_mult':        dec_mult,
    }

# ─────────────────────────────────────────────
# MASTER SUMMARY
# ─────────────────────────────────────────────

print("\n\n" + "="*80)
print("BEST-PER-BRANCH FORECAST  —  MASTER SUMMARY")
print("="*80)
print(f"  {'Branch':<22} {'Method':<10} {'Accuracy':>10}   {'Rationale'}")
print(f"  {'-'*72}")
rationale = {
    'Conut':              'Clean linear trend — log adds distortion',
    'Conut - Tyre':       'Stable post-imputation — linear generalizes better',
    'Conut Jnah':         'Exponential growth pattern — log transform wins',
    'Main Street Coffee': 'Only 2 log points — linear more reliable',
}
for branch, f in results.items():
    acc_str = f"{f['accuracy']}%" if f['accuracy'] is not None else "N/A*"
    print(f"  {branch:<22} {f['method'].upper():<10} {acc_str:>10}   {rationale[branch]}")

print("\n\n" + "="*80)
print("FULL FORECAST  —  ALL BRANCHES")
print(f"CI: Residual Bootstrap (N={N_BOOTSTRAP}, P{CI_LOWER}–P{CI_UPPER})")
print("="*80)

for branch, f in results.items():
    tags = []
    if f['outlier_imputed']: tags.append("outlier imputed")
    if f['rampup']:          tags.append("ramp-up removed")
    if f['ci_fallback']:     tags.append("CI=±20% fallback")
    tag_str = f"  [{', '.join(tags)}]" if tags else ""
    acc_str  = f"{f['accuracy']}%" if f['accuracy'] is not None else "N/A"

    print(f"\n📍 {branch} ({f['branch_type'].upper()})  |  Method: {f['method'].upper()}{tag_str}")
    print(f"   Accuracy: {acc_str}  |  MAPE: {f['mape']}%" if f['mape'] else f"   Accuracy: {acc_str}")
    if f['dec_mult']:
        print(f"   December multiplier: {f['dec_mult']:.3f}x")
    print()
    print(f"   {'Month':<22} {'⬇ Worst (P10)':>15} {'● Expected':>14} {'⬆ Best (P90)':>14}")
    print(f"   {'-'*68}")
    for label, vals in f['monthly'].items():
        note = f"  ← {vals['note']}" if 'note' in vals else ''
        print(f"   {label:<22} {vals['worst']:>15,.0f} "
              f"{vals['expected']:>14,.0f} "
              f"{vals['best']:>14,.0f}{note}")

# ─────────────────────────────────────────────
# FINAL ACCURACY LEADERBOARD
# ─────────────────────────────────────────────

all_methods = {
    'Conut':              {'linear': 95.8, 'optimized': 86.4, 'ensemble': 92.9, 'log_mult': 79.9},
    'Conut - Tyre':       {'linear': 69.6, 'optimized': 96.6, 'ensemble':100.0, 'log_mult': 77.9},
    'Conut Jnah':         {'linear': 40.3, 'optimized': 33.6, 'ensemble': 37.4, 'log_mult': 65.7},
    'Main Street Coffee': {'linear': 57.6, 'optimized': 40.5, 'ensemble': 54.7, 'log_mult': None},
}

print("\n\n" + "="*80)
print("FINAL ACCURACY LEADERBOARD  —  All Methods Compared")
print("="*80)
print(f"\n{'Branch':<22} {'Linear':>10} {'Optimized':>12} {'Ensemble':>12} {'Log+Mult':>12}  {'✅ Best Used':>14}")
print("-" * 86)
for branch, f in results.items():
    m   = all_methods[branch]
    cur = f['accuracy']
    print(f"{branch:<22} {m['linear']:>9.1f}%  {m['optimized']:>10.1f}%  "
          f"{m['ensemble']:>10.1f}%  "
          f"{str(m['log_mult'])+'%' if m['log_mult'] else 'N/A':>11}  "
          f"  {f['method'].upper()} ({cur}%)" if cur else f"  {f['method'].upper()} (N/A)")

print("\n" + "="*80)
print("⚠️  Disclaimer: 4-5 months of data only. Directional estimates ±20%.")
print("    December 2026 assumes same seasonal pattern as 2025.")
print("="*80)

# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────

eval_df = pd.DataFrame(eval_rows)
eval_df.to_csv('model_evaluation_best_per_branch.csv', index=False)

forecast_rows = []
for branch, f in results.items():
    for month, vals in f['monthly'].items():
        forecast_rows.append({
            'branch':          branch,
            'branch_type':     f['branch_type'],
            'method':          f['method'],
            'period':          month,
            'worst_case':      vals['worst'],
            'expected':        vals['expected'],
            'best_case':       vals['best'],
            'is_dec_estimate': 'note' in vals,
            'accuracy_pct':    f['accuracy'],
        })

pd.DataFrame(forecast_rows).to_csv('demand_forecasts_best_per_branch.csv', index=False)
print("\n✅ Saved: model_evaluation_best_per_branch.csv")
print("✅ Saved: demand_forecasts_best_per_branch.csv")