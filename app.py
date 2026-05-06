import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from core import config, db
from core.auth import auth_bp
from core.api import api_bp
from core.routes import routes_bp
from core.timer import SessionMonitor

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    cfg = config.load()
    app.secret_key = cfg.get("SECRET_KEY", "dev-secret")
    db.init_db()
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(routes_bp)
    SessionMonitor(interval=cfg.get("SESSION_MONITOR_INTERVAL_SECS", 30)).start()
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
