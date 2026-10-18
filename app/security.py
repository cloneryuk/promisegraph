"""Access control and process-local limits for a shared, single-worker demo."""

import base64
import binascii
import math
import os
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from dotenv import dotenv_values
from starlette.responses import JSONResponse

from .config import ROOT


@dataclass(frozen=True)
class SecuritySettings:
    required: bool = False
    username: str = ""
    password: str = field(default="", repr=False)
    ai_per_minute: int = 6
    ai_per_hour: int = 60
    writes_per_minute: int = 30
    ai_concurrency: int = 2
    body_bytes: int = 262144
    public_until: float | None = None

    def public_access_open(self):
        return self.public_until is not None and time.time() < self.public_until

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT / ".env"), **os.environ}
        flag = str(values.get("AUTH_REQUIRED") or "false").lower()
        if flag not in {"true", "false"}:
            raise ValueError("AUTH_REQUIRED must be true or false.")
        hosted = str(values.get("RENDER") or "").lower() == "true"
        production = values.get("APP_ENV") == "production"
        username = values.get("DEMO_USERNAME") or ""
        password = values.get("DEMO_PASSWORD") or ""
        public_until = None
        deadline = values.get("PUBLIC_DEMO_UNTIL") or ""
        if deadline:
            try:
                parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    raise ValueError("Timezone required")
                public_until = parsed.timestamp()
            except (ValueError, OverflowError) as exc:
                raise ValueError("PUBLIC_DEMO_UNTIL must be an ISO timestamp with a timezone.") from exc
        # Retain credentials and limits even while the login prompt is suspended.
        required = hosted or production or flag == "true" or bool(username or password) or public_until is not None
        if required and (not username or ":" in username or len(password) < 20):
            raise ValueError(
                "Protected hosting requires DEMO_USERNAME (without ':') and "
                "DEMO_PASSWORD of at least 20 characters."
            )

        def positive(name, default):
            value = int(values.get(name) or default)
            if value < 1:
                raise ValueError(f"{name} must be a positive integer.")
            return value

        return cls(
            required=required,
            username=username,
            password=password,
            public_until=public_until,
            ai_per_minute=positive("AI_REQUESTS_PER_MINUTE", 6),
            ai_per_hour=positive("AI_REQUESTS_PER_HOUR", 60),
            writes_per_minute=positive("WRITE_REQUESTS_PER_MINUTE", 30),
            ai_concurrency=positive("AI_MAX_CONCURRENT", 2),
        )


class DemoLimits:
    """One bounded set of counters, not spoofable per-IP buckets."""

    def __init__(self, settings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.lock = threading.Lock()
        self.events = {name: deque() for name in ("login", "writes", "ai_minute", "ai_hour")}
        self.active = 0

    def reserve(self, buckets, ai=False):
        with self.lock:
            now = self.clock()
            retry = 0
            for name, limit, window in buckets:
                queue = self.events[name]
                while queue and queue[0] <= now - window:
                    queue.popleft()
                if len(queue) >= limit:
                    retry = max(retry, math.ceil(queue[0] + window - now))
            if ai and self.active >= self.settings.ai_concurrency:
                retry = max(retry, 2)
            if retry:
                return retry
            for name, _, _ in buckets:
                self.events[name].append(now)
            if ai:
                self.active += 1
            return 0

    def release(self):
        with self.lock:
            self.active -= 1


class DemoSecurityMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings
        self.limits = DemoLimits(settings)

    def authenticated(self, header):
        if len(header) > 4096:
            return False
        try:
            scheme, token = header.split(" ", 1)
            if scheme.lower() != "basic":
                return False
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (ValueError, UnicodeError, binascii.Error):
            return False
        user_ok = secrets.compare_digest(username.encode(), self.settings.username.encode())
        password_ok = secrets.compare_digest(password.encode(), self.settings.password.encode())
        return user_ok and password_ok

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        headers = {key.lower(): value.decode("latin-1") for key, value in scope["headers"]}

        async def reject(status, detail, extra=None):
            response = JSONResponse(
                {"detail": detail}, status_code=status,
                headers={"Cache-Control": "no-store", **(extra or {})},
            )
            await response(scope, receive, send)

        # Render probes process liveness without exposing graph or model information.
        if path == "/healthz" and method in {"GET", "HEAD"}:
            response = JSONResponse({"status": "ok"}, headers={"Cache-Control": "no-store"})
            return await response(scope, receive, send)

        if self.settings.required and not self.settings.public_access_open() and not self.authenticated(headers.get(b"authorization", "")):
            retry = self.limits.reserve([("login", 30, 60)])
            if retry:
                return await reject(429, "Too many login attempts. Try again shortly.", {"Retry-After": str(retry)})
            return await reject(401, "Demo login required.", {"WWW-Authenticate": 'Basic realm="PromiseGraph demo", charset="UTF-8"'})

        write = method not in {"GET", "HEAD", "OPTIONS"}
        if write:
            origin = headers.get(b"origin")
            if origin and urlparse(origin).netloc != headers.get(b"host"):
                return await reject(403, "Cross-origin writes are disabled.")
            # A cross-site HTML form cannot submit application/json. Browsers
            # must pass the origin check as well as authentication for writes.
            if headers.get(b"content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return await reject(415, "Write requests must use application/json.")

        ai = write and path.rstrip("/") in {"/documents", "/assess", "/api/demo"}
        reserved = False
        if self.settings.required and write:
            buckets = [("writes", self.settings.writes_per_minute, 60)]
            if ai:
                buckets.extend([
                    ("ai_minute", self.settings.ai_per_minute, 60),
                    ("ai_hour", self.settings.ai_per_hour, 3600),
                ])
            retry = self.limits.reserve(buckets, ai=ai)
            if retry:
                return await reject(429, "Demo request limit reached. Try again after the indicated delay.", {"Retry-After": str(retry)})
            reserved = ai

        async def private_send(message):
            if self.settings.required and message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        try:
            # Bound the actual streamed body, including chunked requests without
            # Content-Length, before JSON parsing or any database/model operation.
            if write:
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > self.settings.body_bytes:
                        return await reject(413, "Request body exceeds the 256 KiB limit.")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
                delivered = False

                async def buffered_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, buffered_receive, private_send)
            else:
                await self.app(scope, receive, private_send)
        finally:
            if reserved:
                self.limits.release()
