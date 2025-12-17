from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import statistics
from datetime import datetime, timedelta

class CalculateBaseline(BaseTool):
    """Compute statistical baseline for cost patterns using rolling window average with seasonal adjustment.

    Use this tool to establish expected cost ranges for anomaly detection by analyzing historical
    cost data over a configurable window (default 30 days). The baseline calculation includes
    mean, standard deviation, and seasonal factors to account for predictable weekly or monthly
    patterns (e.g., higher weekend batch processing costs).

    Do NOT use this tool with less than 14 days of historical data - insufficient data produces
    unreliable baselines with high false positive rates. For new resources or services, wait until
    adequate history accumulates before enabling anomaly detection.

    Returns: JSON object containing baseline_mean (average expected cost), std_deviation (variance),
    seasonal_factors (day-of-week multipliers), confidence_interval (±2 standard deviations), and
    sample_size (number of data points analyzed). These metrics feed into DetectSpike and
    DetectTrendChange tools for anomaly identification.

    The seasonal adjustment identifies if certain days consistently have higher/lower costs
    (e.g., batch jobs on Sundays) and factors this into the baseline to reduce false positives.
    """

    cost_history: str = Field(
        ...,
        description="JSON array of historical cost data points with date and cost fields. Format: [{date: 'YYYY-MM-DD', cost: 123.45}, ...]. Minimum 14 data points required for reliable baseline."
    )
    window_days: int = Field(
        default=30,
        description="Number of days to include in rolling window calculation. Default 30 days balances responsiveness vs stability. Use 14 for faster detection, 60 for more stable baselines."
    )
    enable_seasonal_adjustment: bool = Field(
        default=True,
        description="Enable day-of-week seasonal adjustment to account for predictable patterns. Set to False for resources with uniform daily costs."
    )

    def run(self):
        """Calculate baseline cost metrics from historical data."""
        # Step 1: Parse and validate cost history
        try:
            history = json.loads(self.cost_history)

            if not isinstance(history, list):
                return "Error: cost_history must be JSON array of objects with 'date' and 'cost' fields. Example: [{\"date\": \"2025-12-01\", \"cost\": 100.5}, ...]"

            if len(history) < 14:
                return f"Error: Insufficient historical data. Provided {len(history)} data points, minimum 14 required for reliable baseline. Wait until more cost history accumulates."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in cost_history. Details: {str(e)}"

        # Step 2: Validate window_days
        if self.window_days < 7:
            return "Error: window_days must be at least 7 for meaningful baseline. Use 14-60 days for optimal results."

        if self.window_days > len(history):
            # Cap window_days to available data instead of returning early
            self.window_days = len(history)

        try:
            # Step 3: Extract costs and validate data
            costs = []
            dates = []

            for entry in history:
                if "cost" not in entry or "date" not in entry:
                    continue

                try:
                    cost = float(entry["cost"])
                    date_str = entry["date"]
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                    costs.append(cost)
                    dates.append(date_obj)
                except (ValueError, TypeError):
                    continue

            if len(costs) < 14:
                return f"Error: Only {len(costs)} valid cost entries found after validation. Need at least 14."

            # Step 4: Calculate rolling window (use most recent window_days)
            window_costs = costs[-self.window_days:]
            window_dates = dates[-self.window_days:]

            # Step 5: Calculate baseline statistics
            baseline_mean = statistics.mean(window_costs)
            std_deviation = statistics.stdev(window_costs) if len(window_costs) > 1 else 0

            # Step 6: Calculate seasonal factors (day of week patterns)
            seasonal_factors = {}

            if self.enable_seasonal_adjustment and len(window_costs) >= 14:
                # Group costs by day of week
                day_costs = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday

                for date, cost in zip(window_dates, window_costs, strict=True):
                    day_of_week = date.weekday()
                    day_costs[day_of_week].append(cost)

                # Calculate day-of-week multipliers
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

                for day_num, day_name in enumerate(day_names):
                    if day_costs[day_num]:
                        day_avg = statistics.mean(day_costs[day_num])
                        seasonal_factors[day_name] = round(day_avg / baseline_mean, 3) if baseline_mean > 0 else 1.0
                    else:
                        seasonal_factors[day_name] = 1.0
            else:
                # No seasonal adjustment
                seasonal_factors = {day: 1.0 for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}

            # Step 7: Calculate confidence intervals
            confidence_95_lower = baseline_mean - (2 * std_deviation)
            confidence_95_upper = baseline_mean + (2 * std_deviation)
            confidence_99_lower = baseline_mean - (3 * std_deviation)
            confidence_99_upper = baseline_mean + (3 * std_deviation)

            # Step 8: Calculate coefficient of variation (CV) for stability metric
            cv = (std_deviation / baseline_mean * 100) if baseline_mean > 0 else 0

            # Step 9: Add interpretation
            stability = "stable" if cv < 15 else "moderate" if cv < 30 else "highly variable"

            # Step 10: Build result with summary included for tool chaining
            result = {
                "summary": f"Calculated baseline from {len(window_costs)} days of cost data. Mean: ${baseline_mean:.2f}, Std Dev: ${std_deviation:.2f}, CV: {cv:.1f}% ({stability}). 95% confidence interval: ${confidence_95_lower:.2f} - ${confidence_95_upper:.2f}. Seasonal adjustment: {self.enable_seasonal_adjustment}.",
                "baseline_mean": round(baseline_mean, 2),
                "std_deviation": round(std_deviation, 2),
                "coefficient_of_variation": round(cv, 2),
                "confidence_intervals": {
                    "95_percent": {
                        "lower": round(max(0, confidence_95_lower), 2),
                        "upper": round(confidence_95_upper, 2)
                    },
                    "99_percent": {
                        "lower": round(max(0, confidence_99_lower), 2),
                        "upper": round(confidence_99_upper, 2)
                    }
                },
                "seasonal_factors": seasonal_factors,
                "sample_size": len(window_costs),
                "window_days": self.window_days,
                "date_range": f"{window_dates[0].strftime('%Y-%m-%d')} to {window_dates[-1].strftime('%Y-%m-%d')}",
                "seasonal_adjustment_enabled": self.enable_seasonal_adjustment
            }

            # Return pure JSON for downstream tool chaining
            return json.dumps(result, indent=2)

        except statistics.StatisticsError as e:
            return f"Error calculating statistics: {str(e)}. Ensure cost_history contains valid numeric cost values."
        except Exception as e:
            return f"Error calculating baseline: {str(e)}. Verify cost_history format matches expected structure."


if __name__ == "__main__":
    # Test with 30 days of sample cost data including seasonal pattern
    import random

    # Generate sample data with weekly pattern (higher costs on weekends)
    sample_data = []
    base_cost = 1000

    for i in range(35):
        date = (datetime.now() - timedelta(days=35-i)).strftime("%Y-%m-%d")
        day_of_week = (datetime.now() - timedelta(days=35-i)).weekday()

        # Weekend multiplier
        multiplier = 1.3 if day_of_week >= 5 else 1.0

        # Add random variation
        cost = base_cost * multiplier * (1 + random.uniform(-0.1, 0.1))

        sample_data.append({"date": date, "cost": round(cost, 2)})

    tool = CalculateBaseline(
        cost_history=json.dumps(sample_data),
        window_days=30,
        enable_seasonal_adjustment=True
    )
    print(tool.run())
