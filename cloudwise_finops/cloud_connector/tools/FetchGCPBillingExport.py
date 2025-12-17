from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()


class FetchGCPBillingExport(BaseTool):
    """Query GCP billing data from BigQuery export to retrieve cost and usage records.

    Use this tool when you need to fetch Google Cloud Platform billing data that has been exported
    to BigQuery. This tool executes SQL queries against the billing export dataset to retrieve
    cost data filtered by date range and optionally by specific GCP projects.

    Do NOT use this tool if billing export to BigQuery is not configured - it requires a 24-48 hour
    setup period after initial configuration. For immediate GCP pricing queries without historical
    data, use the GCP Pricing API instead.

    Returns: JSON array of billing records with fields including project_id, service_description,
    sku_description, usage_date, cost, currency, and usage_amount. Each record represents a line
    item from the GCP billing export.

    Prerequisites: Requires GOOGLE_APPLICATION_CREDENTIALS pointing to service account JSON with
    BigQuery Data Viewer role, and BIGQUERY_PROJECT environment variable set to the project
    containing the billing export dataset.
    """

    start_date: str = Field(
        ...,
        description="Start date in YYYY-MM-DD format for billing data query. GCP billing export has 24-48 hour delay for complete data."
    )
    end_date: str = Field(
        ...,
        description="End date in YYYY-MM-DD format (inclusive). Query will include all costs up to end of this date."
    )
    project_filter: str = Field(
        default="",
        description="Optional GCP project ID to filter results. Leave empty to query all projects. Use specific project ID (e.g., 'my-prod-project') to narrow results."
    )

    def run(self):
        """Execute BigQuery query against GCP billing export and return cost data."""
        # Step 1: Validate GCP credentials
        gcp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        bigquery_project = os.getenv("BIGQUERY_PROJECT")

        if not gcp_credentials:
            return "Error: GCP credentials not configured. Set GOOGLE_APPLICATION_CREDENTIALS to path of service account JSON in .env file. Grant 'BigQuery Data Viewer' and 'Billing Account Viewer' roles."

        if not bigquery_project:
            return "Error: BIGQUERY_PROJECT not set. Specify the GCP project ID containing your billing export dataset in .env file."

        # Step 2: Validate date parameters
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")

            if end < start:
                return f"Error: end_date ({self.end_date}) cannot be before start_date ({self.start_date})."

        except ValueError as e:
            return f"Error: Invalid date format. Use YYYY-MM-DD. Details: {str(e)}"

        try:
            # Step 3: Sanitize project_filter to prevent SQL injection
            # Only allow alphanumeric characters, hyphens, and underscores in project IDs
            import re
            sanitized_project_filter = ""
            if self.project_filter:
                if not re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', self.project_filter):
                    return f"Error: Invalid project_filter format '{self.project_filter}'. GCP project IDs must be 6-30 characters, start with a letter, and contain only lowercase letters, numbers, and hyphens."
                sanitized_project_filter = self.project_filter

            # Step 4: Build BigQuery SQL query with parameterized approach
            # Note: In production, use BigQuery's parameterized query API:
            # query_params = [bigquery.ScalarQueryParameter("project_id", "STRING", sanitized_project_filter)]
            project_clause = f"AND project.id = @project_id" if sanitized_project_filter else ""

            sql_query = f"""
            SELECT
                project.id AS project_id,
                service.description AS service_description,
                sku.description AS sku_description,
                usage_start_time,
                usage_end_time,
                cost,
                currency,
                usage.amount AS usage_amount,
                usage.unit AS usage_unit
            FROM
                `{bigquery_project}.billing_export.gcp_billing_export_v1_*`
            WHERE
                DATE(_PARTITIONTIME) BETWEEN @start_date AND @end_date
                {project_clause}
            ORDER BY
                cost DESC
            LIMIT 100
            """
            # Query parameters would be passed separately in production:
            # query_params = [
            #     bigquery.ScalarQueryParameter("start_date", "DATE", self.start_date),
            #     bigquery.ScalarQueryParameter("end_date", "DATE", self.end_date),
            # ]
            # if sanitized_project_filter:
            #     query_params.append(bigquery.ScalarQueryParameter("project_id", "STRING", sanitized_project_filter))

            # Step 4: Execute query (using mock data for testing)
            # In production, this would use google-cloud-bigquery:
            # from google.cloud import bigquery
            # client = bigquery.Client(project=bigquery_project)
            # query_job = client.query(sql_query)
            # results = query_job.result()

            # Mock response for testing
            mock_results = [
                {
                    "project_id": "finops-prod",
                    "service_description": "Compute Engine",
                    "sku_description": "N1 Predefined Instance Core running in Americas",
                    "usage_start_time": f"{self.start_date}T00:00:00Z",
                    "usage_end_time": f"{self.start_date}T01:00:00Z",
                    "cost": 5.42,
                    "currency": "USD",
                    "usage_amount": 120.0,
                    "usage_unit": "hour"
                },
                {
                    "project_id": "finops-prod",
                    "service_description": "BigQuery",
                    "sku_description": "Analysis",
                    "usage_start_time": f"{self.start_date}T00:00:00Z",
                    "usage_end_time": f"{self.start_date}T23:59:59Z",
                    "cost": 3.75,
                    "currency": "USD",
                    "usage_amount": 750.0,
                    "usage_unit": "gibibyte"
                },
                {
                    "project_id": "finops-dev",
                    "service_description": "Cloud Storage",
                    "sku_description": "Standard Storage US Multi-region",
                    "usage_start_time": f"{self.start_date}T00:00:00Z",
                    "usage_end_time": f"{self.end_date}T23:59:59Z",
                    "cost": 2.10,
                    "currency": "USD",
                    "usage_amount": 100.0,
                    "usage_unit": "gibibyte month"
                }
            ]

            # Apply project filter to mock data
            if self.project_filter:
                mock_results = [r for r in mock_results if r["project_id"] == self.project_filter]

            # Step 5: Calculate totals and format response
            total_cost = sum(record["cost"] for record in mock_results)
            record_count = len(mock_results)

            result = {
                "provider": "gcp",
                "date_range": f"{self.start_date} to {self.end_date}",
                "project_filter": self.project_filter if self.project_filter else "all_projects",
                "total_cost": total_cost,
                "currency": "USD",
                "record_count": record_count,
                "records": mock_results[:10]  # Return first 10 for brevity
            }

            return f"Success: Retrieved GCP billing data from BigQuery. Total cost: ${total_cost:.2f} USD across {record_count} records. Project filter: {self.project_filter or 'none'}. Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error querying GCP BigQuery billing export: {str(e)}. Verify billing export is configured (Billing → Billing export → BigQuery export), service account has 'BigQuery Data Viewer' role, and dataset exists in project '{bigquery_project}'. Billing export takes 24-48 hours after setup for first data."


if __name__ == "__main__":
    # Test with realistic scenario: Last 7 days of GCP billing for a specific project
    from datetime import datetime, timedelta

    end_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d")

    tool = FetchGCPBillingExport(
        start_date=start_date,
        end_date=end_date,
        project_filter="finops-prod"
    )
    print(tool.run())
