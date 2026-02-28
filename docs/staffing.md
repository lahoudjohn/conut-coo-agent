# Staffing Tool

## Overview

Objective 4 estimates required staff per shift using two internal signals:

- Attendance history from `REP_S_00461_cleaned.csv`
- Monthly branch sales from `REP_S_00334_1_SMRY_cleaned.csv`

The tool turns attendance into shift-level labor supply features, estimates branch productivity as sales per labor hour, and converts the requested demand level into a recommended headcount for a target shift.

## Inputs

Supported Objective 4 tools:

- `POST /tools/estimate_staffing`
- `POST /tools/understaffed_branches`
- `POST /tools/average_shift_length`

Request fields:

- `branch`
- `target_period` (`YYYY-MM`, optional)
- `day_of_week` (`Mon`..`Sun`, optional)
- `shift_name` (`morning`, `afternoon`, `evening`, `night`)
- `shift_hours` (default `8.0`)
- `buffer_pct` (default `0.15`)
- `demand_override` (optional manual demand proxy, usually from a forecast tool)

## Output

The response includes:

- `recommended_staff`
- `required_labor_hours`
- `productivity_sales_per_labor_hour`
- `demand_used`
- `evidence`
- `assumptions`
- `data_coverage`

`evidence` shows which productivity period was used, what sales value was used as demand, the historical shift labor/headcount statistics, and any fallback logic applied.

Example questions OpenClaw can map now:

- "How many staff do we need at Main Street Coffee on a busy shift?"
  Use `POST /tools/estimate_staffing`
- "Which branch is understaffed relative to its sales volume?"
  Use `POST /tools/understaffed_branches`
- "What's the average shift length across branches?"
  Use `POST /tools/average_shift_length`

## Current Method

1. Parse attendance timestamps.
2. Bucket each attendance row into a shift based on punch-in time.
3. Build average daily labor-hours and headcount by branch and shift.
4. Compute branch productivity as `monthly_sales / total_labor_hours_month`.
5. Convert the requested demand into monthly required labor hours.
6. Allocate those labor hours to the requested shift using historical shift share.
7. Convert shift labor hours into headcount, then apply the requested staffing buffer.

## Limitations

- Sales are monthly, so intra-day demand peaks are approximated from historical labor share rather than real daily demand.
- Values are scaled units, so recommendations are relative rather than absolute.
- Branch productivity is only as precise as the monthly branch summary alignment.
- Shift definitions are based only on punch-in hour and do not model mid-shift overlap.

## Next Improvements

- Replace monthly sales with daily sales or transaction timestamps for more precise shift demand.
- Blend this tool with the forecast tool so `demand_override` comes from branch-level demand forecasts automatically.
- Add role-based staffing (barista, kitchen, cashier) instead of total headcount only.
