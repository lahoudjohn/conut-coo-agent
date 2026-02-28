# Executive Brief Template

## Title
Conut AI COO Agent: Operational Decision Support for Growth, Inventory, and Staffing

## 1. Problem Framing
- Conut needs an operations assistant that converts historical sales and operational records into practical branch-level decisions.
- The dataset is noisy report-style CSV data, so robust ingestion and cleaning are required before analytics.
- The business needs support across five specific decisions: combos, forecasting, expansion, staffing, and coffee/milkshake growth.

## 2. Solution Overview
- We built a FastAPI-based COO agent exposing structured tool endpoints.
- The system ingests raw CSV reports, cleans repeated headers/page markers, caches standardized parquet files, engineers operational features, and serves business recommendations.
- OpenClaw can call the tool endpoints directly using JSON.

## 3. Top Findings
Add your actual outputs here after running the pipeline.

Suggested subsections:
- Best-performing product combinations
- Highest-demand branches and peak periods
- Best internal analogs for expansion
- Branches with highest staffing pressure
- Coffee and milkshake whitespace opportunities

## 4. Recommended Actions
List 3 to 5 concrete actions, for example:
- Launch branch-specific bundles around top co-purchase pairs
- Increase prep staffing on high-pressure evening shifts
- Pilot new branch expansion only in regions matching top benchmark branches
- Prioritize menu placement and combo upsells for under-indexing beverage categories

## 5. Expected Impact
Translate findings into operational impact:
- lower stockouts
- better labor alignment
- improved ticket size
- stronger beverage attach rate
- reduced expansion risk

## 6. Risks and Constraints
- Scaled data preserves patterns, not absolute financial values
- Internal-only expansion scoring lacks external footfall/rent data
- Keyword-based category detection depends on naming consistency
- Initial forecasting is a baseline model, not a production-grade time-series stack

## 7. Demo Evidence
Reference:
- `/docs/architecture.png`
- `/demo/`
- OpenClaw tool invocation screenshots/video

## 8. Appendix
Include:
- endpoint list
- assumptions
- sample JSON outputs
