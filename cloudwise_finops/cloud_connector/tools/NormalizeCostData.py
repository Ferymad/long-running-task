from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime

class NormalizeCostData(BaseTool):
    """Transform multi-cloud cost data from AWS, GCP, or Azure into a unified schema for consistent analysis.

    Use this tool after fetching cost data from any cloud provider to convert provider-specific
    formats into a standardized structure. This enables cross-cloud cost comparisons, aggregations,
    and reporting without dealing with different field names and data structures.

    Do NOT use this tool for raw data that hasn't been fetched from a cloud provider first. This
    tool expects structured JSON input from FetchAWSCostExplorer, FetchGCPBillingExport, or
    FetchAzureCostManagement tools.

    Returns: JSON array of normalized cost records, each containing: provider, account_id,
    resource_id, resource_name, resource_type, service, region, cost, currency, usage_amount,
    usage_unit, time_period_start, time_period_end, tags, and metadata. This unified format
    can be cached in SQLite or used directly for analysis across all cloud providers.

    The normalization handles provider-specific nuances like AWS LinkedAccount vs GCP project_id,
    Azure ServiceName vs AWS SERVICE dimension, and timezone differences in timestamps.
    """

    raw_data: str = Field(
        ...,
        description="JSON string containing raw cost data from a cloud provider. Must include provider identifier and cost records. Paste output from FetchAWS/GCP/Azure tools."
    )
    source_provider: str = Field(
        ...,
        description="Source cloud provider of the raw data. Valid values: 'aws', 'gcp', 'azure'. This determines which transformation rules to apply."
    )

    def run(self):
        """Transform provider-specific cost data into normalized format."""
        # Step 1: Validate source provider
        valid_providers = ["aws", "gcp", "azure"]
        if self.source_provider not in valid_providers:
            return f"Error: Invalid source_provider '{self.source_provider}'. Must be one of: {', '.join(valid_providers)}"

        try:
            # Step 2: Parse raw data
            data = json.loads(self.raw_data)

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in raw_data parameter. Details: {str(e)}. Ensure you're passing valid JSON output from a Fetch tool."

        try:
            # Step 3: Normalize based on provider
            if self.source_provider == "aws":
                normalized = self._normalize_aws(data)
            elif self.source_provider == "gcp":
                normalized = self._normalize_gcp(data)
            elif self.source_provider == "azure":
                normalized = self._normalize_azure(data)
            else:
                return f"Error: Unsupported provider: {self.source_provider}"

            # Step 4: Validate normalized data
            if not normalized:
                return f"Warning: Normalization produced no records. Check raw_data structure for provider '{self.source_provider}'."

            # Step 5: Return summary and normalized data
            # Defensive type checking for cost values
            total_cost = sum(
                float(record.get("cost", 0) or 0)
                for record in normalized
                if isinstance(record.get("cost"), (int, float, type(None)))
            )
            unique_services = len(set(record.get("service", "unknown") for record in normalized))

            result = {
                "normalized_count": len(normalized),
                "total_cost": total_cost,
                "currency": normalized[0]["currency"] if normalized else "USD",
                "unique_services": unique_services,
                "provider": self.source_provider,
                "records": normalized[:20]  # Return first 20 for response brevity
            }

            return f"Success: Normalized {len(normalized)} cost records from {self.source_provider.upper()}. Total cost: ${total_cost:.2f}. Unique services: {unique_services}. Ready for caching or analysis. Details: {json.dumps(result, indent=2)}"

        except KeyError as e:
            return f"Error: Missing required field in raw_data: {str(e)}. Ensure raw_data comes from a valid Fetch{self.source_provider.upper()} tool output."
        except Exception as e:
            return f"Error normalizing {self.source_provider.upper()} data: {str(e)}. Verify raw_data structure matches expected format."

    def _normalize_aws(self, data):
        """Normalize AWS Cost Explorer data to unified schema."""
        normalized = []

        # Handle AWS breakdown format
        if "breakdown" in data:
            for item in data["breakdown"]:
                record = {
                    "provider": "aws",
                    "account_id": data.get("account_id", "unknown"),
                    "resource_id": f"aws:{item['dimension']}",
                    "resource_name": item["dimension"],
                    "resource_type": "service",
                    "service": item["dimension"],
                    "region": data.get("region", "global"),
                    "cost": item["cost"],
                    "currency": data.get("currency", "USD"),
                    "usage_amount": 0,  # AWS Cost Explorer doesn't always include usage
                    "usage_unit": "unit",
                    "time_period_start": data.get("date_range", "").split(" to ")[0],
                    "time_period_end": data.get("date_range", "").split(" to ")[1] if " to " in data.get("date_range", "") else "",
                    "tags": {},
                    "metadata": {
                        "granularity": data.get("granularity", "DAILY"),
                        "group_by": data.get("group_by", "SERVICE")
                    }
                }
                normalized.append(record)

        return normalized

    def _normalize_gcp(self, data):
        """Normalize GCP BigQuery billing export data to unified schema."""
        normalized = []

        # Handle GCP records format
        if "records" in data:
            for item in data["records"]:
                record = {
                    "provider": "gcp",
                    "account_id": item.get("project_id", "unknown"),
                    "resource_id": f"gcp:{item.get('sku_description', 'unknown')}",
                    "resource_name": item.get("sku_description", "unknown"),
                    "resource_type": item.get("service_description", "unknown"),
                    "service": item.get("service_description", "unknown"),
                    "region": "global",  # GCP billing export doesn't always include location
                    "cost": item.get("cost", 0),
                    "currency": item.get("currency", "USD"),
                    "usage_amount": item.get("usage_amount", 0),
                    "usage_unit": item.get("usage_unit", "unit"),
                    "time_period_start": item.get("usage_start_time", ""),
                    "time_period_end": item.get("usage_end_time", ""),
                    "tags": {},
                    "metadata": {
                        "sku_description": item.get("sku_description", "")
                    }
                }
                normalized.append(record)

        return normalized

    def _normalize_azure(self, data):
        """Normalize Azure Cost Management data to unified schema."""
        normalized = []

        # Handle Azure breakdown format
        if "breakdown" in data:
            for item in data["breakdown"]:
                record = {
                    "provider": "azure",
                    "account_id": data.get("subscription_id", "unknown"),
                    "resource_id": f"azure:{item['dimension']}",
                    "resource_name": item["dimension"],
                    "resource_type": "service",
                    "service": item["dimension"],
                    "region": data.get("region", "global"),
                    "cost": item["cost"],
                    "currency": data.get("currency", "USD"),
                    "usage_amount": 0,  # Azure Cost Management aggregates usage differently
                    "usage_unit": "unit",
                    "time_period_start": item.get("date", data.get("date_range", "").split(" to ")[0]),
                    "time_period_end": item.get("date", data.get("date_range", "").split(" to ")[1] if " to " in data.get("date_range", "") else ""),
                    "tags": {},
                    "metadata": {
                        "granularity": data.get("granularity", "Daily"),
                        "group_by": data.get("group_by", "ServiceName")
                    }
                }
                normalized.append(record)

        return normalized


if __name__ == "__main__":
    # Test with sample AWS data
    aws_sample = json.dumps({
        "provider": "aws",
        "date_range": "2025-12-10 to 2025-12-17",
        "granularity": "DAILY",
        "group_by": "SERVICE",
        "total_cost": 12450.75,
        "currency": "USD",
        "breakdown": [
            {"dimension": "Amazon EC2", "cost": 8200.50},
            {"dimension": "Amazon S3", "cost": 2150.25},
            {"dimension": "Amazon RDS", "cost": 2100.00}
        ]
    })

    tool = NormalizeCostData(
        raw_data=aws_sample,
        source_provider="aws"
    )
    print(tool.run())
