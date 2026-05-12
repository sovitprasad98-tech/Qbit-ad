"""
Vercel Cron — runs every 6 hours.
Checks sponsored posts older than 24h and credits earnings to channel owners.

Earning logic:
  - Uses live view count if tracked via webhook (edited_channel_post)
  - Falls back to channel's avg_views if live count is 0
  - ₹5 per 100 views, minimum 100 views to qualify
"""

import json
import os
import time
import requests
from http.server import BaseHTTPRequestHandler

FB_URL            = os.environ.get("FIREBASE_URL", "https://cyber-attack-c5414-default-rtdb.firebaseio.com")
CRON_SECRET       = os.environ.get("CRON_SECRET",  "")
RATE_PER_100      = 5    # ₹5 per 100 views
MIN_VIEWS         = 100  # Minimum views to qualify for payout
POST_MATURITY_SEC = 86400  # 24 hours before payout


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


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # ── Auth check ───────────────────────────────────────────────────────
        is_vercel = self.headers.get("x-vercel-cron") == "1"
        bearer    = self.headers.get("Authorization", "")
        if not is_vercel and bearer != f"Bearer {CRON_SECRET}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        now           = int(time.time())
        paid_channels = 0
        total_amount  = 0.0

        posts         = fb_get("sponsored_posts") or {}
        channels_data = fb_get("channels")        or {}

        for pid, pdata in posts.items():
            sent_at = pdata.get("sent_at", 0)

            # Skip posts younger than 24h
            if now - sent_at < POST_MATURITY_SEC:
                continue

            for ch_key, ch_info in (pdata.get("channels") or {}).items():
                if ch_info.get("paid"):
                    continue

                owner_id = str(ch_info.get("owner_id", ""))
                if not owner_id:
                    continue

                # Use live tracked views, else fall back to channel avg
                views = ch_info.get("views", 0)
                if views < MIN_VIEWS:
                    avg = channels_data.get(ch_key, {}).get("avg_views", 0)
                    views = avg

                if views < MIN_VIEWS:
                    continue

                amount = round((views / 100) * RATE_PER_100, 2)

                # ── Credit wallet ────────────────────────────────────────────
                user = fb_get(f"users/{owner_id}")
                if not user:
                    continue

                new_bal = round(float(user.get("wallet_balance", 0)) + amount, 2)
                fb_patch(f"users/{owner_id}", {"wallet_balance": new_bal})

                # ── Mark post-channel as paid ────────────────────────────────
                fb_patch(f"sponsored_posts/{pid}/channels/{ch_key}", {
                    "paid"       : True,
                    "paid_amount": amount,
                    "paid_views" : views,
                    "paid_at"    : now
                })

                # ── Write earning record ─────────────────────────────────────
                ch_title = channels_data.get(ch_key, {}).get("title", ch_key)
                fb_set(f"earnings/{owner_id}/earn_{pid}_{ch_key}", {
                    "post_id"      : pid,
                    "channel_key"  : ch_key,
                    "channel_title": ch_title,
                    "views"        : views,
                    "amount"       : amount,
                    "earned_at"    : now * 1000  # ms for JS Date compatibility
                })

                paid_channels += 1
                total_amount  += amount

        result = json.dumps({
            "ok"            : True,
            "paid_channels" : paid_channels,
            "total_amount"  : round(total_amount, 2),
            "checked_at"    : now
        }).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, *args):
        pass
