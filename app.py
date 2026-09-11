"""Abraham Bike warranty activation application.

Run with: python app.py
Then visit: http://127.0.0.1:8000
"""

import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
PUBLIC_URL = os.environ.get("PUBLIC_URL", f"http://127.0.0.1:{PORT}").rstrip("/")
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DATABASE_PATH = Path(os.environ.get("WARRANTY_DB_PATH", DATA_DIR / "warranties.db"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")
MAX_BODY_SIZE = 16 * 1024
PHONE_PATTERN = re.compile(r"^(0|\+84)[0-9]{9,10}$")
SESSION_DURATION = 12 * 60 * 60
ADMIN_SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS warranties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def render_login_page(error=""):
    error_html = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Đăng nhập quản trị | Abraham Bike</title>
  <style>
    :root {{ font-family: Inter, Arial, sans-serif; color: #17191d; background: #eef3f6; }}
    * {{ box-sizing: border-box; }}
    body {{ min-height: 100vh; display: grid; place-items: center; margin: 0; padding: 24px; }}
    .login-card {{ width: min(420px, 100%); overflow: hidden; border: 1px solid #dfe3e7; border-radius: 18px; background: #fff; box-shadow: 0 20px 55px rgba(32, 45, 60, .14); }}
    .brand {{ padding: 30px 32px 24px; background: linear-gradient(145deg, #eef4f7, #e5edf1); }}
    .eyebrow {{ margin: 0 0 8px; color: #68717d; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; }}
    h1 {{ margin: 0; font-size: 27px; }}
    .subtitle {{ margin: 8px 0 0; color: #626b76; font-size: 14px; line-height: 1.5; }}
    form {{ display: grid; gap: 18px; padding: 28px 32px 32px; }}
    label {{ display: grid; gap: 7px; font-size: 13px; font-weight: 600; }}
    input {{ width: 100%; height: 46px; padding: 0 14px; border: 1px solid #cfd4d9; border-radius: 9px; outline: 0; font: inherit; font-weight: 400; }}
    input:focus {{ border-color: #ff6d22; box-shadow: 0 0 0 3px rgba(255, 109, 34, .14); }}
    button {{ height: 47px; border: 0; border-radius: 9px; color: #fff; background: linear-gradient(#ff853f, #ff641b); box-shadow: 0 8px 18px rgba(227, 78, 11, .24); cursor: pointer; font-size: 14px; font-weight: 700; }}
    button:hover {{ filter: brightness(1.04); }}
    .error {{ margin: -4px 0 0; padding: 11px 12px; border-radius: 8px; color: #a82f1d; background: #fff0ed; font-size: 13px; }}
    .back {{ color: #606975; font-size: 12px; text-align: center; text-decoration: none; }}
    .back:hover {{ color: #d95010; }}
  </style>
</head>
<body>
  <main class="login-card">
    <div class="brand">
      <p class="eyebrow">ABRAHAM BIKE</p>
      <h1>Đăng nhập quản trị</h1>
      <p class="subtitle">Nhập tài khoản quản trị để xem dữ liệu bảo hành.</p>
    </div>
    <form action="/admin/login" method="post">
      {error_html}
      <label>Tên đăng nhập<input name="username" autocomplete="username" required autofocus></label>
      <label>Mật khẩu<input type="password" name="password" autocomplete="current-password" required></label>
      <button type="submit">Đăng Nhập</button>
      <a class="back" href="/">← Quay lại trang đăng ký bảo hành</a>
    </form>
  </main>
</body>
</html>"""


def render_admin_page(rows):
    table_rows = "".join(
        f"""
        <tr>
          <td>{row['id']}</td>
          <td><strong>{html.escape(row['full_name'])}</strong></td>
          <td><a href="tel:{html.escape(row['phone'])}">{html.escape(row['phone'])}</a></td>
          <td>{html.escape(row['address'])}</td>
          <td>{html.escape(row['product'])}</td>
          <td>{html.escape(row['purchase_date'])}</td>
          <td>{html.escape(row['serial']) or '—'}</td>
          <td>{html.escape(row['created_at'])}</td>
        </tr>
        """
        for row in rows
    )
    if not table_rows:
        table_rows = '<tr><td class="empty" colspan="8">Chưa có dữ liệu đăng ký bảo hành.</td></tr>'

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>Quản trị bảo hành | Abraham Bike</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, Arial, sans-serif; color: #17191d; background: #f3f5f7; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 32px; }}
    main {{ max-width: 1400px; margin: auto; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 16px; margin-bottom: 20px; }}
    h1 {{ margin: 0 0 5px; font-size: 28px; }}
    p {{ margin: 0; color: #68717d; }}
    .header-actions {{ display: flex; align-items: center; gap: 10px; }}
    .count {{ padding: 8px 13px; border-radius: 999px; color: #fff; background: #ff6d22; font-weight: 700; }}
    .logout-form {{ margin: 0; }}
    .logout {{ padding: 8px 13px; border: 1px solid #cfd4d9; border-radius: 8px; color: #38414b; background: #fff; cursor: pointer; font-weight: 600; }}
    .logout:hover {{ border-color: #ff6d22; color: #d95010; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid #dde1e5; border-radius: 12px; background: #fff; box-shadow: 0 8px 25px rgba(30, 40, 55, .07); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 13px 14px; border-bottom: 1px solid #eceef0; text-align: left; vertical-align: top; white-space: nowrap; }}
    th {{ position: sticky; top: 0; color: #4d5661; background: #f8f9fa; font-size: 12px; text-transform: uppercase; }}
    td:nth-child(4) {{ min-width: 220px; white-space: normal; }}
    tbody tr:hover {{ background: #fff8f4; }}
    a {{ color: #d95010; }}
    .empty {{ padding: 50px; color: #68717d; text-align: center; }}
    @media (max-width: 700px) {{ body {{ padding: 18px; }} header {{ align-items: start; flex-direction: column; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Dữ liệu bảo hành</h1><p>Các đăng ký mới nhất được hiển thị trước.</p></div>
      <div class="header-actions">
        <span class="count">{len(rows)} đăng ký</span>
        <form class="logout-form" action="/admin/logout" method="post"><button class="logout" type="submit">Đăng xuất</button></form>
      </div>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Khách hàng</th><th>Điện thoại</th><th>Địa chỉ</th><th>Sản phẩm</th><th>Ngày mua</th><th>Số khung</th><th>Ngày gửi</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </main>
</body>
</html>"""


class LandingPageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, content):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def get_session_token(self):
        raw_cookie = self.headers.get("Cookie", "")
        try:
            cookie = SimpleCookie()
            cookie.load(raw_cookie)
            return cookie["admin_session"].value if "admin_session" in cookie else None
        except CookieError:
            return None

    def is_admin_authenticated(self):
        token = self.get_session_token()
        if not token:
            return False
        now = time.time()
        with SESSIONS_LOCK:
            expired = [key for key, expiry in ADMIN_SESSIONS.items() if expiry <= now]
            for key in expired:
                ADMIN_SESSIONS.pop(key, None)
            return ADMIN_SESSIONS.get(token, 0) > now

    def create_admin_session(self):
        token = secrets.token_urlsafe(32)
        with SESSIONS_LOCK:
            ADMIN_SESSIONS[token] = time.time() + SESSION_DURATION
        cookie = f"admin_session={token}; Path=/admin; HttpOnly; SameSite=Strict; Max-Age={SESSION_DURATION}"
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
        if forwarded_proto == "https" or os.environ.get("ADMIN_COOKIE_SECURE") == "1":
            cookie += "; Secure"
        return cookie

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index", "/index.html"}:
            self.path = "/index.html"
            return super().do_GET()
        if path.startswith("/static/"):
            return super().do_GET()
        if path == "/admin/login":
            if self.is_admin_authenticated():
                return self.redirect("/admin")
            return self.send_html(200, render_login_page())
        if path in {"/admin", "/admin/"}:
            if not self.is_admin_authenticated():
                return self.redirect("/admin/login")
            with get_connection() as connection:
                rows = connection.execute("SELECT * FROM warranties ORDER BY id DESC").fetchall()
            return self.send_html(200, render_admin_page(rows))
        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/admin/login":
            return self.handle_admin_login()
        if path == "/admin/logout":
            return self.handle_admin_logout()
        if path != "/api/warranties":
            return self.send_error(404, "Not found")

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"ok": False, "message": "Yêu cầu không hợp lệ."})
        if content_length <= 0 or content_length > MAX_BODY_SIZE:
            return self.send_json(413, {"ok": False, "message": "Dữ liệu gửi lên quá lớn hoặc bị trống."})

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json(400, {"ok": False, "message": "Dữ liệu JSON không hợp lệ."})
        if not isinstance(payload, dict):
            return self.send_json(400, {"ok": False, "message": "Dữ liệu gửi lên không hợp lệ."})

        fields, error = validate_submission(payload)
        if error:
            return self.send_json(422, {"ok": False, "message": error})

        created_at = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO warranties (full_name, phone, address, product, purchase_date, serial, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fields["full_name"], fields["phone"], fields["address"],
                    fields["product"], fields["purchase_date"], fields["serial"], created_at,
                ),
            )
        return self.send_json(201, {"ok": True, "id": cursor.lastrowid})

    def handle_admin_login(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > 8 * 1024:
            return self.send_html(400, render_login_page("Yêu cầu đăng nhập không hợp lệ."))

        try:
            form_data = parse_qs(self.rfile.read(content_length).decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError:
            return self.send_html(400, render_login_page("Yêu cầu đăng nhập không hợp lệ."))
        username = form_data.get("username", [""])[0]
        password = form_data.get("password", [""])[0]
        credentials_match = (
            hmac.compare_digest(username, ADMIN_USERNAME)
            and hmac.compare_digest(password, ADMIN_PASSWORD)
        )
        if not credentials_match:
            return self.send_html(401, render_login_page("Tên đăng nhập hoặc mật khẩu không đúng."))
        return self.redirect("/admin", self.create_admin_session())

    def handle_admin_logout(self):
        token = self.get_session_token()
        if token:
            with SESSIONS_LOCK:
                ADMIN_SESSIONS.pop(token, None)
        expired_cookie = "admin_session=; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=0"
        return self.redirect("/admin/login", expired_cookie)


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), LandingPageHandler)
    print(f"Abraham Bike is running at {PUBLIC_URL}")
    print(f"Admin page: {PUBLIC_URL}/admin")
    print(f"Admin username: {ADMIN_USERNAME}")
    print(f"Admin password: {ADMIN_PASSWORD}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
