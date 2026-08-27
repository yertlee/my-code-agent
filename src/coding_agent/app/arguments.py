from __future__ import annotations

import argparse

from coding_agent import __version__
from coding_agent.memory.models import MemoryKind
from coding_agent.permissions import PermissionMode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="A small, explainable CLI coding agent",
    )
    parser.add_argument("-p", "--prompt", help="run one prompt and exit")
    parser.add_argument(
        "--provider",
        choices=("fake", "openai-compatible"),
        help="provider adapter (default: CODING_AGENT_PROVIDER or fake)",
    )
    parser.add_argument("--model", help="model name (or CODING_AGENT_MODEL)")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL (or OPENAI_BASE_URL)")
    parser.add_argument("--cwd", default=".", help="workspace root (default: current directory)")
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="environment variable containing the API key",
    )
    parser.add_argument(
        "--no-stream-usage",
        action="store_true",
        help="omit stream_options for services that do not support streamed usage",
    )
    parser.add_argument(
        "--fake-response",
        default="这是 Fake Provider 的响应。",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fake-scenario",
        choices=("text", "readonly", "write"),
        default="text",
        help="deterministic fake scenario for demos and tests",
    )
    parser.add_argument("--max-model-calls", type=int, default=8)
    parser.add_argument("--max-tool-rounds", type=int, default=6)
    parser.add_argument(
        "--context-window",
        type=int,
        help="context window token limit (overrides CODING_AGENT_CONTEXT_WINDOW)",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="turn timeout in seconds")
    parser.add_argument(
        "--permission-mode",
        choices=tuple(mode.value for mode in PermissionMode),
        default=PermissionMode.STANDARD.value,
        help="side-effect policy: plan, standard, or bypass",
    )
    parser.add_argument(
        "--session-dir",
        help="workspace-relative directory for durable JSONL sessions",
    )
    parser.add_argument(
        "--memory-dir",
        help="workspace-relative directory for project memory",
    )
    parser.add_argument(
        "--memory-writer",
        choices=("evidence", "llm"),
        help="automatic project-fact writer strategy (default: evidence)",
    )
    parser.add_argument("--remember", metavar="FACT", help="save one explicit project fact")
    parser.add_argument(
        "--memory-kind",
        choices=tuple(kind.value for kind in MemoryKind),
        default=MemoryKind.DECISION.value,
        help="fact kind used with --remember",
    )
    parser.add_argument("--memory-key", help="stable fact key used with --remember")
    parser.add_argument("--list-memory", action="store_true", help="list project memory")
    parser.add_argument("--inspect-memory", metavar="MEMORY_ID", help="show one memory record")
    parser.add_argument("--forget-memory", metavar="MEMORY_ID", help="forget one memory record")
    parser.add_argument("--resume", metavar="SESSION_ID", help="resume a waiting session")
    parser.add_argument(
        "--permission-choice",
        choices=("deny", "allow_once", "allow_session"),
        help="permission answer used with --resume",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="list durable sessions and their status",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser
