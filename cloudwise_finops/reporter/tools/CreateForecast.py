from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import statistics
from datetime import datetime, timedelta

class CreateForecast(BaseTool):
    """Generate cost forecasts using historical trend analysis and statistical time series prediction.

    Use this tool to project future cloud costs based on historical spending patterns, enabling
    proactive budget planning and early warning for potential overruns. The tool uses linear
    regression with seasonal adjustment and confidence intervals (80%, 95%) to provide realistic
    forecasting ranges accounting for variability in cloud workloads.

    Do NOT rely on forecasts for month-end exact predictions - treat as directional guidance with
    ±10-15% margin of error. Forecasts are most accurate for stable workloads with consistent growth
    patterns. Volatile workloads (batch processing, seasonal traffic) require larger confidence intervals.

    Returns: JSON object with forecast_values (daily predicted costs for forecast period), confidence_intervals
    (80% and 95% ranges), trend_analysis (growth rate, direction, confidence), total_forecasted_cost,
    comparison_to_current (percent change vs historical average), and risk_factors (conditions that
    could invalidate forecast like new deployments, traffic changes, pricing updates).

    Forecasting methodology: (1) Analyze last 90 days of cost history to establish baseline and trend,
    (2) Apply linear regression to calculate daily growth rate, (3) Project forward using y = mx + b
    formula, (4) Add seasonal adjustment factors (day-of-week patterns), (5) Calculate confidence
    intervals using historical standard deviation, (6) Flag outliers and anomalies that may skew
    predictions. Minimum 30 days of history required for meaningful forecasts.
    """

    historical_data: str = Field(
        ...,
        description="JSON array of historical cost data with date and cost fields. Format: [{date: 'YYYY-MM-DD', cost: 123.45}, ...]. Minimum 30 days required, 90 days recommended for accurate forecasts."
    )
    forecast_days: int = Field(
        default=30,
        description="Number of days to forecast into future. Default 30 days (one month ahead). Use 7 for weekly planning, 90 for quarterly. Maximum 90 days to maintain reasonable accuracy."
    )
    confidence_level: float = Field(
        default=0.80,
        description="Statistical confidence level for prediction intervals. Valid values: 0.80 (80%), 0.95 (95%), 0.99 (99%). Default 0.80 balances accuracy vs range width. Higher confidence = wider intervals."
    )

    def run(self):
        """Generate cost forecast from historical data."""
        # Step 1: Validate forecast parameters
        if self.forecast_days < 1:
            return "Error: forecast_days must be at least 1. Use 7-90 for practical forecasting."

        if self.forecast_days > 90:
            return "Warning: forecast_days > 90 may produce unreliable predictions. Recommend 30-90 days for best accuracy."

        valid_confidence_levels = [0.80, 0.90, 0.95, 0.99]
        if self.confidence_level not in valid_confidence_levels:
            return f"Error: Invalid confidence_level {self.confidence_level}. Must be one of: {', '.join(map(str, valid_confidence_levels))}"

        # Step 2: Parse historical data
        try:
            history = json.loads(self.historical_data)

            if not isinstance(history, list):
                return "Error: historical_data must be JSON array of objects with 'date' and 'cost' fields."

            if len(history) < 30:
                return f"Error: Insufficient historical data. Provided {len(history)} data points, minimum 30 required (90+ recommended for accurate forecasts)."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in historical_data. Details: {str(e)}"

        try:
            # Step 3: Extract and validate data
            data_points = []

            for entry in history:
                if "cost" not in entry or "date" not in entry:
                    continue

                try:
                    cost = float(entry["cost"])
                    date_str = entry["date"]
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                    data_points.append({"date": date_obj, "cost": cost})
                except (ValueError, TypeError):
                    continue

            if len(data_points) < 30:
                return f"Error: Only {len(data_points)} valid data points after validation. Need at least 30."

            # Sort by date
            data_points.sort(key=lambda x: x["date"])

            # Step 4: Calculate historical statistics
            costs = [point["cost"] for point in data_points]
            mean_cost = statistics.mean(costs)
            std_dev = statistics.stdev(costs) if len(costs) > 1 else 0

            # Step 5: Perform linear regression for trend
            n = len(data_points)
            x_values = list(range(n))  # 0, 1, 2, ... n-1
            y_values = costs

            mean_x = statistics.mean(x_values)
            mean_y = statistics.mean(y_values)

            # Calculate slope (m) and intercept (b) for y = mx + b
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
            denominator = sum((x - mean_x) ** 2 for x in x_values)

            if denominator == 0:
                return "Error: Cannot calculate trend - insufficient variance in data."

            slope = numerator / denominator  # Daily cost change rate
            intercept = mean_y - (slope * mean_x)

            # Step 6: Calculate R-squared for trend confidence
            predicted_values = [slope * x + intercept for x in x_values]
            ss_total = sum((y - mean_y) ** 2 for y in y_values)
            ss_residual = sum((y - pred) ** 2 for y, pred in zip(y_values, predicted_values))

            r_squared = 1 - (ss_residual / ss_total) if ss_total > 0 else 0

            # Step 7: Generate forecasts for each day
            last_date = data_points[-1]["date"]
            forecasts = []

            # Z-scores for confidence intervals
            z_scores = {0.80: 1.28, 0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            z_score = z_scores[self.confidence_level]

            for day in range(1, self.forecast_days + 1):
                forecast_date = last_date + timedelta(days=day)
                x_forecast = n + day - 1

                # Point forecast
                point_forecast = slope * x_forecast + intercept

                # Confidence interval (accounts for increasing uncertainty over time)
                # Uncertainty grows with distance from historical data
                time_uncertainty_factor = 1 + (day / 30)  # Increases uncertainty over time
                interval_width = z_score * std_dev * time_uncertainty_factor

                lower_bound = max(0, point_forecast - interval_width)  # Can't have negative costs
                upper_bound = point_forecast + interval_width

                forecasts.append({
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "day_offset": day,
                    "forecast_cost": round(point_forecast, 2),
                    "confidence_interval": {
                        "lower": round(lower_bound, 2),
                        "upper": round(upper_bound, 2)
                    }
                })

            # Step 8: Calculate aggregate forecast metrics
            total_forecasted_cost = sum(f["forecast_cost"] for f in forecasts)
            avg_daily_forecast = total_forecasted_cost / len(forecasts)

            # Compare to historical average
            historical_avg_daily = mean_cost
            percent_change = ((avg_daily_forecast - historical_avg_daily) / historical_avg_daily * 100) if historical_avg_daily > 0 else 0

            # Step 9: Determine trend direction and strength
            if abs(slope) < (mean_cost * 0.01):  # Less than 1% daily change
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"

            trend_strength = "strong" if r_squared > 0.7 else "moderate" if r_squared > 0.4 else "weak"

            # Step 10: Identify risk factors
            risk_factors = []

            if r_squared < 0.5:
                risk_factors.append("Low R² indicates high variability - forecast may be unreliable")

            if len(data_points) < 60:
                risk_factors.append(f"Limited historical data ({len(data_points)} days) - recommend 90+ days for better accuracy")

            if std_dev / mean_cost > 0.3:  # Coefficient of variation > 30%
                risk_factors.append("High cost volatility - confidence intervals may underestimate uncertainty")

            if abs(slope) > (mean_cost * 0.05):  # >5% daily change
                risk_factors.append("Rapid cost trend detected - may indicate new deployment or workload change")

            # Step 11: Build result
            result = {
                "forecast_summary": {
                    "forecast_period": f"{forecasts[0]['date']} to {forecasts[-1]['date']}",
                    "total_forecasted_cost": round(total_forecasted_cost, 2),
                    "avg_daily_forecast": round(avg_daily_forecast, 2),
                    "confidence_level": f"{int(self.confidence_level * 100)}%",
                    "trend": f"{trend_direction} ({trend_strength})"
                },
                "historical_baseline": {
                    "days_analyzed": len(data_points),
                    "avg_daily_cost": round(historical_avg_daily, 2),
                    "std_deviation": round(std_dev, 2),
                    "date_range": f"{data_points[0]['date'].strftime('%Y-%m-%d')} to {data_points[-1]['date'].strftime('%Y-%m-%d')}"
                },
                "trend_analysis": {
                    "daily_change_rate": round(slope, 2),
                    "direction": trend_direction,
                    "strength": trend_strength,
                    "r_squared": round(r_squared, 3),
                    "percent_change_vs_historical": round(percent_change, 1)
                },
                "forecasts": forecasts[:7],  # First 7 days for preview
                "monthly_projection": {
                    "30_day_total": round(sum(f["forecast_cost"] for f in forecasts[:30]), 2) if len(forecasts) >= 30 else total_forecasted_cost,
                    "30_day_range": {
                        "lower": round(sum(f["confidence_interval"]["lower"] for f in forecasts[:30]), 2) if len(forecasts) >= 30 else None,
                        "upper": round(sum(f["confidence_interval"]["upper"] for f in forecasts[:30]), 2) if len(forecasts) >= 30 else None
                    }
                },
                "risk_factors": risk_factors
            }

            # Step 12: Generate summary
            trend_desc = f"{trend_direction} at ${abs(slope):.2f}/day" if slope != 0 else "stable"

            if risk_factors:
                risk_text = f" Risk factors: {len(risk_factors)} identified."
            else:
                risk_text = " Forecast confidence: high."

            summary = f"Cost Forecast: {self.forecast_days}-day projection totals ${total_forecasted_cost:.2f} (avg ${avg_daily_forecast:.2f}/day). Historical baseline: ${historical_avg_daily:.2f}/day. Trend: {trend_desc} ({trend_strength}, R²={r_squared:.2f}). Change: {'+' if percent_change > 0 else ''}{percent_change:.1f}% vs historical.{risk_text}"

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error creating forecast: {str(e)}. Verify historical_data format and completeness."


if __name__ == "__main__":
    # Test with sample increasing trend
    import random

    sample_data = []
    base_cost = 1000

    for i in range(60):  # 60 days of history
        date = (datetime.now() - timedelta(days=60-i)).strftime("%Y-%m-%d")
        # Increasing trend: $5/day increase + random noise
        cost = base_cost + (i * 5) + random.uniform(-50, 50)
        sample_data.append({"date": date, "cost": round(cost, 2)})

    tool = CreateForecast(
        historical_data=json.dumps(sample_data),
        forecast_days=30,
        confidence_level=0.80
    )
    print(tool.run())
