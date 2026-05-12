import json, os, time, requests
from http.server import BaseHTTPRequestHandler

FB_URL       = os.environ.get("FIREBASE_URL","https://cyber-attack-c5414-default-rtdb.firebaseio.com")
CRON_SECRET  = os.environ.get("CRON_SECRET","")
RATE         = 0.05  # ₹0.05 per view (= ₹5 per 100 views, continuous)
MIN_VIEWS    = 100
MATURITY_SEC = 86400   # 24 h


def fb_get(p):
    try:    return requests.get(f"{FB_URL}/{p}.json", timeout=10).json()
    except: return None

def fb_set(p, d):
    try: requests.put(f"{FB_URL}/{p}.json",   json=d, timeout=10)
    except: pass

def fb_patch(p, d):
    try: requests.patch(f"{FB_URL}/{p}.json", json=d, timeout=10)
    except: pass


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if (self.headers.get("x-vercel-cron") != "1"
                and self.headers.get("Authorization") != f"Bearer {CRON_SECRET}"):
            self.send_response(401); self.end_headers(); self.wfile.write(b"Unauthorized"); return

        now         = int(time.time())
        paid_count  = 0
        total_paid  = 0.0
        posts       = fb_get("sponsored_posts") or {}
        ch_cache    = fb_get("channels")         or {}

        for pid, pdata in posts.items():
            if now - pdata.get("sent_at",0) < MATURITY_SEC: continue

            for ch_key, ci in (pdata.get("channels") or {}).items():
                if ci.get("paid"): continue

                owner_id = str(ci.get("owner_id",""))
                if not owner_id: continue

                # Views: prefer live tracked, else channel avg
                views = ci.get("views", 0)
                if views < MIN_VIEWS:
                    views = ch_cache.get(ch_key, {}).get("avg_views", 0)
                if views < MIN_VIEWS: continue

                total_amount = round(views * RATE, 2)

                # Avoid double-crediting what was already given via realtime webhook
                existing = fb_get(f"earnings/{owner_id}/earn_{pid}_{ch_key}")
                already  = existing.get("amount", 0) if existing else 0
                remaining = round(total_amount - already, 2)

                if remaining > 0:
                    user = fb_get(f"users/{owner_id}")
                    if not user: continue
                    new_bal = round(float(user.get("wallet_balance",0)) + remaining, 2)
                    fb_patch(f"users/{owner_id}", {"wallet_balance": new_bal})

                    ch_title = ch_cache.get(ch_key, {}).get("title", ch_key)
                    fb_set(f"earnings/{owner_id}/earn_{pid}_{ch_key}", {
                        "post_id":       pid,
                        "channel_key":   ch_key,
                        "channel_title": ch_title,
                        "views":         views,
                        "amount":        total_amount,
                        "earned_at":     now * 1000
                    })
                    paid_count += 1
                    total_paid += remaining

                fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {
                    "paid": True, "paid_at": now,
                    "paid_amount": total_amount, "paid_views": views
                })

        res = json.dumps({"ok":True,"paid":paid_count,"total":round(total_paid,2)}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(res)))
        self.end_headers(); self.wfile.write(res)

    def log_message(self, *a): pass
