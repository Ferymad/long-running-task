from agency_swarm.tools import BaseTool
from pydantic import Field
import json
import statistics
from datetime import datetime

class DetectTrendChange(BaseTool):
    """Detect sustained cost trend changes using linear regression analysis over a lookback period.

    Use this tool to identify gradual cost increases or decreases that span multiple days, as
    opposed to single-day spikes. Trend detection uses simple linear regression to calculate
    slope (rate of change) and R-squared (trend strength) to determine if costs are systematically
    rising, falling, or remaining stable over time.

    Do NOT use this tool for sudden single-day anomalies - use DetectSpike instead. Trend analysis
    requires at least 7 days of data and is most effective with 14+ days to distinguish real trends
    from random fluctuations. Short lookback periods (3-5 days) produce unreliable trend signals.

    Returns: JSON object with trend_direction ('increasing', 'decreasing', 'stable'), slope
    (daily cost change rate), r_squared (trend strength 0-1), confidence_score (reliability),
    projected_30day_impact (extrapolated cost change), and is_significant (boolean indicating
    actionable trend requiring attention).

    A significant trend is defined as: slope exceeding threshold, R-squared > 0.5 (strong linear
    fit), and projected impact > $100/month. These criteria filter noise and focus on meaningful
    cost pattern changes that warrant investigation or optimization.
    """

    cost_history: str = Field(
        ...,
        description="JSON array of recent cost data points with date and cost fields. Format: [{date: 'YYYY-MM-DD', cost: 123.45}, ...]. Minimum 7 data points required, 14+ recommended for reliable trend detection."
    )
    lookback_days: int = Field(
        default=14,
        description="Number of recent days to analyze for trend. Default 14 days balances responsiveness vs noise. Use 7 for faster detection, 21-30 for more stable trends."
    )
    min_slope_threshold: float = Field(
        default=5.0,
        description="Minimum daily cost change (dollars) to consider trend significant. Default $5/day ($150/month). Adjust based on your cost scale: use 1.0 for small accounts, 20.0 for large enterprises."
    )

    def run(self):
        """Analyze cost history for sustained trend changes using regression."""
        # Step 1: Parse and validate cost history
        try:
            history = json.loads(self.cost_history)

            if not isinstance(history, list):
                return "Error: cost_history must be JSON array of objects with 'date' and 'cost' fields. Example: [{\"date\": \"2025-12-01\", \"cost\": 100.5}, ...]"

            if len(history) < 7:
                return f"Error: Insufficient data for trend analysis. Provided {len(history)} data points, minimum 7 required (14+ recommended for reliable trends)."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in cost_history. Details: {str(e)}"

        # Step 2: Validate parameters
        if self.lookback_days < 7:
            return "Error: lookback_days must be at least 7 for meaningful trend analysis. Use 14-30 for optimal results."

        if self.min_slope_threshold < 0:
            return "Error: min_slope_threshold must be positive. Typical values: 1-20 dollars per day."

        try:
            # Step 3: Extract and sort cost data
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

            if len(data_points) < 7:
                return f"Error: Only {len(data_points)} valid cost entries found after validation. Need at least 7."

            # Sort by date
            data_points.sort(key=lambda x: x["date"])

            # Step 4: Use most recent lookback_days
            lookback_data = data_points[-self.lookback_days:]

            if len(lookback_data) < 7:
                lookback_data = data_points  # Use all available if less than lookback_days

            # Step 5: Perform linear regression (y = mx + b)
            n = len(lookback_data)

            # Convert dates to numeric x values (days since first date)
            x_values = list(range(n))
            y_values = [point["cost"] for point in lookback_data]

            # Calculate means
            mean_x = statistics.mean(x_values)
            mean_y = statistics.mean(y_values)

            # Calculate slope (m) and intercept (b)
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
            denominator = sum((x - mean_x) ** 2 for x in x_values)

            if denominator == 0:
                return "Error: Cannot calculate trend - all dates are identical. Ensure cost_history spans multiple days."

            slope = numerator / denominator
            intercept = mean_y - (slope * mean_x)

            # Step 6: Calculate R-squared (goodness of fit)
            predicted_values = [slope * x + intercept for x in x_values]
            ss_total = sum((y - mean_y) ** 2 for y in y_values)
            ss_residual = sum((y - pred) ** 2 for y, pred in zip(y_values, predicted_values))

            if ss_total == 0:
                r_squared = 0.0  # All y values identical
            else:
                r_squared = 1 - (ss_residual / ss_total)

            # Step 7: Determine trend direction
            if abs(slope) < self.min_slope_threshold:
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"

            # Step 8: Calculate projected impacts
            projected_7day = slope * 7
            projected_30day = slope * 30
            projected_90day = slope * 90

            # Step 9: Determine significance
            # Significant if: strong trend (R² > 0.5), meaningful slope, and material impact
            is_significant = (
                r_squared > 0.5 and
                abs(slope) >= self.min_slope_threshold and
                abs(projected_30day) > 100  # $100/month threshold
            )

            # Step 10: Calculate confidence score (0-100)
            # Based on R-squared strength and sample size adequacy
            r_squared_confidence = r_squared * 70  # Max 70 points for perfect fit
            sample_size_confidence = min(30, (n / 14) * 30)  # Max 30 points for 14+ days
            confidence = round(r_squared_confidence + sample_size_confidence, 1)

            # Step 11: Build result
            result = {
                "trend_direction": trend_direction,
                "slope": round(slope, 2),
                "slope_interpretation": f"${abs(slope):.2f}/day {'increase' if slope > 0 else 'decrease'}",
                "intercept": round(intercept, 2),
                "r_squared": round(r_squared, 3),
                "r_squared_interpretation": self._interpret_r_squared(r_squared),
                "is_significant": is_significant,
                "confidence": confidence,
                "projections": {
                    "7_day": round(projected_7day, 2),
                    "30_day": round(projected_30day, 2),
                    "90_day": round(projected_90day, 2)
                },
                "analysis_period": {
                    "days_analyzed": n,
                    "start_date": lookback_data[0]["date"].strftime("%Y-%m-%d"),
                    "end_date": lookback_data[-1]["date"].strftime("%Y-%m-%d"),
                    "start_cost": lookback_data[0]["cost"],
                    "end_cost": lookback_data[-1]["cost"],
                    "total_change": round(lookback_data[-1]["cost"] - lookback_data[0]["cost"], 2)
                },
                "thresholds": {
                    "min_slope": self.min_slope_threshold,
                    "lookback_days": self.lookback_days
                }
            }

            # Step 12: Generate summary
            if is_significant:
                direction_text = "increasing" if slope > 0 else "decreasing"
                summary = f"SIGNIFICANT TREND DETECTED: Costs are {direction_text} at ${abs(slope):.2f}/day. Projected 30-day impact: ${abs(projected_30day):.2f}. Trend strength: {self._interpret_r_squared(r_squared)} (R²={r_squared:.3f}). Confidence: {confidence}%."
            else:
                if trend_direction == "stable":
                    summary = f"No significant trend detected. Costs are stable with minimal daily change (${abs(slope):.2f}/day). R²={r_squared:.3f}."
                else:
                    summary = f"Trend detected but not significant. Costs are {trend_direction} at ${abs(slope):.2f}/day but below threshold (${self.min_slope_threshold}/day) or weak correlation (R²={r_squared:.3f})."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except statistics.StatisticsError as e:
            return f"Error calculating trend statistics: {str(e)}. Ensure cost_history contains valid numeric cost values."
        except Exception as e:
            return f"Error detecting trend change: {str(e)}. Verify cost_history format and data validity."

    def _interpret_r_squared(self, r_squared):
        """Interpret R-squared value in human-readable terms."""
        if r_squared >= 0.9:
            return "very strong trend"
        elif r_squared >= 0.7:
            return "strong trend"
        elif r_squared >= 0.5:
            return "moderate trend"
        elif r_squared >= 0.3:
            return "weak trend"
        else:
            return "no clear trend"


if __name__ == "__main__":
    # Test with increasing trend data
    import random
    from datetime import timedelta

    sample_data = []
    base_cost = 1000

    for i in range(21):
        date = (datetime.now() - timedelta(days=21-i)).strftime("%Y-%m-%d")
        # Increasing trend: $10/day increase + random noise
        cost = base_cost + (i * 10) + random.uniform(-20, 20)
        sample_data.append({"date": date, "cost": round(cost, 2)})

    tool = DetectTrendChange(
        cost_history=json.dumps(sample_data),
        lookback_days=14,
        min_slope_threshold=5.0
    )
    print(tool.run())
