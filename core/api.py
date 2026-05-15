import csv, io, json, os, secrets, string
from datetime import datetime, timedelta, date
from flask import Blueprint, request, session, jsonify, Response
from core import db, analysis, config, achievements
from core.auth import login_required
from core.analysis import TILE_NAMES

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/profile")
@login_required
def profile():
    uid = session["user_id"]
    stats = analysis.summary_stats(uid)
    farm = db.get_farm(uid)
    streak = analysis.compute_streak(uid)
    return jsonify({"ok": True, "username": session["username"],
                    "streak": streak, "tiles": farm["total_tiles"] if farm else 0, **stats})

@api_bp.route("/farm")
@login_required
def get_farm():
    farm = db.get_farm(session["user_id"])
    if not farm:
        return jsonify({"ok": False, "error": "Farm not found"}), 404
    return jsonify({"ok": True, "tiles": json.loads(farm["tiles_json"]), "total_tiles": farm["total_tiles"]})

@api_bp.route("/sessions/start", methods=["POST"])
@login_required
def start_session():
    uid = session["user_id"]
    data = request.get_json() or {}
    dur = int(data.get("duration_mins", 25))
    dur = max(config.get("MIN_DURATION_MINS", 5), min(config.get("MAX_DURATION_MINS", 60), dur))
    if db.get_active_session(uid):
        return jsonify({"ok": False, "error": "Session already active"}), 400
    now = datetime.utcnow()
    ends = now + timedelta(minutes=dur)
    sid = db.create_session(uid, dur, now.isoformat(), ends.isoformat())
    return jsonify({"ok": True, "session_id": sid, "started_at": now.isoformat(),
                    "ends_at": ends.isoformat(), "duration_mins": dur})

@api_bp.route("/sessions/complete", methods=["POST"])
@login_required
def complete_session():
    uid = session["user_id"]
    data = request.get_json() or {}
    sid = data.get("session_id")
    if not sid:
        return jsonify({"ok": False, "error": "session_id required"}), 400
    sess = db.get_session(sid)
    if not sess or sess["user_id"] != uid:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    if sess["status"] != "active":
        return jsonify({"ok": False, "error": f"Session already {sess['status']}"}), 400
    now = datetime.utcnow()
    elapsed = (now - datetime.fromisoformat(sess["started_at"])).total_seconds()
    if elapsed < sess["duration_mins"] * 60 * config.get("COMPLETION_THRESHOLD", 0.9):
        return jsonify({"ok": False, "error": "Not enough time elapsed"}), 400
    # Snapshot achievements BEFORE completing the session
    before = get_achievements_snapshot(uid)

    tile_index = db.unlock_next_tile(uid)
    db.complete_session(sid, now.isoformat(), tile_index)

    # Find newly unlocked achievements AFTER completing
    newly_unlocked = achievements.get_newly_unlocked(uid, before)

    return jsonify({"ok": True, "tile_index": tile_index,
                    "tile_name": TILE_NAMES[tile_index] if tile_index is not None and tile_index < len(TILE_NAMES) else None,
                    "new_streak": analysis.compute_streak(uid),
                    "new_achievements": newly_unlocked})

@api_bp.route("/sessions/abort", methods=["POST"])
@login_required
def abort_session():
    uid = session["user_id"]
    data = request.get_json() or {}
    sid = data.get("session_id")
    if not sid:
        return jsonify({"ok": False, "error": "session_id required"}), 400
    sess = db.get_session(sid)
    if not sess or sess["user_id"] != uid:
        return jsonify({"ok": False, "error": "Session not found"}), 404
    if sess["status"] != "active":
        return jsonify({"ok": False, "error": "Session not active"}), 400
    db.abort_session(sid)
    return jsonify({"ok": True})

@api_bp.route("/sessions/history")
@login_required
def session_history():
    return jsonify({"ok": True, "sessions": db.get_session_history(session["user_id"], 50)})

@api_bp.route("/sessions/export")
@login_required
def export_sessions():
    rows = db.get_session_history(session["user_id"], 500)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "duration_mins", "started_at", "completed_at", "status", "tile_unlocked"])
    for r in rows:
        w.writerow([r["id"], r["duration_mins"], r["started_at"],
                    r["completed_at"] or "", r["status"], r["tile_unlocked"] or ""])
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=sessions_{session['username']}.csv"})

def _gen_code():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "FARM-" + "".join(secrets.choice(chars) for _ in range(4))

def get_achievements_snapshot(user_id: int):
    """Return list of currently unlocked achievement IDs — used for diff."""
    data = achievements.get_achievements(user_id)
    return [a["id"] for a in data["achievements"] if a["unlocked"]]

@api_bp.route("/squads/create", methods=["POST"])
@login_required
def create_squad():
    uid = session["user_id"]
    data = request.get_json() or {}
    name = (data.get("name") or "").strip() or f"{session['username']}'s Squad"
    code = _gen_code()
    squad_id = db.create_squad(name, code, uid)
    return jsonify({"ok": True, "squad_id": squad_id, "code": code, "name": name})

@api_bp.route("/squads/join", methods=["POST"])
@login_required
def join_squad():
    uid = session["user_id"]
    data = request.get_json() or {}
    code = (data.get("code") or "").strip().upper()
    squad = db.get_squad_by_code(code)
    if not squad:
        return jsonify({"ok": False, "error": "Squad not found"}), 404
    db.join_squad(squad["id"], uid)
    return jsonify({"ok": True, "squad_id": squad["id"], "name": squad["name"], "code": squad["code"]})

@api_bp.route("/squads/status")
@login_required
def squad_status():
    uid = session["user_id"]
    squad = db.get_user_squad(uid)
    if not squad:
        return jsonify({"ok": False, "in_squad": False})
    members = db.get_squad_members(squad["id"])
    now = datetime.utcnow()
    member_data = []
    for m in members:
        active = db.get_active_session(m["id"])
        if active:
            elapsed = (now - datetime.fromisoformat(active["started_at"])).total_seconds()
            total = active["duration_mins"] * 60
            pct = min(100, round(elapsed / total * 100))
            status_label = f"Focusing · {max(0, round((total - elapsed) / 60))}m left"
        else:
            pct, elapsed, status_label = 0, 0, "Idle"
        member_data.append({"user_id": m["id"], "username": m["username"],
                             "is_you": m["id"] == uid, "status": status_label,
                             "progress_pct": pct, "elapsed_mins": round(elapsed / 60) if elapsed else 0})
    team = db.get_team_stats(squad["id"])
    return jsonify({"ok": True, "in_squad": True, "squad_name": squad["name"],
                    "squad_code": squad["code"], "members": member_data,
                    "team_ops": team["total_ops"], "team_mins": team["total_mins"],
                    "member_count": len(members)})
@api_bp.route("/squads/momentum")
@login_required
def squad_momentum():
    uid = session["user_id"]
    squad = db.get_user_squad(uid)
    if not squad:
        return jsonify({"ok": False, "in_squad": False})
    members = db.get_squad_members(squad["id"])
    total_members = len(members)
    if total_members == 0:
        return jsonify({
            "ok": True,
            "momentum": 0,
            "breakdown": []
        })
    today = date.today().isoformat()
    now = datetime.utcnow()
    members_active_today = 0
    sessions_today = 0
    breakdown = []
    for m in members:
        all_sessions = db.get_session_history(m["id"], limit=50)
        today_sessions = [
            s for s in all_sessions
            if s["status"] == "completed"
            and (s["completed_at"] or "")[:10] == today
        ]
        sessions_today += len(today_sessions)
        if len(today_sessions) > 0:
            members_active_today += 1
        completed = [
            s for s in all_sessions
            if s["status"] == "completed"
        ]
        if completed:
            last = completed[0]
            last_dt = datetime.fromisoformat(last["completed_at"])
            days_ago = (now - last_dt).days
            note = (
                "focused today ✓"
                if days_ago == 0
                else f"last focused {days_ago}d ago"
            )
        else:
            note = "hasn't focused yet"
        breakdown.append({
            "username": m["username"],
            "sessions_today": len(today_sessions),
            "note": note,
        })
    team_stats = db.get_team_stats(squad["id"])
    team_ops = team_stats["total_ops"]
    team_streak = min(team_ops // total_members, 10)
    momentum = round(
        (members_active_today / total_members) * 40 +
        min(team_streak * 5, 30) +
        min((sessions_today / total_members) * 10, 30)
    )
    level = (
        "� On ffre!" if momentum >= 80 else
        "� Going strong" if momentum >= 55 else
        "� Getting there" if momentum >= 30 else
        "� Quiet day"
)
    return jsonify({
        "ok": True,
        "momentum": momentum,
        "level": level,
        "members_active_today": members_active_today,
        "total_members": total_members,
        "sessions_today": sessions_today,
        "breakdown": breakdown,
    })

@api_bp.route("/analysis")
@login_required
def get_analysis():
    return jsonify({"ok": True, **analysis.get_analysis(session["user_id"])})

@api_bp.route("/achievements")
@login_required
def get_achievements():
    return jsonify({"ok": True, **achievements.get_achievements(session["user_id"])})
