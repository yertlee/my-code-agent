"""Structured user-input boundary for future pauses and interactive frontends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UserInputRequest:
    request_id: str
    kind: str
    question: str


@dataclass(frozen=True, slots=True)
class UserInputResponse:
    request_id: str
    answer: str


class UserInputPort(Protocol):
    async def ask(self, request: UserInputRequest) -> UserInputResponse: ...
