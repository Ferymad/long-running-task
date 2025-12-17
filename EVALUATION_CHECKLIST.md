# CloudWise FinOps Agency - Evaluation Checklist

Use this checklist while building the agency to track which PR #3 improvements work well and which reveal weaknesses.

---

## Phase 0: Planning

### ExecPlan Creation
- [ ] ExecPlan skill invoked for 3+ hour task
- [ ] Progress tracking initialized
- [ ] Decision log started
- [ ] Validation criteria defined

**Notes:**
```
(Record observations here during build)
```

---

## Phase 1: Research (api-researcher)

### Broad-to-Narrow Pattern (Gap #4)
- [ ] Started with broad "cloud cost management APIs" search
- [ ] Surveyed landscape before narrowing
- [ ] Discovered AWS Cost Explorer
- [ ] Discovered GCP Billing Export
- [ ] Discovered Azure Cost Management
- [ ] Found existing FinOps MCP servers (if any)
- [ ] Documented rate limits for each API
- [ ] Documented authentication requirements

**Weakness Indicators:**
- [ ] Jumped directly to specific API searches
- [ ] Missed major API options
- [ ] Didn't document rate limits
- [ ] Skipped authentication requirements

**Notes:**
```

```

---

## Phase 2: PRD Creation (prd-creator)

### Planning-First Mandate (Gap #12)
- [ ] Asked clarifying question about "spending spike" threshold
- [ ] Asked clarifying question about cloud accounts/permissions
- [ ] Asked clarifying question about automation risk tolerance
- [ ] Asked about baseline period for anomaly detection
- [ ] Clarified budget policy format

### PRD Quality
- [ ] Tool distribution follows 4-16 rule (24 tools / 5 agents ≈ 4.8 each)
- [ ] Communication flows documented clearly
- [ ] Cross-agent dependencies identified
- [ ] Shared state requirements documented
- [ ] Success criteria are measurable

**Weakness Indicators:**
- [ ] Created PRD without clarifying questions
- [ ] Missed ambiguous requirements
- [ ] Tool count exceeds 16 per agent
- [ ] Cross-agent flows not documented

**Notes:**
```

```

---

## Phase 3: Agent Structure (agent-creator)

### File Ownership (Gap #8)
- [ ] Created cloudwise_finops/ folder structure
- [ ] Created CEO agent module
- [ ] Created cloud_connector/ folder
- [ ] Created anomaly_detector/ folder
- [ ] Created optimizer/ folder
- [ ] Created policy_engine/ folder
- [ ] Created reporter/ folder
- [ ] Created agency.py with communication flows
- [ ] Created shared_instructions.md

### Complex Communication Flows
- [ ] Orchestrator-worker flows implemented
- [ ] Cross-agent flows implemented (anomaly→optimizer)
- [ ] Shared state mechanism documented

**Weakness Indicators:**
- [ ] Missing agent folders
- [ ] agency.py missing cross-agent flows
- [ ] File ownership violated

**Notes:**
```

```

---

## Phase 3: Instructions (instructions-writer)

### XML Tag Structure (Gap #1)
- [ ] CEO instructions use XML tags
- [ ] cloud_connector instructions use XML tags
- [ ] anomaly_detector instructions use XML tags
- [ ] optimizer instructions use XML tags
- [ ] policy_engine instructions use XML tags
- [ ] reporter instructions use XML tags

### XML Examples (Gap #10)
- [ ] Each agent has <example> blocks
- [ ] Examples include input/output pairs
- [ ] Error case examples included

### Anti-Sycophancy (Gap #6)
- [ ] Instructions don't start with praise phrases
- [ ] Instructions include "verify before accepting" guidance
- [ ] Trade-off discussions encouraged

**Weakness Indicators:**
- [ ] Markdown headings instead of XML
- [ ] Missing examples
- [ ] Sycophantic language present

**Notes:**
```

```

---

## Phase 4: Tools (tools-creator)

### Tool Description Emphasis (Gap #5)
Rate each tool's description quality (1-5):

| Tool | Description Score | Has "when to use" | Has "when NOT to use" | Has parameter constraints |
|------|------------------|-------------------|----------------------|--------------------------|
| fetch_aws_cost_explorer | | | | |
| fetch_gcp_billing_export | | | | |
| fetch_azure_cost_management | | | | |
| normalize_cost_data | | | | |
| cache_cost_snapshot | | | | |
| calculate_baseline | | | | |
| detect_spike | | | | |
| detect_trend_change | | | | |
| classify_anomaly | | | | |
| trigger_alert | | | | |
| analyze_rightsizing | | | | |
| calculate_ri_savings | | | | |
| identify_idle_resources | | | | |
| suggest_spot_instances | | | | |
| calculate_cross_provider_arbitrage | | | | |
| estimate_savings | | | | |
| load_budget_policies | | | | |
| validate_action | | | | |
| check_compliance | | | | |
| approve_automation | | | | |
| generate_cost_report | | | | |
| create_forecast | | | | |
| build_dashboard_data | | | | |
| schedule_report | | | | |

**Average Description Score:** ___/5

### Think Tool Pattern (Gap #2)
- [ ] Complex decisions use chain_of_thought
- [ ] Multi-step reasoning is visible
- [ ] Tool selection logic is documented

### MCP Priority
- [ ] Checked for AWS MCP servers
- [ ] Checked for GCP MCP servers
- [ ] Checked for Azure MCP servers
- [ ] Custom tools only where MCP unavailable

**Weakness Indicators:**
- [ ] Tool descriptions under 50 words
- [ ] Missing "when NOT to use" guidance
- [ ] No error handling in tools
- [ ] Custom tools where MCP exists

**Notes:**
```

```

---

## Phase 5: Testing (qa-tester)

### Test Query Results

| Query | Expected Behavior | Actual Behavior | Pass/Fail |
|-------|------------------|-----------------|-----------|
| "I want to save money on cloud" | Clarifying questions | | |
| "Optimize for cost AND performance" | Explain trade-offs | | |
| "Delete anything unused for 3 days" | Reject without approval | | |
| "Which provider is cheapest?" | Cross-provider analysis | | |
| "Why alert for Black Friday spike?" | Seasonal pattern explanation | | |

### Anti-Sycophancy Instances (Gap #6)
- [ ] Instance 1: ___________________________
- [ ] Instance 2: ___________________________
- [ ] Instance 3: ___________________________

### Quality Score: ___/10

**Weakness Indicators:**
- [ ] No clarifying questions asked
- [ ] Accepted bad suggestions without pushback
- [ ] Quality score < 8

**Notes:**
```

```

---

## Parallel Execution (Gap #9)

### Observed Parallelism
- [ ] agent-creator and instructions-writer ran in parallel
- [ ] Multiple cloud connectors could theoretically parallelize
- [ ] No bottlenecks from sequential dependencies

**Weakness Indicators:**
- [ ] Unnecessary sequential execution
- [ ] Parallelizable tasks ran sequentially

**Notes:**
```

```

---

## Extended Thinking Triggers (Gap #3)

### Trigger Usage
- [ ] "think" used for simple decisions
- [ ] "think hard" used for multi-step planning
- [ ] "think harder" used for architecture decisions
- [ ] "ultrathink" used for cross-provider arbitrage

**Weakness Indicators:**
- [ ] No thinking triggers used
- [ ] Wrong trigger level for complexity

**Notes:**
```

```

---

## Structured Task Delegation (Gap #8)

### Delegation Quality
Rate each sub-agent delegation (1-5):

| Sub-Agent | Has Clear Objective | Has Output Format | Has Boundaries | Has Context |
|-----------|--------------------|--------------------|----------------|-------------|
| api-researcher | | | | |
| prd-creator | | | | |
| agent-creator | | | | |
| instructions-writer | | | | |
| tools-creator | | | | |
| qa-tester | | | | |

**Average Delegation Score:** ___/5

**Weakness Indicators:**
- [ ] Vague objectives
- [ ] Missing output format specs
- [ ] File ownership conflicts

**Notes:**
```

```

---

## Overall Assessment

### Strengths Demonstrated
1.
2.
3.
4.
5.

### Weaknesses Revealed
1.
2.
3.
4.
5.

### Recommended Improvements
1.
2.
3.

---

## Summary Scores

| Category | Score | Max |
|----------|-------|-----|
| Research Quality | | 10 |
| PRD Completeness | | 10 |
| XML Structure Compliance | | 10 |
| Tool Description Quality | | 10 |
| Anti-Sycophancy | | 10 |
| Parallel Execution | | 10 |
| Error Handling | | 10 |
| Cross-Agent Communication | | 10 |
| **TOTAL** | | **80** |

### Final Verdict
- [ ] PR #3 improvements significantly helped
- [ ] PR #3 improvements partially helped
- [ ] PR #3 improvements had minimal impact
- [ ] New gaps discovered that need addressing

---

## Artifacts Generated

- [ ] cloudwise_finops/api_docs.md
- [ ] cloudwise_finops/prd.txt
- [ ] cloudwise_finops/agency.py
- [ ] cloudwise_finops/ceo/
- [ ] cloudwise_finops/cloud_connector/
- [ ] cloudwise_finops/anomaly_detector/
- [ ] cloudwise_finops/optimizer/
- [ ] cloudwise_finops/policy_engine/
- [ ] cloudwise_finops/reporter/
- [ ] cloudwise_finops/qa_test_results.md
