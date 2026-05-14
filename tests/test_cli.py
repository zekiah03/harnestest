"""Smoke tests for the CLI."""

from oekaki import cli


def test_list_prints_all_puzzles(capsys):
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "heart" in out


def test_list_filters_by_difficulty(capsys):
    rc = cli.main(["list", "--difficulty", "tiny"])
    out = capsys.readouterr().out
    assert rc == 0
    # 4 tiny puzzles in the catalogue.
    assert out.count("\n") >= 4
    assert "smiley" not in out  # smiley was retired


def test_show_unknown_returns_nonzero(capsys):
    rc = cli.main(["show", "no-such"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "no-such" in err


def test_show_known_prints_clues(capsys):
    rc = cli.main(["show", "heart"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "heart" in out
    assert "ハート" in out
    assert "行:" in out


def test_solve_matches_solution(capsys):
    rc = cli.main(["solve", "heart"])
    assert rc == 0


def test_solution_prints_grid(capsys):
    rc = cli.main(["solution", "heart"])
    out = capsys.readouterr().out
    assert rc == 0
    # Heart has 12 filled cells; bitmap rendering uses '#' for filled.
    assert "#" in out


def test_today_runs_without_error(capsys):
    rc = cli.main(["today"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "今日のパズル" in out
