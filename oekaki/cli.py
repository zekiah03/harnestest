"""Command-line interface for お絵かきロジック.

A small text-mode play loop. Supports:

  oekaki list                 — list bundled puzzles
  oekaki show <id>            — print a puzzle's clues
  oekaki solution <id>        — print a puzzle's solution (cheat sheet)
  oekaki solve <id>           — run the solver and print its answer
  oekaki today                — print today's daily puzzle
  oekaki play <id>            — interactive text play (toggle cells)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional, Sequence

from oekaki.daily import today_jst, today_puzzle
from oekaki.models import Cell, Grid, Puzzle
from oekaki.puzzles import PUZZLES, get_puzzle
from oekaki.solver import next_deducible, solve


# ---- pretty printers --------------------------------------------------
def _format_clues(clue: Sequence[int]) -> str:
    return " ".join(str(c) for c in clue) if clue else "-"


def _format_puzzle_header(p: Puzzle) -> str:
    return (
        f"{p.id}  ({p.title}, {p.rows}x{p.cols}, {p.difficulty})\n"
        f"行: {' | '.join(_format_clues(c) for c in p.row_clues)}\n"
        f"列: {' | '.join(_format_clues(c) for c in p.col_clues)}"
    )


def _render_solution(bitmap, fill="#", empty=".") -> str:
    return "\n".join("".join(fill if v else empty for v in row) for row in bitmap)


def _render_player_grid(grid: Grid) -> str:
    glyph = {Cell.UNKNOWN: "·", Cell.EMPTY: "x", Cell.FILLED: "#"}
    return "\n".join("".join(glyph[v] for v in row) for row in grid.cells)


# ---- subcommands ------------------------------------------------------
def cmd_list(args) -> int:
    for p in PUZZLES:
        if args.difficulty and p.difficulty != args.difficulty:
            continue
        print(f"{p.id:14s} {p.title:10s} {p.rows}x{p.cols:<4d} {p.difficulty}")
    return 0


def cmd_show(args) -> int:
    p = get_puzzle(args.id)
    if p is None:
        print(f"unknown puzzle id: {args.id}", file=sys.stderr)
        return 1
    print(_format_puzzle_header(p))
    return 0


def cmd_solution(args) -> int:
    p = get_puzzle(args.id)
    if p is None:
        print(f"unknown puzzle id: {args.id}", file=sys.stderr)
        return 1
    print(_render_solution(p.solution))
    return 0


def cmd_solve(args) -> int:
    p = get_puzzle(args.id)
    if p is None:
        print(f"unknown puzzle id: {args.id}", file=sys.stderr)
        return 1
    solution = solve(p.row_clues, p.col_clues)
    print(_render_solution(solution))
    return 0 if solution == p.solution else 2


def cmd_today(args) -> int:
    p = today_puzzle()
    print(f"今日のパズル ({today_jst().isoformat()}):")
    print(_format_puzzle_header(p))
    return 0


def cmd_play(args) -> int:
    p = get_puzzle(args.id)
    if p is None:
        print(f"unknown puzzle id: {args.id}", file=sys.stderr)
        return 1
    grid = Grid(rows=p.rows, cols=p.cols)
    print(_format_puzzle_header(p))
    print("\nコマンド: 'f R C' 塗る  'e R C' 印  'c R C' 消す  'h' ヒント  'q' 終了")
    while True:
        print()
        print(_render_player_grid(grid))
        if grid.matches(p.solution):
            print("\nクリア!  おめでとう。")
            return 0
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0].lower()
        if cmd == "q":
            return 0
        if cmd == "h":
            hint = next_deducible(p, grid.cells)
            if hint is None:
                print("論理だけでは進めない。推測してみて。")
            else:
                r, c, v = hint
                label = "塗り" if v == Cell.FILLED else "印"
                print(f"ヒント: ({r}, {c}) は {label}")
            continue
        if cmd in ("f", "e", "c") and len(parts) == 3:
            try:
                r = int(parts[1])
                c = int(parts[2])
            except ValueError:
                print("座標は整数で。")
                continue
            if not (0 <= r < p.rows and 0 <= c < p.cols):
                print("範囲外。")
                continue
            value = {"f": Cell.FILLED, "e": Cell.EMPTY, "c": Cell.UNKNOWN}[cmd]
            grid.set(r, c, value)
            continue
        print("コマンドが分からない。")


# ---- arg parser -------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="oekaki",
        description="お絵かきロジック — daily nonogram puzzles.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="list bundled puzzles")
    sp.add_argument("--difficulty", choices=("tiny", "easy", "medium", "hard"))
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("show", help="print clues for a puzzle")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("solution", help="print the canonical solution")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_solution)

    sp = sub.add_parser("solve", help="run the solver and print its answer")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_solve)

    sp = sub.add_parser("today", help="print today's daily puzzle")
    sp.set_defaults(func=cmd_today)

    sp = sub.add_parser("play", help="text-mode interactive play")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_play)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
