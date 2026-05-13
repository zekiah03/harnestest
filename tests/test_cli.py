"""End-to-end tests for the CLI."""

import json
from io import StringIO

import pytest

from favorgame import cli


def run(args, capsys):
    rc = cli.main(args)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_register_and_show_user(tmp_path, capsys):
    state = tmp_path / "s.json"
    rc, out, _ = run(
        ["--state", str(state), "register", "alice", "--starting-yen", "500"],
        capsys,
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["username"] == "alice"
    assert payload["wallet_yen"] == 500

    rc, out, _ = run(["--state", str(state), "show-user", "alice"], capsys)
    assert rc == 0
    assert json.loads(out)["wallet_yen"] == 500


def test_full_paid_flow(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob", "carol"):
        run(["--state", str(state), "register", name, "--starting-yen", "1000"], capsys)

    rc, out, _ = run(
        ["--state", str(state), "request", "alice", "seat", "100"], capsys
    )
    assert rc == 0
    req_id = json.loads(out)["id"]

    rc, out, _ = run(
        ["--state", str(state), "accept", "bob", str(req_id)], capsys
    )
    assert rc == 0
    assert json.loads(out)["status"] == "accepted"

    rc, out, _ = run(
        ["--state", str(state), "complete", "alice", str(req_id)], capsys
    )
    assert rc == 0
    assert json.loads(out)["status"] == "completed"

    rc, out, _ = run(
        ["--state", str(state), "show-user", "bob"], capsys
    )
    assert json.loads(out)["wallet_yen"] == 1100
    assert json.loads(out)["points"] == 10


def test_inbox_and_ignore(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob"):
        run(["--state", str(state), "register", name, "--starting-yen", "500"], capsys)
    rc, out, _ = run(
        ["--state", str(state), "request", "alice", "luggage", "100"], capsys
    )
    rc, out, _ = run(["--state", str(state), "inbox", "bob"], capsys)
    notes = json.loads(out)
    assert len(notes) == 1
    nid = notes[0]["id"]

    rc, out, _ = run(
        ["--state", str(state), "ignore", "bob", str(nid)], capsys
    )
    assert rc == 0
    assert json.loads(out)["response"] == "ignored"

    rc, out, _ = run(["--state", str(state), "inbox", "bob"], capsys)
    assert json.loads(out) == []


def test_spontaneous_cli(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob"):
        run(["--state", str(state), "register", name], capsys)
    rc, out, _ = run(
        ["--state", str(state), "spontaneous", "alice", "bob", "seat", "--note", "JR"],
        capsys,
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["giver_delta"] == 5
    assert payload["receiver_delta"] == -2


def test_topup_cli(tmp_path, capsys):
    state = tmp_path / "s.json"
    run(["--state", str(state), "register", "alice"], capsys)
    rc, out, _ = run(["--state", str(state), "topup", "alice", "300"], capsys)
    assert rc == 0
    assert json.loads(out)["wallet_yen"] == 300


def test_cancel_refunds_via_cli(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob"):
        run(["--state", str(state), "register", name, "--starting-yen", "500"], capsys)
    rc, out, _ = run(
        ["--state", str(state), "request", "alice", "seat", "200"], capsys
    )
    req_id = json.loads(out)["id"]

    rc, out, _ = run(["--state", str(state), "show-user", "alice"], capsys)
    assert json.loads(out)["wallet_yen"] == 300

    rc, _, _ = run(
        ["--state", str(state), "cancel", "alice", str(req_id)], capsys
    )
    assert rc == 0
    rc, out, _ = run(["--state", str(state), "show-user", "alice"], capsys)
    assert json.loads(out)["wallet_yen"] == 500


def test_leaderboard_cli(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob", "carol"):
        run(["--state", str(state), "register", name], capsys)
    run(
        ["--state", str(state), "spontaneous", "alice", "bob", "luggage"], capsys
    )
    rc, out, _ = run(["--state", str(state), "leaderboard"], capsys)
    board = json.loads(out)
    # Alice gained 8 from luggage; Bob lost 3.
    assert board[0]["username"] == "alice"
    assert board[0]["points"] == 8
    assert board[-1]["username"] == "bob"
    assert board[-1]["points"] == -3


def test_request_filter_by_status(tmp_path, capsys):
    state = tmp_path / "s.json"
    for name in ("alice", "bob"):
        run(["--state", str(state), "register", name, "--starting-yen", "500"], capsys)
    run(["--state", str(state), "request", "alice", "seat", "100"], capsys)
    rc, out, _ = run(
        ["--state", str(state), "requests", "--status", "open"], capsys
    )
    assert len(json.loads(out)) == 1
    rc, out, _ = run(
        ["--state", str(state), "requests", "--status", "completed"], capsys
    )
    assert json.loads(out) == []


def test_error_reports_to_stderr(tmp_path, capsys):
    state = tmp_path / "s.json"
    rc, _, err = run(["--state", str(state), "show-user", "ghost"], capsys)
    assert rc == 1
    assert "ghost" in err


def test_state_is_persisted_across_invocations(tmp_path, capsys):
    state = tmp_path / "s.json"
    run(["--state", str(state), "register", "alice", "--starting-yen", "100"], capsys)
    # Confirm we read back from the persisted file.
    assert state.exists()
    rc, out, _ = run(["--state", str(state), "show-user", "alice"], capsys)
    assert json.loads(out)["wallet_yen"] == 100
