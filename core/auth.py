import hashlib, secrets
from functools import wraps
from flask import Blueprint, request, session, jsonify
from core import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def _hash(password, salt):
    return hashlib.sha256((password + salt).encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"ok": False, "error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400
    if len(username) < 2 or len(username) > 24:
        return jsonify({"ok": False, "error": "Username must be 2-24 characters"}), 400
    if len(password) < 4:
        return jsonify({"ok": False, "error": "Password must be at least 4 characters"}), 400
    if db.get_user_by_username(username):
        return jsonify({"ok": False, "error": "Username already taken"}), 409
    salt = secrets.token_hex(8)
    user_id = db.create_user(username, _hash(password, salt), salt)
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"ok": True, "user_id": user_id, "username": username})

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = db.get_user_by_username(username)
    if not user or _hash(password, user["salt"]) != user["password_hash"]:
        return jsonify({"ok": False, "error": "Invalid username or password"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"ok": True, "user_id": user["id"], "username": user["username"]})

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@auth_bp.route("/me")
def me():
    if "user_id" not in session:
        return jsonify({"ok": False, "logged_in": False})
    return jsonify({"ok": True, "logged_in": True,
                    "user_id": session["user_id"], "username": session["username"]})
