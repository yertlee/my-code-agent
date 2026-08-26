from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class PermissionAction(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHELL = "shell"
    SESSION_STATE = "session_state"


class PermissionMode(StrEnum):
    PLAN = "plan"
    STANDARD = "standard"
    BYPASS = "bypass"


class PermissionVerdict(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionChoice(StrEnum):
    DENY = "deny"
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"


@dataclass(frozen=True, slots=True)
class PermissionRequest:
    request_id: str
    action: PermissionAction
    target: str
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    verdict: PermissionVerdict
    reason: str
    choice: PermissionChoice | None = None


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    action: PermissionAction
    normalized_target: str


class PermissionPolicy(Protocol):
    def decide(self, request: PermissionRequest, *, mode: PermissionMode) -> PermissionDecision: ...


class DefaultPermissionPolicy:
    def decide(self, request: PermissionRequest, *, mode: PermissionMode) -> PermissionDecision:
        if request.action in {PermissionAction.READ, PermissionAction.SESSION_STATE}:
            return PermissionDecision(PermissionVerdict.ALLOW, "non-side-effecting operation")
        if mode is PermissionMode.PLAN:
            return PermissionDecision(PermissionVerdict.DENY, "plan mode blocks side effects")
        if mode is PermissionMode.BYPASS:
            return PermissionDecision(PermissionVerdict.ALLOW, "bypass mode")
        if request.action in {
            PermissionAction.WRITE,
            PermissionAction.DELETE,
            PermissionAction.SHELL,
        }:
            return PermissionDecision(PermissionVerdict.ASK, "user confirmation required")
        return PermissionDecision(PermissionVerdict.DENY, "unknown permission action")


class PermissionManager:
    def __init__(
        self,
        *,
        mode: PermissionMode = PermissionMode.STANDARD,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self.mode = mode
        self.policy = policy or DefaultPermissionPolicy()
        self._grants: list[PermissionGrant] = []

    def preflight(self, request: PermissionRequest) -> PermissionDecision:
        policy_decision = self.policy.decide(request, mode=self.mode)
        if policy_decision.verdict is PermissionVerdict.DENY:
            return policy_decision
        grant = self._matching_grant(request)
        if grant is not None and policy_decision.verdict is PermissionVerdict.ASK:
            return PermissionDecision(PermissionVerdict.ALLOW, "session grant")
        return policy_decision

    def resolve(self, request: PermissionRequest, choice: str) -> PermissionDecision:
        current = self.policy.decide(request, mode=self.mode)
        if current.verdict is not PermissionVerdict.ASK:
            return current
        try:
            selected = PermissionChoice(_normalize_choice(choice))
        except ValueError:
            return PermissionDecision(PermissionVerdict.DENY, f"unknown choice: {choice}")
        if selected is PermissionChoice.DENY:
            return PermissionDecision(PermissionVerdict.DENY, "user denied request", selected)
        if selected is PermissionChoice.ALLOW_SESSION:
            if request.action not in {PermissionAction.WRITE, PermissionAction.DELETE}:
                return PermissionDecision(
                    PermissionVerdict.DENY,
                    "session grants are only supported for Edit paths",
                    selected,
                )
            self._grants.append(
                PermissionGrant(
                    action=request.action,
                    normalized_target=_normalize_target(request.target),
                )
            )
        return PermissionDecision(PermissionVerdict.ALLOW, "user allowed request", selected)

    def _matching_grant(self, request: PermissionRequest) -> PermissionGrant | None:
        normalized = _normalize_target(request.target)
        return next(
            (
                grant
                for grant in self._grants
                if grant.action is request.action and grant.normalized_target == normalized
            ),
            None,
        )


def permission_request(
    action: PermissionAction,
    target: str,
    reason: str,
    **metadata: object,
) -> PermissionRequest:
    return PermissionRequest(
        request_id=f"perm_{uuid4().hex}",
        action=action,
        target=target,
        reason=reason,
        metadata=metadata,
    )


def _normalize_target(value: str) -> str:
    if os.path.isabs(value):
        return os.path.normcase(os.path.normpath(value))
    return os.path.normcase(str(Path(value)))


def _normalize_choice(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    return {
        "n": "deny",
        "no": "deny",
        "1": "deny",
        "y": "allow_once",
        "yes": "allow_once",
        "2": "allow_once",
        "allow": "allow_once",
        "once": "allow_once",
        "3": "allow_session",
        "always": "allow_session",
        "session": "allow_session",
    }.get(normalized, normalized)
