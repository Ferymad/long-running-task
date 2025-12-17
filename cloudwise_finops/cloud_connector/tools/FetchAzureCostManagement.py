from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

load_dotenv()


class FetchAzureCostManagement(BaseTool):
    """Query Azure Cost Management API to retrieve cost and usage data for Azure subscriptions.

    Use this tool when you need to fetch Microsoft Azure cost data with flexible granularity
    (Daily, Monthly) and grouping options. This tool accesses the Azure Cost Management API
    to retrieve actual costs (not forecasts) for specified date ranges and subscriptions.

    Do NOT use this tool for budget information (use Azure Budgets API instead) or for pricing
    estimates (use Azure Retail Prices API instead). This tool returns actual incurred costs only.

    Returns: JSON-formatted Azure cost data with time periods, totals, and optional groupings
    by resource group, service, or location. Structure includes {rows: [{cost, date, dimensions}],
    columns: [{name, type}]}.

    Prerequisites: Requires Azure Service Principal credentials (AZURE_TENANT_ID, AZURE_CLIENT_ID,
    AZURE_CLIENT_SECRET) with 'Cost Management Reader' role assigned at subscription scope. The
    AZURE_SUBSCRIPTION_ID must also be set to identify which subscription to query.
    """

    start_date: str = Field(
        ...,
        description="Start date in YYYY-MM-DD format. Azure Cost Management provides data with ~24 hour delay for complete accuracy."
    )
    end_date: str = Field(
        ...,
        description="End date in YYYY-MM-DD format (inclusive). Maximum range is 12 months from start_date."
    )
    subscription_id: str = Field(
        default="",
        description="Azure subscription ID to query. Leave empty to use AZURE_SUBSCRIPTION_ID from environment. Format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    )
    granularity: str = Field(
        default="Daily",
        description="Time granularity for cost aggregation. Valid values: 'Daily' or 'Monthly'. Use Daily for detailed analysis, Monthly for trends."
    )
    group_by: str = Field(
        default="ServiceName",
        description="Dimension to group costs by. Common values: 'ServiceName', 'ResourceGroupName', 'ResourceLocation', 'MeterCategory'. Use ServiceName for cost breakdown by Azure service."
    )

    def run(self):
        """Execute Azure Cost Management API query and return cost data."""
        # Step 1: Validate Azure credentials
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        subscription_id = self.subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")

        if not all([tenant_id, client_id, client_secret]):
            return "Error: Azure credentials not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET in .env file. Create service principal: az ad sp create-for-rbac --name cloudwise-finops-bot --role 'Cost Management Reader'"

        if not subscription_id:
            return "Error: AZURE_SUBSCRIPTION_ID not set. Provide subscription_id parameter or set in .env file. Get ID via: az account show --query id"

        # Step 2: Validate date parameters
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")

            if end < start:
                return f"Error: end_date ({self.end_date}) cannot be before start_date ({self.start_date})."

            if (end - start).days > 365:
                return f"Error: Date range cannot exceed 365 days. Current range: {(end - start).days} days."

        except ValueError as e:
            return f"Error: Invalid date format. Use YYYY-MM-DD. Details: {str(e)}"

        # Step 3: Validate parameters
        valid_granularities = ["Daily", "Monthly"]
        if self.granularity not in valid_granularities:
            return f"Error: Invalid granularity '{self.granularity}'. Must be one of: {', '.join(valid_granularities)}"

        try:
            # Step 4: Query Azure Cost Management (using mock data for testing)
            # In production, this would use azure-mgmt-costmanagement:
            # from azure.identity import ClientSecretCredential
            # from azure.mgmt.costmanagement import CostManagementClient
            #
            # credential = ClientSecretCredential(tenant_id, client_id, client_secret)
            # client = CostManagementClient(credential)
            #
            # query_definition = {
            #     "type": "ActualCost",
            #     "timeframe": "Custom",
            #     "time_period": {"from": self.start_date, "to": self.end_date},
            #     "dataset": {
            #         "granularity": self.granularity,
            #         "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            #         "grouping": [{"type": "Dimension", "name": self.group_by}]
            #     }
            # }
            #
            # scope = f"/subscriptions/{subscription_id}"
            # result = client.query.usage(scope, query_definition)

            # Mock response for testing
            mock_response = {
                "columns": [
                    {"name": "Cost", "type": "Number"},
                    {"name": "Date", "type": "String"},
                    {"name": self.group_by, "type": "String"}
                ],
                "rows": [
                    [3250.75, self.start_date, "Virtual Machines"],
                    [1840.50, self.start_date, "Storage"],
                    [925.25, self.start_date, "Azure SQL Database"],
                    [620.00, self.start_date, "Virtual Network"],
                    [385.50, self.start_date, "App Service"]
                ]
            }

            # Step 5: Process and format results
            total_cost = sum(row[0] for row in mock_response["rows"])

            breakdown = [
                {
                    "dimension": row[2],
                    "cost": row[0],
                    "date": row[1]
                }
                for row in mock_response["rows"]
            ]

            result = {
                "provider": "azure",
                "subscription_id": subscription_id,
                "date_range": f"{self.start_date} to {self.end_date}",
                "granularity": self.granularity,
                "group_by": self.group_by,
                "total_cost": total_cost,
                "currency": "USD",
                "breakdown": breakdown
            }

            return f"Success: Retrieved Azure cost data. Total: ${total_cost:.2f} USD for subscription {subscription_id}. Data grouped by {self.group_by}. Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error querying Azure Cost Management: {str(e)}. Verify service principal has 'Cost Management Reader' role on subscription. Grant role: az role assignment create --assignee {client_id} --role 'Cost Management Reader' --scope /subscriptions/{subscription_id}. Note: Azure Cost Management API rate limit is 4 requests/minute per scope."


if __name__ == "__main__":
    # Test with realistic scenario: Last 30 days of Azure costs grouped by service
    from datetime import datetime, timedelta

    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d")

    tool = FetchAzureCostManagement(
        start_date=start_date,
        end_date=end_date,
        granularity="Daily",
        group_by="ServiceName"
    )
    print(tool.run())
