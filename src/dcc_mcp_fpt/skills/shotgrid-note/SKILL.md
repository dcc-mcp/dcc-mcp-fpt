---
name: shotgrid-note
description: >-
  ShotGrid notes skill — create, read, and update notes linked to entities.
  Use when an AI agent needs to annotate shots, assets, tasks, or versions
  with notes. Not for entity CRUD — use shotgrid-crud for that.
license: MIT
compatibility: "Python 3.8+; dcc-mcp-core 0.18+"
allowed-tools: Bash Read Write Edit
metadata:
  dcc-mcp:
    dcc: fpt
    version: "0.1.0"
    layer: domain
    stage: authoring
    tags: ["notes", "annotation", "communication", "shotgrid"]
    search-hint: "create note, find notes, update note, annotate shot, note on task"
    tools: tools.yaml
---

# ShotGrid Notes

Manage notes linked to ShotGrid entities. Notes support threaded
communication on shots, assets, tasks, and versions.

## Tools

| Tool | Intent |
|------|--------|
| `create_note` | Create a note linked to entities |
| `find_notes` | Find notes for a given entity |
| `update_note` | Update a note's content or subject |

## After Success

- `create_note` returns the new Note entity.
- `find_notes` returns notes for the specified entity.
- `update_note` returns the updated note.

## After Failure

- Verify linked entity exists via `shotgrid-crud__find_one_entity`.
- Verify credentials via `shotgrid-discovery__check_connection`.
