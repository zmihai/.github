"""Checks the request that actions/gemini-agent/build_request.py builds for the managed agent."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "actions" / "gemini-agent" / "build_request.py"
HEAD = "0123456789abcdef0123456789abcdef01234567"


def build(tmp_path, mode, context_data=None, **overrides):
    context = tmp_path / "context.json"
    if context_data is None:
        context_data = {"repository": "octo/demo", "pull_request_number": "7"}
    context.write_text(json.dumps(context_data), encoding="utf-8")
    request = tmp_path / "request.json"
    env = {
        "PATH": os.environ["PATH"],
        "MODE": mode,
        "MODEL": "some-model",
        "MAX_TOTAL_TOKENS": "3000000",
        "COMMANDS_DIR": str(ROOT / ".github" / "commands"),
        "CONTEXT_FILE": str(context),
        "REQUEST_FILE": str(request),
        "PULL_REQUEST_NUMBER": "7",
        "BASE_REF": "main",
        "HEAD_SHA": HEAD,
        "PROMPT_ARGS": "",
        "GH_TOKEN": "mcp-token",
        "GIT_AUTH": "Z2l0LWF1dGg=",
        "GITHUB_MCP_URL": "https://mcp.invalid/",
        "REPOSITORY": "octo/demo",
    }
    env.update(overrides)
    env = {name: value for name, value in env.items() if value is not None}
    result = subprocess.run([sys.executable, "-I", str(SCRIPT)], env=env, capture_output=True, text=True)
    return result, request


def tools_header(body):
    servers = [tool for tool in body["tools"] if tool["type"] == "mcp_server"]
    assert len(servers) == 1
    return servers[0]["headers"]


@pytest.mark.parametrize("mode", ["review", "merge"])
def test_request_shape(tmp_path, mode):
    result, request = build(tmp_path, mode)
    assert result.returncode == 0, result.stderr
    body = json.loads(request.read_text(encoding="utf-8"))

    assert body["agent_config"] == {"type": "antigravity", "model": "some-model", "max_total_tokens": "3000000"}
    assert {"type": "code_execution"} in body["tools"]
    assert tools_header(body)["Authorization"] == "Bearer mcp-token"
    assert body["environment"]["sources"] == [
        {"type": "repository", "source": "https://github.com/octo/demo", "target": "/workspace/repo"}
    ]
    # The Input Data replaced the placeholder, and the head commit reached the notes.
    assert "@{.gemini-context.json}" not in body["input"]
    assert '"repository": "octo/demo"' in body["input"]
    assert HEAD in body["input"]
    # Neither token may leak into the prompt.
    assert "mcp-token" not in body["input"]
    assert "Z2l0LWF1dGg=" not in body["input"]


def test_review_cannot_merge_and_reaches_github_only(tmp_path):
    result, request = build(tmp_path, "review")
    assert result.returncode == 0, result.stderr
    body = json.loads(request.read_text(encoding="utf-8"))

    assert "merge_pull_request" not in tools_header(body)["X-MCP-Tools"]
    assert body["environment"]["network"]["allowlist"] == [
        {"domain": "github.com", "transform": {"Authorization": "Basic Z2l0LWF1dGg="}}
    ]


def test_merge_can_merge_and_has_open_network(tmp_path):
    result, request = build(tmp_path, "merge")
    assert result.returncode == 0, result.stderr
    body = json.loads(request.read_text(encoding="utf-8"))

    assert "merge_pull_request" in tools_header(body)["X-MCP-Tools"].split(",")
    # Compared whole: the open entry must not carry the git credentials.
    assert body["environment"]["network"]["allowlist"] == [
        {"domain": "github.com", "transform": {"Authorization": "Basic Z2l0LWF1dGg="}},
        {"domain": "*"},
    ]
    assert "expectedHeadSha" in body["input"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"MODE": "deploy"},
        {"MAX_TOTAL_TOKENS": "0"},
        {"MAX_TOTAL_TOKENS": "3e6"},
        {"MAX_TOTAL_TOKENS": "-5"},
        {"GH_TOKEN": ""},
        {"GIT_AUTH": None},
        {"HEAD_SHA": ""},
        {"MODEL": ""},
    ],
)
def test_bad_input_is_refused_without_writing_a_request(tmp_path, overrides):
    result, request = build(tmp_path, overrides.get("MODE", "review"), **overrides)
    assert result.returncode != 0
    assert not request.exists()


DIRECT_HEADING = "## Direct merge path"
LONG_BODY = "release notes " * 400


def clean_context(**changes):
    context = {
        "repository": "octo/demo",
        "pull_request_number": "7",
        "issue_title": "bump a dependency",
        "issue_body": LONG_BODY,
        "additional_context": "",
        "projects": [
            {"name": "server", "ci-outcome": "success", "scan-outcome": "success"},
            {"name": "client", "ci-outcome": "success", "scan-outcome": "success"},
        ],
        "review_summary": "## Review (state: APPROVED)\nLooks fine.\n\n## 🚦 Blocking Findings\n\nNone.\n",
        "head_ref": "dependabot/pip/x",
    }
    context.update(changes)
    return context


def merge_input(tmp_path, context_data, **overrides):
    result, request = build(tmp_path, "merge", context_data=context_data, **overrides)
    assert result.returncode == 0, result.stderr
    return result, json.loads(request.read_text(encoding="utf-8"))["input"]


@pytest.mark.parametrize("setting", [{}, {"MERGE_PATH": ""}, {"MERGE_PATH": "direct"}])
def test_clean_merge_takes_the_direct_path(tmp_path, setting):
    result, prompt = merge_input(tmp_path, clean_context(), **setting)

    assert "Merge path: direct" in result.stdout.splitlines()
    assert prompt.count(DIRECT_HEADING) == 1
    # The direct notes come after the general merge notes, and name the head commit to merge.
    assert prompt.index(DIRECT_HEADING) > prompt.index("Step 2.5 (remediation) applies")
    assert f'expectedHeadSha\n  "{HEAD}"' in prompt[prompt.index(DIRECT_HEADING):]
    direct_notes = prompt[prompt.index(DIRECT_HEADING):]
    # Both ways back to the workflow are spelled out.
    assert "any Critical or High issue" in direct_notes and "carry out the whole workflow above" in direct_notes
    assert "When the call fails" in direct_notes and "from Step 3" in direct_notes
    # The long description is cut, and says so.
    assert LONG_BODY not in prompt
    assert LONG_BODY[:2000].rstrip() in prompt
    assert "[Pull request description cut at 2,000 characters for the direct merge path.]" in prompt


def test_skipped_outcomes_beside_a_success_still_take_the_direct_path(tmp_path):
    projects = [
        {"name": "server", "ci-outcome": "success", "scan-outcome": "success"},
        {"name": "ops", "ci-outcome": "success", "scan-outcome": "skipped"},
        {"name": "docs", "ci-outcome": "skipped", "scan-outcome": "skipped"},
    ]
    result, prompt = merge_input(tmp_path, clean_context(projects=projects))

    assert "Merge path: direct" in result.stdout.splitlines()
    assert DIRECT_HEADING in prompt


@pytest.mark.parametrize("body", [None, 7, ["a" * 3000], {"text": "a" * 3000}])
def test_description_that_is_not_text_is_passed_through_on_the_direct_path(tmp_path, body):
    result, prompt = merge_input(tmp_path, clean_context(issue_body=body))

    assert "Merge path: direct" in result.stdout.splitlines()
    assert "description cut at" not in prompt[: prompt.index(DIRECT_HEADING)]


def test_description_at_the_limit_is_not_cut(tmp_path):
    _, prompt = merge_input(tmp_path, clean_context(issue_body="a" * 2000))
    assert '"issue_body": "' + "a" * 2000 + '"' in prompt
    _, prompt = merge_input(tmp_path, clean_context(issue_body="a" * 2001))
    assert '"issue_body": "' + "a" * 2000 + '\\n\\n[Pull request description cut' in prompt


def test_full_setting_keeps_the_previous_request(tmp_path):
    result, prompt = merge_input(tmp_path, clean_context(), MERGE_PATH="full")

    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt
    assert "Merge path: full (set by GEMINI_AGENT_MERGE_PATH)" in result.stdout.splitlines()
    assert any(line.startswith("::notice::") and "deprecated" in line for line in result.stdout.splitlines())


def test_short_description_is_left_alone_on_the_direct_path(tmp_path):
    _, prompt = merge_input(tmp_path, clean_context(issue_body="short"))

    assert DIRECT_HEADING in prompt
    assert '"issue_body": "short"' in prompt
    assert "description cut at" not in prompt[: prompt.index(DIRECT_HEADING)]


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"additional_context": "focus on security"}, "additional instructions"),
        ({"additional_context": None}, "additional instructions"),
        ({"review_summary": ""}, "did not hand over an approval"),
        ({"review_summary": None}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: COMMENTED)\nfine"}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: CHANGES_REQUESTED)\nno"}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: NOT SUBMITTED)\n"}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: APPROVED) and more\n"}, "did not hand over an approval"),
        ({"review_summary": "intro\n## Review (state: APPROVED)\n"}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: APPROVED)\nx\n\n[Review summary cut at 20,000 characters. Read the full review on the pull request before deciding.]"}, "summary was cut"),
        ({"projects": []}, "no project outcomes"),
        ({"projects": None}, "no project outcomes"),
        ({"projects": {"ci-outcome": "success"}}, "no project outcomes"),
        ({"projects": ["server"]}, "not an object"),
        ({"projects": [{"name": "server"}]}, "carries no outcome"),
        ({"projects": [{"name": "s", "ci-outcome": "success", "scan-outcome": "failure"}]}, "neither success nor skipped"),
        ({"projects": [{"name": "s", "ci-outcome": "success"}, {"name": "c", "ci-outcome": "cancelled"}]}, "neither success nor skipped"),
        ({"projects": [{"name": "s", "ci-outcome": ""}]}, "neither success nor skipped"),
        ({"projects": [{"name": "s", "ci-outcome": "Success"}]}, "neither success nor skipped"),
        ({"projects": [{"name": "s", "ci-outcome": True}]}, "neither success nor skipped"),
        ({"projects": [{"name": "s", "ci-outcome": "skipped", "scan-outcome": "skipped"}]}, "no project outcome is success"),
        # Any key that ends in "outcome" counts, not only the two documented ones.
        ({"projects": [{"name": "s", "ci-outcome": "success", "lint-outcome": "failure"}]}, "neither success nor skipped"),
    ],
)
def test_anything_unexpected_takes_the_full_path(tmp_path, changes, reason):
    result, prompt = merge_input(tmp_path, clean_context(**changes))

    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt
    lines = [line for line in result.stdout.splitlines() if line.startswith("Merge path: ")]
    assert len(lines) == 1 and lines[0].startswith("Merge path: full (") and reason in lines[0]


def test_input_data_that_is_not_an_object_takes_the_full_path(tmp_path):
    result, prompt = merge_input(tmp_path, ["not", "an", "object"])

    assert DIRECT_HEADING not in prompt
    assert "Merge path: full (the Input Data is not an object)" in result.stdout.splitlines()


def test_unknown_merge_path_is_refused(tmp_path):
    result, request = build(tmp_path, "merge", context_data=clean_context(), MERGE_PATH="fast")

    assert result.returncode != 0
    assert "MERGE_PATH" in result.stderr
    assert not request.exists()


def test_review_ignores_the_merge_path(tmp_path):
    result, request = build(tmp_path, "review", context_data=clean_context(), MERGE_PATH="fast")

    assert result.returncode == 0, result.stderr
    prompt = json.loads(request.read_text(encoding="utf-8"))["input"]
    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt
    assert "Merge path" not in result.stdout
