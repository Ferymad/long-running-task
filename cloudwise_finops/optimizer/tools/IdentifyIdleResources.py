from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime, timedelta

class IdentifyIdleResources(BaseTool):
    """Identify idle or underutilized cloud resources consuming costs with minimal business value.

    Use this tool to discover zombie resources across AWS, GCP, and Azure that have consistent
    low utilization (<5% CPU/memory average) over an extended period (14+ days). Common idle
    resources include: stopped-but-not-terminated instances, unattached EBS volumes, unused
    load balancers, idle databases, and orphaned elastic IPs that accumulate costs silently.

    Do NOT use this tool immediately after deployments or during known maintenance periods -
    temporary idle states during rollouts are expected. Focus on resources with sustained low
    utilization over 2+ weeks that indicate forgotten or abandoned infrastructure.

    Returns: JSON array of idle resources with resource_id, resource_type, provider, region,
    last_activity_timestamp, days_idle, current_monthly_cost, potential_monthly_savings,
    and recommended_action (terminate, downsize, or investigate). Total potential savings
    aggregated across all identified idle resources.

    Detection thresholds: <5% avg utilization for 14+ consecutive days, OR stopped state for
    7+ days (AWS EC2), OR zero network traffic for 14+ days (load balancers, NAT gateways).
    Storage resources flagged if unattached for 30+ days. Adjust sensitivity with lookback_days.
    """

    provider: str = Field(
        ...,
        description="Cloud provider to scan for idle resources. Valid values: 'aws', 'gcp', 'azure', 'all'. Use 'all' to scan across multi-cloud environment."
    )
    resource_type: str = Field(
        default="all",
        description="Specific resource type to analyze or 'all' for comprehensive scan. Examples: 'compute', 'storage', 'database', 'network'. Use 'all' for initial discovery."
    )
    lookback_days: int = Field(
        default=14,
        description="Number of days to analyze for idle detection. Default 14 days balances accuracy vs detection delay. Use 7 for aggressive cleanup, 30 for conservative approach."
    )

    def run(self):
        """Scan for idle resources and calculate potential savings."""
        # Step 1: Validate provider
        valid_providers = ["aws", "gcp", "azure", "all"]
        if self.provider not in valid_providers:
            return f"Error: Invalid provider '{self.provider}'. Must be one of: {', '.join(valid_providers)}"

        # Step 2: Validate lookback period
        if self.lookback_days < 7:
            return "Warning: lookback_days < 7 may produce false positives during normal operations. Recommend 14-30 days for reliable idle detection."

        if self.lookback_days > 90:
            return "Warning: lookback_days > 90 may miss recently idle resources. Consider 14-30 days for active cleanup."

        # Step 3: Determine providers to scan
        providers_to_scan = [self.provider] if self.provider != "all" else ["aws", "gcp", "azure"]

        try:
            # Step 4: Scan each provider for idle resources
            all_idle_resources = []

            for provider in providers_to_scan:
                idle_resources = self._scan_provider(provider, self.resource_type, self.lookback_days)
                all_idle_resources.extend(idle_resources)

            # Step 5: Calculate total savings potential
            total_monthly_savings = sum(r["potential_monthly_savings"] for r in all_idle_resources)
            total_annual_savings = total_monthly_savings * 12

            # Step 6: Group by resource type for summary
            resource_type_breakdown = {}

            for resource in all_idle_resources:
                rtype = resource["resource_type"]
                if rtype not in resource_type_breakdown:
                    resource_type_breakdown[rtype] = {
                        "count": 0,
                        "total_savings": 0
                    }

                resource_type_breakdown[rtype]["count"] += 1
                resource_type_breakdown[rtype]["total_savings"] += resource["potential_monthly_savings"]

            # Step 7: Prioritize resources by savings potential
            sorted_resources = sorted(
                all_idle_resources,
                key=lambda x: x["potential_monthly_savings"],
                reverse=True
            )

            # Step 8: Build result
            result = {
                "scan_summary": {
                    "providers_scanned": providers_to_scan,
                    "resource_type_filter": self.resource_type,
                    "lookback_days": self.lookback_days,
                    "total_idle_resources": len(all_idle_resources),
                    "total_monthly_savings": round(total_monthly_savings, 2),
                    "total_annual_savings": round(total_annual_savings, 2)
                },
                "breakdown_by_type": resource_type_breakdown,
                "idle_resources": sorted_resources[:20],  # Top 20 by savings potential
                "quick_wins": [r for r in sorted_resources if r["potential_monthly_savings"] > 100][:5]
            }

            # Step 9: Generate summary
            if all_idle_resources:
                top_resource = sorted_resources[0]
                summary = f"Identified {len(all_idle_resources)} idle resources across {', '.join(providers_to_scan)}. Total potential savings: ${total_monthly_savings:.2f}/month (${total_annual_savings:.2f}/year). Top opportunity: {top_resource['resource_id']} ({top_resource['resource_type']}) - ${top_resource['potential_monthly_savings']:.2f}/month. Recommended action: {top_resource['recommended_action']}."
            else:
                summary = f"No idle resources detected across {', '.join(providers_to_scan)} with lookback period of {self.lookback_days} days. Either infrastructure is well-optimized or detection thresholds may need adjustment."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error identifying idle resources: {str(e)}. Verify provider credentials and API access permissions."

    def _scan_provider(self, provider, resource_type, lookback_days):
        """Scan specific provider for idle resources (mock implementation)."""
        # In production, this would query cloud provider APIs with metrics
        # For testing, return mock idle resources

        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        mock_idle_resources = {
            "aws": [
                {
                    "resource_id": "i-0abcd1234efgh5678",
                    "resource_name": "legacy-web-server-2023",
                    "resource_type": "EC2 Instance",
                    "provider": "aws",
                    "region": "us-east-1",
                    "last_activity": (datetime.now() - timedelta(days=21)).isoformat(),
                    "days_idle": 21,
                    "utilization_metrics": {
                        "cpu_avg": 2.1,
                        "network_in_avg_kbps": 0.5,
                        "network_out_avg_kbps": 0.3
                    },
                    "current_monthly_cost": 140.16,
                    "potential_monthly_savings": 140.16,
                    "recommended_action": "Terminate - stopped instance still incurring EBS costs",
                    "risk_level": "LOW"
                },
                {
                    "resource_id": "vol-0xyz9876543210abc",
                    "resource_name": "unattached-volume",
                    "resource_type": "EBS Volume",
                    "provider": "aws",
                    "region": "us-east-1",
                    "last_activity": (datetime.now() - timedelta(days=45)).isoformat(),
                    "days_idle": 45,
                    "utilization_metrics": {
                        "attached": False,
                        "size_gb": 500
                    },
                    "current_monthly_cost": 50.00,
                    "potential_monthly_savings": 50.00,
                    "recommended_action": "Delete - unattached for 45 days, create snapshot first",
                    "risk_level": "LOW"
                },
                {
                    "resource_id": "db-mysql-dev-001",
                    "resource_name": "dev-mysql-instance",
                    "resource_type": "RDS Database",
                    "provider": "aws",
                    "region": "us-west-2",
                    "last_activity": (datetime.now() - timedelta(days=18)).isoformat(),
                    "days_idle": 18,
                    "utilization_metrics": {
                        "connections_avg": 0,
                        "cpu_avg": 1.5,
                        "database_size_gb": 20
                    },
                    "current_monthly_cost": 85.00,
                    "potential_monthly_savings": 85.00,
                    "recommended_action": "Investigate - zero connections for 18 days, may be orphaned",
                    "risk_level": "MEDIUM"
                }
            ],
            "gcp": [
                {
                    "resource_id": "instance-staging-old",
                    "resource_name": "staging-vm-2023-q2",
                    "resource_type": "Compute Instance",
                    "provider": "gcp",
                    "region": "us-central1",
                    "last_activity": (datetime.now() - timedelta(days=16)).isoformat(),
                    "days_idle": 16,
                    "utilization_metrics": {
                        "cpu_avg": 3.2,
                        "memory_avg": 15.0
                    },
                    "current_monthly_cost": 97.09,
                    "potential_monthly_savings": 97.09,
                    "recommended_action": "Downsize to smaller instance type or terminate",
                    "risk_level": "LOW"
                }
            ],
            "azure": [
                {
                    "resource_id": "/subscriptions/xxx/resourceGroups/dev/providers/Microsoft.Compute/virtualMachines/test-vm",
                    "resource_name": "test-vm-abandoned",
                    "resource_type": "Virtual Machine",
                    "provider": "azure",
                    "region": "eastus",
                    "last_activity": (datetime.now() - timedelta(days=30)).isoformat(),
                    "days_idle": 30,
                    "utilization_metrics": {
                        "cpu_avg": 1.8,
                        "disk_io_ops_avg": 5
                    },
                    "current_monthly_cost": 140.16,
                    "potential_monthly_savings": 140.16,
                    "recommended_action": "Terminate - test VM idle for 30 days",
                    "risk_level": "LOW"
                }
            ]
        }

        # Filter by resource type if specified
        resources = mock_idle_resources.get(provider, [])

        if resource_type != "all":
            resources = [
                r for r in resources
                if resource_type.lower() in r["resource_type"].lower()
            ]

        return resources


if __name__ == "__main__":
    # Test multi-cloud scan
    tool = IdentifyIdleResources(
        provider="all",
        resource_type="all",
        lookback_days=14
    )
    print(tool.run())
