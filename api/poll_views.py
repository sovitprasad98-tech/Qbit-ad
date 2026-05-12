"""
poll_views.py  —  Vercel cron, runs every 5 minutes
Fetches real view counts from Telegram for all active sponsored posts.

How it works:
- Bot is admin in user's channel
- Telegram Bot API `forwardMessage` copies the message to bot's own DM
- The original message in channel gets its views updated in Telegram's servers  
- We read views via `getMessages` (works for admin bots) OR use the
  `channel_post` forward trick where we forward back and read the returned object
"""
import json, os, time, requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN   = os.environ.get("BOT_TOKEN",   "8729878269:AAEXcfd0fHweIpJBWVYwLr6tkyike6-5ais")
FB_URL      = os.environ.get("FIREBASE_URL","https://cyber-attack-c5414-default-rtdb.firebaseio.com")
CRON_SECRET = os.environ.get("CRON_SECRET", "")
RATE        = 0.05


def tg(method, **kw):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                          json=kw, timeout=15)
        return r.json()
    except:
        return {"ok": False}


def fb_get(p):
    try:    return requests.get(f"{FB_URL}/{p}.json", timeout=10).json()
    except: return None

def fb_patch(p, d):
    try: requests.patch(f"{FB_URL}/{p}.json", json=d, timeout=10)
    except: pass

def fb_set(p, d):
    try: requests.put(f"{FB_URL}/{p}.json", json=d, timeout=10)
    except: pass


def fetch_views(chat_id, message_id):
    """
    Get real view count for a message using Telegram Bot API.
    Uses forwardMessage to bot's own chat — the forward includes
    forward_origin.views on newer Telegram versions.
    Falls back to getMessages which works for admin bots.
    """
    # Try 1: getMessages — works when bot is channel admin
    res = tg("getMessages", chat_id=chat_id, message_ids=[message_id])
    if res.get("ok"):
        msgs = res.get("result") or []
        if msgs and isinstance(msgs, list) and len(msgs) > 0:
            v = msgs[0].get("views")
            if v is not None:
                return v

    # Try 2: Forward to bot DM and read forward_origin
    me = tg("getMe")
    bot_id = (me.get("result") or {}).get("id")
    if not bot_id:
        return None

    fwd = tg("forwardMessage",
             chat_id=bot_id,
             from_chat_id=chat_id,
             message_id=message_id)

    fwd_msg_id = None
    views      = None

    if fwd.get("ok"):
        fwd_msg    = fwd.get("result", {})
        fwd_msg_id = fwd_msg.get("message_id")
        # Check forward_origin for views (Telegram Bot API v7+)
        origin = fwd_msg.get("forward_origin") or {}
        views  = origin.get("message", {}).get("views")
        # Older API: forward_from_message_id present, views may be top-level
        if views is None:
            views = fwd_msg.get("views")
        # Delete the forwarded copy
        if fwd_msg_id:
            tg("deleteMessage", chat_id=bot_id, message_id=fwd_msg_id)

    return views  # None if both methods failed


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if (self.headers.get("x-vercel-cron") != "1"
                and self.headers.get("Authorization") != f"Bearer {CRON_SECRET}"):
            self.send_response(401); self.end_headers()
            self.wfile.write(b"Unauthorized"); return

        now      = int(time.time())
        results  = []
        posts    = fb_get("sponsored_posts") or {}
        ch_cache = fb_get("channels")         or {}

        for pid, pdata in posts.items():
            channels = pdata.get("channels") or {}
            for ch_key, ci in channels.items():
                if ci.get("paid"):    continue
                if ci.get("deleted"): continue

                chat_id    = ci.get("chat_id")
                message_id = ci.get("message_id")
                owner_id   = str(ci.get("owner_id", ""))
                if not all([chat_id, message_id, owner_id]):
                    continue

                views = fetch_views(chat_id, message_id)

                if views is None:
                    results.append({"pid": pid, "ch_key": ch_key, "status": "api_fail"})
                    continue

                old_views = ci.get("views", 0)

                if views <= old_views:
                    results.append({"pid": pid, "ch_key": ch_key,
                                    "views": views, "status": "no_change"})
                    continue

                # Update Firebase
                fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {"views": views})

                # Credit incremental earnings
                delta     = views - old_views
                increment = round(delta * RATE, 2)

                if increment > 0:
                    user = fb_get(f"users/{owner_id}")
                    if user:
                        new_bal = round(float(user.get("wallet_balance", 0)) + increment, 2)
                        fb_patch(f"users/{owner_id}", {"wallet_balance": new_bal})

                    ch_title     = ch_cache.get(ch_key, {}).get("title", ch_key)
                    total_earned = round(views * RATE, 2)
                    fb_set(f"earnings/{owner_id}/earn_{pid}_{ch_key}", {
                        "post_id":       pid,
                        "channel_key":   ch_key,
                        "channel_title": ch_title,
                        "views":         views,
                        "amount":        total_earned,
                        "earned_at":     now * 1000
                    })

                results.append({
                    "pid":       pid,
                    "ch_key":    ch_key,
                    "old_views": old_views,
                    "new_views": views,
                    "increment": increment if increment > 0 else 0,
                    "status":    "updated"
                })

        resp = json.dumps({"ok": True, "ts": now, "results": results}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, *a): pass
