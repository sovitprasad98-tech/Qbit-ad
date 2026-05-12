import json, os, time, requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN  = os.environ.get("BOT_TOKEN",  "8729878269:AAEXcfd0fHweIpJBWVYwLr6tkyike6-5ais")
FB_URL     = os.environ.get("FIREBASE_URL","https://cyber-attack-c5414-default-rtdb.firebaseio.com")
WEBAPP_URL = os.environ.get("WEBAPP_URL",  "https://your-project.vercel.app")
OFFICIAL   = "qbit_ad"
RATE       = 0.05  # ₹0.05 per view (= ₹5 per 100 views, but credited continuously)


def tg(method, **kw):
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=kw, timeout=10)
    return r.json()

def fb_get(path):
    try:
        return requests.get(f"{FB_URL}/{path}.json", timeout=10).json()
    except: return None

def fb_set(path, data):
    try: requests.put(f"{FB_URL}/{path}.json",   json=data, timeout=10)
    except: pass

def fb_patch(path, data):
    try: requests.patch(f"{FB_URL}/{path}.json", json=data, timeout=10)
    except: pass


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
        try:    update = json.loads(body)
        except: return

        if "message" in update:
            self._handle_message(update["message"])
        elif "channel_post" in update:
            self._handle_ch_post(update["channel_post"], edited=False)
        elif "edited_channel_post" in update:
            self._handle_ch_post(update["edited_channel_post"], edited=True)

    # ── /start ──────────────────────────────────────────────────────────────
    def _handle_message(self, msg):
        user    = msg.get("from", {})
        uid     = str(user.get("id", ""))
        chat_id = msg["chat"]["id"]
        if not msg.get("text","").startswith("/start"): return

        if not fb_get(f"users/{uid}"):
            fb_set(f"users/{uid}", {
                "name": user.get("first_name","User"),
                "username": user.get("username",""),
                "wallet_balance": 0,
                "joined_at": msg.get("date",0)
            })

        tg("sendMessage",
           chat_id=chat_id, parse_mode="HTML",
           text=(
               f"👋 Welcome <b>{user.get('first_name','User')}</b> to <b>Qbit Ad</b>!\n\n"
               "💰 Earn real money by hosting sponsored posts on your Telegram channel.\n\n"
               "📌 <b>How it works:</b>\n"
               "1️⃣ Open the app and add your channel\n"
               "2️⃣ Make @Qbit_Ad_Bot an admin\n"
               "3️⃣ Sponsored posts arrive automatically\n"
               "4️⃣ <b>Earn ₹0.05 per view — credited in real time!</b>\n\n"
               "👇 Tap below to get started:"
           ),
           reply_markup=json.dumps({"inline_keyboard":[[{
               "text":"🚀 Open Qbit Ad Dashboard",
               "web_app":{"url": WEBAPP_URL}
           }]]})
        )

    # ── Channel posts ────────────────────────────────────────────────────────
    def _handle_ch_post(self, post, edited=False):
        chat        = post.get("chat", {})
        ch_username = chat.get("username","").lower()
        message_id  = post["message_id"]
        views       = post.get("views", 0)

        # ── Incoming sponsored post from @qbit_ad → broadcast ────────────
        if ch_username == OFFICIAL.lower() and not edited:
            caption   = (post.get("caption") or post.get("text") or "")[:200]
            post_type = ("photo"    if "photo"      in post else
                         "video"    if "video"       in post else
                         "document" if "document"    in post else
                         "audio"    if "audio"       in post else "text")

            channels      = fb_get("channels") or {}
            post_channels = {}

            for ch_key, ch_data in channels.items():
                if not ch_data.get("active"): continue
                target = ch_data.get("chat_id")
                if not target:                continue

                res = tg("copyMessage",
                         chat_id=target,
                         from_chat_id=chat["id"],
                         message_id=message_id)

                if res.get("ok"):
                    post_channels[ch_key] = {
                        "message_id": res["result"]["message_id"],
                        "chat_id":    target,
                        "owner_id":   ch_data["owner_id"],
                        "views":      0,
                        "paid":       False
                    }

            if post_channels:
                fb_set(f"sponsored_posts/post_{message_id}", {
                    "source_message_id": message_id,
                    "caption":           caption,
                    "post_type":         post_type,
                    "sent_at":           post.get("date", 0),
                    "channels":          post_channels
                })

        # ── Post deleted from user channel ───────────────────────────────
        elif edited and not post.get("text") and not post.get("caption") and not post.get("photo") and not post.get("video") and not post.get("document") and not post.get("audio"):
            # Telegram sends edited_channel_post with empty content when post content is cleared
            # Mark as deleted in Firebase
            chat_id_str = str(chat["id"])
            posts = fb_get("sponsored_posts") or {}
            for pid, pdata in posts.items():
                for ch_key, ch_info in (pdata.get("channels") or {}).items():
                    if str(ch_info.get("chat_id")) == chat_id_str and ch_info.get("message_id") == message_id:
                        fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {"deleted": True})
                        break

        # ── View update from a user's channel → realtime earnings ─────────
        elif views > 0 and ch_username != OFFICIAL.lower():
            chat_id_str = str(chat["id"])
            posts       = fb_get("sponsored_posts") or {}

            for pid, pdata in posts.items():
                for ch_key, ch_info in (pdata.get("channels") or {}).items():
                    if (str(ch_info.get("chat_id")) != chat_id_str
                            or ch_info.get("message_id") != message_id):
                        continue

                    old_views = ch_info.get("views", 0)
                    if views <= old_views: continue

                    # Update stored view count
                    fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {"views": views})

                    owner_id = str(ch_info.get("owner_id",""))
                    if not owner_id or ch_info.get("paid"): continue

                    # Incremental earnings — continuous ₹0.05 per new view
                    new_views = views - old_views
                    increment = round(new_views * RATE, 2)

                    if increment <= 0: continue

                    # Credit wallet
                    user_data = fb_get(f"users/{owner_id}")
                    if user_data:
                        new_bal = round(float(user_data.get("wallet_balance",0)) + increment, 2)
                        fb_patch(f"users/{owner_id}", {"wallet_balance": new_bal})

                    # Upsert earning record (total for this post-channel pair)
                    channels_cache = fb_get("channels") or {}
                    ch_title       = channels_cache.get(ch_key, {}).get("title", ch_key)
                    total_earned   = round(views * RATE, 2)

                    fb_set(f"earnings/{owner_id}/earn_{pid}_{ch_key}", {
                        "post_id":       pid,
                        "channel_key":   ch_key,
                        "channel_title": ch_title,
                        "views":         views,
                        "amount":        total_earned,
                        "earned_at":     int(time.time()) * 1000
                    })

    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Qbit Ad webhook live!")

    def log_message(self, *a): pass
