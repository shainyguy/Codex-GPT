import json
import os
import sqlite3
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from yookassa import Configuration, Payment

BASE_DIR = Path(__file__).resolve().parent
SITE_DIR = BASE_DIR / "site"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "salt_pepper.db"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "salt-pepper-admin-token")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            comment TEXT,
            order_type TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            payment_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            items_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            text TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def telegram_notify(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=7,
    )


def db_query(query, args=(), fetch=False):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cur = db.execute(query, args)
    rows = [dict(x) for x in cur.fetchall()] if fetch else None
    lastrowid = cur.lastrowid
    db.commit()
    db.close()
    return rows if fetch else lastrowid


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, code=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path, content_type="text/html; charset=utf-8"):
        if not path.exists():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def is_admin(self):
        cookie = self.headers.get("Cookie", "")
        return f"admin_token={ADMIN_TOKEN}" in cookie

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.send_file(SITE_DIR / "index.html")
        if path == "/menu":
            return self.send_file(SITE_DIR / "menu.html")
        if path == "/admin":
            return self.send_file(SITE_DIR / ("admin.html" if self.is_admin() else "login.html"))
        if path == "/privacy":
            return self.send_file(SITE_DIR / "privacy.html")
        if path == "/offer":
            return self.send_file(SITE_DIR / "offer.html")
        if path == "/api/menu":
            return self.send_json(read_json(DATA_DIR / "menu.json"))
        if path == "/api/reviews":
            reviews = db_query(
                "SELECT id, customer_name, rating, text, created_at FROM reviews WHERE approved=1 ORDER BY id DESC",
                fetch=True,
            )
            return self.send_json(reviews)
        if path == "/api/admin":
            if not self.is_admin():
                return self.send_json({"ok": False}, 401)
            return self.send_json({
                "orders": db_query("SELECT * FROM orders ORDER BY id DESC", fetch=True),
                "reviews": db_query("SELECT * FROM reviews ORDER BY id DESC", fetch=True),
                "contacts": db_query("SELECT * FROM contacts ORDER BY id DESC", fetch=True),
            })
        if path.startswith("/static/"):
            file_path = BASE_DIR / path.lstrip("/")
            ext = file_path.suffix
            mime = {
                ".css": "text/css",
                ".js": "application/javascript",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")
            return self.send_file(file_path, mime)
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")

        if "application/json" in ctype:
            body = json.loads(raw.decode("utf-8") or "{}")
        else:
            body = {k: v[0] for k, v in parse_qs(raw.decode("utf-8")).items()}

        if path == "/api/login":
            if body.get("username") == ADMIN_USERNAME and body.get("password") == ADMIN_PASSWORD:
                self.send_response(200)
                self.send_header("Set-Cookie", f"admin_token={ADMIN_TOKEN}; Path=/; HttpOnly")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                return
            return self.send_json({"ok": False}, 401)

        if path == "/api/reviews":
            db_query(
                "INSERT INTO reviews(customer_name,rating,text,approved,created_at) VALUES(?,?,?,?,?)",
                (body["customer_name"], int(body["rating"]), body["text"], 0, datetime.utcnow().isoformat()),
            )
            return self.send_json({"ok": True, "message": "Отзыв отправлен на модерацию"})

        if path == "/api/contact":
            db_query(
                "INSERT INTO contacts(name,phone,message,created_at) VALUES(?,?,?,?)",
                (body["name"], body["phone"], body.get("message", ""), datetime.utcnow().isoformat()),
            )
            telegram_notify(f"📞 Новая заявка\n{body['name']} {body['phone']}\n{body.get('message','')}")
            return self.send_json({"ok": True})

        if path == "/api/order":
            items = body.get("items", [])
            if body.get("order_type") == "delivery" and any(i.get("isBar") for i in items):
                return self.send_json({"ok": False, "error": "Алкоголь запрещен к доставке в РФ."}, 400)
            total = sum(float(i["price"]) * int(i["qty"]) for i in items)
            order_id = db_query(
                "INSERT INTO orders(customer_name,phone,address,comment,order_type,total,status,payment_status,created_at,items_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    body["customer_name"],
                    body["phone"],
                    body.get("address", ""),
                    body.get("comment", ""),
                    body.get("order_type", "delivery"),
                    total,
                    "new",
                    "pending",
                    datetime.utcnow().isoformat(),
                    json.dumps(items, ensure_ascii=False),
                ),
            )
            telegram_notify(f"🛒 Новый заказ #{order_id}\n{body['customer_name']} {body['phone']}\nСумма: {total} ₽")
            payment_url = None
            if body.get("payment") == "yookassa" and YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
                payment = Payment.create(
                    {
                        "amount": {"value": f"{total:.2f}", "currency": "RUB"},
                        "confirmation": {"type": "redirect", "return_url": "http://localhost:5000"},
                        "capture": True,
                        "description": f"Соль Перец заказ #{order_id}",
                    },
                    uuid.uuid4(),
                )
                payment_url = payment.confirmation.confirmation_url
            return self.send_json({"ok": True, "order_id": order_id, "total": total, "payment_url": payment_url})

        if path == "/api/admin/order-status":
            if not self.is_admin():
                return self.send_json({"ok": False}, 401)
            db_query("UPDATE orders SET status=? WHERE id=?", (body["status"], int(body["id"])))
            return self.send_json({"ok": True})

        if path == "/api/admin/review-approve":
            if not self.is_admin():
                return self.send_json({"ok": False}, 401)
            db_query("UPDATE reviews SET approved=1 WHERE id=?", (int(body["id"]),))
            return self.send_json({"ok": True})

        if path == "/api/admin/review-delete":
            if not self.is_admin():
                return self.send_json({"ok": False}, 401)
            db_query("DELETE FROM reviews WHERE id=?", (int(body["id"]),))
            return self.send_json({"ok": True})

        self.send_error(404)


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "5000"))
    print(f"Running on http://127.0.0.1:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
