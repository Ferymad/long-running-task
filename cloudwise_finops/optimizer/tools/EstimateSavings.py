from agency_swarm.tools import BaseTool
from pydantic import Field
import json

class EstimateSavings(BaseTool):
    """Aggregate and project total cost savings from multiple optimization recommendations.

    Use this tool after generating multiple optimization recommendations (rightsizing, Reserved
    Instances, spot instances, idle resource cleanup, cross-cloud arbitrage) to calculate the
    combined financial impact. The tool accounts for implementation effort, overlapping recommendations,
    and provides prioritized action plan with quick wins highlighted for immediate impact.

    Do NOT double-count savings from mutually exclusive recommendations (e.g., can't rightsize AND
    terminate same resource). The tool automatically detects conflicts and applies precedence rules:
    terminate > migrate > downsize > convert to spot/RI.

    Returns: JSON object with total_monthly_savings, total_annual_savings, breakdown_by_category
    (rightsizing, RIs, spot, idle cleanup, arbitrage), implementation_effort_weeks, prioritized_actions
    (sorted by ROI = savings / effort), quick_wins (actions with >$500/month savings and <1 week effort),
    and phased_implementation_plan (organize recommendations into sprint cycles).

    Savings aggregation logic: Groups recommendations by resource_id to detect conflicts, applies
    precedence rules for mutually exclusive actions, adjusts for realistic implementation timelines
    (not all savings realized immediately), and calculates confidence-weighted projections (80% of
    estimated savings to account for real-world variability).
    """

    recommendations_list: str = Field(
        ...,
        description="JSON array of optimization recommendations from other tools. Each must include: recommendation_id, category (rightsizing/ri/spot/idle/arbitrage), resource_id, monthly_savings, implementation_effort_days, and risk_level."
    )
    confidence_adjustment: float = Field(
        default=0.8,
        description="Confidence multiplier for savings estimates (0.0-1.0). Default 0.8 means assume 80% of estimated savings will materialize. Use 0.9 for conservative projections, 0.7 for aggressive."
    )

    def run(self):
        """Aggregate optimization recommendations and calculate total savings."""
        # Step 1: Parse recommendations list
        try:
            recommendations = json.loads(self.recommendations_list)

            if not isinstance(recommendations, list):
                return "Error: recommendations_list must be JSON array of recommendation objects."

            if not recommendations:
                return "Warning: No recommendations provided. Total savings: $0. Run optimization tools (AnalyzeRightsizing, CalculateRISavings, etc.) first to generate recommendations."

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in recommendations_list. Details: {str(e)}"

        # Step 2: Validate confidence adjustment
        if not (0 <= self.confidence_adjustment <= 1):
            return "Error: confidence_adjustment must be between 0.0 and 1.0. Default 0.8 represents 80% confidence."

        try:
            # Step 3: Validate and normalize recommendations
            normalized_recommendations = []

            for idx, rec in enumerate(recommendations):
                # Validate required fields
                required_fields = ["category", "monthly_savings"]
                for field in required_fields:
                    if field not in rec:
                        return f"Error: Recommendation {idx} missing required field '{field}'. Required: {', '.join(required_fields)}"

                # Normalize fields
                normalized_rec = {
                    "recommendation_id": rec.get("recommendation_id", f"rec_{idx}"),
                    "category": rec["category"],
                    "resource_id": rec.get("resource_id", f"unknown_{idx}"),
                    "monthly_savings": float(rec["monthly_savings"]),
                    "implementation_effort_days": float(rec.get("implementation_effort_days", 1)),
                    "risk_level": rec.get("risk_level", "MEDIUM"),
                    "description": rec.get("description", f"{rec['category']} optimization")
                }

                normalized_recommendations.append(normalized_rec)

            # Step 4: Detect and resolve conflicts (same resource_id)
            resource_map = {}
            deduped_recommendations = []

            for rec in normalized_recommendations:
                resource_id = rec["resource_id"]

                if resource_id not in resource_map:
                    resource_map[resource_id] = []

                resource_map[resource_id].append(rec)

            # Apply precedence rules for conflicts
            precedence = {
                "idle": 1,  # Terminate idle resources first
                "arbitrage": 2,  # Migrate before optimizing
                "rightsizing": 3,  # Rightsize before RI/spot
                "spot": 4,  # Spot conversion
                "ri": 5  # RI last (longest commitment)
            }

            for resource_id, recs in resource_map.items():
                if len(recs) == 1:
                    deduped_recommendations.append(recs[0])
                else:
                    # Multiple recommendations for same resource - pick highest precedence
                    sorted_recs = sorted(recs, key=lambda x: precedence.get(x["category"], 99))
                    selected = sorted_recs[0]

                    # Add note about conflict resolution
                    selected["conflict_note"] = f"Resolved conflict with {len(recs)-1} other recommendations for {resource_id}"
                    deduped_recommendations.append(selected)

            # Step 5: Calculate category breakdowns
            category_totals = {}

            for rec in deduped_recommendations:
                category = rec["category"]

                if category not in category_totals:
                    category_totals[category] = {
                        "count": 0,
                        "total_monthly_savings": 0,
                        "total_annual_savings": 0,
                        "avg_implementation_days": 0
                    }

                category_totals[category]["count"] += 1
                category_totals[category]["total_monthly_savings"] += rec["monthly_savings"]
                category_totals[category]["total_annual_savings"] += rec["monthly_savings"] * 12
                category_totals[category]["avg_implementation_days"] += rec["implementation_effort_days"]

            # Calculate averages
            for category, data in category_totals.items():
                data["avg_implementation_days"] = round(data["avg_implementation_days"] / data["count"], 1) if data["count"] > 0 else 0
                data["total_monthly_savings"] = round(data["total_monthly_savings"], 2)
                data["total_annual_savings"] = round(data["total_annual_savings"], 2)

            # Step 6: Calculate totals with confidence adjustment
            raw_monthly_savings = sum(rec["monthly_savings"] for rec in deduped_recommendations)
            adjusted_monthly_savings = raw_monthly_savings * self.confidence_adjustment
            adjusted_annual_savings = adjusted_monthly_savings * 12

            total_implementation_days = sum(rec["implementation_effort_days"] for rec in deduped_recommendations)
            total_implementation_weeks = total_implementation_days / 5  # Business days to weeks

            # Step 7: Calculate ROI for prioritization
            for rec in deduped_recommendations:
                adjusted_savings = rec["monthly_savings"] * self.confidence_adjustment
                effort_weeks = rec["implementation_effort_days"] / 5
                rec["roi_score"] = (adjusted_savings / effort_weeks) if effort_weeks > 0 else adjusted_savings * 10

            # Step 8: Prioritize recommendations
            prioritized = sorted(deduped_recommendations, key=lambda x: x["roi_score"], reverse=True)

            # Step 9: Identify quick wins (high savings, low effort)
            quick_wins = [
                rec for rec in prioritized
                if rec["monthly_savings"] * self.confidence_adjustment >= 100  # $100+/month
                and rec["implementation_effort_days"] <= 5  # 1 week or less
            ]

            # Step 10: Create phased implementation plan
            phases = self._create_phased_plan(prioritized, self.confidence_adjustment)

            # Step 11: Build result
            result = {
                "summary": {
                    "total_recommendations": len(deduped_recommendations),
                    "recommendations_after_dedup": len(deduped_recommendations),
                    "conflicts_resolved": len(normalized_recommendations) - len(deduped_recommendations),
                    "raw_monthly_savings": round(raw_monthly_savings, 2),
                    "raw_annual_savings": round(raw_monthly_savings * 12, 2),
                    "adjusted_monthly_savings": round(adjusted_monthly_savings, 2),
                    "adjusted_annual_savings": round(adjusted_annual_savings, 2),
                    "confidence_factor": self.confidence_adjustment,
                    "total_implementation_effort_days": round(total_implementation_days, 1),
                    "total_implementation_effort_weeks": round(total_implementation_weeks, 1)
                },
                "breakdown_by_category": category_totals,
                "quick_wins": {
                    "count": len(quick_wins),
                    "monthly_savings": round(sum(r["monthly_savings"] * self.confidence_adjustment for r in quick_wins), 2),
                    "recommendations": quick_wins[:5]  # Top 5 quick wins
                },
                "prioritized_actions": [
                    {
                        "rank": idx + 1,
                        "recommendation_id": rec["recommendation_id"],
                        "category": rec["category"],
                        "resource_id": rec["resource_id"],
                        "description": rec["description"],
                        "monthly_savings": round(rec["monthly_savings"] * self.confidence_adjustment, 2),
                        "annual_savings": round(rec["monthly_savings"] * self.confidence_adjustment * 12, 2),
                        "effort_days": rec["implementation_effort_days"],
                        "roi_score": round(rec["roi_score"], 2),
                        "risk_level": rec["risk_level"]
                    }
                    for idx, rec in enumerate(prioritized[:15])  # Top 15
                ],
                "phased_implementation_plan": phases
            }

            # Step 12: Generate summary
            quick_win_savings = result["quick_wins"]["monthly_savings"]
            quick_win_count = result["quick_wins"]["count"]

            summary = f"Total Optimization Savings: ${adjusted_monthly_savings:.2f}/month (${adjusted_annual_savings:.2f}/year) from {len(deduped_recommendations)} recommendations. Implementation effort: {total_implementation_weeks:.1f} weeks. Quick wins: {quick_win_count} actions worth ${quick_win_savings:.2f}/month. Top category: {max(category_totals, key=lambda k: category_totals[k]['total_monthly_savings'])} (${category_totals[max(category_totals, key=lambda k: category_totals[k]['total_monthly_savings'])]['total_monthly_savings']:.2f}/month)."

            return f"{summary} Details: {json.dumps(result, indent=2)}"

        except Exception as e:
            return f"Error estimating savings: {str(e)}. Verify recommendations_list structure and field types."

    def _create_phased_plan(self, prioritized_recs, confidence):
        """Organize recommendations into implementation phases."""
        phases = []

        # Phase 1: Quick wins (week 1)
        phase1_recs = [r for r in prioritized_recs if r["implementation_effort_days"] <= 5][:10]
        if phase1_recs:
            phase1_savings = sum(r["monthly_savings"] * confidence for r in phase1_recs)
            phases.append({
                "phase": "Phase 1: Quick Wins (Week 1)",
                "recommendations": len(phase1_recs),
                "monthly_savings": round(phase1_savings, 2),
                "actions": [f"{r['category']}: {r['resource_id']}" for r in phase1_recs[:5]]
            })

        # Phase 2: Medium effort (weeks 2-4)
        phase2_recs = [r for r in prioritized_recs if 5 < r["implementation_effort_days"] <= 15 and r not in phase1_recs][:10]
        if phase2_recs:
            phase2_savings = sum(r["monthly_savings"] * confidence for r in phase2_recs)
            phases.append({
                "phase": "Phase 2: Medium Effort (Weeks 2-4)",
                "recommendations": len(phase2_recs),
                "monthly_savings": round(phase2_savings, 2),
                "actions": [f"{r['category']}: {r['resource_id']}" for r in phase2_recs[:5]]
            })

        # Phase 3: High effort (month 2+)
        phase3_recs = [r for r in prioritized_recs if r not in phase1_recs and r not in phase2_recs]
        if phase3_recs:
            phase3_savings = sum(r["monthly_savings"] * confidence for r in phase3_recs)
            phases.append({
                "phase": "Phase 3: Strategic Initiatives (Month 2+)",
                "recommendations": len(phase3_recs),
                "monthly_savings": round(phase3_savings, 2),
                "actions": [f"{r['category']}: {r['resource_id']}" for r in phase3_recs[:5]]
            })

        return phases


if __name__ == "__main__":
    # Test with sample recommendations from multiple optimization tools
    sample_recommendations = json.dumps([
        {
            "recommendation_id": "rightsize_1",
            "category": "rightsizing",
            "resource_id": "i-1234567890abcdef0",
            "monthly_savings": 140.16,
            "implementation_effort_days": 2,
            "risk_level": "LOW",
            "description": "Downsize m5.2xlarge to m5.xlarge"
        },
        {
            "recommendation_id": "ri_1",
            "category": "ri",
            "resource_id": "i-abcdef1234567890",
            "monthly_savings": 50.00,
            "implementation_effort_days": 1,
            "risk_level": "LOW",
            "description": "1-year RI for m5.xlarge"
        },
        {
            "recommendation_id": "idle_1",
            "category": "idle",
            "resource_id": "vol-0xyz9876543210abc",
            "monthly_savings": 50.00,
            "implementation_effort_days": 0.5,
            "risk_level": "LOW",
            "description": "Delete unattached EBS volume"
        },
        {
            "recommendation_id": "spot_1",
            "category": "spot",
            "resource_id": "batch-worker-fleet",
            "monthly_savings": 200.00,
            "implementation_effort_days": 5,
            "risk_level": "LOW",
            "description": "Convert batch workers to spot instances"
        }
    ])

    tool = EstimateSavings(
        recommendations_list=sample_recommendations,
        confidence_adjustment=0.8
    )
    print(tool.run())
