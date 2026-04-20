import sys
import json


def read_message() -> dict:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline().decode("utf-8")
        if line in ("\r\n", "\n", ""):
            break
        if ":" in line:
            key, _, val = line.partition(":")
            headers[key.strip()] = val.strip()
    length = int(headers.get("Content-Length", 0))
    body = sys.stdin.buffer.read(length)
    return json.loads(body)


def write_message(obj: dict) -> None:
    body = json.dumps(obj).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header + body)
    sys.stdout.buffer.flush()


def ok_response(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def error_response(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def tool_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}
