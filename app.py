"""Abraham Bike warranty application for local use and Vercel."""

import hashlib
import hmac
import os
import re
import sqlite3
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DATABASE_PATH = Path(os.environ.get("WARRANTY_DB_PATH", DATA_DIR / "warranties.db"))
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("POSTGRES_URL_NON_POOLING")
    or ""
).strip()
IS_VERCEL = bool(os.environ.get("VERCEL"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")
DEFAULT_SECRET = hashlib.sha256(f"abraham-admin:{ADMIN_PASSWORD}".encode()).hexdigest()
PHONE_PATTERN = re.compile(r"^(0|\+84)[0-9]{9,10}$")
DATABASE_LOCK = threading.Lock()
DATABASE_INITIALIZED = False

app = Flask(__name__, static_folder="static", static_url_path="/static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", DEFAULT_SECRET)
app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=IS_VERCEL or os.environ.get("ADMIN_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=12 * 60 * 60,
)


class DatabaseNotConfigured(RuntimeError):
    pass


def using_postgres():
    return bool(DATABASE_URL)


def get_connection():
    if using_postgres():
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    if IS_VERCEL:
        raise DatabaseNotConfigured(
            "Chưa kết nối database. Hãy thêm PostgreSQL từ Vercel Marketplace và đặt biến DATABASE_URL."
        )
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    global DATABASE_INITIALIZED
    if DATABASE_INITIALIZED:
        return
    with DATABASE_LOCK:
        if DATABASE_INITIALIZED:
            return
        primary_key = "BIGSERIAL PRIMARY KEY" if using_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with get_connection() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS warranties (
                    id {primary_key},
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    product TEXT NOT NULL,
                    purchase_date TEXT NOT NULL,
                    serial TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
        DATABASE_INITIALIZED = True


def validate_submission(payload):
    fields = {
        "full_name": str(payload.get("full_name", "")).strip(),
        "phone": str(payload.get("phone", "")).strip(),
        "address": str(payload.get("address", "")).strip(),
        "product": str(payload.get("product", payload.get("model", ""))).strip(),
        "purchase_date": str(payload.get("purchase_date", "")).strip(),
        "serial": str(payload.get("serial", "")).strip(),
    }

    required = ("full_name", "phone", "address", "product", "purchase_date")
    if not all(fields[name] for name in required):
        return None, "Vui lòng nhập đầy đủ các trường bắt buộc."

    normalized_phone = re.sub(r"[ .-]", "", fields["phone"])
    if not PHONE_PATTERN.fullmatch(normalized_phone):
        return None, "Số điện thoại không hợp lệ."

    try:
        purchase_date = date.fromisoformat(fields["purchase_date"])
    except ValueError:
        return None, "Ngày mua không hợp lệ."
    if purchase_date > date.today():
        return None, "Ngày mua không thể ở trong tương lai."

    fields["phone"] = normalized_phone
    return fields, None


def fetch_warranties():
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM warranties ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def save_warranty(fields):
    initialize_database()
    created_at = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    values = (
        fields["full_name"],
        fields["phone"],
        fields["address"],
        fields["product"],
        fields["purchase_date"],
        fields["serial"],
        created_at,
    )
    with get_connection() as connection:
        if using_postgres():
            row = connection.execute(
                """
                INSERT INTO warranties (full_name, phone, address, product, purchase_date, serial, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                values,
            ).fetchone()
            return row["id"]
        cursor = connection.execute(
            """
            INSERT INTO warranties (full_name, phone, address, product, purchase_date, serial, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        return cursor.lastrowid


def admin_is_authenticated():
    return session.get("admin_authenticated") is True


@app.get("/")
@app.get("/index")
@app.get("/index.html")
def index():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if admin_is_authenticated():
        return redirect(url_for("admin_dashboard"))

    error = ""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        credentials_match = (
            hmac.compare_digest(username, ADMIN_USERNAME)
            and hmac.compare_digest(password, ADMIN_PASSWORD)
        )
        if credentials_match:
            session.clear()
            session.permanent = True
            session["admin_authenticated"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Tên đăng nhập hoặc mật khẩu không đúng."
        return render_template("admin_login.html", error=error), 401

    return render_template("admin_login.html", error=error)


@app.get("/admin")
@app.get("/admin/")
def admin_dashboard():
    if not admin_is_authenticated():
        return redirect(url_for("admin_login"))
    try:
        rows = fetch_warranties()
        database_error = ""
    except DatabaseNotConfigured as error:
        rows = []
        database_error = str(error)
    return render_template("admin_dashboard.html", rows=rows, database_error=database_error)


@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.post("/api/warranties")
def create_warranty():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(ok=False, message="Dữ liệu gửi lên không hợp lệ."), 400

    fields, error = validate_submission(payload)
    if error:
        return jsonify(ok=False, message=error), 422

    try:
        warranty_id = save_warranty(fields)
    except DatabaseNotConfigured as database_error:
        return jsonify(ok=False, message=str(database_error)), 503
    return jsonify(ok=True, id=warranty_id), 201


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(ok=False, message="Dữ liệu gửi lên quá lớn."), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    initialize_database()
    print(f"Website: http://127.0.0.1:{port}")
    print(f"Admin: http://127.0.0.1:{port}/admin")
    print(f"Đăng nhập: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    app.run(host="0.0.0.0", port=port)
