import json, os, requests
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN","8729878269:AAEXcfd0fHweIpJBWVYwLr6tkyike6-5ais")

def tg(method, **kw):
    return requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=kw, timeout=10).json()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length",0)))
        try:    data = json.loads(body)
        except: self._json({"ok":False,"error":"Invalid request"}); return

        channel = data.get("channel","").strip()
        if not channel: self._json({"ok":False,"error":"Channel username required"}); return
        if not channel.startswith("@"): channel = "@"+channel

        try:
            chat_res = tg("getChat", chat_id=channel)
            if not chat_res.get("ok"):
                self._json({"ok":False,"error":"Channel not found. Is the username correct?"}); return
            chat = chat_res["result"]
            if chat.get("type") != "channel":
                self._json({"ok":False,"error":"This is not a channel. Only Telegram channels are supported."}); return

            bot_id       = tg("getMe")["result"]["id"]
            admins       = tg("getChatAdministrators", chat_id=channel)
            bot_is_admin = any(a["user"]["id"]==bot_id for a in admins.get("result",[]))

            if not bot_is_admin:
                self._json({"ok":False,"error":"bot_not_admin",
                            "chat_id":chat["id"],"title":chat.get("title",""),"username":chat.get("username","")}); return

            subs     = tg("getChatMemberCount", chat_id=channel).get("result",0)
            avg_view = max(int(subs*0.25), 10)
            self._json({"ok":True,"chat_id":chat["id"],"title":chat.get("title",channel),
                        "username":chat.get("username",channel.lstrip("@")),
                        "subscribers":subs,"avg_views":avg_view,
                        "est_earnings":round(avg_view*0.05,2)})
        except Exception as e:
            self._json({"ok":False,"error":str(e)})

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _json(self, data):
        b = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self._cors(); self.end_headers(); self.wfile.write(b)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")

    def log_message(self, *a): pass
