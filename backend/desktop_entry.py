"""PyInstaller 桌面后端入口：绑定回环端口并向 Electron 报告实际端口。"""
from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preferred-port", type=int, default=0)
    parser.add_argument("--parent-pid", type=int, required=True)
    return parser.parse_args()


def reserve_loopback_port(preferred_port: int) -> socket.socket:
    if preferred_port and not 49152 <= preferred_port <= 65535:
        raise ValueError("preferred port must be in the dynamic private range")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", preferred_port))
    except OSError:
        sock.bind(("127.0.0.1", 0))
    sock.listen(2048)
    return sock


def parent_is_alive(parent_pid: int) -> bool:
    if parent_pid <= 0:
        return False
    try:
        import psutil

        return psutil.pid_exists(parent_pid)
    except Exception:
        return True


def main() -> int:
    args = parse_args()
    if os.environ.get("DESKTOP_MODE", "").lower() != "true":
        raise RuntimeError("desktop entry requires DESKTOP_MODE=true")
    if not os.environ.get("DESKTOP_AUTH_TOKEN", ""):
        raise RuntimeError("desktop entry requires DESKTOP_AUTH_TOKEN")

    socket_handle = reserve_loopback_port(args.preferred_port)
    port = int(socket_handle.getsockname()[1])
    from app.main import app

    config = uvicorn.Config(app, log_config=None, access_log=False)
    server = uvicorn.Server(config)
    app.state.request_desktop_shutdown = lambda: setattr(server, "should_exit", True)

    def watch_parent() -> None:
        while not server.should_exit:
            if not parent_is_alive(args.parent_pid):
                server.should_exit = True
                return
            time.sleep(2)

    threading.Thread(target=watch_parent, name="desktop-parent-watchdog", daemon=True).start()
    print(json.dumps({"event": "desktop-listening", "port": port}), flush=True)
    server.run(sockets=[socket_handle])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
