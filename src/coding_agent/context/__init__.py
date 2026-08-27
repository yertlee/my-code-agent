from coding_agent.context.budget import (
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_OUTPUT_RESERVE,
    ContextBudget,
    ContextProjection,
    ContextProjectionLevel,
    build_context_budget,
)
from coding_agent.context.builder import (
    SYSTEM_GUIDANCE,
    BasicContextBuilder,
    BudgetedContextBuilder,
    ContextBuilder,
    facts_to_model_messages,
)
from coding_agent.context.compaction import (
    TOOL_RESULT_FRACTION,
    CompactionResult,
    ContextCompactor,
    ToolResultLifecycle,
    classify_tool_result_lifecycles,
    compact_tool_result_content,
)
from coding_agent.context.estimator import (
    estimate_message_tokens,
    estimate_snapshot_tokens,
    estimate_text_tokens,
    estimate_tool_definition_tokens,
)
from coding_agent.context.strategy import ContextStrategy, DeterministicContextStrategy

__all__ = [
    "DEFAULT_CONTEXT_WINDOW",
    "DEFAULT_OUTPUT_RESERVE",
    "BasicContextBuilder",
    "BudgetedContextBuilder",
    "ContextBudget",
    "ContextBuilder",
    "ContextCompactor",
    "CompactionResult",
    "ContextProjection",
    "ContextProjectionLevel",
    "ContextStrategy",
    "DeterministicContextStrategy",
    "SYSTEM_GUIDANCE",
    "TOOL_RESULT_FRACTION",
    "ToolResultLifecycle",
    "build_context_budget",
    "classify_tool_result_lifecycles",
    "compact_tool_result_content",
    "estimate_message_tokens",
    "estimate_snapshot_tokens",
    "estimate_text_tokens",
    "estimate_tool_definition_tokens",
    "facts_to_model_messages",
]
