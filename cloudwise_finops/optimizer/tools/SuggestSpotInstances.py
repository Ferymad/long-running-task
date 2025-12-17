from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class SuggestSpotInstances(BaseTool):
    """Recommend spot/preemptible instance usage for fault-tolerant workloads to achieve 60-90 percent cost savings.

    Use this tool to identify opportunities for migrating on-demand or reserved instances to spot
    instances (AWS), preemptible VMs (GCP), or spot VMs (Azure). The tool evaluates workload
    characteristics, interruption tolerance, and historical spot pricing to recommend which instances
    are good candidates for spot usage, with projected savings and interruption risk analysis.

    Do NOT recommend spot instances for stateful workloads, databases, or user-facing production
    services requiring high availability. Spot instances are ideal for: batch processing, CI/CD,
    data analytics, rendering, machine learning training, and other interruptible workloads.

    Returns: JSON object with recommendation ('recommended', 'conditional', 'not_recommended'),
    spot_price_current, ondemand_price, savings_percent, estimated_monthly_savings, historical
    interruption_rate, and implementation_guidance with specific steps to migrate safely.

    Spot instance best practices: Use multiple availability zones, implement checkpointing for
    long-running jobs, set maximum spot price to control costs, and use spot fleet/instance groups
    for automatic replacement on interruption. Typical interruption rates: 5-10% for popular types.
    """

    instance_type: str = Field(
        ...,
        description="Instance type to evaluate for spot usage (e.g., 'm5.2xlarge', 'n1-standard-4', 'Standard_D4s_v3'). Must be available as spot/preemptible in the target region."
    )
    region: str = Field(
        ...,
        description="Cloud region where workload runs (e.g., 'us-east-1', 'us-central1', 'eastus'). Spot pricing and availability vary significantly by region."
    )
    interruption_tolerance: str = Field(
        ...,
        description="Workload's tolerance for instance interruption. Valid values: 'high' (batch jobs, can restart anytime), 'medium' (checkpointing available, <30min loss acceptable), 'low' (stateful, minimal interruption tolerance). Determines recommendation confidence."
    )
    provider: str = Field(
        default="aws",
        description="Cloud provider. Valid values: 'aws' (spot instances), 'gcp' (preemptible VMs), 'azure' (spot VMs). Each has different interruption policies and pricing."
    )

    def run(self):
        """Analyze spot instance viability and generate recommendation."""
        # Step 1: Validate provider
        valid_providers = ["aws", "gcp", "azure"]
        if self.provider not in valid_providers:
            return f"Error: Invalid provider '{self.provider}'. Must be one of: {', '.join(valid_providers)}"

        # Step 2: Validate interruption tolerance
        valid_tolerances = ["high", "medium", "low"]
        if self.interruption_tolerance not in valid_tolerances:
            return f"Error: Invalid interruption_tolerance '{self.interruption_tolerance}'. Must be one of: {', '.join(valid_tolerances)}"

        try:
            # Step 3: Get pricing data
            pricing = self._get_spot_pricing(self.provider, self.instance_type, self.region)

            if not pricing:
                return f"Error: Spot pricing not available for {self.instance_type} in {self.region}. Verify instance type is eligible for spot/preemptible instances."

            ondemand_hourly = pricing["ondemand_hourly"]
            spot_hourly = pricing["spot_hourly"]
            historical_interruption_rate = pricing["interruption_rate_pct"]

            # Step 4: Calculate savings
            hourly_savings = ondemand_hourly - spot_hourly
            savings_pct = (hourly_savings / ondemand_hourly * 100) if ondemand_hourly > 0 else 0

            # Assuming 730 hours/month full utilization
            monthly_ondemand_cost = ondemand_hourly * 730
            monthly_spot_cost = spot_hourly * 730
            monthly_savings = monthly_ondemand_cost - monthly_spot_cost

            # Step 5: Determine recommendation based on interruption tolerance and savings
            recommendation, confidence, reasoning = self._evaluate_recommendation(
                self.interruption_tolerance,
                savings_pct,
                historical_interruption_rate
            )

            # Step 6: Calculate effective cost including interruption overhead
            # Account for lost compute time due to interruptions
            interruption_overhead_pct = historical_interruption_rate * 0.5  # Assume 50% of interrupted time is waste
            effective_monthly_cost = monthly_spot_cost * (1 + interruption_overhead_pct / 100)
            effective_monthly_savings = monthly_ondemand_cost - effective_monthly_cost
            effective_savings_pct = (effective_monthly_savings / monthly_ondemand_cost * 100) if monthly_ondemand_cost > 0 else 0

            # Step 7: Generate implementation guidance
            implementation_steps = self._generate_implementation_guidance(
                self.provider,
                self.instance_type,
                self.interruption_tolerance,
                recommendation
            )

            # Step 8: Identify risk factors
            risk_factors = []

            if historical_interruption_rate > 15:
                risk_factors.append(f"High interruption rate ({historical_interruption_rate}%) may impact workload completion")

            if self.interruption_tolerance == "low":
                risk_factors.append("Low interruption tolerance limits spot instance suitability")

            if savings_pct < 50:
                risk_factors.append(f"Moderate savings ({savings_pct:.1f}%) may not justify migration effort")

            if not risk_factors:
                risk_factors.append("Low risk - good spot instance candidate")

            # Step 9: Build result
            result = {
                "instance_type": self.instance_type,
                "region": self.region,
                "provider": self.provider,
                "recommendation": recommendation,
                "confidence": confidence,
                "reasoning": reasoning,
                "pricing_analysis": {
                    "ondemand_hourly": round(ondemand_hourly, 4),
                    "spot_hourly": round(spot_hourly, 4),
                    "hourly_savings": round(hourly_savings, 4),
                    "savings_percent": round(savings_pct, 1),
                    "monthly_ondemand_cost": round(monthly_ondemand_cost, 2),
                    "monthly_spot_cost": round(monthly_spot_cost, 2),
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(monthly_savings * 12, 2)
                },
                "interruption_analysis": {
                    "historical_interruption_rate_pct": historical_interruption_rate,
                    "estimated_overhead_pct": round(interruption_overhead_pct, 1),
                    "effective_monthly_cost": round(effective_monthly_cost, 2),
                    "effective_monthly_savings": round(effective_monthly_savings, 2),
                    "effective_savings_pct": round(effective_savings_pct, 1)
                },
                "workload_characteristics": {
                    "interruption_tolerance": self.interruption_tolerance,
                    "recommended_use_cases": self._get_use_cases(self.interruption_tolerance)
                },
                "risk_factors": risk_factors,
                "implementation_guidance": implementation_steps
            }

            # Step 10: Generate summary
            if recommendation == "recommended":
                summary = f"Spot Instance Recommendation: RECOMMENDED for {self.instance_type}. Potential savings: ${monthly_savings:.2f}/month ({savings_pct:.1f}%). Effective savings after {historical_interruption_rate}% interruption rate: ${effective_monthly_savings:.2f}/month ({effective_savings_pct:.1f}%). Confidence: {confidence}. {reasoning}"
            elif recommendation == "conditional":
                summary = f"Spot Instance Recommendation: CONDITIONAL for {self.instance_type}. Savings: ${monthly_savings:.2f}/month ({savings_pct:.1f}%), but {reasoning}. Implement with caution: {' | '.join(implementation_steps[:2])}."
            else:
                summary = f"Spot Instance Recommendation: NOT RECOMMENDED for {self.instance_type}. {reasoning}. Consider on-demand or Reserved Instances instead."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error analyzing spot instance viability: {str(e)}. Verify instance_type, region, and provider are valid."

    def _get_spot_pricing(self, provider, instance_type, region):
        """Get simplified spot and on-demand pricing."""
        # Simplified pricing (in production, query spot price history APIs)
        # Spot prices are typically 60-90% cheaper than on-demand

        base_pricing = {
            "aws": {
                "m5.2xlarge": {
                    "ondemand_hourly": 0.384,
                    "spot_hourly": 0.115,  # ~70% savings
                    "interruption_rate_pct": 8.5
                },
                "m5.xlarge": {
                    "ondemand_hourly": 0.192,
                    "spot_hourly": 0.058,
                    "interruption_rate_pct": 7.2
                }
            },
            "gcp": {
                "n1-standard-4": {
                    "ondemand_hourly": 0.190,
                    "spot_hourly": 0.047,  # ~75% savings (preemptible)
                    "interruption_rate_pct": 12.0  # GCP preemptibles guaranteed <24h
                }
            },
            "azure": {
                "Standard_D4s_v3": {
                    "ondemand_hourly": 0.192,
                    "spot_hourly": 0.058,  # ~70% savings
                    "interruption_rate_pct": 9.0
                }
            }
        }

        return base_pricing.get(provider, {}).get(instance_type)

    def _evaluate_recommendation(self, tolerance, savings_pct, interruption_rate):
        """Determine recommendation based on workload and savings."""
        if tolerance == "high":
            if savings_pct >= 60:
                return "recommended", "HIGH", f"High interruption tolerance + {savings_pct:.1f}% savings"
            elif savings_pct >= 40:
                return "recommended", "MEDIUM", f"Good savings ({savings_pct:.1f}%) for fault-tolerant workload"
            else:
                return "conditional", "LOW", f"Moderate savings ({savings_pct:.1f}%), evaluate migration effort"

        elif tolerance == "medium":
            if savings_pct >= 70 and interruption_rate < 10:
                return "recommended", "MEDIUM", f"Strong savings ({savings_pct:.1f}%) with acceptable interruption rate"
            elif savings_pct >= 50:
                return "conditional", "MEDIUM", f"Good savings but implement checkpointing for resilience"
            else:
                return "conditional", "LOW", f"Modest savings ({savings_pct:.1f}%), requires careful implementation"

        else:  # low tolerance
            if savings_pct >= 80 and interruption_rate < 5:
                return "conditional", "LOW", f"Exceptional savings ({savings_pct:.1f}%) but workload sensitivity is high risk"
            else:
                return "not_recommended", "LOW", "Low interruption tolerance makes spot instances high risk"

    def _generate_implementation_guidance(self, provider, instance_type, tolerance, recommendation):
        """Generate provider-specific implementation steps."""
        steps = []

        if recommendation == "not_recommended":
            return ["Do not migrate to spot instances - use on-demand or Reserved Instances"]

        # Common steps
        steps.append(f"1. Test {instance_type} spot instances in non-production first")
        steps.append("2. Implement graceful shutdown handling (2-minute warning for AWS/Azure, 30-sec for GCP)")

        # Provider-specific guidance
        if provider == "aws":
            steps.append("3. Use EC2 Spot Fleet or Auto Scaling Groups with mixed instance types")
            steps.append("4. Set maximum spot price at 50-70% of on-demand to control costs")
            steps.append("5. Distribute across multiple AZs to reduce interruption impact")

        elif provider == "gcp":
            steps.append("3. Use Managed Instance Groups with preemptible instances")
            steps.append("4. Note: GCP preemptible VMs automatically terminated after 24 hours max")
            steps.append("5. Implement checkpointing every 20-22 hours for long jobs")

        elif provider == "azure":
            steps.append("3. Use Virtual Machine Scale Sets with Spot VMs")
            steps.append("4. Set eviction policy: Deallocate (preserves data) vs Delete")
            steps.append("5. Configure capacity reservation for critical minimum capacity")

        # Tolerance-specific steps
        if tolerance in ["medium", "high"]:
            steps.append("6. Implement job checkpointing to resume from last state")
            steps.append("7. Monitor spot interruption rates and adjust strategy monthly")

        return steps

    def _get_use_cases(self, tolerance):
        """Return appropriate use cases based on interruption tolerance."""
        use_cases = {
            "high": [
                "Batch processing jobs",
                "CI/CD build workers",
                "Data processing pipelines with retry logic",
                "Rendering farms",
                "ML training (with checkpointing)"
            ],
            "medium": [
                "Development/test environments",
                "Analytics workloads with intermediate results saved",
                "ETL jobs with transaction boundaries",
                "Containerized stateless applications"
            ],
            "low": [
                "Not recommended for low tolerance workloads",
                "Consider Reserved Instances or on-demand instead"
            ]
        }

        return use_cases.get(tolerance, [])


if __name__ == "__main__":
    # Test with high-tolerance batch workload
    tool = SuggestSpotInstances(
        instance_type="m5.2xlarge",
        region="us-east-1",
        interruption_tolerance="high",
        provider="aws"
    )
    print(tool.run())
