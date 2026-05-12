# 🚀 Qbit Ad Bot — Setup Guide

## 📁 File Structure
```
qbit-ad-bot/
├── api/
│   ├── webhook.py          → Telegram bot logic (/start + post forwarder)
│   ├── verify_channel.py   → WebApp channel verification API
│   └── check_views.py      → Cron: views check + earnings payout
├── public/
│   └── index.html          → Full Telegram WebApp (single file)
├── vercel.json             → Vercel config + cron schedule
├── requirements.txt        → Python dependencies
└── .env.example            → Environment variables template
```

---

## 🔧 Step 1 — Firebase Setup

1. Firebase Console → **Realtime Database** → **Rules** → Paste:

```json
{
  "rules": {
    ".read": true,
    ".write": true,
    "channels": { ".indexOn": ["owner_id"] },
    "withdrawals": { ".indexOn": ["user_id"] }
  }
}
```

2. Click **Publish**.

---

## 📦 Step 2 — GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/qbit-ad-bot.git
git push -u origin main
```

---

## ☁️ Step 3 — Vercel Deploy

1. Go to **vercel.com** → New Project → Import your GitHub repo
2. Add these **Environment Variables** in Vercel:

| Variable       | Value                                                    |
|----------------|----------------------------------------------------------|
| `BOT_TOKEN`    | `8724448269:AAGfYdcR6u7S9BW3plxiIRm-oV2Tix-zbNQ`       |
| `FIREBASE_URL` | `https://cyber-attack-c5414-default-rtdb.firebaseio.com` |
| `WEBAPP_URL`   | `https://your-project-name.vercel.app`  ← deploy ke baad milega |
| `CRON_SECRET`  | Any random string (e.g. `qbitsecret_xyz123`)             |

3. Click **Deploy**.
4. Note your Vercel URL (e.g. `https://qbit-ad-bot.vercel.app`).
5. Go back to **Settings → Environment Variables**, update `WEBAPP_URL` with the real URL.
6. **Redeploy** (Settings → Deployments → Redeploy latest).

---

## 🔗 Step 4 — Set Telegram Webhook

Open this URL in your browser (replace values):

```
https://api.telegram.org/bot8724448269:AAGfYdcR6u7S9BW3plxiIRm-oV2Tix-zbNQ/setWebhook?url=https://your-project-name.vercel.app/api/webhook&allowed_updates=["message","channel_post","edited_channel_post"]
```

You should see: `{"ok":true,"result":true,...}`

---

## ✅ Step 5 — Verify Everything

Test webhook status:
```
https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

Test bot:
- Send `/start` to `@Qbit_Ad_Bot`
- Button aana chahiye "Open Qbit Ad App"

---

## 📢 How Sponsored Posts Work

1. Post anything to your **@qbit_ad** channel
2. Bot automatically copies it to **all registered user channels**
3. After **24 hours**, cron job runs and credits earnings:
   - ₹5 per 100 views
   - Minimum 100 views required to get paid
4. Users withdraw via UPI through the WebApp

---

## ⏰ Cron Schedule

`vercel.json` has: `"schedule": "0 */6 * * *"`
→ Runs every 6 hours automatically on Vercel.

To test manually, call:
```
GET https://your-project.vercel.app/api/check_views
Authorization: Bearer your_cron_secret
```

---

## 🔒 Security Notes (Production ke liye)

- Firebase rules mein proper auth lagao
- `CRON_SECRET` strong rakho
- Bot token kabhi public repo mein mat daalo (Vercel env vars use karo)

---

## ❓ Common Issues

| Issue | Fix |
|---|---|
| WebApp open nahi ho raha | `WEBAPP_URL` env var sahi set karo + redeploy |
| Channel verify fail | Bot `@Qbit_Ad_Bot` ko channel admin banana padega |
| Cron nahi chal raha | Vercel Pro plan pe crons chalte hain (free mein limited) |
| Firebase error | Database rules publish kiye? URL sahi hai? |
