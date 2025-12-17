from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class AnalyzeRightsizing(BaseTool):
    """Analyze compute resource utilization to identify rightsizing opportunities by comparing actual usage against provisioned capacity.

    Use this tool to identify oversized or undersized instances, containers, or virtual machines
    across AWS, GCP, and Azure. The tool evaluates CPU, memory, disk I/O, and network utilization
    over a lookback period (typically 14-30 days) to recommend optimal instance sizes with
    estimated cost savings and performance impact assessment.

    Do NOT use this tool for resources with highly variable workloads (batch jobs, development
    environments) where occasional spikes are expected - rightsizing may cause performance issues.
    Focus on steady-state production workloads with consistent utilization patterns for best results.

    Returns: JSON object with recommendation ('upsize', 'downsize', 'optimal'), target_instance_type,
    potential_monthly_savings (positive for downsizing, negative for upsizing), risk_level
    (LOW/MEDIUM/HIGH based on utilization headroom), current_utilization_metrics, and
    implementation_notes (specific steps to apply recommendation safely).

    Rightsizing logic: <30% avg utilization → downsize (if max <60%), 30-70% → optimal,
    >70% sustained → upsize. The tool accounts for burst requirements and applies safety margins
    to prevent over-optimization that could impact application performance.
    """

    resource_id: str = Field(
        ...,
        description="Unique identifier for the resource to analyze (e.g., AWS instance ID 'i-1234567890abcdef0', GCP instance name, Azure VM resource ID). Used to fetch utilization metrics."
    )
    provider: str = Field(
        ...,
        description="Cloud provider hosting the resource. Valid values: 'aws', 'gcp', 'azure'. Determines which pricing and instance family mapping to use."
    )
    usage_metrics: str = Field(
        ...,
        description="JSON string with historical utilization data. Format: {cpu_avg: 25.5, cpu_max: 45.0, memory_avg: 40.0, memory_max: 65.0, lookback_days: 14}. All percentages 0-100."
    )
    current_instance_type: str = Field(
        default="",
        description="Current instance type/size (e.g., 'm5.2xlarge', 'n1-standard-4', 'Standard_D4s_v3'). If empty, tool will attempt to infer from resource_id."
    )

    def run(self):
        """Analyze resource utilization and generate rightsizing recommendation."""
        # Step 1: Validate provider
        valid_providers = ["aws", "gcp", "azure"]
        if self.provider not in valid_providers:
            return f"Error: Invalid provider '{self.provider}'. Must be one of: {', '.join(valid_providers)}"

        # Step 2: Parse usage metrics
        try:
            metrics = json.loads(self.usage_metrics)

            required_fields = ["cpu_avg", "cpu_max", "memory_avg", "memory_max"]
            for field in required_fields:
                if field not in metrics:
                    return f"Error: Missing required field '{field}' in usage_metrics. Provide: {', '.join(required_fields)}"

            cpu_avg = float(metrics["cpu_avg"])
            cpu_max = float(metrics["cpu_max"])
            memory_avg = float(metrics["memory_avg"])
            memory_max = float(metrics["memory_max"])
            lookback_days = int(metrics.get("lookback_days", 14))

            # Validate ranges
            if not (0 <= cpu_avg <= 100 and 0 <= cpu_max <= 100):
                return f"Error: CPU metrics must be 0-100. Got avg={cpu_avg}, max={cpu_max}"
            if not (0 <= memory_avg <= 100 and 0 <= memory_max <= 100):
                return f"Error: Memory metrics must be 0-100. Got avg={memory_avg}, max={memory_max}"

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in usage_metrics. Details: {str(e)}"
        except (ValueError, KeyError) as e:
            return f"Error: Invalid usage_metrics structure. Details: {str(e)}"

        # Step 3: Validate lookback period
        if lookback_days < 7:
            return f"Warning: lookback_days ({lookback_days}) is less than 7. Recommendations based on short periods may be unreliable. Use 14-30 days for production workloads."

        try:
            # Step 4: Determine current instance specs
            if not self.current_instance_type:
                return "Error: current_instance_type is required for rightsizing analysis. Provide instance type (e.g., 'm5.2xlarge', 'n1-standard-4')."

            current_specs = self._get_instance_specs(self.provider, self.current_instance_type)

            if not current_specs:
                return f"Error: Unknown instance type '{self.current_instance_type}' for provider '{self.provider}'. Verify instance type is valid."

            # Step 5: Calculate utilization efficiency
            # Use weighted average: 60% weight on average, 40% on max (to account for bursts)
            cpu_efficiency = (cpu_avg * 0.6) + (cpu_max * 0.4)
            memory_efficiency = (memory_avg * 0.6) + (memory_max * 0.4)

            # Overall efficiency is the max of CPU or memory (bottleneck resource)
            overall_efficiency = max(cpu_efficiency, memory_efficiency)

            # Step 6: Determine recommendation
            if overall_efficiency < 30 and cpu_max < 60 and memory_max < 60:
                recommendation = "downsize"
                reason = "Low average utilization with no sustained peaks"
            elif overall_efficiency < 30 and (cpu_max >= 60 or memory_max >= 60):
                recommendation = "optimal"
                reason = "Low average but occasional bursts require current capacity"
            elif overall_efficiency <= 70:
                recommendation = "optimal"
                reason = "Utilization within optimal range (30-70%)"
            elif overall_efficiency > 70 and (cpu_max > 85 or memory_max > 85):
                recommendation = "upsize"
                reason = "High sustained utilization with peaks approaching capacity limits"
            else:
                recommendation = "optimal"
                reason = "Current size appears appropriate for workload"

            # Step 7: Determine target instance type (if not optimal)
            if recommendation == "downsize":
                target_type, savings_pct = self._get_smaller_instance(
                    self.provider,
                    self.current_instance_type,
                    current_specs
                )
            elif recommendation == "upsize":
                target_type, cost_increase_pct = self._get_larger_instance(
                    self.provider,
                    self.current_instance_type,
                    current_specs
                )
                savings_pct = -cost_increase_pct  # Negative savings (cost increase)
            else:
                target_type = self.current_instance_type
                savings_pct = 0

            # Step 8: Calculate cost impact
            # Estimate based on typical instance pricing
            estimated_monthly_cost = current_specs["typical_monthly_cost"]
            potential_savings = estimated_monthly_cost * (savings_pct / 100)

            # Step 9: Assess risk level
            if recommendation == "optimal":
                risk_level = "NONE"
            elif recommendation == "downsize":
                if cpu_max > 50 or memory_max > 50:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
            else:  # upsize
                risk_level = "LOW"  # Upsizing is generally low risk

            # Step 10: Generate implementation notes
            implementation_notes = self._generate_implementation_notes(
                recommendation,
                self.provider,
                risk_level,
                target_type
            )

            # Step 11: Build result
            result = {
                "resource_id": self.resource_id,
                "provider": self.provider,
                "current_instance_type": self.current_instance_type,
                "recommendation": recommendation,
                "target_instance_type": target_type,
                "current_utilization": {
                    "cpu_average": cpu_avg,
                    "cpu_max": cpu_max,
                    "memory_average": memory_avg,
                    "memory_max": memory_max,
                    "efficiency_score": round(overall_efficiency, 1)
                },
                "cost_impact": {
                    "estimated_current_monthly_cost": estimated_monthly_cost,
                    "potential_monthly_savings": round(potential_savings, 2),
                    "potential_annual_savings": round(potential_savings * 12, 2),
                    "savings_percentage": savings_pct
                },
                "risk_assessment": {
                    "risk_level": risk_level,
                    "reason": reason,
                    "headroom_cpu": round(100 - cpu_max, 1),
                    "headroom_memory": round(100 - memory_max, 1)
                },
                "implementation_notes": implementation_notes,
                "analysis_period": f"{lookback_days} days"
            }

            # Step 12: Generate summary
            if recommendation == "downsize":
                summary = f"Rightsizing recommendation: DOWNSIZE {self.current_instance_type} → {target_type}. Potential savings: ${abs(potential_savings):.2f}/month (${abs(potential_savings * 12):.2f}/year). Current utilization: {overall_efficiency:.1f}%. Risk: {risk_level}."
            elif recommendation == "upsize":
                summary = f"Rightsizing recommendation: UPSIZE {self.current_instance_type} → {target_type}. Cost increase: ${abs(potential_savings):.2f}/month for better performance. Current utilization: {overall_efficiency:.1f}%. Risk: {risk_level}."
            else:
                summary = f"Rightsizing recommendation: OPTIMAL - No change needed. {self.current_instance_type} is appropriately sized. Current utilization: {overall_efficiency:.1f}%."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error analyzing rightsizing: {str(e)}. Verify resource_id, provider, and usage_metrics are valid."

    def _get_instance_specs(self, provider, instance_type):
        """Get instance specifications including vCPU, memory, and typical cost."""
        # Simplified instance catalog (in production, query cloud provider APIs)
        instance_catalog = {
            "aws": {
                "t3.micro": {"vcpu": 2, "memory_gb": 1, "typical_monthly_cost": 7.60},
                "t3.small": {"vcpu": 2, "memory_gb": 2, "typical_monthly_cost": 15.20},
                "t3.medium": {"vcpu": 2, "memory_gb": 4, "typical_monthly_cost": 30.40},
                "m5.large": {"vcpu": 2, "memory_gb": 8, "typical_monthly_cost": 70.08},
                "m5.xlarge": {"vcpu": 4, "memory_gb": 16, "typical_monthly_cost": 140.16},
                "m5.2xlarge": {"vcpu": 8, "memory_gb": 32, "typical_monthly_cost": 280.32},
                "m5.4xlarge": {"vcpu": 16, "memory_gb": 64, "typical_monthly_cost": 560.64},
            },
            "gcp": {
                "n1-standard-1": {"vcpu": 1, "memory_gb": 3.75, "typical_monthly_cost": 24.27},
                "n1-standard-2": {"vcpu": 2, "memory_gb": 7.5, "typical_monthly_cost": 48.54},
                "n1-standard-4": {"vcpu": 4, "memory_gb": 15, "typical_monthly_cost": 97.09},
                "n1-standard-8": {"vcpu": 8, "memory_gb": 30, "typical_monthly_cost": 194.18},
            },
            "azure": {
                "Standard_B1s": {"vcpu": 1, "memory_gb": 1, "typical_monthly_cost": 7.59},
                "Standard_B2s": {"vcpu": 2, "memory_gb": 4, "typical_monthly_cost": 30.37},
                "Standard_D2s_v3": {"vcpu": 2, "memory_gb": 8, "typical_monthly_cost": 70.08},
                "Standard_D4s_v3": {"vcpu": 4, "memory_gb": 16, "typical_monthly_cost": 140.16},
                "Standard_D8s_v3": {"vcpu": 8, "memory_gb": 32, "typical_monthly_cost": 280.32},
            }
        }

        return instance_catalog.get(provider, {}).get(instance_type)

    def _get_smaller_instance(self, provider, current_type, current_specs):
        """Determine next smaller instance size."""
        # Simplified logic: reduce by ~50% capacity
        target_vcpu = max(1, current_specs["vcpu"] // 2)

        size_map = {
            "aws": {
                "m5.4xlarge": ("m5.2xlarge", 50),
                "m5.2xlarge": ("m5.xlarge", 50),
                "m5.xlarge": ("m5.large", 50),
            },
            "gcp": {
                "n1-standard-8": ("n1-standard-4", 50),
                "n1-standard-4": ("n1-standard-2", 50),
            },
            "azure": {
                "Standard_D8s_v3": ("Standard_D4s_v3", 50),
                "Standard_D4s_v3": ("Standard_D2s_v3", 50),
            }
        }

        return size_map.get(provider, {}).get(current_type, (current_type, 0))

    def _get_larger_instance(self, provider, current_type, current_specs):
        """Determine next larger instance size."""
        size_map = {
            "aws": {
                "m5.large": ("m5.xlarge", 100),
                "m5.xlarge": ("m5.2xlarge", 100),
                "m5.2xlarge": ("m5.4xlarge", 100),
            },
            "gcp": {
                "n1-standard-2": ("n1-standard-4", 100),
                "n1-standard-4": ("n1-standard-8", 100),
            },
            "azure": {
                "Standard_D2s_v3": ("Standard_D4s_v3", 100),
                "Standard_D4s_v3": ("Standard_D8s_v3", 100),
            }
        }

        return size_map.get(provider, {}).get(current_type, (current_type, 0))

    def _generate_implementation_notes(self, recommendation, provider, risk_level, target_type):
        """Generate specific implementation guidance."""
        notes = []

        if recommendation == "downsize":
            notes.append(f"1. Test {target_type} in non-production environment first")
            notes.append("2. Monitor performance for 48 hours before production rollout")
            notes.append("3. Set up CloudWatch/Stackdriver alarms for >80% utilization")

            if risk_level == "MEDIUM":
                notes.append("4. CAUTION: Peak utilization suggests occasional bursts - ensure target size can handle")
                notes.append("5. Consider burst-capable instance families (T3/T3a for AWS)")

        elif recommendation == "upsize":
            notes.append(f"1. Schedule upsizing during maintenance window to minimize disruption")
            notes.append("2. Resize immediately if current utilization consistently >85%")
            notes.append("3. Verify application can utilize additional resources")

        else:  # optimal
            notes.append("1. Continue monitoring utilization trends")
            notes.append("2. Re-evaluate in 30 days or if workload patterns change")

        return notes


if __name__ == "__main__":
    # Test with oversized instance scenario
    sample_metrics = json.dumps({
        "cpu_avg": 18.5,
        "cpu_max": 42.0,
        "memory_avg": 25.3,
        "memory_max": 55.0,
        "lookback_days": 14
    })

    tool = AnalyzeRightsizing(
        resource_id="i-1234567890abcdef0",
        provider="aws",
        usage_metrics=sample_metrics,
        current_instance_type="m5.2xlarge"
    )
    print(tool.run())
