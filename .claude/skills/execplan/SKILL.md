---
name: execplan
description: Create and maintain execution plans (ExecPlans) for complex features, refactors, or multi-milestone development work. Use when asked to plan significant coding tasks, design complex features, write implementation specifications, or when work involves multiple steps with unknowns that need de-risking. Triggers on phrases like "create an execplan", "write an execution plan", "plan this feature", "design this refactor", "specification for", or when the user explicitly references PLANS.md or the ExecPlan format. Ideal for long-running tasks that require careful planning and progress tracking.
---

# ExecPlan Skill

ExecPlans are self-contained design documents that enable any novice to implement a feature end-to-end without prior knowledge of the codebase. They are living documents maintained throughout development, specifically designed to support long-running autonomous coding tasks.

## Core Principles

**Self-contained**: Include all knowledge needed—no external references, no "as described previously". Define all terms inline.

**Outcome-focused**: Begin with why the work matters. What can someone do after this change? How can they see it working?

**Observable verification**: Acceptance = behavior a human can verify (HTTP 200 response, test passing), not internal attributes (added a struct).

**Living document**: Update Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective as work proceeds.

## When to Create an ExecPlan

- Complex multi-step features requiring hours of implementation
- Significant refactors touching multiple files/modules
- Work with challenging requirements or unknowns
- Prototyping to de-risk larger changes
- Any task benefiting from incremental, verifiable milestones
- Long-running autonomous coding sessions (3+ hours)
- Agency Swarm multi-agent system development

## Workflow

**Authoring**: Read references/skeleton.md for the complete template. Research thoroughly—read source files, understand existing patterns before writing.

**Implementing**: Proceed through milestones without prompting for next steps. Keep all sections current. Commit frequently. Resolve ambiguities autonomously and document in Decision Log.

**Discussing changes**: Record all decisions in Decision Log with rationale. ExecPlans should make it clear why any change was made.

## Writing Guidelines

**Plain prose over lists**: Use sentences and paragraphs. Checklists only in Progress section.

**Concrete specificity**: Name files with full repo-relative paths. Name functions, modules, types precisely. Show exact commands with working directory.

**Milestones tell a story**: Goal → work → result → proof. Each milestone independently verifiable.

**No nested code fences**: Use indentation (4 spaces) for code/commands within the ExecPlan.

## Required Living Sections

Every ExecPlan must maintain:

- **Progress**: Checkboxes with timestamps tracking granular steps
- **Surprises & Discoveries**: Unexpected behaviors, bugs, insights with evidence
- **Decision Log**: Every decision with rationale and date
- **Outcomes & Retrospective**: Summary at milestones or completion

## Format Rules

- Single markdown file (no nested triple-backtick fences)
- Two newlines after every heading
- Indented blocks (4 spaces) for code examples, commands, transcripts
- When saving ExecPlan as a .md file, omit the outer code fence
- Save to `EXECPLAN.md` or `PLANS.md` in project root

## Validation Checklist

Before considering an ExecPlan complete:

- A novice could implement this without asking questions
- All terms of art are defined inline
- Acceptance criteria are observable behaviors
- File paths are repo-relative and complete
- Commands include working directory and expected output
- Each milestone has clear verification steps
- Living sections are current and populated

## Integration with Agency Swarm Workflow

When creating ExecPlans for Agency Swarm agencies:

1. **Phase 1 (Research & Design)**
   - Document API research findings in Context section
   - Record PRD decisions in Decision Log
   - Track api-researcher and prd-creator progress

2. **Phase 2 (Parallel Creation)**
   - Track agent-creator and instructions-writer tasks
   - Document file creation in Progress with timestamps

3. **Phase 3 (Tools & Testing)**
   - Track tools-creator implementation
   - Document qa-tester results in Surprises & Discoveries
   - Record iteration decisions

## Template

See references/skeleton.md for the complete ExecPlan template structure with all required sections.
