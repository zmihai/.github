# Copilot instructions for this repository

This repository holds reusable GitHub Actions workflows, composite actions, and Gemini CLI
command prompts (`.github/commands/*.toml`) that automatically review and merge pull requests in
other repositories. Because changes here drive automation that runs elsewhere, correctness and
security matter far more than style.

## Code review guidance

When reviewing a pull request:

- **Be comprehensive on the first pass.** Surface every issue you can find the first time you
  review a change — correctness, security, logic, and internal consistency — instead of holding
  findings back for later passes. Do not drip-feed feedback across multiple rounds.
- **Prioritize by severity.** Lead with correctness bugs, security issues, and logic errors.
  Treat naming, wording, formatting, and idiom preferences as low priority and label them clearly
  as minor/optional.
- **On re-reviews, focus on what changed.** When you review a branch you have already reviewed,
  comment primarily on whether the latest changes are correct and whether they introduced
  regressions. Do not re-surface pre-existing issues you could have raised in an earlier pass
  unless they are genuine bugs.
- **Be accurate; don't speculate.** Do not raise an issue based on an unverified assumption about
  an API or library. Avoid "this might be undefined / might fail" comments when the documented
  contract already guarantees the behavior — confirm before flagging.
- **No duplicates.** If the same issue appears in several places, raise it once.
- **Respect intentional patterns.** Actions are pinned by commit SHA with a `# ratchet:` comment,
  and workflow expressions are quoted deliberately; these are intentional and should not be
  flagged.

## Context that affects reviews

- The merge automation lives in `.github/workflows/gemini-merge.yml` and `.github/commands/pr-merge.toml`.
- The merge policy is intentional: failures are classified **related** vs **unrelated/pre-existing**;
  related failures must pass or be remediated, while unrelated pre-existing failures (including
  security) do not block the merge. Review changes against this policy rather than assuming an
  "all checks must pass" rule.
- The durable-outcome gate in `gemini-merge.yml` intentionally fails closed and detects this run's
  outcome by snapshotting review IDs before the model runs — not by timestamps.
