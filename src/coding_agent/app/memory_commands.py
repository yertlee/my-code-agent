from __future__ import annotations

import json

from coding_agent.memory.base import MemoryService
from coding_agent.memory.default import manual_memory_candidate
from coding_agent.memory.models import MemoryKind


async def run_memory_command(
    service: MemoryService,
    *,
    remember: str | None,
    kind: MemoryKind,
    key: str | None,
    list_memory: bool,
    inspect_id: str | None,
    forget_id: str | None,
    json_mode: bool,
) -> int:
    if remember is not None:
        upsert = await service.remember(
            manual_memory_candidate(remember, kind=kind, key=key)
        )
        return _render_payload(
            {
                "action": "remember",
                "created": upsert.created,
                "memory": upsert.record.to_dict(),
            },
            json_mode=json_mode,
        )
    if list_memory:
        records = await service.list_records()
        return _render_payload(
            {"action": "list", "memories": [record.to_dict() for record in records]},
            json_mode=json_mode,
        )
    if inspect_id is not None:
        records = await service.list_records(include_inactive=True)
        record = next((item for item in records if item.id == inspect_id), None)
        if record is None:
            raise ValueError(f"unknown memory: {inspect_id}")
        return _render_payload(
            {"action": "inspect", "memory": record.to_dict()},
            json_mode=json_mode,
        )
    if forget_id is not None:
        if not await service.forget(forget_id):
            raise ValueError(f"unknown memory: {forget_id}")
        return _render_payload(
            {"action": "forget", "memory_id": forget_id, "forgotten": True},
            json_mode=json_mode,
        )
    raise AssertionError("memory command has no selected operation")


def _render_payload(payload: dict[str, object], *, json_mode: bool) -> int:
    document = {"schema_version": 1, **payload}
    memory_value = payload.get("memory")
    if json_mode:
        print(json.dumps(document, ensure_ascii=False, separators=(",", ":")))
    elif payload.get("action") == "list":
        memories = payload.get("memories", [])
        if isinstance(memories, list):
            for memory in memories:
                if isinstance(memory, dict):
                    print(
                        f"{memory['id']}  {memory['kind']}  {memory['status']}  "
                        f"{memory['content']}"
                    )
    elif isinstance(memory_value, dict):
        print(
            f"{memory_value.get('id')}  {memory_value.get('kind')}  "
            f"{memory_value.get('status')}  {memory_value.get('content')}"
        )
    elif payload.get("action") == "forget":
        print(f"forgotten: {payload['memory_id']}")
    return 0
