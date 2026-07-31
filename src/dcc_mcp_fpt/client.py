"""ShotGrid client backed by the ``fpt`` command-line interface."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Callable, Dict, List, Optional

from dcc_mcp_fpt.access import ProjectRef, ShotGridAccessPolicy
from dcc_mcp_fpt.exceptions import ShotGridConnectionError, ShotGridQueryError
from dcc_mcp_fpt.fpt_cli import resolve_fpt_cli
from dcc_mcp_fpt.models import ShotGridConnectionInfo
from dcc_mcp_fpt.schema_cache import SchemaCache

GLOBAL_ENTITY_TYPES = {
    "ApiUser",
    "Department",
    "EventLogEntry",
    "Group",
    "HumanUser",
    "LocalStorage",
    "Page",
    "PermissionRuleSet",
    "PipelineConfiguration",
    "Project",
    "ScriptUser",
    "Step",
    "TaskTemplate",
}
_CREDENTIAL_ENV_NAMES = (
    "FPT_SITE",
    "FPT_AUTH_MODE",
    "FPT_SCRIPT_NAME",
    "FPT_SCRIPT_KEY",
    "FPT_USERNAME",
    "FPT_PASSWORD",
    "FPT_AUTH_TOKEN",
    "FPT_SESSION_TOKEN",
    "FPT_API_VERSION",
    "SG_SITE",
    "SG_AUTH_MODE",
    "SG_SCRIPT_NAME",
    "SG_SCRIPT_KEY",
    "SG_USERNAME",
    "SG_PASSWORD",
    "SG_AUTH_TOKEN",
    "SG_SESSION_TOKEN",
    "SG_API_VERSION",
)


class ShotGridClient:
    """Keep the adapter's Python contract while delegating transport to ``fpt``."""

    def __init__(
        self,
        url: str,
        script_name: str,
        api_key: str,
        *,
        schema_cache: Optional[SchemaCache] = None,
        access_policy: Optional[ShotGridAccessPolicy] = None,
        default_project: Optional[str] = None,
        default_project_id: Optional[int] = None,
        cli_path: Optional[str] = None,
        timeout: Optional[float] = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self._url = url.rstrip("/")
        self._script_name = script_name
        self._api_key = api_key
        self._schema_cache = schema_cache or SchemaCache()
        self._access_policy = access_policy or ShotGridAccessPolicy.from_env()
        self._default_project = (
            default_project or os.environ.get("SHOTGRID_PROJECT") or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
        )
        self._default_project_id = (
            default_project_id if default_project_id is not None else _env_int("SHOTGRID_PROJECT_ID")
        )
        self._cli_path = cli_path
        self._timeout = timeout or float(os.environ.get("DCC_MCP_FPT_CLI_TIMEOUT", "30"))
        self._runner = runner
        self._connected = False
        self._project_cache: Dict[str, ProjectRef] = {}
        self._entity_project_cache: Dict[str, Optional[ProjectRef]] = {}

    def connect(self) -> None:
        """Verify the configured CLI and credentials."""
        self._execute("auth", "test")
        self._connected = True

    def close(self) -> None:
        """Release local state; the CLI owns its HTTP connections."""
        self._connected = False

    def get_connection_info(self) -> ShotGridConnectionInfo:
        return ShotGridConnectionInfo(
            url=self._url,
            script_name=self._script_name,
            authenticated=self._connected,
        )

    def find(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
        order: Optional[List[Dict[str, str]]] = None,
        limit: int = 500,
        retired_only: bool = False,
        page: int = 1,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> List[Dict[str, Any]]:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        self._access_policy.require(
            "find",
            project_ref=project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        payload = self._execute(
            "entity",
            "find",
            entity_type,
            input_data=_find_input(
                self._with_project_filter(entity_type, filters, project_ref), fields, order, limit, page, retired_only
            ),
        )
        return _entities(payload)

    def find_one(
        self,
        entity_type: str,
        filters: List[Any],
        fields: Optional[List[str]] = None,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Optional[Dict[str, Any]]:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        self._access_policy.require(
            "find_one",
            project_ref=project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        payload = self._execute(
            "entity",
            "find-one",
            entity_type,
            input_data=_find_input(
                self._with_project_filter(entity_type, filters, project_ref), fields, None, 1, 1, False
            ),
        )
        return _entity(_data(payload))

    def create(
        self,
        entity_type: str,
        data: Dict[str, Any],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Dict[str, Any]:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        data = self._with_project_data(entity_type, data, project_ref)
        self._access_policy.require(
            "create",
            project_ref=self._project_from_data(data) or project_ref,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        return _entity_or_empty(self._execute("entity", "create", entity_type, input_data=data))

    def update(
        self,
        entity_type: str,
        entity_id: int,
        data: Dict[str, Any],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> Dict[str, Any]:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        target_project = self._project_from_data(data) or project_ref or self._entity_project(entity_type, entity_id)
        self._access_policy.require(
            "update",
            project_ref=target_project,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        return _entity_or_empty(self._execute("entity", "update", entity_type, str(entity_id), input_data=data))

    def delete(
        self,
        entity_type: str,
        entity_id: int,
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> bool:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        target_project = project_ref or self._entity_project(entity_type, entity_id)
        self._access_policy.require(
            "delete",
            project_ref=target_project,
            project_identifier=project or self._default_project,
            entity_type=entity_type,
        )
        self._execute("entity", "delete", entity_type, str(entity_id), "--yes")
        return True

    def batch(
        self,
        requests: List[Dict[str, Any]],
        *,
        project: Optional[str] = None,
        project_id: Optional[int] = None,
        project_scoped: bool = True,
    ) -> List[Any]:
        project_ref = self.resolve_project(project, project_id) if project_scoped else None
        prepared = [
            self._prepare_batch_request(request, project_ref, project or self._default_project) for request in requests
        ]
        results = []
        for request in prepared:
            request_type = str(request["request_type"]).lower()
            if request_type == "create":
                results.append(self.create(request["entity_type"], request.get("data") or {}, project_scoped=False))
            elif request_type == "update":
                results.append(
                    self.update(
                        request["entity_type"],
                        int(request["entity_id"]),
                        request.get("data") or {},
                        project_scoped=False,
                    )
                )
            elif request_type == "delete":
                results.append(self.delete(request["entity_type"], int(request["entity_id"]), project_scoped=False))
            else:
                raise ShotGridQueryError(f"Unsupported ShotGrid batch request_type: {request_type}")
        return results

    def resolve_project(self, project: Optional[str] = None, project_id: Optional[int] = None) -> Optional[ProjectRef]:
        effective_id = project_id if project_id is not None else self._default_project_id
        effective_project = project or self._default_project
        if effective_id is None and not effective_project:
            return None
        cache_key = f"id:{effective_id}" if effective_id is not None else str(effective_project)
        cached = self._project_cache.get(cache_key.lower())
        if cached is not None:
            return cached
        entity = (
            self.find_one(
                "Project", [["id", "is", effective_id]], ["id", "name", "tank_name", "code"], project_scoped=False
            )
            if effective_id is not None
            else self._find_project_by_identifier(str(effective_project))
        )
        if entity is None:
            raise ShotGridQueryError(f"ShotGrid Project {cache_key} was not found")
        project_ref = ProjectRef(
            id=int(entity["id"]), name=entity.get("name"), code=entity.get("code"), tank_name=entity.get("tank_name")
        )
        for key in project_ref.policy_keys():
            self._project_cache[key.lower()] = project_ref
        return project_ref

    def get_schema(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        cache_key = entity_type or "__all__"
        cached = self._schema_cache.get(cache_key)
        if cached is not None:
            return cached
        command = ("schema", "fields", entity_type) if entity_type else ("schema", "entities")
        schema = self._execute(*command)
        self._schema_cache.set(cache_key, schema)
        return schema

    def get_entity_types(self) -> List[str]:
        data = _data(self.get_schema())
        if isinstance(data, dict):
            return sorted(data)
        if isinstance(data, list):
            names = [_schema_name(item) for item in data]
            return sorted(name for name in names if name)
        return []

    def __enter__(self) -> "ShotGridClient":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _execute(self, *command: str, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            executable = self._cli_path or resolve_fpt_cli()
        except RuntimeError as exc:
            raise ShotGridConnectionError(str(exc)) from exc
        args = [executable, *command]
        if input_data is not None:
            args.extend(("--input", json.dumps(input_data, separators=(",", ":"))))
        args.extend(("--output", "json"))
        try:
            result = self._runner(
                args, capture_output=True, text=True, timeout=self._timeout, env=self._environment(), check=False
            )
        except FileNotFoundError as exc:
            raise ShotGridConnectionError(
                f"fpt CLI was not found at '{self._cli_path}'. Set DCC_MCP_FPT_CLI_PATH to an executable path."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ShotGridConnectionError(f"fpt CLI timed out after {self._timeout:g}s") from exc
        if result.returncode:
            message = _error_message(result.stdout, result.stderr)
            raise ShotGridQueryError(f"fpt {' '.join(command)} failed: {message}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ShotGridQueryError(f"fpt {' '.join(command)} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ShotGridQueryError(f"fpt {' '.join(command)} returned an unexpected JSON shape")
        return payload

    def _environment(self) -> Dict[str, str]:
        environment = os.environ.copy()
        for name in _CREDENTIAL_ENV_NAMES:
            environment.pop(name, None)
        environment.update(
            {
                "FPT_SITE": self._url,
                "FPT_AUTH_MODE": "script",
                "FPT_SCRIPT_NAME": self._script_name,
                "FPT_SCRIPT_KEY": self._api_key,
            }
        )
        return environment

    def _find_project_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        for field in ("name", "tank_name", "code"):
            entity = self.find_one(
                "Project", [[field, "is", identifier]], ["id", "name", "tank_name", "code"], project_scoped=False
            )
            if entity is not None:
                return entity
        return None

    def _with_project_filter(
        self, entity_type: str, filters: List[Any], project_ref: Optional[ProjectRef]
    ) -> List[Any]:
        if project_ref is None or entity_type in GLOBAL_ENTITY_TYPES or _has_project_filter(filters):
            return list(filters or [])
        return list(filters or []) + [["project", "is", project_ref.as_entity_ref()]]

    def _with_project_data(
        self, entity_type: str, data: Dict[str, Any], project_ref: Optional[ProjectRef]
    ) -> Dict[str, Any]:
        result = dict(data)
        if project_ref is not None and entity_type not in GLOBAL_ENTITY_TYPES and "project" not in result:
            result["project"] = project_ref.as_entity_ref()
        return result

    def _project_from_data(self, data: Dict[str, Any]) -> Optional[ProjectRef]:
        value = data.get("project")
        if isinstance(value, dict) and value.get("type") == "Project" and value.get("id"):
            return ProjectRef(
                id=int(value["id"]), name=value.get("name"), code=value.get("code"), tank_name=value.get("tank_name")
            )
        return None

    def _entity_project(self, entity_type: str, entity_id: int) -> Optional[ProjectRef]:
        if entity_type == "Project":
            return ProjectRef(id=entity_id)
        cache_key = f"{entity_type}:{entity_id}"
        if cache_key not in self._entity_project_cache:
            entity = self.find_one(entity_type, [["id", "is", entity_id]], ["id", "project"], project_scoped=False)
            self._entity_project_cache[cache_key] = self._project_from_data(entity or {})
        return self._entity_project_cache[cache_key]

    def _prepare_batch_request(
        self,
        request: Dict[str, Any],
        default_project_ref: Optional[ProjectRef],
        default_project_identifier: Optional[str],
    ) -> Dict[str, Any]:
        prepared = dict(request)
        request_type = str(prepared.get("request_type", "")).lower()
        entity_type = str(prepared.get("entity_type", ""))
        request_project = prepared.pop("project", None)
        request_project_id = prepared.pop("project_id", None)
        project_ref = (
            self.resolve_project(request_project, request_project_id)
            if request_project or request_project_id
            else default_project_ref
        )
        if request_type == "create":
            prepared["data"] = self._with_project_data(entity_type, prepared.get("data") or {}, project_ref)
            target_project = self._project_from_data(prepared["data"]) or project_ref
        elif request_type in {"update", "delete"}:
            target_project = project_ref or self._entity_project(entity_type, int(prepared["entity_id"]))
        else:
            raise ShotGridQueryError(f"Unsupported ShotGrid batch request_type: {request_type}")
        self._access_policy.require(
            request_type,
            project_ref=target_project,
            project_identifier=request_project or default_project_identifier,
            entity_type=entity_type,
        )
        return prepared


def _find_input(
    filters: List[Any],
    fields: Optional[List[str]],
    order: Optional[List[Dict[str, str]]],
    limit: int,
    page: int,
    retired_only: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"search": {"filters": filters}, "page": {"size": limit, "number": page}}
    if fields:
        payload["search"]["fields"] = fields
    if order:
        payload["sort"] = ",".join(
            ("-" if item.get("direction") == "desc" else "") + item["field_name"] for item in order
        )
    if retired_only:
        payload["options"] = {"retired_only": True}
    return payload


def _data(payload: Dict[str, Any]) -> Any:
    return payload.get("data", payload)


def _entities(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = _data(payload)
    return [_entity(item) for item in data] if isinstance(data, list) else []


def _entity_or_empty(payload: Dict[str, Any]) -> Dict[str, Any]:
    entity = _entity(_data(payload))
    return entity or {}


def _entity(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ShotGridQueryError("fpt returned an entity with an unexpected shape")
    attributes = value.get("attributes")
    if not isinstance(attributes, dict):
        return dict(value)
    entity = dict(attributes)
    entity["id"] = value.get("id")
    entity["type"] = value.get("type")
    return entity


def _schema_name(value: Any) -> Optional[str]:
    if not isinstance(value, dict):
        return None
    attributes = value.get("attributes")
    return str(value.get("id") or value.get("type") or (attributes or {}).get("name") or "") or None


def _has_project_filter(filters: List[Any]) -> bool:
    return any(isinstance(item, (list, tuple)) and item and item[0] == "project" for item in filters or [])


def _error_message(stdout: str, stderr: str) -> str:
    for value in (stdout, stderr):
        if value.strip():
            try:
                payload = json.loads(value)
                if isinstance(payload, dict):
                    return str(payload.get("message") or payload.get("error") or value.strip())
            except json.JSONDecodeError:
                pass
            return value.strip()
    return "unknown error"


def _env_int(name: str) -> Optional[int]:
    value = os.environ.get(name)
    return int(value) if value else None
