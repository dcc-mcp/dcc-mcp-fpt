"""Security contracts for the release workflow."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "release.yml"


def test_release_actions_are_commit_pinned_and_jobs_have_minimal_permissions():
    contents = _WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(contents)

    action_refs = re.findall(r"\buses:\s*([^\s#]+)", contents)
    assert action_refs
    assert all(re.search(r"@[0-9a-f]{40}$", action) for action in action_refs)

    assert workflow["permissions"] == {}
    assert workflow["jobs"]["release-please"]["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
    }
    assert workflow["jobs"]["validate-release"]["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["build"]["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["publish"]["permissions"] == {"id-token": "write"}
    assert workflow["jobs"]["attach-release-assets"]["permissions"] == {"contents": "write"}

    publish_actions = [step.get("uses", "") for step in workflow["jobs"]["publish"]["steps"]]
    assert not any(action.startswith("actions/checkout@") for action in publish_actions)
