# Architecture

Deep-dive reference for this project's reusable workflows and internals.
For day-to-day guidance and conventions, see [AGENTS.md](../AGENTS.md).

> This is reference material — read it when working on the relevant subsystem.
> Verify details against the source before relying on them; like any doc it can
> drift from the code.

This repo is `.github` — an organization-level repository of **reusable GitHub
Actions workflows**, **composite actions**, **starter workflow templates**, and a
**Gemini-CLI-powered PR review/merge automation**. Other repositories consume it via
references; nothing here builds an app of its own.

---

## 1. Gemini automation (the heart of the repo)

The Gemini automation reviews PRs, runs a security pass, and conditionally squash-merges,
all driven by the Gemini CLI (`google-github-actions/run-gemini-cli`) running the GitHub
MCP server. There are four workflows plus two prompt files:

```
reusable-gemini-guard.yml      ── trigger policy + command/ref/fork resolution (shared gate)
reusable-gemini-dispatch.yml   ── entry point; runs the guard, fans out
   ├─> reusable-gemini-guard.yml (internal)
   ├─> gemini-review.yml        ── code-review pass + security pass (2 Gemini invocations)
   └─> gemini-merge.yml         ── classify failures, optionally remediate, squash-merge

.github/commands/gemini-review.toml   ── the review prompt (loaded via /gemini-review)
.github/commands/gemini-merge.toml    ── the review-and-merge prompt (loaded via /gemini-merge)
```

### 1.0 `reusable-gemini-guard.yml` — the shared gate

The single source of truth for the trigger policy, extracted from the dispatch so
downstream callers can run the **exact same gate before their own CI jobs** (which check
out code and receive secrets). A single `github-script` job:

- **Trigger policy** (`proceed` output): allows non-fork `pull_request` events; `issues`
  opened/reopened; and comments/reviews/issue-bodies that **start with `@gemini-cli`**
  *and* come from an `OWNER`/`MEMBER`/`COLLABORATOR` human user (`sender.type == 'User'`).
  When the policy rejects the event, the job short-circuits: no ref lookup, `is_fork`
  reported `'true'` (fail closed).
- Resolves a **command**: `pull_request` events → `review` (or `review-and-merge` when
  the actor is `dependabot[bot]`); `@gemini-cli /review` → `review`,
  `@gemini-cli /review-and-merge` → `review-and-merge`, `@gemini-cli /merge` → `merge`;
  otherwise `fallthrough`. `@gemini-cli` commands are honored **only from authorized
  human authors for every event type** — including issue bodies, which pass the trigger
  policy without an association check (the old dispatch gate only checked association on
  the comment/review branch, so a command in a new issue's body ran unauthenticated).
- Resolves the **ref** (`resolved_ref`): the `ref` input if given, else the PR head SHA —
  looked up via the API for `issue_comment` events, whose payload carries **no** PR head
  SHA (without this a caller-side build silently builds the default branch).
- Computes **`is_fork`**, **failing closed** (`is_fork='true'`) if the PR lookup throws,
  to avoid leaking secrets to forks. A fork + real command becomes `unsupported-fork`.
- Reports **`is_pr`** so callers can skip build jobs on plain issues.

**Inputs:** `ref` (optional override).
**Outputs:** `proceed`, `command`, `request`, `additional_context`, `resolved_ref`,
`is_fork`, `is_pr`, `issue_number`.

Recommended caller gates: CI/build jobs require `proceed == 'true' && is_pr == 'true' &&
is_fork == 'false'` and check out `resolved_ref`; the dispatch call requires
`proceed == 'true' && is_pr == 'true'` — deliberately **not** `is_fork`, because on fork
PRs the dispatch never checks out code (review/merge skip on `unsupported-fork`) and must
run to post the "forks not supported" acknowledgement. See `workflow-templates/gemini.yml`
for the canonical wiring.

### 1.1 `reusable-gemini-dispatch.yml` — entry point

The downstream caller wires this to `pull_request`, `issue_comment`, `issues`, and
`pull_request_review` events. Jobs:

- **`debugger`** — gated on `vars.DEBUG`/`ACTIONS_STEP_DEBUG`; dumps event context.
- **`guard`** — calls `reusable-gemini-guard.yml` (above) with the `ref` input, so the
  dispatch-side gate can never drift from the caller-side one.
- **`dispatch`** — runs only when the guard's `proceed` is `'true'`; re-exports the
  guard's outputs and posts the acknowledgement comment to the PR/issue (or the
  "forks not supported" comment on `unsupported-fork`).
- **`review`** / **`merge`** — call `gemini-review.yml` / `gemini-merge.yml` with
  `secrets: inherit`. `merge` runs when the command is `merge`, or when `review`'s output
  command is `review-and-merge`.
- **`fallthrough`** — runs on `failure()` or an unrecognized command; posts a failure
  comment.

**Inputs:** `projects` (required JSON string), `ref` (optional).
**Secrets:** `GEMINI_API_KEY` (required), `CALLER_GITHUB_TOKEN` (required).
**Caller permissions:** the caller's token caps what called reusable workflows can do, and
GitHub validates each nested job's `permissions:` request against the caller's grant — so
every permission a `uses:` job requests becomes part of the mandatory caller contract. The
dispatch chain requires `contents: write`, `pull-requests: write`, `issues: write`,
`id-token: write`. Callers running `reusable-security-scan` with `scan-code: true` (CodeQL)
additionally need `security-events: write` and `actions: read`.

### 1.2 Identity token

Every Gemini workflow first runs a **"Mint identity token"** step
(`actions/create-github-app-token`) gated on `vars.APP_ID`. When a GitHub App is
configured (`vars.APP_ID` + `secrets.APP_PRIVATE_KEY`), the workflows act as that App so
its reviews/merges are attributable to a bot identity. The token fallback chain used
throughout is:

```
steps.mint_identity_token.outputs.token || secrets.CALLER_GITHUB_TOKEN || secrets.GITHUB_TOKEN || github.token
```

### 1.3 `gemini-review.yml` — two sequential Gemini passes

`timeout-minutes: 25` (two passes), `concurrency` keyed per PR with
`cancel-in-progress: true`. Steps:

1. Mint token, checkout the resolved ref.
2. **Prepare prompt context** — writes `.gemini/context.json` via `jq`. Note `projects`
   is injected with **`--argjson`** (not `--arg`) so it stays a JSON array (see [AGENTS.md](../AGENTS.md)).
3. **Run Gemini pull request review** — `run-gemini-cli` with the
   `gemini-cli-extensions/code-review` extension and the GitHub MCP server
   **`ghcr.io/github/github-mcp-server:v0.27.0`**. Runs the `/gemini-review` prompt.
4. **Run Gemini security analysis** — a **separate** `run-gemini-cli` invocation (loading
   both extensions in one invocation causes tool-registration collisions) using the
   `gemini-cli-extensions/security` extension, pinned to GitHub MCP **`v0.18.0`** (the
   version that extension was authored against). Runs `/security:analyze-github-pr`.
   `upload_artifacts: 'false'` here to avoid colliding with the review step's artifact.
5. **Combine review and security summaries** — folds both into a single `review_summary`
   output (with `## Code Review` and `## Security Analysis` sections) so the merge gate
   applies to security findings too.

MCP tool wiring for the review pass: `includeTools` exposes `pull_request_review_write`,
`add_comment_to_pending_review`, `pull_request_read`; `tools.core` lists those same tools
under their `mcp_github_*` FQNs (required for the MCP tools to reach the model — verified
0.42.0–0.46.0) plus `run_shell_command`, `grep_search`, `list_directory`, `read_file`.

The security pass needs **unscoped `run_shell_command`** in `tools.core` because
`/security:analyze-github-pr` runs `git diff` etc.; a scoped allowlist (cat/echo/grep/…)
makes git commands "denied by policy" and fails the step.

### 1.4 `gemini-merge.yml` — review, remediate, merge

`timeout-minutes: 15`, `concurrency` group `…-merge-…` so **only one merge runs at a
time** (`cancel-in-progress` is false for dependabot). Steps:

1. Mint token, checkout resolved ref.
2. **Resolve PR head ref** — `github-script` returns the PR's `head.ref`. It **validates
   the branch name** against `^[A-Za-z0-9._\/-]+$` and throws otherwise — because the
   branch name is later substituted into `git push origin HEAD:refs/heads/<head_ref>` in a
   shell that holds write credentials, and git permits shell metacharacters in branch
   names.
3. **Prepare prompt context** — writes `.gemini/context.json` including `review_summary`
   and `head_ref`.
4. **Snapshot PR review state** (`pre_state`) — records the set of decisive review IDs
   (`APPROVED`/`CHANGES_REQUESTED`) and the merged state **before** the model runs, by
   **identity (IDs), not timestamps** — immune to clock skew and second-granularity.
5. **Run Gemini pull request merge** — `run-gemini-cli` with the code-review extension and
   GitHub MCP **`v0.27.0`**; `includeTools` adds **`merge_pull_request`** (and its
   `mcp_github_merge_pull_request` FQN in `tools.core`). Runs `/gemini-merge
   --merge_strategy=squash …`.
6. **Verify durable merge outcome** — fails the job unless **this run** either merged the
   PR (`merged_at` newly non-null) or added a **new** decisive review not in the
   pre-snapshot. This catches the model narrating "I merged it" without actually invoking
   the tool — the CLI exits 0 either way. Fails **closed** if the snapshot is missing/
   malformed.

### 1.5 The prompt files (`.github/commands/*.toml`)

These are the actual instructions the model follows; the workflow YAML only wires up
tools/extensions/env.

- **`gemini-review.toml`** — pure review. Posts a pending review, adds severity-tagged
  inline comments (`🔴`/`🟠`/`🟡`/`🟢`), and submits `REQUEST_CHANGES` (on 🔴/🟠),
  `APPROVE`, or `COMMENT`. **Tool-exclusive: no git/gh/shell mutation of repo state.**
- **`gemini-merge.toml`** — review **and** conditionally merge. Encodes the merge policy
  (below). Key mechanism rules baked into the prompt:
  - **Merge** via `mcp_github_merge_pull_request` (squash) first; fall back to
    `gh pr merge <n> --squash --repo <owner>/<repo>` (reads `GITHUB_TOKEN` from env).
    **Never** `git merge`/`git push` to merge; **never** `curl`/token-in-argv.
  - **Remediation fix** (Step 2.5): edit, **locally verify**, then
    `git push origin HEAD:refs/heads/<head_ref>` to the PR's **source branch**.
  - **Forbidden:** pushing/merging to the **default branch**; command substitution
    `$(...)`/`<(...)`/`>(...)`; tokens on the command line.
  - After `gh pr merge` exits 0, **re-read the PR to confirm `merged`** (a 0 exit can mean
    "auto-merge enabled / queued", not merged).

### 1.6 Merge safety policy (the "v0.9.0 posture")

Encoded in `gemini-merge.toml` and summarized in `.github/copilot-instructions.md`:

- Each failing `ci-outcome`/`scan-outcome` is classified **related** vs
  **unrelated/pre-existing**. **When in doubt → related.**
- **Related** failures must pass or be remediated (low-risk fix, locally verified, pushed
  to the source branch); an unremediable related failure **blocks** the merge.
- **Unrelated, pre-existing** failures (including security-scan failures) do **not** block
  the merge, but should be itemized in the approval summary.
- Any **🔴 Critical / 🟠 High** code-review **or** security finding → **REQUEST_CHANGES**
  (block; never auto-merge). Severity is judged by *described meaning*, not just emoji.
- Existing `REQUEST_CHANGES` reviews block the merge.

> A "fix-everything / remediate-then-merge" variant was tried and rolled back because it
> merged an unfixed Critical. Do not re-enable a remediate-then-merge-Critical posture
> without a confirm-fix-on-remote guard.

### 1.7 Gemini model & CLI version selection

Resolved per task, each falling back to a shared var, then a literal default:

| Task     | Variable chain                                                        |
|----------|-----------------------------------------------------------------------|
| Review   | `GEMINI_REVIEW_MODEL` → `GEMINI_MODEL` → `gemini-flash-latest`         |
| Security | `GEMINI_SECURITY_REVIEW_MODEL` → `GEMINI_MODEL` → `gemini-flash-latest`|
| Merge    | `GEMINI_MERGE_MODEL` → `GEMINI_MODEL` → `gemini-flash-latest`          |

- **`gemini-flash-latest` is a deliberate, capable default** (resolves to Flash 3.5) — do
  not treat it as weak or "upgrade" it.
- **`GEMINI_CLI_VERSION`** defaults to a **pinned `0.46.0`** (not floating `latest`),
  because newer CLI releases tightened env/MCP permissions and need prompt/action updates
  before they can safely replace the pin.

---

## 2. Reusable CI (`reusable-ci.yml` + per-language sub-workflows)

`reusable-ci.yml` is a thin dispatcher. A `resolve-ref` job resolves the checkout ref
(input `ref` → PR head SHA → `github.sha`), then exactly one language job runs based on
`inputs.language`, delegating to a local per-language workflow. The composite `outcome`
output is the result of whichever language job actually ran (`'failure'` otherwise). An
unsupported language hits `ci-unsupported`, which fails explicitly.

| `language`   | Sub-workflow    | Setup action            | Lint                                              | Test            | Build                         |
|--------------|-----------------|-------------------------|---------------------------------------------------|-----------------|-------------------------------|
| `javascript` | `ci-npm.yml`    | `setup-node-env`        | `npm run lint`                                    | `npm test`      | `npm run build`               |
| `python`     | `ci-python.yml` | `setup-python-env`      | `flake8` (syntax-error gate + zero-exit warnings) | `pytest`        | — (no build)                  |
| `php`        | `ci-php.yml`    | `setup-php-env`         | `phpcs`/`php-cs-fixer` if present, else skip      | `phpunit` if present | — (no build)             |
| `java`       | `ci-java.yml`   | `setup-java-env`        | compile main+test; SpotBugs/Checkstyle if configured | `mvn/gradle test` | `mvn package -DskipTests` / `gradle assemble` |

Per-language notes:

- **npm** accepts `build-before-test` (run tests after build) and a `CUSTOM_TOKEN` secret
  (exposed as `NODE_AUTH_TOKEN` for private packages).
- **python** test step is best-effort about installing dev deps: `requirements-dev.txt`,
  then a `pyproject.toml` `[project.optional-dependencies].dev` extra (detected by parsing
  the TOML with `tomllib`/`tomli`), then `pytest`. (Earlier versions did not actually run
  pytest — fixed in v0.8.0.)
- **php** lint/test are conditional on the tool existing in `vendor/bin`; absent tools are
  skipped, not failed.
- **java** `extensions` maps to the setup action's `system-packages` (apt packages such as
  `protobuf-compiler` for `protoc`). Lint always compiles; SpotBugs/Checkstyle run only
  when the plugin/task is configured. Build skips tests so `run-lint`/`run-test` stay in
  control.

---

## 3. Reusable security scan (`reusable-security-scan.yml`)

Independent of CI — it does **not** build the project or generate lockfiles first
(it runs against untrusted PR refs). Same `resolve-ref` pattern. The `outcome` output is
`success` only if every relevant scan job is `success`/`skipped` (and the unsupported job
did not run).

- **Dependency scan** (`scan-dependencies`, default true), per language:
  - js → `npm audit --audit-level=moderate`
  - python → `pip-audit` over `requirements*.txt` only (never installs/builds; fails if no
    requirements file is present, with guidance to export a lockfile)
  - php → `composer audit --locked`
  - java → **Trivy** filesystem scan (`scanners: vuln`, `severity: MEDIUM,HIGH,CRITICAL`,
    `exit-code: 1`). Trivy reads `pom.xml`, built JAR/WAR/etc., and committed Gradle/SBT
    lockfiles; a Gradle project with only `build.gradle` and no lockfile may not be fully
    assessed.
  - unsupported language → `dependency-scan-unsupported` fails.
- **CodeQL** (`scan-code`, default false) — init/autobuild/analyze for `inputs.language`;
  needs `security-events: write` + `actions: read` **at runtime, granted by the caller**.
  The job deliberately has no `permissions:` block: GitHub validates nested permission
  requests against the caller's grant at startup **regardless of `if:` conditions**, so a
  static request here would startup-fail every least-privilege caller with `scan-code`
  off.

---

## 4. Composite actions (`actions/*/action.yml`)

All use `runs.using: composite`, and pin nested actions by commit
SHA with a `# ratchet:` comment.

| Action             | Key inputs (defaults)                                              | Outputs       | Notes |
|--------------------|-------------------------------------------------------------------|---------------|-------|
| `setup-node-env`   | `node-version` (20), `cache` (npm), `install-dependencies` (true), `working-directory` (.) | `cache-hit` | Installs via `npm ci` / `yarn --frozen-lockfile` / `pnpm --frozen-lockfile` by cache type. |
| `setup-python-env` | `python-version` (3.11), `install-dependencies` (true), `working-directory` (.) | `cache-hit` | pip cache keyed on `requirements.txt`/`pyproject.toml`; installs `pip install .` (pyproject) or `-r requirements.txt`. |
| `setup-php-env`    | `php-version` (8.4), `install-dependencies` (true), `working-directory` (.), `extensions` ('') | — | `extensions` defaults to `json, mbstring, xml, iconv`; composer:v2; composer cache; `composer install`. |
| `setup-java-env`   | `java-version` (21), `distribution` (temurin), `install-dependencies` (true), `working-directory` (.), `system-packages` ('') | `build-tool` | Auto-detects maven/gradle (fails if neither); validates & apt-installs `system-packages`; best-effort dependency warmup. |

---

## 5. Workflow templates (`workflow-templates/`)

Starter workflows shown in repos' Actions tab. Served from the **default branch** (not a
tag), so `workflow-templates/` edits take effect without a release.

- `ci.yml` / `ci.properties.json`, `security-scan.yml` / `security-scan.properties.json`,
  and `gemini.yml` / `gemini.properties.json` (the canonical Gemini caller: guard-first
  gating, `pull_request: synchronize` in the trigger set, a per-PR `concurrency` group
  with `cancel-in-progress`, and the minimum `permissions` grant for the dispatch).
- Templates can't auto-detect language, so they hardcode `language: 'javascript'` and list
  the supported languages in comments.
- `*.properties.json` `filePatterns` are **regexes** (dots escaped, **not** anchored to
  the repo root so monorepo subdirs still match) with one marker file per ecosystem
  (`package.json`, `composer.json`, `requirements.txt`/`pyproject.toml`,
  `pom.xml`/`build.gradle(.kts)`/`settings.gradle(.kts)`).
- `tests/test_workflow_templates.py`, `tests/test_php_support.py`, and
  `tests/test_java_support.py` keep these patterns/inputs in sync with supported languages.

---

## 6. Conventions baked into the source

- **All nested action refs are pinned by commit SHA** with a `# ratchet:` comment naming
  the human-readable version. Do not "clean up" these to floating tags.
- references inside the workflows/templates are pinned to the release tag and
  must be bumped on release (see AGENTS.md → Versioning).
- Workflow expressions are quoted deliberately; jobs carry `timeout-minutes`.
- `defaults.run.shell: bash` everywhere.
