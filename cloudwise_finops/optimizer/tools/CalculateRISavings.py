from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class CalculateRISavings(BaseTool):
    """Calculate Reserved Instance and Savings Plans ROI by comparing on-demand costs against commitment pricing.

    Use this tool to analyze potential cost savings from purchasing Reserved Instances (AWS, Azure)
    or Committed Use Discounts/Savings Plans (GCP, AWS). The tool evaluates historical instance
    usage patterns, calculates optimal commitment levels (1-year or 3-year terms), estimates
    monthly and annual savings, and determines break-even points to support purchasing decisions.

    Do NOT use this tool for workloads with unpredictable usage patterns, short-lived projects
    (<6 months), or resources scheduled for migration/retirement. Reservations work best for
    steady-state production workloads with consistent utilization over the commitment period.

    Returns: JSON object with monthly_savings, annual_savings, break_even_months, recommended_term
    (1yr or 3yr), commitment_utilization_percent (how much of RI capacity will be used),
    upfront_cost, and risk_assessment (LOW/MEDIUM/HIGH based on usage volatility and term length).

    Savings calculations assume: 1-year RI saves ~30-40%, 3-year saves ~50-60% vs on-demand. GCP
    Committed Use Discounts save ~25-55%. Azure Reserved Instances save ~40-72%. Actual savings
    vary by instance family, region, and payment option (all-upfront, partial, no-upfront).
    """

    instance_type: str = Field(
        ...,
        description="Instance type/size to analyze for RI purchase (e.g., 'm5.2xlarge', 'n1-standard-4', 'Standard_D4s_v3'). Must be eligible for reservations."
    )
    region: str = Field(
        ...,
        description="Cloud region where instances run (e.g., 'us-east-1', 'us-central1', 'eastus'). RI pricing varies by region."
    )
    commitment_term: str = Field(
        ...,
        description="Commitment term length. Valid values: '1year' or '3year'. Longer terms offer higher discounts but greater commitment risk."
    )
    usage_hours: float = Field(
        ...,
        description="Average monthly usage hours for this instance type. Full utilization = 730 hours/month (24/7). Use historical data from last 3-6 months."
    )
    provider: str = Field(
        default="aws",
        description="Cloud provider. Valid values: 'aws', 'gcp', 'azure'. Determines pricing model (RI vs CUD vs Reservation) and discount rates."
    )

    def run(self):
        """Calculate RI/Savings Plan ROI and generate purchase recommendation."""
        # Step 1: Validate provider
        valid_providers = ["aws", "gcp", "azure"]
        if self.provider not in valid_providers:
            return f"Error: Invalid provider '{self.provider}'. Must be one of: {', '.join(valid_providers)}"

        # Step 2: Validate commitment term
        valid_terms = ["1year", "3year"]
        if self.commitment_term not in valid_terms:
            return f"Error: Invalid commitment_term '{self.commitment_term}'. Must be '1year' or '3year'."

        # Step 3: Validate usage_hours
        max_monthly_hours = 730  # 24 hours * ~30.4 days

        if self.usage_hours < 0:
            return "Error: usage_hours cannot be negative."

        if self.usage_hours > max_monthly_hours:
            # Cap usage_hours to maximum instead of returning early
            self.usage_hours = max_monthly_hours

        # Step 4: Calculate utilization percentage
        utilization_pct = (self.usage_hours / max_monthly_hours) * 100

        # Check if RI makes sense (typically need >40% utilization)
        if utilization_pct < 40:
            return f"Warning: Low utilization ({utilization_pct:.1f}%). Reserved Instances typically require >40% utilization for positive ROI. Consider on-demand or Savings Plans instead for flexibility."

        try:
            # Step 5: Get on-demand and RI pricing
            pricing = self._get_pricing(self.provider, self.instance_type, self.region, self.commitment_term)

            if not pricing:
                return f"Error: Pricing not available for {self.instance_type} in {self.region}. Verify instance type is valid and RI-eligible."

            hourly_ondemand = pricing["ondemand_hourly"]
            hourly_ri = pricing["ri_hourly"]
            upfront_cost = pricing["upfront_cost"]

            # Step 6: Calculate costs
            monthly_ondemand_cost = hourly_ondemand * self.usage_hours
            monthly_ri_cost = (hourly_ri * self.usage_hours) + (upfront_cost / (12 if self.commitment_term == "1year" else 36))

            monthly_savings = monthly_ondemand_cost - monthly_ri_cost
            annual_savings = monthly_savings * 12

            # Calculate savings percentage
            savings_pct = (monthly_savings / monthly_ondemand_cost * 100) if monthly_ondemand_cost > 0 else 0

            # Step 7: Calculate break-even point
            if monthly_savings > 0:
                break_even_months = upfront_cost / monthly_savings if monthly_savings > 0 else 999
            else:
                break_even_months = 999  # No break-even if not saving

            # Step 8: Determine recommendation
            if break_even_months <= 3:
                recommendation = "STRONGLY RECOMMENDED"
            elif break_even_months <= 6:
                recommendation = "RECOMMENDED"
            elif break_even_months <= 12:
                recommendation = "CONSIDER"
            else:
                recommendation = "NOT RECOMMENDED"

            # Step 9: Assess risk level
            risk_level = self._assess_ri_risk(
                utilization_pct,
                self.commitment_term,
                break_even_months
            )

            # Step 10: Generate alternative options
            alternatives = []

            if self.commitment_term == "3year" and risk_level in ["MEDIUM", "HIGH"]:
                alternatives.append("Consider 1-year term for lower commitment risk")

            if utilization_pct < 70:
                alternatives.append(f"Current utilization {utilization_pct:.1f}% - consider Savings Plans for flexibility")

            if self.provider == "aws" and upfront_cost > 0:
                alternatives.append("Evaluate no-upfront or partial-upfront payment options for lower initial cost")

            # Step 11: Build result
            result = {
                "instance_type": self.instance_type,
                "region": self.region,
                "provider": self.provider,
                "commitment_term": self.commitment_term,
                "recommendation": recommendation,
                "utilization": {
                    "monthly_usage_hours": self.usage_hours,
                    "max_monthly_hours": max_monthly_hours,
                    "utilization_percent": round(utilization_pct, 1)
                },
                "cost_comparison": {
                    "monthly_ondemand_cost": round(monthly_ondemand_cost, 2),
                    "monthly_ri_cost": round(monthly_ri_cost, 2),
                    "monthly_savings": round(monthly_savings, 2),
                    "annual_savings": round(annual_savings, 2),
                    "savings_percent": round(savings_pct, 1)
                },
                "financial_metrics": {
                    "upfront_cost": upfront_cost,
                    "break_even_months": round(break_even_months, 1),
                    "roi_12_months": round((annual_savings / upfront_cost * 100), 1) if upfront_cost > 0 else 0
                },
                "risk_assessment": {
                    "risk_level": risk_level,
                    "factors": self._get_risk_factors(utilization_pct, self.commitment_term)
                },
                "alternatives": alternatives
            }

            # Step 12: Generate summary
            term_display = "1-year" if self.commitment_term == "1year" else "3-year"

            if recommendation in ["STRONGLY RECOMMENDED", "RECOMMENDED"]:
                summary = f"RI Purchase Recommendation: {recommendation} - {term_display} reservation for {self.instance_type}. Monthly savings: ${monthly_savings:.2f} ({savings_pct:.1f}%). Annual savings: ${annual_savings:.2f}. Break-even: {break_even_months:.1f} months. Risk: {risk_level}."
            else:
                summary = f"RI Purchase Recommendation: {recommendation} - {term_display} reservation break-even is {break_even_months:.1f} months (target <12). Savings: ${monthly_savings:.2f}/month. Consider alternatives: {', '.join(alternatives) if alternatives else 'on-demand pricing'}."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error calculating RI savings: {str(e)}. Verify instance_type, region, and provider are valid."

    def _get_pricing(self, provider, instance_type, _region, term):
        """Get simplified pricing for on-demand and RI options."""
        # Simplified pricing (in production, query cloud provider pricing APIs)
        # Discount rates: 1yr RI ~35%, 3yr RI ~55% off on-demand

        base_pricing = {
            "aws": {
                "m5.2xlarge": {"ondemand_hourly": 0.384},
                "m5.xlarge": {"ondemand_hourly": 0.192},
                "t3.medium": {"ondemand_hourly": 0.0416},
            },
            "gcp": {
                "n1-standard-4": {"ondemand_hourly": 0.190},
                "n1-standard-2": {"ondemand_hourly": 0.095},
            },
            "azure": {
                "Standard_D4s_v3": {"ondemand_hourly": 0.192},
                "Standard_D2s_v3": {"ondemand_hourly": 0.096},
            }
        }

        base_price = base_pricing.get(provider, {}).get(instance_type)

        if not base_price:
            return None

        ondemand_hourly = base_price["ondemand_hourly"]

        # Calculate RI pricing based on term
        if term == "1year":
            discount_pct = 35
            upfront_cost = ondemand_hourly * 730 * 12 * 0.10  # ~10% upfront for partial prepayment
        else:  # 3year
            discount_pct = 55
            upfront_cost = ondemand_hourly * 730 * 36 * 0.15  # ~15% upfront for partial prepayment

        ri_hourly = ondemand_hourly * (1 - discount_pct / 100)

        return {
            "ondemand_hourly": ondemand_hourly,
            "ri_hourly": ri_hourly,
            "upfront_cost": round(upfront_cost, 2),
            "discount_percent": discount_pct
        }

    def _assess_ri_risk(self, utilization_pct, term, break_even_months):
        """Assess risk level of RI purchase."""
        risk_score = 0

        # Factor 1: Utilization
        if utilization_pct < 50:
            risk_score += 2
        elif utilization_pct < 70:
            risk_score += 1

        # Factor 2: Term length
        if term == "3year":
            risk_score += 2
        else:
            risk_score += 1

        # Factor 3: Break-even time
        if break_even_months > 12:
            risk_score += 2
        elif break_even_months > 6:
            risk_score += 1

        # Map score to risk level
        if risk_score <= 2:
            return "LOW"
        elif risk_score <= 4:
            return "MEDIUM"
        else:
            return "HIGH"

    def _get_risk_factors(self, utilization_pct, term):
        """Identify specific risk factors."""
        factors = []

        if utilization_pct < 70:
            factors.append(f"Utilization {utilization_pct:.1f}% - underutilization risk")

        if term == "3year":
            factors.append("3-year commitment limits flexibility for workload changes")

        if utilization_pct > 95:
            factors.append("Very high utilization - consider capacity buffer")

        if not factors:
            factors.append("Low risk - good RI candidate")

        return factors


if __name__ == "__main__":
    # Test with high-utilization scenario
    tool = CalculateRISavings(
        instance_type="m5.2xlarge",
        region="us-east-1",
        commitment_term="1year",
        usage_hours=700,  # 96% utilization
        provider="aws"
    )
    print(tool.run())
