# Host a protected demonstration on Render

This deployment uses one shared judge login over HTTPS. It does not create separate
accounts, permissions or workspaces for visitors. Anyone with the password can
review facts, run Gemini and export the synthetic demo records. Keep the credentials
out of GitHub and share them only in private judge access instructions.

## Create the service

1. Push this version of the repository to GitHub.
2. In Render, choose **New > Web Service**, connect GitHub and select this repository.
3. Select branch `main`, language **Python 3**, and leave Root Directory blank.
4. Build command: `pip install -r requirements.txt`.
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.
6. Health Check Path: `/healthz`. It returns only process liveness, not database
   readiness, graph details or credentials. `/api/health` requires login.
7. Keep exactly **one instance and one worker**. Choose a region near FalkorDB.
8. Add the environment variables below before deploying. `.python-version` pins
   the Python 3.12 series; no Docker installation is required.

Render's free web service sleeps after 15 minutes without inbound traffic. Allow
for a cold start when sharing the URL; select paid compute if you need it always
running. Check the current price before choosing a paid plan.

## Environment variables

| Name | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `AUTH_REQUIRED` | `true` |
| `DEMO_USERNAME` | A shared demo username, such as `judge` |
| `DEMO_PASSWORD` | A randomly generated password, at least 20 characters |
| `GEMINI_API_KEY` | Your existing key; enter it only in Render's secret settings |
| `GEMINI_MODEL` | Your tested model ID from local configuration |
| `FALKORDB_HOST` | Database hostname, without scheme or port |
| `FALKORDB_PORT` | Assigned database port |
| `FALKORDB_USERNAME` | Database username |
| `FALKORDB_PASSWORD` | Database password |
| `FALKORDB_SSL` | `true` if the endpoint requires TLS; otherwise its supplied setting |
| `FALKORDB_GRAPH` | `promisegraph_hosted_demo`, separate from your local workspace |
| `AI_REQUESTS_PER_MINUTE` | `6` |
| `AI_REQUESTS_PER_HOUR` | `60` |
| `WRITE_REQUESTS_PER_MINUTE` | `30` |
| `AI_MAX_CONCURRENT` | `2` |

Generate a password in your password manager or locally with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Do not put that output into a GitHub issue, README, commit or public submission text.
Render requires authentication automatically through its `RENDER=true` environment;
`AUTH_REQUIRED=false` cannot disable it there. Production mode also requires it.
Missing credentials, a password shorter than 20 characters, or invalid limits stop
startup instead of serving an unprotected app.

For local-only use, leave the new fields in `.env.example` at their defaults. Setting
either credential turns authentication on and requires the other. Restart after
changing credentials or limits. HTTP Basic uses the browser's own login prompt;
the app's screens remain unchanged. Use HTTPS when hosted. Closing all private
browsing windows clears that private session's remembered login; there is no app
logout button. Rotate the password in Render and redeploy to revoke old access.

## What the limits mean

- `/documents`, `/assess` and `/api/demo` share the AI limits, including rehearsal
  mode, failed requests and attempts that later fail validation. Changing modes,
  paths or a forwarded-IP header does not create another quota.
- These are **application operation limits**, not a count of Gemini API calls or
  a dollar budget. A demo ingestion or agent operation can make multiple provider
  requests. Configure provider quotas separately if a hard cost bound is needed.
- All writes, including accept/reject actions, share the 30-per-minute allowance.
- At most two AI operations may be in flight. Slots are released after success,
  error or cancellation. A rejected request returns HTTP 429 and `Retry-After`.
- Failed/missing logins share a 30-per-minute challenge allowance. A correct login
  still works when that allowance is exhausted.
- JSON bodies over 256 KiB are rejected before parsing or downstream work. Writes
  require JSON and reject a mismatched browser Origin, including with valid login.
- Counters are in memory and shared by all visitors. They reset on restart/deploy
  and are not distributed or durable billing caps. Do not scale to multiple workers
  or instances without replacing them and the existing graph-write coordination.

## Verify before sharing

1. Open the HTTPS URL in a private browser: it must show a login prompt.
2. With no credentials, check `/api/export`, `/docs`, `/openapi.json` and
   `/api/health`: they must require login. Only `/healthz` is public.
3. Sign in and confirm the graph connection. If FalkorDB restricts networks, allow
   the service's documented outbound addresses in the Cloud network settings.
4. Populate the new graph through **Extract demo notes with Gemini**, inspect the
   actual proposals and accept valid ones. Do not label rehearsal data as live.
5. Test a revision, evidence links, agent trace and export. Visitors share changes,
   so document the prepared starting state in your submission.
6. Share the app URL and private demo credentials with the judges. Keep the video
   on your chosen video host, separate from the repository.

Automated security regression coverage is in `tests/test_security.py`. These checks
are not a penetration test or a claim of production multi-user readiness.

References: [Render FastAPI deployment](https://render.com/docs/deploy-fastapi),
[Render environment variables](https://render.com/docs/configure-environment-variables),
[Render free-service limits](https://render.com/docs/free),
[FastAPI HTTP Basic authentication](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/).
