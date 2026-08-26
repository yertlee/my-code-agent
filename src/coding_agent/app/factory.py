from __future__ import annotations

from coding_agent.agent import AgentLoop, RuntimeLimits
from coding_agent.app.application import AgentApplication
from coding_agent.context import BasicContextBuilder, ContextBuilder
from coding_agent.permissions import PermissionManager, PermissionMode, PermissionPolicy
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import EventSink
from coding_agent.session import InMemorySessionStore, SessionBackend
from coding_agent.tools import ToolContext, ToolRegistry
from coding_agent.workspace import Workspace


def build_application(
    *,
    provider: ChatProvider,
    model: str,
    workspace: Workspace,
    tools: ToolRegistry,
    limits: RuntimeLimits | None = None,
    event_sink: EventSink | None = None,
    permission_mode: PermissionMode = PermissionMode.STANDARD,
    session_store: SessionBackend | None = None,
    context_builder: ContextBuilder | None = None,
    permission_policy: PermissionPolicy | None = None,
) -> AgentApplication:
    session_store = session_store if session_store is not None else InMemorySessionStore()
    context_builder = context_builder if context_builder is not None else BasicContextBuilder()
    permission_manager = PermissionManager(mode=permission_mode, policy=permission_policy)
    loop = AgentLoop(
        provider=provider,
        model=model,
        session_store=session_store,
        context_builder=context_builder,
        permission_manager=permission_manager,
        tool_context=ToolContext(workspace=workspace),
        tools=tools,
        limits=limits,
        event_sink=event_sink,
    )
    return AgentApplication(agent_loop=loop, provider=provider)
