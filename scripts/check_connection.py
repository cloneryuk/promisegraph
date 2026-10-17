"""Read connection status without printing passwords, keys, or endpoint credentials."""

import json
from app.config import Settings
from app.graph import GraphRepository, DatabaseUnavailable

s = Settings.load()
report = {
    "gemini_key_configured": bool(s.api_key),
    "model": s.model,
    "graph": s.graph,
    "tls": s.ssl,
}
try:
    repo = GraphRepository(s)
    repo.check_connection()
    report["falkordb"] = "connected"
    try:
        modules = repo.db.execute_command("MODULE", "LIST")
        report["server_modules"] = modules
    except Exception:
        report["server_modules"] = (
            "Unavailable with this database account; check version in the Cloud console."
        )
except DatabaseUnavailable as exc:
    report.update(falkordb="unavailable", error=str(exc))
print(json.dumps(report, indent=2, default=str))
