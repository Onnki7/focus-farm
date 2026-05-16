import sqlite3, json, os, threading
from datetime import datetime
from core import config

_lock = threading.Lock()

def _connect():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, config.get("DATABASE_PATH", "focus_farm.db"))
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            duration_mins INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            tile_unlocked INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            tiles_json TEXT NOT NULL DEFAULT '[]',
            total_tiles INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS squads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS squad_members (
            squad_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL UNIQUE,
            joined_at TEXT NOT NULL,
            PRIMARY KEY (squad_id, user_id),
            FOREIGN KEY (squad_id) REFERENCES squads(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

# ── Users ──────────────────────────────────────────────────────────────────────
def create_user(username, password_hash, salt):
    conn = _connect()
    now = datetime.utcnow().isoformat()
    with _lock:
        conn.execute("INSERT INTO users (username,password_hash,salt,created_at) VALUES (?,?,?,?)",
                     (username, password_hash, salt, now))
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO farms (user_id,tiles_json,total_tiles,updated_at) VALUES (?,?,?,?)",
                     (user_id, "[]", 0, now))
        conn.commit()
    conn.close()
    return user_id

def get_user_by_username(username):
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ── Sessions ───────────────────────────────────────────────────────────────────
def create_session(user_id, duration_mins, started_at, ends_at):
    conn = _connect()
    with _lock:
        conn.execute("INSERT INTO sessions (user_id,duration_mins,started_at,ends_at,status) VALUES (?,?,?,?,?)",
                     (user_id, duration_mins, started_at, ends_at, "active"))
        conn.commit()
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return sid

def get_session(session_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_active_session(user_id):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM sessions WHERE user_id=? AND status='active' ORDER BY started_at DESC LIMIT 1",
        (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def complete_session(session_id, completed_at, tile_index):
    conn = _connect()
    with _lock:
        conn.execute("UPDATE sessions SET status='completed',completed_at=?,tile_unlocked=? WHERE id=?",
                     (completed_at, tile_index, session_id))
        conn.commit()
    conn.close()

def abort_session(session_id):
    conn = _connect()
    with _lock:
        conn.execute("UPDATE sessions SET status='aborted' WHERE id=?", (session_id,))
        conn.commit()
    conn.close()

def expire_overdue_sessions(now):
    conn = _connect()
    with _lock:
        conn.execute("UPDATE sessions SET status='expired' WHERE status='active' AND ends_at<?", (now,))
        conn.commit()
    conn.close()

def get_session_history(user_id, limit=50):
    conn = _connect()
    rows = conn.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY started_at DESC LIMIT ?",
                        (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_completed_sessions(user_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE user_id=? AND status='completed' ORDER BY completed_at DESC",
        (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_sessions(user_id, days=14):
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM sessions WHERE user_id=? AND status='completed'
           AND completed_at >= datetime('now',?) ORDER BY completed_at ASC""",
        (user_id, f"-{days} days")).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Farm ───────────────────────────────────────────────────────────────────────
def get_farm(user_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM farms WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def unlock_next_tile(user_id):
    farm = get_farm(user_id)
    if not farm:
        return None
    tiles = json.loads(farm["tiles_json"])
    if len(tiles) >= config.get("MAX_FARM_TILES", 20):
        return None
    next_index = len(tiles)
    tiles.append(next_index)
    now = datetime.utcnow().isoformat()
    conn = _connect()
    with _lock:
        conn.execute("UPDATE farms SET tiles_json=?,total_tiles=?,updated_at=? WHERE user_id=?",
                     (json.dumps(tiles), len(tiles), now, user_id))
        conn.commit()
    conn.close()
    return next_index

# ── Squads ─────────────────────────────────────────────────────────────────────
def create_squad(name, code, created_by):
    now = datetime.utcnow().isoformat()
    conn = _connect()
    with _lock:
        conn.execute("INSERT INTO squads (code,name,created_by,created_at) VALUES (?,?,?,?)",
                     (code, name, created_by, now))
        conn.commit()
        squad_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO squad_members (squad_id,user_id,joined_at) VALUES (?,?,?)",
                     (squad_id, created_by, now))
        conn.commit()
    conn.close()
    return squad_id

def get_squad_by_code(code):
    conn = _connect()
    row = conn.execute("SELECT * FROM squads WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_squad(user_id):
    conn = _connect()
    row = conn.execute(
        "SELECT s.* FROM squads s JOIN squad_members sm ON sm.squad_id=s.id WHERE sm.user_id=?",
        (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def join_squad(squad_id, user_id):
    now = datetime.utcnow().isoformat()
    conn = _connect()
    with _lock:
        conn.execute("INSERT OR REPLACE INTO squad_members (squad_id,user_id,joined_at) VALUES (?,?,?)",
                     (squad_id, user_id, now))
        conn.commit()
    conn.close()

def get_squad_members(squad_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT u.id,u.username FROM users u JOIN squad_members sm ON sm.user_id=u.id WHERE sm.squad_id=?",
        (squad_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_team_stats(squad_id):
    conn = _connect()
    row = conn.execute(
        """SELECT COUNT(*) as total_ops, COALESCE(SUM(s.duration_mins),0) as total_mins
           FROM sessions s JOIN squad_members sm ON sm.user_id=s.user_id
           WHERE sm.squad_id=? AND s.status='completed'""",
        (squad_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"total_ops": 0, "total_mins": 0}

def get_all_sessions_including_aborted(user_id, days=14):
    """Fetch both completed AND aborted sessions for honesty graph."""
    conn = _connect()
    rows = conn.execute(
        """SELECT * FROM sessions
           WHERE user_id=?
             AND status IN ('completed', 'aborted', 'expired')
             AND started_at >= datetime('now', ?)
           ORDER BY started_at ASC""",
        (user_id, f"-{days} days")
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
