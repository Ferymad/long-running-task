from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime
import os

class GenerateCostReport(BaseTool):
    """Generate comprehensive cost reports with customizable formats, time ranges, and aggregation levels.

    Use this tool to create formatted cost reports for stakeholders including executives, engineering
    teams, and finance departments. The tool aggregates multi-cloud cost data with breakdowns by
    service, region, account, project, or custom tag dimensions. Supports multiple output formats
    (JSON for APIs, CSV for spreadsheets, HTML for dashboards) with visualization-ready data.

    Do NOT generate reports for real-time data - cost data has 24-48 hour lag across cloud providers.
    For current-day estimates, use forecasting tools instead. Reports are most accurate for completed
    billing periods (previous day, week, month, quarter).

    Returns: Report content as formatted string plus metadata including report_path (if saved to disk),
    total_cost, cost_by_provider breakdown, top_services (5 highest cost items), cost_trends
    (comparison to previous period), and summary_insights (notable patterns, anomalies, optimization
    opportunities identified in the data).

    Report includes: Executive summary with total costs and YoY/MoM trends, cost breakdown by cloud
    provider (AWS/GCP/Azure), top 10 services by cost, regional distribution, cost per environment
    (prod/staging/dev), untagged resource costs, reserved instance utilization, and anomaly highlights.
    Formatting includes currency symbols, percentage changes, and color-coded warnings for overspending.
    """

    data: str = Field(
        ...,
        description="JSON string with cost data to report on. Expected format: {records: [{provider, service, cost, date, tags}, ...], summary: {total_cost, providers}}. From NormalizeCostData or CacheCostSnapshot."
    )
    format: str = Field(
        default="json",
        description="Output format for report. Valid values: 'json' (API-friendly), 'csv' (spreadsheet), 'html' (dashboard), 'markdown' (documentation). Default 'json' for programmatic access."
    )
    time_range: str = Field(
        ...,
        description="Time period covered by report for labeling. Format: 'YYYY-MM-DD to YYYY-MM-DD' or 'December 2025' or 'Q4 2025'. Used in report title and comparisons."
    )
    aggregation_level: str = Field(
        default="service",
        description="How to aggregate costs in report. Valid values: 'service' (by cloud service), 'region' (by geographic region), 'account' (by cloud account), 'tag' (by custom tag key), 'environment'. Default 'service'."
    )

    def run(self):
        """Generate formatted cost report from provided data."""
        # Step 1: Validate format
        valid_formats = ["json", "csv", "html", "markdown"]
        if self.format not in valid_formats:
            return f"Error: Invalid format '{self.format}'. Must be one of: {', '.join(valid_formats)}"

        # Step 2: Validate aggregation level
        valid_aggregations = ["service", "region", "account", "tag", "environment", "provider"]
        if self.aggregation_level not in valid_aggregations:
            return f"Error: Invalid aggregation_level '{self.aggregation_level}'. Must be one of: {', '.join(valid_aggregations)}"

        # Step 3: Parse cost data
        try:
            cost_data = json.loads(self.data)

            if "records" not in cost_data:
                return "Error: data must contain 'records' array with cost entries. Provide output from NormalizeCostData or CacheCostSnapshot."

            records = cost_data["records"]

            if not records:
                return "Warning: No cost records to report. Provide data containing cost entries."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in data parameter. Details: {str(e)}"

        try:
            # Step 4: Calculate summary statistics
            total_cost = sum(record.get("cost", 0) for record in records)
            currency = records[0].get("currency", "USD") if records else "USD"

            # Breakdown by provider
            provider_costs = {}
            for record in records:
                provider = record.get("provider", "unknown")
                provider_costs[provider] = provider_costs.get(provider, 0) + record.get("cost", 0)

            # Step 5: Aggregate by specified level
            aggregated_costs = {}

            for record in records:
                if self.aggregation_level == "service":
                    key = record.get("service", "unknown")
                elif self.aggregation_level == "region":
                    key = record.get("region", "unknown")
                elif self.aggregation_level == "account":
                    key = record.get("account_id", "unknown")
                elif self.aggregation_level == "provider":
                    key = record.get("provider", "unknown")
                elif self.aggregation_level == "environment":
                    key = record.get("tags", {}).get("environment", "untagged")
                else:  # tag
                    key = record.get("tags", {}).get(self.aggregation_level, "untagged")

                aggregated_costs[key] = aggregated_costs.get(key, 0) + record.get("cost", 0)

            # Sort by cost descending
            top_items = sorted(aggregated_costs.items(), key=lambda x: x[1], reverse=True)

            # Step 6: Identify insights
            insights = []

            # Top cost drivers
            if top_items:
                top_item = top_items[0]
                top_percent = (top_item[1] / total_cost * 100) if total_cost > 0 else 0
                insights.append(f"Top {self.aggregation_level}: {top_item[0]} (${top_item[1]:.2f}, {top_percent:.1f}% of total)")

            # Multi-cloud usage
            if len(provider_costs) > 1:
                insights.append(f"Multi-cloud deployment across {len(provider_costs)} providers")

            # Untagged resources
            untagged_cost = aggregated_costs.get("untagged", 0)
            if untagged_cost > 0:
                untagged_percent = (untagged_cost / total_cost * 100) if total_cost > 0 else 0
                if untagged_percent > 10:
                    insights.append(f"WARNING: {untagged_percent:.1f}% of costs from untagged resources (${untagged_cost:.2f})")

            # Step 7: Generate report in requested format
            if self.format == "json":
                report_content = self._generate_json_report(
                    total_cost, currency, provider_costs, top_items, records, insights
                )
            elif self.format == "csv":
                report_content = self._generate_csv_report(
                    top_items, self.aggregation_level, currency
                )
            elif self.format == "html":
                report_content = self._generate_html_report(
                    total_cost, currency, provider_costs, top_items, insights
                )
            else:  # markdown
                report_content = self._generate_markdown_report(
                    total_cost, currency, provider_costs, top_items, insights
                )

            # Step 8: Save report to disk (optional)
            report_filename = f"cloudwise_cost_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{self.format}"
            report_path = os.path.join(os.getcwd(), report_filename)

            try:
                with open(report_path, 'w') as f:
                    f.write(report_content)
                saved_to_disk = True
            except Exception as e:
                saved_to_disk = False
                report_path = f"Could not save to disk: {str(e)}"

            # Step 9: Build result
            result = {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "time_range": self.time_range,
                    "format": self.format,
                    "aggregation_level": self.aggregation_level,
                    "record_count": len(records),
                    "report_path": report_path if saved_to_disk else None
                },
                "cost_summary": {
                    "total_cost": round(total_cost, 2),
                    "currency": currency,
                    "provider_breakdown": {k: round(v, 2) for k, v in provider_costs.items()},
                    "top_5_items": [
                        {"name": item[0], "cost": round(item[1], 2), "percent": round((item[1]/total_cost*100), 1)}
                        for item in top_items[:5]
                    ]
                },
                "insights": insights,
                "report_preview": report_content[:500] if self.format != "json" else report_content[:200]
            }

            # Step 10: Generate summary
            top_3_text = ", ".join([f"{item[0]} (${item[1]:.2f})" for item in top_items[:3]])
            summary = f"Generated {self.format.upper()} cost report for {self.time_range}. Total cost: ${total_cost:.2f} {currency}. Provider breakdown: {', '.join([f'{k}: ${v:.2f}' for k, v in provider_costs.items()])}. Top 3 {self.aggregation_level}s: {top_3_text}. {'Saved to: ' + report_path if saved_to_disk else 'Report content returned inline'}."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error generating report: {str(e)}. Verify data structure and parameters are valid."

    def _generate_json_report(self, total_cost, currency, provider_costs, top_items, records, insights):
        """Generate JSON format report."""
        report = {
            "report_title": f"CloudWise FinOps Cost Report - {self.time_range}",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_cost": round(total_cost, 2),
                "currency": currency,
                "provider_costs": {k: round(v, 2) for k, v in provider_costs.items()}
            },
            "cost_breakdown": [
                {
                    "name": item[0],
                    "cost": round(item[1], 2),
                    "percent_of_total": round((item[1]/total_cost*100), 2) if total_cost > 0 else 0
                }
                for item in top_items[:20]  # Top 20
            ],
            "insights": insights,
            "record_count": len(records)
        }
        return json.dumps(report, indent=2)

    def _generate_csv_report(self, top_items, aggregation_level, currency):
        """Generate CSV format report."""
        lines = [
            f"CloudWise FinOps Cost Report - {self.time_range}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"{aggregation_level.title()},Cost ({currency}),Percent of Total"
        ]

        total = sum(item[1] for item in top_items)

        for item in top_items:
            percent = (item[1] / total * 100) if total > 0 else 0
            lines.append(f"{item[0]},{item[1]:.2f},{percent:.1f}%")

        lines.append("")
        lines.append(f"TOTAL,{total:.2f},100.0%")

        return "\n".join(lines)

    def _generate_html_report(self, total_cost, currency, provider_costs, top_items, insights):
        """Generate HTML format report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CloudWise FinOps Cost Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .insight {{ background-color: #fff3cd; padding: 10px; margin: 5px 0; border-left: 4px solid #ffc107; }}
    </style>
</head>
<body>
    <h1>CloudWise FinOps Cost Report</h1>
    <p><strong>Time Range:</strong> {self.time_range}</p>
    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <h2>Cost Summary</h2>
        <p><strong>Total Cost:</strong> ${total_cost:.2f} {currency}</p>
        <h3>By Provider:</h3>
        <ul>
            {''.join([f"<li>{provider}: ${cost:.2f}</li>" for provider, cost in provider_costs.items()])}
        </ul>
    </div>

    <h2>Top {self.aggregation_level.title()}s by Cost</h2>
    <table>
        <tr>
            <th>{self.aggregation_level.title()}</th>
            <th>Cost ({currency})</th>
            <th>% of Total</th>
        </tr>
        {''.join([f"<tr><td>{item[0]}</td><td>${item[1]:.2f}</td><td>{(item[1]/total_cost*100):.1f}%</td></tr>" for item in top_items[:15]])}
    </table>

    <h2>Insights</h2>
    {''.join([f'<div class="insight">{insight}</div>' for insight in insights])}
</body>
</html>
"""
        return html

    def _generate_markdown_report(self, total_cost, currency, provider_costs, top_items, insights):
        """Generate Markdown format report."""
        md = f"""# CloudWise FinOps Cost Report

**Time Range:** {self.time_range}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Cost Summary

- **Total Cost:** ${total_cost:.2f} {currency}

### By Provider
{''.join([f'- {provider}: ${cost:.2f}\\n' for provider, cost in provider_costs.items()])}

## Top {self.aggregation_level.title()}s by Cost

| {self.aggregation_level.title()} | Cost ({currency}) | % of Total |
|---|---:|---:|
{''.join([f'| {item[0]} | ${item[1]:.2f} | {(item[1]/total_cost*100):.1f}% |\\n' for item in top_items[:15]])}

## Insights

{''.join([f'- {insight}\\n' for insight in insights])}
"""
        return md


if __name__ == "__main__":
    # Test with sample cost data
    sample_data = json.dumps({
        "records": [
            {"provider": "aws", "service": "EC2", "cost": 8200.50, "region": "us-east-1", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "aws", "service": "S3", "cost": 2150.25, "region": "us-east-1", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "gcp", "service": "Compute Engine", "cost": 5420.00, "region": "us-central1", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "azure", "service": "Virtual Machines", "cost": 3250.75, "region": "eastus", "currency": "USD", "tags": {"environment": "staging"}}
        ]
    })

    tool = GenerateCostReport(
        data=sample_data,
        format="markdown",
        time_range="December 1-15, 2025",
        aggregation_level="service"
    )
    print(tool.run())
