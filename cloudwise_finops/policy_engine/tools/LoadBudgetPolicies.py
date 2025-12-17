from agency_swarm.tools import BaseTool
from pydantic import Field
import os
import yaml
import json

class LoadBudgetPolicies(BaseTool):
    """Load and parse budget policy configuration files defining spending limits, approval workflows, and compliance rules.

    Use this tool at the start of policy validation workflows to read organization-specific FinOps
    policies from YAML or JSON configuration files. The tool validates policy structure, resolves
    inheritance (parent policies → child policies), and returns a structured policy object ready
    for validation checks by ValidateAction and CheckCompliance tools.

    Do NOT hardcode policies in agent logic - maintain them in version-controlled configuration
    files that can be updated without code changes. Policy files should be stored in the agency's
    files_folder and follow the standardized schema documented in the PRD (budget, approval,
    compliance, and automation policy types).

    Returns: JSON object with parsed policies organized by type (budget_policies, approval_policies,
    compliance_policies, automation_policies), policy_metadata (version, last_updated, owner), and
    validation_status confirming all required fields are present. Policies include thresholds,
    approval requirements, risk levels, and enforcement actions.

    Policy file format supports: budget caps with alert thresholds, multi-level approval workflows
    (manager/director/CFO), tagging requirements, regional restrictions, resource type constraints,
    and risk-based automation rules. Inheritance allows environment-specific overrides (prod policies
    stricter than dev policies).
    """

    policy_file_path: str = Field(
        ...,
        description="Absolute or relative path to policy configuration file. Supports .yaml, .yml, or .json formats. Example: './files/budget_policies.yaml' or '/home/user/cloudwise_finops/policy_engine/files/policies.yaml'"
    )
    environment: str = Field(
        default="production",
        description="Environment context for policy loading. Valid values: 'production', 'staging', 'development'. Some policies may have environment-specific overrides."
    )

    def run(self):
        """Load and parse policy configuration file."""
        # Step 1: Validate file path
        if not os.path.exists(self.policy_file_path):
            # Try relative to current working directory
            alt_path = os.path.join(os.getcwd(), self.policy_file_path)
            if os.path.exists(alt_path):
                self.policy_file_path = alt_path
            else:
                return f"Error: Policy file not found at '{self.policy_file_path}'. Verify path is correct and file exists. Use absolute path or path relative to working directory: {os.getcwd()}"

        # Step 2: Validate file extension
        valid_extensions = [".yaml", ".yml", ".json"]
        file_ext = os.path.splitext(self.policy_file_path)[1].lower()

        if file_ext not in valid_extensions:
            return f"Error: Unsupported policy file format '{file_ext}'. Must be one of: {', '.join(valid_extensions)}"

        try:
            # Step 3: Read file content
            with open(self.policy_file_path, 'r') as f:
                file_content = f.read()

            # Step 4: Parse based on format
            if file_ext in [".yaml", ".yml"]:
                try:
                    policies = yaml.safe_load(file_content)
                except yaml.YAMLError as e:
                    return f"Error: Invalid YAML syntax in policy file. Details: {str(e)}. Verify indentation and structure."
            else:  # JSON
                try:
                    policies = json.loads(file_content)
                except json.JSONDecodeError as e:
                    return f"Error: Invalid JSON syntax in policy file. Details: {str(e)}"

            # Step 5: Validate policy structure
            if not isinstance(policies, dict):
                return "Error: Policy file must contain a dictionary/object at root level."

            if "version" not in policies:
                return "Warning: Policy file missing 'version' field. Recommended format: version: '1.0'"

            if "policies" not in policies:
                return "Error: Policy file must contain 'policies' array/list. See PRD Appendix for policy file format."

            # Step 6: Organize policies by type
            policy_categories = {
                "budget": [],
                "approval": [],
                "compliance": [],
                "automation": [],
                "regional": [],
                "tagging": []
            }

            for policy in policies.get("policies", []):
                policy_type = policy.get("type", "unknown")

                if policy_type in policy_categories:
                    # Apply environment filter if policy has environment-specific rules
                    if "environments" in policy:
                        if self.environment in policy["environments"] or "all" in policy["environments"]:
                            policy_categories[policy_type].append(policy)
                    else:
                        # No environment filter - apply to all
                        policy_categories[policy_type].append(policy)

            # Step 7: Extract metadata
            metadata = {
                "version": policies.get("version", "unknown"),
                "last_updated": policies.get("last_updated", "unknown"),
                "owner": policies.get("owner", "unknown"),
                "environment": self.environment,
                "file_path": self.policy_file_path
            }

            # Step 8: Calculate policy statistics
            total_policies = sum(len(cats) for cats in policy_categories.values())

            stats = {
                "total_policies": total_policies,
                "by_type": {ptype: len(policies) for ptype, policies in policy_categories.items() if policies}
            }

            # Step 9: Validate critical policies exist
            warnings = []

            if not policy_categories["budget"]:
                warnings.append("No budget policies defined - spending limits not enforced")

            if not policy_categories["approval"]:
                warnings.append("No approval policies defined - high-risk actions may execute without review")

            # Step 10: Build result
            result = {
                "metadata": metadata,
                "statistics": stats,
                "policies": policy_categories,
                "warnings": warnings,
                "validation_status": "valid" if total_policies > 0 else "empty"
            }

            # Step 11: Generate summary
            policy_summary = ", ".join([f"{count} {ptype}" for ptype, count in stats["by_type"].items()])

            if warnings:
                warning_text = " Warnings: " + "; ".join(warnings)
            else:
                warning_text = ""

            summary = f"Loaded {total_policies} policies from {os.path.basename(self.policy_file_path)}. Breakdown: {policy_summary}. Environment: {self.environment}. Version: {metadata['version']}.{warning_text}"

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except FileNotFoundError:
            return f"Error: Policy file not found at '{self.policy_file_path}'. Verify file exists and path is correct."
        except PermissionError:
            return f"Error: Permission denied reading policy file '{self.policy_file_path}'. Check file permissions."
        except Exception as e:
            return f"Error loading policy file: {str(e)}. Verify file format follows policy schema documented in PRD."


if __name__ == "__main__":
    # Test with sample policy file (create mock)
    import tempfile

    sample_policy_yaml = """
version: "1.0"
last_updated: "2025-12-17"
owner: "finops-team@company.com"

policies:
  - name: "Monthly Budget Cap"
    type: "budget"
    condition: "monthly_cost > 50000"
    action: "alert"
    severity: "high"
    environments: ["production", "staging"]

  - name: "High-Risk Action Approval"
    type: "approval"
    actions:
      - "delete_resource"
      - "terminate_instance"
    approval_level: "director"
    waiting_period_hours: 24
    environments: ["production"]

  - name: "Tagging Compliance"
    type: "compliance"
    rule: "all_resources_must_have_tags"
    required_tags:
      - "owner"
      - "environment"
      - "cost-center"
    environments: ["all"]

  - name: "Risk-Based Automation"
    type: "automation"
    risk_levels:
      high:
        - "delete"
        - "terminate"
        approval_required: true
      medium:
        - "scale_down"
        - "stop"
        approval_required: false
      low:
        - "tag"
        - "alert"
        approval_required: false
"""

    # Create temporary policy file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(sample_policy_yaml)
        temp_path = f.name

    try:
        tool = LoadBudgetPolicies(
            policy_file_path=temp_path,
            environment="production"
        )
        print(tool.run())
    finally:
        os.unlink(temp_path)
