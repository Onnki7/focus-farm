"""
achievements.py — Achievement system for Focus Farm.

Computes personal and squad achievements from session history.
No Flask imports — fully testable in isolation.
All achievement checking is stateless: computed fresh from the database
on each call, so no separate achievements table is needed.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import List, Dict, Any

from core import db

# ── Achievement definitions ───────────────────────────────────────────────────

PERSONAL_ACHIEVEMENTS = [
    # id, icon, title, description, category
    ("first_sprout",     "🌱", "First Sprout",     "Complete your very first session",              "milestone"),
    ("on_fire",          "🔥", "On Fire",           "Reach a 3-day focus streak",                   "streak"),
    ("committed",        "💪", "Committed",         "Reach a 7-day focus streak",                   "streak"),
    ("unstoppable",      "🏆", "Unstoppable",       "Reach a 14-day focus streak",                  "streak"),
    ("early_bird",       "🌅", "Early Bird",        "Complete a session before 9:00 AM",            "habit"),
    ("night_owl",        "🦉", "Night Owl",         "Complete a session after 10:00 PM",            "habit"),
    ("weekend_warrior",  "📅", "Weekend Warrior",   "Focus on both Saturday and Sunday",            "habit"),
    ("harvest_day",      "🌾", "Harvest Day",       "Complete 10 sessions total",                   "milestone"),
    ("farmer",           "🚜", "Farmer",            "Complete 25 sessions total",                   "milestone"),
    ("master_farmer",    "👑", "Master Farmer",     "Complete 50 sessions total",                   "milestone"),
    ("speed_runner",     "⚡", "Speed Runner",      "Complete a 5-minute session",                  "special"),
    ("marathon",         "🧘", "Marathon",          "Complete a 60-minute session",                 "special"),
    ("full_bloom",       "🌻", "Full Bloom",        "Unlock all 20 farm tiles",                     "special"),
    ("century",          "💯", "Century",           "Accumulate 100 total focus minutes",           "time"),
    ("five_hundred",     "⏱️", "500 Club",          "Accumulate 500 total focus minutes",           "time"),
    ("thousand",         "🎯", "Thousand",          "Accumulate 1000 total focus minutes",          "time"),
]

SQUAD_ACHIEVEMENTS = [
    ("squad_up",         "👫", "Squad Up",          "Join or create a squad",                       "squad"),
    ("team_player",      "🤝", "Team Player",       "Focus while a teammate is also focusing",      "squad"),
    ("village",          "🏡", "Village",           "Squad completes 10 sessions combined",         "squad"),
    ("township",         "🌆", "Township",          "Squad completes 30 sessions combined",         "squad"),
    ("dream_team",       "💪", "Dream Team",        "All squad members focus on the same day",      "squad"),
]

ALL_ACHIEVEMENTS = PERSONAL_ACHIEVEMENTS + SQUAD_ACHIEVEMENTS


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_df(rows: list) -> pd.DataFrame:
    """Convert completed session dicts to a DataFrame with parsed timestamps."""
    if not rows:
        return pd.DataFrame(columns=[
            "id", "duration_mins", "started_at", "completed_at",
            "status", "tile_unlocked", "hour", "weekday", "date"
        ])
    df = pd.DataFrame(rows)
    df["completed_at"] = pd.to_datetime(df["completed_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["completed_at"])
    df["hour"]    = df["completed_at"].dt.hour
    df["weekday"] = df["completed_at"].dt.day_name()
    df["date"]    = df["completed_at"].dt.date
    return df


def _compute_streak(df: pd.DataFrame) -> int:
    """Current consecutive-day streak ending today (or yesterday)."""
    if df.empty:
        return 0
    unique_dates = np.array(sorted(df["date"].unique()), dtype="datetime64[D]")
    today = np.datetime64(date.today(), "D")
    if unique_dates[-1] < today - np.timedelta64(1, "D"):
        return 0
    streak, expected = 0, today
    for d in reversed(unique_dates):
        if d == expected:
            streak += 1
            expected -= np.timedelta64(1, "D")
        elif d < expected:
            break
    return streak


# ── Personal achievement checker ──────────────────────────────────────────────

def _check_personal(user_id: int) -> Dict[str, bool]:
    """
    Returns a dict of {achievement_id: bool} for all personal achievements.
    Uses pandas for all session analysis.
    """
    rows = db.get_completed_sessions(user_id)
    df   = _to_df(rows)
    farm = db.get_farm(user_id)
    total_tiles = farm["total_tiles"] if farm else 0

    total_sessions = len(df)
    total_minutes  = int(df["duration_mins"].sum()) if not df.empty else 0
    streak         = _compute_streak(df)

    # Weekend check — has sessions on BOTH Saturday and Sunday
    weekdays_seen = set(df["weekday"].unique()) if not df.empty else set()

    # Hour checks
    has_early = bool((df["hour"] < 9).any())        if not df.empty else False
    has_night = bool((df["hour"] >= 22).any())       if not df.empty else False

    # Duration checks
    durations = df["duration_mins"].values if not df.empty else np.array([])
    has_5min  = bool((durations == 5).any())
    has_60min = bool((durations == 60).any())

    return {
        "first_sprout":    total_sessions >= 1,
        "on_fire":         streak >= 3,
        "committed":       streak >= 7,
        "unstoppable":     streak >= 14,
        "early_bird":      has_early,
        "night_owl":       has_night,
        "weekend_warrior": "Saturday" in weekdays_seen and "Sunday" in weekdays_seen,
        "harvest_day":     total_sessions >= 10,
        "farmer":          total_sessions >= 25,
        "master_farmer":   total_sessions >= 50,
        "speed_runner":    has_5min,
        "marathon":        has_60min,
        "full_bloom":      total_tiles >= 20,
        "century":         total_minutes >= 100,
        "five_hundred":    total_minutes >= 500,
        "thousand":        total_minutes >= 1000,
    }


# ── Squad achievement checker ─────────────────────────────────────────────────

def _check_squad(user_id: int) -> Dict[str, bool]:
    """
    Returns a dict of {achievement_id: bool} for all squad achievements.
    """
    squad = db.get_user_squad(user_id)

    if not squad:
        return {a[0]: False for a in SQUAD_ACHIEVEMENTS}

    squad_id = squad["id"]
    members  = db.get_squad_members(squad_id)
    member_ids = [m["id"] for m in members]

    # Team ops
    team_stats  = db.get_team_stats(squad_id)
    team_ops    = team_stats["total_ops"]

    # Dream team — all members focused on the same calendar day
    # Build a DataFrame of all member sessions
    all_sessions = []
    for mid in member_ids:
        rows = db.get_completed_sessions(mid)
        for r in rows:
            r["_uid"] = mid
            all_sessions.append(r)

    dream_team = False
    if all_sessions and len(member_ids) > 1:
        sdf = _to_df(all_sessions)
        if not sdf.empty:
            # Count distinct members per date
            members_per_day = (
                sdf.groupby("date")["_uid"]
                .nunique()
            )
            dream_team = bool((members_per_day >= len(member_ids)).any())

    # Team player — current user has a completed session on a day
    # when at least one OTHER member also had an active/completed session
    team_player = False
    user_rows = db.get_completed_sessions(user_id)
    user_df   = _to_df(user_rows)
    if not user_df.empty and len(member_ids) > 1:
        user_dates = set(user_df["date"].unique())
        for mid in member_ids:
            if mid == user_id:
                continue
            mate_rows = db.get_completed_sessions(mid)
            mate_df   = _to_df(mate_rows)
            if not mate_df.empty:
                mate_dates = set(mate_df["date"].unique())
                if user_dates & mate_dates:   # intersection — same day
                    team_player = True
                    break

    return {
        "squad_up":    True,           # just being in a squad qualifies
        "team_player": team_player,
        "village":     team_ops >= 10,
        "township":    team_ops >= 30,
        "dream_team":  dream_team,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_achievements(user_id: int) -> Dict[str, Any]:
    """
    Return all achievements with unlock status, grouped by category.
    This is what the /api/achievements endpoint returns.
    """
    personal_unlocked = _check_personal(user_id)
    squad_unlocked    = _check_squad(user_id)
    all_unlocked      = {**personal_unlocked, **squad_unlocked}

    results = []
    for (aid, icon, title, desc, category) in ALL_ACHIEVEMENTS:
        results.append({
            "id":          aid,
            "icon":        icon,
            "title":       title,
            "description": desc,
            "category":    category,
            "unlocked":    all_unlocked.get(aid, False),
        })

    total    = len(results)
    unlocked = sum(1 for r in results if r["unlocked"])

    return {
        "achievements": results,
        "total":        total,
        "unlocked":     unlocked,
        "completion":   round(unlocked / total * 100) if total else 0,
    }


def get_newly_unlocked(user_id: int, previous_ids: List[str]) -> List[Dict]:
    """
    Compare current unlocked achievements against a previous snapshot.
    Returns only achievements newly unlocked since the snapshot.
    Used by the session complete endpoint to surface instant notifications.
    """
    current = get_achievements(user_id)
    current_ids = {a["id"] for a in current["achievements"] if a["unlocked"]}
    prev_ids    = set(previous_ids)
    new_ids     = current_ids - prev_ids

    return [a for a in current["achievements"] if a["id"] in new_ids]
