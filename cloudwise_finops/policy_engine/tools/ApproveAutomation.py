from agency_swarm.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime

class ApproveAutomation(BaseTool):
    """Implement human-in-the-loop approval workflow for cost optimization actions exceeding automated thresholds.

    Use this tool when ValidateAction returns 'requires_approval' status to route optimization
    recommendations to appropriate stakeholders for review. The tool generates approval requests,
    tracks approval status, and determines if action can proceed based on auto-approve thresholds,
    manual approvals received, or timeout policies. Supports both synchronous (wait for approval)
    and asynchronous (log and continue) workflows.

    Do NOT use this tool to bypass policy requirements - if ValidateAction returns 'blocked',
    the action cannot be approved without resolving violations first. This tool handles the
    approval workflow step between validation and execution.

    Returns: JSON object with approved (boolean), approval_method ('auto' if below threshold,
    'manual_required' if needs human approval, 'timeout' if expired), approver_list (who approved),
    approval_timestamp, reason for decision, and next_steps (execute action or escalate further).

    Auto-approval criteria: (1) Risk level LOW and cost impact <$100/month, (2) Compliance score >90,
    (3) Action type in pre-approved list (tagging, stop non-prod instances), (4) No critical
    policy violations. Manual approval required for: (1) HIGH risk actions, (2) Cost impact >$1000/month,
    (3) Production environment changes, (4) Policy overrides requested.
    """

    action: str = Field(
        ...,
        description="JSON string with action details from ValidateAction including action_type, resource_id, cost_impact, risk_level, and validation_result. Used to determine approval requirements."
    )
    risk_level: str = Field(
        ...,
        description="Risk level of proposed action. Valid values: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'. Determines approval workflow routing and auto-approve eligibility."
    )
    auto_approve_threshold: float = Field(
        default=100.0,
        description="Maximum monthly cost impact (dollars) that can be auto-approved for LOW risk actions. Default $100. Use 0 to require manual approval for all actions, 1000 for more permissive threshold."
    )

    def run(self):
        """Process approval request and determine if action can proceed."""
        # Step 1: Validate risk level
        valid_risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        if self.risk_level not in valid_risk_levels:
            return f"Error: Invalid risk_level '{self.risk_level}'. Must be one of: {', '.join(valid_risk_levels)}"

        # Step 2: Validate auto-approve threshold
        if self.auto_approve_threshold < 0:
            return "Error: auto_approve_threshold cannot be negative. Use 0 to disable auto-approval, or positive dollar amount."

        # Step 3: Parse action details
        try:
            action_data = json.loads(self.action)

            required_fields = ["action_type", "resource_id", "cost_impact"]
            for field in required_fields:
                if field not in action_data:
                    return f"Error: Missing required field '{field}' in action parameter. Provide: {', '.join(required_fields)}"

            action_type = action_data["action_type"]
            resource_id = action_data["resource_id"]
            cost_impact = float(action_data["cost_impact"])
            environment = action_data.get("environment", "unknown")
            validation_result = action_data.get("validation_result", {})

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in action parameter. Details: {str(e)}"
        except ValueError as e:
            return f"Error: Invalid cost_impact value. Must be numeric. Details: {str(e)}"

        try:
            # Step 4: Check if auto-approval is possible
            can_auto_approve, auto_approve_reason = self._check_auto_approve_eligibility(
                self.risk_level,
                cost_impact,
                action_type,
                environment,
                validation_result
            )

            # Step 5: Process based on auto-approve eligibility
            if can_auto_approve and cost_impact <= self.auto_approve_threshold:
                # AUTO-APPROVED
                approval_decision = self._create_auto_approval(
                    action_data,
                    auto_approve_reason
                )
            else:
                # MANUAL APPROVAL REQUIRED
                approval_decision = self._create_manual_approval_request(
                    action_data,
                    self.risk_level,
                    cost_impact,
                    environment
                )

            # Step 6: Build result
            result = {
                "approval_summary": {
                    "approved": approval_decision["approved"],
                    "approval_method": approval_decision["method"],
                    "approval_timestamp": approval_decision["timestamp"],
                    "reason": approval_decision["reason"]
                },
                "action_details": {
                    "action_type": action_type,
                    "resource_id": resource_id,
                    "cost_impact": cost_impact,
                    "risk_level": self.risk_level,
                    "environment": environment
                },
                "approval_workflow": {
                    "approvers_required": approval_decision.get("approvers_required", []),
                    "approvers_received": approval_decision.get("approvers_received", []),
                    "approval_status": approval_decision.get("status", "complete"),
                    "estimated_approval_time": approval_decision.get("estimated_time", "immediate")
                },
                "next_steps": approval_decision["next_steps"]
            }

            # Step 7: Generate summary
            if approval_decision["approved"]:
                summary = f"Approval: GRANTED via {approval_decision['method'].upper()} - Action '{action_type}' on {resource_id} approved. {approval_decision['reason']}. Proceed with execution."
            else:
                approvers = ", ".join(approval_decision.get("approvers_required", ["manager"]))
                summary = f"Approval: PENDING - Action '{action_type}' on {resource_id} requires manual approval from {approvers}. Risk: {self.risk_level}, Cost impact: ${cost_impact:.2f}/month. {approval_decision['reason']}. {approval_decision.get('estimated_time', 'Review within 24-48 hours')}."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error processing approval: {str(e)}. Verify action structure and parameters are valid."

    def _check_auto_approve_eligibility(self, risk_level, cost_impact, action_type, environment, validation_result):
        """Determine if action qualifies for auto-approval."""
        # Rule 1: Only LOW risk actions can be auto-approved
        if risk_level not in ["LOW"]:
            return False, f"{risk_level} risk actions require manual approval"

        # Rule 2: Production environment changes need approval
        if environment in ["production", "prod"]:
            return False, "Production environment changes require manual approval"

        # Rule 3: Destructive actions need approval
        destructive_actions = ["terminate_instance", "delete_resource", "delete_volume"]
        if action_type in destructive_actions:
            return False, f"Destructive action ({action_type}) requires manual approval"

        # Rule 4: Check validation result for compliance issues
        compliance_score = validation_result.get("compliance_score", 100)
        if compliance_score < 90:
            return False, f"Low compliance score ({compliance_score}) requires manual review"

        # Rule 5: Pre-approved action types (safe operations)
        pre_approved_actions = ["modify_tags", "stop_instance", "add_monitoring"]
        if action_type in pre_approved_actions and cost_impact == 0:
            return True, f"Pre-approved action type ({action_type}) with no cost impact"

        # Rule 6: Low cost impact can be auto-approved
        return True, f"LOW risk action with cost impact ${cost_impact:.2f}/month within threshold"

    def _create_auto_approval(self, action_data, reason):
        """Create auto-approval decision."""
        return {
            "approved": True,
            "method": "auto",
            "timestamp": datetime.now().isoformat(),
            "reason": f"Auto-approved: {reason}",
            "approvers_received": ["system_auto_approval"],
            "status": "complete",
            "estimated_time": "immediate",
            "next_steps": [
                "Execute approved action immediately",
                "Log action in audit trail",
                "Monitor execution results"
            ]
        }

    def _create_manual_approval_request(self, action_data, risk_level, cost_impact, environment):
        """Create manual approval request routing."""
        # Determine required approvers based on risk and cost
        approvers_required = []

        if risk_level == "LOW" and cost_impact < 500:
            approvers_required = ["team_lead"]
            estimated_time = "4-8 hours"
        elif risk_level == "MEDIUM" or (risk_level == "LOW" and cost_impact >= 500):
            approvers_required = ["engineering_manager"]
            estimated_time = "12-24 hours"
        elif risk_level == "HIGH" or cost_impact >= 1000:
            approvers_required = ["engineering_director"]
            estimated_time = "24-48 hours"
        else:  # CRITICAL
            approvers_required = ["engineering_director", "cfo"]
            estimated_time = "48-72 hours"

        # Additional approver for production
        if environment in ["production", "prod"] and "engineering_director" not in approvers_required:
            approvers_required.append("engineering_director")

        return {
            "approved": False,
            "method": "manual_required",
            "timestamp": datetime.now().isoformat(),
            "reason": f"Manual approval required: {risk_level} risk, ${cost_impact:.2f}/month cost impact",
            "approvers_required": approvers_required,
            "approvers_received": [],
            "status": "pending",
            "estimated_time": estimated_time,
            "next_steps": [
                f"Submit approval request to: {', '.join(approvers_required)}",
                f"Include action details: {action_data.get('action_type')} on {action_data.get('resource_id')}",
                f"Estimated approval time: {estimated_time}",
                "Monitor approval status via ticketing system",
                "Re-run ApproveAutomation after approval received to confirm"
            ]
        }


if __name__ == "__main__":
    # Test with LOW risk action (should auto-approve)
    sample_action = json.dumps({
        "action_type": "downsize",
        "resource_id": "i-1234567890abcdef0",
        "resource_type": "EC2 Instance",
        "cost_impact": 70.08,
        "environment": "staging",
        "validation_result": {
            "is_valid": True,
            "compliance_score": 95
        }
    })

    print("Test 1: LOW risk, low cost (should auto-approve)")
    tool1 = ApproveAutomation(
        action=sample_action,
        risk_level="LOW",
        auto_approve_threshold=100.0
    )
    print(tool1.run())
    print("\n" + "="*80 + "\n")

    # Test with HIGH risk action (should require manual approval)
    sample_action_high_risk = json.dumps({
        "action_type": "terminate_instance",
        "resource_id": "i-abcdef0987654321",
        "resource_type": "EC2 Instance",
        "cost_impact": 280.32,
        "environment": "production",
        "validation_result": {
            "is_valid": True,
            "compliance_score": 85
        }
    })

    print("Test 2: HIGH risk, production (should require manual approval)")
    tool2 = ApproveAutomation(
        action=sample_action_high_risk,
        risk_level="HIGH",
        auto_approve_threshold=100.0
    )
    print(tool2.run())
