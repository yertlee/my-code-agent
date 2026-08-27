"""Run the fixed Memory Writer comparison cases and print observable metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from coding_agent.memory.assisted import StructuredExtractionWriter
from coding_agent.memory.base import MemoryWriter
from coding_agent.memory.default import EvidenceMemoryWriter
from coding_agent.memory.models import MemoryObservation
from coding_agent.protocol import ToolResult
from coding_agent.providers import OpenAICompatibleConfig, OpenAICompatibleProvider
from coding_agent.session import tool_result_message

ROOT = Path(__file__).parents[1]
DEFAULT_CASES = ROOT / "evals" / "memory_writer_cases.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare project Memory Writer strategies")
    parser.add_argument("--writer", choices=("evidence", "llm"), required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--model", default=os.getenv("CODING_AGENT_MODEL"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    provider: OpenAICompatibleProvider | None = None
    if args.writer == "llm":
        api_key = os.getenv(str(args.api_key_env))
        if not api_key or not args.model:
            raise SystemExit("llm writer requires API key environment variable and --model")
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                model=str(args.model),
                api_key=api_key,
                base_url=None if args.base_url is None else str(args.base_url),
                include_stream_usage=False,
            )
        )
        writer: MemoryWriter = StructuredExtractionWriter(
            provider=provider,
            model=str(args.model),
        )
    else:
        writer = EvidenceMemoryWriter()
    try:
        report = await _evaluate(writer, _load_cases(args.cases))
    finally:
        if provider is not None:
            await provider.aclose()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        _print_report(report)
    return 0


async def _evaluate(
    writer: MemoryWriter,
    cases: list[dict[str, Any]],
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    totals = {
        "expected": 0,
        "matched": 0,
        "proposed": 0,
        "accepted": 0,
        "rejected": 0,
        "noise": 0,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    for index, case in enumerate(cases, 1):
        metadata = dict(case.get("metadata", {}))
        result = ToolResult(
            f"eval_call_{index}",
            str(case["tool_name"]),
            str(case["content"]),
            is_error=bool(case.get("is_error", False)),
            metadata=metadata,
        )
        message = tool_result_message("eval_session", result, turn_id=f"eval_turn_{index}")
        proposal = await writer.propose(MemoryObservation((message,)))
        combined = "\n".join(candidate.content for candidate in proposal.candidates).casefold()
        expected = case.get("expected_facts", [])
        matches = sum(
            all(str(term).casefold() in combined for term in terms)
            for terms in expected
        )
        noise = len(proposal.candidates) if not expected else 0
        case_result = {
            "id": case["id"],
            "expected": len(expected),
            "matched": matches,
            "proposed": proposal.proposed,
            "accepted": len(proposal.candidates),
            "rejected": proposal.rejected,
            "noise": noise,
            "model_calls": proposal.model_calls,
            "error": proposal.error,
        }
        results.append(case_result)
        totals["expected"] += len(expected)
        totals["matched"] += matches
        totals["proposed"] += proposal.proposed
        totals["accepted"] += len(proposal.candidates)
        totals["rejected"] += proposal.rejected
        totals["noise"] += noise
        totals["model_calls"] += proposal.model_calls
        totals["input_tokens"] += proposal.usage.input_tokens or 0
        totals["output_tokens"] += proposal.usage.output_tokens or 0
    expected_total = totals["expected"]
    totals["fact_recall"] = round(totals["matched"] / expected_total, 4)
    return {"schema_version": 1, "writer": writer.name, "totals": totals, "cases": results}


def _load_cases(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("cases"), list):
        raise ValueError("invalid memory writer evaluation cases")
    return document["cases"]


def _print_report(report: dict[str, object]) -> None:
    print(f"writer: {report['writer']}")
    for case in report["cases"]:  # type: ignore[union-attr]
        print(
            f"{case['id']}: matched={case['matched']}/{case['expected']} "
            f"accepted={case['accepted']} rejected={case['rejected']} "
            f"noise={case['noise']} error={case['error']}"
        )
    totals = report["totals"]
    print(
        f"fact_recall={totals['fact_recall']} accepted={totals['accepted']} "
        f"rejected={totals['rejected']} noise={totals['noise']} "
        f"model_calls={totals['model_calls']} "
        f"tokens={totals['input_tokens']}+{totals['output_tokens']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
