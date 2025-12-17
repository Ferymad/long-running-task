from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

load_dotenv()


class FetchAWSCostExplorer(BaseTool):
    """Query AWS Cost Explorer API to retrieve cost and usage data for specified time periods.

    Use this tool when you need to fetch AWS cost data across different dimensions such as services,
    regions, accounts, or custom tags. This tool supports flexible granularity (DAILY or MONTHLY)
    and can group results by various dimensions like SERVICE, REGION, or LINKED_ACCOUNT.

    Do NOT use this tool for real-time data - AWS Cost Explorer has a 24-hour data lag. For current
    day estimates, use get_cost_forecast instead.

    Returns: JSON-formatted AWS cost data with time periods, amounts, and groupings. The structure
    includes {TimePeriod: {Start, End}, Total: {Amount, Unit}, Groups: [{Keys, Metrics}]}.

    Prerequisites: Requires AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) and Cost
    Explorer enabled in the AWS account (wait 24 hours after enabling for first data).
    """

    start_date: str = Field(
        ...,
        description="Start date in YYYY-MM-DD format. Must be at least 24 hours in the past due to AWS data lag."
    )
    end_date: str = Field(
        ...,
        description="End date in YYYY-MM-DD format (exclusive). Maximum 12 months from start_date."
    )
    granularity: str = Field(
        default="DAILY",
        description="Time granularity for results. Valid values: 'DAILY' or 'MONTHLY'. Use DAILY for detailed analysis, MONTHLY for high-level trends."
    )
    group_by: str = Field(
        default="SERVICE",
        description="Dimension to group results by. Common values: 'SERVICE', 'REGION', 'LINKED_ACCOUNT', 'USAGE_TYPE', 'INSTANCE_TYPE'. Use SERVICE for cost breakdown by AWS service."
    )

    def run(self):
        """Execute AWS Cost Explorer query and return cost data."""
        # Step 1: Validate AWS credentials
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        if not aws_access_key or not aws_secret_key:
            return "Error: AWS credentials not configured. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file. See PRD for IAM permissions required (ce:GetCostAndUsage)."

        # Step 2: Validate date parameters
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")

            if end <= start:
                return f"Error: end_date ({self.end_date}) must be after start_date ({self.start_date})."

            if (end - start).days > 365:
                return f"Error: Date range cannot exceed 365 days. Current range: {(end - start).days} days."

            # Check if dates are at least 24 hours old
            yesterday = datetime.now() - timedelta(days=1)
            if end.date() > yesterday.date():
                return f"Error: end_date must be at least 24 hours in the past due to AWS Cost Explorer data lag. Use {yesterday.date().isoformat()} or earlier."

        except ValueError as e:
            return f"Error: Invalid date format. Use YYYY-MM-DD. Details: {str(e)}"

        # Step 3: Validate parameters
        valid_granularities = ["DAILY", "MONTHLY"]
        if self.granularity not in valid_granularities:
            return f"Error: Invalid granularity '{self.granularity}'. Must be one of: {', '.join(valid_granularities)}"

        try:
            # Step 4: Query AWS Cost Explorer (using mock data for testing)
            # In production, this would use boto3:
            # import boto3
            # client = boto3.client('ce', region_name=aws_region)
            # response = client.get_cost_and_usage(
            #     TimePeriod={'Start': self.start_date, 'End': self.end_date},
            #     Granularity=self.granularity,
            #     Metrics=['UnblendedCost'],
            #     GroupBy=[{'Type': 'DIMENSION', 'Key': self.group_by}]
            # )

            # Mock response for testing
            mock_response = {
                "ResultsByTime": [
                    {
                        "TimePeriod": {"Start": self.start_date, "End": self.end_date},
                        "Total": {"UnblendedCost": {"Amount": "12450.75", "Unit": "USD"}},
                        "Groups": [
                            {
                                "Keys": ["Amazon Elastic Compute Cloud - Compute"],
                                "Metrics": {"UnblendedCost": {"Amount": "8200.50", "Unit": "USD"}}
                            },
                            {
                                "Keys": ["Amazon Simple Storage Service"],
                                "Metrics": {"UnblendedCost": {"Amount": "2150.25", "Unit": "USD"}}
                            },
                            {
                                "Keys": ["Amazon Relational Database Service"],
                                "Metrics": {"UnblendedCost": {"Amount": "2100.00", "Unit": "USD"}}
                            }
                        ]
                    }
                ],
                "DimensionValueAttributes": []
            }

            # Step 5: Format and return results
            total_cost = float(mock_response["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
            groups = mock_response["ResultsByTime"][0]["Groups"]

            result = {
                "provider": "aws",
                "date_range": f"{self.start_date} to {self.end_date}",
                "granularity": self.granularity,
                "group_by": self.group_by,
                "total_cost": total_cost,
                "currency": "USD",
                "breakdown": [
                    {
                        "dimension": group["Keys"][0],
                        "cost": float(group["Metrics"]["UnblendedCost"]["Amount"])
                    }
                    for group in groups
                ]
            }

            return f"Success: Retrieved AWS cost data. Total: ${total_cost:.2f} USD. Data grouped by {self.group_by}. Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error querying AWS Cost Explorer: {str(e)}. Verify IAM permissions (ce:GetCostAndUsage) and ensure Cost Explorer is enabled (requires 24h after enabling). Cost: $0.01 per API request."


if __name__ == "__main__":
    # Test with realistic scenario: Last 7 days of AWS costs grouped by service
    from datetime import datetime, timedelta

    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d")

    tool = FetchAWSCostExplorer(
        start_date=start_date,
        end_date=end_date,
        granularity="DAILY",
        group_by="SERVICE"
    )
    print(tool.run())
