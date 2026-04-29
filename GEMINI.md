# Gemini CLI - .github Project Instructions

This file contains project-specific instructions and conventions for the Gemini CLI workflows and commands in this repository.

## 1. GitHub MCP Tool Naming Convention
- **Rule:** When writing or updating prompt templates (like those in `commands/`), always use the exact prefixed tool names exposed by the MCP server.
- **Detail:** The GitHub MCP server automatically prefixes its tools with `mcp_github_`. 
  - **Correct:** `mcp_github_pull_request_review_write`, `mcp_github_add_comment_to_pending_review`
  - **Incorrect:** `pull_request_review_write`, `add_comment_to_pending_review`

## 2. Parsing JSON Arrays in GitHub Actions (`jq`)
- **Rule:** When injecting JSON array variables (like `PROJECTS`) into `.gemini/context.json` using `jq`, you MUST use `--argjson` instead of `--arg`.
- **Detail:** `--arg` treats the input strictly as a string, which can cause schema validation errors for fields expecting an array. `--argjson` correctly parses the string representation into a structured JSON array.
  - **Example:** `jq --argjson projects "${PROJECTS:-[]}" ...`

## 3. Sandbox Policies & YOLO Mode
- **Rule:** To allow unrestricted shell command execution in YOLO mode, the tool policy must specify `"run_shell_command"` without any arguments.
- **Detail:** If you specify `"run_shell_command(echo)"` (or any other constrained argument), it will restrict the agent to *only* running that specific command, even if YOLO mode is enabled.
