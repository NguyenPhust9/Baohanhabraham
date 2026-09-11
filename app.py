"""Abraham Bike warranty activation application.

Run with: python app.py
Then visit: http://127.0.0.1:8000
"""

import base64
import binascii
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DATABASE_PATH = Path(os.environ.get("WARRANTY_DB_PATH", DATA_DIR / "warranties.db"))
PASSWORD_FILE = DATA_DIR / "admin_password.txt"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
MAX_BODY_SIZE = 16 * 1024
PHONE_PATTERN = re.compile(r"^(0|\+84)[0-9]{9,10}$")


def get_admin_password():
    configured_password = os.environ.get("ADMIN_PASSWORD")
    if configured_password:
        return configured_password, False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip(), False

    password = secrets.token_urlsafe(12)
    PASSWORD_FILE.write_text(password, encoding="utf-8")
    return password, True


ADMIN_PASSWORD, PASSWORD_WAS_CREATED = get_admin_password()


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
    .count {{ padding: 8px 13px; border-radius: 999px; color: #fff; background: #ff6d22; font-weight: 700; }}
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
      <span class="count">{len(rows)} đăng ký</span>
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

    def is_admin_authenticated(self):
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return False
        return hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)

    def request_admin_login(self):
        body = "Cần đăng nhập để xem dữ liệu quản trị.".encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Abraham Bike Admin", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index", "/index.html"}:
            self.path = "/index.html"
            return super().do_GET()
        if path.startswith("/static/"):
            return super().do_GET()
        if path in {"/admin", "/admin/"}:
            if not self.is_admin_authenticated():
                return self.request_admin_login()
            with get_connection() as connection:
                rows = connection.execute("SELECT * FROM warranties ORDER BY id DESC").fetchall()
            body = render_admin_page(rows).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        self.send_error(404, "Not found")

    def do_POST(self):
        if urlparse(self.path).path != "/api/warranties":
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


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), LandingPageHandler)
    print(f"Abraham Bike is running at http://127.0.0.1:{PORT}")
    print(f"Admin page: http://127.0.0.1:{PORT}/admin")
    print(f"Admin username: {ADMIN_USERNAME}")
    if PASSWORD_WAS_CREATED:
        print(f"New admin password: {ADMIN_PASSWORD}")
        print(f"The password was saved to: {PASSWORD_FILE}")
    elif os.environ.get("ADMIN_PASSWORD"):
        print("Admin password: using ADMIN_PASSWORD environment variable")
    else:
        print(f"Admin password: stored in {PASSWORD_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()
