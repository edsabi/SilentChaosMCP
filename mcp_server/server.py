#!/usr/bin/env python3
"""Silent Chaos MCP Server — raw JSON-RPC 2.0 over stdio, no MCP SDK."""

import asyncio
import json
import os
import sys

from client import GameClient
from protocol import (
    error_response,
    ok_response,
    read_message,
    tool_result,
    write_message,
)
from tools import TOOL_LIST, TOOL_REGISTRY

_client = GameClient(
    base_url=os.environ.get("GAME_BASE_URL", "http://localhost:5000"),
    api_key=os.environ.get("GAME_API_KEY") or None,
)


def _handle_initialize(req: dict) -> dict:
    return ok_response(
        req["id"],
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "silent-chaos", "version": "1.0.0"},
        },
    )


def _handle_tools_list(req: dict) -> dict:
    return ok_response(req["id"], {"tools": TOOL_LIST})


async def _handle_tools_call(req: dict) -> dict:
    params = req.get("params", {})
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name not in TOOL_REGISTRY:
        return error_response(req["id"], -32601, f"Unknown tool: {name}")

    try:
        result = await TOOL_REGISTRY[name](_client, args)
        return ok_response(req["id"], tool_result(json.dumps(result, indent=2)))
    except Exception as exc:
        return ok_response(
            req["id"],
            tool_result(json.dumps({"ok": False, "error": str(exc)})),
        )


async def main() -> None:
    username = os.environ.get("GAME_USERNAME")
    password = os.environ.get("GAME_PASSWORD")
    if username and password and not _client.api_key:
        await _client.auto_login(username, password)

    _client.start_sse_listener()

    print("[silent-chaos] MCP server ready", file=sys.stderr)

    while True:
        try:
            msg = read_message()
        except EOFError:
            break
        except Exception as exc:
            print(f"[silent-chaos] read error: {exc}", file=sys.stderr)
            break

        method = msg.get("method", "")
        req_id = msg.get("id")

        if method == "initialize":
            write_message(_handle_initialize(msg))

        elif method in ("notifications/initialized", "notifications/cancelled"):
            pass  # no response for notifications

        elif method == "tools/list":
            write_message(_handle_tools_list(msg))

        elif method == "tools/call":
            write_message(await _handle_tools_call(msg))

        elif method == "ping":
            write_message(ok_response(req_id, {}))

        elif req_id is not None:
            write_message(error_response(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    asyncio.run(main())
