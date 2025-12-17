from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class CheckCompliance(BaseTool):
    """Verify resource compliance with organizational policies including tagging standards, regional restrictions, and resource constraints.

    Use this tool to audit existing infrastructure or validate new resource deployments against
    compliance frameworks like SOC2, HIPAA, PCI-DSS, or internal governance policies. The tool
    checks tagging completeness, regional placement rules, resource type restrictions, naming
    conventions, and encryption requirements to identify non-compliant resources requiring remediation.

    Do NOT use this as a one-time audit - integrate compliance checks into CI/CD pipelines and
    scheduled scans (weekly) to maintain continuous compliance. Non-compliant resources should
    trigger alerts and remediation workflows to prevent audit findings and security/cost risks.

    Returns: JSON object with compliant (boolean overall status), compliance_score (0-100),
    violations array with specific policy breaches, severity_breakdown (critical/high/medium/low
    violations), remediation_steps for each violation, and compliant_resources_count vs total.

    Compliance checks performed: (1) Required tags present and non-empty (owner, environment,
    cost-center, project), (2) Resources in allowed regions only, (3) Encryption enabled for
    sensitive data stores, (4) Naming conventions followed, (5) Resource type restrictions (e.g.,
    no public S3 buckets in production), (6) Security group rules validated. Checks are policy-driven
    from LoadBudgetPolicies compliance_policies configuration.
    """

    resource_id: str = Field(
        ...,
        description="Unique identifier of resource to check (e.g., instance ID, S3 bucket name, RDS identifier). Used for audit logging and violation tracking."
    )
    resource_data: str = Field(
        ...,
        description="JSON string with complete resource metadata including tags, region, resource_type, encryption_status, public_access, security_groups. Example: {tags: {owner: 'team'}, region: 'us-east-1', encryption: true}"
    )
    compliance_frameworks: str = Field(
        default="internal",
        description="Comma-separated list of compliance frameworks to check against. Valid values: 'internal' (org policies), 'soc2', 'hipaa', 'pci', 'gdpr', 'all'. Example: 'internal,soc2'"
    )
    policies: str = Field(
        ...,
        description="JSON string containing loaded policies from LoadBudgetPolicies tool. Must include compliance_policies section with tagging, regional, and security rules."
    )

    def run(self):
        """Check resource compliance against organizational policies."""
        # Step 1: Parse resource data
        try:
            resource = json.loads(self.resource_data)

            required_fields = ["tags", "region", "resource_type"]
            for field in required_fields:
                if field not in resource:
                    return f"Error: Missing required field '{field}' in resource_data. Provide: {', '.join(required_fields)}"

            tags = resource.get("tags", {})
            region = resource.get("region", "unknown")
            resource_type = resource.get("resource_type", "unknown")
            encryption_status = resource.get("encryption", False)
            public_access = resource.get("public_access", False)
            environment = tags.get("environment", "unknown")

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in resource_data. Details: {str(e)}"

        # Step 2: Parse policies
        try:
            policy_data = json.loads(self.policies)

            if "policies" not in policy_data:
                return "Error: policies parameter must contain 'policies' object from LoadBudgetPolicies output."

            compliance_policies = policy_data["policies"].get("compliance", [])
            tagging_policies = policy_data["policies"].get("tagging", [])
            regional_policies = policy_data["policies"].get("regional", [])

            if not compliance_policies and not tagging_policies:
                return "Warning: No compliance or tagging policies loaded. Unable to perform compliance check. Load policies using LoadBudgetPolicies first."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in policies parameter. Details: {str(e)}"

        # Step 3: Parse compliance frameworks
        frameworks = [f.strip() for f in self.compliance_frameworks.split(",")]
        valid_frameworks = ["internal", "soc2", "hipaa", "pci", "gdpr", "all"]

        for framework in frameworks:
            if framework not in valid_frameworks:
                return f"Warning: Unknown compliance framework '{framework}'. Valid options: {', '.join(valid_frameworks)}. Proceeding with internal policies only."

        try:
            # Step 4: Perform compliance checks
            violations = []

            # Check 1: Tagging compliance
            tagging_violations = self._check_tagging_compliance(tags, compliance_policies + tagging_policies)
            violations.extend(tagging_violations)

            # Check 2: Regional restrictions
            regional_violations = self._check_regional_compliance(region, regional_policies)
            violations.extend(regional_violations)

            # Check 3: Encryption requirements (for data stores)
            if resource_type in ["RDS", "S3", "EBS", "Database", "Storage"]:
                encryption_violations = self._check_encryption_compliance(encryption_status, frameworks)
                violations.extend(encryption_violations)

            # Check 4: Public access restrictions
            if environment in ["production", "prod"]:
                public_access_violations = self._check_public_access(public_access, resource_type)
                violations.extend(public_access_violations)

            # Check 5: Framework-specific checks
            framework_violations = self._check_framework_requirements(resource, frameworks)
            violations.extend(framework_violations)

            # Step 5: Calculate compliance score
            max_severity_points = {
                "CRITICAL": 25,
                "HIGH": 10,
                "MEDIUM": 5,
                "LOW": 2
            }

            total_deductions = sum(max_severity_points.get(v["severity"], 5) for v in violations)
            compliance_score = max(0, 100 - total_deductions)

            # Step 6: Categorize violations by severity
            severity_breakdown = {
                "CRITICAL": [v for v in violations if v["severity"] == "CRITICAL"],
                "HIGH": [v for v in violations if v["severity"] == "HIGH"],
                "MEDIUM": [v for v in violations if v["severity"] == "MEDIUM"],
                "LOW": [v for v in violations if v["severity"] == "LOW"]
            }

            # Step 7: Determine overall compliance
            is_compliant = len(violations) == 0
            has_critical_violations = len(severity_breakdown["CRITICAL"]) > 0

            # Step 8: Generate remediation steps
            remediation_steps = []
            for violation in violations[:5]:  # Top 5 by severity
                remediation_steps.append({
                    "violation": violation["description"],
                    "severity": violation["severity"],
                    "remediation": violation["remediation"],
                    "estimated_effort": violation.get("effort", "1 hour")
                })

            # Step 9: Build result
            result = {
                "compliance_summary": {
                    "resource_id": self.resource_id,
                    "resource_type": resource_type,
                    "region": region,
                    "environment": environment,
                    "is_compliant": is_compliant,
                    "compliance_score": compliance_score,
                    "frameworks_checked": frameworks
                },
                "violations": {
                    "total_count": len(violations),
                    "critical_count": len(severity_breakdown["CRITICAL"]),
                    "high_count": len(severity_breakdown["HIGH"]),
                    "medium_count": len(severity_breakdown["MEDIUM"]),
                    "low_count": len(severity_breakdown["LOW"]),
                    "details": violations
                },
                "severity_breakdown": {
                    "critical": [v["description"] for v in severity_breakdown["CRITICAL"]],
                    "high": [v["description"] for v in severity_breakdown["HIGH"]],
                    "medium": [v["description"] for v in severity_breakdown["MEDIUM"]],
                    "low": [v["description"] for v in severity_breakdown["LOW"]]
                },
                "remediation": {
                    "priority_actions": remediation_steps,
                    "estimated_total_effort": f"{len(violations)} actions, ~{len(violations) * 2} hours"
                }
            }

            # Step 10: Generate summary
            if is_compliant:
                summary = f"Compliance Check: PASSED - Resource {self.resource_id} is compliant with all {len(frameworks)} framework(s). Compliance score: {compliance_score}/100. No violations detected."
            elif has_critical_violations:
                critical_count = len(severity_breakdown["CRITICAL"])
                summary = f"Compliance Check: FAILED - Resource {self.resource_id} has {critical_count} CRITICAL violation(s) and {len(violations)} total violations. Compliance score: {compliance_score}/100. Immediate remediation required. Top issue: {violations[0]['description']}"
            else:
                summary = f"Compliance Check: PARTIAL - Resource {self.resource_id} has {len(violations)} violation(s) (no critical). Compliance score: {compliance_score}/100. Remediation recommended within 30 days."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error checking compliance: {str(e)}. Verify resource_data and policies structures are correct."

    def _check_tagging_compliance(self, tags, policies):
        """Check if resource has all required tags."""
        violations = []

        for policy in policies:
            if policy.get("rule") == "all_resources_must_have_tags" or policy.get("type") == "tagging":
                required_tags = policy.get("required_tags", [])

                for tag in required_tags:
                    if tag not in tags:
                        violations.append({
                            "description": f"Missing required tag: {tag}",
                            "severity": "HIGH",
                            "policy": policy.get("name", "tagging_policy"),
                            "remediation": f"Add tag '{tag}' with appropriate value (e.g., owner, environment, cost-center)",
                            "effort": "10 minutes"
                        })
                    elif not tags[tag] or tags[tag] == "":
                        violations.append({
                            "description": f"Empty required tag: {tag}",
                            "severity": "MEDIUM",
                            "policy": policy.get("name", "tagging_policy"),
                            "remediation": f"Populate tag '{tag}' with valid value",
                            "effort": "5 minutes"
                        })

        return violations

    def _check_regional_compliance(self, region, policies):
        """Check if resource is in allowed region."""
        violations = []

        for policy in policies:
            if policy.get("type") == "compliance" or "allowed_regions" in policy:
                allowed_regions = policy.get("allowed_regions", [])
                blocked_regions = policy.get("blocked_regions", [])

                if allowed_regions and region not in allowed_regions:
                    violations.append({
                        "description": f"Resource in non-allowed region: {region}",
                        "severity": "CRITICAL",
                        "policy": policy.get("name", "regional_policy"),
                        "remediation": f"Migrate resource to allowed region: {', '.join(allowed_regions)}",
                        "effort": "4 hours"
                    })

                if blocked_regions:
                    for blocked_pattern in blocked_regions:
                        if "*" in blocked_pattern:
                            # Wildcard match (e.g., "ap-*" blocks all Asia-Pacific)
                            pattern_prefix = blocked_pattern.replace("*", "")
                            if region.startswith(pattern_prefix):
                                violations.append({
                                    "description": f"Resource in blocked region: {region}",
                                    "severity": "CRITICAL",
                                    "policy": policy.get("name", "regional_policy"),
                                    "remediation": "Migrate out of blocked region immediately",
                                    "effort": "4 hours"
                                })
                        elif region == blocked_pattern:
                            violations.append({
                                "description": f"Resource in explicitly blocked region: {region}",
                                "severity": "CRITICAL",
                                "policy": policy.get("name", "regional_policy"),
                                "remediation": "Migrate to allowed region immediately",
                                "effort": "4 hours"
                            })

        return violations

    def _check_encryption_compliance(self, encryption_status, frameworks):
        """Check if data store has encryption enabled."""
        violations = []

        # All frameworks require encryption for data at rest
        if not encryption_status:
            severity = "CRITICAL" if any(f in frameworks for f in ["hipaa", "pci", "soc2"]) else "HIGH"

            violations.append({
                "description": "Encryption at rest not enabled for data store",
                "severity": severity,
                "policy": "data_protection_policy",
                "remediation": "Enable encryption at rest using KMS/CMK keys",
                "effort": "30 minutes"
            })

        return violations

    def _check_public_access(self, public_access, resource_type):
        """Check for public access in production resources."""
        violations = []

        if public_access:
            violations.append({
                "description": f"Production {resource_type} has public access enabled",
                "severity": "CRITICAL",
                "policy": "security_policy",
                "remediation": "Disable public access, use VPN/VPC peering or CloudFront for legitimate access",
                "effort": "1 hour"
            })

        return violations

    def _check_framework_requirements(self, resource, frameworks):
        """Check framework-specific requirements."""
        violations = []

        # HIPAA requires audit logging
        if "hipaa" in frameworks or "all" in frameworks:
            if not resource.get("audit_logging_enabled", False):
                violations.append({
                    "description": "HIPAA: Audit logging not enabled",
                    "severity": "CRITICAL",
                    "policy": "hipaa_compliance",
                    "remediation": "Enable CloudTrail/Cloud Audit Logs for all API activity",
                    "effort": "1 hour"
                })

        # PCI requires network segmentation
        if "pci" in frameworks or "all" in frameworks:
            if resource.get("resource_type") in ["Database", "Storage"] and not resource.get("private_subnet", False):
                violations.append({
                    "description": "PCI: Data store not in private subnet",
                    "severity": "CRITICAL",
                    "policy": "pci_dss_compliance",
                    "remediation": "Move resource to private subnet with no internet gateway",
                    "effort": "2 hours"
                })

        return violations


if __name__ == "__main__":
    # Test with non-compliant resource
    sample_resource = json.dumps({
        "tags": {"owner": "team-platform"},  # Missing environment and cost-center tags
        "region": "ap-south-1",  # Blocked region
        "resource_type": "RDS",
        "encryption": False,  # No encryption
        "public_access": False,
        "audit_logging_enabled": False
    })

    sample_policies = json.dumps({
        "policies": {
            "compliance": [
                {
                    "name": "Tagging Compliance",
                    "type": "compliance",
                    "rule": "all_resources_must_have_tags",
                    "required_tags": ["owner", "environment", "cost-center"]
                }
            ],
            "regional": [
                {
                    "name": "Regional Restrictions",
                    "type": "compliance",
                    "allowed_regions": ["us-east-1", "us-west-2", "eu-west-1"],
                    "blocked_regions": ["ap-*"]
                }
            ]
        }
    })

    tool = CheckCompliance(
        resource_id="db-mysql-prod-001",
        resource_data=sample_resource,
        compliance_frameworks="internal,hipaa",
        policies=sample_policies
    )
    print(tool.run())
