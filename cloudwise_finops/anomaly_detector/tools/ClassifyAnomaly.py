from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class ClassifyAnomaly(BaseTool):
    """Categorize detected cost anomalies into specific types using rule-based classification logic.

    Use this tool after DetectSpike or DetectTrendChange identifies an anomaly to determine its
    root cause category. Classification helps prioritize remediation actions: cost spikes may
    indicate misconfigurations, usage spikes suggest demand changes, new resources need review,
    and zombie resources should be terminated or downsized.

    Do NOT use this tool if no anomaly was detected - classification requires confirmed deviation
    from baseline. This tool analyzes cost breakdown by service, resource type, and usage patterns
    to determine the most likely anomaly type with confidence scoring.

    Returns: JSON object with classification ('cost_spike', 'usage_spike', 'new_resource',
    'zombie_resource', 'seasonal_pattern', or 'configuration_change'), confidence_score (0-100),
    contributing_factors (which services/resources drove the anomaly), and recommended_actions
    (specific investigation or remediation steps).

    Classification logic: Cost spike (cost up, usage stable), Usage spike (both up proportionally),
    New resource (sudden appearance of new service), Zombie (cost persists despite low/zero usage),
    Seasonal (matches historical day-of-week pattern), Configuration (service mix change).
    """

    anomaly_data: str = Field(
        ...,
        description="JSON string containing anomaly detection results from DetectSpike or DetectTrendChange. Must include is_spike/is_significant, deviation_percent, and severity fields."
    )
    cost_breakdown: str = Field(
        ...,
        description="JSON string with detailed cost breakdown by service or resource. Format: [{service: 'EC2', cost: 1000, usage: 720, previous_cost: 800}, ...]. Used to identify which services contributed to the anomaly."
    )

    def run(self):
        """Classify detected anomaly based on cost patterns and breakdown."""
        # Step 1: Parse and validate anomaly data
        try:
            anomaly = json.loads(self.anomaly_data)

            # Check if anomaly was actually detected
            is_anomaly = anomaly.get("is_spike", False) or anomaly.get("is_significant", False)

            if not is_anomaly:
                return "Warning: No anomaly detected in provided data. Classification requires confirmed spike or trend change. Ensure you pass output from DetectSpike or DetectTrendChange that identified an anomaly."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in anomaly_data. Details: {str(e)}"

        # Step 2: Parse and validate cost breakdown
        try:
            breakdown = json.loads(self.cost_breakdown)

            if not isinstance(breakdown, list) or not breakdown:
                return "Error: cost_breakdown must be non-empty JSON array of service cost records. Format: [{service: 'name', cost: 100, usage: 50, previous_cost: 80}, ...]"

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in cost_breakdown. Details: {str(e)}"

        try:
            # Step 3: Extract anomaly metrics
            deviation_percent = anomaly.get("deviation_percent", 0)
            severity = anomaly.get("severity", "UNKNOWN")
            current_value = anomaly.get("current_value", 0)
            trend_direction = anomaly.get("trend_direction", "unknown")

            # Step 4: Analyze cost breakdown for classification signals
            classification_signals = {
                "new_services": [],
                "usage_spikes": [],
                "cost_only_spikes": [],
                "zombie_candidates": [],
                "major_contributors": []
            }

            for service in breakdown:
                service_name = service.get("service", "unknown")
                current_cost = service.get("cost", 0)
                current_usage = service.get("usage", 0)
                previous_cost = service.get("previous_cost", 0)
                previous_usage = service.get("previous_usage", 0)

                # Calculate service-level changes
                if previous_cost == 0 and current_cost > 0:
                    # New service appeared
                    classification_signals["new_services"].append({
                        "service": service_name,
                        "cost": current_cost
                    })

                elif previous_cost > 0:
                    cost_change_pct = ((current_cost - previous_cost) / previous_cost) * 100

                    # Check if usage changed proportionally to cost
                    if previous_usage > 0:
                        usage_change_pct = ((current_usage - previous_usage) / previous_usage) * 100

                        if abs(cost_change_pct - usage_change_pct) < 10:
                            # Cost and usage changed together -> usage spike
                            classification_signals["usage_spikes"].append({
                                "service": service_name,
                                "cost_change": cost_change_pct,
                                "usage_change": usage_change_pct
                            })
                        elif cost_change_pct > 20 and abs(usage_change_pct) < 5:
                            # Cost increased but usage stable -> pricing or config change
                            classification_signals["cost_only_spikes"].append({
                                "service": service_name,
                                "cost_change": cost_change_pct
                            })

                # Identify major contributors (>30% of total cost)
                if current_cost > (current_value * 0.3):
                    classification_signals["major_contributors"].append({
                        "service": service_name,
                        "cost": current_cost,
                        "percent_of_total": round((current_cost / current_value * 100), 1)
                    })

                # Check for zombie resources (high cost, low usage)
                if current_usage < (current_cost * 0.05) and current_cost > 50:
                    classification_signals["zombie_candidates"].append({
                        "service": service_name,
                        "cost": current_cost,
                        "usage": current_usage,
                        "utilization_pct": round((current_usage / current_cost * 100), 1) if current_cost > 0 else 0
                    })

            # Step 5: Apply classification rules with confidence scoring
            classification = "unknown"
            confidence = 0
            reasoning = []

            # Rule 1: New resource (high confidence if new services appeared)
            if classification_signals["new_services"]:
                classification = "new_resource"
                confidence = 85
                reasoning.append(f"New services detected: {', '.join([s['service'] for s in classification_signals['new_services']])}")

            # Rule 2: Usage spike (cost and usage both increased)
            elif classification_signals["usage_spikes"]:
                classification = "usage_spike"
                confidence = 80
                avg_usage_change = sum([s["usage_change"] for s in classification_signals["usage_spikes"]]) / len(classification_signals["usage_spikes"])
                reasoning.append(f"Usage increased by {avg_usage_change:.1f}% proportionally with cost")

            # Rule 3: Cost-only spike (cost up, usage stable)
            elif classification_signals["cost_only_spikes"]:
                classification = "cost_spike"
                confidence = 75
                reasoning.append("Cost increased without proportional usage increase - likely pricing or configuration change")

            # Rule 4: Zombie resources (cost persists with low usage)
            elif classification_signals["zombie_candidates"]:
                classification = "zombie_resource"
                confidence = 70
                reasoning.append(f"Detected {len(classification_signals['zombie_candidates'])} resources with <5% utilization")

            # Rule 5: Trend-based classification
            elif trend_direction in ["increasing", "decreasing"]:
                classification = "sustained_trend"
                confidence = 65
                reasoning.append(f"Gradual {trend_direction} trend over multiple days")

            # Rule 6: Generic spike (fallback)
            else:
                classification = "cost_spike"
                confidence = 50
                reasoning.append("Cost anomaly detected but specific cause unclear")

            # Step 6: Generate recommended actions
            recommended_actions = self._generate_recommendations(
                classification,
                classification_signals,
                severity
            )

            # Step 7: Build result
            result = {
                "classification": classification,
                "confidence": confidence,
                "reasoning": reasoning,
                "severity": severity,
                "deviation_percent": deviation_percent,
                "contributing_factors": {
                    "new_services": classification_signals["new_services"],
                    "usage_spikes": classification_signals["usage_spikes"],
                    "cost_only_spikes": classification_signals["cost_only_spikes"],
                    "zombie_candidates": classification_signals["zombie_candidates"],
                    "major_contributors": classification_signals["major_contributors"]
                },
                "recommended_actions": recommended_actions
            }

            # Step 8: Generate summary
            summary = f"Classification: {classification.upper()} (confidence: {confidence}%). Severity: {severity}. {' | '.join(reasoning)}. Recommended actions: {recommended_actions[0] if recommended_actions else 'Review cost breakdown'}."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error classifying anomaly: {str(e)}. Verify anomaly_data and cost_breakdown structures."

    def _generate_recommendations(self, classification, signals, severity):
        """Generate specific remediation recommendations based on classification."""
        actions = []

        if classification == "new_resource":
            actions.append("Review new service deployments - verify they were authorized")
            actions.append("Check if new resources have proper tagging (owner, environment, cost-center)")
            actions.append("Validate that new resources follow sizing best practices")

        elif classification == "usage_spike":
            actions.append("Investigate traffic or workload increase - is it expected?")
            actions.append("Check if autoscaling is configured appropriately")
            actions.append("Review if additional capacity is needed or if this is temporary")

        elif classification == "cost_spike":
            actions.append("Review recent configuration changes or pricing model updates")
            actions.append("Check if Reserved Instance or Savings Plan coverage decreased")
            actions.append("Verify no inadvertent instance type or storage class changes")

        elif classification == "zombie_resource":
            actions.append("Identify idle resources for potential termination or downsizing")
            actions.append("Check last activity timestamps for resources with <5% utilization")
            actions.append("Create termination plan with appropriate approval workflow")

        elif classification == "sustained_trend":
            actions.append("Analyze long-term capacity planning - is infrastructure scaling appropriately?")
            actions.append("Review optimization opportunities (rightsizing, Reserved Instances)")
            actions.append("Consider setting up budget alerts if trend continues")

        else:
            actions.append("Conduct detailed cost breakdown analysis by service and resource")
            actions.append("Compare with previous periods to identify specific changes")
            actions.append("Review recent infrastructure or application changes")

        # Add severity-based actions
        if severity in ["HIGH", "CRITICAL"]:
            actions.insert(0, "URGENT: Escalate to engineering team for immediate investigation")
            actions.insert(1, "Review spending limits and consider temporary restrictions if unauthorized")

        return actions


if __name__ == "__main__":
    # Test with cost spike scenario
    sample_anomaly = json.dumps({
        "is_spike": True,
        "current_value": 1400.0,
        "deviation_percent": 40.0,
        "severity": "HIGH",
        "confidence": 85.0
    })

    sample_breakdown = json.dumps([
        {
            "service": "Amazon EC2",
            "cost": 800.0,
            "usage": 750.0,
            "previous_cost": 500.0,
            "previous_usage": 720.0
        },
        {
            "service": "Amazon S3",
            "cost": 400.0,
            "usage": 500.0,
            "previous_cost": 350.0,
            "previous_usage": 480.0
        },
        {
            "service": "Amazon Lambda",
            "cost": 200.0,
            "usage": 100.0,
            "previous_cost": 0.0,
            "previous_usage": 0.0
        }
    ])

    tool = ClassifyAnomaly(
        anomaly_data=sample_anomaly,
        cost_breakdown=sample_breakdown
    )
    print(tool.run())
