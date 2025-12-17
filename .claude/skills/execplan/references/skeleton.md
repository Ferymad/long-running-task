# ExecPlan Skeleton Template

Use this template when creating a new ExecPlan. Copy the structure below and fill in each section.

## Template

    # <Short, action-oriented description>

    This ExecPlan is a living document. The sections Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective must be kept up to date as work proceeds.

    If PLANS.md file is checked into the repo, reference the path here and note that this document must be maintained in accordance with PLANS.md.


    ## Purpose / Big Picture

    Explain in a few sentences what someone gains after this change and how they can see it working. State the user-visible behavior you will enable.


    ## Progress

    Use a list with checkboxes to summarize granular steps. Every stopping point must be documented here, even if it requires splitting a partially completed task into two ("done" vs. "remaining"). This section must always reflect the actual current state of the work.

    - [x] (2025-10-01 13:00Z) Example completed step.
    - [ ] Example incomplete step.
    - [ ] Example partially completed step (completed: X; remaining: Y).

    Use timestamps to measure rates of progress.


    ## Surprises & Discoveries

    Document unexpected behaviors, bugs, optimizations, or insights discovered during implementation. Provide concise evidence.

    - Observation: ...
      Evidence: ...


    ## Decision Log

    Record every decision made while working on the plan in the format:

    - Decision: ...
      Rationale: ...
      Date/Author: ...


    ## Outcomes & Retrospective

    Summarize outcomes, gaps, and lessons learned at major milestones or at completion. Compare the result against the original purpose.


    ## Context and Orientation

    Describe the current state relevant to this task as if the reader knows nothing. Name the key files and modules by full path. Define any non-obvious term you will use. Do not refer to prior plans.


    ## Plan of Work

    Describe, in prose, the sequence of edits and additions. For each edit, name the file and location (function, module) and what to insert or change. Keep it concrete and minimal.


    ## Concrete Steps

    State the exact commands to run and where to run them (working directory). When a command generates output, show a short expected transcript so the reader can compare. This section must be updated as work proceeds.


    ## Validation and Acceptance

    Describe how to start or exercise the system and what to observe. Phrase acceptance as behavior, with specific inputs and outputs. If tests are involved, say "run <project's test command> and expect <N> passed; the new test <name> fails before the change and passes after".


    ## Idempotence and Recovery

    If steps can be repeated safely, say so. If a step is risky, provide a safe retry or rollback path. Keep the environment clean after completion.


    ## Artifacts and Notes

    Include the most important transcripts, diffs, or snippets as indented examples. Keep them concise and focused on what proves success.


    ## Interfaces and Dependencies

    Be prescriptive. Name the libraries, modules, and services to use and why. Specify the types, traits/interfaces, and function signatures that must exist at the end of the milestone. Prefer stable names and paths such as crate::module::function or package.submodule.Interface.

    Example format:

        In crates/foo/planner.rs, define:

            pub trait Planner {
                fn plan(&self, observed: &Observed) -> Vec<Action>;
            }


## Section Writing Guidelines

### Purpose / Big Picture
Answer: Why does this work matter? What can users do after that they couldn't before? Keep it to 2-4 sentences focused on user-visible outcomes.

### Context and Orientation
Treat the reader as having only the working tree and this ExecPlan. Name every relevant file with full paths. Define every term of art. If you mention "the config system", explain what files comprise it and how they interact.

### Plan of Work
Use prose, not bullets. Walk through the logical sequence: "First, we add X to file Y. This enables Z. Then we modify A in file B to consume X." Name functions and modules precisely.

### Concrete Steps
Be executable. Show working directory, exact command, expected output. Example:

    From repository root:

        cargo test --package mypackage

    Expected output:

        running 3 tests
        test tests::new_feature ... ok
        test tests::existing_feature ... ok
        test tests::edge_case ... ok

        test result: ok. 3 passed; 0 failed

### Validation and Acceptance
Frame as observable behavior:
- "Navigate to http://localhost:8080/health and receive HTTP 200 with body OK"
- "Run `make test` and see 'test_new_feature ... PASSED'"
- "After running the migration, query `SELECT count(*) FROM users` returns 1000"

### Milestones
When breaking work into milestones, each must be:
- Independently verifiable (has its own acceptance criteria)
- Incrementally valuable (produces working behavior, not just code)
- Self-contained (reader can understand scope without reading other milestones)

Introduce each milestone with: scope, what exists at the end, commands to run, expected observations.


## Common Anti-Patterns to Avoid

**Vague acceptance**: "The feature works correctly" -> Instead: "POST to /api/users returns 201 and the user appears in GET /api/users"

**Undefined jargon**: "Update the middleware" -> Instead: "In src/middleware/auth.rs, modify the validate_token function to accept expired tokens in debug mode"

**External references**: "See the API docs for details" -> Instead: Embed the relevant API details in the plan

**Letter-of-the-law completion**: Code compiles but doesn't do anything meaningful -> Always include end-to-end verification that proves the feature works

**Incomplete Progress tracking**: Only updating Progress at the start/end -> Update Progress at every stopping point, even mid-task


## Long-Running Task Integration

For tasks expected to run 3+ hours autonomously:

1. **Break into clear milestones** - Each milestone should be completable in 30-60 minutes
2. **Include checkpoint verification** - After each milestone, document how to verify progress
3. **Plan recovery paths** - If interrupted, the plan should allow resumption from any checkpoint
4. **Track time estimates vs actuals** - In Progress section, note estimated vs actual time for future planning
5. **Document blockers immediately** - Any unexpected issue goes in Surprises & Discoveries with timestamp
