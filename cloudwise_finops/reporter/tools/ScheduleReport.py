from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime
import os

class ScheduleReport(BaseTool):
    """Schedule recurring cost reports for automated delivery to stakeholders on daily, weekly, or monthly basis.

    Use this tool to set up automated FinOps reporting workflows that run on cron schedules, reducing
    manual effort and ensuring consistent stakeholder communication. The tool creates schedule
    configurations that integrate with job schedulers (cron, systemd timers, Airflow, GitHub Actions)
    to trigger report generation and distribution automatically.

    Do NOT use this for one-time reports - use GenerateCostReport directly instead. Scheduled reports
    are for recurring operational needs: daily anomaly summaries, weekly cost reviews, monthly
    executive reports, and quarterly budget reviews. Each schedule includes data collection, report
    generation, and delivery (email, Slack, S3, dashboard refresh) in a single automated workflow.

    Returns: JSON object with schedule_id (unique identifier for tracking), schedule_config
    (cron expression and parameters), next_run_time (when report will next execute), report_recipients
    (delivery targets), and activation_status (whether schedule is enabled and validated).

    Schedule configuration includes: cron timing (e.g., "0 9 * * MON" for 9 AM every Monday),
    report parameters (format, aggregation, time range logic like "last 7 days"), delivery method
    (email addresses, Slack webhooks, S3 buckets), retry policy (attempts and backoff), and
    notification settings (send only if anomalies detected, include executive summary).
    """

    report_config: str = Field(
        ...,
        description="JSON string with report configuration including format (json/csv/html), aggregation_level (daily/weekly/monthly), filters (providers, services, tags). Example: {format: 'html', aggregation: 'service', providers: ['aws', 'gcp']}"
    )
    schedule_cron: str = Field(
        ...,
        description="Cron expression defining schedule frequency. Examples: '0 9 * * *' (9 AM daily), '0 9 * * MON' (9 AM Mondays), '0 9 1 * *' (9 AM first of month). Use standard cron syntax (minute hour day month weekday)."
    )
    recipients: str = Field(
        ...,
        description="Comma-separated list of delivery targets. Email: 'user@company.com', Slack: 'slack://channel-name', S3: 's3://bucket/path', Multiple: 'user@company.com,slack://finops-alerts'. At least one recipient required."
    )
    time_range_mode: str = Field(
        default="relative",
        description="How to calculate report time range. Valid values: 'relative' (e.g., 'last 7 days'), 'fixed' (e.g., '2025-12-01 to 2025-12-31'), 'period' (e.g., 'current_month'). Default 'relative' for rolling windows."
    )

    def run(self):
        """Create scheduled report configuration."""
        # Step 1: Parse report configuration
        try:
            config = json.loads(self.report_config)

            required_fields = ["format"]
            for field in required_fields:
                if field not in config:
                    return f"Error: Missing required field '{field}' in report_config. Provide: {', '.join(required_fields)}"

            report_format = config["format"]
            aggregation = config.get("aggregation_level", "service")
            providers_filter = config.get("providers", ["all"])

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in report_config. Details: {str(e)}"

        # Step 2: Validate cron expression
        cron_parts = self.schedule_cron.strip().split()

        if len(cron_parts) != 5:
            return f"Error: Invalid cron expression '{self.schedule_cron}'. Must have 5 fields: minute hour day month weekday. Example: '0 9 * * MON'"

        try:
            # Basic validation of cron fields
            minute, hour, day, month, weekday = cron_parts

            # Validate ranges (simplified - production would use croniter library)
            if not all(c in "0123456789*/-," for c in minute):
                return f"Error: Invalid minute field '{minute}' in cron expression."

        except ValueError:
            return f"Error: Could not parse cron expression '{self.schedule_cron}'. Use standard cron format."

        # Step 3: Parse and validate recipients
        recipient_list = [r.strip() for r in self.recipients.split(",")]

        if not recipient_list:
            return "Error: At least one recipient required. Provide email addresses, Slack webhooks, or S3 paths."

        validated_recipients = []

        for recipient in recipient_list:
            if "@" in recipient:
                # Email recipient
                validated_recipients.append({
                    "type": "email",
                    "address": recipient
                })
            elif recipient.startswith("slack://"):
                # Slack channel
                channel = recipient.replace("slack://", "")
                validated_recipients.append({
                    "type": "slack",
                    "channel": channel
                })
            elif recipient.startswith("s3://"):
                # S3 bucket
                validated_recipients.append({
                    "type": "s3",
                    "path": recipient
                })
            else:
                return f"Warning: Unrecognized recipient format '{recipient}'. Use: email@domain.com, slack://channel, or s3://bucket/path"

        # Step 4: Validate time range mode
        valid_time_modes = ["relative", "fixed", "period"]
        if self.time_range_mode not in valid_time_modes:
            return f"Error: Invalid time_range_mode '{self.time_range_mode}'. Must be one of: {', '.join(valid_time_modes)}"

        try:
            # Step 5: Calculate next run time (simplified - production would use croniter)
            next_run_time = self._calculate_next_run(self.schedule_cron)

            # Step 6: Generate schedule ID
            schedule_id = f"schedule_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Step 7: Interpret schedule frequency for human readability
            frequency_description = self._interpret_cron(self.schedule_cron)

            # Step 8: Generate implementation commands
            implementation_steps = self._generate_implementation_steps(
                schedule_id,
                self.schedule_cron,
                config,
                validated_recipients
            )

            # Step 9: Build result
            result = {
                "schedule_summary": {
                    "schedule_id": schedule_id,
                    "frequency": frequency_description,
                    "next_run_time": next_run_time,
                    "activation_status": "pending_implementation",
                    "created_at": datetime.now().isoformat()
                },
                "report_configuration": {
                    "format": report_format,
                    "aggregation_level": aggregation,
                    "providers_filter": providers_filter,
                    "time_range_mode": self.time_range_mode
                },
                "schedule_details": {
                    "cron_expression": self.schedule_cron,
                    "timezone": "UTC",
                    "retry_policy": {
                        "max_attempts": 3,
                        "backoff_minutes": 15
                    }
                },
                "delivery": {
                    "recipient_count": len(validated_recipients),
                    "recipients": validated_recipients,
                    "delivery_methods": list(set(r["type"] for r in validated_recipients))
                },
                "implementation": {
                    "implementation_method": "cron",
                    "steps": implementation_steps
                }
            }

            # Step 10: Generate summary
            recipient_summary = ", ".join([f"{r['type']}({r.get('address', r.get('channel', r.get('path')))})" for r in validated_recipients[:3]])
            if len(validated_recipients) > 3:
                recipient_summary += f" (+{len(validated_recipients) - 3} more)"

            summary = f"Created schedule: {schedule_id}. Frequency: {frequency_description}. Next run: {next_run_time}. Report: {report_format.upper()} aggregated by {aggregation}. Recipients: {recipient_summary}. Status: pending_implementation - see implementation steps."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error creating schedule: {str(e)}. Verify report_config, schedule_cron, and recipients are valid."

    def _calculate_next_run(self, cron_expr):
        """Calculate next run time (simplified)."""
        # In production, would use croniter library for accurate calculation
        # For demo, return approximate next run

        parts = cron_expr.split()
        minute = parts[0]
        hour = parts[1]

        # Simple approximation for next run time
        if minute == "*" and hour == "*":
            next_run = "Within next hour"
        elif minute != "*" and hour != "*":
            next_run = f"Next at {hour}:{minute} UTC"
        else:
            next_run = "Next matching cron schedule"

        return next_run

    def _interpret_cron(self, cron_expr):
        """Convert cron expression to human-readable frequency."""
        parts = cron_expr.split()
        minute, hour, day, month, weekday = parts

        # Daily
        if day == "*" and month == "*" and weekday == "*":
            if hour == "*":
                return "Hourly"
            else:
                return f"Daily at {hour}:{minute if minute != '0' else '00'}"

        # Weekly
        if day == "*" and month == "*" and weekday != "*":
            weekday_names = {
                "0": "Sunday", "1": "Monday", "2": "Tuesday",
                "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday",
                "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
                "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"
            }
            day_name = weekday_names.get(weekday, weekday)
            return f"Weekly on {day_name} at {hour}:{minute if minute != '0' else '00'}"

        # Monthly
        if day != "*" and month == "*":
            return f"Monthly on day {day} at {hour}:{minute if minute != '0' else '00'}"

        return f"Custom schedule: {cron_expr}"

    def _generate_implementation_steps(self, schedule_id, cron_expr, config, recipients):
        """Generate implementation instructions for various schedulers."""
        steps = []

        # Step 1: Cron-based implementation
        steps.append({
            "method": "cron",
            "description": "Add to crontab for Linux/Unix systems",
            "command": f"{cron_expr} cd /path/to/cloudwise_finops && python -m agency_swarm run_scheduled_report --schedule-id {schedule_id}",
            "setup": [
                "Edit crontab: crontab -e",
                "Add command above",
                "Verify with: crontab -l"
            ]
        })

        # Step 2: GitHub Actions (for cloud-native deployments)
        steps.append({
            "method": "github_actions",
            "description": "Schedule via GitHub Actions workflow",
            "config": {
                "name": f"Scheduled Report - {schedule_id}",
                "on": {
                    "schedule": [{"cron": cron_expr}]
                },
                "jobs": {
                    "generate_report": {
                        "runs-on": "ubuntu-latest",
                        "steps": [
                            {"uses": "actions/checkout@v3"},
                            {"name": "Run report", "run": f"python generate_report.py --schedule-id {schedule_id}"}
                        ]
                    }
                }
            }
        })

        # Step 3: Docker/Kubernetes CronJob
        steps.append({
            "method": "kubernetes_cronjob",
            "description": "Deploy as Kubernetes CronJob",
            "yaml": {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {"name": f"finops-report-{schedule_id}"},
                "spec": {
                    "schedule": cron_expr,
                    "jobTemplate": {
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [{
                                        "name": "reporter",
                                        "image": "cloudwise-finops:latest",
                                        "args": ["--schedule-id", schedule_id]
                                    }],
                                    "restartPolicy": "OnFailure"
                                }
                            }
                        }
                    }
                }
            }
        })

        return steps


if __name__ == "__main__":
    # Test with daily report to email
    sample_config = json.dumps({
        "format": "html",
        "aggregation_level": "service",
        "providers": ["aws", "gcp", "azure"]
    })

    tool = ScheduleReport(
        report_config=sample_config,
        schedule_cron="0 9 * * *",  # 9 AM daily
        recipients="finops-team@company.com,slack://finops-alerts",
        time_range_mode="relative"
    )
    print(tool.run())
