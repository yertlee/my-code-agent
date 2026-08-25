from __future__ import annotations

import json
from pathlib import Path

import pytest

from coding_agent.cli import main


def test_plain_fake_cli_streams_text(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["-p", "hello", "--fake-response", "streamed"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "streamed\n"
    assert captured.err == ""


def test_json_mode_emits_exactly_one_json_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["-p", "hello", "--fake-response", "机器可读", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert payload["schema_version"] == 1
    assert payload["status"] == "completed"
    assert payload["output_text"] == "机器可读"
    assert payload["verified"] is None
    assert payload["error"] is None


def test_json_config_error_keeps_contract_and_exit_code(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    exit_code = main(
        [
            "-p",
            "hello",
            "--provider",
            "openai-compatible",
            "--model",
            "demo",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert captured.err == ""
    assert payload["status"] == "failed"
    assert payload["stop_reason"] == "config_error"
    assert payload["error"]["kind"] == "config"


def test_json_mode_requires_one_shot_prompt(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert captured.err == ""
    assert payload["stop_reason"] == "config_error"
    assert payload["error"]["message"] == "--json requires -p/--prompt"


def test_fake_readonly_scenario_runs_grep_read_final_loop(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "-p",
            "找到 ProviderErrorKind 的定义",
            "--fake-scenario",
            "readonly",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["status"] == "completed"
    assert payload["tools_used"] == ["Grep", "Read"]
    assert payload["model_calls"] == 3
    assert payload["tool_rounds"] == 2


def test_json_write_scenario_returns_waiting_without_side_effect(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "-p",
            "create demo",
            "--fake-scenario",
            "write",
            "--cwd",
            str(tmp_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 3
    assert captured.err == ""
    assert payload["status"] == "waiting"
    assert payload["pending_input"]["kind"] == "permission_confirmation"
    assert payload["pending_input"]["payload"]["preview"]["operation"] == "create"
    assert not (tmp_path / "m4-demo.txt").exists()
