/* Generated placeholder. Replace by running: npm run generate:client */

export interface paths {
  "/tools/recommend_combos": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            branch?: string;
            top_n?: number;
            min_support?: number;
          };
        };
      };
    };
  };
  "/tools/forecast_demand": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            branch: string;
            horizon_days?: number;
          };
        };
      };
    };
  };
  "/tools/estimate_staffing": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            branch: string;
            shift?: "morning" | "afternoon" | "evening" | "night";
            target_date?: string;
          };
        };
      };
    };
  };
  "/tools/expansion_feasibility": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            candidate_location: string;
            target_region?: string;
          };
        };
      };
    };
  };
  "/tools/growth_strategy": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            branch?: string;
            focus_categories?: string[];
          };
        };
      };
    };
  };
}
