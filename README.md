# 🌾 Focus Farm

> *Grow your farm, one focus session at a time.*

Focus Farm is a gamified productivity web application built with Python and Flask. Complete Pomodoro-style focus sessions to permanently unlock farm tiles — watching a barren field transform into a thriving estate as a visual record of your real-world effort.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🕐 **Focus Timer** | Pomodoro-style countdown (5–60 min) with animated ring |
| 🌾 **Farm Grid** | 20 unlockable tiles drawn on HTML5 Canvas, progressing from soil to manor |
| 🔥 **Streak System** | Tracks consecutive focus days — don't break the chain |
| 👥 **Squad Mode** | Create or join squads, see teammates' live session progress |
| 📊 **Data Analysis** | 14-day trend chart, streak stats, peak hour — powered by pandas & numpy |
| 📋 **Session Log** | Full history with status dots, exportable as CSV |
| 🏆 **Achievements** | 21 personal and squad achievements across 6 categories |
| 📈 **Honesty Graph** | Compare intended vs actual focus time — no sugar coating |
| 🕐 **Quiet Hours** | Personalised focus window recommendation from your own data |
| 💪 **Team Momentum** | Live squad momentum score based on collective activity |

---

## 🖥️ Demo

```
Register an account → Start a session → Complete it → Watch your farm grow
```

Create a squad with a share code (e.g. `FARM-XK7Q`) and invite teammates.  
See each other's progress bars update live on the Squad tab.

---

## 🚀 Quick Start

### Requirements
- Python 3.9 or above
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/focus-farm.git
cd focus-farm

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py

# 4. Open in your browser
# http://localhost:5000
```

The SQLite database (`focus_farm.db`) is created automatically on first run.  
No configuration needed — register any username and password on the login screen.

### Running for the whole team (same WiFi)

```bash
# Change one line in app.py:
app.run(host='0.0.0.0', debug=True, threaded=True, port=5000)

# Teammates open your IP address in their browser:
# http://YOUR_IP:5000
```

Find your IP with `ipconfig` (Windows) or `ipconfig getifaddr en0` (Mac).

---

## 📁 Project Structure

```
focus_farm/
│
├── app.py                  # Flask app factory + entry point
├── config.json             # App settings
├── requirements.txt        # Dependencies: flask, pandas, numpy
│
├── core/
│   ├── db.py               # All SQLite operations (5 tables, thread-safe)
│   ├── auth.py             # Register / login / logout
│   ├── api.py              # 14 REST endpoints
│   ├── analysis.py         # pandas + numpy data analysis
│   ├── achievements.py     # 21 achievement definitions and checks
│   ├── timer.py            # Background session monitor thread
│   ├── config.py           # Config file loader
│   └── routes.py           # Serves index.html
│
├── static/
│   ├── app.js              # All frontend logic
│   └── style.css           # All styling
│
├── templates/
│   └── index.html          # Single-page HTML shell
│
└── exports/                # CSV session exports saved here
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Sign in |
| POST | `/auth/logout` | Sign out |
| GET | `/api/profile` | User stats |
| GET | `/api/farm` | Farm tile state |
| POST | `/api/sessions/start` | Begin a focus session |
| POST | `/api/sessions/complete` | Complete session + unlock tile |
| POST | `/api/sessions/abort` | Abandon session |
| GET | `/api/sessions/history` | Last 50 sessions |
| GET | `/api/sessions/export` | Download CSV |
| POST | `/api/squads/create` | Create a squad |
| POST | `/api/squads/join` | Join by code |
| GET | `/api/squads/status` | Member status + team stats |
| GET | `/api/squads/momentum` | Team momentum score |
| GET | `/api/analysis` | Full analysis data for charts |
| GET | `/api/achievements` | All achievements with unlock status |

---

## 🧠 Knowledge Areas Covered

| Area | Implementation |
|---|---|
| **Web Programming** ★ | Flask HTTP server, 16 REST endpoints, Jinja2 template, Fetch API |
| **Database** | SQLite via `sqlite3` — 5 tables, WAL mode, foreign keys, thread-safe writes |
| **File Operations** | `config.json` read at startup; CSV export via `csv.writer` + `io.StringIO` |
| **Multithreading** | `SessionMonitor(Thread)` daemon; `threading.Lock` for all DB writes |
| **Data Analysis** ★ | pandas groupby/reindex, numpy streak detection, peak-hour rolling window |

★ Mandatory requirements

---

## 🗄️ Database Schema

```
users          — id, username, password_hash, salt, created_at
sessions       — id, user_id, duration_mins, started_at, ends_at,
                 completed_at, status, tile_unlocked
farms          — id, user_id, tiles_json, total_tiles, updated_at
squads         — id, code, name, created_by, created_at
squad_members  — squad_id, user_id, joined_at
```

---

## ⚙️ Configuration

Edit `config.json` to change defaults:

```json
{
  "SECRET_KEY": "change-this-in-production",
  "DATABASE_PATH": "focus_farm.db",
  "DEFAULT_DURATION_MINS": 25,
  "MIN_DURATION_MINS": 5,
  "MAX_DURATION_MINS": 60,
  "COMPLETION_THRESHOLD": 0.9,
  "MAX_FARM_TILES": 20,
  "SESSION_MONITOR_INTERVAL_SECS": 30
}
```

`COMPLETION_THRESHOLD` — fraction of session time that must elapse before completion is accepted (0.9 = 90%). Prevents gaming the system.

---

## 🏆 Achievements

21 achievements across 6 categories:

| Category | Examples |
|---|---|
| 🏅 Milestones | First Sprout, Harvest Day (10 sessions), Master Farmer (50 sessions) |
| 🔥 Streaks | On Fire (3 days), Committed (7 days), Unstoppable (14 days) |
| 📆 Habits | Early Bird (before 9am), Night Owl (after 10pm), Weekend Warrior |
| ✨ Special | Speed Runner (5 min), Marathon (60 min), Full Bloom (all 20 tiles) |
| ⏱️ Time | Century (100 min), 500 Club, Thousand (1000 min) |
| 👥 Squad | Squad Up, Team Player, Village (10 team ops), Dream Team |

---

## 👥 Team

| Member | Role | Responsibilities |
|---|---|---|
| Member 1 | Backend Lead | `app.py`, `auth.py`, `api.py`, `timer.py` |
| Member 2 | Database Engineer | `db.py`, `config.py`, schema design |
| Member 3 | Frontend Developer | `app.js`, `style.css`, `index.html` |
| Member 4 | Analysis Engineer | `analysis.py`, `achievements.py` |

---

## 📦 Dependencies

```
flask>=3.0.0      # Web framework
pandas>=2.0.0     # Data analysis and aggregation
numpy>=1.24.0     # Numerical computing for streak detection
```

Install all with:
```bash
pip install -r requirements.txt
```

---

## 📝 License

This project was built as a Python Programming course team assignment.

---

*Built with 🌱 and lots of focus sessions.*
