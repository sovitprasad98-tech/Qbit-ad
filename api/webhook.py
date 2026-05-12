import json
import os
import requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN  = os.environ.get("BOT_TOKEN",  "8724448269:AAGfYdcR6u7S9BW3plxiIRm-oV2Tix-zbNQ")
FB_URL     = os.environ.get("FIREBASE_URL","https://cyber-attack-c5414-default-rtdb.firebaseio.com")
WEBAPP_URL = os.environ.get("WEBAPP_URL",  "https://your-project.vercel.app")
OFFICIAL   = "qbit_ad"          # @qbit_ad username (no @)


# ── Telegram helper ──────────────────────────────────────────────────────────
def tg(method, **kw):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=kw, timeout=10
    )
    return r.json()


# ── Firebase helpers ─────────────────────────────────────────────────────────
def fb_get(path):
    try:
        r = requests.get(f"{FB_URL}/{path}.json", timeout=10)
        return r.json()
    except Exception:
        return None

def fb_set(path, data):
    try:
        requests.put(f"{FB_URL}/{path}.json", json=data, timeout=10)
    except Exception:
        pass

def fb_patch(path, data):
    try:
        requests.patch(f"{FB_URL}/{path}.json", json=data, timeout=10)
    except Exception:
        pass


# ── Handler ──────────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        # Always respond 200 immediately
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

        try:
            update = json.loads(body)
        except Exception:
            return

        # ── /start command ───────────────────────────────────────────────────
        if "message" in update:
            msg     = update["message"]
            user    = msg.get("from", {})
            chat_id = msg["chat"]["id"]
            uid     = str(user.get("id", ""))
            text    = msg.get("text", "")

            if text.startswith("/start"):
                # Create user record if new
                if not fb_get(f"users/{uid}"):
                    fb_set(f"users/{uid}", {
                        "name"           : user.get("first_name", "User"),
                        "username"       : user.get("username", ""),
                        "wallet_balance" : 0,
                        "joined_at"      : msg.get("date", 0)
                    })

                tg("sendMessage",
                   chat_id      = chat_id,
                   parse_mode   = "HTML",
                   text         = (
                       f"👋 Welcome <b>{user.get('first_name','User')}</b> to <b>Qbit Ad</b>!\n\n"
                       "💰 Apne Telegram channel par sponsored posts laao aur <b>real paisa</b> kamao!\n\n"
                       "📌 <b>Kaise kaam karta hai?</b>\n"
                       "1️⃣ App kholo aur apna channel add karo\n"
                       "2️⃣ @Qbit_Ad_Bot ko channel ka admin banao\n"
                       "3️⃣ Sponsored posts automatically aate rahenge\n"
                       "4️⃣ <b>₹5 milega har 100 views par!</b>\n\n"
                       "👇 Button dabao aur abhi shuru karo:"
                   ),
                   reply_markup = json.dumps({
                       "inline_keyboard": [[{
                           "text"    : "🚀 Open Qbit Ad App",
                           "web_app" : {"url": WEBAPP_URL}
                       }]]
                   })
                )

        # ── Channel posts ────────────────────────────────────────────────────
        elif "channel_post" in update:
            self._handle_channel_post(update["channel_post"])

        elif "edited_channel_post" in update:
            self._handle_channel_post(update["edited_channel_post"], edited=True)

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _handle_channel_post(self, post, edited=False):
        chat        = post.get("chat", {})
        ch_username = chat.get("username", "").lower()
        message_id  = post["message_id"]
        views       = post.get("views", 0)

        # 1️⃣  Post from official sponsor channel → copy to all active channels
        if ch_username == OFFICIAL.lower() and not edited:
            from_chat_id = chat["id"]
            channels     = fb_get("channels") or {}
            post_channels = {}

            for ch_key, ch_data in channels.items():
                if not ch_data.get("active"):
                    continue
                target = ch_data.get("chat_id")
                if not target:
                    continue

                res = tg("copyMessage",
                         chat_id      = target,
                         from_chat_id = from_chat_id,
                         message_id   = message_id)

                if res.get("ok"):
                    post_channels[ch_key] = {
                        "message_id" : res["result"]["message_id"],
                        "chat_id"    : target,
                        "owner_id"   : ch_data["owner_id"],
                        "views"      : 0,
                        "paid"       : False
                    }

            if post_channels:
                fb_set(f"sponsored_posts/post_{message_id}", {
                    "source_message_id" : message_id,
                    "sent_at"           : post.get("date", 0),
                    "channels"          : post_channels
                })

        # 2️⃣  Post/edit from a user channel → update live view count
        elif views > 0 and ch_username != OFFICIAL.lower():
            chat_id_str = str(chat["id"])
            posts       = fb_get("sponsored_posts") or {}

            for pid, pdata in posts.items():
                for ch_key, ch_info in (pdata.get("channels") or {}).items():
                    if (str(ch_info.get("chat_id")) == chat_id_str
                            and ch_info.get("message_id") == message_id):
                        fb_patch(
                            f"sponsored_posts/{pid}/channels/{ch_key}",
                            {"views": views}
                        )

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Qbit Ad Bot webhook is live!")

    def log_message(self, *args):
        pass
