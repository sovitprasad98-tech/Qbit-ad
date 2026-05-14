"""
poll_views_user.py
Called from frontend every 60s for the logged-in user's posts only.
Body: { "owner_id": "123", "ch_keys": ["mychannel"] }
Uses forwardMessage trick to get real Telegram view counts.
"""
import json, os, time, requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN",    "8729878269:AAEXcfd0fHweIpJBWVYwLr6tkyike6-5ais")
FB_URL    = os.environ.get("FIREBASE_URL", "https://cyber-attack-c5414-default-rtdb.firebaseio.com")
RATE      = 0.05

def tg(method, **kw):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
                          json=kw, timeout=12)
        return r.json()
    except: return {"ok": False}

def fb_get(p):
    try:    return requests.get(f"{FB_URL}/{p}.json", timeout=8).json()
    except: return None

def fb_patch(p, d):
    try: requests.patch(f"{FB_URL}/{p}.json", json=d, timeout=8)
    except: pass

def fb_set(p, d):
    try: requests.put(f"{FB_URL}/{p}.json", json=d, timeout=8)
    except: pass

def get_bot_id():
    me = tg("getMe")
    return (me.get("result") or {}).get("id")

def fetch_views(chat_id, message_id, bot_id):
    # Method 1: getMessages (works when bot is channel admin, Bot API 7+)
    res = tg("getMessages", chat_id=chat_id, message_ids=[message_id])
    if res.get("ok"):
        msgs = res.get("result") or []
        if msgs and isinstance(msgs, list):
            v = msgs[0].get("views")
            if v is not None: return v

    # Method 2: forward to bot's DM → read views from forward_origin
    if not bot_id: return None
    fwd = tg("forwardMessage", chat_id=bot_id,
             from_chat_id=chat_id, message_id=message_id)
    if not fwd.get("ok"): return None

    msg        = fwd.get("result", {})
    fwd_msg_id = msg.get("message_id")
    views      = (msg.get("forward_origin") or {}).get("message", {}).get("views")
    if views is None: views = msg.get("views")

    if fwd_msg_id:
        tg("deleteMessage", chat_id=bot_id, message_id=fwd_msg_id)

    return views

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:    data = json.loads(body)
        except: self._json({"ok": False, "error": "bad json"}); return

        owner_id = str(data.get("owner_id", ""))
        ch_keys  = data.get("ch_keys", [])
        if not owner_id or not ch_keys:
            self._json({"ok": False, "error": "missing fields"}); return

        bot_id  = get_bot_id()
        posts   = fb_get("sponsored_posts") or {}
        ch_cache= fb_get("channels") or {}
        updated = []

        for pid, pdata in posts.items():
            channels = pdata.get("channels") or {}
            for ch_key in ch_keys:
                ci = channels.get(ch_key)
                if not ci: continue
                if str(ci.get("owner_id","")) != owner_id: continue
                if ci.get("paid") or ci.get("deleted"): continue

                chat_id    = ci.get("chat_id")
                message_id = ci.get("message_id")
                if not chat_id or not message_id: continue

                views = fetch_views(chat_id, message_id, bot_id)
                if views is None:
                    updated.append({"pid":pid,"ch_key":ch_key,"status":"api_fail"})
                    continue

                old_views = ci.get("views", 0)
                if views <= old_views:
                    updated.append({"pid":pid,"ch_key":ch_key,"views":views,"status":"no_change"})
                    continue

                # Update Firebase — triggers frontend listener automatically
                fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {"views": views})

                delta     = views - old_views
                increment = round(delta * RATE, 2)
                if increment > 0:
                    user = fb_get(f"users/{owner_id}")
                    if user:
                        new_bal = round(float(user.get("wallet_balance",0)) + increment, 2)
                        fb_patch(f"users/{owner_id}", {"wallet_balance": new_bal})
                    ch_title     = ch_cache.get(ch_key, {}).get("title", ch_key)
                    total_earned = round(views * RATE, 2)
                    fb_set(f"earnings/{owner_id}/earn_{pid}_{ch_key}", {
                        "post_id":pid,"channel_key":ch_key,
                        "channel_title":ch_title,"views":views,
                        "amount":total_earned,"earned_at":int(time.time())*1000
                    })
                updated.append({"pid":pid,"ch_key":ch_key,
                                "old":old_views,"new":views,"status":"updated"})

        self._json({"ok":True,"updated":updated})

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _json(self, d):
        b = json.dumps(d).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self._cors(); self.end_headers(); self.wfile.write(b)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")

    def log_message(self,*a): pass
