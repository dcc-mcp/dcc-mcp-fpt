"""Live ShotGrid CRUD smoke test.

This script intentionally requires explicit confirmation before mutating
ShotGrid data. It creates a temporary entity, finds it, updates it, then
retires it.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from dcc_mcp_fpt.access import PermissionLevel, ShotGridAccessPolicy
from dcc_mcp_fpt.client import ShotGridClient


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run a live ShotGrid CRUD smoke test.")
    parser.add_argument(
        "--project", default=os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
    )
    parser.add_argument("--project-id", type=int, default=_env_int("SHOTGRID_PROJECT_ID"))
    parser.add_argument("--entity-type", default=os.environ.get("SHOTGRID_SMOKE_ENTITY_TYPE", "Playlist"))
    parser.add_argument(
        "--confirm", action="store_true", help="Confirm create/update/delete against the configured site."
    )
    parser.add_argument(
        "--keep", action="store_true", help="Leave the created entity in ShotGrid instead of retiring it."
    )
    args = parser.parse_args(argv)

    missing = [
        name for name in ("SHOTGRID_URL", "SHOTGRID_SCRIPT_NAME", "SHOTGRID_SCRIPT_KEY") if not os.environ.get(name)
    ]
    if missing:
        print(f"Skipping live smoke: missing {', '.join(missing)}")
        return 0

    if not args.project and args.project_id is None:
        print("Skipping live smoke: set SHOTGRID_PROJECT or SHOTGRID_PROJECT_ID")
        return 0

    confirmed = args.confirm or _env_truthy("SHOTGRID_LIVE_CRUD_CONFIRM")
    if not confirmed:
        print("Skipping live CRUD mutations: pass --confirm or set SHOTGRID_LIVE_CRUD_CONFIRM=1")
        return 0

    policy = ShotGridAccessPolicy(
        default_level=PermissionLevel.ADMIN,
        project_levels={str(args.project or f"id:{args.project_id}").lower(): PermissionLevel.ADMIN},
    )
    client = ShotGridClient(
        os.environ["SHOTGRID_URL"],
        os.environ["SHOTGRID_SCRIPT_NAME"],
        os.environ["SHOTGRID_SCRIPT_KEY"],
        access_policy=policy,
        default_project=args.project,
        default_project_id=args.project_id,
    )

    created_id = None
    code = f"dcc-mcp-fpt-smoke-{int(time.time())}"
    updated_code = f"{code}-updated"

    try:
        project_ref = client.resolve_project(args.project, args.project_id)
        if project_ref is None:
            raise RuntimeError("Project did not resolve")
        print(f"Resolved project id={project_ref.id}")

        created = client.create(args.entity_type, {"code": code})
        created_id = int(created["id"])
        print(f"Created {args.entity_type} id={created_id}")

        found = client.find_one(args.entity_type, [["id", "is", created_id]], fields=["id", "code", "project"])
        if not found:
            raise RuntimeError(f"Created {args.entity_type} id={created_id} was not found")
        print(f"Found {args.entity_type} id={created_id}")

        updated = client.update(args.entity_type, created_id, {"code": updated_code})
        if updated and updated.get("id") != created_id:
            raise RuntimeError(f"Unexpected update result: {updated}")
        print(f"Updated {args.entity_type} id={created_id}")

        if not args.keep:
            deleted = client.delete(args.entity_type, created_id)
            if not deleted:
                raise RuntimeError(f"Delete returned false for {args.entity_type} id={created_id}")
            print(f"Retired {args.entity_type} id={created_id}")
            created_id = None

        print("Live ShotGrid CRUD smoke passed")
        return 0
    finally:
        if created_id is not None and not args.keep:
            _best_effort_delete(client, args.entity_type, created_id)
        client.close()


def _best_effort_delete(client: ShotGridClient, entity_type: str, entity_id: int) -> None:
    try:
        client.delete(entity_type, entity_id)
    except Exception as exc:
        print(f"Cleanup warning: could not retire {entity_type} id={entity_id}: {exc}", file=sys.stderr)


def _env_int(name: str):
    value = os.environ.get(name)
    if not value:
        return None
    return int(value)


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name)
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
