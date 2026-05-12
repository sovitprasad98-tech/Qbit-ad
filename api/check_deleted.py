import json, os, requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8729878269:AAEXcfd0fHweIpJBWVYwLr6tkyike6-5ais")
FB_URL    = os.environ.get("FIREBASE_URL", "https://cyber-attack-c5414-default-rtdb.firebaseio.com")

def tg(method, **kw):
    return requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=kw, timeout=10).json()

def fb_get(p):
    try: return requests.get(f"{FB_URL}/{p}.json", timeout=10).json()
    except: return None

def fb_patch(p, d):
    try: requests.patch(f"{FB_URL}/{p}.json", json=d, timeout=10)
    except: pass


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:    data = json.loads(body)
        except: self._json({"ok": False, "error": "Invalid JSON"}); return

        # data = { "posts": [ {"pid": "post_123", "ch_key": "mychannel", "chat_id": -100xxx, "message_id": 5} ] }
        posts_to_check = data.get("posts", [])
        results = []

        for item in posts_to_check:
            pid        = item.get("pid")
            ch_key     = item.get("ch_key")
            chat_id    = item.get("chat_id")
            message_id = item.get("message_id")
            if not all([pid, ch_key, chat_id, message_id]):
                continue

            # Try to forward the message to itself — if message deleted, Telegram returns error
            res = tg("forwardMessage", chat_id=chat_id, from_chat_id=chat_id, message_id=message_id)
            if res.get("ok"):
                # Message exists — delete the forwarded copy immediately
                tg("deleteMessage", chat_id=chat_id, message_id=res["result"]["message_id"])
                results.append({"pid": pid, "ch_key": ch_key, "deleted": False})
            else:
                err = res.get("description", "")
                if "message to forward not found" in err or "MESSAGE_ID_INVALID" in err or "message not found" in err.lower():
                    # Post was deleted — mark in Firebase
                    fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {"deleted": True})
                    results.append({"pid": pid, "ch_key": ch_key, "deleted": True})
                else:
                    # Other error (permissions etc) — don't mark deleted
                    results.append({"pid": pid, "ch_key": ch_key, "deleted": False, "err": err})

        self._json({"ok": True, "results": results})

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _json(self, data):
        b = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self._cors(); self.end_headers(); self.wfile.write(b)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *a): pass
