from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class CalculateCrossProviderArbitrage(BaseTool):
    """Compare pricing across AWS, GCP, and Azure to identify cost arbitrage opportunities for portable workloads.

    Use this tool to evaluate if migrating workloads between cloud providers could yield significant
    cost savings. The tool analyzes compute, storage, and network pricing across the big three cloud
    providers for equivalent workload specifications (CPU, memory, storage, bandwidth) and identifies
    the most cost-effective provider with migration feasibility assessment.

    Do NOT recommend cross-provider migration for workloads with deep cloud-specific integrations
    (AWS-native services like DynamoDB, GCP-specific ML APIs, Azure AD-coupled applications) as
    migration costs and complexity may outweigh savings. Focus on containerized, cloud-agnostic
    applications running on VMs, Kubernetes, or serverless with portable architectures.

    Returns: JSON object with provider_comparison (costs for AWS/GCP/Azure), recommended_provider,
    potential_monthly_savings, potential_annual_savings, migration_complexity (LOW/MEDIUM/HIGH),
    migration_cost_estimate, break_even_months (when savings offset migration costs), and
    implementation_roadmap with specific migration steps.

    Arbitrage factors analyzed: compute pricing differences (AWS typically 10-30% more than GCP for
    general compute), egress bandwidth costs (GCP first 1TB free, AWS charges from first GB), storage
    pricing variations, and region-specific pricing where significant gaps exist (e.g., GCP asia-south1
    vs AWS ap-south-1). Tool accounts for migration effort: LOW (containerized apps), MEDIUM (VMs with
    dependencies), HIGH (complex architectures with cloud-native services).
    """

    workload_type: str = Field(
        ...,
        description="Type of workload to analyze. Valid values: 'compute_vm' (virtual machines), 'kubernetes' (containerized), 'serverless' (functions), 'database' (managed DB), 'storage' (object storage). Determines portability and migration complexity."
    )
    specs: str = Field(
        ...,
        description="JSON string with workload specifications. For compute: {vcpu: 8, memory_gb: 32, storage_gb: 500, bandwidth_gb_month: 1000}. For storage: {size_tb: 10, iops: 3000, bandwidth_gb_month: 2000}."
    )
    current_provider: str = Field(
        default="aws",
        description="Current cloud provider hosting the workload. Valid values: 'aws', 'gcp', 'azure'. Used as baseline for savings calculation."
    )
    region_preference: str = Field(
        default="us_east",
        description="Geographic region preference. Valid values: 'us_east', 'us_west', 'europe', 'asia'. Pricing varies significantly by region."
    )

    def run(self):
        """Calculate cross-cloud cost arbitrage opportunities."""
        # Step 1: Validate workload type
        valid_types = ["compute_vm", "kubernetes", "serverless", "database", "storage"]
        if self.workload_type not in valid_types:
            return f"Error: Invalid workload_type '{self.workload_type}'. Must be one of: {', '.join(valid_types)}"

        # Step 2: Validate current provider
        valid_providers = ["aws", "gcp", "azure"]
        if self.current_provider not in valid_providers:
            return f"Error: Invalid current_provider '{self.current_provider}'. Must be one of: {', '.join(valid_providers)}"

        # Step 3: Parse and validate specs
        try:
            specs = json.loads(self.specs)

            if self.workload_type in ["compute_vm", "kubernetes"]:
                required_fields = ["vcpu", "memory_gb"]
                for field in required_fields:
                    if field not in specs:
                        return f"Error: Missing required field '{field}' for workload_type '{self.workload_type}'"

            elif self.workload_type == "storage":
                if "size_tb" not in specs:
                    return "Error: Missing required field 'size_tb' for storage workload"

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in specs. Details: {str(e)}"

        try:
            # Step 4: Get pricing from all providers
            provider_costs = {}

            for provider in valid_providers:
                monthly_cost = self._calculate_provider_cost(
                    provider,
                    self.workload_type,
                    specs,
                    self.region_preference
                )
                provider_costs[provider] = monthly_cost

            # Step 5: Identify cheapest provider and calculate savings
            current_cost = provider_costs[self.current_provider]
            cheapest_provider = min(provider_costs, key=provider_costs.get)
            cheapest_cost = provider_costs[cheapest_provider]

            monthly_savings = current_cost - cheapest_cost
            annual_savings = monthly_savings * 12
            savings_pct = (monthly_savings / current_cost * 100) if current_cost > 0 else 0

            # Step 6: Assess migration complexity
            migration_complexity = self._assess_migration_complexity(
                self.workload_type,
                self.current_provider,
                cheapest_provider
            )

            # Step 7: Estimate migration cost
            migration_cost_estimate = self._estimate_migration_cost(
                self.workload_type,
                migration_complexity,
                specs
            )

            # Step 8: Calculate break-even period
            if monthly_savings > 0:
                break_even_months = migration_cost_estimate / monthly_savings
            else:
                break_even_months = 999  # No break-even if not saving

            # Step 9: Determine recommendation
            if cheapest_provider == self.current_provider:
                recommendation = "STAY"
                recommendation_reason = f"Current provider ({self.current_provider.upper()}) is already most cost-effective"
            elif break_even_months <= 6 and migration_complexity != "HIGH":
                recommendation = "MIGRATE"
                recommendation_reason = f"Strong arbitrage opportunity: {savings_pct:.1f}% savings, {break_even_months:.1f} month break-even"
            elif break_even_months <= 12 and migration_complexity == "LOW":
                recommendation = "CONSIDER"
                recommendation_reason = f"Moderate opportunity: {savings_pct:.1f}% savings but {break_even_months:.1f} month break-even"
            else:
                recommendation = "STAY"
                recommendation_reason = f"Migration not justified: {break_even_months:.1f} month break-even or HIGH complexity"

            # Step 10: Build provider comparison
            provider_comparison = []

            for provider in ["aws", "gcp", "azure"]:
                cost = provider_costs[provider]
                savings_vs_current = current_cost - cost

                comparison_entry = {
                    "provider": provider,
                    "monthly_cost": round(cost, 2),
                    "annual_cost": round(cost * 12, 2),
                    "vs_current": {
                        "monthly_diff": round(savings_vs_current, 2),
                        "annual_diff": round(savings_vs_current * 12, 2),
                        "percent_diff": round((savings_vs_current / current_cost * 100) if current_cost > 0 else 0, 1)
                    },
                    "is_current": provider == self.current_provider,
                    "is_cheapest": provider == cheapest_provider
                }
                provider_comparison.append(comparison_entry)

            # Sort by cost
            provider_comparison.sort(key=lambda x: x["monthly_cost"])

            # Step 11: Generate migration roadmap
            migration_roadmap = self._generate_migration_roadmap(
                self.workload_type,
                self.current_provider,
                cheapest_provider,
                migration_complexity
            ) if recommendation in ["MIGRATE", "CONSIDER"] else []

            # Step 12: Build result
            result = {
                "workload_analysis": {
                    "workload_type": self.workload_type,
                    "specifications": specs,
                    "region_preference": self.region_preference
                },
                "current_state": {
                    "provider": self.current_provider,
                    "monthly_cost": round(current_cost, 2),
                    "annual_cost": round(current_cost * 12, 2)
                },
                "recommendation": {
                    "action": recommendation,
                    "target_provider": cheapest_provider if recommendation in ["MIGRATE", "CONSIDER"] else self.current_provider,
                    "reason": recommendation_reason
                },
                "savings_potential": {
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(annual_savings, 2),
                    "savings_percent": round(savings_pct, 1)
                },
                "migration_assessment": {
                    "complexity": migration_complexity,
                    "estimated_cost": migration_cost_estimate,
                    "estimated_effort_weeks": self._estimate_effort_weeks(migration_complexity),
                    "break_even_months": round(break_even_months, 1)
                },
                "provider_comparison": provider_comparison,
                "migration_roadmap": migration_roadmap
            }

            # Step 13: Generate summary
            if recommendation == "MIGRATE":
                summary = f"Cross-Cloud Arbitrage: MIGRATE RECOMMENDED from {self.current_provider.upper()} to {cheapest_provider.upper()}. Savings: ${monthly_savings:.2f}/month (${annual_savings:.2f}/year, {savings_pct:.1f}%). Migration complexity: {migration_complexity}, cost: ${migration_cost_estimate}, break-even: {break_even_months:.1f} months."
            elif recommendation == "CONSIDER":
                summary = f"Cross-Cloud Arbitrage: CONSIDER migration from {self.current_provider.upper()} to {cheapest_provider.upper()}. Savings: ${monthly_savings:.2f}/month ({savings_pct:.1f}%). Break-even: {break_even_months:.1f} months. Evaluate migration effort ({migration_complexity} complexity) against savings."
            else:
                summary = f"Cross-Cloud Arbitrage: STAY on {self.current_provider.upper()}. {recommendation_reason}. Alternative providers: GCP ${provider_costs['gcp']:.2f}/mo, Azure ${provider_costs['azure']:.2f}/mo."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error calculating cross-provider arbitrage: {str(e)}. Verify workload_type, specs, and provider are valid."

    def _calculate_provider_cost(self, provider, workload_type, specs, region):
        """Calculate monthly cost for workload on specific provider."""
        # Simplified pricing logic (in production, use provider pricing APIs)

        if workload_type in ["compute_vm", "kubernetes"]:
            vcpu = specs.get("vcpu", 0)
            memory_gb = specs.get("memory_gb", 0)
            storage_gb = specs.get("storage_gb", 0)
            bandwidth_gb = specs.get("bandwidth_gb_month", 0)

            # Base compute cost per vCPU-hour (varies by provider and region)
            compute_rates = {
                "aws": {"us_east": 0.048, "us_west": 0.048, "europe": 0.053, "asia": 0.054},
                "gcp": {"us_east": 0.042, "us_west": 0.042, "europe": 0.046, "asia": 0.048},  # ~12% cheaper
                "azure": {"us_east": 0.046, "us_west": 0.046, "europe": 0.050, "asia": 0.052}
            }

            compute_hourly = vcpu * compute_rates[provider][region]
            compute_monthly = compute_hourly * 730

            # Memory cost
            memory_hourly = memory_gb * 0.005  # Simplified
            memory_monthly = memory_hourly * 730

            # Storage cost (per GB-month)
            storage_rates = {"aws": 0.10, "gcp": 0.04, "azure": 0.08}  # GCP cheaper for persistent disk
            storage_monthly = storage_gb * storage_rates[provider]

            # Bandwidth cost (egress)
            bandwidth_rates = {
                "aws": 0.09,  # Charges from first GB
                "gcp": 0.12 if bandwidth_gb > 1000 else 0,  # First 1TB free
                "azure": 0.087
            }
            bandwidth_monthly = max(0, bandwidth_gb - (1000 if provider == "gcp" else 0)) * bandwidth_rates[provider]

            return compute_monthly + memory_monthly + storage_monthly + bandwidth_monthly

        elif workload_type == "storage":
            size_tb = specs.get("size_tb", 0)
            bandwidth_gb = specs.get("bandwidth_gb_month", 0)

            # Object storage pricing per TB-month
            storage_rates = {"aws": 23.55, "gcp": 20.48, "azure": 21.12}  # GCP cheapest
            storage_monthly = size_tb * storage_rates[provider]

            # Egress costs
            bandwidth_rates = {"aws": 0.09, "gcp": 0.12, "azure": 0.087}
            bandwidth_monthly = bandwidth_gb * bandwidth_rates[provider]

            return storage_monthly + bandwidth_monthly

        return 0

    def _assess_migration_complexity(self, workload_type, from_provider, to_provider):
        """Assess migration complexity based on workload type."""
        if workload_type == "kubernetes":
            return "LOW"  # Containers are portable
        elif workload_type == "compute_vm":
            return "MEDIUM"  # VMs need conversion/reconfiguration
        elif workload_type == "storage":
            return "LOW"  # Object storage is transferable
        elif workload_type == "serverless":
            return "MEDIUM"  # Functions need rewriting for different platforms
        elif workload_type == "database":
            return "HIGH"  # Managed DBs have vendor lock-in
        else:
            return "MEDIUM"

    def _estimate_migration_cost(self, workload_type, complexity, specs):
        """Estimate one-time migration cost."""
        base_costs = {
            "LOW": 500,
            "MEDIUM": 2000,
            "HIGH": 10000
        }

        base_cost = base_costs[complexity]

        # Add data transfer costs if applicable
        if workload_type == "storage":
            size_tb = specs.get("size_tb", 0)
            transfer_cost = size_tb * 50  # ~$50/TB for cross-cloud transfer
            return base_cost + transfer_cost

        return base_cost

    def _estimate_effort_weeks(self, complexity):
        """Estimate migration effort in weeks."""
        return {"LOW": 1, "MEDIUM": 4, "HIGH": 12}.get(complexity, 4)

    def _generate_migration_roadmap(self, workload_type, from_provider, to_provider, complexity):
        """Generate step-by-step migration roadmap."""
        roadmap = []

        roadmap.append(f"Phase 1: Assessment (Week 1)")
        roadmap.append(f"- Audit dependencies on {from_provider.upper()}-specific services")
        roadmap.append(f"- Identify portable vs vendor-locked components")
        roadmap.append(f"- Create {to_provider.upper()} trial account and test environment")

        roadmap.append(f"Phase 2: Planning (Week 2)")
        roadmap.append(f"- Design {to_provider.upper()} architecture equivalent to current")
        roadmap.append(f"- Plan data migration strategy (minimize downtime)")
        roadmap.append("- Establish rollback procedures")

        if workload_type == "kubernetes":
            roadmap.append("Phase 3: Migration (Week 3)")
            roadmap.append(f"- Deploy Kubernetes cluster on {to_provider.upper()}")
            roadmap.append("- Update container registries and CI/CD pipelines")
            roadmap.append("- Blue-green deployment to minimize downtime")

        elif workload_type == "compute_vm":
            roadmap.append("Phase 3: Migration (Weeks 3-4)")
            roadmap.append(f"- Convert VM images to {to_provider.upper()} format")
            roadmap.append("- Migrate data using cloud transfer service")
            roadmap.append("- Reconfigure networking, DNS, and load balancers")

        roadmap.append("Phase 4: Validation & Cutover")
        roadmap.append("- Performance testing and cost validation")
        roadmap.append("- Gradual traffic migration (10% → 50% → 100%)")
        roadmap.append(f"- Decommission {from_provider.upper()} resources after stabilization")

        return roadmap


if __name__ == "__main__":
    # Test with compute workload
    sample_specs = json.dumps({
        "vcpu": 8,
        "memory_gb": 32,
        "storage_gb": 500,
        "bandwidth_gb_month": 1000
    })

    tool = CalculateCrossProviderArbitrage(
        workload_type="compute_vm",
        specs=sample_specs,
        current_provider="aws",
        region_preference="us_east"
    )
    print(tool.run())
