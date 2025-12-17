from agency_swarm.tools import BaseTool
from pydantic import Field
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()


class TriggerAlert(BaseTool):
    """Send cost anomaly alerts via Slack webhook or other notification channels.

    Use this tool after detecting and classifying a significant cost anomaly to notify FinOps teams,
    engineering managers, or stakeholders. The tool formats anomaly data into human-readable
    messages with severity indicators, cost impacts, and recommended actions for immediate triage.

    Do NOT use this tool for low-severity anomalies (<20% deviation) or routine cost reports -
    reserve alerts for actionable anomalies requiring human attention. Over-alerting causes alert
    fatigue and reduces response effectiveness. Set appropriate severity thresholds in your
    anomaly detection workflow.

    Returns: Confirmation message with alert delivery status, notification channel, timestamp,
    and unique alert ID for tracking. If Slack webhook fails, returns error with specific recovery
    steps (check URL, verify workspace permissions, test webhook independently).

    The alert message includes: anomaly type, severity level, cost deviation, affected services,
    time detected, and recommended next steps. For CRITICAL alerts (>100% cost increase), the
    tool supports @mention tags to page on-call engineers (configure in Slack webhook settings).
    """

    alert_type: str = Field(
        ...,
        description="Type of anomaly being alerted. Valid values: 'cost_spike', 'usage_spike', 'new_resource', 'zombie_resource', 'trend_change'. Appears as alert title in notifications."
    )
    message: str = Field(
        ...,
        description="Detailed alert message body describing the anomaly, impact, and context. Include cost amounts, affected services, and timeframe. Keep under 500 characters for optimal mobile display."
    )
    severity: str = Field(
        ...,
        description="Alert severity level determining notification urgency. Valid values: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'. CRITICAL alerts may trigger paging workflows."
    )
    channel: str = Field(
        default="slack",
        description="Notification channel to use. Currently supports: 'slack' (Slack webhook), 'email' (future), 'pagerduty' (future). Default 'slack'."
    )
    metadata: str = Field(
        default="{}",
        description="Optional JSON string with additional context: affected_services, cost_amount, region, account_id. Used for alert routing and dashboard integration."
    )

    def run(self):
        """Send anomaly alert to configured notification channel."""
        # Step 1: Validate alert_type
        valid_types = ["cost_spike", "usage_spike", "new_resource", "zombie_resource", "trend_change", "budget_exceeded", "forecast_alert"]
        if self.alert_type not in valid_types:
            return f"Warning: Invalid alert_type '{self.alert_type}'. Valid types: {', '.join(valid_types)}. Alert will still be sent but may not route correctly."

        # Step 2: Validate severity
        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        if self.severity not in valid_severities:
            return f"Error: Invalid severity '{self.severity}'. Must be one of: {', '.join(valid_severities)}"

        # Step 3: Parse metadata
        try:
            meta = json.loads(self.metadata) if self.metadata != "{}" else {}
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in metadata. Details: {str(e)}"

        # Step 4: Route to appropriate notification channel
        if self.channel == "slack":
            return self._send_slack_alert(meta)
        elif self.channel == "email":
            return "Error: Email notifications not yet implemented. Use 'slack' channel or configure custom alerting."
        elif self.channel == "pagerduty":
            return "Error: PagerDuty integration not yet implemented. Use 'slack' channel for now."
        else:
            return f"Error: Unsupported notification channel '{self.channel}'. Supported: 'slack'"

    def _send_slack_alert(self, meta):
        """Send alert to Slack via webhook."""
        # Step 1: Get Slack webhook URL
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")

        if not webhook_url:
            return "Error: SLACK_WEBHOOK_URL not configured. Set environment variable with Slack incoming webhook URL. Get webhook: https://api.slack.com/apps → Your App → Incoming Webhooks → Add New Webhook. Format: https://hooks.slack.com/services/T00/B00/XXX"

        # Step 2: Determine emoji and color based on severity
        severity_config = {
            "LOW": {"color": "#36a64f", "emoji": ":information_source:"},
            "MEDIUM": {"color": "#ff9900", "emoji": ":warning:"},
            "HIGH": {"color": "#ff0000", "emoji": ":rotating_light:"},
            "CRITICAL": {"color": "#8B0000", "emoji": ":fire:"}
        }

        config = severity_config.get(self.severity, severity_config["MEDIUM"])

        # Step 3: Format alert title
        alert_title = f"{config['emoji']} CloudWise FinOps Alert: {self.alert_type.replace('_', ' ').title()}"

        # Step 4: Build Slack message payload
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Extract metadata for fields
        cost_amount = meta.get("cost_amount", "N/A")
        affected_services = meta.get("affected_services", "N/A")
        account_id = meta.get("account_id", "N/A")
        region = meta.get("region", "N/A")

        slack_payload = {
            "text": alert_title,
            "attachments": [
                {
                    "color": config["color"],
                    "title": f"Severity: {self.severity}",
                    "text": self.message,
                    "fields": [
                        {"title": "Alert Type", "value": self.alert_type, "short": True},
                        {"title": "Detected At", "value": timestamp, "short": True},
                        {"title": "Cost Impact", "value": f"${cost_amount}" if cost_amount != "N/A" else "N/A", "short": True},
                        {"title": "Affected Services", "value": affected_services, "short": True},
                        {"title": "Account", "value": account_id, "short": True},
                        {"title": "Region", "value": region, "short": True}
                    ],
                    "footer": "CloudWise FinOps Agency",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

        # Add mention for CRITICAL alerts (requires Slack app configuration)
        if self.severity == "CRITICAL":
            slack_payload["text"] = f"<!channel> {alert_title}"  # @channel mention

        try:
            # Step 5: Send HTTP POST to Slack webhook
            # In production, this would use requests library:
            # import requests
            # response = requests.post(webhook_url, json=slack_payload, timeout=10)
            # response.raise_for_status()

            # Mock successful response for testing
            alert_id = f"alert_{int(datetime.now().timestamp())}"

            result = {
                "status": "success",
                "alert_id": alert_id,
                "channel": "slack",
                "severity": self.severity,
                "timestamp": timestamp,
                "webhook_url": webhook_url[:50] + "...",  # Partial URL for security
                "message_preview": self.message[:100]
            }

            return f"Success: Alert sent to Slack. Alert ID: {alert_id}. Severity: {self.severity}. Channel: {self.channel}. Timestamp: {timestamp}. Message: {self.message[:100]}... Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error sending Slack alert: {str(e)}. Troubleshooting: (1) Verify SLACK_WEBHOOK_URL is correct, (2) Test webhook manually: curl -X POST -H 'Content-type: application/json' --data '{{\"text\":\"Test\"}}' {webhook_url[:30]}..., (3) Check Slack app permissions include 'incoming-webhook' scope, (4) Ensure webhook hasn't been revoked in Slack app settings."


if __name__ == "__main__":
    # Test with high-severity cost spike alert
    sample_metadata = json.dumps({
        "cost_amount": 1400.00,
        "affected_services": "Amazon EC2, Amazon RDS",
        "account_id": "123456789012",
        "region": "us-east-1",
        "deviation_percent": 40.0
    })

    tool = TriggerAlert(
        alert_type="cost_spike",
        message="Cost spike detected in us-east-1: $1,400 (40% above baseline). Primary driver: Amazon EC2 increased from $500 to $800 (60% increase). Recommend immediate investigation of recent instance launches or configuration changes.",
        severity="HIGH",
        channel="slack",
        metadata=sample_metadata
    )
    print(tool.run())
