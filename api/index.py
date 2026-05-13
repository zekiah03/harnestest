"""Vercel serverless entry point.

Exposes the favorgame package as a Flask HTTP API. Every request to
``/api/*`` is rewritten to this file (see ``vercel.json``).

State lives in ``/tmp/favorgame.json``. Vercel's ``/tmp`` is writable but
ephemeral — surviving for the lifetime of a warm function instance only.
Cold starts reset to an empty network. Good enough for a demo; swap in
Vercel KV / Postgres if you want anything closer to durable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Allow `import favorgame` when running from /api on Vercel.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from favorgame.errors import FavorGameError  # noqa: E402
from favorgame.game import Game  # noqa: E402
from favorgame.models import (  # noqa: E402
    FavorKind, REACTION_GLYPHS, ReactionTarget, RequestStatus,
)
from favorgame.tiers import status_for as tier_status_for  # noqa: E402
from favorgame.achievements import evaluate_for as evaluate_achievements  # noqa: E402
from favorgame.locations import LOCATIONS, get as get_location  # noqa: E402
from favorgame.multipliers import active_multipliers  # noqa: E402
from favorgame.quests import evaluate_for as evaluate_quests  # noqa: E402
from favorgame.streaks import streak_for  # noqa: E402


STATE_PATH = Path(os.environ.get("FAVORGAME_STATE", "/tmp/favorgame.json"))

app = Flask(__name__)


def _game() -> Game:
    """Construct a Game backed by the configured state path on every call.

    Cheap (just a JSON load) and keeps each request hermetic.
    """
    return Game(path=STATE_PATH)


def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.errorhandler(FavorGameError)
def _handle_domain_error(exc: FavorGameError):
    return _err(str(exc), status=400)


@app.errorhandler(404)
def _not_found(_):
    return _err("not found", status=404)


@app.route("/api", methods=["GET"])
@app.route("/api/", methods=["GET"])
def root():
    return jsonify(
        {
            "name": "favorgame",
            "version": "0.2.0",
            "endpoints": [
                "GET  /api/users",
                "POST /api/users           {username, display_name?, starting_yen?, location?}",
                "POST /api/users/<u>/location  {location}",
                "POST /api/topup           {username, yen}",
                "GET  /api/requests?status=open",
                "POST /api/requests        {requester, kind, bounty_yen, description?}",
                "POST /api/requests/<id>/accept   {accepter}",
                "POST /api/requests/<id>/complete {requester}",
                "POST /api/requests/<id>/cancel   {requester}",
                "POST /api/spontaneous     {giver, receiver, kind, note?}",
                "GET  /api/inbox/<username>",
                "POST /api/notifications/<id>/ignore {username}",
                "GET  /api/leaderboard?limit=N",
                "GET  /api/activity?limit=N",
                "GET  /api/tier/<username>",
                "GET  /api/achievements/<username>",
                "GET  /api/profile/<username>",
                "GET  /api/quests/<username>",
                "GET  /api/streak/<username>",
                "GET  /api/multipliers",
                "GET  /api/locations",
                "POST /api/reactions       {user, target, target_id, glyph}",
                "DELETE /api/reactions     {user, target, target_id}",
                "POST /api/seed?force=true",
            ],
            "kinds": [k.value for k in FavorKind],
            "statuses": [s.value for s in RequestStatus],
            "reaction_glyphs": list(REACTION_GLYPHS),
        }
    )


# ----------------------------------------------------------------------
# users
# ----------------------------------------------------------------------
@app.route("/api/users", methods=["GET"])
def list_users():
    g = _game()
    return jsonify([u.to_dict() for u in g.repo.list_users()])


@app.route("/api/users", methods=["POST"])
def register_user():
    body = request.get_json(silent=True) or {}
    username = body.get("username")
    if not username:
        return _err("username is required")
    g = _game()
    user = g.register(
        username,
        display_name=body.get("display_name", ""),
        starting_yen=int(body.get("starting_yen", 0)),
        location=body.get("location", ""),
    )
    g.save()
    return jsonify(user.to_dict()), 201


@app.route("/api/users/<username>/location", methods=["POST"])
def update_location(username: str):
    body = request.get_json(silent=True) or {}
    if "location" not in body:
        return _err("location is required")
    g = _game()
    user = g.set_location(username, body["location"])
    g.save()
    return jsonify(user.to_dict())


@app.route("/api/topup", methods=["POST"])
def topup():
    body = request.get_json(silent=True) or {}
    username = body.get("username")
    yen = body.get("yen")
    if not username or yen is None:
        return _err("username and yen are required")
    g = _game()
    user = g.user(username)
    balance = g.ledger.topup(user.id, int(yen))
    g.save()
    return jsonify({"username": username, "wallet_yen": balance})


# ----------------------------------------------------------------------
# favor requests
# ----------------------------------------------------------------------
@app.route("/api/requests", methods=["GET"])
def list_requests():
    g = _game()
    items = g.repo.list_requests()
    status = request.args.get("status")
    if status:
        target = RequestStatus.parse(status)
        items = [r for r in items if r.status is target]
    return jsonify([r.to_dict() for r in items])


@app.route("/api/requests", methods=["POST"])
def create_request():
    body = request.get_json(silent=True) or {}
    for field in ("requester", "kind", "bounty_yen"):
        if field not in body:
            return _err(f"{field} is required")
    g = _game()
    req = g.request_favor(
        requester=body["requester"],
        kind=body["kind"],
        bounty_yen=int(body["bounty_yen"]),
        description=body.get("description", ""),
    )
    g.save()
    return jsonify(req.to_dict()), 201


@app.route("/api/requests/<int:request_id>/accept", methods=["POST"])
def accept_request(request_id: int):
    body = request.get_json(silent=True) or {}
    accepter = body.get("accepter")
    if not accepter:
        return _err("accepter is required")
    g = _game()
    req = g.accept_favor(accepter=accepter, request_id=request_id)
    g.save()
    return jsonify(req.to_dict())


@app.route("/api/requests/<int:request_id>/complete", methods=["POST"])
def complete_request(request_id: int):
    body = request.get_json(silent=True) or {}
    requester = body.get("requester")
    if not requester:
        return _err("requester is required")
    g = _game()
    req = g.complete_favor(requester=requester, request_id=request_id)
    g.save()
    return jsonify(req.to_dict())


@app.route("/api/requests/<int:request_id>/cancel", methods=["POST"])
def cancel_request(request_id: int):
    body = request.get_json(silent=True) or {}
    requester = body.get("requester")
    if not requester:
        return _err("requester is required")
    g = _game()
    req = g.cancel_favor(requester=requester, request_id=request_id)
    g.save()
    return jsonify(req.to_dict())


# ----------------------------------------------------------------------
# spontaneous
# ----------------------------------------------------------------------
@app.route("/api/spontaneous", methods=["POST"])
def report_spontaneous():
    body = request.get_json(silent=True) or {}
    for field in ("giver", "receiver", "kind"):
        if field not in body:
            return _err(f"{field} is required")
    g = _game()
    act = g.report_spontaneous(
        giver=body["giver"],
        receiver=body["receiver"],
        kind=body["kind"],
        note=body.get("note", ""),
    )
    g.save()
    return jsonify(act.to_dict()), 201


# ----------------------------------------------------------------------
# notifications
# ----------------------------------------------------------------------
@app.route("/api/inbox/<username>", methods=["GET"])
def inbox(username: str):
    g = _game()
    notes = g.inbox(username)
    return jsonify([n.to_dict() for n in notes])


@app.route("/api/notifications/<int:notification_id>/ignore", methods=["POST"])
def ignore_notification(notification_id: int):
    body = request.get_json(silent=True) or {}
    username = body.get("username")
    if not username:
        return _err("username is required")
    g = _game()
    user = g.user(username)
    note = g.repo.get_notification(notification_id)
    if note.recipient_id != user.id:
        return _err("notification does not belong to this user", status=403)
    note = g.notifications.ignore(notification_id)
    g.save()
    return jsonify(note.to_dict())


# ----------------------------------------------------------------------
# leaderboard
# ----------------------------------------------------------------------
@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    limit_arg = request.args.get("limit")
    limit = int(limit_arg) if limit_arg else None
    g = _game()
    return jsonify(
        [
            {
                "rank": e.rank,
                "username": e.user.username,
                "display_name": e.user.display_name,
                "points": e.user.points,
                "wallet_yen": e.user.wallet_yen,
            }
            for e in g.leaderboard(limit=limit)
        ]
    )


# ----------------------------------------------------------------------
# tier + achievements + profile
# ----------------------------------------------------------------------
@app.route("/api/tier/<username>", methods=["GET"])
def tier_for_user(username: str):
    g = _game()
    user = g.user(username)
    return jsonify(tier_status_for(user.points).to_dict())


@app.route("/api/achievements/<username>", methods=["GET"])
def achievements_for_user(username: str):
    g = _game()
    user = g.user(username)
    return jsonify([s.to_dict() for s in evaluate_achievements(user, g.repo)])


@app.route("/api/profile/<username>", methods=["GET"])
def profile(username: str):
    """One-shot endpoint feeding the user profile card on the frontend."""
    g = _game()
    user = g.user(username)
    tier = tier_status_for(user.points)
    achievements = evaluate_achievements(user, g.repo)
    earned = [a.to_dict() for a in achievements if a.earned]
    in_progress = [
        a.to_dict()
        for a in achievements
        if not a.earned and a.progress > 0
    ]
    locked = [a.to_dict() for a in achievements if a.progress == 0 and not a.earned]
    rank = g.ranking.rank_of(user.id)
    quests = [q.to_dict() for q in evaluate_quests(user, g.repo)]
    streak = streak_for(user, g.repo).to_dict()
    return jsonify({
        "user": user.to_dict(),
        "tier": tier.to_dict(),
        "rank": rank,
        "achievements": {
            "earned": earned,
            "in_progress": in_progress,
            "locked": locked,
            "total": len(achievements),
            "earned_count": len(earned),
        },
        "quests": quests,
        "streak": streak,
        "location": get_location(user.location).to_dict() if user.location else None,
    })


@app.route("/api/quests/<username>", methods=["GET"])
def quests_for_user(username: str):
    g = _game()
    user = g.user(username)
    return jsonify([q.to_dict() for q in evaluate_quests(user, g.repo)])


@app.route("/api/streak/<username>", methods=["GET"])
def streak_for_user(username: str):
    g = _game()
    user = g.user(username)
    return jsonify(streak_for(user, g.repo).to_dict())


@app.route("/api/multipliers", methods=["GET"])
def multipliers():
    """Currently-active reward multipliers across all kinds."""
    active = active_multipliers()
    return jsonify([
        {
            "kind": m.kind.value,
            "factor": m.factor,
            "reason": m.reason,
        }
        for m in active
    ])


@app.route("/api/locations", methods=["GET"])
def locations():
    return jsonify([loc.to_dict() for loc in LOCATIONS])


# ---------------------------------------------------------------------- reactions
@app.route("/api/reactions", methods=["POST"])
def add_reaction():
    body = request.get_json(silent=True) or {}
    for field in ("user", "target", "target_id", "glyph"):
        if field not in body:
            return _err(f"{field} is required")
    g = _game()
    user = g.user(body["user"])
    rx = g.reactions.react(
        user_id=user.id,
        target=body["target"],
        target_id=int(body["target_id"]),
        glyph=body["glyph"],
    )
    g.save()
    return jsonify(rx.to_dict()), 201


@app.route("/api/reactions", methods=["DELETE"])
def remove_reaction():
    body = request.get_json(silent=True) or {}
    for field in ("user", "target", "target_id"):
        if field not in body:
            return _err(f"{field} is required")
    g = _game()
    user = g.user(body["user"])
    removed = g.reactions.remove(
        user_id=user.id, target=body["target"], target_id=int(body["target_id"]),
    )
    g.save()
    return jsonify({"removed": removed})


# ----------------------------------------------------------------------
# seed (demo data)
# ----------------------------------------------------------------------
@app.route("/api/seed", methods=["POST"])
def seed():
    """Populate the network with three personas + sample history so the
    app has something to look at on first visit. By default refuses if
    state is non-empty; pass ``?force=true`` to wipe and re-seed.
    """
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    if STATE_PATH.exists() and not force:
        g = _game()
        if g.repo.list_users():
            return _err("already seeded; pass ?force=true to overwrite", status=409)

    if STATE_PATH.exists():
        STATE_PATH.unlink()
    g = _game()

    # Three personas with hand-picked display names + locations.
    g.register("alice", display_name="山田アリス", starting_yen=2500, location="shinjuku")
    g.register("bob",   display_name="田中タロウ", starting_yen=2000, location="shinjuku")
    g.register("carol", display_name="鈴木ハナ",   starting_yen=1500, location="shibuya")
    g.register("dave",  display_name="高橋ケン",   starting_yen=1800, location="shinjuku")
    g.register("eve",   display_name="松本ユイ",   starting_yen=1200, location="")  # anywhere

    # Spontaneous history — exercises a variety of kinds so the activity
    # feed and achievements feel populated.
    g.report_spontaneous(giver="alice", receiver="bob",   kind=FavorKind.SEAT,         note="JR 山手線")
    g.report_spontaneous(giver="alice", receiver="bob",   kind=FavorKind.SEAT,         note="バス")
    g.report_spontaneous(giver="alice", receiver="carol", kind=FavorKind.LUGGAGE,      note="駅階段で")
    g.report_spontaneous(giver="alice", receiver="carol", kind=FavorKind.CHILD_WATCH,  note="カフェで5分")
    g.report_spontaneous(giver="bob",   receiver="carol", kind=FavorKind.TOILET_ORDER)
    g.report_spontaneous(giver="bob",   receiver="alice", kind=FavorKind.LUGGAGE,      note="お返し")
    g.report_spontaneous(giver="dave",  receiver="eve",   kind=FavorKind.DIRECTIONS,   note="新宿西口で")
    g.report_spontaneous(giver="dave",  receiver="alice", kind=FavorKind.PHOTO,        note="集合写真")
    g.report_spontaneous(giver="eve",   receiver="bob",   kind=FavorKind.UMBRELLA,     note="夕立")
    g.report_spontaneous(giver="bob",   receiver="dave",  kind=FavorKind.CHARGER)
    g.report_spontaneous(giver="alice", receiver="eve",   kind=FavorKind.TRANSLATE,    note="観光客の質問")
    g.report_spontaneous(giver="carol", receiver="dave",  kind=FavorKind.REACH,        note="棚の本")

    # A completed paid request: Alice asks Bob to swap toilet order
    # (both at shinjuku, so the notification fans correctly).
    req_done = g.request_favor(
        requester="alice", kind=FavorKind.TOILET_ORDER, bounty_yen=100,
    )
    g.accept_favor(accepter="bob", request_id=req_done.id)
    g.complete_favor(requester="alice", request_id=req_done.id)

    # An accepted-but-not-yet-completed request: Dave asks Bob to watch
    # his child briefly. Shows up in the active feed.
    req_inflight = g.request_favor(
        requester="dave", kind=FavorKind.CHILD_WATCH, bounty_yen=300,
        description="駅で5分だけ見ててほしい",
    )
    g.accept_favor(accepter="bob", request_id=req_inflight.id)

    # An open request waiting on someone: Carol (shibuya) asks for a
    # seat. Fans only to Eve (ANYWHERE) — demonstrates location filter.
    g.request_favor(
        requester="carol", kind=FavorKind.SEAT, bounty_yen=200,
        description="新幹線で作業したいので",
    )

    # Another open one in shinjuku to give Bob/Dave something live in
    # their inbox.
    g.request_favor(
        requester="alice", kind=FavorKind.LUGGAGE, bounty_yen=150,
        description="スーツケース重い",
    )

    # A few reactions so the activity feed shows them.
    acts = g.repo.list_spontaneous()
    if acts:
        g.reactions.react(
            user_id=g.user("carol").id, target="spontaneous",
            target_id=acts[0].id, glyph="heart",
        )
        g.reactions.react(
            user_id=g.user("eve").id, target="spontaneous",
            target_id=acts[0].id, glyph="clap",
        )

    g.save()
    return jsonify({
        "ok": True,
        "users": [u.to_dict() for u in g.repo.list_users()],
        "message": "seeded 3 personas + 6 spontaneous acts + 3 requests",
    }), 201


# ----------------------------------------------------------------------
# activity feed
# ----------------------------------------------------------------------
@app.route("/api/activity", methods=["GET"])
def activity():
    """Recent events across the network — paid completions, cancels,
    spontaneous acts. Sorted newest first."""
    g = _game()
    users_by_id = {u.id: u for u in g.repo.list_users()}

    def name(uid):
        u = users_by_id.get(uid)
        return u.display_name if u else f"#{uid}"

    events = []
    for tx in g.repo.list_transactions():
        events.append({
            "kind": "paid",
            "at": tx.created_at.isoformat(),
            "ref": {"target": "transaction", "id": tx.id},
            "payer": name(tx.payer_id),
            "payee": name(tx.payee_id),
            "yen": tx.yen_amount,
            "points": tx.point_amount,
            "memo": tx.memo,
            "reactions": g.reactions.summary_for(target="transaction", target_id=tx.id),
        })
    for act in g.repo.list_spontaneous():
        events.append({
            "kind": "spontaneous",
            "at": act.created_at.isoformat(),
            "ref": {"target": "spontaneous", "id": act.id},
            "giver": name(act.giver_id),
            "receiver": name(act.receiver_id),
            "favor": act.kind.value,
            "giver_delta": act.giver_delta,
            "receiver_delta": act.receiver_delta,
            "note": act.note,
            "multiplier": act.multiplier,
            "multiplier_reason": act.multiplier_reason,
            "reactions": g.reactions.summary_for(target="spontaneous", target_id=act.id),
        })
    for req in g.repo.list_requests():
        if req.status is RequestStatus.CANCELLED:
            events.append({
                "kind": "cancelled",
                "at": (req.completed_at or req.accepted_at or req.created_at).isoformat(),
                "ref": None,
                "requester": name(req.requester_id),
                "favor": req.kind.value,
                "yen": req.bounty_yen,
            })
    events.sort(key=lambda e: e["at"], reverse=True)
    limit_arg = request.args.get("limit")
    if limit_arg:
        events = events[: int(limit_arg)]
    return jsonify(events)



# Vercel discovers the WSGI app via this module-level variable.
# (Setting ``application`` as well covers the legacy Vercel runtime alias.)
application = app


if __name__ == "__main__":
    # Local dev: `python -m api.index`
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
