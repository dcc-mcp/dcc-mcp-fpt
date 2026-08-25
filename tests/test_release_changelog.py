"""Release changelog regressions."""

from pathlib import Path


def test_release_has_one_project_id_fix_entry_with_both_commits():
    changelog = (Path(__file__).parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
    entries = [line for line in changelog.splitlines() if "resolve project id" in line.lower()]

    assert len(entries) == 1
    assert "fd6d015" in entries[0]
    assert "c25b666" in entries[0]
