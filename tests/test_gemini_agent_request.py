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


def build(tmp_path, mode, **overrides):
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"repository": "octo/demo", "pull_request_number": "7"}), encoding="utf-8")
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
    domains = [entry["domain"] for entry in body["environment"]["network"]["allowlist"]]
    assert domains == ["github.com", "*"]
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
