"""Request-scoped ShotGrid context resolution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from dcc_mcp_fpt.access import PermissionLevel, ShotGridAccessPolicy
from dcc_mcp_fpt.utils import get_shotgrid_env

PROFILE_ENV_NAMES = (
    "DCC_MCP_FPT_CREDENTIAL_PROFILES",
    "SHOTGRID_CREDENTIAL_PROFILES",
)
PROFILE_FILE_ENV_NAMES = (
    "DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE",
    "SHOTGRID_CREDENTIAL_PROFILES_FILE",
)
INLINE_CREDENTIALS_ENV = "DCC_MCP_ALLOW_INLINE_CREDENTIALS"
MAX_CONTEXT_VALUE_LENGTH = 256
META_CONTEXT_KEYS = ("credential_profile", "permission_hint", "project_scope", "project_id")


@dataclass(frozen=True)
class AgentContext:
    """Bounded request identity data supplied via MCP ``_meta``."""

    requester_id: Optional[str] = None
    requester_type: Optional[str] = None
    credential_profile: Optional[str] = None
    permission_hint: Optional[str] = None
    project_scope: Optional[str] = None
    project_id: Optional[int] = None

    @property
    def is_empty(self) -> bool:
        """Return True when no useful context fields were supplied."""
        return not any(
            (
                self.requester_id,
                self.requester_type,
                self.credential_profile,
                self.permission_hint,
                self.project_scope,
                self.project_id is not None,
            )
        )

    def diagnostics(self) -> Dict[str, Any]:
        """Return non-secret context diagnostics."""
        return {
            "requester_id": self.requester_id,
            "requester_type": self.requester_type,
            "credential_profile": self.credential_profile,
            "permission_hint": self.permission_hint,
            "project_scope": self.project_scope,
            "project_id": self.project_id,
        }


@dataclass(frozen=True)
class ShotGridCredentials:
    """Resolved ShotGrid credentials for one request."""

    url: str
    script_name: str
    api_key: str
    source: str = "env_default"
    credential_profile: Optional[str] = None

    def diagnostics(self) -> Dict[str, Any]:
        """Return non-secret credential diagnostics."""
        return {
            "source": self.source,
            "credential_profile": self.credential_profile,
            "url": self.url,
            "script_name": self.script_name,
        }


@dataclass(frozen=True)
class ResolvedRequestContext:
    """Fully resolved ShotGrid client inputs for one tool call."""

    agent_context: AgentContext
    credentials: ShotGridCredentials
    access_policy: ShotGridAccessPolicy
    default_project: Optional[str] = None
    default_project_id: Optional[int] = None

    @property
    def uses_env_default(self) -> bool:
        """Return True when the request did not override env credentials."""
        return self.credentials.source == "env_default" and self.agent_context.is_empty

    def diagnostics(self) -> Dict[str, Any]:
        """Return request diagnostics without credential secrets."""
        return {
            "agent_context": self.agent_context.diagnostics(),
            "credentials": self.credentials.diagnostics(),
            "effective_permission_level": self.access_policy.default_level.value,
            "read_only": self.access_policy.read_only,
            "project": self.default_project,
            "project_id": self.default_project_id,
        }


def resolve_request_context(
    params: Optional[Mapping[str, Any]] = None,
    *,
    base_policy: Optional[ShotGridAccessPolicy] = None,
    default_project: Optional[str] = None,
    default_project_id: Optional[int] = None,
) -> ResolvedRequestContext:
    """Resolve request-scoped credentials, policy, and project scope."""
    params = params or {}
    raw_agent_context = _raw_agent_context(params)
    agent_context = extract_agent_context(params)
    profiles = load_credential_profiles()
    profile = _profile_mapping(profiles, agent_context.credential_profile)
    credentials = _resolve_credentials(agent_context, profile, raw_agent_context)
    access_policy = _resolve_access_policy(agent_context, profile, base_policy)

    project = (
        _bounded_string(agent_context.project_scope)
        or _optional_string(profile.get("project"))
        or _optional_string(profile.get("project_scope"))
        or default_project
        or os.environ.get("SHOTGRID_PROJECT")
        or os.environ.get("SHOTGRID_DEFAULT_PROJECT")
    )
    if agent_context.project_id is not None:
        project_id = agent_context.project_id
    elif profile.get("project_id") is not None:
        project_id = _optional_int(profile.get("project_id"))
    elif default_project_id is not None:
        project_id = default_project_id
    else:
        project_id = _env_int("SHOTGRID_PROJECT_ID")

    return ResolvedRequestContext(
        agent_context=agent_context,
        credentials=credentials,
        access_policy=access_policy,
        default_project=project,
        default_project_id=project_id,
    )


def extract_agent_context(params: Mapping[str, Any]) -> AgentContext:
    """Extract bounded ``agent_context`` from tool params or MCP meta."""
    raw = _raw_agent_context(params)
    if not raw:
        return AgentContext()

    return AgentContext(
        requester_id=_bounded_string(raw.get("requester_id") or raw.get("actor_id") or raw.get("agent_id")),
        requester_type=_bounded_string(raw.get("requester_type")),
        credential_profile=_bounded_string(raw.get("credential_profile")),
        permission_hint=_bounded_string(raw.get("permission_hint")),
        project_scope=_bounded_string(raw.get("project_scope")),
        project_id=_optional_int(raw.get("project_id")),
    )


def load_credential_profiles() -> Dict[str, Dict[str, Any]]:
    """Load profile mappings from JSON env or a JSON profile file."""
    raw = ""
    for name in PROFILE_ENV_NAMES:
        raw = os.environ.get(name, "").strip()
        if raw:
            break

    if not raw:
        for name in PROFILE_FILE_ENV_NAMES:
            path = os.environ.get(name, "").strip()
            if path:
                try:
                    raw = Path(path).read_text(encoding="utf-8")
                except FileNotFoundError as exc:
                    raise ValueError(f"ShotGrid credential profiles file not found: {path}") from exc
                except PermissionError as exc:
                    raise ValueError(f"ShotGrid credential profiles file not readable: {path}") from exc
                except OSError as exc:
                    raise ValueError(f"Failed to read ShotGrid credential profiles file {path}: {exc}") from exc
                break

    if not raw:
        return {}

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("ShotGrid credential profiles must be a JSON object")

    profiles: Dict[str, Dict[str, Any]] = {}
    for key, value in parsed.items():
        if isinstance(value, Mapping):
            profiles[str(key)] = dict(value)
    return profiles


def _resolve_credentials(
    agent_context: AgentContext,
    profile: Mapping[str, Any],
    raw_agent_context: Mapping[str, Any],
) -> ShotGridCredentials:
    if agent_context.credential_profile:
        if not profile:
            raise ValueError(f"Unknown ShotGrid credential_profile: {agent_context.credential_profile}")
        return ShotGridCredentials(
            url=_required_profile_value(profile, "url"),
            script_name=_required_profile_value(profile, "script_name"),
            api_key=_required_profile_value(profile, "script_key", "api_key"),
            source="credential_profile",
            credential_profile=agent_context.credential_profile,
        )

    inline = _inline_credentials(raw_agent_context) or _inline_credentials(profile)
    if inline:
        if not _env_truthy(os.environ.get(INLINE_CREDENTIALS_ENV)):
            raise ValueError(
                f"Inline ShotGrid credentials are disabled. Set {INLINE_CREDENTIALS_ENV}=1 only for local development."
            )
        return inline

    url, script_name, api_key = get_shotgrid_env()
    return ShotGridCredentials(url=url, script_name=script_name, api_key=api_key)


def _resolve_access_policy(
    agent_context: AgentContext,
    profile: Mapping[str, Any],
    base_policy: Optional[ShotGridAccessPolicy],
) -> ShotGridAccessPolicy:
    policy = base_policy or ShotGridAccessPolicy.from_env()
    if profile:
        policy = policy.merge_min(ShotGridAccessPolicy.from_mapping(profile))
    if agent_context.permission_hint:
        hint = ShotGridAccessPolicy(default_level=_permission_hint_level(agent_context.permission_hint))
        policy = policy.merge_min(hint)
    return policy


def _raw_agent_context(params: Mapping[str, Any]) -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    direct = params.get("agent_context")
    if isinstance(direct, Mapping):
        raw.update(direct)

    for meta_key in ("_meta", "meta"):
        meta = params.get(meta_key)
        if not isinstance(meta, Mapping):
            continue
        nested = meta.get("agent_context")
        if isinstance(nested, Mapping):
            raw.update(nested)
        # Core PIP-520 keeps credential/profile controls as bounded top-level
        # _meta fields; agent_context only carries caller identity.
        for key in META_CONTEXT_KEYS:
            if key in meta:
                raw[key] = meta[key]

    for key in META_CONTEXT_KEYS:
        if key in params:
            raw[key] = params[key]
    return raw


def _profile_mapping(
    profiles: Mapping[str, Mapping[str, Any]],
    credential_profile: Optional[str],
) -> Dict[str, Any]:
    if not credential_profile:
        return {}
    profile = profiles.get(credential_profile)
    return dict(profile) if isinstance(profile, Mapping) else {}


def _inline_credentials(profile: Mapping[str, Any]) -> Optional[ShotGridCredentials]:
    credentials = profile.get("credentials") if isinstance(profile, Mapping) else None
    if not isinstance(credentials, Mapping):
        credentials = profile
    url = credentials.get("url") or credentials.get("shotgrid_url")
    script_name = credentials.get("script_name") or credentials.get("shotgrid_script_name")
    api_key = credentials.get("script_key") or credentials.get("api_key") or credentials.get("shotgrid_script_key")
    if not (url and script_name and api_key):
        return None
    return ShotGridCredentials(
        url=str(url),
        script_name=str(script_name),
        api_key=str(api_key),
        source="inline_credentials",
    )


def _required_profile_value(profile: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = profile.get(name)
        if value:
            return str(value)
    raise ValueError(f"ShotGrid credential profile is missing {names[0]}")


def _permission_hint_level(value: str) -> PermissionLevel:
    return ShotGridAccessPolicy.from_mapping({"permission_hint": value}).default_level


def _bounded_string(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:MAX_CONTEXT_VALUE_LENGTH]


def _optional_string(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def _env_int(name: str) -> Optional[int]:
    value = os.environ.get(name)
    if not value:
        return None
    return int(value)


def _env_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
