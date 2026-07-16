"""Ronaldo fan club demo server (Python standard library only)."""

from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

ROOT = Path(__file__).parent
DB = ROOT / "fanclub.db"
SESSIONS: dict[str, tuple[int, str]] = {}


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300_000)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def send_json(self, status, data, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 10_000:
            raise ValueError("요청이 너무 큽니다.")
        return json.loads(self.rfile.read(length))

    def current_user(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie"))
        token = jar.get("session")
        if not token or token.value not in SESSIONS:
            return None
        user_id, name = SESSIONS[token.value]
        return {"id": user_id, "name": name}

    def do_GET(self):
        if self.path == "/api/status":
            with db() as con:
                count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return self.send_json(200, {"members": count, "user": self.current_user()})
        super().do_GET()

    def do_POST(self):
        try:
            data = self.read_json()
            if self.path == "/api/register":
                return self.register(data)
            if self.path == "/api/login":
                return self.login(data)
            if self.path == "/api/logout":
                jar = cookies.SimpleCookie(self.headers.get("Cookie"))
                if jar.get("session"):
                    SESSIONS.pop(jar["session"].value, None)
                return self.send_json(200, {"message": "로그아웃했습니다."}, "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict")
            self.send_json(404, {"error": "주소를 찾을 수 없습니다."})
        except (ValueError, json.JSONDecodeError):
            self.send_json(400, {"error": "잘못된 요청입니다."})

    def register(self, data):
        name = str(data.get("name", "")).strip()[:30]
        email = str(data.get("email", "")).strip().lower()[:120]
        password = str(data.get("password", ""))
        if len(name) < 2 or "@" not in email or len(password) < 8:
            return self.send_json(400, {"error": "이름, 이메일, 8자 이상 비밀번호를 확인하세요."})
        salt = secrets.token_bytes(16)
        try:
            with db() as con:
                cur = con.execute("INSERT INTO users(name,email,password_hash,salt) VALUES(?,?,?,?)",
                                  (name, email, hash_password(password, salt), salt))
        except sqlite3.IntegrityError:
            return self.send_json(409, {"error": "이미 가입된 이메일입니다."})
        return self.start_session(cur.lastrowid, name, "팬클럽 가입을 환영합니다!")

    def login(self, data):
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user or not hmac.compare_digest(hash_password(password, user["salt"]), user["password_hash"]):
            time.sleep(0.2)
            return self.send_json(401, {"error": "이메일 또는 비밀번호가 올바르지 않습니다."})
        return self.start_session(user["id"], user["name"], "다시 만나 반가워요!")

    def start_session(self, user_id, name, message):
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = (user_id, name)
        cookie = f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400"
        self.send_json(200, {"message": message, "user": {"name": name}}, cookie)


if __name__ == "__main__":
    init_db()
    print("팬클럽 홈페이지: http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
