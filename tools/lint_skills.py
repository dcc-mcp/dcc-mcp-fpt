"""Validate bundled dcc-mcp skill metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Lint bundled SKILL.md and tools.yaml files.")
    parser.add_argument(
        "--skills-root",
        default="src/dcc_mcp_fpt/skills",
        help="Directory containing bundled skill folders.",
    )
    args = parser.parse_args(argv)

    root = Path(args.skills_root)
    errors: List[str] = []
    if not root.exists():
        errors.append(f"skills root not found: {root}")
    else:
        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            errors.extend(_lint_skill(skill_dir))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Validated bundled skills in {root}")
    return 0


def _lint_skill(skill_dir: Path) -> List[str]:
    errors: List[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_dir}: missing SKILL.md"]

    try:
        frontmatter = _read_frontmatter(skill_md)
    except ValueError as exc:
        return [f"{skill_md}: {exc}"]

    for key in ("name", "description", "allowed-tools", "metadata"):
        if key not in frontmatter:
            errors.append(f"{skill_md}: missing frontmatter key '{key}'")

    tools_rel = frontmatter.get("metadata", {}).get("dcc-mcp", {}).get("tools", "tools.yaml")
    tools_path = skill_dir / tools_rel
    if not tools_path.exists():
        errors.append(f"{skill_md}: tools file not found: {tools_rel}")
        return errors

    try:
        tools_doc = yaml.safe_load(tools_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{tools_path}: invalid YAML: {exc}")
        return errors

    tools = tools_doc.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append(f"{tools_path}: expected non-empty tools list")
        return errors

    seen = set()
    for tool in tools:
        errors.extend(_lint_tool(skill_dir, tools_path, tool, seen))
    return errors


def _lint_tool(skill_dir: Path, tools_path: Path, tool: Dict[str, Any], seen: set) -> List[str]:
    errors: List[str] = []
    name = tool.get("name", "<unnamed>")
    if name in seen:
        errors.append(f"{tools_path}: duplicate tool name '{name}'")
    seen.add(name)

    for key in ("name", "description", "source_file", "input_schema", "output_schema", "annotations"):
        if key not in tool:
            errors.append(f"{tools_path}: tool '{name}' missing '{key}'")

    source_file = tool.get("source_file")
    if source_file and not (skill_dir / source_file).exists():
        errors.append(f"{tools_path}: tool '{name}' source_file not found: {source_file}")

    input_schema = tool.get("input_schema")
    if isinstance(input_schema, dict):
        if input_schema.get("type") != "object":
            errors.append(f"{tools_path}: tool '{name}' input_schema.type must be object")
        if "properties" not in input_schema:
            errors.append(f"{tools_path}: tool '{name}' input_schema missing properties")
    else:
        errors.append(f"{tools_path}: tool '{name}' input_schema must be an object")

    return errors


def _read_frontmatter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    _, body = text.split("---\n", 1)
    raw, _, _rest = body.partition("\n---")
    if not raw.strip():
        raise ValueError("empty YAML frontmatter")
    parsed = yaml.safe_load(raw) or {}
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
