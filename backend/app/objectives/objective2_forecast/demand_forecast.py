import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

def forecast_future_demand_wma(processed_data_path="data/processed", forecast_horizon=3):
    """
    Executes a 3-Period Weighted Moving Average (WMA) forecast.
    Weights are distributed as 50% (most recent), 30% (middle), 20% (oldest).
    """
    report = "\n" + "="*80 + "\n"
    report += "📈 CHIEF OF OPERATIONS: 3-MONTH WMA FORECAST\n"
    report += "="*80 + "\n"

    # Define our WMA weights (Must add up to 1.0)
    # Ordered from oldest to newest: t-2 (20%), t-1 (30%), t (50%)
    weights = np.array([0.2, 0.3, 0.5])
    window_size = len(weights)

    try:
        # 1. Load and Clean Data
        file_path = os.path.join(processed_data_path, "REP_S_00334_1_SMRY_cleaned.csv")
        df = pd.read_csv(file_path)
        
        df = df.sort_values(by=['year', 'month'])
        df = df.groupby(['branch_name', 'year', 'month'], as_index=False)['total_sales'].sum()
        df['time_step'] = df.groupby('branch_name').cumcount() + 1
        
        max_months = df['time_step'].max()

        report += "🏢 MODEL ARCHITECTURE: 3-Period Weighted Moving Average (Iterative)\n"
        report += f"⚖️  WEIGHT DISTRIBUTION: 50% Recent | 30% Previous | 20% Oldest\n"
        report += f"⏳ DATA RANGE: Trained up to Month {max_months}\n"
        report += f"🔮 FORECASTING: Months {max_months + 1} to {max_months + forecast_horizon}\n\n"
        report += "📍 PER-BRANCH PROJECTIONS:\n"

        plot_data = {}

        # 2. Iterate through each unique branch
        for branch in df['branch_name'].unique():
            branch_df = df[df['branch_name'] == branch].copy()
            
            # WMA requires at least 'window_size' (3) historical data points to start
            if len(branch_df) < window_size:
                report += f"   * {branch.upper()}: Insufficient data (Needs at least {window_size} months).\n"
                continue
            
            X_train = branch_df['time_step'].values
            y_train = branch_df['total_sales'].values

            # Create future time steps for the X-axis
            future_steps = np.arange(max_months + 1, max_months + 1 + forecast_horizon)
            
            # 3. Execute Iterative WMA
            predictions = []
            
            # Grab the last 3 actual months to seed the first prediction
            current_window = list(y_train[-window_size:])
            
            for _ in range(forecast_horizon):
                # Calculate the weighted average (Dot product multiplies values by their respective weights and sums them)
                next_val = np.dot(current_window, weights)
                
                # Prevent physically impossible negative sales
                next_val = max(next_val, 0)
                predictions.append(next_val)
                
                # Slide the window forward: remove the oldest value, append the brand new forecast
                current_window.pop(0)
                current_window.append(next_val)
            
            report += f"   * {branch.upper()}:\n"
            for i, step in enumerate(future_steps):
                report += f"       - Month {step}: ~{predictions[i]:,.2f} projected units\n"

            plot_data[branch] = {
                'X_train': X_train, 'y_train': y_train,
                'X_future': future_steps, 'predictions': predictions,
                'max_historical_month': max_months
            }
        
    except FileNotFoundError:
        report += f"❌ ERROR: Could not find CSV file in {processed_data_path}.\n"
        return report, None
    except Exception as e:
        report += f"❌ UNEXPECTED ERROR: {e}\n"
        return report, None

    report += "\n" + "="*80 + "\n"
    report += "🤖 AGENT VERDICT: RESOURCE ALLOCATION\n"
    report += "Forecast utilizes a Weighted Moving Average to establish a highly stable, conservative operational baseline.\n"
    report += "="*80 + "\n"
    
    return report, plot_data


if __name__ == "__main__":
    processed_path = os.path.join("backend", "data", "processed")
    final_report, plotting_data = forecast_future_demand_wma(processed_path)
    
    print(final_report)
    
    # --- DYNAMIC PLOTTING BLOCK ---
    if plotting_data is not None and len(plotting_data) > 0:
        plt.figure(figsize=(12, 7))
        colors = {'Conut': 'blue', 'Conut - Tyre': 'orange', 'Conut Jnah': 'green'} 
        
        for branch, data in plotting_data.items():
            color = colors.get(branch, 'black')
            
            # Plot Actual History
            plt.plot(data['X_train'], data['y_train'], marker='o', 
                     color=color, alpha=0.6, label=f'History ({branch})')

            # Plot Future Forecast
            plt.plot(data['X_future'], data['predictions'], marker='x',
                     color=color, linestyle='--', linewidth=2.5, label=f'WMA Forecast ({branch})')

            # Connect the last historical point to the first forecast point so the line doesn't break
            plt.plot([data['X_train'][-1], data['X_future'][0]], 
                     [data['y_train'][-1], data['predictions'][0]], 
                     color=color, linestyle='--', linewidth=2.5, alpha=0.5)

        # Draw a line separating History from the Future
        actual_split = list(plotting_data.values())[0]['max_historical_month']
        plt.axvline(x=actual_split + 0.5, color='red', linestyle=':', linewidth=2, label='Present Day')

        plt.title('3-Month WMA Operational Demand Forecast', fontsize=16, fontweight='bold')
        plt.xlabel('Time (Months)', fontsize=12)
        plt.ylabel('Total Sales / Output', fontsize=12)

        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize=10)
        plt.grid(True, linestyle=':', alpha=0.7)
        plt.tight_layout()

        plt.show()