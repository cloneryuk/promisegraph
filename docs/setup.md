# Setup without Docker

PromiseGraph runs locally in Python and connects directly to FalkorDB Cloud.

## 1. Gemini

1. Open https://aistudio.google.com/api-keys and sign in.
2. Create an API key. Create or select a Google Cloud project if prompted.
3. Open the project's `.env` file. Paste the key after `GEMINI_API_KEY=`.
4. Keep `GEMINI_MODEL=gemini-3.5-flash-lite` if available to your account; otherwise use a supported Gemini model with structured output and function calling.

Official key guide: https://ai.google.dev/gemini-api/docs/api-key

## 2. FalkorDB Cloud

1. Open https://www.falkordb.com/try-free/ and follow the Cloud sign-up link.
2. Create a database instance using a plan you choose. Review any cost before provisioning.
3. When it is ready, open its connection/connectivity details.
4. Copy the hostname, assigned port, username, and password into `.env`. Use the database endpoint, not the website/browser URL. Do not add `https://` to the hostname.
5. Match `FALKORDB_SSL` to the connection's TLS requirement (`true` for TLS).
6. Leave `FALKORDB_GRAPH=promisegraph_demo`; this is the logical graph name within your instance.
7. Save the file and click **Connection settings → Check connections** in the app.

```dotenv
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.5-flash-lite
FALKORDB_HOST=your_database_hostname
FALKORDB_PORT=your_assigned_port
FALKORDB_USERNAME=your_username
FALKORDB_PASSWORD=your_database_password
FALKORDB_SSL=true
FALKORDB_GRAPH=promisegraph_demo
```

Do not paste these values into chat, screenshots, source control, or your demo video. `.env` is ignored by Git and excluded from the submission ZIP.

Official connection guide: https://www.falkordb.com/blog/graph-database-deployment-guide/

## 3. Start the app

Install Python 3.12. From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only if .env does not already exist:
Copy-Item .env.example .env
# Edit .env, then:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000. Alternatively, run `./start.ps1` (it preserves an existing .env).

macOS/Linux: `sh start.sh`. The app needs network access to your database and Gemini. The local UI can load without those connections, but graph features deliberately return an error when FalkorDB is unavailable.

## 4. Rehearse, then record a live run

1. Click **Load pre-reviewed rehearsal** to insert labeled, hand-authored synthetic fixtures into the real database. Gemini is not used.
2. Verify Acme and Beacon are at risk; Cedar cannot be assessed.
3. Go to **Add knowledge → Queue rehearsal revision**. In Review inbox, confirm the replacement and accept it.
4. Acme now has no deadline conflict in known forecasts; Beacon stays at risk. The forecast-order warning remains.
5. For a fresh live recording, change `FALKORDB_GRAPH` to a new name, e.g. `promisegraph_live_demo`. Click **Extract demo notes with Gemini**, review the proposals, then fill the revision note and extract it live.
6. Run the Gemini agent and show actual tool events, source quotes, and Cypher. A key-present check alone does not establish successful model execution.

## Troubleshooting

- Connection failure: recheck endpoint, port, username, password and TLS against the Cloud console. Ensure the instance is running and permits your network to connect.
- HTTP 400/404 from Gemini: verify model availability and name. HTTP 403: check project/key access. HTTP 429: check quota, wait or choose available capacity. No canned result replaces a failed live call.
- A review is blocked: inspect validation flags. The prototype supports only explicit full dates and approved aliases from `data/entities.json`. Reject the proposal or add a corrected source.
- Duplicate ingestion keeps its original mode and review state. Use a new graph when comparing live extraction with rehearsal.
- Run exactly one app worker. Local mode binds to localhost. For a hosted shared demo, configure the password gate and request limits in [hosting.md](hosting.md); per-user accounts and tenant controls are not implemented.

FalkorDB Cloud is explicitly allowed by rule 4: https://www.wemakedevs.org/hackathons/falkordb/rules
