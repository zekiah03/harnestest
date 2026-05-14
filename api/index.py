"""Vercel serverless entry point for お絵かきロジック.

A thin Flask wrapper over the ``oekaki`` package. Every request to
``/api/*`` is rewritten to this single file (see ``vercel.json``).

Endpoints
---------
GET  /api                     — service index + endpoint listing
GET  /api/puzzles             — bundled catalogue (no solutions)
GET  /api/puzzles/<id>        — one puzzle (no solution)
GET  /api/today               — today's daily puzzle (no solution)
POST /api/validate            — body: {puzzle_id, cells} → mistakes + completion
POST /api/hint                — body: {puzzle_id, cells} → next deducible cell
POST /api/solve               — body: {row_clues, col_clues} → solution bitmap

Cells in /api/validate and /api/hint are a 2D array where each entry is
one of -1 (unknown), 0 (player marked empty), or 1 (player filled).
"""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, request


# Make the project root importable so this file can be deployed verbatim
# from /api on Vercel.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from oekaki.daily import today_jst, today_puzzle  # noqa: E402
from oekaki.models import Cell, Puzzle  # noqa: E402
from oekaki.puzzles import PUZZLES, get_puzzle, list_puzzles  # noqa: E402
from oekaki.solver import (  # noqa: E402
    SolveError,
    next_deducible,
    solve,
)


app = Flask(__name__)


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.errorhandler(404)
def _not_found(_):
    return _err("not found", status=404)


@app.errorhandler(SolveError)
def _on_solve_error(exc: SolveError):
    return _err(str(exc), status=400)


# ---------------------------------------------------------------- index
@app.route("/api", methods=["GET"])
@app.route("/api/", methods=["GET"])
def root():
    return jsonify({
        "name": "oekaki",
        "version": "0.1.0",
        "today": today_jst().isoformat(),
        "puzzle_count": len(PUZZLES),
        "endpoints": [
            "GET  /api/puzzles?difficulty=<tiny|easy|medium|hard>",
            "GET  /api/puzzles/<id>",
            "GET  /api/today",
            "POST /api/validate     {puzzle_id, cells}",
            "POST /api/hint         {puzzle_id, cells}",
            "POST /api/solve        {row_clues, col_clues}",
        ],
    })


# ---------------------------------------------------------------- catalogue
@app.route("/api/puzzles", methods=["GET"])
def puzzles_index():
    difficulty = request.args.get("difficulty")
    items = list_puzzles(difficulty if difficulty else None)
    return jsonify([p.to_dict(include_solution=False) for p in items])


@app.route("/api/puzzles/<puzzle_id>", methods=["GET"])
def puzzle_by_id(puzzle_id: str):
    p = get_puzzle(puzzle_id)
    if p is None:
        return _err(f"unknown puzzle: {puzzle_id!r}", status=404)
    return jsonify(p.to_dict(include_solution=False))


@app.route("/api/today", methods=["GET"])
def daily():
    p = today_puzzle()
    body = p.to_dict(include_solution=False)
    body["date"] = today_jst().isoformat()
    return jsonify(body)


# ---------------------------------------------------------------- validate
def _coerce_cells(raw, rows: int, cols: int):
    if not isinstance(raw, list) or len(raw) != rows:
        raise ValueError(f"cells must be a {rows}x{cols} array")
    out = []
    for r, row in enumerate(raw):
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError(f"row {r} must have {cols} cells")
        new_row = []
        for c, v in enumerate(row):
            iv = int(v)
            if iv not in (Cell.UNKNOWN, Cell.EMPTY, Cell.FILLED):
                raise ValueError(f"cell ({r},{c}) must be -1, 0, or 1; got {v!r}")
            new_row.append(iv)
        out.append(new_row)
    return out


@app.route("/api/validate", methods=["POST"])
def validate():
    body = request.get_json(silent=True) or {}
    puzzle_id = body.get("puzzle_id")
    p = get_puzzle(puzzle_id) if puzzle_id else None
    if p is None:
        return _err("unknown puzzle_id", status=404)
    try:
        cells = _coerce_cells(body.get("cells"), p.rows, p.cols)
    except ValueError as exc:
        return _err(str(exc))

    # Find mistakes: cells the player marked FILLED or EMPTY that
    # disagree with the unique solution.
    mistakes = []
    for r in range(p.rows):
        for c in range(p.cols):
            v = cells[r][c]
            if v == Cell.UNKNOWN:
                continue
            want = Cell.FILLED if p.solution[r][c] == 1 else Cell.EMPTY
            if v != want:
                mistakes.append([r, c])

    # Completeness check: every FILLED cell in the solution must be marked
    # FILLED by the player (UNKNOWN or EMPTY both fail completeness).
    correct_fills = sum(
        1
        for r in range(p.rows) for c in range(p.cols)
        if cells[r][c] == Cell.FILLED and p.solution[r][c] == 1
    )
    total_fills = p.total_filled()
    complete = (not mistakes) and correct_fills == total_fills

    return jsonify({
        "complete": complete,
        "mistakes": mistakes,
        "filled_progress": correct_fills,
        "filled_total": total_fills,
    })


# ---------------------------------------------------------------- hint
@app.route("/api/hint", methods=["POST"])
def hint():
    body = request.get_json(silent=True) or {}
    puzzle_id = body.get("puzzle_id")
    p = get_puzzle(puzzle_id) if puzzle_id else None
    if p is None:
        return _err("unknown puzzle_id", status=404)
    try:
        cells = _coerce_cells(body.get("cells"), p.rows, p.cols)
    except ValueError as exc:
        return _err(str(exc))
    suggestion = next_deducible(p, cells)
    if suggestion is None:
        return jsonify({"hint": None})
    r, c, v = suggestion
    return jsonify({"hint": {"r": r, "c": c, "value": v}})


# ---------------------------------------------------------------- solve
@app.route("/api/solve", methods=["POST"])
def solve_endpoint():
    body = request.get_json(silent=True) or {}
    row_clues = body.get("row_clues")
    col_clues = body.get("col_clues")
    if not isinstance(row_clues, list) or not isinstance(col_clues, list):
        return _err("row_clues and col_clues must be arrays")
    try:
        solution = solve(row_clues, col_clues)
    except SolveError as exc:
        return _err(str(exc))
    return jsonify({"solution": solution})


# Vercel auto-detects this name.
application = app


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
