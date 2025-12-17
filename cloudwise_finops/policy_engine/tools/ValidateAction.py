from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class ValidateAction(BaseTool):
    """Validate proposed optimization or infrastructure actions against organizational policies and approval requirements.

    Use this tool before executing any cost optimization action (rightsizing, termination, migration)
    to ensure it complies with budget limits, approval workflows, and risk policies. The tool checks
    the action against loaded policies (from LoadBudgetPolicies) and returns approval status,
    required_approvals list, violations if any, and next_steps for policy-compliant execution.

    Do NOT bypass this validation for "quick wins" or low-risk actions - all changes to production
    infrastructure must pass policy validation to maintain governance and audit compliance. For
    emergency actions, policies should define expedited approval paths rather than skipping validation.

    Returns: JSON object with is_valid (boolean), approval_status ('auto_approved', 'requires_approval',
    'blocked'), required_approvers (list of roles/emails), policy_violations (specific rules violated),
    estimated_approval_time (hours or days), and recommended_next_steps (specific actions to proceed).

    Validation logic checks: (1) Budget impact - does action exceed spending authority limits,
    (2) Risk level - HIGH risk actions require director approval, (3) Resource protection - blocked
    if resource has critical tags, (4) Environment restrictions - production has stricter rules,
    (5) Approval workflow - routes to appropriate level based on action type and cost impact.
    """

    action_type: str = Field(
        ...,
        description="Type of action to validate. Valid values: 'terminate_instance', 'delete_resource', 'downsize', 'upsize', 'stop_instance', 'migrate', 'modify_tags', 'change_configuration'. Maps to policy risk levels."
    )
    target_resource: str = Field(
        ...,
        description="JSON string with resource details including resource_id, resource_type, tags, cost_impact, environment. Used to check protection policies and cost thresholds."
    )
    policies: str = Field(
        ...,
        description="JSON string containing loaded policies from LoadBudgetPolicies tool. Must include approval_policies and automation_policies for validation."
    )

    def run(self):
        """Validate action against policies and determine approval requirements."""
        # Step 1: Validate action_type
        valid_actions = [
            "terminate_instance", "delete_resource", "downsize", "upsize",
            "stop_instance", "start_instance", "migrate", "modify_tags",
            "change_configuration", "create_resource"
        ]

        if self.action_type not in valid_actions:
            return f"Warning: Unknown action_type '{self.action_type}'. Validation will proceed but may not match policy rules. Valid types: {', '.join(valid_actions)}"

        # Step 2: Parse target resource
        try:
            resource = json.loads(self.target_resource)

            required_fields = ["resource_id", "resource_type"]
            for field in required_fields:
                if field not in resource:
                    return f"Error: Missing required field '{field}' in target_resource. Provide: {', '.join(required_fields)}"

            resource_id = resource["resource_id"]
            resource_type = resource["resource_type"]
            tags = resource.get("tags", {})
            cost_impact = resource.get("cost_impact", 0)
            environment = resource.get("environment", "unknown")

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in target_resource. Details: {str(e)}"

        # Step 3: Parse policies
        try:
            policy_data = json.loads(self.policies)

            if "policies" not in policy_data:
                return "Error: policies parameter must contain 'policies' object from LoadBudgetPolicies output."

            approval_policies = policy_data["policies"].get("approval", [])
            automation_policies = policy_data["policies"].get("automation", [])
            compliance_policies = policy_data["policies"].get("compliance", [])

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in policies parameter. Details: {str(e)}"

        try:
            # Step 4: Determine action risk level
            risk_level = self._assess_action_risk(self.action_type, cost_impact)

            # Step 5: Check for resource protection (critical tags)
            protection_status = self._check_resource_protection(tags, resource_id)

            if protection_status["is_protected"]:
                return self._build_blocked_response(
                    protection_status["reason"],
                    protection_status["details"],
                    resource_id
                )

            # Step 6: Check approval policies
            approval_result = self._check_approval_requirements(
                self.action_type,
                risk_level,
                cost_impact,
                environment,
                approval_policies
            )

            # Step 7: Check automation policies
            automation_result = self._check_automation_policies(
                self.action_type,
                risk_level,
                automation_policies
            )

            # Step 8: Check compliance policies
            compliance_result = self._check_compliance(
                resource,
                compliance_policies
            )

            # Step 9: Aggregate validation results
            is_valid = (
                not protection_status["is_protected"] and
                compliance_result["is_compliant"] and
                (automation_result["can_automate"] or approval_result["can_proceed_with_approval"])
            )

            # Determine approval status
            if protection_status["is_protected"]:
                approval_status = "blocked"
            elif automation_result["can_automate"] and not approval_result["requires_approval"]:
                approval_status = "auto_approved"
            elif approval_result["requires_approval"]:
                approval_status = "requires_approval"
            elif compliance_result["is_compliant"]:
                approval_status = "auto_approved"
            else:
                approval_status = "blocked"

            # Step 10: Build result
            violations = []

            if protection_status["is_protected"]:
                violations.append(protection_status["reason"])

            if not compliance_result["is_compliant"]:
                violations.extend(compliance_result["violations"])

            result = {
                "validation_summary": {
                    "is_valid": is_valid,
                    "approval_status": approval_status,
                    "risk_level": risk_level
                },
                "action_details": {
                    "action_type": self.action_type,
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                    "environment": environment,
                    "cost_impact": cost_impact
                },
                "approval_requirements": {
                    "requires_approval": approval_result["requires_approval"],
                    "required_approvers": approval_result["required_approvers"],
                    "approval_level": approval_result["approval_level"],
                    "waiting_period_hours": approval_result.get("waiting_period_hours", 0),
                    "estimated_approval_time": approval_result.get("estimated_approval_time", "immediate")
                },
                "policy_checks": {
                    "protection_check": protection_status,
                    "automation_check": automation_result,
                    "compliance_check": compliance_result
                },
                "violations": violations,
                "next_steps": self._generate_next_steps(
                    approval_status,
                    approval_result,
                    violations
                )
            }

            # Step 11: Generate summary
            if approval_status == "auto_approved":
                summary = f"Validation: APPROVED - Action '{self.action_type}' on {resource_id} can proceed automatically. Risk level: {risk_level}. No policy violations detected."
            elif approval_status == "requires_approval":
                approvers = ", ".join(approval_result["required_approvers"])
                summary = f"Validation: REQUIRES APPROVAL - Action '{self.action_type}' on {resource_id} needs approval from {approvers}. Risk level: {risk_level}. Waiting period: {approval_result.get('waiting_period_hours', 0)} hours."
            else:  # blocked
                violation_text = "; ".join(violations)
                summary = f"Validation: BLOCKED - Action '{self.action_type}' on {resource_id} violates policies: {violation_text}. Cannot proceed."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error validating action: {str(e)}. Verify target_resource and policies structures are correct."

    def _assess_action_risk(self, action_type, cost_impact):
        """Determine risk level based on action type and cost impact."""
        high_risk_actions = ["terminate_instance", "delete_resource", "migrate"]
        medium_risk_actions = ["downsize", "stop_instance", "change_configuration"]
        low_risk_actions = ["modify_tags", "upsize", "start_instance"]

        if action_type in high_risk_actions or cost_impact > 1000:
            return "HIGH"
        elif action_type in medium_risk_actions or cost_impact > 100:
            return "MEDIUM"
        else:
            return "LOW"

    def _check_resource_protection(self, tags, resource_id):
        """Check if resource has protection tags preventing modification."""
        protected_tags = ["critical", "protected", "do-not-delete", "production-critical"]

        for tag_key, tag_value in tags.items():
            if tag_key.lower() in protected_tags or str(tag_value).lower() in ["true", "critical", "protected"]:
                return {
                    "is_protected": True,
                    "reason": f"Resource has protected tag: {tag_key}={tag_value}",
                    "details": f"Remove protection tag or obtain override approval"
                }

        return {"is_protected": False}

    def _check_approval_requirements(self, action_type, risk_level, cost_impact, environment, approval_policies):
        """Check if action requires approval based on policies."""
        requires_approval = False
        required_approvers = []
        approval_level = "none"
        waiting_period_hours = 0

        # Check each approval policy
        for policy in approval_policies:
            policy_actions = policy.get("actions", [])
            policy_env = policy.get("environments", ["all"])

            # Check if policy applies to this action and environment
            if (action_type in policy_actions or "all" in policy_actions) and \
               (environment in policy_env or "all" in policy_env):

                requires_approval = True
                approval_level = policy.get("approval_level", "manager")
                waiting_period_hours = policy.get("waiting_period_hours", 0)

                # Map approval level to approvers
                if approval_level == "manager":
                    required_approvers.append("Team Manager")
                elif approval_level == "director":
                    required_approvers.append("Engineering Director")
                elif approval_level == "cfo":
                    required_approvers.append("CFO")

        # Risk-based approval requirements
        if risk_level == "HIGH" and "Engineering Director" not in required_approvers:
            requires_approval = True
            required_approvers.append("Engineering Director")
            approval_level = "director"

        return {
            "requires_approval": requires_approval,
            "required_approvers": list(set(required_approvers)),  # Remove duplicates
            "approval_level": approval_level,
            "can_proceed_with_approval": True,
            "waiting_period_hours": waiting_period_hours,
            "estimated_approval_time": f"{waiting_period_hours + 24} hours" if requires_approval else "immediate"
        }

    def _check_automation_policies(self, action_type, risk_level, automation_policies):
        """Check if action can be automated based on risk policies."""
        for policy in automation_policies:
            risk_levels = policy.get("risk_levels", {})

            for level, config in risk_levels.items():
                if level.upper() == risk_level:
                    actions = config if isinstance(config, list) else config.get("actions", [])

                    # Check if action is in allowed automation list
                    action_category = action_type.split("_")[0]  # e.g., "delete" from "delete_resource"

                    if action_category in actions or action_type in actions:
                        approval_required = config.get("approval_required", False) if isinstance(config, dict) else False

                        return {
                            "can_automate": not approval_required,
                            "requires_approval": approval_required,
                            "policy_matched": policy.get("name", "automation_policy")
                        }

        return {"can_automate": False, "requires_approval": True, "policy_matched": None}

    def _check_compliance(self, resource, compliance_policies):
        """Check resource compliance with tagging and other policies."""
        violations = []

        for policy in compliance_policies:
            if policy.get("rule") == "all_resources_must_have_tags":
                required_tags = policy.get("required_tags", [])
                resource_tags = resource.get("tags", {})

                for tag in required_tags:
                    if tag not in resource_tags or not resource_tags[tag]:
                        violations.append(f"Missing required tag: {tag}")

        return {
            "is_compliant": len(violations) == 0,
            "violations": violations
        }

    def _generate_next_steps(self, approval_status, approval_result, violations):
        """Generate actionable next steps based on validation result."""
        if approval_status == "auto_approved":
            return [
                "Action validated and can proceed immediately",
                "Execute action using appropriate tool (e.g., terminate, downsize)",
                "Log action in audit trail for compliance"
            ]
        elif approval_status == "requires_approval":
            steps = [
                f"Submit approval request to: {', '.join(approval_result['required_approvers'])}",
                f"Wait {approval_result.get('waiting_period_hours', 24)} hours for approval window",
                "Upon approval, re-run validation and execute action"
            ]
            return steps
        else:  # blocked
            steps = [f"Resolve policy violation: {v}" for v in violations]
            steps.append("Re-run validation after resolving violations")
            return steps

    def _build_blocked_response(self, reason, details, resource_id):
        """Build response for blocked actions."""
        result = {
            "validation_summary": {
                "is_valid": False,
                "approval_status": "blocked",
                "risk_level": "HIGH"
            },
            "violations": [reason],
            "next_steps": [details]
        }

        return f"Validation: BLOCKED - {reason} for {resource_id}. {details} Details: {json.dumps(result, indent=2)}"


if __name__ == "__main__":
    # Test with sample action and policies
    sample_resource = json.dumps({
        "resource_id": "i-1234567890abcdef0",
        "resource_type": "EC2 Instance",
        "tags": {"environment": "production", "owner": "team-platform"},
        "cost_impact": 140.16,
        "environment": "production"
    })

    sample_policies = json.dumps({
        "policies": {
            "approval": [
                {
                    "name": "High-Risk Action Approval",
                    "type": "approval",
                    "actions": ["delete_resource", "terminate_instance"],
                    "approval_level": "director",
                    "waiting_period_hours": 24,
                    "environments": ["production"]
                }
            ],
            "automation": [
                {
                    "name": "Risk-Based Automation",
                    "type": "automation",
                    "risk_levels": {
                        "high": {"actions": ["delete", "terminate"], "approval_required": True},
                        "medium": {"actions": ["scale_down", "stop"], "approval_required": False},
                        "low": {"actions": ["tag", "alert"], "approval_required": False}
                    }
                }
            ],
            "compliance": []
        }
    })

    tool = ValidateAction(
        action_type="terminate_instance",
        target_resource=sample_resource,
        policies=sample_policies
    )
    print(tool.run())
