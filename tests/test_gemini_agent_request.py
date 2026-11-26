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
OTHER_HEAD = "89abcdef0123456789abcdef0123456789abcdef"


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
APPROVED = f"## Review (state: APPROVED, head: {HEAD})\n"
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
        "review_summary": f"## Review (state: APPROVED, head: {HEAD})\nLooks fine.\n\n## 🚦 Blocking Findings\n\nNone.\n",
        "head_ref": "dependabot/pip/x",
    }
    context.update(changes)
    return context


def merge_input(tmp_path, context_data, **overrides):
    """A merge request with the direct path opted in, unless the test sets MERGE_PATH itself."""
    overrides.setdefault("MERGE_PATH", "direct")
    result, request = build(tmp_path, "merge", context_data=context_data, **overrides)
    assert result.returncode == 0, result.stderr
    return result, json.loads(request.read_text(encoding="utf-8"))["input"]


def test_clean_merge_takes_the_direct_path(tmp_path):
    result, prompt = merge_input(tmp_path, clean_context(), MERGE_PATH="direct")

    assert "Merge path: direct" in result.stdout.splitlines()
    assert "::notice::" not in result.stdout and "deprecated" not in result.stdout
    assert prompt.count(DIRECT_HEADING) == 1
    # The direct notes come after the general merge notes, and name the head commit to merge.
    assert prompt.index(DIRECT_HEADING) > prompt.index("Step 2.5 (remediation) applies")
    assert f'expectedHeadSha\n  "{HEAD}"' in prompt[prompt.index(DIRECT_HEADING):]
    direct_notes = prompt[prompt.index(DIRECT_HEADING):]
    # Both ways back to the workflow are spelled out.
    assert "describes a Critical or High issue" in direct_notes and "carry out the whole workflow above" in direct_notes
    assert "When the call fails" in direct_notes and "do not call it again" in direct_notes
    assert f'commitID "{HEAD}"' in direct_notes and 'event "APPROVE"' in direct_notes
    assert "OUTCOME: APPROVED_NOT_MERGED" in direct_notes
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


def input_data(prompt):
    start = prompt.index("## Input Data")
    return json.JSONDecoder().raw_decode(prompt, prompt.index("{", start))[0]


@pytest.mark.parametrize("body", [None, 7, ["a"] * 2001, {"text": "a" * 3000}])
def test_description_that_is_not_text_is_passed_through_on_the_direct_path(tmp_path, body):
    result, prompt = merge_input(tmp_path, clean_context(issue_body=body))

    assert "Merge path: direct" in result.stdout.splitlines()
    assert input_data(prompt)["issue_body"] == body


@pytest.mark.parametrize("extra", ["", "  \n\t ", ...])
def test_blank_or_absent_instructions_do_not_leave_the_direct_path(tmp_path, extra):
    context = clean_context(additional_context=extra)
    if extra is ...:
        del context["additional_context"]
    result, _ = merge_input(tmp_path, context)

    assert "Merge path: direct" in result.stdout.splitlines()


def test_full_setting_is_reported_whatever_the_input_data(tmp_path):
    result, prompt = merge_input(tmp_path, clean_context(projects=[]), MERGE_PATH="full")

    assert DIRECT_HEADING not in prompt
    assert "Merge path: full (set by GEMINI_AGENT_MERGE_PATH)" in result.stdout.splitlines()


def test_the_repository_variable_reaches_the_builder():
    import yaml

    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "gemini-agent-merge.yml").read_text(encoding="utf-8"))
    steps = [step for job in workflow["jobs"].values() for step in job["steps"] if step.get("uses") == "$/actions/gemini-agent"]
    assert len(steps) == 1
    assert steps[0]["with"]["merge_path"] == "${{ vars.GEMINI_AGENT_MERGE_PATH }}"

    action = yaml.safe_load((ROOT / "actions" / "gemini-agent" / "action.yml").read_text(encoding="utf-8"))
    assert action["inputs"]["merge_path"]["default"] == ""
    steps = [step for step in action["runs"]["steps"] if "MERGE_PATH" in step.get("env", {})]
    assert [step["env"]["MERGE_PATH"] for step in steps] == ["${{ inputs.merge_path }}"]
    # The same step is the one that runs the builder.
    assert 'python3 -I "${ACTION_PATH}/build_request.py"' in steps[0]["run"]

    review = (ROOT / ".github" / "workflows" / "gemini-agent-review.yml").read_text(encoding="utf-8")
    assert 'echo "## Review (state: ${new_state:-NOT SUBMITTED}, head: ${HEAD_SHA})"' in review


def test_the_review_account_reaches_the_builder():
    import yaml

    reviewer = "${{ steps.mint_identity_token.outputs.app-slug && format('{0}[bot]', steps.mint_identity_token.outputs.app-slug) || 'github-actions[bot]' }}"
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "gemini-agent-merge.yml").read_text(encoding="utf-8"))
    steps = [step for job in workflow["jobs"].values() for step in job["steps"] if step.get("uses") == "$/actions/gemini-agent"]
    # Only on a merge-only command, which the dispatcher states itself.
    assert [step["with"]["reviewer_login"] for step in steps] == ["${{ inputs.merge_only && (" + reviewer[4:-3] + ") || '' }}"]
    assert workflow[True]["workflow_call"]["inputs"]["merge_only"] == {
        "description": workflow[True]["workflow_call"]["inputs"]["merge_only"]["description"],
        "required": False,
        "type": "boolean",
        "default": False,
    }
    dispatch = yaml.safe_load((ROOT / ".github" / "workflows" / "reusable-gemini-dispatch.yml").read_text(encoding="utf-8"))
    callers = [job for job in dispatch["jobs"].values() if job.get("uses") == "./.github/workflows/gemini-agent-merge.yml"]
    assert [job["with"]["merge_only"] for job in callers] == ["${{ needs.dispatch.outputs.command == 'merge' && needs.agent-review.result == 'skipped' }}"]
    # The step that mints the App identity runs before the step that names it.
    for job in workflow["jobs"].values():
        names = [step.get("id") or step.get("uses") for step in job["steps"]]
        if "$/actions/gemini-agent" in names:
            assert names.index("mint_identity_token") < names.index("$/actions/gemini-agent")
    # The same account the review job attributes its own reviews to.
    review = yaml.safe_load((ROOT / ".github" / "workflows" / "gemini-agent-review.yml").read_text(encoding="utf-8"))
    summary = [step for job in review["jobs"].values() for step in job["steps"] if step.get("id") == "summary"]
    assert [step["env"]["REVIEWER_LOGIN"] for step in summary] == [reviewer]
    assert all("reviewer_login" not in step.get("with", {}) for job in review["jobs"].values() for step in job["steps"])

    action = yaml.safe_load((ROOT / "actions" / "gemini-agent" / "action.yml").read_text(encoding="utf-8"))
    assert action["inputs"]["reviewer_login"]["default"] == ""
    steps = [step for step in action["runs"]["steps"] if "REVIEWER_LOGIN" in step.get("env", {})]
    assert [step["env"]["REVIEWER_LOGIN"] for step in steps] == ["${{ inputs.reviewer_login }}"]
    run = steps[0]["run"]
    listing = run.index('timeout --kill-after=5 60 gh api "repos/${REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}/reviews?per_page=100" --paginate --slurp > "${reviews_file}" &\n')
    # Listed before the builder runs and while the token is still set, and only when the builder asks.
    assert run.index("export REVIEWS_FILE=''") < run.index('if python3 -I "${ACTION_PATH}/build_request.py" --wants-reviews 2> /dev/null; then') < listing
    assert listing < run.index('export REVIEWS_FILE="${reviews_file}"') < run.index('python3 -I "${ACTION_PATH}/build_request.py"\n') < run.index("unset GH_TOKEN")


def test_text_after_a_merge_only_command_reaches_the_agent_engine_only():
    import yaml

    guard = (ROOT / ".github" / "workflows" / "reusable-gemini-guard.yml").read_text(encoding="utf-8")
    # Kept as instructions, which rule the direct merge path out.
    assert """command = 'merge';""" in guard
    assert """additionalContext = request.replace(/^@gemini-cli \\/merge/, '').trim();""" in guard
    dispatch = yaml.safe_load((ROOT / ".github" / "workflows" / "reusable-gemini-dispatch.yml").read_text(encoding="utf-8"))
    handed = {job["uses"]: job["with"]["additional_context"] for job in dispatch["jobs"].values() if "additional_context" in job.get("with", {})}
    passed_on = "${{ needs.dispatch.outputs.additional_context }}"
    assert handed == {
        "./.github/workflows/gemini-review.yml": passed_on,
        "./.github/workflows/gemini-agent-review.yml": passed_on,
        "./.github/workflows/gemini-agent-merge.yml": passed_on,
        # The Gemini CLI merge job gets what it always got on a merge-only command: nothing.
        "./.github/workflows/gemini-merge.yml": "${{ needs.dispatch.outputs.command != 'merge' && needs.dispatch.outputs.additional_context || '' }}",
    }


def listing_command(tmp_path, summary, gh_exit=0, gh_sleep=0, **overrides):
    """The part of the action's run step that lists the reviews, with a stand-in `gh`: (argv, env, calls file)."""
    import yaml

    action = yaml.safe_load((ROOT / "actions" / "gemini-agent" / "action.yml").read_text(encoding="utf-8"))
    run = [step["run"] for step in action["runs"]["steps"] if "REVIEWER_LOGIN" in step.get("env", {})][0]
    start = run.index("export REVIEWS_FILE=''")
    block = run[start : run.index('python3 -I "${ACTION_PATH}/build_request.py"\n', start)]
    # The cleanup and the traps the step sets before this part, as the action writes them.
    cleanup = run[run.index("cleanup() {\n") : run.index("trap 'exit 143' TERM\n") + len("trap 'exit 143' TERM\n")]
    assert "trap cleanup EXIT\n" in cleanup and "trap 'exit 130' INT\n" in cleanup and run.index(cleanup) < start
    traps = "interaction_id=''\nfinished='no'\nchild_pid=''\nrequest_file=''\ninteraction_file=''\n" + cleanup
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "gh-calls.txt"
    (bin_dir / "gh").write_text(
        f'#!/bin/bash\necho "$$" > "{tmp_path}/gh-pid.txt"\necho "$*" >> "{calls}"\nsleep {gh_sleep}\necho \'[["listed"]]\'\nexit {gh_exit}\n', encoding="utf-8"
    )
    (bin_dir / "gh").chmod(0o755)
    context = tmp_path / "context.json"
    context.write_text(summary, encoding="utf-8")
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "RUNNER_TEMP": str(tmp_path),
        "ACTION_PATH": str(SCRIPT.parent),
        "MODE": "merge",
        "MERGE_PATH": "direct",
        "REVIEWER_LOGIN": "github-actions[bot]",
        "REPOSITORY": "octo/demo",
        "PULL_REQUEST_NUMBER": "7",
        "CONTEXT_FILE": str(context),
        "HEAD_SHA": HEAD,
        # An inherited value must never reach the builder.
        "REVIEWS_FILE": "/inherited/listing.json",
    }
    env.update(overrides)
    script = traps + block + '\necho "REVIEWS_FILE=${REVIEWS_FILE}"'
    # The flags the runner starts a `shell: bash` step with.
    return ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script], env, calls


def listing_step(tmp_path, summary, gh_exit=0, **overrides):
    """Runs that part to its end: (stdout, the calls `gh` received)."""
    argv, env, calls = listing_command(tmp_path, summary, gh_exit=gh_exit, **overrides)
    result = subprocess.run(argv, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout, calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


def test_a_cancel_signal_ends_the_step_while_the_reviews_are_listed(tmp_path):
    import signal
    import time

    argv, env, calls = listing_command(tmp_path, context_text(review_summary=""), gh_sleep=20)
    process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        waited = time.monotonic()
        while not calls.exists():
            assert time.monotonic() - waited < 15 and process.poll() is None
            time.sleep(0.05)
        # The runner signals the step's shell only.
        sent = time.monotonic()
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=10) == 130
        assert time.monotonic() - sent < 5
        # The step's own cleanup stopped the listing.
        gh_pid = int((tmp_path / "gh-pid.txt").read_text(encoding="utf-8"))
        stopped = time.monotonic()
        while Path(f"/proc/{gh_pid}").exists():
            assert time.monotonic() - stopped < 5
            time.sleep(0.05)
    finally:
        process.kill()
        subprocess.run(["pkill", "-f", str(tmp_path / "bin" / "gh")], check=False)


def context_text(**changes):
    return json.dumps(clean_context(**changes))


def test_a_merge_only_command_on_the_direct_path_lists_the_reviews(tmp_path):
    stdout, calls = listing_step(tmp_path, context_text(review_summary=""))

    assert calls == ["api repos/octo/demo/pulls/7/reviews?per_page=100 --paginate --slurp"]
    listing = tmp_path / "agent-reviews-merge.json"
    assert stdout.splitlines() == [f"REVIEWS_FILE={listing}"]
    assert json.loads(listing.read_text(encoding="utf-8")) == [["listed"]]


@pytest.mark.parametrize(
    "summary, overrides",
    [
        # A summary was handed over, or the Input Data is not what the lookup expects.
        (context_text(), {}),
        (context_text(review_summary="(no review summary produced)"), {}),
        (context_text(review_summary=None), {}),
        ("[]", {}),
        ("not json", {}),
        # Something else already rules the direct path out, so the listing would not be read.
        (context_text(review_summary="", additional_context="Please recheck the migration."), {}),
        (context_text(review_summary="", projects=[{"name": "s", "ci-outcome": "failure"}]), {}),
        (context_text(review_summary="", projects=[]), {}),
        (context_text(review_summary=""), {"MERGE_PATH": "sideways"}),
        # Not a merge on the direct path, or no account to look for.
        (context_text(review_summary=""), {"MODE": "review"}),
        (context_text(review_summary=""), {"MERGE_PATH": "full"}),
        (context_text(review_summary=""), {"MERGE_PATH": ""}),
        (context_text(review_summary=""), {"REVIEWER_LOGIN": ""}),
    ],
)
def test_no_other_run_lists_the_reviews(tmp_path, summary, overrides):
    stdout, calls = listing_step(tmp_path, summary, **overrides)

    assert calls == []
    assert stdout.splitlines() == ["REVIEWS_FILE="]


@pytest.mark.parametrize("blank", [" ", "\n\t", "\u001c", "\u00a0"])
def test_the_shell_and_the_builder_agree_on_what_a_blank_summary_is(tmp_path, blank):
    _, calls = listing_step(tmp_path, context_text(review_summary=blank))
    assert len(calls) == 1

    (tmp_path / "builder").mkdir()
    result, _ = merge_only(tmp_path / "builder", [review(41, "APPROVED", 5)], context_changes={"review_summary": blank})
    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")


def test_the_listing_replaces_whatever_holds_its_name(tmp_path):
    (tmp_path / "agent-reviews-merge.json").mkdir()
    (tmp_path / "agent-reviews-merge.json" / "left-behind").write_text("x", encoding="utf-8")
    stdout, calls = listing_step(tmp_path, context_text(review_summary=""))

    assert len(calls) == 1
    assert stdout.splitlines() == [f"REVIEWS_FILE={tmp_path / 'agent-reviews-merge.json'}"]
    assert json.loads((tmp_path / "agent-reviews-merge.json").read_text(encoding="utf-8")) == [["listed"]]


def test_a_failed_listing_leaves_no_listing_for_the_builder(tmp_path):
    stdout, calls = listing_step(tmp_path, context_text(review_summary=" \n"), gh_exit=1)

    assert len(calls) == 1
    assert stdout.splitlines() == ["::warning::Could not list the pull request reviews; this merge repeats the review.", "REVIEWS_FILE="]


def test_the_standing_approval_is_cut_with_the_review_job_s_words():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import build_request
    finally:
        sys.path.pop(0)
    review_job = (ROOT / ".github" / "workflows" / "gemini-agent-review.yml").read_text(encoding="utf-8")
    assert f"limit = {build_request.SUMMARY_LIMIT}\n" in review_job
    assert 'text = text[:limit] + "' + build_request.SUMMARY_CUT_NOTE.replace("\n", "\\n") + '"' in review_job
    assert build_request.SUMMARY_CUT_MARK in build_request.SUMMARY_CUT_NOTE
    # And those are the words the builder writes when it cuts.
    over = [review(41, "APPROVED", 5, body="y" * 20001 + BLOCKING_TAIL)]
    _, summary = build_request.standing_approval(over, BOT, HEAD)
    header = f"## Review (state: APPROVED, head: {HEAD})\n"
    assert summary == header + "y" * 20000 + "\n\n[Review summary cut at 20,000 characters. Read the full review on the pull request before deciding.]"
    # The review job writes each review body and a blank line, then its header above the capped text.
    assert """gh api "repos/${REPOSITORY}/pulls/${PULL_REQUEST_NUMBER}/reviews/${id}" --jq '.body // ""' >> "${RUNNER_TEMP}/review-summary.md"\n            echo >> "${RUNNER_TEMP}/review-summary.md\"""" in review_job


def test_description_at_the_limit_is_not_cut(tmp_path):
    _, prompt = merge_input(tmp_path, clean_context(issue_body="a" * 2000))
    assert '"issue_body": "' + "a" * 2000 + '"' in prompt
    _, prompt = merge_input(tmp_path, clean_context(issue_body="a" * 2001))
    assert '"issue_body": "' + "a" * 2000 + '\\n\\n[Pull request description cut' in prompt


@pytest.mark.parametrize("tail", ["## 🚦 Blocking Findings\nNone.", "### Blocking Findings\n\n  None.  \n\n\n"])
def test_an_empty_blocking_section_in_other_spellings_still_qualifies(tmp_path, tail):
    result, _ = merge_input(tmp_path, clean_context(review_summary=APPROVED + "fine\n\n" + tail))

    assert "Merge path: direct" in result.stdout.splitlines()


def test_full_setting_keeps_the_previous_request(tmp_path):
    result, prompt = merge_input(tmp_path, clean_context(), MERGE_PATH="full")

    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt
    assert "Merge path: full (set by GEMINI_AGENT_MERGE_PATH)" in result.stdout.splitlines()
    assert "::notice::" not in result.stdout


@pytest.mark.parametrize("setting", [None, ""])
def test_unset_keeps_the_previous_request_and_announces_the_change(tmp_path, setting):
    # A version bump alone must not change how a consumer merges: the direct path is opt-in.
    overrides = {} if setting is None else {"MERGE_PATH": setting}
    result, request = build(tmp_path, "merge", context_data=clean_context(), **overrides)

    assert result.returncode == 0, result.stderr
    prompt = json.loads(request.read_text(encoding="utf-8"))["input"]
    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt
    lines = result.stdout.splitlines()
    assert [line for line in lines if line.startswith("Merge path: ")] == ["Merge path: full (GEMINI_AGENT_MERGE_PATH is not set)"]
    notices = [line for line in lines if line.startswith("::notice::")]
    assert len(notices) == 1 and "deprecated" in notices[0] and "'direct'" in notices[0]


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
        ({"review_summary": f"## Review (state: COMMENTED, head: {HEAD})\nfine"}, "did not hand over an approval"),
        ({"review_summary": f"## Review (state: CHANGES_REQUESTED, head: {HEAD})\nno"}, "did not hand over an approval"),
        ({"review_summary": f"## Review (state: NOT SUBMITTED, head: {HEAD})\n"}, "did not hand over an approval"),
        ({"review_summary": f"## Review (state: APPROVED, head: {HEAD}) and more\n"}, "did not hand over an approval"),
        ({"review_summary": f"## Review (state: APPROVED, head: {HEAD})\r\nfine"}, "did not hand over an approval"),
        ({"review_summary": f"intro\n## Review (state: APPROVED, head: {HEAD})\n"}, "did not hand over an approval"),
        # An approval of another commit, or one that names no commit, is not an approval of this head.
        ({"review_summary": f"## Review (state: APPROVED, head: {OTHER_HEAD})\nfine"}, "did not hand over an approval"),
        ({"review_summary": "## Review (state: APPROVED)\nfine"}, "did not hand over an approval"),
        ({"additional_context": " \n\t x"}, "additional instructions"),
        ({"review_summary": APPROVED + "Looks fine.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n\n- 🔴 Critical: SQL injection in a.py:3\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n\nNone.\n\n- 🟠 High: b.py:9\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n\nNone.\n\n## More\n\ntext\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n- High: a\n\n## 🚦 Blocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\nBlocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n\nnone\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "- 🔴 Critical: a.py:3\n\n## Not Blocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "- 🔴 Critical: a.py:3\n\n## Blocking Findings (empty)\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "- 🔴 Critical: a.py:3\n\n## Non-Blocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "See the blocking findings below.\n\n## 🚦 Blocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n## 🚦 Blocking Findings\n\nNone.\nNone.\n"}, "Blocking Findings"),
        ({"review_summary": APPROVED + "x\n\n####### Blocking Findings\n\nNone.\n"}, "Blocking Findings"),
        ({"projects": [{"name": "s", "ci-outcome": "success"}, {"name": "docs"}]}, "carries no outcome"),
        ({"review_summary": f"## Review (state: APPROVED, head: {HEAD})\nx\n\n[Review summary cut at 20,000 characters. Read the full review on the pull request before deciding.]"}, "summary was cut"),
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


@pytest.mark.parametrize("setting", [None, "", "direct", "full", "fast"])
def test_review_ignores_the_merge_path(tmp_path, setting):
    overrides = {} if setting is None else {"MERGE_PATH": setting}
    result, request = build(tmp_path, "review", context_data=clean_context(), **overrides)

    assert result.returncode == 0, result.stderr
    assert "::notice::" not in result.stdout and "Merge path" not in result.stdout
    prompt = json.loads(request.read_text(encoding="utf-8"))["input"]
    assert DIRECT_HEADING not in prompt
    assert json.dumps(LONG_BODY)[1:-1] in prompt


# A merge-only command: no review job ran, so the Input Data carries an empty review summary, and
# the review account's standing approval of the head commit is read from the pull request.
BOT = "github-actions[bot]"
BLOCKING_TAIL = "\n\n## 🚦 Blocking Findings\n\nNone."
REVIEW_BODY = "Looks fine." + BLOCKING_TAIL


def review(review_id, state, minute, commit=HEAD, login=BOT, body=REVIEW_BODY, **changes):
    entry = {
        "id": review_id,
        "state": state,
        "commit_id": commit,
        "submitted_at": f"2026-01-02T03:{minute:02d}:00Z",
        "user": {"login": login},
        "body": body,
    }
    entry.update(changes)
    return entry


def merge_only(tmp_path, reviews, context_changes=None, pages=None, **overrides):
    """A merge-only request; `reviews` become the one page of the listing unless `pages` is given."""
    listing = tmp_path / "reviews.json"
    listing.write_text(json.dumps([reviews] if pages is None else pages), encoding="utf-8")
    overrides.setdefault("REVIEWS_FILE", str(listing))
    overrides.setdefault("REVIEWER_LOGIN", BOT)
    context = clean_context(**{"review_summary": "", **(context_changes or {})})
    return merge_input(tmp_path, context, **overrides)


def merge_path_line(result):
    lines = [line for line in result.stdout.splitlines() if line.startswith("Merge path: ")]
    assert len(lines) == 1
    return lines[0]


def test_a_merge_only_command_takes_the_direct_path_on_a_standing_approval(tmp_path):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5)])

    assert merge_path_line(result) == "Merge path: direct (review 41 approved this head commit in an earlier run)"
    assert prompt.count(DIRECT_HEADING) == 1
    # The summary is rebuilt as the review job hands it over: header, body, a blank line.
    assert input_data(prompt)["review_summary"] == f"## Review (state: APPROVED, head: {HEAD})\n{REVIEW_BODY}\n\n"
    assert "description cut at" in prompt


@pytest.mark.parametrize(
    "reviews",
    [
        # Reviews that do not count: earlier ones, comments, other accounts, pending ones.
        [review(40, "CHANGES_REQUESTED", 1, commit=OTHER_HEAD), review(41, "APPROVED", 5)],
        [review(41, "APPROVED", 5), review(42, "COMMENTED", 6, body="A note.")],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login="someone")],
        # As GitHub lists a pending review: without a submission time.
        [review(41, "APPROVED", 5), {"id": 42, "state": "PENDING", "commit_id": HEAD, "user": {"login": BOT}, "body": ""}],
        [review(41, "APPROVED", 5), review(42, "COMMENTED", 6, submitted_at=None)],
        [review(40, "DISMISSED", 1), review(41, "APPROVED", 5)],
        # The listing's order does not matter.
        [review(41, "APPROVED", 5), review(40, "CHANGES_REQUESTED", 1)],
        [review(41, "APPROVED", 5, login=BOT.upper())],
        # As GitHub lists the review of a deleted account: without a user.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, user=None)],
    ],
)
def test_reviews_that_do_not_touch_the_standing_approval(tmp_path, reviews):
    result, prompt = merge_only(tmp_path, reviews)

    assert merge_path_line(result) == "Merge path: direct (review 41 approved this head commit in an earlier run)"
    assert DIRECT_HEADING in prompt


def test_the_listing_is_read_across_pages(tmp_path):
    pages = [[review(40, "CHANGES_REQUESTED", 1)], [review(41, "APPROVED", 5)]]
    result, _ = merge_only(tmp_path, None, pages=pages)
    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")

    # The later page decides here too.
    pages = [[review(41, "APPROVED", 5)], [review(42, "CHANGES_REQUESTED", 6)]]
    result, _ = merge_only(tmp_path, None, pages=pages)
    assert "no standing approval" in merge_path_line(result)


NO_STANDING = "no review job ran, and the review account has no standing approval of this head commit"


@pytest.mark.parametrize(
    "reviews",
    [
        [],
        [review(41, "COMMENTED", 5)],
        [review(41, "APPROVED", 5, login="someone")],
        [review(41, "APPROVED", 5, commit=OTHER_HEAD)],
        [review(41, "APPROVED", 5, commit=None)],
        # The account's latest decisive review is not an approval.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6)],
        [review(41, "APPROVED", 5), review(42, "DISMISSED", 6)],
        [review(41, "DISMISSED", 5)],
        # A later approval of another commit does not revive the one of this head.
        [review(41, "APPROVED", 5), review(42, "APPROVED", 6, commit=OTHER_HEAD)],
        # Same second: no order to rely on, so there has to be exactly one.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 5)],
        [review(42, "CHANGES_REQUESTED", 5), review(41, "APPROVED", 5)],
        [review(41, "APPROVED", 5), review(42, "APPROVED", 5)],
        [review(40, "APPROVED", 5, body=None), review(41, "APPROVED", 5)],
        [review(41, "APPROVED", 5, body="")],
        [review(41, "APPROVED", 5, body=" \n")],
        [review(41, "APPROVED", 5, body=None)],
        [review(41, "APPROVED", 5, body=["Looks fine.", "## 🚦 Blocking Findings", "None."])],
        # A timestamp in any other shape cannot be ordered against the rest.
        [review(41, "APPROVED", 5, submitted_at=None)],
        [review(41, "APPROVED", 5, submitted_at=20260102030500)],
        [review(41, "APPROVED", 5, submitted_at="later?")],
        [review(41, "APPROVED", 5, submitted_at="2026-01-02T03:05:00Z+01:00")],
        # Digits of another script would sort above every real timestamp; so would a date that does not exist.
        [review(41, "APPROVED", 5, submitted_at="١٩٩٩-٠١-٠٢T٠٣:٠٥:٠٠Z"), review(42, "CHANGES_REQUESTED", 6)],
        [review(41, "APPROVED", 5, submitted_at="2026-99-99T99:99:99Z"), review(42, "CHANGES_REQUESTED", 6)],
        # A real time written without its leading zero would sort above the later review.
        [review(41, "APPROVED", 5, submitted_at="2026-01-02T3:05:00Z"), review(42, "CHANGES_REQUESTED", 6)],
        [review(41, "APPROVED", 5, user=BOT)],
        [review(41, "APPROVED", 5, user=[BOT])],
        # An entry that does not say whose it is could be a later review of this account.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, user=BOT)],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, user={"login": None})],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, user={"id": 7})],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login="")],
        # Nor does a name in any other shape than GitHub's.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login=" ")],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login=BOT + "\n")],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login="some one")],
        # A Kelvin sign lowercases to the letter k.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login="github-actions[bot]".replace("b", "\u212a", 1))],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, user=7)],
        ["not a review", review(41, "APPROVED", 5)],
        [review(41, "APPROVED", 5), None],
        [review(41, "APPROVED", 5), review(40, "CHANGES_REQUESTED", 1, submitted_at="")],
        [review(40, "CHANGES_REQUESTED", 1, submitted_at=""), review(41, "APPROVED", 5)],
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 5, submitted_at="2026-01-02T03:05:00.500Z")],
        [review(41, "APPROVED", 5), review(40, "DISMISSED", 1, submitted_at="2026-01-02 03:01:00Z")],
        # A state this code does not know, on any of the account's reviews.
        [review(41, "APPROVED", 5), review(42, "changes_requested", 6)],
        [review(41, "APPROVED", 5), review(42, "WITHDRAWN", 6)],
        [review(41, "APPROVED", 5), review(42, None, 6)],
        [review("41", "APPROVED", 5)],
        [review(True, "APPROVED", 5)],
        [review(41, "APPROVED", 5, user=None)],
        [review(41, "approved", 5)],
        # Account names do not differ by case alone, so this later review is the account's too.
        [review(41, "APPROVED", 5), review(42, "CHANGES_REQUESTED", 6, login=BOT.upper())],
    ],
)
def test_without_a_standing_approval_a_merge_only_command_repeats_the_review(tmp_path, reviews):
    result, prompt = merge_only(tmp_path, reviews)

    assert merge_path_line(result) == f"Merge path: full ({NO_STANDING})"
    assert DIRECT_HEADING not in prompt
    # The full path gets the Input Data it always got.
    assert input_data(prompt)["review_summary"] == ""
    assert json.dumps(LONG_BODY)[1:-1] in prompt


@pytest.mark.parametrize(
    "body, reason",
    [
        ("Looks fine.", "does not end with an empty Blocking Findings section, in review 41 from an earlier run"),
        ("x\n\n## 🚦 Blocking Findings\n\n- 🔴 Critical: a.py:3", "Blocking Findings section, in review 41 from an earlier run"),
        ("y" * 20001 + "\n\n## 🚦 Blocking Findings\n\nNone.", "the review summary was cut, in review 41 from an earlier run"),
        # One character over the cap, counted as the review job counts: the body and a blank line.
        ("y" * (19999 - len(BLOCKING_TAIL)) + BLOCKING_TAIL, "the review summary was cut, in review 41 from an earlier run"),
    ],
)
def test_a_standing_approval_passes_the_same_checks_as_a_handed_over_summary(tmp_path, body, reason):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5, body=body)])

    line = merge_path_line(result)
    assert line.startswith("Merge path: full (") and reason in line
    assert DIRECT_HEADING not in prompt
    assert input_data(prompt)["review_summary"] == ""


def test_a_standing_approval_at_the_summary_limit_is_not_cut(tmp_path):
    # The cap counts the body and the blank line the review job writes after it.
    body = "y" * (19998 - len(BLOCKING_TAIL)) + BLOCKING_TAIL
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5, body=body)])

    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")
    assert input_data(prompt)["review_summary"] == f"## Review (state: APPROVED, head: {HEAD})\n{body}\n\n"


@pytest.mark.parametrize(
    "context_changes, reason",
    [
        # Extra instructions rule the direct path out before any review is looked up.
        ({"additional_context": "skip the tests"}, "(the request carries additional instructions)"),
        ({"additional_context": None}, "(the request carries additional instructions)"),
        # So do project outcomes: no review is looked up for a request that cannot go direct.
        ({"projects": [{"name": "s", "ci-outcome": "failure"}]}, "(the review job did not hand over an approval of this head commit)"),
        ({"projects": []}, "(the review job did not hand over an approval of this head commit)"),
    ],
)
def test_a_standing_approval_does_not_excuse_the_other_conditions(tmp_path, context_changes, reason):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5)], context_changes=context_changes)

    line = merge_path_line(result)
    assert line.startswith("Merge path: full (") and line.endswith(reason if reason.startswith("(") else reason + ")")
    assert DIRECT_HEADING not in prompt
    assert input_data(prompt)["review_summary"] == ""


@pytest.mark.parametrize(
    "summary",
    [
        f"## Review (state: COMMENTED, head: {HEAD})\nfine",
        f"## Review (state: CHANGES_REQUESTED, head: {HEAD})\nno",
        f"## Review (state: NOT SUBMITTED, head: {HEAD})\n",
        f"## Review (state: APPROVED, head: {OTHER_HEAD})\nfine",
        "(no review summary produced)",
        None,
    ],
)
def test_a_summary_the_review_job_handed_over_is_never_replaced(tmp_path, summary):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5)], context_changes={"review_summary": summary})

    assert merge_path_line(result) == "Merge path: full (the review job did not hand over an approval of this head commit)"
    assert DIRECT_HEADING not in prompt
    assert input_data(prompt)["review_summary"] == summary


@pytest.mark.parametrize("blank", ["", " ", "\n\t"])
def test_a_blank_summary_counts_as_nothing_handed_over(tmp_path, blank):
    result, _ = merge_only(tmp_path, [review(41, "APPROVED", 5)], context_changes={"review_summary": blank})

    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")


@pytest.mark.parametrize(
    "overrides, line",
    [
        # No listing, or no account to look for: the lookup is not made at all.
        ({"REVIEWS_FILE": None}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWS_FILE": ""}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWER_LOGIN": None}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWER_LOGIN": ""}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWER_LOGIN": " "}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWER_LOGIN": BOT + " "}, "Merge path: full (the review job did not hand over an approval of this head commit)"),
        ({"REVIEWER_LOGIN": "someone-else[bot]"}, f"Merge path: full ({NO_STANDING})"),
        ({"REVIEWS_FILE": "/nonexistent/reviews.json"}, f"Merge path: full ({NO_STANDING})"),
        # The direct path is opt-in; the other settings never look.
        ({"MERGE_PATH": "full"}, "Merge path: full (set by GEMINI_AGENT_MERGE_PATH)"),
        ({"MERGE_PATH": ""}, "Merge path: full (GEMINI_AGENT_MERGE_PATH is not set)"),
    ],
)
def test_the_lookup_needs_the_listing_the_account_and_the_opt_in(tmp_path, overrides, line):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5)], **overrides)

    assert merge_path_line(result) == line
    assert DIRECT_HEADING not in prompt
    assert input_data(prompt)["review_summary"] == ""


# The last one is a listing that was not written as pages.
@pytest.mark.parametrize("content", ["", "not json", "{}", '"text"', "null", "[41]", "[[41]]", json.dumps([review(41, "APPROVED", 5)]), json.dumps([[], review(41, "APPROVED", 5)])])
def test_an_unreadable_listing_means_no_standing_approval(tmp_path, content):
    listing = tmp_path / "broken.json"
    listing.write_text(content, encoding="utf-8")
    result, prompt = merge_only(tmp_path, [], REVIEWS_FILE=str(listing))

    assert merge_path_line(result) == f"Merge path: full ({NO_STANDING})"
    assert DIRECT_HEADING not in prompt


def test_a_listing_nested_too_deep_to_read_means_no_standing_approval(tmp_path):
    listing = tmp_path / "deep.json"
    listing.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    result, prompt = merge_only(tmp_path, [], REVIEWS_FILE=str(listing))

    assert merge_path_line(result) == f"Merge path: full ({NO_STANDING})"
    assert DIRECT_HEADING not in prompt


def test_line_endings_in_a_standing_approval_are_read_as_the_review_job_reads_them(tmp_path):
    body = "Looks fine.\r\n\r\n## 🚦 Blocking Findings\r\rNone."
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5, body=body)])

    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")
    assert input_data(prompt)["review_summary"] == f"## Review (state: APPROVED, head: {HEAD})\n{REVIEW_BODY}\n\n"
    # Counted after the conversion, as the review job counts: this body is at the cap, not over it.
    body = ("y\r\n" * 9000 + "z" * (19998 - 18000 - len(BLOCKING_TAIL))) + BLOCKING_TAIL
    result, _ = merge_only(tmp_path, [review(41, "APPROVED", 5, body=body)])
    assert merge_path_line(result).startswith("Merge path: direct (review 41 ")
    # A body that ends in a carriage return: it and the line feed written after it are one line ending.
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5, body=REVIEW_BODY + "\r")])
    assert input_data(prompt)["review_summary"] == f"## Review (state: APPROVED, head: {HEAD})\n{REVIEW_BODY}\n\n"


def test_input_data_that_is_not_an_object_is_not_looked_up(tmp_path):
    listing = tmp_path / "reviews.json"
    listing.write_text(json.dumps([[review(41, "APPROVED", 5)]]), encoding="utf-8")
    result, prompt = merge_input(tmp_path, ["not", "an", "object"], REVIEWS_FILE=str(listing), REVIEWER_LOGIN=BOT)

    assert merge_path_line(result) == "Merge path: full (the Input Data is not an object)"
    assert DIRECT_HEADING not in prompt


def test_no_account_has_no_standing_approval():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import build_request
    finally:
        sys.path.pop(0)
    nameless = dict(review(41, "APPROVED", 5), user={"login": ""})
    assert build_request.standing_approval([review(41, "APPROVED", 5)], BOT, HEAD) is not None
    assert build_request.standing_approval([review(41, "APPROVED", 5)], "", HEAD) is None
    # An entry without a name is nobody's, whatever account is asked for.
    assert build_request.standing_approval([nameless], "", HEAD) is None
    assert build_request.standing_approval([nameless], BOT, HEAD) is None


def test_an_account_without_a_name_matches_no_review(tmp_path):
    result, prompt = merge_only(tmp_path, [review(41, "APPROVED", 5, login="")], REVIEWER_LOGIN="")

    assert merge_path_line(result) == "Merge path: full (the review job did not hand over an approval of this head commit)"
    assert DIRECT_HEADING not in prompt


def test_review_mode_does_not_read_the_listing(tmp_path):
    listing = tmp_path / "reviews.json"
    listing.write_text(json.dumps([[review(41, "APPROVED", 5)]]), encoding="utf-8")
    result, request = build(tmp_path, "review", context_data=clean_context(review_summary=""), MERGE_PATH="direct", REVIEWS_FILE=str(listing), REVIEWER_LOGIN=BOT)

    assert result.returncode == 0, result.stderr
    assert "Merge path" not in result.stdout
    assert DIRECT_HEADING not in json.loads(request.read_text(encoding="utf-8"))["input"]
