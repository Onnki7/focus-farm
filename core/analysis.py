"""
analysis.py — Data analysis layer for Focus Farm.

Uses pandas for DataFrame-based session aggregation and numpy for
numerical computations. No Flask imports; fully testable in isolation.

Compatible with Python 3.9+.
"""

from __future__ import annotations  # enables modern type hints on Python 3.9

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Any

from core import db

TILE_NAMES = [
    "Soil patch cleared", "Sprout appeared", "Crop row planted", "Wheat field grown",
    "Fence erected", "Barn built", "Well dug", "Pond filled",
    "Silo raised", "Greenhouse assembled", "Windmill constructed", "Orchard planted",
    "Stable completed", "Beehive placed", "Trough installed", "Market stall opened",
    "Cottage built", "Tree line planted", "Fountain carved", "Manor established"
]


def _sessions_df(user_id: int) -> pd.DataFrame:  # type: ignore[type-arg]
    """
    Load all completed sessions for a user into a pandas DataFrame.
    Parses timestamps and derives helper columns used across analyses.
    """
    rows = db.get_completed_sessions(user_id)
    if not rows:
        return pd.DataFrame(columns=[
            "id", "duration_mins", "started_at", "completed_at",
            "status", "tile_unlocked", "date", "hour", "weekday"
        ])

    df = pd.DataFrame(rows)

    # Parse completed_at as UTC datetime
    df["completed_at"] = pd.to_datetime(df["completed_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["completed_at"])

    # Derived columns used by multiple analyses
    df["date"]    = df["completed_at"].dt.date          # calendar date (date object)
    df["hour"]    = df["completed_at"].dt.hour           # 0–23
    df["weekday"] = df["completed_at"].dt.day_name()    # e.g. "Monday"

    return df


# ── 1. Daily focus minutes ────────────────────────────────────────────────────

def daily_minutes(user_id: int, days: int = 14) -> List[Dict[str, Any]]:
    """
    Return total focus minutes per calendar day for the last `days` days.
    Days with no sessions are zero-filled.

    Uses pandas groupby + sum, then reindexes over a complete date range
    so the result always has exactly `days` entries.
    """
    df = _sessions_df(user_id)

    # Build the full date window
    today = date.today()
    date_range = pd.date_range(
        end=pd.Timestamp(today),
        periods=days,
        freq="D"
    ).date  # array of date objects

    if df.empty:
        return [{"date": str(d), "minutes": 0} for d in date_range]

    # Aggregate: sum duration_mins per date
    daily = (
        df.groupby("date")["duration_mins"]
        .sum()
        .reindex(date_range, fill_value=0)
    )

    return [
        {"date": str(d), "minutes": int(minutes)}
        for d, minutes in daily.items()
    ]


# ── 2. Streak calculation ─────────────────────────────────────────────────────

def compute_streak(user_id: int) -> int:
    """
    Current consecutive-day streak ending today.

    Uses numpy.diff on sorted unique dates to find gaps (diff != 1 day),
    then counts backward from today.
    """
    df = _sessions_df(user_id)
    if df.empty:
        return 0

    # Unique session dates as numpy array of datetime64[D]
    unique_dates = np.array(
        sorted(df["date"].unique()),
        dtype="datetime64[D]"
    )

    today = np.datetime64(date.today(), "D")

    # Must have a session today or yesterday to have a current streak
    if len(unique_dates) == 0 or unique_dates[-1] < today - np.timedelta64(1, "D"):
        return 0

    # Walk backward counting consecutive days
    streak = 0
    expected = today
    for d in reversed(unique_dates):
        if d == expected:
            streak += 1
            expected -= np.timedelta64(1, "D")
        elif d < expected:
            break

    return int(streak)


def longest_streak(user_id: int) -> int:
    """
    All-time longest consecutive-day streak.

    Uses numpy.diff to find gaps between sorted unique session dates,
    then counts the longest run with no gap > 1 day.
    """
    df = _sessions_df(user_id)
    if df.empty:
        return 0

    unique_dates = np.array(
        sorted(df["date"].unique()),
        dtype="datetime64[D]"
    )

    if len(unique_dates) == 1:
        return 1

    # Differences between consecutive dates in days
    gaps = np.diff(unique_dates) / np.timedelta64(1, "D")

    best = 1
    current = 1
    for gap in gaps:
        if gap == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1

    return int(best)


# ── 3. Hourly distribution ────────────────────────────────────────────────────

def hourly_distribution(user_id: int) -> dict:
    """
    Count completed sessions by hour of day (0–23).

    Uses pandas value_counts + reindex to produce a full 24-bucket
    distribution even for hours with no sessions.
    Returns the distribution array and the peak hour index.
    """
    df = _sessions_df(user_id)

    all_hours = pd.Index(range(24))

    if df.empty:
        return {"distribution": [0] * 24, "peak_hour": -1}

    counts = (
        df["hour"]
        .value_counts()
        .reindex(all_hours, fill_value=0)
        .sort_index()
    )

    distribution = counts.tolist()
    peak_hour = int(counts.idxmax()) if counts.sum() > 0 else -1

    return {"distribution": distribution, "peak_hour": peak_hour}


# ── 4. Weekday breakdown ──────────────────────────────────────────────────────

def weekday_breakdown(user_id: int) -> dict:
    """
    Total focus minutes by weekday (Monday–Sunday).

    New analysis not in the plain-Python version.
    Useful for identifying which days of the week the user is most productive.
    """
    df = _sessions_df(user_id)

    ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if df.empty:
        return {"weekday_minutes": {d: 0 for d in ordered_days}, "best_weekday": None}

    breakdown = (
        df.groupby("weekday")["duration_mins"]
        .sum()
        .reindex(ordered_days, fill_value=0)
    )

    best_day = breakdown.idxmax() if breakdown.sum() > 0 else None

    return {
        "weekday_minutes": breakdown.to_dict(),
        "best_weekday": best_day,
    }


# ── 5. Summary statistics ─────────────────────────────────────────────────────

def summary_stats(user_id: int) -> dict:
    """
    Aggregate summary statistics using pandas + numpy.

    Returns total sessions, total minutes, mean session length,
    median session length, and standard deviation — giving a fuller
    picture of focus behaviour than counts alone.
    """
    df = _sessions_df(user_id)

    if df.empty:
        return {
            "total_sessions": 0,
            "total_minutes": 0,
            "mean_duration": 0.0,
            "median_duration": 0.0,
            "std_duration": 0.0,
        }

    durations = df["duration_mins"].astype(float)

    return {
        "total_sessions": int(len(df)),
        "total_minutes":  int(durations.sum()),
        "mean_duration":  round(float(np.mean(durations)), 1),
        "median_duration": round(float(np.median(durations)), 1),
        "std_duration":   round(float(np.std(durations)), 1),
    }

def honesty_graph(user_id: int, days: int = 14) -> dict:
    """
    Compare intended focus time vs actual completed time per day.

    Intended = sum of duration_mins for ALL started sessions
    Actual   = sum of duration_mins for COMPLETED sessions only
    Completion rate = actual / intended * 100
    """
    all_rows = db.get_all_sessions_including_aborted(user_id, days)
    completed_rows = [r for r in all_rows if r["status"] == "completed"]

    if not all_rows:
        return {
            "labels": [],
            "intended": [],
            "actual": [],
            "completion_rate": 0,
            "insight": "No sessions yet — start your first focus session!",
        }

    # Build DataFrames
    df_all  = pd.DataFrame(all_rows)
    df_done = pd.DataFrame(completed_rows) if completed_rows else pd.DataFrame()

    df_all["date"] = pd.to_datetime(
        df_all["started_at"], errors="coerce", utc=True
    ).dt.date

    # Full date range
    today = date.today()
    date_range = pd.date_range(
        end=pd.Timestamp(today), periods=days, freq="D"
    ).date

    # Intended minutes per day (all started sessions)
    intended_by_date = (
        df_all.groupby("date")["duration_mins"]
        .sum()
        .reindex(date_range, fill_value=0)
    )

    # Actual minutes per day (completed only)
    if not df_done.empty:
        df_done["date"] = pd.to_datetime(
            df_done["started_at"], errors="coerce", utc=True
        ).dt.date
        actual_by_date = (
            df_done.groupby("date")["duration_mins"]
            .sum()
            .reindex(date_range, fill_value=0)
        )
    else:
        actual_by_date = pd.Series(0, index=date_range)

    # Overall completion rate
    total_intended  = int(intended_by_date.sum())
    total_actual    = int(actual_by_date.sum())
    completion_rate = round(total_actual / total_intended * 100) \
        if total_intended > 0 else 0

    # Human insight line
    if completion_rate >= 90:
        insight = "Excellent discipline — you follow through almost every time."
    elif completion_rate >= 70:
        insight = f"You complete {completion_rate}% of what you plan. Solid consistency."
    elif completion_rate >= 50:
        insight = f"You complete {completion_rate}% of planned sessions. " \
                  f"Try shorter sessions to boost this."
    else:
        insight = f"Only {completion_rate}% completion. " \
                  f"Consider setting more realistic session lengths."

    return {
        "labels":          [str(d)[5:] for d in date_range],  # MM-DD
        "intended":        intended_by_date.tolist(),
        "actual":          actual_by_date.tolist(),
        "total_intended":  total_intended,
        "total_actual":    total_actual,
        "completion_rate": completion_rate,
        "insight":         insight,
    }

# ── 6. Master analysis response ───────────────────────────────────────────────

def honesty_graph(user_id: int, days: int = 14) -> dict:
    all_rows = db.get_all_sessions_including_aborted(user_id, days)

    completed_rows = [
        r for r in all_rows
        if r["status"] == "completed"
    ]

    if not all_rows:
        return {
            "labels": [],
            "intended": [],
            "actual": [],
            "completion_rate": 0,
            "insight": "No sessions yet — start your first focus session!",
        }

    df_all = pd.DataFrame(all_rows)
    df_done = (
        pd.DataFrame(completed_rows)
        if completed_rows
        else pd.DataFrame()
    )

    df_all["date"] = pd.to_datetime(
        df_all["started_at"],
        errors="coerce",
        utc=True
    ).dt.date

    today = date.today()

    date_range = pd.date_range(
        end=pd.Timestamp(today),
        periods=days,
        freq="D"
    ).date

    intended_by_date = (
        df_all.groupby("date")["duration_mins"]
        .sum()
        .reindex(date_range, fill_value=0)
    )

    if not df_done.empty:
        df_done["date"] = pd.to_datetime(
            df_done["started_at"],
            errors="coerce",
            utc=True
        ).dt.date

        actual_by_date = (
            df_done.groupby("date")["duration_mins"]
            .sum()
            .reindex(date_range, fill_value=0)
        )
    else:
        actual_by_date = pd.Series(0, index=date_range)

    total_intended = int(intended_by_date.sum())
    total_actual = int(actual_by_date.sum())

    completion_rate = (
        round(total_actual / total_intended * 100)
        if total_intended > 0
        else 0
    )

    if completion_rate >= 90:
        insight = "Excellent discipline."
    elif completion_rate >= 70:
        insight = "Solid consistency."
    elif completion_rate >= 50:
        insight = "Try shorter sessions."
    else:
        insight = "Set more realistic goals."

    return {
        "labels": [str(d)[5:] for d in date_range],
        "intended": intended_by_date.tolist(),
        "actual": actual_by_date.tolist(),
        "total_intended": total_intended,
        "total_actual": total_actual,
        "completion_rate": completion_rate,
        "insight": insight,
    }

def get_analysis(user_id: int) -> dict:
    stats   = summary_stats(user_id)
    hourly  = hourly_distribution(user_id)
    weekday = weekday_breakdown(user_id)
    honesty = honesty_graph(user_id)      # ← add this line

    return {
        "daily_minutes":   daily_minutes(user_id),
        "current_streak":  compute_streak(user_id),
        "longest_streak":  longest_streak(user_id),
        "peak_hour":       hourly["peak_hour"],
        "distribution":    hourly["distribution"],
        "weekday_minutes": weekday["weekday_minutes"],
        "best_weekday":    weekday["best_weekday"],
        "honesty":         honesty,        # ← add this line
        **stats,
    }
