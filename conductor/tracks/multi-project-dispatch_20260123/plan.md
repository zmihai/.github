# Implementation Plan: Multi-Project Support for Gemini Dispatcher

This plan outlines the steps to update the Gemini dispatch and merge workflows to support multiple projects within a single repository (monorepos).

## Phase 1: Update Dispatcher Input and Context
Update `reusable-gemini-dispatch.yml` to accept the new `projects` JSON input and propagate it.

- [x] Task: Update `.github/workflows/reusable-gemini-dispatch.yml` inputs
    - [ ] Add `projects` input (type: string, required: false, default: '[]').
    - [ ] Update `dispatch` job outputs to include `projects`.
    - [ ] Update `review` and `merge` job calls to pass the `projects` input.
- [x] Task: Update `.github/workflows/gemini-review.yml` to accept `projects`
    - [ ] Add `projects` input to `workflow_call`.
    - [ ] Update the Gemini CLI prompt to include the `projects` context.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Update Dispatcher Input and Context' (Protocol in workflow.md)

## Phase 2: Update Merge Workflow for Multi-Project Status
Refactor `gemini-merge.yml` to handle multiple project outcomes and the "missing" status.

- [x] Task: Update `.github/workflows/gemini-merge.yml` inputs and prompt
    - [ ] Add `projects` input to `workflow_call`.
    - [ ] Update the Gemini CLI prompt to pass the `projects` JSON string.
    - [ ] Ensure the prompt clearly explains that some projects may have `"missing"` outcomes.
- [x] Task: Conductor - User Manual Verification 'Phase 2: Update Merge Workflow for Multi-Project Status' (Protocol in workflow.md)

## Phase 3: Verification and Testing
Verify the changes using manual testing and simulated PR scenarios.

- [x] Task: Create a test PR with a mock `projects` JSON payload [fdbce78]
    - [ ] Verify that `reusable-gemini-dispatch` correctly passes the JSON to downstream workflows.
    - [ ] Verify that `gemini-review` and `gemini-merge` receive and process the multi-project context.
- [x] Task: Conductor - User Manual Verification 'Phase 3: Verification and Testing' (Protocol in workflow.md)
