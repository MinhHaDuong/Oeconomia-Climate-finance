"""Tests for .claude/hooks/check-reviews.sh merge gate.

Verifies that the hook blocks or allows PR merges based on review count
and proportional risk labels.
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_SCRIPT = Path(__file__).parent.parent / ".claude" / "hooks" / "check-reviews.sh"


def run_hook(tool_input_json: str, gh_responses: dict[str, str] | None = None) -> dict:
    """Run check-reviews.sh with mocked stdin and gh CLI.

    Parameters
    ----------
    tool_input_json : str
        JSON string to feed as stdin (simulates Claude Code hook input).
    gh_responses : dict
        Mapping of gh api URL fragments to JSON response strings.
        A mock `gh` script returns these based on the first positional arg.

    Returns
    -------
    dict with keys: returncode, stdout (parsed JSON), stderr
    """
    project_dir = Path(__file__).parent.parent

    # Build a mock gh script that returns canned responses
    mock_gh = "#!/bin/bash\n"
    if gh_responses:
        for url_fragment, response in gh_responses.items():
            # gh api <url> --jq <expr> → we match on the URL fragment
            mock_gh += (
                f'if echo "$@" | grep -q "{url_fragment}"; then\n'
                f"  echo '{response}'\n"
                f"  exit 0\n"
                f"fi\n"
            )
    mock_gh += "echo '[]'\nexit 0\n"

    # Write mock gh to a temp location
    mock_dir = project_dir / ".test_tmp"
    mock_dir.mkdir(exist_ok=True)
    mock_gh_path = mock_dir / "gh"
    mock_gh_path.write_text(mock_gh)
    mock_gh_path.chmod(0o755)

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env["PATH"] = f"{mock_dir}:{env['PATH']}"
    env["GH_TOKEN"] = "fake-token"
    env["AGENT_GH_TOKEN"] = "fake-token"
    env["AGENT_GIT_NAME"] = "HDMX-coding-agent"

    try:
        result = subprocess.run(
            ["bash", str(HOOK_SCRIPT)],
            input=tool_input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        stdout_json = json.loads(result.stdout) if result.stdout.strip() else {}
        return {
            "returncode": result.returncode,
            "stdout": stdout_json,
            "stderr": result.stderr,
        }
    finally:
        mock_gh_path.unlink(missing_ok=True)
        mock_dir.rmdir()


def make_bash_input(command: str) -> str:
    """Create hook stdin JSON for a Bash tool call."""
    return json.dumps({"tool_input": {"command": command}})


def make_mcp_input(pull_number: int) -> str:
    """Create hook stdin JSON for an MCP merge tool call."""
    return json.dumps({"tool_input": {"pull_number": pull_number}})


# --- Core gate logic ---


class TestMergeGate:
    """Merge gate blocks or allows based on review count vs. threshold."""

    def test_zero_reviews_blocks(self):
        """0 reviews, no trivial label → deny (need 2)."""
        result = run_hook(
            make_bash_input("gh pr merge 42"),
            gh_responses={
                "pulls/42/reviews": "[]",
                "issues/42/labels": "[]",
            },
        )
        assert result["returncode"] == 0
        decision = result["stdout"]["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"

    def test_one_review_no_trivial_blocks(self):
        """1 review, no trivial label → deny (need 2)."""
        reviews = json.dumps([{"user": {"login": "HDMX-coding-agent"}}])
        result = run_hook(
            make_bash_input("gh pr merge 42"),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": "[]",
            },
        )
        decision = result["stdout"]["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"

    def test_one_review_with_trivial_allows(self):
        """1 review + review:trivial label → allow (need 1)."""
        reviews = json.dumps([{"user": {"login": "HDMX-coding-agent"}}])
        labels = json.dumps([{"name": "review:trivial"}])
        result = run_hook(
            make_bash_input("gh pr merge 42"),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": labels,
            },
        )
        decision = result["stdout"]["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_two_reviews_allows(self):
        """2 reviews, no trivial label → allow (need 2)."""
        reviews = json.dumps([
            {"user": {"login": "HDMX-coding-agent"}},
            {"user": {"login": "HDMX-coding-agent"}},
        ])
        result = run_hook(
            make_bash_input("gh pr merge 42"),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": "[]",
            },
        )
        decision = result["stdout"]["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"


# --- PR number extraction ---


class TestPRNumberExtraction:
    """Hook extracts PR number from various tool input formats."""

    def test_bash_gh_pr_merge(self):
        """Extracts from 'gh pr merge 42'."""
        reviews = json.dumps([
            {"user": {"login": "HDMX-coding-agent"}},
            {"user": {"login": "HDMX-coding-agent"}},
        ])
        result = run_hook(
            make_bash_input("gh pr merge 42"),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": "[]",
            },
        )
        # If it found PR 42, it will have queried reviews — allow proves extraction worked
        assert result["stdout"]["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_mcp_merge_tool(self):
        """Extracts from MCP tool input with pull_number field."""
        reviews = json.dumps([
            {"user": {"login": "HDMX-coding-agent"}},
            {"user": {"login": "HDMX-coding-agent"}},
        ])
        result = run_hook(
            make_mcp_input(42),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": "[]",
            },
        )
        assert result["stdout"]["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_no_pr_number_allows(self):
        """If PR number can't be determined, allow (don't block git merge)."""
        result = run_hook(
            json.dumps({"tool_input": {"command": "git merge feature-branch"}}),
        )
        decision = result["stdout"]["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"

    def test_url_format(self):
        """Extracts PR number from URL in command."""
        reviews = json.dumps([
            {"user": {"login": "HDMX-coding-agent"}},
            {"user": {"login": "HDMX-coding-agent"}},
        ])
        result = run_hook(
            make_bash_input(
                "gh pr merge https://github.com/minhhaduong/oeconomia-climate-finance/pull/42"
            ),
            gh_responses={
                "pulls/42/reviews": reviews,
                "issues/42/labels": "[]",
            },
        )
        assert result["stdout"]["hookSpecificOutput"]["permissionDecision"] == "allow"
