"""浏览器前端服务：HTTP + JSON 接口，页面是同一目录下的 index.html。

浏览器不能直接跟 server.py 的 TCP 端口通信，所以这里加一层 HTTP：
    页面：http://127.0.0.1:8000
    POST /api/users      {"username": "张三"}
    POST /api/history    {"username": "张三", "question": "问事业", ...}
    GET  /api/history?username=张三
    POST /api/register   {"username": "张三", "display_name": "小张", "password": "123456"}
    POST /api/login      {"username": "张三", "password": "123456"}

数据库操作直接复用 server.py 里已经写好的函数。
"""
import base64
import os
import hashlib
import hmac
import json
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pymysql

from server import get_conn, get_user_id, init_db as init_tables

HOST = "0.0.0.0"
PORT = 8000
INDEX_FILE = Path(__file__).with_name("index.html")


class UserExists(Exception):
    """用户名已被注册。"""


class AuthFailed(Exception):
    """用户名或密码不正确。"""


# ============================== 用户信息 ==============================
PBKDF2_SALT = b"xingxun-2026"
PBKDF2_ITER = 200000


def hash_password(password):
    """PBKDF2-HMAC-SHA256 加盐哈希，纯标准库实现。"""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), PBKDF2_SALT, PBKDF2_ITER).hex()
    return "pbkdf2$" + digest


def verify_password(password, stored):
    """校验密码：新格式用 pbkdf2，旧格式（64 位 sha256）继续兼容。"""
    stored = stored or ""
    if stored.startswith("pbkdf2$"):
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), PBKDF2_SALT, PBKDF2_ITER).hex()
        return hmac.compare_digest(stored[len("pbkdf2$"):], expected)
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), stored)


def user_payload(row):
    """把数据库一行转成前端要的格式。"""
    username = row[0]
    return {
        "username": username,
        "display_name": row[1] or username,
        "created_at": row[2].strftime("%Y-%m-%d %H:%M:%S") if row[2] else "",
    }


def _reading_payload(result):
    """尝试把 history.result 里的 JSON 字符串还原成字典。"""
    if not result:
        return {}
    try:
        value = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _divination_fields(username, method, question, result):
    """从一条 history 记录里拆出 divinations 表需要的字段。"""
    reading = _reading_payload(result)

    topic = str(reading.get("topic") or "")[:32]
    answer = str(reading.get("answer") or "")
    if not reading and result:
        answer = result

    board_text = json.dumps({
        "cards": reading.get("cards") or [],
        "analysis": reading.get("analysis"),
        "birth": reading.get("birth"),
        "calendar": reading.get("calendar"),
        "spreadName": reading.get("spreadName"),
    }, ensure_ascii=False)

    return {
        "user_id": username[:64],
        "method": method[:16],
        "topic": topic,
        "question": question[:5000],
        "board_text": board_text[:20000],
        "answer": answer[:20000],
    }


def insert_divination(cur, fields):
    """在给定游标上插入一条 divinations 记录，返回自增 id。"""
    cur.execute(
        "INSERT INTO divinations (user_id, method, topic, question, board_text, answer) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            fields["user_id"], fields["method"], fields["topic"],
            fields["question"], fields["board_text"], fields["answer"],
        ),
    )
    return cur.lastrowid


def ensure_auth_schema():
    """给已有的 users 表补上昵称和密码列（可重复执行）。"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SHOW COLUMNS FROM users LIKE 'display_name'")
    if cur.fetchone() is None:
        cur.execute("ALTER TABLE users ADD COLUMN display_name VARCHAR(100) NULL AFTER username")

    cur.execute("SHOW COLUMNS FROM users LIKE 'password_hash'")
    row = cur.fetchone()
    if row is None:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128) NULL AFTER display_name")
    else:
        # 旧库是 VARCHAR(64)，放不下 pbkdf2 前缀，这里自动放宽
        cur.execute("ALTER TABLE users MODIFY password_hash VARCHAR(128) NULL")

    conn.commit()
    cur.close()
    conn.close()


def seed_demo_user():
    """保证页面上的 demo / tarot2026 能登录。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash FROM users WHERE username = 'demo'")
    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO users (username, display_name, password_hash) VALUES (%s, %s, %s)",
            ("demo", "旅人", hash_password("tarot2026")),
        )
    elif row[1] is None:
        cur.execute(
            "UPDATE users SET display_name = %s, password_hash = %s WHERE id = %s",
            ("旅人", hash_password("tarot2026"), row[0]),
        )

    conn.commit()
    cur.close()
    conn.close()


def init_db():
    """建库建表，并保证用户表有注册/登录需要的列。"""
    init_tables()
    ensure_auth_schema()
    seed_demo_user()


# ============================== 业务操作 ==============================
def save_user(data):
    """写入用户，返回 user_id。"""
    username = str(data.get("username", "")).strip()
    if username == "":
        raise ValueError("username 不能为空")

    conn = get_conn()
    cur = conn.cursor()
    user_id = get_user_id(cur, username)
    conn.commit()
    cur.close()
    conn.close()
    return user_id


def save_divination(data):
    """直接写入 divinations 表（对应参考 server.py 的 /divinations）。"""
    fields = {
        "user_id": str(data.get("user_id") or data.get("username") or "").strip()[:64],
        "method": str(data.get("method") or "")[:16],
        "topic": str(data.get("topic") or "")[:32],
        "question": str(data.get("question") or "")[:5000],
        "board_text": str(data.get("board_text") or "")[:20000],
        "answer": str(data.get("answer") or "")[:20000],
    }
    if fields["user_id"] == "" or fields["question"] == "":
        raise ValueError("user_id 和 question 不能为空")

    conn = get_conn()
    cur = conn.cursor()
    try:
        divination_id = insert_divination(cur, fields)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return divination_id


def register_user(data):
    """注册：把用户名、昵称、密码哈希写入 users 表。"""
    username = str(data.get("username", "")).strip()
    display_name = str(data.get("display_name") or "").strip() or username
    password = str(data.get("password", ""))

    if len(username) < 2:
        raise ValueError("用户名至少需要 2 个字符")
    if len(username) > 32:
        raise ValueError("用户名最多 32 个字符")
    if len(display_name) > 100:
        raise ValueError("昵称最多 100 个字符")
    if len(password) < 6:
        raise ValueError("密码至少需要 6 个字符")

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone() is not None:
            raise UserExists("这个用户名已被使用，请换一个。")

        cur.execute(
            "INSERT INTO users (username, display_name, password_hash) VALUES (%s, %s, %s)",
            (username, display_name, hash_password(password)),
        )
        conn.commit()

        cur.execute(
            "SELECT username, display_name, created_at FROM users WHERE id = %s",
            (cur.lastrowid,),
        )
        return user_payload(cur.fetchone())
    except pymysql.err.IntegrityError:
        conn.rollback()
        raise UserExists("这个用户名已被使用，请换一个。")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def login_user(data):
    """登录：校验密码哈希，返回前端需要的用户信息。"""
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if username == "" or password == "":
        raise ValueError("用户名和密码都要填")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, display_name, created_at, password_hash "
        "FROM users WHERE username = %s",
        (username,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None or not verify_password(password, row[3]):
        raise AuthFailed("用户名或密码不正确，请重新输入。")

    return user_payload(row)


def save_history(data):
    """写入一条历史记录，返回 record_id 和 user_id。"""
    username = str(data.get("username", "")).strip()
    question = str(data.get("question", "")).strip()
    if username == "" or question == "":
        raise ValueError("username 和 question 不能为空")

    method = str(data.get("method") or "liuyao")
    hexagram = str(data.get("hexagram") or "")
    result = str(data.get("result") or "")

    conn = get_conn()
    cur = conn.cursor()
    try:
        user_id = get_user_id(cur, username)
        cur.execute(
            "INSERT INTO history (user_id, question, method, hexagram, result) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, question, method, hexagram, result),
        )
        record_id = cur.lastrowid

        # 同步写入新增的 divinations 表
        divination_id = insert_divination(
            cur,
            _divination_fields(username, method, question, result),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    return {
        "record_id": record_id,
        "user_id": user_id,
        "divination_id": divination_id,
    }


def list_history(username="", limit=50):
    """查历史记录，返回能直接转成 JSON 的列表。"""
    conn = get_conn()
    cur = conn.cursor()

    sql = (
        "SELECT h.id, u.username, h.question, h.method, h.hexagram, "
        "       h.result, h.created_at "
        "FROM history h JOIN users u ON u.id = h.user_id "
    )
    args = []
    if username != "":
        sql += "WHERE u.username = %s "
        args.append(username)
    sql += "ORDER BY h.id DESC LIMIT %s"
    args.append(int(limit))

    cur.execute(sql, tuple(args))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    data = []
    for row in rows:
        data.append({
            "id": row[0],
            "username": row[1],
            "question": row[2],
            "method": row[3],
            "hexagram": row[4] or "",
            "result": row[5] or "",
            "created_at": row[6].strftime("%Y-%m-%d %H:%M:%S") if row[6] else "",
        })
    return data


def list_divinations(user_id="", limit=50):
    """查 divinations 表，返回结构化盘面和答案。"""
    conn = get_conn()
    cur = conn.cursor()

    sql = (
        "SELECT id, user_id, method, topic, question, board_text, "
        "       answer, created_at "
        "FROM divinations "
    )
    args = []
    if user_id != "":
        sql += "WHERE user_id = %s "
        args.append(user_id)
    sql += "ORDER BY id DESC LIMIT %s"
    args.append(int(limit))

    cur.execute(sql, tuple(args))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    data = []
    for row in rows:
        data.append({
            "id": row[0],
            "user_id": row[1] or "",
            "method": row[2] or "",
            "topic": row[3] or "",
            "question": row[4] or "",
            "board_text": row[5] or "",
            "answer": row[6] or "",
            "created_at": row[7].strftime("%Y-%m-%d %H:%M:%S") if row[7] else "",
        })
    return data


# ============================== 令牌与前端负载 ==============================

TOKEN_SECRET = os.getenv(
    "XINGXUN_TOKEN_SECRET",
    "dev-only-change-me-before-deploy",
).encode("utf-8")
TOKEN_TTL = 7 * 24 * 3600


def make_token(username):
    """签发一个 HMAC 签名的轻量令牌，不依赖第三方库。"""
    payload = "%s|%d" % (username, int(time.time()) + TOKEN_TTL)
    raw = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    sig = hmac.new(TOKEN_SECRET, raw.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return raw + "." + sig


def read_token(token):
    """校验令牌，返回用户名；失败返回空串。"""
    try:
        raw, sig = token.split(".", 1)
    except ValueError:
        return ""
    expect = hmac.new(TOKEN_SECRET, raw.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expect):
        return ""
    try:
        payload = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8")
        username, exp = payload.rsplit("|", 1)
        if int(exp) < int(time.time()):
            return ""
        return username
    except Exception:
        return ""


def auth_user(user):
    """前端要的是驼峰命名的公开用户信息。"""
    return {
        "username": user.get("username", ""),
        "displayName": user.get("display_name") or user.get("username", ""),
        "createdAt": user.get("created_at", ""),
    }


def to_iso(value):
    """数据库的 datetime 字符串转成前端习惯的 ISO 格式。"""
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return value


def history_payload(item, username):
    """把 history 一行的 result(JSON 字符串) 还原成前端能直接用的档案对象。"""
    reading = {}
    raw = item.get("result") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                reading = parsed
        except Exception:
            reading = {}

    reading["id"] = str(reading.get("id") or item.get("id", ""))
    reading["username"] = username
    reading["question"] = item.get("question", "")
    reading["method"] = item.get("method", "")
    reading.setdefault("spreadName", item.get("hexagram") or "")
    iso = to_iso(item.get("created_at") or "")
    reading["createdAt"] = reading.get("createdAt") or iso
    reading["updatedAt"] = reading.get("updatedAt") or reading["createdAt"]
    return reading


# ============================== HTTP 处理 ==============================
class Handler(BaseHTTPRequestHandler):
    server_version = "DivinationWeb/1.1"

    def current_user(self):
        """从 Authorization: Bearer <token> 里取用户名。"""
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return read_token(auth[7:].strip())
        return ""

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"

        if path in ("/", "/index.html"):
            return self.send_file(INDEX_FILE, "text/html; charset=utf-8")

        if path == "/api/history":
            username = parse_qs(url.query).get("username", [""])[0].strip() or self.current_user()
            try:
                rows = list_history(username)
                items = [history_payload(row, username or row.get("username", "")) for row in rows]
                return self.send_json(200, {"ok": True, "data": items, "total": len(items)})
            except Exception as exc:
                return self.send_json(500, {"ok": False, "error": str(exc)})

        if path == "/api/divinations":
            query = parse_qs(url.query)
            user_id = (query.get("user_id", [""])[0].strip()
                       or query.get("username", [""])[0].strip())
            try:
                return self.send_json(200, {"ok": True, "data": list_divinations(user_id)})
            except Exception as exc:
                return self.send_json(500, {"ok": False, "error": str(exc)})

        if path == "/api/health":
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.close()
                conn.close()
                return self.send_json(200, {"ok": True})
            except Exception as exc:
                return self.send_json(500, {"ok": False, "error": str(exc)})

        return self.send_json(404, {"ok": False, "error": "接口不存在"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8"))

            if path == "/api/users":
                user_id = save_user(data)
                return self.send_json(201, {"ok": True, "user_id": user_id})

            if path in ("/api/auth/register", "/api/register"):
                user = register_user(data)
                return self.send_json(201, {
                    "ok": True,
                    "token": make_token(user["username"]),
                    "user": auth_user(user),
                    **user,
                })

            if path in ("/api/auth/login", "/api/login"):
                user = login_user(data)
                return self.send_json(200, {
                    "ok": True,
                    "token": make_token(user["username"]),
                    "user": auth_user(user),
                    **user,
                })

            if path == "/api/auth/logout":
                return self.send_json(200, {"ok": True})

            if path == "/api/history":
                token_user = self.current_user()
                if token_user:
                    data["username"] = token_user
                info = save_history(data)
                reading = history_payload(
                    {
                        "id": info["record_id"],
                        "question": data.get("question") or "",
                        "method": data.get("method") or "",
                        "hexagram": data.get("hexagram") or "",
                        "result": data.get("result") or "",
                        "created_at": "",
                    },
                    data.get("username") or token_user or "",
                )
                return self.send_json(201, {
                    "ok": True,
                    "reading": reading,
                    "record_id": info["record_id"],
                    "user_id": info["user_id"],
                    "divination_id": info["divination_id"],
                })

            if path in ("/api/divinations", "/divinations"):
                divination_id = save_divination(data)
                return self.send_json(201, {"ok": True, "id": divination_id})

            return self.send_json(404, {"ok": False, "error": "接口不存在"})

        except json.JSONDecodeError:
            return self.send_json(400, {"ok": False, "error": "请求体不是合法 JSON"})
        except UserExists as exc:
            return self.send_json(409, {"ok": False, "error": str(exc)})
        except AuthFailed as exc:
            return self.send_json(401, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            return self.send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self.send_json(500, {"ok": False, "error": str(exc)})

    def do_OPTIONS(self):
        """浏览器的跨域预检请求。"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -- 回复工具 ------------------------------------------------------
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        if not path.is_file():
            return self.send_json(404, {"ok": False, "error": "缺少 index.html"})
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)


class WebServer(ThreadingHTTPServer):
    # Windows 下默认的 SO_REUSEADDR 会让第二个进程也能绑定 8000，
    # 请求被旧进程分走就会出现“数据时好时坏”。这里禁止重复绑定。
    allow_reuse_address = False


def main():
    init_db()

    try:
        http_server = WebServer((HOST, PORT), Handler)
    except OSError as exc:
        print("端口 %d 启动失败：%s" % (PORT, exc))
        print("可能已有程序占用 8000，先关掉它，或修改 web_app.py 顶部的 PORT")
        return

    print("前端页面：http://127.0.0.1:%d" % PORT)
    print("接口：POST /api/users   POST /api/history   GET /api/history?username=xxx")
    print("      POST /api/register   POST /api/login")
    print("      POST /api/divinations   GET /api/divinations?user_id=xxx")
    print("按 Ctrl+C 停止")
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        http_server.server_close()


if __name__ == "__main__":
    main()
