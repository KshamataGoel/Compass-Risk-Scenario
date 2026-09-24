# Deploying Compass to Render

Two services are created from `render.yaml`:
- **compass-backend** — FastAPI (Python). Reads both Excel workbooks from `Database/`.
- **compass-frontend** — Next.js (Node). Proxies `/api/*` to the backend server-side.

The browser only ever talks to the frontend, which forwards API calls to the backend — so
there are no CORS problems.

---

## Step 1 — Put the code on GitHub

Render deploys from a Git repo. From the project folder:

```bash
git init
git add .
git commit -m "Compass: Market Risk + Operational Resilience app"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Create the empty GitHub repo first at https://github.com/new (no README/.gitignore — this repo already has one). `backend/.env` is git-ignored, so **your Groq key is never pushed**. The two `.xlsx` workbooks in `Database/` **are** committed (the app needs them).

## Step 2 — Create the Render Blueprint

1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Connect GitHub and pick the repo. Render reads `render.yaml` and shows two services.
3. Click **Apply**. Render starts building both.

## Step 3 — Set the secrets/URLs (the `sync: false` values)

**compass-backend → Environment:**
- `GROQ_API_KEY` = your Groq key (from https://console.groq.com/keys)
- `FRONTEND_ORIGINS` = the frontend URL, e.g. `https://compass-frontend.onrender.com`

**compass-frontend → Environment:**
- `NEXT_PUBLIC_API_BASE` = the backend URL, e.g. `https://compass-backend.onrender.com`
  (copy the exact URL Render shows for compass-backend — it may add a random suffix).

After setting these, click **Manual Deploy → Deploy latest commit** on each service so they
pick up the values (the frontend must rebuild so the proxy target takes effect).

## Step 4 — Verify

- Backend health: open `https://<backend>.onrender.com/api/health` → `{"status":"ok","groq_configured":true,"model":"openai/gpt-oss-120b"}`
- Open the frontend URL and run a request, e.g. *"Trading VaR for 1 day using 6 observations at 99%"* or *"Show operational resilience impact for Asian storm"*.

---

## Notes
- **Free tier** spins services down after ~15 min idle; the first request then takes ~50s to wake. Upgrade the plan to keep them warm.
- **Save Simulation** writes to `output/` which is **ephemeral** on Render (cleared on redeploy/restart) — fine for a demo; use a database/object store for durable saves.
- **TLS**: `GROQ_VERIFY_SSL` is `true` on Render (no corporate proxy). Keep it `false` only for local corporate networks.
- The Excel workbooks are the data source and are read-only at runtime — they ship in the repo.
- To change models, edit `GROQ_MODEL` in the backend env (e.g. `llama-3.3-70b-versatile` is retired; use `openai/gpt-oss-120b`).
