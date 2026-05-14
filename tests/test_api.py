"""End-to-end tests for the Flask API."""

from __future__ import annotations

import importlib
import json
import sys

import pytest

flask = pytest.importorskip("flask")


@pytest.fixture
def client(monkeypatch):
    # Force a fresh import so we don't accidentally inherit module-level
    # state from a previous test.
    sys.modules.pop("api.index", None)
    sys.modules.pop("api", None)
    module = importlib.import_module("api.index")
    yield module.app.test_client()


def _json(resp):
    return json.loads(resp.get_data(as_text=True))


class TestRoot:
    def test_index_lists_endpoints_and_today(self, client):
        r = client.get("/api")
        assert r.status_code == 200
        d = _json(r)
        assert d["name"] == "oekaki"
        assert "endpoints" in d
        assert d["puzzle_count"] >= 1
        assert "today" in d


class TestCatalogue:
    def test_all_puzzles_returned(self, client):
        d = _json(client.get("/api/puzzles"))
        ids = {p["id"] for p in d}
        assert "heart" in ids
        # Solutions must NOT be exposed via the listing.
        assert all("solution" not in p for p in d)

    def test_filter_by_difficulty(self, client):
        d = _json(client.get("/api/puzzles?difficulty=tiny"))
        assert all(p["difficulty"] == "tiny" for p in d)
        assert len(d) >= 1

    def test_get_specific(self, client):
        r = client.get("/api/puzzles/heart")
        assert r.status_code == 200
        d = _json(r)
        assert d["id"] == "heart"
        assert "solution" not in d

    def test_unknown_returns_404(self, client):
        r = client.get("/api/puzzles/no-such")
        assert r.status_code == 404


class TestToday:
    def test_today_returns_a_puzzle(self, client):
        r = client.get("/api/today")
        assert r.status_code == 200
        d = _json(r)
        assert "row_clues" in d
        assert "col_clues" in d
        assert "date" in d


class TestValidate:
    def test_complete_correct_returns_complete_true(self, client):
        catalog = _json(client.get("/api/puzzles"))
        # Use a small one.
        target = next(p for p in catalog if p["id"] == "heart")
        # The frontend never sees the solution; for this test we cheat
        # via the in-process catalog import.
        from oekaki.puzzles import get_puzzle
        heart = get_puzzle("heart")
        cells = [[1 if v == 1 else 0 for v in row] for row in heart.solution]
        r = client.post("/api/validate", json={"puzzle_id": "heart", "cells": cells})
        d = _json(r)
        assert d["complete"] is True
        assert d["mistakes"] == []

    def test_partial_correct_returns_incomplete(self, client):
        from oekaki.puzzles import get_puzzle
        heart = get_puzzle("heart")
        # Only one cell filled.
        cells = [[-1] * heart.cols for _ in range(heart.rows)]
        for r in range(heart.rows):
            for c in range(heart.cols):
                if heart.solution[r][c] == 1:
                    cells[r][c] = 1
                    break
            else:
                continue
            break
        r2 = client.post("/api/validate", json={"puzzle_id": "heart", "cells": cells})
        d = _json(r2)
        assert d["complete"] is False
        assert d["mistakes"] == []

    def test_mistake_reported(self, client):
        from oekaki.puzzles import get_puzzle
        heart = get_puzzle("heart")
        cells = [[-1] * heart.cols for _ in range(heart.rows)]
        # Pick a cell that should be EMPTY in the solution and mark it FILLED.
        for r in range(heart.rows):
            for c in range(heart.cols):
                if heart.solution[r][c] == 0:
                    cells[r][c] = 1
                    rmistake, cmistake = r, c
                    break
            else:
                continue
            break
        resp = client.post("/api/validate", json={"puzzle_id": "heart", "cells": cells})
        d = _json(resp)
        assert d["complete"] is False
        assert [rmistake, cmistake] in d["mistakes"]

    def test_unknown_puzzle_404(self, client):
        r = client.post("/api/validate", json={"puzzle_id": "no", "cells": []})
        assert r.status_code == 404

    def test_bad_shape_rejected(self, client):
        r = client.post(
            "/api/validate",
            json={"puzzle_id": "heart", "cells": [[1, 2, 3]]},
        )
        assert r.status_code == 400


class TestHint:
    def test_empty_grid_yields_a_hint(self, client):
        from oekaki.puzzles import get_puzzle
        heart = get_puzzle("heart")
        cells = [[-1] * heart.cols for _ in range(heart.rows)]
        r = client.post("/api/hint", json={"puzzle_id": "heart", "cells": cells})
        d = _json(r)
        assert d["hint"] is not None
        assert "r" in d["hint"]
        assert "c" in d["hint"]
        assert d["hint"]["value"] in (0, 1)


class TestSolveEndpoint:
    def test_solve_returns_unique_solution(self, client):
        # 3x3 plus.
        row_clues = [[1], [3], [1]]
        col_clues = [[1], [3], [1]]
        r = client.post("/api/solve", json={"row_clues": row_clues, "col_clues": col_clues})
        assert r.status_code == 200
        assert _json(r)["solution"] == [[0, 1, 0], [1, 1, 1], [0, 1, 0]]

    def test_unsolvable_returns_400(self, client):
        r = client.post("/api/solve", json={"row_clues": [[1]], "col_clues": [[]]})
        assert r.status_code == 400

    def test_missing_payload_400(self, client):
        r = client.post("/api/solve", json={"row_clues": [[1]]})
        assert r.status_code == 400


class TestNoEmojiPayloads:
    """Sanity: no codepoint U+1F000 or above appears in any API surface."""

    def test_no_emoji_anywhere(self, client):
        for path in ("/api", "/api/puzzles", "/api/today",
                     "/api/puzzles/heart"):
            r = client.get(path)
            assert r.status_code == 200, path
            txt = r.get_data(as_text=True)
            offenders = [c for c in txt if ord(c) >= 0x1F000]
            assert not offenders, f"{path} contained {offenders!r}"
