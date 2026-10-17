from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    host: str = "localhost"
    port: int = 6379
    username: str = "default"
    password: str = field(default="", repr=False)
    ssl: bool = False
    graph: str = "promisegraph_demo"
    api_key: str = field(default="", repr=False)
    model: str = "gemini-3.5-flash-lite"
    read_timeout_ms: int = 1000
    max_depth: int = 8
    path_limit: int = 200

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT / ".env"), **os.environ}
        return cls(
            host=values.get("FALKORDB_HOST") or "localhost",
            port=int(values.get("FALKORDB_PORT") or 6379),
            username=values.get("FALKORDB_USERNAME") or "default",
            password=values.get("FALKORDB_PASSWORD") or "",
            ssl=str(values.get("FALKORDB_SSL", "false")).lower() == "true",
            graph=values.get("FALKORDB_GRAPH") or "promisegraph_demo",
            api_key=values.get("GEMINI_API_KEY") or "",
            model=values.get("GEMINI_MODEL") or "gemini-3.5-flash-lite",
        )
