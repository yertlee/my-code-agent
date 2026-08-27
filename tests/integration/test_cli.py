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
    assert payload["context"]["context_window"] == 32_768
    assert payload["context"]["budget_exceeded"] is False


def test_cli_context_window_overrides_environment_and_is_reported_in_json(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODING_AGENT_CONTEXT_WINDOW", "16384")

    exit_code = main(
        ["-p", "hello", "--fake-response", "ok", "--context-window", "8192", "--json"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["context"]["context_window"] == 8_192
    assert payload["context"]["input_capacity"] == 4_096


def test_cli_reports_context_budget_stop_in_json_and_terminal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = "x" * 5_000

    json_exit = main(["-p", prompt, "--context-window", "5000", "--json"])
    json_capture = capsys.readouterr()
    payload = json.loads(json_capture.out)
    plain_exit = main(["-p", prompt, "--context-window", "5000"])
    plain_capture = capsys.readouterr()

    assert json_exit == 4
    assert payload["stop_reason"] == "context_budget_exceeded"
    assert payload["context"]["budget_exceeded"] is True
    assert plain_exit == 4
    assert "[context]" in plain_capture.err
    assert "budget_exceeded" in plain_capture.err


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


def test_json_mode_requires_one_operation(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert captured.err == ""
    assert payload["stop_reason"] == "config_error"
    assert payload["error"]["message"] == (
        "--json requires --prompt, --resume, or --list-sessions"
    )


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


def test_json_cli_creates_lists_and_resumes_durable_session(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    common = ["--cwd", str(tmp_path), "--session-dir", ".sessions", "--json"]
    create_exit = main(
        ["-p", "create demo", "--fake-scenario", "write", *common]
    )
    created = json.loads(capsys.readouterr().out)

    assert create_exit == 3
    assert created["status"] == "waiting"
    assert not (tmp_path / "m4-demo.txt").exists()

    list_exit = main(["--list-sessions", *common])
    listed = json.loads(capsys.readouterr().out)
    assert list_exit == 0
    assert listed["sessions"][0]["session_id"] == created["session_id"]
    assert listed["sessions"][0]["status"] == "waiting"

    resume_exit = main(
        [
            "--resume",
            created["session_id"],
            "--permission-choice",
            "allow_once",
            "--fake-scenario",
            "write",
            *common,
        ]
    )
    resumed = json.loads(capsys.readouterr().out)
    assert resume_exit == 0
    assert resumed["status"] == "completed"
    assert resumed["session_id"] == created["session_id"]
    assert (tmp_path / "m4-demo.txt").read_text(encoding="utf-8") == (
        "M4 permission demo\n"
    )
