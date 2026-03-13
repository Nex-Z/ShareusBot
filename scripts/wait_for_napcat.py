#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import socket
import sys
import time
from urllib.parse import urlparse


def _load_ws_uri(config_path: str) -> str | None:
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("ws_uri:"):
                value = line.split(":", 1)[1].strip()
                value = re.sub(r"^['\"]|['\"]$", "", value)
                return value or None
    return None


def _parse_host_port(ws_uri: str) -> tuple[str, int] | None:
    parsed = urlparse(ws_uri)
    if not parsed.hostname:
        return None
    if parsed.port:
        return parsed.hostname, parsed.port
    if parsed.scheme in ("wss", "https"):
        return parsed.hostname, 443
    return parsed.hostname, 80


def main() -> int:
    enabled = os.getenv("NAPCAT_WAIT_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not enabled:
        print("[wait-for-napcat] disabled via NAPCAT_WAIT_ENABLED")
        return 0

    config_path = os.getenv("NCATBOT_CONFIG_PATH", "/app/config.yaml")
    ws_uri = _load_ws_uri(config_path)
    if not ws_uri:
        print(f"[wait-for-napcat] ws_uri not found in {config_path}; skip wait")
        return 0

    target = _parse_host_port(ws_uri)
    if not target:
        print(f"[wait-for-napcat] invalid ws_uri: {ws_uri}")
        return 1

    host, port = target
    timeout = int(os.getenv("NAPCAT_WAIT_TIMEOUT", "120"))
    interval = float(os.getenv("NAPCAT_WAIT_INTERVAL", "2"))
    deadline = time.time() + max(1, timeout)

    print(f"[wait-for-napcat] waiting for {host}:{port} (timeout={timeout}s)")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=3):
                print("[wait-for-napcat] napcat is reachable")
                return 0
        except OSError:
            time.sleep(interval)

    print("[wait-for-napcat] timeout waiting for napcat")
    return 1


if __name__ == "__main__":
    sys.exit(main())
