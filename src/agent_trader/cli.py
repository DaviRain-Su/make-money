import asyncio
import inspect
import json
import sys
from typing import List, Optional

from agent_trader.config import load_settings
from agent_trader.demo_smoke import run_demo_smoke_test
from agent_trader.healthcheck import run_local_healthcheck
from agent_trader.runtime_entry import build_runtime_daemon



def _run_maybe_async(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value



def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: cli.py [runtime-once|health-check|demo-smoke <json-payload>]")
        return 2

    command = args[0]
    settings = load_settings()

    if command == "runtime-once":
        daemon = build_runtime_daemon(current_settings=settings, load_open_orders=lambda: [])
        _run_maybe_async(daemon.run_once(send_ping=True))
        if getattr(daemon, "last_error", None):
            print(f"runtime-once failed: {daemon.last_error}")
            return 1
        print("runtime-once complete")
        return 0

    if command == "health-check":
        result = run_local_healthcheck(current_settings=settings)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status") == "ok" else 1

    if command == "demo-smoke":
        if len(args) < 2:
            print("demo-smoke requires JSON payload")
            return 2
        payload = json.loads(args[1])
        result = run_demo_smoke_test(payload, current_settings=settings)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    print(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
