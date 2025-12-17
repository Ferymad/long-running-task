from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class DetectSpike(BaseTool):
    """Detect cost spikes by comparing current cost against baseline using threshold and Z-score analysis.

    Use this tool after calculating a baseline to identify sudden, significant cost increases that
    deviate from expected patterns. The tool uses dual detection methods: percentage threshold
    (e.g., >20% increase) and Z-score analysis (statistical standard deviations) to balance
    sensitivity and false positive rates.

    Do NOT use this tool for gradual cost increases over multiple days - use DetectTrendChange
    instead for sustained pattern changes. Spike detection is optimized for sudden, single-day
    anomalies like misconfigurations, unexpected traffic surges, or resource sprawl.

    Returns: JSON object with is_spike (boolean), deviation_percent (how much above baseline),
    z_score (standard deviations from mean), severity_level (low/medium/high/critical based on
    magnitude), and confidence (reliability of detection). A spike is confirmed when both
    percentage threshold AND Z-score thresholds are exceeded.

    Severity levels: LOW (20-35% above baseline), MEDIUM (35-50%), HIGH (50-100%), CRITICAL (>100%).
    These thresholds can be adjusted based on your organization's cost volatility tolerance.
    """

    current_value: float = Field(
        ...,
        description="Current cost value to evaluate for spike detection. Must be positive number representing today's or latest period's cost."
    )
    baseline: str = Field(
        ...,
        description="JSON string containing baseline statistics from CalculateBaseline tool. Must include baseline_mean, std_deviation, and confidence_intervals fields."
    )
    threshold_percent: float = Field(
        default=20.0,
        description="Percentage increase threshold to trigger spike detection. Default 20% balances sensitivity vs false positives. Use 15% for stricter detection, 30% for critical-only alerts."
    )
    z_score_threshold: float = Field(
        default=2.0,
        description="Z-score (standard deviations) threshold for statistical significance. Default 2.0 (95% confidence). Use 3.0 for 99% confidence (fewer false positives)."
    )

    def run(self):
        """Analyze current cost against baseline to detect spikes."""
        # Step 1: Validate current_value
        if self.current_value < 0:
            return "Error: current_value cannot be negative. Provide valid cost value."

        # Step 2: Parse and validate baseline
        try:
            baseline_data = json.loads(self.baseline)

            if "baseline_mean" not in baseline_data or "std_deviation" not in baseline_data:
                return "Error: baseline must contain 'baseline_mean' and 'std_deviation' fields. Ensure you're passing output from CalculateBaseline tool."

            baseline_mean = float(baseline_data["baseline_mean"])
            std_deviation = float(baseline_data["std_deviation"])

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in baseline parameter. Details: {str(e)}"
        except (ValueError, KeyError) as e:
            return f"Error: Invalid baseline data structure. Details: {str(e)}"

        # Step 3: Validate thresholds (must be greater than zero to avoid division by zero)
        if self.threshold_percent <= 0:
            return "Error: threshold_percent must be greater than zero. Common values: 15-30%."

        if self.z_score_threshold <= 0:
            return "Error: z_score_threshold must be greater than zero. Common values: 2.0 (95% confidence) or 3.0 (99% confidence)."

        try:
            # Step 4: Calculate percentage deviation
            if baseline_mean == 0:
                # Handle edge case of zero baseline
                if self.current_value > 0:
                    deviation_percent = 100.0
                    is_spike_threshold = True
                else:
                    deviation_percent = 0.0
                    is_spike_threshold = False
            else:
                deviation_percent = ((self.current_value - baseline_mean) / baseline_mean) * 100
                is_spike_threshold = deviation_percent > self.threshold_percent

            # Step 5: Calculate Z-score (statistical significance)
            if std_deviation == 0:
                # Handle edge case of zero deviation (perfectly consistent costs)
                z_score = 0.0 if self.current_value == baseline_mean else float('inf')
            else:
                z_score = (self.current_value - baseline_mean) / std_deviation

            is_spike_zscore = z_score > self.z_score_threshold

            # Step 6: Determine if spike is detected (both conditions must be true)
            is_spike = is_spike_threshold and is_spike_zscore

            # Step 7: Calculate severity level
            if deviation_percent <= 20:
                severity = "NONE"
            elif deviation_percent <= 35:
                severity = "LOW"
            elif deviation_percent <= 50:
                severity = "MEDIUM"
            elif deviation_percent <= 100:
                severity = "HIGH"
            else:
                severity = "CRITICAL"

            # Step 8: Calculate confidence score (0-100)
            # Higher confidence when both Z-score and percentage are significantly exceeded
            z_score_confidence = min(100, (abs(z_score) / self.z_score_threshold) * 50)
            threshold_confidence = min(100, (deviation_percent / self.threshold_percent) * 50)
            confidence = round((z_score_confidence + threshold_confidence) / 2, 1)

            # Step 9: Check if current value falls within confidence intervals
            within_95 = baseline_data.get("confidence_intervals", {}).get("95_percent", {})
            within_99 = baseline_data.get("confidence_intervals", {}).get("99_percent", {})

            within_95_interval = within_95.get("lower", 0) <= self.current_value <= within_95.get("upper", float('inf'))
            within_99_interval = within_99.get("lower", 0) <= self.current_value <= within_99.get("upper", float('inf'))

            # Step 10: Build result
            result = {
                "is_spike": is_spike,
                "current_value": self.current_value,
                "baseline_mean": baseline_mean,
                "deviation_amount": round(self.current_value - baseline_mean, 2),
                "deviation_percent": round(deviation_percent, 2),
                "z_score": round(z_score, 2),
                "severity": severity,
                "confidence": confidence,
                "thresholds": {
                    "percent_threshold": self.threshold_percent,
                    "z_score_threshold": self.z_score_threshold,
                    "percent_exceeded": is_spike_threshold,
                    "z_score_exceeded": is_spike_zscore
                },
                "confidence_intervals": {
                    "within_95_percent": within_95_interval,
                    "within_99_percent": within_99_interval
                }
            }

            # Step 11: Generate human-readable summary
            if is_spike:
                summary = f"SPIKE DETECTED: Current cost ${self.current_value:.2f} is {deviation_percent:.1f}% above baseline (${baseline_mean:.2f}). Severity: {severity}. Z-score: {z_score:.2f} ({abs(z_score):.1f} standard deviations). Confidence: {confidence}%."
            else:
                if deviation_percent > 0:
                    summary = f"No spike detected. Current cost ${self.current_value:.2f} is {deviation_percent:.1f}% above baseline but within acceptable threshold ({self.threshold_percent}%) or statistical significance."
                else:
                    summary = f"No spike detected. Current cost ${self.current_value:.2f} is {abs(deviation_percent):.1f}% below baseline (cost decrease)."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error detecting spike: {str(e)}. Verify baseline and current_value are valid numbers."


if __name__ == "__main__":
    # Test with spike scenario
    sample_baseline = json.dumps({
        "baseline_mean": 1000.0,
        "std_deviation": 50.0,
        "confidence_intervals": {
            "95_percent": {"lower": 900.0, "upper": 1100.0},
            "99_percent": {"lower": 850.0, "upper": 1150.0}
        }
    })

    # Test 1: Clear spike (40% above baseline)
    print("Test 1: Clear Spike (40% increase)")
    tool1 = DetectSpike(
        current_value=1400.0,
        baseline=sample_baseline,
        threshold_percent=20.0,
        z_score_threshold=2.0
    )
    print(tool1.run())
    print("\n" + "="*80 + "\n")

    # Test 2: Borderline case (just below threshold)
    print("Test 2: Borderline Case (18% increase)")
    tool2 = DetectSpike(
        current_value=1180.0,
        baseline=sample_baseline,
        threshold_percent=20.0,
        z_score_threshold=2.0
    )
    print(tool2.run())
