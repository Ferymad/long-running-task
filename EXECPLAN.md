# Align Claude Agents with Workflow.mdc

This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.


## Purpose / Big Picture

The `.claude/agents/` folder contains 6 specialized agents for building Agency Swarm agencies. These agents have fallen behind the `workflow.mdc` specification which serves as the source of truth for the Agency Swarm v1.0.0 framework. After this change, all agents will use consistent imports, model versions, templates, and patterns that match the current workflow.mdc specification.


## Progress

- [x] (2025-12-17 00:00Z) Read and analyzed workflow.mdc (source of truth)
- [x] (2025-12-17 00:01Z) Read all 6 agent files in .claude/agents/
- [x] (2025-12-17 00:02Z) Identified misalignments and documented them
- [x] (2025-12-17 00:03Z) Update api-researcher.md - fixed WebSearchTool import to `from agency_swarm.tools import`
- [x] (2025-12-17 00:04Z) Update prd-creator.md - reviewed, no code templates needing updates
- [x] (2025-12-17 00:05Z) Update agent-creator.md - fixed imports, model to gpt-5.2, added Reasoning config, create_agency() pattern
- [x] (2025-12-17 00:06Z) Update tools-creator.md - fixed MCP import to `from agents.mcp`, built-in tools, agent template
- [x] (2025-12-17 00:07Z) Update instructions-writer.md - reviewed, primarily template-based, consistent
- [x] (2025-12-17 00:08Z) Update qa-tester.md - fixed create_agency() pattern, get_response_sync() method
- [x] (2025-12-17 00:09Z) Update .claude/README.md - added key patterns section, aligned with workflow.mdc
- [ ] Commit and push changes


## Surprises & Discoveries

- Observation: The workflow.mdc uses `gpt-5.2` as the default model with `Reasoning` object for reasoning effort configuration
  Evidence: Line 126-127 in workflow.mdc shows `model="gpt-5.2"` and `reasoning=Reasoning(effort="medium", summary="auto")`

- Observation: MCP imports are inconsistent across agents
  Evidence: tools-creator uses `from agency_swarm.tools.mcp import MCPServerStdio` but workflow.mdc uses `from agents.mcp import MCPServerStdio`

- Observation: Built-in tools import path is wrong in multiple agents
  Evidence: api-researcher.md uses `from agents.tool import WebSearchTool` but workflow.mdc uses `from agency_swarm.tools import WebSearchTool`


## Decision Log

- Decision: Use workflow.mdc as the single source of truth for all updates
  Rationale: workflow.mdc is explicitly marked as the primary guide and contains the most up-to-date patterns
  Date/Author: 2025-12-17 / Claude

- Decision: Update model version to `gpt-5.2` across all agents
  Rationale: workflow.mdc line 125-126 specifies `gpt-5.2` as the default model
  Date/Author: 2025-12-17 / Claude

- Decision: Standardize imports based on workflow.mdc patterns
  Rationale: Consistency across agents prevents confusion and errors
  Date/Author: 2025-12-17 / Claude


## Outcomes & Retrospective

(To be filled after completion)


## Context and Orientation

The project is an "Agency Builder" - a system that uses specialized sub-agents to build production-ready Agency Swarm v1.0.0 agencies. Key files:

- `/home/user/long-running-task/CLAUDE.md` - Main orchestrator instructions
- `/home/user/long-running-task/.cursor/rules/workflow.mdc` - **Source of truth** for Agency Swarm patterns
- `/home/user/long-running-task/.claude/agents/` - Contains 6 agent definition files:
  - `api-researcher.md` - Researches MCP servers and APIs
  - `prd-creator.md` - Creates PRDs for agencies
  - `agent-creator.md` - Creates agent modules and folders
  - `tools-creator.md` - Implements tools (MCP preferred)
  - `instructions-writer.md` - Writes agent instructions
  - `qa-tester.md` - Tests agencies with queries
- `/home/user/long-running-task/.claude/README.md` - Summary of agents


## Plan of Work

### Identified Misalignments

1. **Model Version**: Agents use `gpt-4o` or `gpt-5`, workflow uses `gpt-5.2`
2. **Agent Template**: Missing `Reasoning` object configuration
3. **MCP Imports**: Inconsistent paths (`agency_swarm.tools.mcp` vs `agents.mcp`)
4. **Built-in Tools Import**: Wrong path (`agents.tool` vs `agency_swarm.tools`)
5. **Agency Template**: Missing `create_agency()` function pattern
6. **Testing Methods**: Wrong method name (`get_completion` vs `get_response_sync`)

### Update Strategy

For each agent file, we will:
1. Update model version references to `gpt-5.2`
2. Fix import statements to match workflow.mdc
3. Update code templates to include `Reasoning` configuration
4. Fix method names and patterns


## Concrete Steps

From repository root:

    # After making changes, verify syntax
    python3 -c "import ast; ast.parse(open('.claude/agents/api-researcher.md').read())" || echo "Not Python, skip"

    # Commit changes
    git add .claude/agents/ .claude/README.md EXECPLAN.md
    git commit -m "Align Claude agents with workflow.mdc specification"
    git push -u origin claude/align-agents-workflow-vwps7


## Validation and Acceptance

1. All agent files reference `gpt-5.2` as the default model
2. All MCP imports use `from agents.mcp import MCPServerStdio`
3. All built-in tool imports use `from agency_swarm.tools import WebSearchTool, ImageGenerationTool`
4. Agent templates include `ModelSettings` with `Reasoning` configuration
5. Agency template uses `create_agency()` function pattern
6. Test method uses `get_response_sync()` not `get_completion()`


## Idempotence and Recovery

All changes are to markdown files that define agent behavior. Changes can be safely repeated or reverted using git. No runtime state is affected.


## Artifacts and Notes

### Key Template Changes

**Before (agent-creator.md)**:
    from agents import ModelSettings
    from agency_swarm import Agent

    example_agent = Agent(
        name="AgentName",
        model_settings=ModelSettings(
            model="gpt-4o",
            temperature=0.5,
        ),
    )

**After (aligned with workflow.mdc)**:
    from agency_swarm import Agent, ModelSettings
    from openai.types.shared import Reasoning

    example_agent = Agent(
        name="AgentName",
        model="gpt-5.2",
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
        ),
    )


## Interfaces and Dependencies

The agents are Task tool subagent definitions used by Claude Code. They don't have runtime dependencies but must follow the patterns in workflow.mdc for consistency with the Agency Swarm v1.0.0 framework.
