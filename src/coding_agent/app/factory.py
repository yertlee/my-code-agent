from __future__ import annotations

from coding_agent.agent import AgentLoop, RuntimeLimits
from coding_agent.app.application import AgentApplication
from coding_agent.context import BasicContextBuilder
from coding_agent.memory import EmptyMemoryRetriever
from coding_agent.permissions import ReadOnlyPermissionPolicy
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import EventSink
from coding_agent.session import InMemorySessionStore
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
) -> AgentApplication:
    session_store = InMemorySessionStore()
    memory = EmptyMemoryRetriever()
    context_builder = BasicContextBuilder(workspace_root=workspace.root, memory=memory)
    permission_policy = ReadOnlyPermissionPolicy()
    loop = AgentLoop(
        provider=provider,
        model=model,
        session_store=session_store,
        context_builder=context_builder,
        permission_policy=permission_policy,
        tool_context=ToolContext(workspace=workspace),
        tools=tools,
        limits=limits,
        event_sink=event_sink,
    )
    return AgentApplication(agent_loop=loop, provider=provider)
