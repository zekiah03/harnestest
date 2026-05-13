"""Command-line interface for FavorGame.

Run as ``python -m favorgame <subcommand>``. State is persisted to a JSON
file (defaults to ``favorgame.json`` in the current directory) so successive
CLI calls behave like a real session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from favorgame.errors import FavorGameError
from favorgame.game import Game
from favorgame.models import FavorKind, RequestStatus


def _ok(payload: object) -> int:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    sys.stdout.write("\n")
    return 0


def _err(message: str) -> int:
    sys.stderr.write(f"error: {message}\n")
    return 1


def _game(args: argparse.Namespace) -> Game:
    return Game(path=Path(args.state))


# ----------------------------------------------------------------------
# subcommand handlers
# ----------------------------------------------------------------------
def cmd_register(args: argparse.Namespace) -> int:
    game = _game(args)
    user = game.register(
        args.username,
        display_name=args.display_name or "",
        starting_yen=args.starting_yen,
    )
    game.save()
    return _ok(user.to_dict())


def cmd_topup(args: argparse.Namespace) -> int:
    game = _game(args)
    user = game.user(args.username)
    balance = game.ledger.topup(user.id, args.yen)
    game.save()
    return _ok({"username": args.username, "wallet_yen": balance})


def cmd_request(args: argparse.Namespace) -> int:
    game = _game(args)
    req = game.request_favor(
        requester=args.requester,
        kind=FavorKind.parse(args.kind),
        bounty_yen=args.bounty,
        description=args.description or "",
    )
    game.save()
    return _ok(req.to_dict())


def cmd_accept(args: argparse.Namespace) -> int:
    game = _game(args)
    req = game.accept_favor(accepter=args.accepter, request_id=args.request_id)
    game.save()
    return _ok(req.to_dict())


def cmd_complete(args: argparse.Namespace) -> int:
    game = _game(args)
    req = game.complete_favor(requester=args.requester, request_id=args.request_id)
    game.save()
    return _ok(req.to_dict())


def cmd_cancel(args: argparse.Namespace) -> int:
    game = _game(args)
    req = game.cancel_favor(requester=args.requester, request_id=args.request_id)
    game.save()
    return _ok(req.to_dict())


def cmd_spontaneous(args: argparse.Namespace) -> int:
    game = _game(args)
    act = game.report_spontaneous(
        giver=args.giver,
        receiver=args.receiver,
        kind=FavorKind.parse(args.kind),
        note=args.note or "",
    )
    game.save()
    return _ok(act.to_dict())


def cmd_inbox(args: argparse.Namespace) -> int:
    game = _game(args)
    notes = game.inbox(args.username)
    return _ok([n.to_dict() for n in notes])


def cmd_ignore(args: argparse.Namespace) -> int:
    game = _game(args)
    user = game.user(args.username)
    note = game.repo.get_notification(args.notification_id)
    if note.recipient_id != user.id:
        return _err("notification does not belong to this user")
    note = game.notifications.ignore(args.notification_id)
    game.save()
    return _ok(note.to_dict())


def cmd_leaderboard(args: argparse.Namespace) -> int:
    game = _game(args)
    entries = game.leaderboard(limit=args.limit)
    return _ok(
        [
            {
                "rank": e.rank,
                "username": e.user.username,
                "display_name": e.user.display_name,
                "points": e.user.points,
                "wallet_yen": e.user.wallet_yen,
            }
            for e in entries
        ]
    )


def cmd_requests(args: argparse.Namespace) -> int:
    game = _game(args)
    items = game.repo.list_requests()
    if args.status:
        target = RequestStatus.parse(args.status)
        items = [r for r in items if r.status is target]
    return _ok([r.to_dict() for r in items])


def cmd_show_user(args: argparse.Namespace) -> int:
    game = _game(args)
    user = game.user(args.username)
    return _ok(user.to_dict())


# ----------------------------------------------------------------------
# arg parser
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="favorgame",
        description="A real-world favor exchange game.",
    )
    parser.add_argument(
        "--state",
        default="favorgame.json",
        help="path to the JSON state file (default: favorgame.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("register", help="register a new user")
    p.add_argument("username")
    p.add_argument("--display-name", default="")
    p.add_argument("--starting-yen", type=int, default=0)
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("topup", help="add yen to a wallet")
    p.add_argument("username")
    p.add_argument("yen", type=int)
    p.set_defaults(func=cmd_topup)

    kinds = [k.value for k in FavorKind]

    p = sub.add_parser("request", help="post a paid favor request")
    p.add_argument("requester")
    p.add_argument("kind", choices=kinds)
    p.add_argument("bounty", type=int)
    p.add_argument("--description", default="")
    p.set_defaults(func=cmd_request)

    p = sub.add_parser("accept", help="accept a pending request from your inbox")
    p.add_argument("accepter")
    p.add_argument("request_id", type=int)
    p.set_defaults(func=cmd_accept)

    p = sub.add_parser("complete", help="mark an accepted request complete")
    p.add_argument("requester")
    p.add_argument("request_id", type=int)
    p.set_defaults(func=cmd_complete)

    p = sub.add_parser("cancel", help="cancel a request you posted")
    p.add_argument("requester")
    p.add_argument("request_id", type=int)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("spontaneous", help="report a kind deed without money")
    p.add_argument("giver")
    p.add_argument("receiver")
    p.add_argument("kind", choices=kinds)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_spontaneous)

    p = sub.add_parser("inbox", help="list pending notifications")
    p.add_argument("username")
    p.set_defaults(func=cmd_inbox)

    p = sub.add_parser("ignore", help="ignore a pending notification")
    p.add_argument("username")
    p.add_argument("notification_id", type=int)
    p.set_defaults(func=cmd_ignore)

    p = sub.add_parser("leaderboard", help="show the points leaderboard")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_leaderboard)

    p = sub.add_parser("requests", help="list favor requests")
    p.add_argument("--status", choices=[s.value for s in RequestStatus], default=None)
    p.set_defaults(func=cmd_requests)

    p = sub.add_parser("show-user", help="show a user record")
    p.add_argument("username")
    p.set_defaults(func=cmd_show_user)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FavorGameError as exc:
        return _err(str(exc))
