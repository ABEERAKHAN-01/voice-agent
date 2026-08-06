# Step-by-Step Deployment Instructions

Goal: a live, dialable phone number backed by this FastAPI service, deployed on Railway.

## 0. Accounts you need (create these first)
1. **Railway** — railway.app (Postgres + Redis + web service host)
2. **Vapi** — vapi.ai (voice orchestration: STT/LLM/TTS/telephony; also issues your free US phone number — no Twilio needed)
3. **OpenAI** — platform.openai.com (API key for gpt-4o)
4. **Langfuse** — cloud.langfuse.com (optional, for tracing/observability)
5. **Twilio** — twilio.com (OPTIONAL — only if you need a non-US number, or want to keep a number you already own. Skip this section entirely if a free US number is fine.)

## 1. (Optional) Buy a Twilio number
Skip this step unless you need a non-US number or already own one you want to keep —
Vapi's free native US number (provisioned in step 5) covers the assessment requirement
of "a real, dialable U.S. phone number."

If you do want to use Twilio:
1. Twilio Console → Phone Numbers → Buy a Number → pick any US (or international) number with Voice capability.
2. Note the number (E.164 format, e.g. `+15125550123`).
3. Note your **Account SID** and **Auth Token** from the Twilio Console dashboard.
4. Do NOT configure a webhook on the number yet — Vapi will take ownership of it in step 5.
5. Set `USE_TWILIO_IMPORT=true` and fill in the three `TWILIO_*` variables in step 4 below.

## 2. Push this repo to GitHub
```bash
cd voice-agent
git init
git add .
git commit -m "Voice AI patient registration system"
gh repo create voice-agent-patient-registration --private --source=. --push
# or: create the repo on github.com and `git remote add origin <url> && git push -u origin main`
```

## 3. Create Railway project (Postgres + Redis + Web service)
```bash
railway login
railway init                       # creates a new Railway project
railway add --database postgres    # provisions Postgres, sets DATABASE_URL automatically
railway add --database redis       # provisions Redis, sets REDIS_URL automatically
```
Railway's injected `DATABASE_URL` is `postgresql://...` — SQLAlchemy needs the async
driver prefix. In the Railway dashboard, add a **service variable** on the web service:
```
DATABASE_URL=postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
```
(Railway lets you reference other services' variables with `${{ServiceName.VAR}}` — use
the reference picker in the dashboard rather than typing it by hand.)

## 4. Deploy the web service to Railway
```bash
railway up                 # builds from the Dockerfile in this repo
railway domain             # generates a public https://<app>.up.railway.app URL — copy it
```
In the Railway dashboard, set these variables on the web service (Variables tab):
```
ENVIRONMENT=production
LOG_LEVEL=INFO
REDIS_URL=<already set by railway add --database redis>
DATABASE_URL=<from step 3>
OPENAI_API_KEY=<your OpenAI key>
VAPI_API_KEY=<from vapi.ai dashboard, Settings -> API Keys, private key>
VAPI_PUBLIC_KEY=<same page, public key>
VAPI_WEBHOOK_SECRET=<generate: openssl rand -hex 32>
VAPI_SERVER_URL=https://<your-railway-domain>/vapi/webhook
# Only set these three if you're using Twilio (see step 1):
USE_TWILIO_IMPORT=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
LANGFUSE_PUBLIC_KEY=<optional>
LANGFUSE_SECRET_KEY=<optional>
```
Redeploy after setting variables: `railway up`.

Confirm it's live:
```bash
curl https://<your-railway-domain>/health
# {"data":{"status":"ok"},"error":null}
```

## 5. Create the Vapi assistant + provision a phone number
Run this from your machine (it reads the same `.env` — copy the Railway values into a
local `.env` first, or `railway run` to inject them):
```bash
pip install -r requirements.txt
railway run python scripts/setup_vapi.py
```
This script (`scripts/setup_vapi.py`):
- Creates a Vapi Assistant configured with `app/vapi/prompt.py` as the system prompt,
  `gpt-4o` as the model, Deepgram for transcription, 11labs for voice, and the two tools
  in `app/vapi/tools_schema.py`.
- Points the assistant's `serverUrl` at `https://<your-railway-domain>/vapi/webhook`.
- **By default, provisions a free native US number directly from Vapi** — no Twilio
  account needed. If `USE_TWILIO_IMPORT=true`, it imports your Twilio number instead
  (only needed for a non-US number or one you already own).

Copy the printed `assistant_id` into the `VAPI_ASSISTANT_ID` Railway variable (not
strictly required for calls to work, but useful for the Vapi dashboard / future scripts).
The script also prints the callable phone number — that's what you dial in step 7.

> If `scripts/setup_vapi.py` errors on the base URL, check Vapi's current API docs at
> https://docs.vapi.ai/api-reference — API hosts occasionally change; update
> `VAPI_BASE` in the script if needed.

## 6. Seed demo data (optional)
```bash
railway run python scripts/seed.py
```

## 7. Call it
Dial the number printed by `setup_vapi.py` (or your Twilio number if you used the import
path). You should hear the assistant's first message and be able to register a patient
conversationally. Call again from the same number — the agent should recognize you via
`lookup_patient_by_phone` and offer to update instead of duplicate.

## 8. Verify persistence via the REST API
```bash
curl https://<your-railway-domain>/patients
curl "https://<your-railway-domain>/patients?last_name=Doe"
curl https://<your-railway-domain>/patients/<patient_id>
```

## 9. Run tests
```bash
pip install -r requirements.txt   # includes aiosqlite for the test DB
pytest
```

## Troubleshooting
| Symptom | Likely cause | Fix |
|---|---|---|
| Call connects but agent is silent | `VAPI_SERVER_URL` unreachable from Vapi | Confirm `/health` is publicly reachable (not localhost/ngrok that's since closed) |
| Tool calls return errors mid-call | `VAPI_WEBHOOK_SECRET` mismatch | Ensure the same secret is set both in Railway vars and in the assistant's `serverUrlSecret` (re-run `setup_vapi.py` after changing it) |
| Data disappears between calls | `DATABASE_URL` missing `+asyncpg` or pointing at a different DB than Railway's | Re-check step 3 |
| 500s on `/patients` | Redis unreachable | Check `REDIS_URL`; the cache layer is best-effort and shouldn't be the sole cause — check logs (`railway logs`) for the real DB error |
| Assistant sounds robotic / ignores corrections | Prompt/model mismatch | Confirm `model.model` is `gpt-4o` and `SYSTEM_PROMPT` was actually deployed (redeploy assistant via `setup_vapi.py`) |

## Submission checklist
- [ ] Repo pushed to GitHub, reviewer access granted if private
- [ ] `https://<your-railway-domain>/health` returns 200
- [ ] Twilio number is live and callable
- [ ] `README.md` architecture/limitations sections accurate
- [ ] Send: repo URL, phone number, API base URL
