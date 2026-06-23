# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

> **This is the single source of truth for AI-agent guidance.** Tool-specific files
> such as `CLAUDE.md` link here rather than duplicating content — please keep all
> guidance in this file and update it in the same commit as any related code change.

## Project Overview

This is `.github` — an **organization-level repository of reusable GitHub Actions
workflows, composite actions, and starter workflow templates**. Its centerpiece is a
**Gemini-CLI-powered automation** that reviews pull requests, runs a security pass, and
conditionally squash-merges them. There is no application to build here; everything in this
repo is consumed by *other* repositories via pinned references.

Because changes here drive automation that runs in other repositories, **correctness and
security matter far more than style.** A bad change can mis-merge or block PRs org-wide.

The only executable code in-repo is the Python test suite under `tests/`, which validates
the workflow templates and language-support matrix (run with `pytest`). Do **not** run
builds — there is no app build.

## Repository Layout

```
.github/
  workflows/
    reusable-gemini-dispatch.yml   # entry point: parse @gemini-cli command, fan out
    gemini-review.yml              # code-review pass + security pass (2 Gemini calls)
    gemini-merge.yml               # classify failures, optionally remediate, squash-merge
    reusable-ci.yml                # language dispatcher → ci-{npm,python,php,java}.yml
    ci-npm.yml / ci-python.yml / ci-php.yml / ci-java.yml   # per-language CI
    reusable-security-scan.yml     # dependency audit + optional CodeQL
  commands/
    gemini-review.toml             # the review prompt
    gemini-merge.toml              # the review-and-merge prompt (encodes merge policy)
  copilot-instructions.md          # review guidance for AI reviewers of THIS repo
actions/
  setup-node-env/ setup-python-env/ setup-php-env/ setup-java-env/   # composite actions
workflow-templates/                # starter workflows (ci, security-scan) + *.properties.json
tests/                             # pytest suite validating templates + language support
docs/ARCHITECTURE.md               # deep-dive on every workflow/action (see below)
GEMINI.md                          # links to AGENTS.md (single source of truth)
README.md / QUICKSTART.md / CONTRIBUTING.md / examples/
```

## Architecture Overview / Workflow Catalog

The full per-workflow, per-action, per-input catalog lives in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — read it before changing any workflow,
prompt, composite action, or template. The summary below is enough for orientation.

### Reusable Workflows & Composite Actions (what each does)

**Gemini automation** (`reusable-gemini-dispatch.yml` → `gemini-review.yml` /
`gemini-merge.yml`, driven by `.github/commands/*.toml`):

- **Dispatch** is the gatekeeper. It runs only for non-fork `pull_request` events, opened/
  reopened issues, and `@gemini-cli`-prefixed comments from an `OWNER`/`MEMBER`/
  `COLLABORATOR`. It derives a command (`review`, `review-and-merge`, `merge`,
  `fallthrough`, `unsupported-fork`), resolves the PR head ref, and computes `is_fork`
  **failing closed** (fork PRs are unsupported and never receive secrets). Dependabot PRs
  map to `review-and-merge`.
  - Inputs: `projects` (required JSON string), `ref` (optional).
  - Secrets: `GEMINI_API_KEY` (required), `CALLER_GITHUB_TOKEN` (required).
- **Review** runs two *separate* Gemini invocations in one job: a code-review pass
  (code-review extension, GitHub MCP `v0.27.0`) and a security pass (security extension,
  GitHub MCP `v0.18.0`, `/security:analyze-github-pr`). They must stay separate —
  loading both extensions in one invocation causes tool-registration collisions. Their
  outputs are folded into one `review_summary`.
- **Merge** classifies each CI/security failure, may apply+push a low-risk remediation to
  the PR's source branch, then squash-merges — subject to the merge policy below. A
  post-run gate verifies the run left a **durable** outcome (actually merged, or actually
  submitted a new decisive review), comparing against a pre-run snapshot of review IDs.
- Repo-vars consulted: `APP_ID`/`APP_PRIVATE_KEY` (GitHub App identity),
  `GEMINI_*_MODEL`/`GEMINI_MODEL`, `GEMINI_CLI_VERSION`, `GEMINI_DEBUG`,
  `UPLOAD_ARTIFACTS`, and the GCP/Vertex vars (`GOOGLE_CLOUD_*`, `GCP_WIF_PROVIDER`,
  `SERVICE_ACCOUNT_EMAIL`, `GOOGLE_GENAI_USE_*`).

**`reusable-ci.yml`** — dispatches on `language` (javascript/python/php/java) to a
per-language sub-workflow; exposes a single `outcome` output. Key inputs: `language`*,
`language-version`*, `working-directory`, `extensions` (PHP extensions / Java apt
packages), `run-lint`/`run-test`/`run-build`, `build-before-test` (JS), `ref`. Optional
`CUSTOM_TOKEN` secret (JS private packages).

**`reusable-security-scan.yml`** — dependency audit per language (`npm audit`,
`pip-audit`, `composer audit --locked`, Trivy for Java) plus optional CodeQL
(`scan-code`). Runs independently of CI and against untrusted refs, so it never builds the
project. Exposes an `outcome` output.

**Composite actions** (`actions/<name>@vX.Y.Z`) — `setup-node-env`, `setup-python-env`,
`setup-php-env`, `setup-java-env`: set up the toolchain with caching and best-effort
dependency install. `setup-java-env` auto-detects Maven/Gradle and outputs `build-tool`.

## How Downstream Repos Consume These

Downstream repos reference this repo by **pinned release tag**:

```yaml
# Reusable workflow (note the doubled .github/.github path)
uses: zmihai/.github/.github/workflows/reusable-ci.yml@vX.Y.Z
# Composite action
uses: zmihai/.github/actions/setup-node-env@vX.Y.Z
```

To wire up the Gemini automation, a downstream repo runs `reusable-ci.yml` and
`reusable-security-scan.yml` per project, aggregates their `outcome`s into a `projects`
JSON array (`working-directory`, `language`, `language-version`, `ci-outcome`,
`scan-outcome` per project), and passes it to the Gemini workflows with `secrets: inherit`.
See `README.md` / `QUICKSTART.md` / `examples/` for full caller examples.

**Operational practice:** run the review/merge workflows **one PR at a time** to avoid
merge conflicts. The merge workflow has a `concurrency` group enforcing a single merge in
flight.

## Versioning & Release

- The repo is released as semver tags. All in-repo `@vX.Y.Z` references (README, templates, and the
  `zmihai/.github/...` refs inside the workflows) point at that same tag.
- **A release is not just a tag.** Cutting a new version requires sweeping every in-repo
  `@vX.Y.Z` reference to the new tag — the per-language CI workflows and the security-scan
  workflow reference the composite actions as `zmihai/.github/actions/...@vX.Y.Z`, and the
  README/templates contain many `@vX.Y.Z` examples. Bump them all in the release commit,
  then tag.
- **Workflow templates are served from the default branch, not a tag** — edits to
  `workflow-templates/` take effect immediately without a release. (The `uses:` lines
  *inside* the templates still carry a pinned tag that must be bumped on release.)
- Nested third-party actions are pinned by **commit SHA** with a `# ratchet:` comment
  naming the version. Keep that pattern; don't replace SHAs with floating tags.

## AI-Agent / Automation Conventions & Gotchas

These are durable rules, several learned the hard way. Verify against the current source
before relying on them.

**Remotes & branching:**

- **`git fetch` and reconcile against upstream before committing.** Dependabot churn
  makes stale local copies costly to rebase later.
- If a branch's upstream shows `[gone]`, it was almost certainly squash-merged — switch to
  `master` and delete the dead branch.

**Gemini / merge automation:**

- **`gemini-flash-latest` is a deliberate, capable choice** (resolves to Flash 3.5). Do
  not treat it as weak or propose "upgrading" it. Model selection is `GEMINI_*_MODEL` →
  `GEMINI_MODEL` → `gemini-flash-latest`.
- **Keep `GEMINI_DEBUG` `false`/unset.** Debug-on emits multi-MB stderr that exceeds GitHub
  Actions' template object-size limit and fails the job. For observability use
  `UPLOAD_ARTIFACTS=true` (uploads `stdout.log`/`stderr.log`/`telemetry.log`) — note that
  **MCP tool calls appear only in `telemetry.log`, not `stdout.log`**.
- **`GEMINI_CLI_VERSION` defaults to a pinned `0.46.0`, not floating `latest`** — newer CLI
  releases tightened env/MCP permissions and need prompt/action updates first.
- **`tools.core` must list the MCP tools by their `mcp_github_*` FQNs** for the GitHub MCP
  tools to reach the model (it acts as a global allowlist that also filters MCP tools).
- **The security pass needs UNSCOPED `run_shell_command`** in `settings.tools.core` — it
  runs `git diff` etc. A scoped allowlist (cat/echo/grep/…) makes every git command
  "denied by policy" and fails the step.
- **Merge mechanism:** merge via the MCP `merge_pull_request` tool, falling back to
  `gh pr merge <n> --squash` (token from env). **Never** `curl` with a token in argv (it
  leaks into telemetry), and **never** push/merge to the default branch — remediation fixes
  go to the **PR's source branch** (`head_ref`).
- **Merge safety policy (the current "v0.9.0" posture):** classify each failure
  **related** vs **unrelated/pre-existing** (when in doubt → related); related failures
  must pass or be remediated, unrelated pre-existing failures (including security) do not
  block; any **🔴 Critical / 🟠 High** review or security finding → **REQUEST_CHANGES**
  (block, never auto-merge). A "remediate-then-merge everything" variant was tried and
  **rolled back** because it merged an unfixed Critical — do not re-enable a posture that
  auto-merges past a Critical without a confirm-fix-on-remote guard.

**Gemini prompt-authoring & sandbox conventions:**

- **GitHub MCP Tool Naming:** Use the exact **`mcp_github_*`-prefixed** tool names in prompt templates (e.g., `mcp_github_pull_request_review_write`). Bare names are wrong.
- **Parsing JSON Arrays with `jq`:** Inject JSON-array variables (like `PROJECTS`) into `.gemini/context.json` with `jq --argjson` instead of `--arg` (which stringifies it and breaks array-typed schemas).
- **YOLO Mode Tool Policy:** To allow unrestricted shell execution in YOLO mode, specify `"run_shell_command"` with **no** arguments (specifying an argument like `"run_shell_command(echo)"` restricts execution only to that command).

**Reusable security scan & dependency auditing rules:**

- **No Build on Untrusted PRs:** Workflows or steps triggered on untrusted PR refs (such as dependency scans) must **never build the project, run installer scripts, or trigger build hooks** (e.g., running `pip install .` on a custom `setup.py`/`pyproject.toml` or compiling Java projects during audit jobs). This prevents untrusted PRs from executing arbitrary code on our runners.
- **Static Lockfile/Manifest Auditing:** Perform dependency audits on static, pre-existing lockfiles or generate them using strictly read-only, non-resolving commands (such as `uv export --frozen --no-emit-project --no-hashes`).
- **Conditional Tool Installation:** Install auxiliary scanning tools (such as `uv`) conditionally inside workflows (e.g., only if `uv.lock` is present in the working directory). Do not install them unconditionally to avoid unnecessary package-download runtime, dependency overhead, and supply-chain security surface area to repositories that do not use them.

**Inline PR review & comment management via `gh` CLI:**

- When requested to check inline PR review comments or reply to them, use the GitHub REST API via the `gh` CLI for direct and accurate interaction:
  * **Fetch all inline comments:**
    ```bash
    gh api repos/{owner}/{repo}/pulls/{pull_number}/comments
    ```
  * **Reply to an inline comment thread:**
    ```bash
    gh api --method POST -H "Accept: application/vnd.github+json" \
      /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies \
      -f body="Your reply text"
    ```
    *(Note: Use single quotes for inner strings in PowerShell to avoid escaping issues).*

**Reviewing PRs against this repo** (see `.github/copilot-instructions.md`):

- Be comprehensive on the first pass; prioritize correctness/security over style.
- **Respect intentional patterns:** SHA-pinned actions with `# ratchet:` comments and
  deliberately quoted workflow expressions are intentional — do not flag them.
- Review merge-automation changes against the **related/unrelated** policy, not an "all
  checks must pass" assumption. The durable-outcome gate intentionally fails closed and
  detects this run's outcome by snapshotting review IDs (not timestamps).

## Key Files Reference

- `.github/workflows/reusable-gemini-dispatch.yml` — entry point / command router.
- `.github/workflows/gemini-review.yml` — code-review + security passes; builds `review_summary`.
- `.github/workflows/gemini-merge.yml` — merge policy execution + durable-outcome gate.
- `.github/commands/gemini-merge.toml` — the prompt encoding the merge/remediation policy.
- `.github/commands/gemini-review.toml` — the review prompt (severity levels, comment format).
- `.github/workflows/reusable-ci.yml` + `ci-{npm,python,php,java}.yml` — reusable CI.
- `.github/workflows/reusable-security-scan.yml` — dependency audits + CodeQL.
- `actions/setup-{node,python,php,java}-env/action.yml` — composite setup actions.
- `workflow-templates/` — starter workflows + `*.properties.json` auto-suggestion patterns.
- `tests/` — pytest suite validating templates and language support.
- `GEMINI.md` — links to `AGENTS.md` as the single source of truth.
- `.github/copilot-instructions.md` — review guidance for AI reviewers of this repo.
- `README.md` / `QUICKSTART.md` — downstream consumption examples and full input/secret docs.
- `docs/ARCHITECTURE.md` — the full deep-dive catalog.
