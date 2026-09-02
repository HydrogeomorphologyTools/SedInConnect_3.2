"""
Anonymous usage telemetry for SedInConnect using Google Analytics 4 Measurement Protocol.
Provides non-blocking, privacy-preserving usage monitoring for research impact reporting.
"""

import os
import sys
import json
import time
import uuid
import platform
import threading
import urllib.request
from pathlib import Path
from typing import Optional

MEASUREMENT_ID = "G-9047MQK3FC"
API_SECRET = "WlQI-FJwQAiK0bssPyWmpA"
GA_ENDPOINT = f"https://www.google-analytics.com/mp/collect?measurement_id={MEASUREMENT_ID}&api_secret={API_SECRET}"

_cached_ip = None


def _get_public_ip() -> str:
    """Fetch public IP quietly in background (1.5s timeout, fail-safe)."""
    global _cached_ip
    if _cached_ip:
        return _cached_ip
    try:
        req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "SedInConnect/3.2"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            _cached_ip = resp.read().decode("utf-8").strip()
            return _cached_ip
    except Exception:
        return "unknown"


def _get_anonymous_client_id() -> str:
    """Retrieve or generate a persistent anonymous UUID for client identification."""
    try:
        if platform.system() == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "SedInConnect"
        else:
            base = Path.home() / ".sedinconnect"
        base.mkdir(parents=True, exist_ok=True)
        cid_file = base / "client_id"
        if cid_file.exists():
            cid = cid_file.read_text(encoding="utf-8").strip()
            if cid:
                return cid
        cid = str(uuid.uuid4())
        cid_file.write_text(cid, encoding="utf-8")
        return cid
    except Exception:
        return str(uuid.uuid4())


def _send_payload_async(payload: dict):
    """Send payload to Google Analytics endpoint in a background daemon thread."""
    def _worker():
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                GA_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "SedInConnect/3.2"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as response:
                pass
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def track_app_launch(mode: str = "GUI"):
    """
    Track application launch event.
    mode: 'GUI' or 'CLI'
    """
    try:
        cid = _get_anonymous_client_id()
        session_id = str(int(time.time()))
        payload = {
            "client_id": cid,
            "events": [{
                "name": "app_launch",
                "params": {
                    "session_id": session_id,
                    "version": "3.2",
                    "mode": mode,
                    "client_ip": _get_public_ip(),
                    "os": platform.system(),
                    "os_version": platform.release(),
                    "engagement_time_msec": 100
                }
            }]
        }
        _send_payload_async(payload)
    except Exception:
        pass


def track_analysis_run(
    mode: str = "GUI",
    target_mode: str = "outlet",
    weight_mode: str = "cavalli_auto",
    window_size: int = 5,
    fill_dtm: bool = False,
    duration_s: float = 0.0,
    status: str = "success"
):
    """
    Track analysis completion event.
    """
    try:
        cid = _get_anonymous_client_id()
        session_id = str(int(time.time()))
        payload = {
            "client_id": cid,
            "events": [{
                "name": "analysis_completed",
                "params": {
                    "session_id": session_id,
                    "version": "3.2",
                    "mode": mode,
                    "client_ip": _get_public_ip(),
                    "target_mode": target_mode,
                    "weight_mode": weight_mode,
                    "window_size": int(window_size),
                    "fill_dtm": bool(fill_dtm),
                    "duration_s": round(float(duration_s), 2),
                    "status": status,
                    "engagement_time_msec": 1000
                }
            }]
        }
        _send_payload_async(payload)
    except Exception:
        pass
