import collections
import json as _json
import sys
import threading
import time
from typing import Dict, List, Optional

import httpx
from httpx_sse import connect_sse


class GameClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        self._http = httpx.AsyncClient(timeout=15.0)
        self._sync_http = httpx.Client(timeout=30.0)

        self._buffer: collections.deque = collections.deque(maxlen=500)
        self._buffer_lock = threading.Lock()
        self._latest_snapshot: Optional[dict] = None
        self._sse_connected = False
        self._sse_events_received = 0
        self._sse_last_event_time = 0.0
        self._sse_thread: Optional[threading.Thread] = None

    def _auth_headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = await self._http.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: Optional[dict] = None) -> dict:
        resp = await self._http.post(
            f"{self.base_url}{path}",
            json=body or {},
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def auto_login(self, username: str, password: str) -> None:
        data = await self._post("/login", {"username": username, "password": password})
        if data.get("ok") and data.get("api_key"):
            self.api_key = data["api_key"]
            print(f"[silent-chaos] logged in as {username}", file=sys.stderr)
        else:
            print(f"[silent-chaos] auto-login failed: {data.get('error')}", file=sys.stderr)

    def start_sse_listener(self) -> None:
        if self._sse_thread and self._sse_thread.is_alive():
            return
        self._sse_thread = threading.Thread(target=self._sse_loop, daemon=True)
        self._sse_thread.start()

    def _sse_loop(self) -> None:
        reconnect_delay = 5.0
        while True:
            if not self.api_key:
                time.sleep(1.0)
                continue
            try:
                self._stream_once()
            except Exception as e:
                print(f"[silent-chaos] SSE error: {e}", file=sys.stderr)
                self._sse_connected = False
            time.sleep(reconnect_delay)

    def _stream_once(self) -> None:
        url = f"{self.base_url}/stream"
        headers = {k: v for k, v in self._auth_headers().items() if k != "Content-Type"}
        with connect_sse(self._sync_http, "GET", url, headers=headers) as event_source:
            self._sse_connected = True
            for sse in event_source.iter_sse():
                event_type = sse.event or "unknown"
                try:
                    data = _json.loads(sse.data) if sse.data else {}
                except Exception:
                    data = {"raw": sse.data}

                entry = {"event": event_type, "data": data, "time": time.time()}
                with self._buffer_lock:
                    self._buffer.append(entry)
                    if event_type == "snapshot":
                        self._latest_snapshot = data

                self._sse_events_received += 1
                self._sse_last_event_time = time.time()

    def get_event_buffer(self, types: Optional[List[str]] = None, limit: int = 50) -> List[dict]:
        with self._buffer_lock:
            events = list(self._buffer)
        if types:
            events = [e for e in events if e["event"] in types]
        return events[-limit:]

    def get_latest_snapshot(self) -> Optional[dict]:
        return self._latest_snapshot

    def sse_status(self) -> dict:
        with self._buffer_lock:
            buf_size = len(self._buffer)
        return {
            "connected": self._sse_connected,
            "events_received": self._sse_events_received,
            "last_event_time": self._sse_last_event_time,
            "buffer_size": buf_size,
        }
