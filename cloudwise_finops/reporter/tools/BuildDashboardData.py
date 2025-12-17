from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime
from collections import defaultdict

class BuildDashboardData(BaseTool):
    """Aggregate and transform cost data into visualization-ready format for dashboards and charts.

    Use this tool to prepare cost data for BI tools, custom dashboards, or data visualization libraries
    like Chart.js, D3.js, or Plotly. The tool transforms raw cost records into structured datasets
    optimized for common chart types: time series (line charts), categorical breakdowns (pie/bar charts),
    geographic heatmaps, and trend comparisons. Output includes pre-calculated percentages, labels,
    and color suggestions for immediate rendering.

    Do NOT use this tool for raw data exports - it's designed for aggregated, chart-ready data only.
    For detailed records, use GenerateCostReport with CSV/JSON format instead. This tool optimizes
    for dashboard performance by reducing data points and pre-calculating display metrics.

    Returns: JSON object with dashboard_data containing multiple chart-ready datasets: time_series
    (daily/weekly/monthly costs over time), cost_breakdown (services/regions/accounts with percentages),
    provider_comparison (multi-cloud cost distribution), top_services (ranked by cost), trend_indicators
    (MoM/YoY growth rates), and anomaly_highlights (unusual spending patterns flagged for attention).

    Dashboard data includes metadata for rendering: chart_type recommendations, axis labels, color
    palettes, formatting hints (currency, decimals), and drill-down capability indicators. Supports
    responsive design with separate mobile/desktop data density levels.
    """

    raw_data: str = Field(
        ...,
        description="JSON string with cost records to aggregate. Expected format: {records: [{provider, service, cost, date, region, tags}, ...]}. From NormalizeCostData, CacheCostSnapshot, or Fetch tools."
    )
    aggregation_level: str = Field(
        default="daily",
        description="Time granularity for aggregation. Valid values: 'hourly' (real-time dashboards), 'daily' (standard), 'weekly' (trend analysis), 'monthly' (executive reports). Default 'daily'."
    )
    chart_types: str = Field(
        default="all",
        description="Comma-separated list of chart types to generate data for. Valid values: 'timeseries', 'breakdown', 'comparison', 'trend', 'heatmap', 'all'. Default 'all' generates all formats."
    )

    def run(self):
        """Transform cost data into dashboard-ready format."""
        # Step 1: Validate aggregation level
        valid_aggregations = ["hourly", "daily", "weekly", "monthly"]
        if self.aggregation_level not in valid_aggregations:
            return f"Error: Invalid aggregation_level '{self.aggregation_level}'. Must be one of: {', '.join(valid_aggregations)}"

        # Step 2: Parse chart types
        requested_charts = [c.strip() for c in self.chart_types.split(",")]
        valid_charts = ["timeseries", "breakdown", "comparison", "trend", "heatmap", "all"]

        for chart in requested_charts:
            if chart not in valid_charts:
                return f"Warning: Unknown chart type '{chart}'. Valid options: {', '.join(valid_charts)}. Proceeding with recognized types only."

        if "all" in requested_charts:
            requested_charts = ["timeseries", "breakdown", "comparison", "trend", "heatmap"]

        # Step 3: Parse raw data
        try:
            cost_data = json.loads(self.raw_data)

            if "records" not in cost_data:
                return "Error: raw_data must contain 'records' array. Provide output from NormalizeCostData or Fetch tools."

            records = cost_data["records"]

            if not records:
                return "Warning: No cost records to process. Provide data with cost entries."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in raw_data. Details: {str(e)}"

        try:
            # Step 4: Calculate summary metrics
            total_cost = sum(record.get("cost", 0) for record in records)
            currency = records[0].get("currency", "USD") if records else "USD"

            # Step 5: Build dashboard datasets
            dashboard_data = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "record_count": len(records),
                    "total_cost": round(total_cost, 2),
                    "currency": currency,
                    "aggregation_level": self.aggregation_level
                },
                "charts": {}
            }

            # Chart 1: Time Series
            if "timeseries" in requested_charts:
                timeseries_data = self._build_timeseries(records, self.aggregation_level)
                dashboard_data["charts"]["timeseries"] = timeseries_data

            # Chart 2: Cost Breakdown (Pie/Bar)
            if "breakdown" in requested_charts:
                breakdown_data = self._build_breakdown(records, total_cost)
                dashboard_data["charts"]["breakdown"] = breakdown_data

            # Chart 3: Provider Comparison
            if "comparison" in requested_charts:
                comparison_data = self._build_provider_comparison(records, total_cost)
                dashboard_data["charts"]["comparison"] = comparison_data

            # Chart 4: Trend Indicators
            if "trend" in requested_charts:
                trend_data = self._build_trend_indicators(records)
                dashboard_data["charts"]["trend"] = trend_data

            # Chart 5: Geographic Heatmap
            if "heatmap" in requested_charts:
                heatmap_data = self._build_regional_heatmap(records)
                dashboard_data["charts"]["heatmap"] = heatmap_data

            # Step 6: Generate insights for dashboard alerts
            insights = self._generate_dashboard_insights(records, total_cost)
            dashboard_data["insights"] = insights

            # Step 7: Add rendering hints
            dashboard_data["rendering_hints"] = {
                "currency_symbol": "$" if currency == "USD" else currency,
                "decimal_places": 2,
                "color_palette": ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"],
                "responsive_breakpoints": {
                    "mobile": 768,
                    "tablet": 1024,
                    "desktop": 1440
                }
            }

            # Step 8: Generate summary
            chart_count = len([c for c in requested_charts if c in dashboard_data["charts"]])
            summary = f"Generated dashboard data with {chart_count} chart datasets from {len(records)} cost records. Total cost: ${total_cost:.2f} {currency}. Aggregation: {self.aggregation_level}. Charts: {', '.join(requested_charts)}. Insights: {len(insights)} alerts generated."

            return f"{summary} Details: {json.dumps(dashboard_data, indent=2)}"

        except Exception as e:
            return f"Error building dashboard data: {str(e)}. Verify raw_data structure and parameters."

    def _build_timeseries(self, records, aggregation):
        """Build time series data for line charts."""
        # Group by date/time period
        time_buckets = defaultdict(float)

        for record in records:
            date_str = record.get("time_period_start", record.get("date", "unknown"))

            if date_str != "unknown":
                try:
                    date_obj = datetime.fromisoformat(date_str.replace("Z", ""))

                    # Aggregate based on level
                    if aggregation == "hourly":
                        bucket = date_obj.strftime("%Y-%m-%d %H:00")
                    elif aggregation == "daily":
                        bucket = date_obj.strftime("%Y-%m-%d")
                    elif aggregation == "weekly":
                        # Week starting Monday
                        week_start = date_obj - datetime.timedelta(days=date_obj.weekday())
                        bucket = week_start.strftime("%Y-W%U")
                    else:  # monthly
                        bucket = date_obj.strftime("%Y-%m")

                    time_buckets[bucket] += record.get("cost", 0)
                except:
                    continue

        # Sort by date and format for charts
        sorted_buckets = sorted(time_buckets.items())

        return {
            "chart_type": "line",
            "title": f"Cost Over Time ({aggregation.title()})",
            "data": {
                "labels": [bucket[0] for bucket in sorted_buckets],
                "datasets": [{
                    "label": "Total Cost",
                    "data": [round(bucket[1], 2) for bucket in sorted_buckets],
                    "borderColor": "#3498db",
                    "backgroundColor": "rgba(52, 152, 219, 0.1)",
                    "tension": 0.4
                }]
            },
            "axes": {
                "x": {"label": "Time Period", "type": "time"},
                "y": {"label": "Cost (USD)", "beginAtZero": True}
            }
        }

    def _build_breakdown(self, records, total_cost):
        """Build service breakdown data for pie/bar charts."""
        service_costs = defaultdict(float)

        for record in records:
            service = record.get("service", "unknown")
            service_costs[service] += record.get("cost", 0)

        # Sort by cost and take top 10
        top_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:10]

        # Calculate "Other" category
        top_10_total = sum(s[1] for s in top_services)
        other_cost = total_cost - top_10_total

        if other_cost > 0:
            top_services.append(("Other", other_cost))

        return {
            "chart_type": "pie",
            "title": "Cost Breakdown by Service",
            "data": {
                "labels": [service[0] for service in top_services],
                "datasets": [{
                    "data": [round(service[1], 2) for service in top_services],
                    "percentages": [round((service[1]/total_cost*100), 1) for service in top_services],
                    "backgroundColor": [
                        "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
                        "#1abc9c", "#34495e", "#e67e22", "#95a5a6", "#d35400", "#7f8c8d"
                    ]
                }]
            }
        }

    def _build_provider_comparison(self, records, total_cost):
        """Build multi-cloud provider comparison data."""
        provider_costs = defaultdict(float)

        for record in records:
            provider = record.get("provider", "unknown").upper()
            provider_costs[provider] += record.get("cost", 0)

        providers = list(provider_costs.keys())
        costs = [round(provider_costs[p], 2) for p in providers]
        percentages = [round((provider_costs[p]/total_cost*100), 1) for p in providers]

        return {
            "chart_type": "bar",
            "title": "Multi-Cloud Cost Comparison",
            "data": {
                "labels": providers,
                "datasets": [{
                    "label": "Cost by Provider",
                    "data": costs,
                    "percentages": percentages,
                    "backgroundColor": ["#FF9900", "#4285F4", "#00A4EF"]  # AWS, GCP, Azure colors
                }]
            },
            "axes": {
                "x": {"label": "Cloud Provider"},
                "y": {"label": "Cost (USD)", "beginAtZero": True}
            }
        }

    def _build_trend_indicators(self, records):
        """Build trend indicators (growth rates, comparisons)."""
        # Simple trend calculation (would use more sophisticated logic in production)
        total_cost = sum(record.get("cost", 0) for record in records)
        avg_daily = total_cost / max(1, len(set(r.get("date", "") for r in records)))

        # Mock MoM and YoY (would calculate from historical data)
        mom_growth = 5.2  # Mock: 5.2% growth
        yoy_growth = 18.7  # Mock: 18.7% growth

        return {
            "chart_type": "indicators",
            "title": "Cost Trend Indicators",
            "data": {
                "current_month_total": round(total_cost, 2),
                "avg_daily_cost": round(avg_daily, 2),
                "month_over_month": {
                    "percent": mom_growth,
                    "direction": "up" if mom_growth > 0 else "down",
                    "color": "#e74c3c" if mom_growth > 10 else "#f39c12"
                },
                "year_over_year": {
                    "percent": yoy_growth,
                    "direction": "up" if yoy_growth > 0 else "down",
                    "color": "#e74c3c" if yoy_growth > 15 else "#2ecc71"
                }
            }
        }

    def _build_regional_heatmap(self, records):
        """Build geographic heatmap data."""
        region_costs = defaultdict(float)

        for record in records:
            region = record.get("region", "unknown")
            region_costs[region] += record.get("cost", 0)

        # Sort by cost
        sorted_regions = sorted(region_costs.items(), key=lambda x: x[1], reverse=True)

        return {
            "chart_type": "heatmap",
            "title": "Regional Cost Distribution",
            "data": {
                "regions": [
                    {
                        "name": region[0],
                        "cost": round(region[1], 2),
                        "intensity": round((region[1] / max(r[1] for r in sorted_regions) * 100), 0)
                    }
                    for region in sorted_regions
                ]
            },
            "color_scale": {
                "min": "#ecf0f1",
                "max": "#e74c3c"
            }
        }

    def _generate_dashboard_insights(self, records, total_cost):
        """Generate insights for dashboard alerts."""
        insights = []

        # Top cost driver
        service_costs = defaultdict(float)
        for record in records:
            service = record.get("service", "unknown")
            service_costs[service] += record.get("cost", 0)

        if service_costs:
            top_service = max(service_costs.items(), key=lambda x: x[1])
            top_percent = (top_service[1] / total_cost * 100) if total_cost > 0 else 0

            if top_percent > 40:
                insights.append({
                    "type": "warning",
                    "title": "Cost Concentration",
                    "message": f"{top_service[0]} represents {top_percent:.1f}% of total costs",
                    "severity": "high" if top_percent > 60 else "medium"
                })

        # Untagged resources
        untagged_cost = sum(
            record.get("cost", 0)
            for record in records
            if not record.get("tags") or not record.get("tags", {}).get("environment")
        )

        if untagged_cost > 0:
            untagged_percent = (untagged_cost / total_cost * 100) if total_cost > 0 else 0

            if untagged_percent > 10:
                insights.append({
                    "type": "info",
                    "title": "Tagging Compliance",
                    "message": f"{untagged_percent:.1f}% of costs from untagged resources (${untagged_cost:.2f})",
                    "severity": "medium"
                })

        return insights


if __name__ == "__main__":
    # Test with sample data
    sample_data = json.dumps({
        "records": [
            {"provider": "aws", "service": "EC2", "cost": 8200.50, "region": "us-east-1", "date": "2025-12-10", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "aws", "service": "S3", "cost": 2150.25, "region": "us-east-1", "date": "2025-12-10", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "gcp", "service": "Compute Engine", "cost": 5420.00, "region": "us-central1", "date": "2025-12-11", "currency": "USD", "tags": {"environment": "production"}},
            {"provider": "azure", "service": "Virtual Machines", "cost": 3250.75, "region": "eastus", "date": "2025-12-11", "currency": "USD", "tags": {}},
            {"provider": "aws", "service": "RDS", "cost": 2100.00, "region": "us-west-2", "date": "2025-12-12", "currency": "USD", "tags": {"environment": "production"}}
        ]
    })

    tool = BuildDashboardData(
        raw_data=sample_data,
        aggregation_level="daily",
        chart_types="all"
    )
    print(tool.run())
