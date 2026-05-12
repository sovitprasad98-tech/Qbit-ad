import json
import os
import requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8724448269:AAGfYdcR6u7S9BW3plxiIRm-oV2Tix-zbNQ")


def tg(method, **kw):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=kw, timeout=10
    )
    return r.json()


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            data    = json.loads(body)
            channel = data.get("channel", "").strip()
        except Exception:
            self._json({"ok": False, "error": "Invalid request body"})
            return

        if not channel:
            self._json({"ok": False, "error": "Channel username required"})
            return

        if not channel.startswith("@"):
            channel = "@" + channel

        try:
            # ── Step 1: Get chat info ────────────────────────────────────────
            chat_res = tg("getChat", chat_id=channel)
            if not chat_res.get("ok"):
                self._json({"ok": False,
                            "error": "Channel nahi mila. Username sahi hai? (e.g. @mychannel)"})
                return

            chat = chat_res["result"]
            if chat.get("type") != "channel":
                self._json({"ok": False,
                            "error": "Ye channel nahi hai. Sirf Telegram channels allowed hain."})
                return

            # ── Step 2: Check bot is admin ───────────────────────────────────
            bot_res = tg("getMe")
            bot_id  = bot_res["result"]["id"] if bot_res.get("ok") else None

            admins_res  = tg("getChatAdministrators", chat_id=channel)
            bot_is_admin = False

            if admins_res.get("ok") and bot_id:
                for admin in admins_res["result"]:
                    if admin["user"]["id"] == bot_id:
                        bot_is_admin = True
                        break

            if not bot_is_admin:
                self._json({
                    "ok"       : False,
                    "error"    : "bot_not_admin",
                    "chat_id"  : chat["id"],
                    "title"    : chat.get("title", ""),
                    "username" : chat.get("username", "")
                })
                return

            # ── Step 3: Get member count & estimate views ────────────────────
            mc_res      = tg("getChatMemberCount", chat_id=channel)
            subscribers = mc_res.get("result", 0) if mc_res.get("ok") else 0

            # Industry avg: active channels get ~20-30% of subs as views
            avg_views    = max(int(subscribers * 0.25), 10)
            est_earnings = round((avg_views / 100) * 5, 2)

            self._json({
                "ok"          : True,
                "chat_id"     : chat["id"],
                "title"       : chat.get("title", channel),
                "username"    : chat.get("username", channel.lstrip("@")),
                "subscribers" : subscribers,
                "avg_views"   : avg_views,
                "est_earnings": est_earnings
            })

        except Exception as e:
            self._json({"ok": False, "error": f"Server error: {str(e)}"})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *args):
        pass
